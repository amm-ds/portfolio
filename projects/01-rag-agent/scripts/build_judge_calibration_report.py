"""Q3a: judge calibration report over the committed 194-claim label set.

Reads the committed calibration artifacts and writes
``reports/judge_calibration_report.json`` (a new file; existing records are
never overwritten):

- ``data/calibration/claims.jsonl`` — 194 claims with labels by construction
  (supported / unsupported), the Q1 label set.
- ``reports/judge_calibration/results.json`` — local judge (qwen2.5:3b) R7
  run, aggregate metrics only (no per-claim verdicts committed).
- ``reports/judge_calibration_hosted/qwen3_4b-*/predictions.jsonl`` — hosted
  judge (qwen3:4b) per-claim verdicts across two repeat runs.

For each judge the report states the claim false-acceptance rate (FA) with a
Wilson 95% interval under two denominators — the committed R7 convention over
all claims, and the strict unsupported-only denominator — plus Cohen's kappa
against the labels. Where per-claim verdicts exist (hosted judge), kappa gets
a cluster bootstrap 95% interval over claims (seed 42, 2000 resamples); the
local judge ships aggregates only, so its kappa is reported as a point value
with the limitation stated. Fully offline: no model calls, $0 hosted spend.

    uv run python scripts/build_judge_calibration_report.py
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / "data" / "calibration" / "claims.jsonl"
LOCAL_RESULTS = ROOT / "reports" / "judge_calibration" / "results.json"
HOSTED_DIR = ROOT / "reports" / "judge_calibration_hosted"
OUT = ROOT / "reports" / "judge_calibration_report.json"

BOOTSTRAP_REPS = 2000
BOOTSTRAP_SEED = 42


@dataclass(frozen=True)
class Claim:
    id: str
    label: str  # "supported" | "unsupported"


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def cohens_kappa(truth: list[bool], pred: list[bool]) -> float | None:
    """Cohen's kappa on the 2x2 accepted-x-supported table."""
    n = len(truth)
    if n == 0:
        return None
    po = sum(1 for t, p in zip(truth, pred, strict=True) if t == p) / n
    p_yes = sum(pred) / n
    t_yes = sum(truth) / n
    pe = p_yes * t_yes + (1 - p_yes) * (1 - t_yes)
    if pe >= 1.0:
        return None
    return (po - pe) / (1 - pe)


def kappa_bootstrap_ci(
    truth: list[bool], pred: list[bool], reps: int = BOOTSTRAP_REPS, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float] | None:
    """Percentile bootstrap CI for kappa over claims (paired resampling)."""
    n = len(truth)
    if n < 2:
        return None
    rng = random.Random(seed)  # noqa: S311 - bootstrap resampling, not crypto
    stats: list[float] = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        k = cohens_kappa([truth[i] for i in idx], [pred[i] for i in idx])
        if k is not None:
            stats.append(k)
    if not stats:
        return None
    stats.sort()
    lo = stats[max(0, int(0.025 * len(stats)))]
    hi = stats[min(len(stats) - 1, int(0.975 * len(stats)))]
    return (lo, hi)


def load_claims() -> list[Claim]:
    claims = [
        Claim(id=r["id"], label=r["label"])
        for r in (json.loads(line) for line in CLAIMS.read_text().splitlines() if line.strip())
    ]
    bad = [c.id for c in claims if c.label not in ("supported", "unsupported")]
    if bad:
        raise ValueError(f"unexpected labels for {bad[:3]}")
    return claims


def fa_block(claims_n: int, n_unsupported: int, fa_all: int, fa_unsup: int) -> dict[str, Any]:
    """FA rates under both denominators with Wilson intervals."""
    return {
        "n_claims": claims_n,
        "n_unsupported": n_unsupported,
        "false_acceptances_all_claims": fa_all,
        "false_acceptance_rate_all_claims": fa_all / claims_n,
        "fa_wilson95_all_claims": list(wilson_interval(fa_all, claims_n)),
        "false_acceptances_unsupported_only": fa_unsup,
        "false_acceptance_rate_unsupported_only": fa_unsup / n_unsupported,
        "fa_wilson95_unsupported_only": list(wilson_interval(fa_unsup, n_unsupported)),
    }


def local_judge_block(claims: list[Claim]) -> dict[str, Any]:
    r = json.loads(LOCAL_RESULTS.read_text())
    n = int(r["n_claims"])
    n_unsup = sum(1 for c in claims if c.label == "unsupported")
    fa_all = round(float(r["claim_false_acceptance_rate"]) * n)
    block: dict[str, Any] = {
        "id": "local-qwen2.5-3b",
        "model": r["model"],
        "runtime": "local (Ollama)",
        "source": "reports/judge_calibration/results.json",
        "accepts_gate": r["ACCEPTS"],
        "per_claim_verdicts_available": False,
        "committed": {
            "claim_false_acceptance_rate": r["claim_false_acceptance_rate"],
            "claim_false_acceptance_ucb95": r["claim_false_acceptance_ucb95"],
            "claim_false_rejection_rate": r["claim_false_rejection_rate"],
            "cohens_kappa": r["cohens_kappa"],
            "answer_agreement": r["answer_agreement"],
            "repeat_flip_rate": r["repeat_flip_rate"],
            "n_claims": n,
            "n_answers": r["n_answers"],
        },
        "false_rejection_rate": r["claim_false_rejection_rate"],
        "cohens_kappa": r["cohens_kappa"],
        "cohens_kappa_bootstrap95": None,
        "reconciles_with_committed": True,
        "false_acceptances_unsupported_only": None,
        "false_acceptance_rate_unsupported_only": None,
        "fa_wilson95_unsupported_only": None,
        "limitations": (
            "Committed record carries aggregate metrics only; per-claim verdicts "
            "are not stored, so the kappa interval and the strict "
            "unsupported-only false-acceptance count are not derivable from the "
            "record (the committed FA rate uses all 194 claims as denominator)."
        ),
    }
    block.update(fa_block(n, n_unsup, fa_all, 0))
    # fa_block filled unsupported-only fields from a zero count; reset them to
    # unknown — the aggregates do not carry the strict numerator.
    block["false_acceptances_unsupported_only"] = None
    block["false_acceptance_rate_unsupported_only"] = None
    block["fa_wilson95_unsupported_only"] = None
    return block


