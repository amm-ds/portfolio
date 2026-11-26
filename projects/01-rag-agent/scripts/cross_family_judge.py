"""Cross-family second judge (grade pass 4, experiment E8; spec: pass-3 P2.3).

The committed final_v3 verdicts were judged by the Kimi/Moonshot family
(``kimi-for-coding``). This script runs a second judge from a DIFFERENT model
family over the same claim-judge prompt path so the comparison is judge-only:

- Judge: local Ollama ``qwen2.5:3b`` (Qwen family, Alibaba) at
  ``http://127.0.0.1:11434`` — $0, no hosted calls. Credential check found only
  Moonshot (``LLM_BASE_URL=https://api.kimi.com``) and Ollama in the env; no
  Anthropic/OpenAI/Gemini keys exist, so the spec's local-model fallback
  applies. Digest + family recorded in ``summary.json``.
- Prompt path: the EXACT system prompt + user template of
  ``scripts/label_judge_calibration_v2.py`` (the path that produced the
  committed kimi labels), temperature 0, fixed seed. Judge-only means the
  prompt does not change for the new judge.

Phase 1 (calibration gate, always runs): grade the 30 owner-labelled claims
(``reports/judge_calibration_v2/owner_sample_validated.json`` + chunk texts
from ``owner_sample.json``). Agreement with the owner labels < 25/30 -> STOP:
write the calibration result and exit 1 WITHOUT phase 2.

Phase 2 (judge-only agreement, only if the gate passes): grade the 147
committed ``judge_v2`` claims (``data/judge_v2_claims.json``) and report
Cohen's kappa / % agreement against the committed kimi labels
(``reports/judge_calibration_v2/raw/*.json``).

NOTE on spec step 2 (re-grade the committed final_v3 answers): the final_v3
answer texts and per-claim verdicts were never committed — ``reports/
final_v3_e2e/`` and the run checkpoint carry question traces only (verdict,
faithfulness, claim-state counts; no answer text, no claim text). A judge-only
re-grade of final_v3 has therefore no committed input, and regenerating the
answers would violate "fixed outputs; nothing is selected or tuned". Phase 2
is the strongest judge-only agreement the committed artifacts support; the
blocker is recorded in ``summary.json``.

Every call writes ``raw/<slot>.json`` (model, digest, tokens, $0.00 cost,
cumulative meter, latency, hosts, raw response, parsed label) and the run is
resumable. The meter is $0.00 throughout (local inference); the hosted budget
($2.50 cap / $2.20 stop) is untouched and recorded as such.

    uv run python scripts/cross_family_judge.py            # gate + agreement
    uv run python scripts/cross_family_judge.py --limit 3  # smoke
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "cross_family_judge_2026-11-26"
RAW_DIR = OUT_DIR / "raw"
VALIDATED = ROOT / "reports" / "judge_calibration_v2" / "owner_sample_validated.json"
OWNER_SAMPLE = ROOT / "reports" / "judge_calibration_v2" / "owner_sample.json"
CLAIMS = ROOT / "data" / "judge_v2_claims.json"
KIMI_RAW = ROOT / "reports" / "judge_calibration_v2" / "raw"

MODEL = "qwen2.5:3b"
ENDPOINT = "http://127.0.0.1:11434/api/chat"
TAGS_ENDPOINT = "http://127.0.0.1:11434/api/tags"
VERSION_ENDPOINT = "http://127.0.0.1:11434/api/version"
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
SEED = 44
GATE_THRESHOLD = 25  # of 30 owner-labelled claims (spec: < 25/30 -> STOP)
HOSTED_BUDGET_CAP_USD = 2.50
HOSTED_BUDGET_STOP_USD = 2.20

# EXACT copy of the claim-judge prompt path in
# scripts/label_judge_calibration_v2.py — the comparison must be judge-only.
SYSTEM_PROMPT = """You are a strict claim-verification judge for RAG calibration.

You receive one evidence passage and one claim. Decide whether the claim is
supported by the passage, using ONLY the passage — never outside knowledge. A
claim is supported only if the passage states every fact in it; numbers and
dates must match exactly. If any part is missing, contradicted, or not stated,
the claim is unsupported.

