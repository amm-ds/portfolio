"""Metric helpers: pure scoring math, paired cluster bootstrap CIs, peak-capture
and win-rate reports, per-origin scales.

Every function here is a pure numpy computation over the long cell table or
the (origin x horizon x series) window arrays — no model fitting, no I/O.
"""

import math
from typing import Any

import numpy as np

from demand_forecasting.config import ForecastConfig
from demand_forecasting.multistep_constants import COMPARISON_CANDIDATES, FLOOR

# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------


def pinball_loss(y: np.ndarray, q: np.ndarray, tau: float) -> float:
    """Mean pinball (quantile) loss — lower is better."""
    diff = y - q
    return float(np.mean(np.maximum(tau * diff, (tau - 1.0) * diff)))


def order_up_to_cost(
    order: np.ndarray, y: np.ndarray, holding_cost: float, stockout_cost: float
) -> float:
    """Holding + stockout cost of one order-up-to decision (per scored cell).

    ``holding_cost · max(order - actual, 0) + stockout_cost · max(actual -
    order, 0)`` — the order-up-to simulation's cost cell, kept pure so the
    math is hand-testable.
    """
    order = np.asarray(order, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(
        holding_cost * np.maximum(order - y, 0.0).sum()
        + stockout_cost * np.maximum(y - order, 0.0).sum()
    )


def _ladder_quantile(q: float, p10: np.ndarray, p50: np.ndarray, p90: np.ndarray) -> np.ndarray:
    """q-quantile of the committed p10/p50/p90 band ladder (wave 22 newsvendor).

    Linear interpolation between the ladder rungs, linear extrapolation above
    p90 / below p10 (same segment slope), zero-clipped. Pure math, hand-testable:
    with p10=1, p50=3, p90=5 the q=0.8 rung is 3 + 0.3 x (5-3)/0.4 = 4.5.
    """
    lo_slope = (p50 - p10) / (0.5 - 0.1)
    hi_slope = (p90 - p50) / (0.9 - 0.5)
    out = np.where(q <= 0.5, p50 + (q - 0.5) * lo_slope, p50 + (q - 0.5) * hi_slope)
    return np.maximum(out, 0.0)


def _paired_bootstrap_cost(
    cost_a: np.ndarray,
    cost_b: np.ndarray,
    demand: np.ndarray,
    series_codes: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """95% CI on cost-per-unit-demand(A) - cost-per-unit-demand(B).

    Same resampling contract as :func:`_paired_bootstrap_mae` (one shared
    series-index draw per replication, percentile interval); the replicated
    statistic is the resampled-cluster cost ratio difference, so the point
    estimate is (sum A / sum demand) - (sum B / sum demand) over all cells.
    """
    uniques = np.unique(series_codes)
    sum_a = np.array([cost_a[series_codes == i].sum() for i in uniques])
    sum_b = np.array([cost_b[series_codes == i].sum() for i in uniques])
    sum_d = np.array([demand[series_codes == i].sum() for i in uniques])
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, len(uniques), len(uniques))
        denom = sum_d[idx].sum()
        diffs[b] = (sum_a[idx].sum() - sum_b[idx].sum()) / denom if denom > 0 else np.nan
    lo, hi = np.nanquantile(diffs, [0.025, 0.975])
    denom = demand.sum()
    point = (cost_a.sum() - cost_b.sum()) / denom if denom > 0 else float("nan")
    return {
        "diff": float(point),
        "ci95": [float(lo), float(hi)],
        "spans_zero": bool(lo <= 0.0 <= hi),
        "n_boot": n_boot,
        "seed": seed,
    }


def rmsse_pooled(
    err: np.ndarray,
    scale2: np.ndarray,
    volume: np.ndarray,
    series_codes: np.ndarray,
) -> tuple[float, float]:
    """(pooled RMSSE, volume-weighted RMSSE) — M5-style.

    Per series i: ``sqrt(mean(err²) / scale2_i)`` with scale2_i the in-sample
    MSE of the one-step seasonal-naive-7 on the cell's training window
    (scale2 = 0 → the series is excluded, not infinite). The weighted variant
    weights those per-series RMSSEs by the series' training-window volume.
    """
    pooled: list[float] = []
    w_num = 0.0
    w_den = 0.0
    for i in np.unique(series_codes):
        mask = series_codes == i
        s2 = float(scale2[mask][0])
        if s2 > 0:
            r = math.sqrt(float(np.mean(err[mask] ** 2)) / s2)
            pooled.append(r)
            vol = float(volume[mask][0])
            w_num += vol * r
            w_den += vol
    if not pooled:
        return float("nan"), float("nan")
    return float(np.mean(pooled)), (w_num / w_den if w_den > 0 else float("nan"))


def _rmae_cells(cells: dict[str, Any], mask: np.ndarray, pred_key: str) -> float:
    """Relative MAE: candidate pooled MAE / seasonal_naive floor pooled MAE
    over the same masked cells (< 1 = beats the floor). NaN when the floor's
    pooled MAE is 0 (no relative scale exists)."""
    err_c = float(np.abs(cells["pred"][pred_key][mask] - cells["y"][mask]).mean())
    err_f = float(np.abs(cells["pred"][FLOOR][mask] - cells["y"][mask]).mean())
    return err_c / err_f if err_f > 0 else float("nan")


def _rmsse_cells(cells: dict[str, Any], mask: np.ndarray, pred_key: str) -> tuple[float, float]:
    """(pooled, volume-weighted) RMSSE for one candidate over the masked
    cells, M5 convention: the unit is a (series x scored origin) evaluation —
    numerator = MSE of the candidate over that unit's scored horizon days,
    denominator = the in-sample MSE of the one-step seasonal-naive-7 over the
    unit's training window (cells["scale2"], 0-scale units excluded)."""
    err = cells["pred"][pred_key][mask] - cells["y"][mask]
    origins = np.unique(cells["origin"][mask])
    rank = {int(o): k for k, o in enumerate(origins)}
    codes = cells["series"][mask] * len(origins) + np.array(
        [rank[int(o)] for o in cells["origin"][mask]]
    )
    return rmsse_pooled(err, cells["scale2"][mask], cells["volume"][mask], codes)


def _paired_bootstrap_mae(
    err_a: np.ndarray,
    err_b: np.ndarray,
    series_codes: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """95% CI on pooled-MAE(A) - pooled-MAE(B), cluster bootstrap over series.

    One shared index draw per replication resamples SERIES with replacement
    (all cells of a sampled series enter together), so the difference stays
    paired on identical resamples (the projects/05 /10 pattern). Percentile
    interval; ``spans_zero`` marks comparisons the data does not establish.
    """
    abs_a = np.abs(err_a)
    abs_b = np.abs(err_b)
    uniques = np.unique(series_codes)
    sum_a = np.array([abs_a[series_codes == i].sum() for i in uniques])
    sum_b = np.array([abs_b[series_codes == i].sum() for i in uniques])
    cnt = np.array([int((series_codes == i).sum()) for i in uniques], dtype=float)
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, len(uniques), len(uniques))
        denom = cnt[idx].sum()
        diffs[b] = (sum_a[idx].sum() - sum_b[idx].sum()) / denom
    lo, hi = np.quantile(diffs, [0.025, 0.975])
    return {
        "diff": float(abs_a.sum() / cnt.sum() - abs_b.sum() / cnt.sum()),
        "ci95": [float(lo), float(hi)],
        "spans_zero": bool(lo <= 0.0 <= hi),
        "n_boot": n_boot,
        "seed": seed,
    }


def _paired_bootstrap_values(
    val_a: np.ndarray,
    val_b: np.ndarray,
    series_of: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """95% CI on mean(A) - mean(B) over per-window values, clustered by series.

    Same resampling contract as :func:`_paired_bootstrap_mae` (one shared
    series-index draw per replication), but the unit is a scored *window*
    (series x test origin) carrying one value each (peak_mae or peak_recall).
    """
    uniques = np.unique(series_of)
    sum_a = np.array([val_a[series_of == i].sum() for i in uniques])
    sum_b = np.array([val_b[series_of == i].sum() for i in uniques])
    cnt = np.array([int((series_of == i).sum()) for i in uniques], dtype=float)
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, len(uniques), len(uniques))
        denom = cnt[idx].sum()
        diffs[b] = (sum_a[idx].sum() - sum_b[idx].sum()) / denom
    lo, hi = np.quantile(diffs, [0.025, 0.975])
    return {
        "diff": float(val_a.mean() - val_b.mean()),
        "ci95": [float(lo), float(hi)],
        "spans_zero": bool(lo <= 0.0 <= hi),
        "n_boot": n_boot,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Peak-capture metrics (the user's headline concern)
# ---------------------------------------------------------------------------

PEAK_CANDIDATES = (
    "routed",
    "zero",
    "hgb_tweedie",
    "hurdle_hgb",
    "lgbm_tweedie",
    "lgbm_poisson",
    "hurdle_lgbm",
    "peak_weighted_hgb",
    "ensemble_convex",
    "routed_reconciled",
)
# Candidates in the per-series beats-floor win-rate report.
WIN_RATE_CANDIDATES = ("routed", "zero", *COMPARISON_CANDIDATES)


def _window_peak_arrays(y3: np.ndarray, pred3: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """(peak_mae, peak_recall) per (origin, series) window.

    ``y3``/``pred3`` are (n_origins x n_horizons x n_series). ``peak_mae`` is
    the |error| on the window's top-k-by-actual demand days (the top decile:
    ``k = max(1, ceil(0.1 · n_horizons))``); ``peak_recall`` is the share of
    the window's top-5 actual days that the forecast's own top-5 ranked days
    include. Both are per-window scalars — pooled per class downstream.
    """
    n_o, _n_h, n_s = y3.shape
    top_k = np.argsort(y3, axis=1)[:, ::-1][:, :k, :]  # (n_o, k, n_s)
    arange_o = np.arange(n_o)[:, None, None]
    arange_s = np.arange(n_s)[None, None, :]
    peak_mae = np.abs(pred3[arange_o, top_k, arange_s] - y3[arange_o, top_k, arange_s]).mean(axis=1)
    top5 = np.argsort(y3, axis=1)[:, ::-1][:, :5, :]  # (n_o, 5, n_s)
    pred5 = np.argsort(pred3, axis=1)[:, ::-1][:, :5, :]
    recall = np.zeros((n_o, n_s))
    for r in range(n_o):
        for i in range(n_s):
            recall[r, i] = len(set(top5[r, :, i].tolist()) & set(pred5[r, :, i].tolist())) / 5.0
    return peak_mae, recall


def _peak_capture(
    cells: dict[str, Any],
    test: list[int],
    horizons: list[int],
    n_series: int,
    config: ForecastConfig,
) -> dict[str, Any]:
    """Peak-capture report per demand class: peak_mae + peak_recall per
    candidate (routed / zero / hgb_tweedie / hurdle_hgb), each with a paired
    cluster bootstrap CI against the routed and the zero baseline.

    Windows are (series x scored test origin); the peak days are picked within
    each window over the scored h-lattice days, so every compared number is
    an out-of-sample, selection-untouched quantity.
    """
    n_o, n_h = len(test), len(horizons)
    y3 = cells["y"].reshape(n_o, n_h, n_series)
    cls3 = cells["class"].reshape(n_o, n_h, n_series)
    ser3 = cells["series"].reshape(n_o, n_h, n_series)
    classes = [str(c) for c in np.unique(cls3)]
    k = max(1, math.ceil(0.1 * n_h))
    seed = config.seed + 4020  # distinct bootstrap stream
    series_of = ser3[:, 0, :].reshape(-1)  # window -> series

    per_cand: dict[str, dict[str, np.ndarray]] = {}
    for cand in PEAK_CANDIDATES:
        pred3 = cells["pred"][cand].reshape(n_o, n_h, n_series)
        peak_mae, recall = _window_peak_arrays(y3, pred3, k)
        per_cand[cand] = {"peak_mae": peak_mae.reshape(-1), "peak_recall": recall.reshape(-1)}
    per_class: dict[str, Any] = {}
    for cls in classes:
        mask = cls3[:, 0, :].reshape(-1) == cls
        entry: dict[str, Any] = {"n_windows": int(mask.sum())}
        for cand in PEAK_CANDIDATES:
            pm = per_cand[cand]["peak_mae"]
            pr = per_cand[cand]["peak_recall"]
            item: dict[str, Any] = {
                "peak_mae": float(pm[mask].mean()),
                "peak_recall": float(pr[mask].mean()),
            }
            for base in ("routed", "zero"):
                if cand == base:
                    continue
                item[f"peak_mae_vs_{base}"] = _paired_bootstrap_values(
                    pm[mask],
                    per_cand[base]["peak_mae"][mask],
                    series_of[mask],
                    config.bootstrap_reps,
                    seed,
                )
                item[f"peak_recall_vs_{base}"] = _paired_bootstrap_values(
                    pr[mask],
                    per_cand[base]["peak_recall"][mask],
                    series_of[mask],
                    config.bootstrap_reps,
                    seed,
                )
            entry[cand] = item
        per_class[cls] = entry
    return {
        "definition": (
            "per scored window (series x test origin) over the scored h-lattice days: "
            "peak_mae = MAE on the window's top-decile-by-actual demand days "
            f"(k = max(1, ceil(0.1 x {n_h})) = {k}); peak_recall = share of the window's "
            "top-5 actual days whose day ranks in the forecast's own top-5"
        ),
        "candidates": list(PEAK_CANDIDATES),
        "top_k_days": k,
        "top_recall_days": 5,
        "bootstrap": {
            "method": "paired cluster bootstrap over series (windows of a sampled series "
            "enter together), percentile 95% CI",
            "n_boot": config.bootstrap_reps,
            "seed": seed,
        },
        "per_class": per_class,
    }


# ---------------------------------------------------------------------------
# Per-series beats-floor win rates (wave 21: "improve error for EVERY series")
# ---------------------------------------------------------------------------


def _win_rates(
    cells: dict[str, Any], horizons: list[int], config: ForecastConfig
) -> dict[str, Any]:
    """Per-series beats-floor win rate by class and horizon, with a paired
    cluster bootstrap CI on the win rate.

    A series "beats the floor" at horizon h when its summed |error| over the
    scored test origins at that h is strictly below the seasonal-naive
    floor's. The win rate is the share of series (per class) winning that
    per-series comparison; the 95% CI resamples SERIES with replacement (one
    shared index draw per replication across candidates, so the intervals
    stay paired), exactly the cluster-bootstrap contract of the MAE CIs.
    """
    seed = config.seed + 8801  # distinct bootstrap stream
    classes = [str(c) for c in np.unique(cells["class"])]
    n_series_all = int(cells["series"].max()) + 1
    per_class: dict[str, Any] = {}
    for cls in classes:
        cls_mask = cells["class"] == cls
        series_u = np.unique(cells["series"][cls_mask])
        per_h: dict[str, Any] = {}
        for h in horizons:
            mask = cls_mask & (cells["h"] == h)
            ser = cells["series"][mask]
            y = cells["y"][mask]
            floor_s = np.bincount(
                ser, weights=np.abs(cells["pred"][FLOOR][mask] - y), minlength=n_series_all
            )
            win_mat = np.zeros((len(WIN_RATE_CANDIDATES), n_series_all))
            for k, cand in enumerate(WIN_RATE_CANDIDATES):
                cand_s = np.bincount(
                    ser, weights=np.abs(cells["pred"][cand][mask] - y), minlength=n_series_all
                )
                win_mat[k] = cand_s < floor_s
            w_cls = win_mat[:, series_u]  # (n_cand, n_series_in_class)
            rng = np.random.default_rng(seed)
            idx = rng.integers(0, w_cls.shape[1], (config.bootstrap_reps, w_cls.shape[1]))
            rates = w_cls[:, idx].mean(axis=2)  # (n_cand, n_boot)
            h_entry: dict[str, Any] = {}
            for k, cand in enumerate(WIN_RATE_CANDIDATES):
                lo, hi = np.quantile(rates[k], [0.025, 0.975])
                h_entry[cand] = {
                    "win_rate": float(w_cls[k].mean()),
                    "beats_floor_count": int(w_cls[k].sum()),
                    "ci95": [float(lo), float(hi)],
                }
            per_h[str(h)] = h_entry
        per_class[cls] = {"n_series": len(series_u), "per_horizon": per_h}
    return {
        "definition": (
            "per series and horizon: beats-floor = the series' summed |error| over the "
            "scored test origins at that h is strictly below the seasonal_naive floor's; "
            "win_rate = the share of series in the class beating the floor; 95% CI = "
            "percentile interval of a cluster bootstrap over series (one shared index "
            "draw per replication across candidates)"
        ),
        "floor": FLOOR,
        "candidates": list(WIN_RATE_CANDIDATES),
        "bootstrap": {
            "method": "cluster bootstrap over series (one shared index draw per "
            "replication across candidates), percentile 95% CI",
            "n_boot": config.bootstrap_reps,
            "seed": seed,
        },
        "per_class": per_class,
    }


def _scales(units: np.ndarray, origin: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-series (MASE scale, squared seasonal-naive scale, train volume)."""
    diffs = units[7 : origin + 1] - units[: origin + 1 - 7]
    return (
        np.mean(np.abs(diffs), axis=0),
        np.mean(diffs**2, axis=0),
        units[: origin + 1].sum(axis=0),
    )
