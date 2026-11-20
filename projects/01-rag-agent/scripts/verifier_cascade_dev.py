"""Verifier cascade, DEV-only calibration (see reports/verifier_cascade_dev/rule.md).

Modes:

- ``--write-rule-artifacts`` (Step 1): write ``folds.json`` (stratified 5-fold
  over DEV by label, seed 42) and print the sha256 records for rule.md.
- ``--cache-verdicts`` (Step 2): run the forced-local ``qwen2.5:3b`` judge on
  all 194 calibration claims once (judge.py rubric prompt + JudgeVerdict
  parsing) and cache per-claim verdicts. Unparseable verdicts count as
  unsupported and are reported as a count.
- ``--select`` (Step 4): 5-fold CV over the frozen grid on DEV, apply the
  frozen selection rule, fit the chosen band on full DEV; writes
  ``metrics.json``, ``predictions.jsonl`` (DEV decisions), ``report.md``.
- ``--test-reading`` (Step 5, only if a band qualified): apply the frozen final
  thresholds to TEST once; appends the descriptive reading to the artifacts.

Fully offline: forced-local Settings (env kwargs beat the .env file), local
Ollama only, $0 hosted spend.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Script-mode sys.path[0] makes sibling scripts importable; the Wilson helper is
# reused from the Q3a report module (no second implementation).
from build_judge_calibration_report import wilson_interval
from portfolio_core.logging import get_logger
from rag_agent.verifier_cascade import (
    JUDGE_ACCEPT_CUT,
    assign_folds,
    cascade_decision,
    cv_evaluate,
    fit_final_band,
    generate_grid,
    load_minicheck_scores,
    rubric_prompt,
    select_band,
)

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "data" / "calibration" / "claims.jsonl"
SPLIT = ROOT / "data" / "calibration" / "verifier_split.json"
SCORES = ROOT / "reports" / "verifier_challenger" / "predictions.jsonl"
OUT_DIR = ROOT / "reports" / "verifier_cascade_dev"
FOLDS = OUT_DIR / "folds.json"
VERDICTS = OUT_DIR / "local_verdicts.jsonl"
METRICS = OUT_DIR / "metrics.json"
PREDICTIONS = OUT_DIR / "predictions.jsonl"
REPORT = OUT_DIR / "report.md"
MODEL = "qwen2.5:3b"


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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


def _load_split() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(SPLIT.read_text(encoding="utf-8"))
    return payload


def write_rule_artifacts() -> None:
    split = _load_split()
    dev_by_label: dict[str, list[str]] = {}
    claims = [
        json.loads(line) for line in CLAIMS.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    labels = {row["id"]: row["label"] for row in claims}
    for claim_id in split["dev"]:
        dev_by_label.setdefault(labels[claim_id], []).append(claim_id)
    folds = assign_folds(dev_by_label, k=5, seed=split["seed"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FOLDS.write_text(
        json.dumps(
            {
                "seed": split["seed"],
                "k": 5,
                "stratified_by": "label",
                "scope": "DEV only (verifier_split.json dev rows)",
                "assignments": {cid: folds[cid] for cid in sorted(folds)},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"folds": str(FOLDS.relative_to(ROOT))}, indent=2))
    print(f"scores sha256: {_sha256(SCORES)}")
    print(f"split  sha256: {_sha256(SPLIT)}")
    print(f"folds  sha256: {_sha256(FOLDS)}")
    print(f"claims sha256: {_sha256(CLAIMS)}")


def _ollama_digest(model: str) -> str:
    with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=10) as resp:
        payload = json.load(resp)
    for entry in payload.get("models", []):
        if entry.get("name") == model:
            return str(entry.get("digest", "unknown"))
    raise SystemExit(f"model {model} not present in Ollama; stop per handoff")


def cache_verdicts() -> None:
    import os

    os.environ["OLLAMA_MODEL"] = MODEL
    digest = _ollama_digest(MODEL)
    from portfolio_core.config import Settings
    from portfolio_core.llm import build_model
    from portfolio_eval.rag import JudgeVerdict
    from pydantic_ai import Agent, NativeOutput
    from rag_agent.judge import RUBRIC_SYSTEM_PROMPT
    from rag_agent.provider import model_settings_for_provider

    claims = [
        json.loads(line) for line in CLAIMS.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    local_settings = Settings(llm_base_url=None, llm_api_key=None)  # type: ignore[call-arg]  # pydantic-settings by field name; forced local, never hosted
    agent = Agent(
        build_model(settings=local_settings),
        output_type=NativeOutput(JudgeVerdict),
        system_prompt=RUBRIC_SYSTEM_PROMPT,
        model_settings=model_settings_for_provider(),
        retries={"output": 2},
    )
    rows: list[dict[str, Any]] = []
    unparseable = 0
    start = time.perf_counter()
    for claim in claims:
        prompt = rubric_prompt(claim["question"], claim["evidence"], claim["claim"])
        try:
            result = agent.run_sync(prompt)
            score = float(result.output.score)
            rows.append(
                {
                    "id": claim["id"],
                    "judge_accepts": score >= JUDGE_ACCEPT_CUT,
                    "judge_score": score,
                    "judge_reason": result.output.reason,
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
                    "judge_score": None,
                    "judge_reason": None,
                    "parse_ok": False,
                }
            )
    elapsed = round(time.perf_counter() - start, 2)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    header = {
        "model": MODEL,
        "ollama_digest": digest,
        "judge_accept_cut": JUDGE_ACCEPT_CUT,
        "system_prompt_sha256": _sha256_text(RUBRIC_SYSTEM_PROMPT),
        "unparseable": unparseable,
        "n_claims": len(rows),
        "runtime_seconds": elapsed,
        "generated_at": datetime.now(UTC).isoformat(),
        "commit": _commit(),
        "hosted_calls": 0,
    }
    # Single-line header keeps the file strict jsonl (one object per line) so
    # consumers can skip the header with lines[1:].
    VERDICTS.write_text(
        json.dumps(header, ensure_ascii=False)
        + "\n"
        + "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    print(json.dumps(header, indent=2))


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_verdicts() -> dict[str, dict[str, Any]]:
    lines = VERDICTS.read_text(encoding="utf-8").splitlines()
    return {row["id"]: row for row in (json.loads(line) for line in lines[1:] if line.strip())}


def _rows_for(
    ids: list[str], scores: dict[str, Any], verdicts: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        {
            "id": cid,
            "label": scores[cid]["label"],
            "score": scores[cid]["score"],
            "kind": scores[cid].get("kind"),
            "label_note": scores[cid].get("label_note"),
            "judge_accepts": bool(verdicts[cid]["judge_accepts"]),
        }
        for cid in ids
    ]


def select() -> dict[str, Any]:
    split = _load_split()
    scores = load_minicheck_scores(SCORES)
    verdicts = _load_verdicts()
    folds_payload = json.loads(FOLDS.read_text(encoding="utf-8"))
    folds = {cid: int(f) for cid, f in folds_payload["assignments"].items()}
    dev_ids = sorted(split["dev"])
    dev_rows = _rows_for(dev_ids, scores, verdicts)
    grid = generate_grid([row["score"] for row in dev_rows])
    logger.info(
        "grid: %d bands over %d unique DEV scores",
        len(grid),
        len({r["score"] for r in dev_rows}),
    )
    start = time.perf_counter()
    cv_results = [cv_evaluate(band, folds, dev_rows) for band in grid]
    qualifying = [
        r
        for r in cv_results
        if r["fa_rate"] is not None
        and r["fa_rate"] <= 0.10
        and r["fr_rate"] is not None
        and r["fr_rate"] <= 0.10
    ]
    chosen = select_band(
        cv_results,
        dev_ids=set(dev_ids),
        row_ids={row["id"] for row in dev_rows},
    )
    # Full per-band table committed alongside metrics; the report carries the
    # summary (every qualifying band if few, extremes over all bands).
    (OUT_DIR / "cv_results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in cv_results), encoding="utf-8"
    )
    metrics: dict[str, Any] = {
        "rule": "reports/verifier_cascade_dev/rule.md",
        "folds": "reports/verifier_cascade_dev/folds.json",
        "cv_results": "reports/verifier_cascade_dev/cv_results.jsonl",
        "grid_size": len(grid),
        "unique_dev_scores": len({r["score"] for r in dev_rows}),
        "cv": {
            "k": 5,
            "n_bands": len(cv_results),
            "n_qualifying": len(qualifying),
            "qualifying": qualifying if len(qualifying) <= 20 else qualifying[:20],
            "extremes": {
                "min_fa": min(cv_results, key=lambda r: (r["fa_rate"], r["fr_rate"])),
                "min_fr": min(cv_results, key=lambda r: (r["fr_rate"], r["fa_rate"])),
                "min_deferred": min(
                    cv_results, key=lambda r: (r["deferred_share"], r["fa_rate"] + r["fr_rate"])
                ),
            },
        },
        "runtime_seconds": round(time.perf_counter() - start, 2),
        "generated_at": datetime.now(UTC).isoformat(),
        "commit": _commit(),
        "hosted_calls": 0,
    }
    if chosen is None:
        metrics["final_band"] = None
        metrics["note"] = "no qualifying band on DEV CV; TEST not read"
    else:
        band = (chosen["t_lo"], chosen["t_hi"])
        fit = fit_final_band(band, dev_rows)
        metrics["final_band"] = {"t_lo": band[0], "t_hi": band[1], "fit": fit}
    _write_predictions(metrics, split, scores, verdicts, dev_rows, test_reading=None)
    REPORT.write_text(_report_md(metrics), encoding="utf-8")
    METRICS.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"chosen": metrics["final_band"]}, indent=2))
    print(f"written: {OUT_DIR}")
    return metrics


def _decide(row: dict[str, Any], t_lo: float, t_hi: float) -> tuple[str, bool]:
    decision = cascade_decision(row["score"], t_lo, t_hi)
    if decision == "defer":
        return decision, row["judge_accepts"]
    return decision, decision == "accept"


def _write_predictions(
    metrics: dict[str, Any],
    split: dict[str, Any],
    scores: dict[str, Any],
    verdicts: dict[str, Any],
    dev_rows: list[dict[str, Any]],
    test_reading: dict[str, Any] | None,
) -> None:
    band = (
        (metrics["final_band"]["t_lo"], metrics["final_band"]["t_hi"])
        if metrics.get("final_band")
        else None
    )
    rows: list[dict[str, Any]] = []
    for row in dev_rows:
        decision, accepted = _decide(row, *band) if band else ("not_selected", False)
        rows.append(
            {
                "id": row["id"],
                "split": "dev",
                "label": row["label"],
                "score": row["score"],
                "band": decision,
                "cascade_accepts": accepted if band else None,
                "judge_accepts": row["judge_accepts"],
            }
        )
    if test_reading:
        for row in test_reading["rows"]:
            rows.append(
                {
                    "id": row["id"],
                    "split": "test",
                    "label": row["label"],
                    "score": row["score"],
                    "band": row["band"],
                    "cascade_accepts": row["cascade_accepts"],
                    "judge_accepts": row["judge_accepts"],
                }
            )
    PREDICTIONS.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def test_reading() -> None:
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    if not metrics.get("final_band"):
        print("no qualifying band; TEST not read (per rule)")
        return
    band = (metrics["final_band"]["t_lo"], metrics["final_band"]["t_hi"])
    split = _load_split()
    scores = load_minicheck_scores(SCORES)
    verdicts = _load_verdicts()
    test_rows = _rows_for(sorted(split["test"]), scores, verdicts)
    fa = fr = deferred = n_unsup = n_sup = 0
    decided: list[dict[str, Any]] = []
    for row in test_rows:
        band_name, accepted = _decide(row, *band)
        if band_name == "defer":
            deferred += 1
        decided.append(
            {
                **row,
                "band": band_name,
                "cascade_accepts": accepted,
            }
        )
        if row["label"] == "supported":
            n_sup += 1
            if not accepted:
                fr += 1
        else:
            n_unsup += 1
            if accepted:
                fa += 1
    reading = {
        "label": "second use of TEST; descriptive; not used for selection",
        "t_lo": band[0],
        "t_hi": band[1],
        "fa_strict": {
            "k": fa,
            "n": n_unsup,
            "rate": round(fa / n_unsup, 4),
            "wilson95": [round(v, 4) for v in wilson_interval(fa, n_unsup)],
        },
        "false_rejection": {
            "k": fr,
            "n": n_sup,
            "rate": round(fr / n_sup, 4),
            "wilson95": [round(v, 4) for v in wilson_interval(fr, n_sup)],
        },
        "deferred": {
            "k": deferred,
            "n": n_sup + n_unsup,
            "share": round(deferred / (n_sup + n_unsup), 4),
        },
        "rows": decided,
    }
    metrics["test_reading"] = {k: v for k, v in reading.items() if k != "rows"}
    dev_rows = _rows_for(sorted(split["dev"]), scores, verdicts)
    _write_predictions(metrics, split, scores, verdicts, dev_rows, test_reading=reading)
    REPORT.write_text(_report_md(metrics), encoding="utf-8")
    METRICS.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics["test_reading"], indent=2))
    print(f"written: {OUT_DIR}")


def _band_line(prefix: str, r: dict[str, Any]) -> str:
    return (
        f"{prefix} t=[{r['t_lo']:.4f}, {r['t_hi']:.4f}]"
        f" FA {r['fa_k']}/{r['fa_n']} = {r['fa_rate']}"
        f" FR {r['fr_k']}/{r['fr_n']} = {r['fr_rate']}"
        f" deferred {r['deferred_k']}/{r['deferred_n']} = {r['deferred_share']}"
    )


def _report_md(metrics: dict[str, Any]) -> str:
    lines = [
        "# Verifier cascade DEV calibration report",
        "",
        f"Generated: {metrics['generated_at']} (commit `{metrics['commit']}`)",
        "",
        f"- Grid: {metrics['grid_size']} bands over {metrics['unique_dev_scores']}"
        f" unique DEV MiniCheck scores; folds: 5-fold stratified by label, seed 42",
        f"- CV qualifying bands (FA <= 0.10 AND FR <= 0.10): {metrics['cv']['n_qualifying']}"
        f" of {metrics['cv']['n_bands']}",
    ]
    if metrics.get("final_band"):
        fit = metrics["final_band"]["fit"]
        lines += [
            "",
            "## Chosen band (full-DEV fit)",
            "",
            f"- t_lo = {metrics['final_band']['t_lo']}, t_hi = {metrics['final_band']['t_hi']}",
            _band_line("- fit:", fit),
        ]
    else:
        lines += [
            "",
            "## No qualifying band",
            "",
            "No (t_lo, t_hi) grid band met FA <= 0.10 AND FR <= 0.10 on"
            " cross-validated DEV. TEST was not read.",
        ]
    qualifying = metrics["cv"].get("qualifying") or []
    if qualifying:
        listed = len(qualifying)
        lines += [
            "",
            f"## Qualifying bands ({listed} listed"
            + (", selection order" if metrics["cv"]["n_qualifying"] <= 20 else ", first 20")
            + "; full table in cv_results.jsonl)",
            "",
        ]
        for r in qualifying:
            lines.append("- " + _band_line("", r))
    extremes = metrics["cv"].get("extremes") or {}
    if extremes:
        lines += ["", "## Extremes over all bands", ""]
        for key, label in (
            ("min_fa", "Lowest CV FA"),
            ("min_fr", "Lowest CV FR"),
            ("min_deferred", "Lowest CV deferred share"),
        ):
            if key in extremes:
                lines.append("- " + _band_line(f"{label}:", extremes[key]))
    if metrics.get("test_reading"):
        t = metrics["test_reading"]
        lines += [
            "",
            "## TEST reading — " + t["label"],
            "",
            f"- FA strict: {t['fa_strict']['k']}/{t['fa_strict']['n']} ="
            f" {t['fa_strict']['rate']}, Wilson 95% {t['fa_strict']['wilson95']}",
            f"- False rejection: {t['false_rejection']['k']}/{t['false_rejection']['n']} ="
            f" {t['false_rejection']['rate']}, Wilson 95% {t['false_rejection']['wilson95']}",
            f"- Deferred: {t['deferred']['k']}/{t['deferred']['n']} = {t['deferred']['share']}",
        ]
    lines += [
        "",
        f"Runtime {metrics['runtime_seconds']} s, no hosted calls ($0).",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write-rule-artifacts", action="store_true")
    group.add_argument("--cache-verdicts", action="store_true")
    group.add_argument("--select", action="store_true")
    group.add_argument("--test-reading", action="store_true")
    args = parser.parse_args()
    if args.write_rule_artifacts:
        write_rule_artifacts()
    elif args.cache_verdicts:
        cache_verdicts()
    elif args.select:
        select()
    elif args.test_reading:
        test_reading()
    else:
        parser.error("choose one mode")


if __name__ == "__main__":
    main()