Respond with a JSON object only:
{"label": "supported" | "unsupported", "reason": "one short line"}"""


def label_prompt(claim: dict[str, str]) -> str:
    """EXACT user template of label_judge_calibration_v2.label_prompt."""
    return (
        f"Evidence ({claim['chunk_id']}):\n{claim['chunk_text']}\n\n"
        f"Claim: {claim['claim']}\n\nRespond with JSON only."
    )


def parse_json_block(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in response")
    parsed: dict[str, Any] = json.loads(match.group(0))
    return parsed


def post(payload: dict[str, Any], endpoint: str) -> dict[str, Any]:
    host = re.sub(r"^https?://", "", endpoint).split("/")[0].split(":")[0]
    if host not in LOCAL_HOSTS:
        raise SystemExit(f"STOP: non-local request host: {host}")
    req = urllib.request.Request(  # noqa: S310 - localhost-only guard above
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310 - localhost only
        return dict(json.load(resp))


def ollama_model_meta() -> dict[str, str]:
    tags = _get(TAGS_ENDPOINT)
    version = _get(VERSION_ENDPOINT)
    for entry in tags.get("models", []):
        if entry.get("name") == MODEL:
            details = entry.get("details", {})
            return {
                "model": MODEL,
                "digest": str(entry.get("digest", "")),
                "family": str(details.get("family", "")),
                "parameter_size": str(details.get("parameter_size", "")),
                "quantization": str(details.get("quantization_level", "")),
                "ollama_version": str(version.get("version", "")),
            }
    raise SystemExit(f"STOP: model {MODEL} not installed in local Ollama")


def _get(endpoint: str) -> dict[str, Any]:
    host = re.sub(r"^https?://", "", endpoint).split("/")[0].split(":")[0]
    if host not in LOCAL_HOSTS:
        raise SystemExit(f"STOP: non-local request host: {host}")
    with urllib.request.urlopen(endpoint, timeout=30) as resp:  # noqa: S310 - localhost only
        return dict(json.load(resp))


def judge_one(claim: dict[str, str], slot: str, meta: dict[str, str]) -> dict[str, Any]:
    """One claim through the committed prompt path; raw record persisted."""
    raw_path = RAW_DIR / f"{slot}.json"
    if raw_path.exists():
        return dict(json.loads(raw_path.read_text("utf-8")))
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": label_prompt(claim)},
        ],
        "stream": False,
        "options": {"temperature": 0, "seed": SEED, "num_predict": 512},
    }
    started = time.monotonic()
    body = post(payload, ENDPOINT)
    elapsed = time.monotonic() - started
    content = str(body.get("message", {}).get("content", ""))
    parsed: dict[str, Any] = {}
    try:
        parsed = parse_json_block(content)
        if parsed.get("label") not in {"supported", "unsupported"}:
            raise ValueError(f"bad label: {parsed.get('label')!r}")
    except (ValueError, json.JSONDecodeError) as exc:
        parsed = {"label": None, "reason": f"parse error: {exc}"}
    record: dict[str, Any] = {
        "slot": slot,
        "chunk_id": claim["chunk_id"],
        "model": meta["model"],
        "digest": meta["digest"],
        "usage": {
            "input_tokens": int(body.get("prompt_eval_count", 0)),
            "output_tokens": int(body.get("eval_count", 0)),
        },
        "cost_usd_est": "0.0",
        "latency_s": round(elapsed, 2),
        "request_hosts": ["127.0.0.1"],
        "raw_response": content,
        "label": parsed.get("label"),
        "reason": parsed.get("reason"),
    }
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return record


def cohens_kappa(a: list[str], b: list[str]) -> float:
    """Cohen's kappa for two equal-length label sequences."""
    if len(a) != len(b) or not a:
        raise ValueError("kappa needs equal-length non-empty sequences")
    n = len(a)
    po = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    labels = sorted(set(a) | set(b))
    pe = sum((a.count(lab) / n) * (b.count(lab) / n) for lab in labels)
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float]:
    """Wilson 95% interval — mirrors scripts/run_e2e_eval.wilson."""
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [max(0.0, center - half), min(1.0, center + half)]


