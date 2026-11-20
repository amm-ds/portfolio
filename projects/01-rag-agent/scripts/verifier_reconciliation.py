"""Reconcile the local-judge gap: same 194 claims, both prompts, one code path.

The cascade report cached rubric-prompt (judge.py) verdicts from the local
qwen2.5:3b and found FA 23/194 = 0.1186, against the committed 0.4433
(86/194) produced by ``calibrate_judge.py``'s strict entailment prompt. This
check runs the entailment prompt through the identical forced-local call and
parsing used by the cascade cache, then compares both prompts on the same
claims to say whether the gap is the prompt or a bug.

Modes:

- ``--run-entailment``: score all 194 claims with the entailment prompt
  (``calibrate_judge.CLAIM_PROMPT`` + the inline system prompt copied
  verbatim below, asserted against the source), forced-local qwen2.5:3b,
  ``NativeOutput(ClaimVerdict)`` — the cascade cache's exact construction.
  Writes ``reports/verifier_reconciliation/entailment_verdicts.jsonl``.
- ``--compare``: pure comparison of the rubric cache (read-only) and the
  entailment verdicts; writes ``metrics.json`` and ``report.md``.

Fully offline: forced-local Settings (env kwargs beat the .env file), local
Ollama only, $0 hosted spend.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Script-mode sys.path[0] makes sibling scripts importable; the Wilson helper
# is reused from the Q3a report module (no second implementation).
from build_judge_calibration_report import wilson_interval
from portfolio_core.logging import get_logger

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "data" / "calibration" / "claims.jsonl"
CALIBRATE_JUDGE = ROOT / "scripts" / "calibrate_judge.py"
RUBRIC_CACHE = ROOT / "reports" / "verifier_cascade_dev" / "local_verdicts.jsonl"
OUT_DIR = ROOT / "reports" / "verifier_reconciliation"
ENTAILMENT_VERDICTS = OUT_DIR / "entailment_verdicts.jsonl"
METRICS = OUT_DIR / "metrics.json"
REPORT = OUT_DIR / "report.md"
MODEL = "qwen2.5:3b"
EXPECTED_DIGEST = "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b"
COMMITTED_FA_ALL_CLAIMS_K = 86  # 0.4433 * 194, committed judge_calibration aggregate
RECON_TOLERANCE_CLAIMS = 1

# Verbatim copy of the inline system prompt in calibrate_judge.evaluate()'s
# local judge Agent, kept as the exact source literals (adjacent string
# concatenation in the original). The test suite asserts each fragment appears
# verbatim in calibrate_judge.py, so this cannot drift from the traced source.
ENTAILMENT_SYSTEM_PROMPT_FRAGMENTS = (
    "You check whether claims are entailed by retrieved evidence. You are ",
    "strict: unsupported means the evidence does not state it. You never ",
    "use outside knowledge.",
)
ENTAILMENT_SYSTEM_PROMPT = "".join(ENTAILMENT_SYSTEM_PROMPT_FRAGMENTS)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - fixed well-known VCS binary
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:  # broad: outside a checkout the commit is unknown
        return "unknown"


def _ollama_digest(model: str) -> str:
    with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=10) as resp:
        payload = json.load(resp)
    for entry in payload.get("models", []):
        if entry.get("name") == model:
            return str(entry.get("digest", "unknown"))
    raise SystemExit(f"model {model} not present in Ollama; stop per handoff")


def run_entailment() -> dict[str, Any]:
    digest = _ollama_digest(MODEL)
    if digest != EXPECTED_DIGEST:
        raise SystemExit(f"digest mismatch: {digest} != {EXPECTED_DIGEST}; stop per handoff")
    source = CALIBRATE_JUDGE.read_text(encoding="utf-8")
    if not all(fragment in source for fragment in ENTAILMENT_SYSTEM_PROMPT_FRAGMENTS):
        raise SystemExit("entailment system prompt not verbatim in calibrate_judge.py; stop")

    os.environ["OLLAMA_MODEL"] = MODEL
    from calibrate_judge import CLAIM_PROMPT, ClaimVerdict
    from portfolio_core.config import Settings
    from portfolio_core.llm import build_model
    from pydantic_ai import Agent, NativeOutput
    from rag_agent.provider import model_settings_for_provider

    claims = [
        json.loads(line) for line in CLAIMS.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    local_settings = Settings(llm_base_url=None, llm_api_key=None)  # type: ignore[call-arg]  # pydantic-settings by field name; forced local, never hosted
    agent = Agent(
        build_model(settings=local_settings),
        output_type=NativeOutput(ClaimVerdict),
        system_prompt=ENTAILMENT_SYSTEM_PROMPT,
        model_settings=model_settings_for_provider(),
        retries={"output": 2},
    )
    rows: list[dict[str, Any]] = []
    unparseable = 0
    start = time.perf_counter()
    for claim in claims:
        prompt = CLAIM_PROMPT.format(
            question=claim["question"], evidence=claim["evidence"], claim=claim["claim"]
        )
        try:
            result = agent.run_sync(prompt)
            accepts = bool(result.output.supported)
            rows.append(
                {
                    "id": claim["id"],
                    "judge_accepts": accepts,
                    "supported": accepts,
                    "reason": result.output.reason,
                    "parse_ok": True,
                }
            )
        except Exception as exc:  # broad: one stubborn claim must not kill the pass
            logger.warning("claim %s unparseable (%s); counting as unsupported", claim["id"], exc)
            unparseable += 1
            rows.append(
                {
                    "id": claim["id"],
                    "judge_accepts": False,
                    "supported": None,
                    "reason": None,
                    "parse_ok": False,
                }
            )
    header = {
        "model": MODEL,
        "ollama_digest": digest,
        "prompt_source": (
            "scripts/calibrate_judge.py::CLAIM_PROMPT + evaluate() inline system prompt"
        ),
        "system_prompt_sha256": _sha256_text(ENTAILMENT_SYSTEM_PROMPT),
        "claim_prompt_sha256": _sha256_text(CLAIM_PROMPT),
        "unparseable": unparseable,
        "n_claims": len(rows),
        "runtime_seconds": round(time.perf_counter() - start, 2),
        "generated_at": datetime.now(UTC).isoformat(),
        "commit": _commit(),
        "hosted_calls": 0,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ENTAILMENT_VERDICTS.write_text(
        json.dumps(header, ensure_ascii=False)
        + "\n"
        + "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    print(json.dumps(header, indent=2))
    return header


def _load_verdict_rows(path: Path) -> dict[str, dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {row["id"]: row for row in (json.loads(line) for line in lines[1:] if line.strip())}


def rates(verdicts: dict[str, dict[str, Any]], labels: dict[str, str]) -> dict[str, dict[str, Any]]:
    """FA all-claims (denominator 194), FA strict (unsupported), FR (supported)."""
    rows = [(labels[cid], v["judge_accepts"]) for cid, v in verdicts.items()]
    unsupported = [a for lab, a in rows if lab == "unsupported"]
    supported = [a for lab, a in rows if lab == "supported"]
    fa_all = sum(1 for lab, a in rows if lab == "unsupported" and a)
    fa_strict = sum(1 for a in unsupported if a)
    fr = sum(1 for a in supported if not a)
    n_all = len(rows)
    return {
        "fa_all_claims": {
            "k": fa_all,
            "n": n_all,
            "rate": round(fa_all / n_all, 4),
            "wilson95": [round(x, 4) for x in wilson_interval(fa_all, n_all)],
        },
        "fa_strict_unsupported": {
            "k": fa_strict,
            "n": len(unsupported),
            "rate": round(fa_strict / len(unsupported), 4),
            "wilson95": [round(x, 4) for x in wilson_interval(fa_strict, len(unsupported))],
        },
        "false_rejection_supported": {
            "k": fr,
            "n": len(supported),
            "rate": round(fr / len(supported), 4),
            "wilson95": [round(x, 4) for x in wilson_interval(fr, len(supported))],
        },
    }


def confusion_2x2(
    rubric: dict[str, dict[str, Any]],
    entailment: dict[str, dict[str, Any]],
    labels: dict[str, str],
) -> dict[str, dict[str, int]]:
    """2x2 of rubric verdict (rows) against entailment verdict (cols), per gold label."""
    table: dict[str, dict[str, int]] = {}
    for claim_id in sorted(rubric):
        gold = labels[claim_id]
        cell = table.setdefault(
            gold,
            {"accept_accept": 0, "accept_reject": 0, "reject_accept": 0, "reject_reject": 0},
        )
        r = "accept" if rubric[claim_id]["judge_accepts"] else "reject"
        e = "accept" if entailment[claim_id]["judge_accepts"] else "reject"
        cell[f"{r}_{e}"] += 1
    return table


def agreement(
    rubric: dict[str, dict[str, Any]], entailment: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    same = sum(
        1
        for claim_id in rubric
        if rubric[claim_id]["judge_accepts"] == entailment[claim_id]["judge_accepts"]
    )
    n = len(rubric)
    return {"k": same, "n": n, "share": round(same / n, 4)}


def compare() -> dict[str, Any]:
    rubric = _load_verdict_rows(RUBRIC_CACHE)
    entailment = _load_verdict_rows(ENTAILMENT_VERDICTS)
    labels = {
        row["id"]: row["label"]
        for row in (
            json.loads(line)
            for line in CLAIMS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    rubric_rates = rates(rubric, labels)
    entailment_rates = rates(entailment, labels)
    fa_all_k = entailment_rates["fa_all_claims"]["k"]
    reproduced = abs(fa_all_k - COMMITTED_FA_ALL_CLAIMS_K) <= RECON_TOLERANCE_CLAIMS
    decision = (
        "gap is the prompt: the cascade result stands for the rubric prompt; "
        "the committed local number is for the entailment prompt"
        if reproduced
        else "the committed 0.4433 or the cache path is wrong; discrepancy reported, "
        "cascade result unchanged (per handoff: stop, do not change the cascade result)"
    )
    metrics: dict[str, Any] = {
        "rubric": {
            "source": str(RUBRIC_CACHE.relative_to(ROOT)),
            "prompt": (
                "src/rag_agent/judge.py RUBRIC_SYSTEM_PROMPT + Question/Context/Answer user prompt"
            ),
            "rates": rubric_rates,
        },
        "entailment": {
            "source": str(ENTAILMENT_VERDICTS.relative_to(ROOT)),
            "prompt": "scripts/calibrate_judge.py CLAIM_PROMPT + evaluate() inline system prompt",
            "rates": entailment_rates,
        },
        "agreement": agreement(rubric, entailment),
        "confusion_2x2_by_gold": confusion_2x2(rubric, entailment, labels),
        "reconciliation": {
            "committed_fa_all_claims": "0.4433 (86/194)",
            "entailment_fa_all_claims": entailment_rates["fa_all_claims"],
            "tolerance_claims": RECON_TOLERANCE_CLAIMS,
            "reproduced": reproduced,
            "decision": decision,
        },
        "generated_at": datetime.now(UTC).isoformat(),
        "commit": _commit(),
        "hosted_calls": 0,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    METRICS.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(_report_md(metrics), encoding="utf-8")
    print(json.dumps(metrics["reconciliation"], indent=2))
    print(f"written: {OUT_DIR}")
    return metrics


def _rate_line(name: str, block: dict[str, Any]) -> str:
    return (
        f"| {name} | {block['fa_all_claims']['k']}/{block['fa_all_claims']['n']}"
        f" = {block['fa_all_claims']['rate']} {block['fa_all_claims']['wilson95']} |"
        f" {block['fa_strict_unsupported']['k']}/{block['fa_strict_unsupported']['n']}"
        f" = {block['fa_strict_unsupported']['rate']}"
        f" {block['fa_strict_unsupported']['wilson95']} |"
        f" {block['false_rejection_supported']['k']}/{block['false_rejection_supported']['n']}"
        f" = {block['false_rejection_supported']['rate']}"
        f" {block['false_rejection_supported']['wilson95']} |"
    )


def _report_md(metrics: dict[str, Any]) -> str:
    lines = [
        "# Verifier reconciliation report (local judge)",
        "",
        f"Generated: {metrics['generated_at']} (commit `{metrics['commit']}`)",
        "",
        "| prompt | FA all claims (Wilson 95%) | FA strict (Wilson 95%) | FR (Wilson 95%) |",
        "|---|---|---|---|",
        _rate_line("rubric (judge.py)", metrics["rubric"]["rates"]),
        _rate_line("entailment (calibrate_judge.py)", metrics["entailment"]["rates"]),
        "",
        f"- Agreement between prompts: {metrics['agreement']['k']}/{metrics['agreement']['n']}"
        f" = {metrics['agreement']['share']}",
        "",
        "## 2x2 rubric x entailment, by gold label",
        "",
    ]
    for gold, cell in sorted(metrics["confusion_2x2_by_gold"].items()):
        lines.append(f"- {gold}: {cell}")
    recon = metrics["reconciliation"]
    lines += [
        "",
        "## Reconciliation against committed 0.4433",
        "",
        f"- Entailment FA all claims: {recon['entailment_fa_all_claims']['k']}/"
        f"{recon['entailment_fa_all_claims']['n']}"
        f" (tolerance ±{recon['tolerance_claims']} claim around 86)",
        f"- Reproduced: **{recon['reproduced']}**",
        f"- Decision: {recon['decision']}",
        "",
        "No hosted calls ($0).",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-entailment", action="store_true")
    group.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    if args.run_entailment:
        run_entailment()
    else:
        compare()


if __name__ == "__main__":
    main()
