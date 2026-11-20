"""Verifier cascade: three-band decision rule calibrated on DEV only.

A claim's committed MiniCheck score ``s`` decides the confident bands;
the uncertain middle band defers to the cached local ``qwen2.5:3b`` verdict:

- ``s >= t_hi``  -> accept
- ``s <= t_lo``  -> reject
- otherwise      -> defer to the local judge (score >= 0.5 accepts)

Thresholds ``(t_lo, t_hi)`` come from a fixed grid over the sorted unique DEV
MiniCheck scores (``t_lo < t_hi``), selected by stratified 5-fold
cross-validation on DEV under a rule frozen before any scoring
(``reports/verifier_cascade_dev/rule.md``). TEST is read once, after
selection, for a descriptive reading only.

Fully offline: MiniCheck scores are committed, the local judge runs on the
owner's Ollama, $0 hosted spend.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

__all__ = [
    "JUDGE_ACCEPT_CUT",
    "assign_folds",
    "cascade_decision",
    "cv_evaluate",
    "fit_final_band",
    "generate_grid",
    "load_minicheck_scores",
    "rubric_prompt",
    "select_band",
]

# Rubric midpoint of judge.py's JudgeVerdict (0-1): at/above accepts.
JUDGE_ACCEPT_CUT = 0.5

Decision = str  # "accept" | "reject" | "defer"


def cascade_decision(score: float, t_lo: float, t_hi: float) -> Decision:
    """Three-band decision; boundaries are inclusive on the confident sides."""
    if t_lo >= t_hi:
        raise ValueError(f"t_lo must be < t_hi, got {t_lo} >= {t_hi}")
    if score >= t_hi:
        return "accept"
    if score <= t_lo:
        return "reject"
    return "defer"


def generate_grid(unique_scores: list[float]) -> list[tuple[float, float]]:
    """Full pair grid from sorted unique DEV scores with t_lo < t_hi."""
    scores = sorted(set(unique_scores))
    return [(lo, hi) for lo in scores for hi in scores if lo < hi]


def assign_folds(
    dev_ids_by_label: dict[str, list[str]], k: int = 5, seed: int = 42
) -> dict[str, int]:
    """Stratified k-fold assignment over DEV ids, per label, fixed seed.

    Returns ``{claim_id: fold_index}``; every DEV id appears exactly once.
    """
    assignments: dict[str, int] = {}
    for label in sorted(dev_ids_by_label):
        ids = sorted(dev_ids_by_label[label])
        random.Random(f"{seed}:{label}").shuffle(ids)  # noqa: S311 - fixed-seed folds
        for position, claim_id in enumerate(ids):
            assignments[claim_id] = position % k
    return assignments


def cv_evaluate(
    band: tuple[float, float],
    folds: dict[str, int],
    dev_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Out-of-fold CV metrics for one band on DEV.

    ``dev_rows`` carries ``id``, ``label`` ("supported"/"unsupported"),
    ``score`` (MiniCheck), and ``judge_accepts`` (cached local verdict with
    unparseable already resolved to False). For each fold, decisions for that
    fold's claims are made with the band applied to MiniCheck and the cached
    judge verdict for deferred claims (the verdicts are run once, cached, and
    identical across folds — the fold split only changes which claims are
    counted out-of-fold).
    """
    t_lo, t_hi = band
    fa = fr = deferred = n_unsup = n_sup = 0
    for fold in sorted(set(folds.values())):
        for row in dev_rows:
            if folds[row["id"]] != fold:
                continue
            decision = cascade_decision(row["score"], t_lo, t_hi)
            supported_label = row["label"] == "supported"
            if decision == "defer":
                deferred += 1
                accepted = row["judge_accepts"]
            else:
                accepted = decision == "accept"
            if supported_label:
                n_sup += 1
                if not accepted:
                    fr += 1
            else:
                n_unsup += 1
                if accepted:
                    fa += 1
    return {
        "t_lo": t_lo,
        "t_hi": t_hi,
        "fa_k": fa,
        "fa_n": n_unsup,
        "fa_rate": round(fa / n_unsup, 4) if n_unsup else None,
        "fr_k": fr,
        "fr_n": n_sup,
        "fr_rate": round(fr / n_sup, 4) if n_sup else None,
        "deferred_k": deferred,
        "deferred_n": n_unsup + n_sup,
        "deferred_share": round(deferred / (n_unsup + n_sup), 4) if (n_unsup + n_sup) else None,
    }


def select_band(
    cv_results: list[dict[str, Any]],
    dev_ids: set[str],
    row_ids: set[str],
    fa_cap: float = 0.10,
    fr_cap: float = 0.10,
) -> dict[str, Any] | None:
    """Apply the frozen selection rule; assert the input rows are DEV only.

    Qualifying bands have CV FA <= fa_cap AND CV FR <= fr_cap; among them the
    lowest deferred share wins, ties to lower FA (then lower t_hi, then lower
    t_lo, for determinism). Returns the winning CV row or None.
    """
    if not row_ids <= dev_ids:
        stray = sorted(row_ids - dev_ids)
        raise ValueError(f"selection input contains non-DEV ids: {stray[:5]}")
    qualifying = [
        r
        for r in cv_results
        if r["fa_rate"] is not None
        and r["fa_rate"] <= fa_cap
        and r["fr_rate"] is not None
        and r["fr_rate"] <= fr_cap
    ]
    if not qualifying:
        return None
    return min(
        qualifying,
        key=lambda r: (r["deferred_share"], r["fa_rate"], r["t_hi"], r["t_lo"]),
    )


def fit_final_band(band: tuple[float, float], dev_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Fit on full DEV: the band is grid values, so fit = full-DEV evaluation."""
    merged = dict(cv_evaluate(band, folds={row["id"]: 0 for row in dev_rows}, dev_rows=dev_rows))
    merged["fit"] = "full DEV (all 96 claims)"
    return merged


def load_minicheck_scores(path: Path) -> dict[str, dict[str, Any]]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return {row["id"]: row for row in rows}


def rubric_prompt(question: str, context: str, answer: str) -> str:
    """The exact user-prompt shape of ``LLMRubricJudge.judge`` in judge.py."""
    return f"Question: {question}\n\nContext:\n{context}\n\nAnswer:\n{answer}"
