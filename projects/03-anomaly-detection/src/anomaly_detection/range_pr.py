"""Range-based PR evaluation with no-skill controls (external evaluation P1).

``average_precision_score`` scores pointwise label/score agreement; the
operational question is different — how do range precision and recall trade
off as the alert threshold moves, under the project's own window-matching
semantics? This module sweeps the threshold over the score quantiles, computes
(range-recall, range-precision) via :func:`anomaly_detection.nab.match_events`,
and integrates the curve (trapezoid, standard (0, 1) start). It also reports
precision/recall at fixed alert budgets (PA%K — the top-k% highest scores
alert), and aggregates a seeded random-scorer ensemble as the no-skill band
every champion number is read against.
"""

from collections.abc import Callable

import numpy as np

from anomaly_detection.nab import LEAD_STEPS, match_events, range_f1


def interp_precision(recalls: np.ndarray, precisions: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Precision interpolated at common recall grid points (for mean curves)."""
    if len(recalls) == 0:
        return np.ones(len(grid))
    return np.asarray(np.interp(grid, recalls, precisions), dtype=float)


def range_pr_points(
    scores: np.ndarray,
    alert_times: np.ndarray,
    windows: list[list[str]],
    step_ns: float,
    lead_steps: int = LEAD_STEPS,
    n_thresholds: int = 16,
) -> tuple[np.ndarray, np.ndarray]:
    """(recall, precision) points over a quantile threshold sweep.

    Thresholds run from the 99th to the 0th score quantile; each point uses
    the window-matching semantics the rest of the evaluation commits to.
    """
    if len(scores) == 0:
        return np.array([0.0]), np.array([1.0])
    # the grid spans the max score down to the minimum quantile: the top
    # threshold fires only the highest scores (precision 1 at low recall),
    # which a pure quantile grid misses when positives sit above the 99th
    # percentile — the operating point an alert system actually lives at
    grid = np.unique(
        np.concatenate(
            (
                [float(scores.max())],
                np.quantile(scores, np.linspace(0.99, 0.0, n_thresholds)),
            )
        )
    )
    recalls: list[float] = []
    precisions: list[float] = []
    # descending thresholds: at each recall level the first point generated is
    # the highest-precision one, so the dedupe below keeps the best
    for threshold in sorted(grid, reverse=True):
        alerts = scores >= float(threshold)
        detected, in_window = match_events(alert_times[alerts], windows, lead_steps, step_ns)
        rf = range_f1(detected, int((~in_window).sum()))
        recalls.append(rf["range_recall"])
        precisions.append(rf["range_precision"])
    order = np.argsort(recalls, kind="stable")
    r = np.asarray(recalls, dtype=float)[order]
    p = np.asarray(precisions, dtype=float)[order]
    # dedupe recall ties, keeping the best precision at each recall level
    keep = np.concatenate(([True], np.diff(r) > 0))
    return np.concatenate(([0.0], r[keep])), np.concatenate(([1.0], p[keep]))


def range_pr_area(
    scores: np.ndarray,
    alert_times: np.ndarray,
    windows: list[list[str]],
    step_ns: float,
    lead_steps: int = LEAD_STEPS,
    n_thresholds: int = 16,
) -> float:
    """Trapezoidal area under the range-PR curve (VUS-PR at lead_steps fixed)."""
    r, p = range_pr_points(scores, alert_times, windows, step_ns, lead_steps, n_thresholds)
    r_ext = np.concatenate((r, [1.0]))
    p_ext = np.concatenate((p, [p[-1] if len(p) else 1.0]))
    area = np.sum((r_ext[1:] - r_ext[:-1]) * (p_ext[1:] + p_ext[:-1]) / 2.0)
    return float(area)


def pa_k(
    scores: np.ndarray,
    alert_times: np.ndarray,
    windows: list[list[str]],
    step_ns: float,
    k_pct: float,
    lead_steps: int = LEAD_STEPS,
) -> dict[str, float]:
    """Precision/recall when only the top-k%% highest scores may alert."""
    n = len(scores)
    k = max(1, round(n * k_pct / 100.0))
    top = np.sort(np.argsort(-scores, kind="stable")[:k])
    detected, in_window = match_events(alert_times[top], windows, lead_steps, step_ns)
    rf = range_f1(detected, int((~in_window).sum()))
    return {"k_pct": float(k_pct), "alerts": int(k), **rf}


def band(
    seeds: range,
    measure: Callable[[int], dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Aggregate a seeded no-skill ensemble: mean + 2.5/97.5 percentiles."""
    draws = [measure(seed) for seed in seeds]
    out: dict[str, dict[str, float]] = {}
    for key in ("range_pr_auc", "pa_k_precision", "pa_k_recall"):
        values = np.array([draw[key] for draw in draws], dtype=float)
        out[key] = {
            "mean": float(values.mean()),
            "p2.5": float(np.percentile(values, 2.5)),
            "p97.5": float(np.percentile(values, 97.5)),
        }
    return out
