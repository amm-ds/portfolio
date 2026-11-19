"""Phase 1: score the 194-claim calibration set with the MiniCheck-FT5 verifier challenger.

Fixed dev/test split (``data/calibration/verifier_split.json``, committed before
any scoring), threshold chosen on DEV only (maximize accuracy, ties to the lower
threshold), TEST scored once at that threshold, then the full set re-scored
twice more on CPU for the decision-flip rate. Pre-registered gate (handoff,
do not change after results):

- TEST FA strict (unsupported accepted): point estimate <= 0.25 AND Wilson 95%
  upper bound < 0.3269 (lower bound of the committed hosted judge's strict
  interval in ``reports/judge_calibration_report.json``);
- TEST false rejection (supported rejected): point estimate <= 0.10;
- flip rate across two CPU passes <= 0.05.

Baselines on the same TEST claims come from the committed hosted judge
predictions (``reports/judge_calibration_hosted/qwen3_4b-*/predictions.jsonl``),
computed per run and pooled — never from the non-reconciling committed
aggregate. The local qwen2.5:3b judge ships aggregates only (no per-claim
verdicts), so it is quoted on all 194 claims with that limitation stated.

Output: NEW files under ``reports/verifier_challenger/`` only. Fully offline
(local checkpoint, CPU, fp32, batch size 1): no hosted calls, $0 spend.

    uv run python scripts/verifier_challenger.py --write-split   # once (Step 1)
    uv run python scripts/verifier_challenger.py                 # once (Step 3)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Script-mode sys.path[0] makes sibling scripts importable; the Wilson helper is
# reused from the Q3a report module per the handoff (no second implementation).
from build_judge_calibration_report import wilson_interval
from portfolio_core.logging import get_logger
from rag_agent.verifier_challenger import (
    CKPT,
    PINNED_REVISION,
    MiniCheckAdapter,
    choose_threshold,
    chunk_doc,
    load_claims,
    load_verifier_split,
    sha256_file,
    write_verifier_split,
)

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "data" / "calibration" / "claims.jsonl"
SPLIT = ROOT / "data" / "calibration" / "verifier_split.json"
OUT_DIR = ROOT / "reports" / "verifier_challenger"
LICENSE = OUT_DIR / "license.md"
HOSTED_PREDICTIONS = (
    ROOT / "reports" / "judge_calibration_hosted" / "qwen3_4b-20261115T125747" / "predictions.jsonl"
)
# Pre-registered gate constants (handoff §Gate — fixed before the run).
FA_RATE_MAX = 0.25
FA_UCB_EXCLUSIVE_MAX = 0.3269
FR_RATE_MAX = 0.10
FLIP_RATE_MAX = 0.05


def _rates(rows: list[dict[str, Any]], decisions: dict[str, bool] | None = None) -> dict[str, Any]:
    """FA strict over unsupported and FR over supported, with Wilson 95%.

    ``rows`` are claim dicts; ``decisions`` maps claim id -> accepted. Without
    it, ``row["judged"]`` (committed hosted predictions) is used.
    """
    unsupported = [r for r in rows if r["label"] == "unsupported"]
    supported = [r for r in rows if r["label"] == "supported"]

    def accepted(row: dict[str, Any]) -> bool:
        return decisions[row["id"]] if decisions is not None else bool(row["judged"])

    fa = sum(1 for r in unsupported if accepted(r))
    fr = sum(1 for r in supported if not accepted(r))
    return {
        "fa_strict": {
            "k": fa,
            "n": len(unsupported),
            "rate": round(fa / len(unsupported), 4) if unsupported else None,
            "wilson95": [round(v, 4) for v in wilson_interval(fa, len(unsupported))],
        },
        "false_rejection": {
            "k": fr,
            "n": len(supported),
            "rate": round(fr / len(supported), 4) if supported else None,
            "wilson95": [round(v, 4) for v in wilson_interval(fr, len(supported))],
        },
    }


def _test_baselines(test_ids: set[str]) -> dict[str, Any]:
    """Hosted-judge FA/FR recomputed on the TEST claims from committed predictions."""
    rows = [
        json.loads(line)
        for line in HOSTED_PREDICTIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    covered = [r for r in rows if r["id"] in test_ids]
    baselines: dict[str, Any] = {}
    for run in sorted({r["run"] for r in covered}):
        baselines[f"hosted_qwen3_4b_run{run}"] = _rates([r for r in covered if r["run"] == run])
    baselines["hosted_qwen3_4b_pooled"] = _rates(covered)
    baselines["n_test_covered"] = len({r["id"] for r in covered})
    baselines["n_test_total"] = len(test_ids)
    baselines["source"] = str(HOSTED_PREDICTIONS.relative_to(ROOT))
    return baselines


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


def build_dev_rows(
    meta: dict[str, Any], by_id: dict[str, dict[str, Any]], scores: dict[str, float]
) -> list[tuple[str, bool, float]]:
    """DEV rows for threshold selection: ``(claim_id, label_supported, score)``.

    Separate from :func:`choose_threshold` so a test can assert the threshold's
    input contains exactly the DEV ids and nothing else.
    """
    return [(cid, by_id[cid]["label"] == "supported", scores[cid]) for cid in meta["dev"]]


def run() -> dict[str, Any]:
    if not SPLIT.exists():
        raise SystemExit(f"split file missing: {SPLIT} (run --write-split first)")
    claims = load_claims(CLAIMS)
    split = load_verifier_split(SPLIT)
    assignments: dict[str, str] = split["assignments"]
    meta = split["meta"]
    by_id = {row["id"]: row for row in claims}
    missing = sorted(set(by_id) - set(assignments))
    if missing:
        raise SystemExit(f"split does not cover {len(missing)} claims, e.g. {missing[:3]}")

    multi_chunk = sum(1 for row in claims if len(chunk_doc(row["evidence"])) > 1)
    logger.info("evidence chunking: %d of %d claims span >1 chunk", multi_chunk, len(claims))

    adapter = MiniCheckAdapter()

    start = time.perf_counter()

    def score_pass() -> dict[str, float]:
        return {
            row["id"]: adapter.score(claim=row["claim"], evidence=row["evidence"]) for row in claims
        }

    scores = score_pass()
    dev_rows = build_dev_rows(meta, by_id, scores)
    threshold = choose_threshold([(label, score) for _, label, score in dev_rows])
    dev_correct = sum(
        1
        for cid in meta["dev"]
        if ((scores[cid] >= threshold) if threshold is not None else False)
        == (by_id[cid]["label"] == "supported")
    )

    test_rows = [by_id[cid] for cid in meta["test"]]
    test_decisions = {
        cid: (scores[cid] >= threshold) if threshold is not None else False for cid in meta["test"]
    }
    test = _rates(test_rows, decisions=test_decisions)
    sensitivity_rows = [r for r in test_rows if r.get("label_note") != "manual_review"]
    sensitivity = _rates(sensitivity_rows, decisions=test_decisions) if sensitivity_rows else None

    flip_a = score_pass()
    flip_b = score_pass()
    flips = sum(
        1
        for cid in by_id
        if ((flip_a[cid] >= threshold) if threshold is not None else False)
        != ((flip_b[cid] >= threshold) if threshold is not None else False)
    )
    max_abs_diff = max(abs(flip_a[cid] - flip_b[cid]) for cid in by_id)
    runtime_s = round(time.perf_counter() - start, 2)

    gate = {
        "fa_rate_max": FA_RATE_MAX,
        "fa_rate_ok": test["fa_strict"]["rate"] is not None
        and test["fa_strict"]["rate"] <= FA_RATE_MAX,
        "fa_ucb_exclusive_max": FA_UCB_EXCLUSIVE_MAX,
        "fa_ucb_ok": test["fa_strict"]["wilson95"][1] < FA_UCB_EXCLUSIVE_MAX,
        "fr_rate_max": FR_RATE_MAX,
        "fr_rate_ok": test["false_rejection"]["rate"] is not None
        and test["false_rejection"]["rate"] <= FR_RATE_MAX,
        "flip_rate_max": FLIP_RATE_MAX,
        "flip_rate_ok": flips / len(claims) <= FLIP_RATE_MAX,
    }
    gate["pass"] = all(gate[key] for key in gate if key.endswith("_ok"))

    metrics: dict[str, Any] = {
        "checkpoint": {
            "name": CKPT,
            "revision": PINNED_REVISION,
            "license": "mit",
            "license_record": str(LICENSE.relative_to(ROOT)),
        },
        "split": {
            "file": str(SPLIT.relative_to(ROOT)),
            "seed": meta["seed"],
            "counts": meta["counts"],
            "source_sha256": meta["source"]["sha256"],
        },
        "threshold": threshold,
        "threshold_rule": "dev accuracy max, ties to lower threshold"
        if threshold is not None
        else "reject_all",
        "dev": {"n": len(meta["dev"]), "accuracy": round(dev_correct / len(meta["dev"]), 4)},
        "test": test,
        "test_sensitivity_excl_manual_review": sensitivity,
        "baselines_on_test": _test_baselines(set(meta["test"])),
        "local_baseline_all_claims": {
            "judge": "local qwen2.5:3b",
            "fa_strict_all_claims": 0.4433,
            "fa_wilson95_all_claims": [0.3752, 0.5136],
            "source": "reports/judge_calibration/results.json (committed aggregate)",
            "limitation": "per-claim verdicts not committed; cannot restrict to TEST ids",
        },
        "flips": {
            "n": flips,
            "rate": round(flips / len(claims), 4),
            "max_abs_score_diff": max_abs_diff,
        },
        "chunking": {"n_multi_chunk": multi_chunk, "n_claims": len(claims)},
        "gate": gate,
        "runtime_seconds": runtime_s,
        "n_claims": len(claims),
        "generated_at": datetime.now(UTC).isoformat(),
        "commit": _commit(),
        "hosted_calls": 0,
    }
    metrics["checkpoint"]["license_text_sha256"] = (
        sha256_file(LICENSE) if LICENSE.exists() else None
    )

    predictions = [
        {
            "id": row["id"],
            "split": assignments[row["id"]],
            "label": row["label"],
            "kind": row.get("kind"),
            "label_note": row.get("label_note"),
            "score": round(scores[row["id"]], 6),
            "decision": test_decisions.get(row["id"]) if assignments[row["id"]] == "test" else None,
            "flip_pass_a": round(flip_a[row["id"]], 6),
            "flip_pass_b": round(flip_b[row["id"]], 6),
        }
        for row in claims
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "predictions.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in predictions),
        encoding="utf-8",
    )
    report = _report_md(metrics)
    (OUT_DIR / "report.md").write_text(report, encoding="utf-8")
    logger.info("gate pass=%s; written to %s", gate["pass"], OUT_DIR)
    return metrics


def _report_md(metrics: dict[str, Any]) -> str:
    test = metrics["test"]
    gate = metrics["gate"]
    lines = [
        "# Verifier challenger Phase 1 report",
        "",
        f"Generated: {metrics['generated_at']} (commit `{metrics['commit']}`)",
        "",
        "## Checkpoint",
        "",
        f"- `{metrics['checkpoint']['name']}` revision `{metrics['checkpoint']['revision']}`",
        f"- License: {metrics['checkpoint']['license']}"
        f" (record: {metrics['checkpoint']['license_record']})",
        f"- License text sha256: `{metrics['checkpoint']['license_text_sha256']}`",
        "",
        "## Split",
        "",
        f"- File: `{metrics['split']['file']}`, seed {metrics['split']['seed']}",
        f"- Counts per label: `{json.dumps(metrics['split']['counts'])}`",
        f"- claims.jsonl sha256: `{metrics['split']['source_sha256']}`",
        "",
        "## Threshold (DEV only)",
        "",
        f"- `{metrics['threshold']}` ({metrics['threshold_rule']}); DEV n={metrics['dev']['n']},"
        f" accuracy {metrics['dev']['accuracy']}",
        "",
        "## TEST results (n per label above)",
        "",
    ]
    for name, block in (("FA strict (unsupported accepted)", test["fa_strict"]),):
        lines.append(
            f"- {name}: {block['k']}/{block['n']} = {block['rate']}, Wilson 95% {block['wilson95']}"
        )
    fr = test["false_rejection"]
    lines.append(
        f"- False rejection (supported rejected): {fr['k']}/{fr['n']} = {fr['rate']},"
        f" Wilson 95% {fr['wilson95']}"
    )
    if metrics["test_sensitivity_excl_manual_review"]:
        s = metrics["test_sensitivity_excl_manual_review"]
        lines += [
            "",
            "### Sensitivity: TEST excluding `manual_review` rows",
            "",
            f"- FA strict: {s['fa_strict']['k']}/{s['fa_strict']['n']} = {s['fa_strict']['rate']},"
            f" Wilson 95% {s['fa_strict']['wilson95']}",
            f"- False rejection: {s['false_rejection']['k']}/{s['false_rejection']['n']} ="
            f" {s['false_rejection']['rate']}, Wilson 95% {s['false_rejection']['wilson95']}",
        ]
    lines += ["", "## Baselines on the same TEST claims", ""]
    baselines = metrics["baselines_on_test"]
    for key in sorted(k for k in baselines if k.startswith("hosted_")):
        b = baselines[key]
        lines.append(
            f"- {key}: FA strict {b['fa_strict']['k']}/{b['fa_strict']['n']} ="
            f" {b['fa_strict']['rate']}, Wilson 95% {b['fa_strict']['wilson95']}; FR"
            f" {b['false_rejection']['k']}/{b['false_rejection']['n']} ="
            f" {b['false_rejection']['rate']}"
        )
    lines.append(
        f"- covered {baselines['n_test_covered']}/{baselines['n_test_total']} TEST ids"
        f" (source: `{baselines['source']}`)"
    )
    local = metrics["local_baseline_all_claims"]
    lines += [
        f"- {local['judge']} on ALL 194 claims (aggregate, no per-claim verdicts committed):"
        f" FA strict {local['fa_strict_all_claims']}, Wilson 95% {local['fa_wilson95_all_claims']}",
        "",
        "## Flip rate (two full CPU re-scores)",
        "",
        f"- {metrics['flips']['n']}/{metrics['n_claims']} = {metrics['flips']['rate']};"
        f" max |score_a - score_b| = {metrics['flips']['max_abs_score_diff']:.6f}",
        f"- chunking: {metrics['chunking']['n_multi_chunk']} multi-chunk claims of"
        f" {metrics['chunking']['n_claims']}",
        "",
        "## Gate (pre-registered)",
        "",
        f"- FA rate <= {gate['fa_rate_max']}: {test['fa_strict']['rate']} ->"
        f" {'PASS' if gate['fa_rate_ok'] else 'FAIL'}",
        f"- FA Wilson UCB < {gate['fa_ucb_exclusive_max']}:"
        f" {test['fa_strict']['wilson95'][1]} -> {'PASS' if gate['fa_ucb_ok'] else 'FAIL'}",
        f"- FR rate <= {gate['fr_rate_max']}: {test['false_rejection']['rate']} ->"
        f" {'PASS' if gate['fr_rate_ok'] else 'FAIL'}",
        f"- Flip rate <= {gate['flip_rate_max']}: {metrics['flips']['rate']} ->"
        f" {'PASS' if gate['flip_rate_ok'] else 'FAIL'}",
        f"- **Overall: {'PASS' if gate['pass'] else 'FAIL'}**",
        "",
        f"Runtime {metrics['runtime_seconds']} s on CPU (fp32, batch size 1),"
        " no hosted calls ($0).",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write-split",
        action="store_true",
        help="write data/calibration/verifier_split.json and exit (before any scoring)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.write_split:
        payload = write_verifier_split(CLAIMS, SPLIT, seed=args.seed)
        print(json.dumps({"seed": payload["seed"], "counts": payload["counts"]}, indent=2))
        print(f"written: {SPLIT}")
        return
    metrics = run()
    print(json.dumps(metrics["gate"], indent=2))
    print(f"written: {OUT_DIR}")


if __name__ == "__main__":
    main()