def hosted_judge_block(claims: list[Claim]) -> dict[str, Any]:
    preds_path = sorted(HOSTED_DIR.glob("qwen3_4b-*/predictions.jsonl"))[-1]
    results = json.loads((HOSTED_DIR / "results.json").read_text())
    by_id = {c.id: c for c in claims}

    runs: dict[int, list[tuple[Claim, bool]]] = {}
    for line in preds_path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        claim = by_id.get(r["id"])
        if claim is None:
            continue
        runs.setdefault(int(r["run"]), []).append((claim, bool(r["judged"])))

    per_run: list[dict[str, Any]] = []
    pooled: list[tuple[Claim, bool]] = []
    for run in sorted(runs):
        rows = runs[run]
        truth = [c.label == "supported" for c, _ in rows]
        pred = [j for _, j in rows]
        fa_all = sum(1 for (c, j) in rows if j and c.label == "unsupported")
        fa_unsup = fa_all  # unsupported-only count is the same numerator
        block = {
            "run": run,
            "n_judged": len(rows),
            "cohens_kappa": cohens_kappa(truth, pred),
        }
        n_unsup_rows = sum(1 for c, _ in rows if c.label == "unsupported")
        block.update(fa_block(len(rows), n_unsup_rows, fa_all, fa_unsup))
        per_run.append(block)
        pooled.extend(rows)

    truth = [c.label == "supported" for c, _ in pooled]
    pred = [j for _, j in pooled]
    fa_all = sum(1 for (c, j) in pooled if j and c.label == "unsupported")
    pooled_block: dict[str, Any] = {
        "n_judged": len(pooled),
        "cohens_kappa": cohens_kappa(truth, pred),
        "cohens_kappa_bootstrap95": list(kappa_bootstrap_ci(truth, pred) or []),
    }
    n_unsup_pooled = sum(1 for c, _ in pooled if c.label == "unsupported")
    pooled_block.update(fa_block(len(pooled), n_unsup_pooled, fa_all, fa_all))

    fa_pooled = pooled_block["false_acceptance_rate_all_claims"]
    committed_fa = float(results["claim_false_acceptance_rate"])
    reconciles = abs(fa_pooled - committed_fa) < 1e-9
    return {
        "id": "hosted-qwen3-4b",
        "model": results["model"],
        "runtime": "hosted",
        "source": str(preds_path.relative_to(ROOT)),
        "accepts_gate": results["ACCEPTS"],
        "per_claim_verdicts_available": True,
        "repeat_runs": len(per_run),
        "committed": {
            "claim_false_acceptance_rate": committed_fa,
            "claim_false_acceptance_ucb95": results["claim_false_acceptance_ucb95"],
            "claim_false_rejection_rate": results["claim_false_rejection_rate"],
            "cohens_kappa": results["cohens_kappa"],
            "answer_agreement": results["answer_agreement"],
            "repeat_flip_rate": results["repeat_flip_rate"],
            "n_claims": results["n_claims"],
        },
        "per_run": per_run,
        "pooled": pooled_block,
        "reconciliation": (
            "Recomputed FA matches the committed aggregate."
            if reconciles
            else (
                "Recomputed pooled FA from the committed per-claim predictions "
                f"({fa_pooled:.4f}) does not match the committed aggregate "
                f"({committed_fa:.4f}); the committed hosted metrics were "
                "produced with different semantics (see the R7/R8 integrity "
                "review) and should not be quoted alongside these recomputed "
                "values."
            )
        ),
        "reconciles_with_committed": reconciles,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    claims = load_claims()
    n_unsup = sum(1 for c in claims if c.label == "unsupported")
    report = {
        "schema_version": "judge-calibration-report-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "method": (
            "Labels by construction from the Q1 calibration set; false acceptance "
            "= an unsupported claim judged supported, reported over all claims (the "
            "committed R7 convention) and over unsupported claims only (strict "
            "denominator); Cohen's kappa on accepted-x-supported with a paired "
            "percentile bootstrap (2000 reps, seed 42) where per-claim verdicts "
            "exist. Fully offline; no model calls."
        ),
        "label_set": {
            "path": "data/calibration/claims.jsonl",
            "n_claims": len(claims),
            "n_supported": len(claims) - n_unsup,
            "n_unsupported": n_unsup,
        },
        "judges": [local_judge_block(claims), hosted_judge_block(claims)],
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    logger.info("wrote %s (%d claims, %d judges)", OUT, len(claims), len(report["judges"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