def meter(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "n_calls": len(records),
        "input_tokens": sum(int(r["usage"]["input_tokens"]) for r in records),
        "output_tokens": sum(int(r["usage"]["output_tokens"]) for r in records),
        "spend_usd": 0.0,
        "hosted_spend_usd": 0.0,
        "hosted_budget_cap_usd": HOSTED_BUDGET_CAP_USD,
        "hosted_budget_stop_usd": HOSTED_BUDGET_STOP_USD,
        "request_hosts": sorted({h for r in records for h in r["request_hosts"]}),
        "note": "local Ollama inference: $0 API cost; hosted budget untouched",
    }


def run_calibration(meta: dict[str, str], limit: int | None) -> dict[str, Any]:
    """Phase 1: the 30 owner-labelled claims; gate at >= 25/30 vs owner."""
    validated = json.loads(VALIDATED.read_text("utf-8"))
    sample = json.loads(OWNER_SAMPLE.read_text("utf-8"))
    text_by_index = {it["index"]: it["chunk_text"] for it in sample["items"]}
    items = validated["items"][:limit] if limit else validated["items"]
    records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for item in items:
        claim = {
            "claim": item["claim"],
            "chunk_id": item["chunk_id"],
            "chunk_text": text_by_index[item["index"]],
        }
        rec = judge_one(claim, f"cal_{item['index']:03d}", meta)
        records.append(rec)
        rows.append(
            {
                "index": item["index"],
                "chunk_id": item["chunk_id"],
                "owner_label": item["validated_label"],
                "kimi_label": item["kimi_label"],
                "qwen_label": rec["label"],
                "agree_owner": rec["label"] == item["validated_label"],
                "agree_kimi": rec["label"] == item["kimi_label"],
                "reason": rec["reason"],
            }
        )
    n = len(rows)
    n_parse_fail = sum(1 for r in rows if r["qwen_label"] is None)
    matches = sum(1 for r in rows if r["agree_owner"])
    scored = [r for r in rows if r["qwen_label"] is not None]
    qwen_scored = [str(r["qwen_label"]) for r in scored]
    kappa_owner = (
        round(cohens_kappa([r["owner_label"] for r in scored], qwen_scored), 4) if scored else None
    )
    kappa_kimi = (
        round(cohens_kappa([r["kimi_label"] for r in scored], qwen_scored), 4) if scored else None
    )
    result: dict[str, Any] = {
        "n_items": n,
        "n_parse_failures": n_parse_fail,
        "matches_owner": matches,
        "agreement_owner": round(matches / n, 4) if n else 0.0,
        "agreement_owner_wilson95": [round(x, 6) for x in wilson(matches, n)],
        "kappa_owner": kappa_owner,
        "matches_kimi": sum(1 for r in rows if r["agree_kimi"]),
        "kappa_kimi": kappa_kimi,
        "gate_threshold": f">= {GATE_THRESHOLD}/{n} agreement with owner labels",
        "gate_passed": matches >= GATE_THRESHOLD,
        "items": rows,
    }
    (OUT_DIR / "calibration.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    return result


def run_agreement(meta: dict[str, str], limit: int | None) -> dict[str, Any]:
    """Phase 2: the 147 committed judge_v2 claims vs committed kimi labels."""
    claims: list[dict[str, str]] = json.loads(CLAIMS.read_text("utf-8"))
    kimi_labels: dict[int, str] = {}
    for path in sorted(KIMI_RAW.glob("*.json")):
        raw = json.loads(path.read_text("utf-8"))
        kimi_labels[int(raw["index"])] = str(raw["label"])
    indices = list(range(len(claims)))[:limit] if limit else list(range(len(claims)))
    records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for i in indices:
        rec = judge_one(claims[i], f"agree_{i:03d}", meta)
        records.append(rec)
        rows.append(
            {
                "index": i,
                "chunk_id": claims[i]["chunk_id"],
                "kind": claims[i]["kind"],
                "kimi_label": kimi_labels[i],
                "qwen_label": rec["label"],
                "agree_kimi": rec["label"] == kimi_labels[i],
                "agree_kind": rec["label"] == claims[i]["kind"],
                "reason": rec["reason"],
            }
        )
    scored = [r for r in rows if r["qwen_label"] is not None]
    n = len(rows)
    result: dict[str, Any] = {
        "n_items": n,
        "n_parse_failures": sum(1 for r in rows if r["qwen_label"] is None),
        "vs_committed_kimi_labels": {
            "matches": sum(1 for r in scored if r["agree_kimi"]),
            "agreement": round(sum(1 for r in scored if r["agree_kimi"]) / len(scored), 4)
            if scored
            else 0.0,
            "kappa": round(
                cohens_kappa([r["kimi_label"] for r in scored], [r["qwen_label"] for r in scored]),
                4,
            )
            if scored
            else None,
        },
        "vs_construction_kind": {
            "matches": sum(1 for r in scored if r["agree_kind"]),
            "agreement": round(sum(1 for r in scored if r["agree_kind"]) / len(scored), 4)
            if scored
            else 0.0,
            "kappa": round(
                cohens_kappa([r["kind"] for r in scored], [r["qwen_label"] for r in scored]), 4
            )
            if scored
            else None,
        },
        "items": rows,
    }
    (OUT_DIR / "agreement.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="grade only the first N items")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    meta = ollama_model_meta()
    logger.info(
        "cross-family judge: %s (family %s, digest %s) via %s",
        meta["model"],
        meta["family"],
        meta["digest"][:19],
        ENDPOINT,
    )

    calibration = run_calibration(meta, args.limit)
    logger.info(
        "calibration: %d/%d agree with owner (kappa %s); gate %s",
        calibration["matches_owner"],
        calibration["n_items"],
        calibration["kappa_owner"],
        "PASSED" if calibration["gate_passed"] else "FAILED",
    )

    summary: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "experiment": "E8 cross-family second judge (pass-3 P2.3, pass-4 E8)",
        "judge": {**meta, "endpoint": ENDPOINT, "temperature": 0, "seed": SEED},
        "committed_judge": "kimi-for-coding (Moonshot/Kimi family)",
        "prompt_path": "scripts/label_judge_calibration_v2.py SYSTEM_PROMPT + label_prompt "
        "(verbatim; judge-only comparison)",
        "calibration": {k: v for k, v in calibration.items() if k != "items"},
        "final_v3_regrade": {
            "status": "blocked",
            "reason": "final_v3 answer texts and per-claim verdicts were never committed: "
            "reports/final_v3_e2e/ and reports/runs/final_v3-432d6b705715/ carry question "
            "traces only (no answer text, no claim text). A judge-only re-grade has no "
            "committed input; regenerating answers would violate 'fixed outputs; nothing "
            "is selected or tuned'.",
        },
        "meter": None,
    }

    if not calibration["gate_passed"]:
        summary["stop"] = (
            f"calibration {calibration['matches_owner']}/{calibration['n_items']} < "
            f"{GATE_THRESHOLD}/30 owner agreement — STOP per spec; final_v3 NOT re-graded"
        )
        _write_meter_and_summary(summary)
        logger.error("STOP: %s", summary["stop"])
        return 1

    agreement = run_agreement(meta, args.limit)
    summary["agreement_147"] = {k: v for k, v in agreement.items() if k != "items"}
    logger.info(
        "agreement vs committed kimi labels: %s (kappa %s)",
        agreement["vs_committed_kimi_labels"]["agreement"],
        agreement["vs_committed_kimi_labels"]["kappa"],
    )
    _write_meter_and_summary(summary)
    return 0


def _write_meter_and_summary(summary: dict[str, Any]) -> None:
    records = [json.loads(p.read_text("utf-8")) for p in sorted(RAW_DIR.glob("*.json"))]
    summary["meter"] = meter(records)
    (OUT_DIR / "meter.json").write_text(json.dumps(summary["meter"], indent=2) + "\n", "utf-8")
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
