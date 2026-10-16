"""Qini evaluation and profit curves for targeting policies.

Qini curve: sort customers by a policy's score (descending) and plot, at each
targeted fraction f, the incremental conversions

    inc(f) = n_t(f) * [rate_treated(f) - rate_control(f)]

where n_t(f) counts treated customers in the top-f slice and the rates are the
slice's conversion rates by arm. At f=1 this equals n_t * (p_t - p_c), the
difference-in-means incremental conversions; the random-targeting baseline is
the straight line from (0, 0) to that point. The Qini coefficient is the area
between the model curve and the random line (trapezoid rule) — the analogue of
AUROC for uplift, in units of conversions x fraction.

Profit under the campaign cost model: targeting the top-f slice mails
f * N emails and earns inc(f) * revenue, so

    profit(f) = inc(f) * revenue - f * N * cost_per_email.

`revenue_per_conversion` is the measured mean spend among converters — revenue,
not margin: the snapshot exposes no COGS, so profit here is revenue minus the
email send cost alone.
"""

from typing import Any

import numpy as np

EPS = 1e-12


def qini_points(
    treatment: np.ndarray, outcome: np.ndarray, score: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """(fractions, incremental conversions) of the Qini curve, including (0, 0).

    Slice convention: a slice with no control rows counts its treated
    conversions as fully incremental (control rate 0); a slice with no treated
    rows mails nobody and contributes 0. At f=1 the curve ends at
    n_t * (p_t - p_c), the difference-in-means incremental conversions.
    """
    treatment = np.asarray(treatment, dtype=int)
    outcome = np.asarray(outcome, dtype=float)
    score = np.asarray(score, dtype=float)
    order = np.argsort(-score, kind="stable")
    t = treatment[order]
    y = outcome[order]
    n = len(y)
    nt = np.cumsum(t)
    nc = np.cumsum(1 - t)
    st = np.cumsum(y * t)
    sc = np.cumsum(y * (1 - t))
    # Slice-level rates (see docstring for the empty-slice convention).
    rate_t = np.where(nt > 0, st / np.maximum(nt, 1), 0.0)
    rate_c = np.where(nc > 0, sc / np.maximum(nc, 1), 0.0)
    inc = nt * (rate_t - rate_c)
    fractions = np.arange(1, n + 1) / n
    return np.concatenate([[0.0], fractions]), np.concatenate([[0.0], inc])


def trapezoid(x: np.ndarray, y: np.ndarray) -> float:
    """Area under a curve by the trapezoid rule."""
    return float(np.trapezoid(y, x))


def qini_coefficient(treatment: np.ndarray, outcome: np.ndarray, score: np.ndarray) -> float:
    """AUQC(policy) - AUQC(random): area between the model curve and the random line."""
    fractions, inc = qini_points(treatment, outcome, score)
    inc_all = inc[-1]
    area_model = trapezoid(fractions, inc)
    area_random = inc_all / 2.0  # straight line (0,0) -> (1, inc_all)
    return float(area_model - area_random)


def incremental_at_full(treatment: np.ndarray, outcome: np.ndarray) -> float:
    """Difference-in-means incremental conversions at f=1: n_t * (p_t - p_c)."""
    treatment = np.asarray(treatment, dtype=int)
    outcome = np.asarray(outcome, dtype=float)
    n_t = treatment.sum()
    p_t = outcome[treatment == 1].mean()
    p_c = outcome[treatment == 0].mean()
    return float(n_t * (p_t - p_c))


def profit_curve(
    fractions: np.ndarray,
    incremental: np.ndarray,
    n_total: int,
    revenue_per_conversion: float,
    cost_per_email: float,
) -> np.ndarray:
    """profit(f) = incremental(f) * revenue - mailed(f) * cost_per_email."""
    fractions = np.asarray(fractions, dtype=float)
    incremental = np.asarray(incremental, dtype=float)
    mailed = fractions * n_total
    return incremental * revenue_per_conversion - mailed * cost_per_email


def uplift_by_decile(
    treatment: np.ndarray,
    outcome: np.ndarray,
    score: np.ndarray,
    n_deciles: int,
) -> dict[str, np.ndarray]:
    """Per-decile predicted vs empirical uplift (rate_treated - rate_control)."""
    treatment = np.asarray(treatment, dtype=int)
    outcome = np.asarray(outcome, dtype=float)
    score = np.asarray(score, dtype=float)
    ranks = np.argsort(np.argsort(score, kind="stable"), kind="stable")
    # Decile 1 = highest scores (the targeting priority order).
    decile = (n_deciles - 1) - np.minimum((ranks * n_deciles) // max(len(score), 1), n_deciles - 1)
    pred = np.zeros(n_deciles)
    emp = np.zeros(n_deciles)
    n_t = np.zeros(n_deciles)
    n_c = np.zeros(n_deciles)
    for d in range(n_deciles):
        mask = decile == d
        if not mask.any():
            continue
        pred[d] = score[mask].mean()
        td = treatment[mask] == 1
        n_t[d] = int(td.sum())
        n_c[d] = int((~td).sum())
        rate_t = outcome[mask][td].mean() if td.any() else np.nan
        rate_c = outcome[mask][~td].mean() if (~td).any() else np.nan
        emp[d] = rate_t - rate_c
    return {
        "decile": np.arange(1, n_deciles + 1),
        "mean_score": pred,
        "empirical_uplift": emp,
        "n_treated": n_t,
        "n_control": n_c,
    }


# ---------------------------------------------------------------------------
# Paired bootstrap uncertainty (Qini coefficient, profit-at-budget, curves)
# ---------------------------------------------------------------------------


def percentile_ci(values: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
    """Central (1 - alpha) percentile interval, e.g. alpha=0.05 -> the 95% CI."""
    values = np.asarray(values, dtype=float)
    return float(np.quantile(values, alpha / 2)), float(np.quantile(values, 1 - alpha / 2))


def ci_spans_zero(ci: tuple[float, float]) -> bool:
    """True when the interval covers 0 — the comparison is not established."""
    return ci[0] <= 0.0 <= ci[1]


def bootstrap_policy_stats(
    treatment: np.ndarray,
    outcome: np.ndarray,
    scores: dict[str, np.ndarray],
    *,
    budget: float,
    n_total: int,
    revenue_per_conversion: float,
    cost_per_email: float,
    n_boot: int,
    seed: int,
    band_grid: np.ndarray | None = None,
) -> dict[str, Any]:
    """Paired nonparametric bootstrap of the per-policy evaluation read.

    Each replication resamples ROWS with replacement (one shared index draw for
    every policy, so model-vs-model differences are paired on the same
    resample) and recomputes, per policy: the Qini coefficient, the profit at
    the budget fraction, and — when ``band_grid`` is given — the Qini curve
    interpolated onto that grid (for figure bands). Deterministic under
    ``seed``; n_total/mail cost enter exactly as in the point estimates.

    Returns {"qini": {policy: (n_boot,)}, "profit_at_budget": {policy: (n_boot,)},
    "band": {policy: (lo, hi)}, "band_grid": grid or None}.
    """
    treatment = np.asarray(treatment, dtype=int)
    outcome = np.asarray(outcome, dtype=float)
    score_arrs = {p: np.asarray(s, dtype=float) for p, s in scores.items()}
    n = len(outcome)
    grid = None if band_grid is None else np.asarray(band_grid, dtype=float)
    if grid is not None and (grid.ndim != 1 or grid[0] != 0.0 or grid[-1] != 1.0):
        raise ValueError("band_grid must be 1-D from 0.0 to 1.0")

    qini_b: dict[str, list[float]] = {p: [] for p in score_arrs}
    profit_b: dict[str, list[float]] = {p: [] for p in score_arrs}
    band_b: dict[str, list[np.ndarray]] = {p: [] for p in score_arrs}
    rng = np.random.default_rng(seed)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        t_b, y_b = treatment[idx], outcome[idx]
        for policy, s in score_arrs.items():
            fr, inc = qini_points(t_b, y_b, s[idx])
            # Qini coefficient without re-sorting: area minus the random line.
            qini_b[policy].append(trapezoid(fr, inc) - inc[-1] / 2.0)
            k = int(np.argmin(np.abs(fr - budget)))
            profit_b[policy].append(
                float(
                    profit_curve(
                        np.array([fr[k]]),
                        np.array([inc[k]]),
                        n_total,
                        revenue_per_conversion,
                        cost_per_email,
                    )[0]
                )
            )
            if grid is not None:
                band_b[policy].append(np.interp(grid, fr, inc))

    bands: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if grid is not None:
        for policy, curves in band_b.items():
            mat = np.vstack(curves)
            bands[policy] = (
                np.quantile(mat, 0.025, axis=0),
                np.quantile(mat, 0.975, axis=0),
            )
    return {
        "qini": {p: np.asarray(v) for p, v in qini_b.items()},
        "profit_at_budget": {p: np.asarray(v) for p, v in profit_b.items()},
        "band": bands,
        "band_grid": grid,
    }
