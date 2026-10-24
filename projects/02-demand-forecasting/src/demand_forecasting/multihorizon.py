"""Direct multi-horizon forecasting track — protocol ``direct_multihorizon_v1``.

The nowcast track (evaluate.py) answers "tomorrow, given today". This module
answers the question replenishment actually asks: **the next 14 days, issued
once per week**, with each horizon modelled directly:

- **Direct per-horizon models** — one model per horizon
  ``h ∈ config.multistep_horizons``. Features for horizon *h* are the calendar
  of the target date (known in advance) plus lags aged ≥ *h* days relative to
  the target: ``lag_h = units(target - h)``, ``lag_{h+7}``, ``lag_{h+14}``.
  Relative to the origin (issue date *t*, target *t+h*) these are
  ``units(t)``, ``units(t-7)``, ``units(t-14)`` — so **no actual within *h*
  days of the target is ever referenced**, by construction (leakage-proof
  tested with tainted panels). The learner is the champion-config HGB
  (``config.hgb_tuned``) with the series identity as a hi/lo pair of native
  categoricals (HGB caps categorical cardinality at 255; the exact pair
  (id // 64, id % 64) keeps both cardinalities small and memory flat — a
  dense one-hot over 1,600 series would not survive parallel origin fits).
- **Weekly rolling origins** — origin = last training date; the forecast
  window is the 14 days *starting the day after the origin* (no embargo gap —
  the 57-day hole of the nowcast layout is gone). Origins are 7 days apart,
  capped at ``config.multistep_n_origins`` by dropping the oldest (the exact
  weekly cadence is preserved; the cap is documented). The LAST
  ``config.multistep_test_origins`` origins are the test set — scored once,
  never read for selection; the earlier origins select (per-series routing
  method, conformal widths).
- **Routing** — series in the intermittent/lumpy quadrants (ADI ≥ 1.32, see
  intermittent.py) are routed to the best *statistical* method (zero /
  seasonal_naive / Croston / SBA / TSB), chosen per series on the selection
  origins only; smooth/erratic series stay on the direct HGB. Selection on
  train origins only is property-tested (shuffling the test origins' actuals
  leaves the routing unchanged).
- **Uncertainty** — per horizon: quantile HGBs (p10/p50/p90, pinball loss
  reported) plus a split-conformal ±q80 width calibrated on the selection
  origins, zero-clipped and sorted. Sparse (routed) series get an honest
  sparse band instead: P(any sale) + a quantile ladder of the training
  history, which cannot collapse to a zero-width interval.
- **Decision metric** — an order-up-to policy simulation (service level τ →
  order = quantile_τ of the forecast distribution; holding + stockout cost
  against actuals), champion vs seasonal-naive policy, per demand class, cost
  assumptions documented in the JSON. Labelled a simulation — no savings
  claims.
- **Paired bootstrap** — every headline comparison (per-class champion-vs-floor
  and champion-vs-naive at h=7/h=14, model-rank gaps, routing before/after)
  carries a 95% cluster bootstrap CI over (series x scored test origins):
  series are resampled with replacement, one shared index draw per
  replication so differences stay paired (the pattern from projects/05 /10).

Outputs are merged into the track's metrics.json (``_multistep`` block — the
per-model nowcast blocks stay untouched), probabilistic.json (``multistep``
key), evaluation_metadata.json (``multi_horizon`` block) and four new figures
(unit-incompatible metrics never share an axis).
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import polars as pl
from joblib import Parallel, delayed
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_json
from sklearn.ensemble import HistGradientBoostingRegressor

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.evaluate import _json_safe
from demand_forecasting.intermittent import (
    ADI_THRESHOLD,
    CV2_THRESHOLD,
    SPARSE_CLASSES,
    STATISTICAL_METHODS,
    classify_panel,
    statistical_forecast,
)
from demand_forecasting.probabilistic import (
    CALIBRATION_TOL,
    TARGET_COVERAGE,
    calibration_verdict,
)

logger = get_logger(__name__)

PROTOCOL = "direct_multihorizon_v1"
# Target-relative lag ages: lag_h, lag_{h+7}, lag_{h+14} (all ≥ h days old).
LAG_AGES = (0, 7, 14)
# Lag features need units(origin-14), so training origins start at day 14.
MIN_LAG_ORIGIN = 14
ORIGIN_SPACING_DAYS = 7
# Quantile levels for the learner's forecast distribution.
QUANTILES_MS = (0.1, 0.5, 0.9)
# Sparse-band quantile ladder levels (over the training-window demand history).
LADDER_LEVELS = (0.5, 0.8, 0.9, 0.95)

CANDIDATES = ("routed", "direct_hgb", "seasonal_naive", "zero", "croston", "sba", "tsb")
CHAMPION = "routed"
FLOOR = "seasonal_naive"
NAIVE = "zero"


# ---------------------------------------------------------------------------
# Panel → matrix + calendar
# ---------------------------------------------------------------------------


def panel_matrix(panel: pl.DataFrame) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Pivot the panel to (dates, series_ids, units) dense numpy arrays."""
    p = panel.with_columns((pl.col("store") + "|" + pl.col("product")).alias("series_id")).sort(
        ["date", "series_id"]
    )
    wide = p.pivot(index="date", on="series_id", values="units").sort("date")
    series_ids = [str(c) for c in wide.columns if c != "date"]
    units = wide.drop("date").to_numpy().astype(float)
    dates = wide["date"].to_numpy()
    return dates, series_ids, units


def _calendar_features(dates: np.ndarray) -> np.ndarray:
    """The nowcast calendar block (7 columns), as a pure function of date.

    Columns: dow (1=Mon..7=Sun), is_weekend, month, iso week, doy sin/cos, day
    ordinal (trend counter). Deterministic and known in advance — leakage-free.
    """
    py_dates = dates.astype("datetime64[D]").astype(object)
    epoch = np.datetime64("0001-01-01")
    ordinals = (dates.astype("datetime64[D]") - epoch).astype(np.int64) + 1
    dow = np.array([d.weekday() + 1 for d in py_dates], dtype=float)  # 1=Mon
    is_weekend = (dow >= 6).astype(float)
    months = np.array([d.month for d in py_dates], dtype=float)
    weeks = np.array([int(d.isocalendar().week) for d in py_dates], dtype=float)
    doy = np.array([d.timetuple().tm_yday for d in py_dates], dtype=float)
    ang = doy * math.tau / 365.25
    return np.column_stack(
        [dow, is_weekend, months, weeks, np.sin(ang), np.cos(ang), ordinals.astype(float)]
    )


# ---------------------------------------------------------------------------
# Weekly rolling origins (no embargo gap)
# ---------------------------------------------------------------------------


def multistep_origin_indices(n_dates: int, config: ForecastConfig) -> list[int]:
    """Weekly rolling origin indices with the cap applied (documented).

    Origin *o* trains on days 0..o (so ``o + 1 ≥ min_train_size``) and scores
    the window o+1 .. o+window_days (so ``o ≤ n_dates - window_days - 1``).
    The forecast window starts the day AFTER the origin — no embargo gap.
    When the eligible range exceeds ``multistep_n_origins``, the oldest origins
    are dropped (exact weekly cadence preserved; the cap exists for runtime;
    UCI's 43 eligible weekly origins are capped to the most recent 20).
    """
    first = max(config.min_train_size - 1, MIN_LAG_ORIGIN)
    last = n_dates - config.multistep_window_days - 1
    if last < first:
        raise ValueError(
            f"panel too short for the multi-step track: {n_dates} dates, "
            f"need >= {first + config.multistep_window_days + 1}"
        )
    eligible = list(range(first, last + 1, ORIGIN_SPACING_DAYS))
    cap = config.multistep_n_origins
    if len(eligible) > cap:
        # keep the exact weekly cadence: drop the OLDEST origins (runtime cap,
        # documented in the block's cap_note)
        eligible = eligible[-cap:]
    return eligible


def split_origins(origin_indices: list[int], config: ForecastConfig) -> tuple[list[int], list[int]]:
    """(selection origins, test origins) — the LAST ``multistep_test_origins``
    origins are scored once and never read for selection."""
    n_test = min(config.multistep_test_origins, max(1, len(origin_indices) // 3))
    return origin_indices[:-n_test], origin_indices[-n_test:]


# ---------------------------------------------------------------------------
# Per-origin computation
# ---------------------------------------------------------------------------


def _design_train(
    units: np.ndarray, cal: np.ndarray, origin: int, h: int
) -> tuple[np.ndarray, np.ndarray]:
    """Training matrix for the direct model of horizon h issued at ``origin``.

    Rows are (candidate origin o', series i) pairs with
    ``o' ∈ [MIN_LAG_ORIGIN, origin - h]`` — every training target date is ≤
    the issue date, so the fit never reads beyond the origin. Features:
    calendar of the target date o'+h, units(o'), units(o'-7), units(o'-14),
    and the series identity as a hi/lo PAIR of native categoricals (HGB caps
    categorical cardinality at 255; the pair (i // 64, i % 64) identifies the
    series exactly and keeps both cardinalities small). Column order matches
    :func:`_design_pred`.
    """
    n_series = units.shape[1]
    lo, hi = MIN_LAG_ORIGIN, origin - h
    m = hi - lo + 1
    tgt = lo + h + np.arange(m)
    base = np.repeat(cal[tgt], n_series, axis=0)
    lag0 = units[lo : hi + 1].reshape(-1)
    lag7 = units[lo - 7 : hi + 1 - 7].reshape(-1)
    lag14 = units[lo - 14 : hi + 1 - 14].reshape(-1)
    codes = np.tile(np.arange(n_series), m)
    x = np.column_stack([base, lag0, lag7, lag14, codes // 64, codes % 64])
    y = units[tgt].reshape(-1)
    return x, y


def _design_pred(units: np.ndarray, cal: np.ndarray, origin: int, h: int) -> np.ndarray:
    """Prediction matrix for (origin, h): one row per series, target origin+h."""
    n_series = units.shape[1]
    base = np.repeat(cal[origin + h : origin + h + 1], n_series, axis=0)
    codes = np.arange(n_series)
    return np.column_stack(
        [base, units[origin], units[origin - 7], units[origin - 14], codes // 64, codes % 64]
    )


def _fit_hgb(config: ForecastConfig, quantile: float | None) -> HistGradientBoostingRegressor:
    """Champion-config HGB; series identity enters as two native categoricals
    (hi/lo pair, see :func:`_design_train`)."""
    kwargs: dict[str, Any] = config.hgb_tuned.estimator_kwargs()
    kwargs["random_state"] = config.seed
    if quantile is not None:
        kwargs["loss"] = "quantile"
        kwargs["quantile"] = quantile
    n_num = 7 + len(LAG_AGES)
    return HistGradientBoostingRegressor(categorical_features=[n_num, n_num + 1], **kwargs)


def _seasonal_naive_pred(units: np.ndarray, origin: int, horizons: list[int]) -> np.ndarray:
    """Direct multi-step seasonal naive: the most recent same-weekday actual.

    For horizon h the reference day is ``origin + h - 7·⌈h/7⌉`` — the newest
    day sharing the target's weekday that is still ≤ the origin (leakage-free
    by construction).
    """
    n_series = units.shape[1]
    out = np.zeros((n_series, len(horizons)))
    for j, h in enumerate(horizons):
        k = math.ceil(h / 7)
        out[:, j] = units[origin + h - 7 * k]
    return out


def _statistical_preds(units: np.ndarray, origin: int, window: int) -> dict[str, np.ndarray]:
    """Flat Croston/SBA/TSB forecasts per series, fit on days 0..origin only."""
    hist = units[: origin + 1]
    return {
        name: np.array(
            [statistical_forecast(name, hist[:, i], window) for i in range(hist.shape[1])]
        )
        for name in ("croston", "sba", "tsb")
    }


@dataclass
class OriginScore:
    """Predictions for every candidate at one origin (n_series x n_horizons)."""

    origin: int
    preds: dict[str, np.ndarray]
    quantiles: dict[float, np.ndarray]  # learner p10/p50/p90


def _score_origin(
    units: np.ndarray, cal: np.ndarray, origin: int, horizons: list[int], config: ForecastConfig
) -> OriginScore:
    """Fit every direct model issued at ``origin`` and predict the window."""
    n_series = units.shape[1]
    point_cols: list[np.ndarray] = []
    quantile_cols: dict[float, list[np.ndarray]] = {q: [] for q in QUANTILES_MS}
    for h in horizons:
        x_train, y_train = _design_train(units, cal, origin, h)
        x_pred = _design_pred(units, cal, origin, h)
        model = _fit_hgb(config, quantile=None)
        model.fit(x_train, y_train)
        point_cols.append(np.asarray(model.predict(x_pred), dtype=float))
        for q in QUANTILES_MS:
            qm = _fit_hgb(config, quantile=q)
            qm.fit(x_train, y_train)
            quantile_cols[q].append(np.asarray(qm.predict(x_pred), dtype=float))
    preds: dict[str, np.ndarray] = {"direct_hgb": np.column_stack(point_cols)}
    quantiles = {q: np.column_stack(v) for q, v in quantile_cols.items()}
    preds["seasonal_naive"] = _seasonal_naive_pred(units, origin, horizons)
    preds["zero"] = np.zeros((n_series, len(horizons)))
    for name, mat in _statistical_preds(units, origin, config.multistep_window_days).items():
        preds[name] = np.column_stack([mat[:, h - 1] for h in horizons])
    return OriginScore(origin=origin, preds=preds, quantiles=quantiles)


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


# ---------------------------------------------------------------------------
# Long table over test origins
# ---------------------------------------------------------------------------


def _scales(units: np.ndarray, origin: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-series (MASE scale, squared seasonal-naive scale, train volume)."""
    diffs = units[7 : origin + 1] - units[: origin + 1 - 7]
    return (
        np.mean(np.abs(diffs), axis=0),
        np.mean(diffs**2, axis=0),
        units[: origin + 1].sum(axis=0),
    )


def _test_cells(
    by_origin: dict[int, OriginScore],
    test: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
) -> dict[str, Any]:
    """Flatten (series x test origin x horizon) into column arrays."""
    n_cells = units.shape[1] * len(test) * len(horizons)
    cells: dict[str, Any] = {
        "series": np.empty(n_cells, dtype=int),
        "origin": np.empty(n_cells, dtype=int),
        "h": np.empty(n_cells, dtype=int),
        "y": np.empty(n_cells),
        "sparse": np.empty(n_cells, dtype=bool),
        "scale": np.empty(n_cells),
        "scale2": np.empty(n_cells),
        "volume": np.empty(n_cells),
        "pred": {name: np.empty(n_cells) for name in CANDIDATES},
        "p50": np.empty(n_cells),
        "p10": np.empty(n_cells),
        "p90": np.empty(n_cells),
    }
    r = 0
    for o in test:
        sc = by_origin[o]
        sc_mase, sc_scale2, sc_vol = _scales(units, o)
        for j, h in enumerate(horizons):
            n = units.shape[1]
            sl = slice(r, r + n)
            cells["series"][sl] = np.arange(n)
            cells["origin"][sl] = o
            cells["h"][sl] = h
            cells["y"][sl] = units[o + h]
            cells["sparse"][sl] = sparse
            cells["scale"][sl] = sc_mase
            cells["scale2"][sl] = sc_scale2
            cells["volume"][sl] = sc_vol
            cells["p50"][sl] = sc.quantiles[0.5][:, j]
            cells["p10"][sl] = sc.quantiles[0.1][:, j]
            cells["p90"][sl] = sc.quantiles[0.9][:, j]
            for name in ("direct_hgb", "seasonal_naive", "zero", "croston", "sba", "tsb"):
                cells["pred"][name][sl] = sc.preds[name][:, j]
            stat_pred = np.zeros(n)
            for name in STATISTICAL_METHODS:
                mask = sparse & (method_of == name)
                stat_pred[mask] = sc.preds[name][mask, j]
            cells["pred"]["routed"][sl] = np.where(sparse, stat_pred, sc.preds["direct_hgb"][:, j])
            r += n
    return cells


# ---------------------------------------------------------------------------
# Result container + main entry
# ---------------------------------------------------------------------------


@dataclass
class MultiStepResult:
    """Everything the multi-step track produced, plus the report figures."""

    block: dict[str, Any] = field(default_factory=dict)  # metrics.json "_multistep"
    probabilistic_block: dict[str, Any] = field(default_factory=dict)  # probabilistic.json
    metadata_block: dict[str, Any] = field(default_factory=dict)  # evaluation_metadata.json
    figures: dict[str, go.Figure] = field(default_factory=dict)


def run_multistep(
    settings: DemandSettings, config: ForecastConfig, panel: pl.DataFrame
) -> MultiStepResult:
    """Run the full direct multi-horizon track; returns JSON blocks + figures."""
    del settings  # artifact merging is the caller's job (evaluate.py)
    dates, series_ids, units = panel_matrix(panel)
    cal = _calendar_features(dates)
    horizons = list(config.multistep_horizons)
    n_series = len(series_ids)
    classes = classify_panel(units, series_ids)
    sparse = np.array([classes[s]["class"] in SPARSE_CLASSES for s in series_ids])

    origins = multistep_origin_indices(len(dates), config)
    selection, test = split_origins(origins, config)
    logger.info(
        "multistep: %d origins (%d selection + %d test), horizons %s, %d series, "
        "%d sparse (%.1f%%)",
        len(origins),
        len(selection),
        len(test),
        horizons,
        n_series,
        int(sparse.sum()),
        100.0 * sparse.mean(),
    )
    scores = Parallel(n_jobs=-2, backend="loky")(
        delayed(_score_origin)(units, cal, o, horizons, config) for o in origins
    )
    by_origin = {s.origin: s for s in scores}

    # ---- routing: per-series best statistical method on SELECTION origins ----
    method_of = _route(by_origin, selection, horizons, units, sparse, n_series)

    # ---- long table over the TEST origins (scored once) ----
    cells = _test_cells(by_origin, test, horizons, units, sparse, method_of)
    class_of_series = np.array([classes[s]["class"] for s in series_ids])
    cells["class"] = class_of_series[cells["series"]]

    per_horizon = _per_horizon_metrics(cells, horizons)
    bands = _bands(by_origin, selection, test, horizons, units, sparse, cells)
    bootstrap = _bootstrap_suite(cells, horizons, config)
    growth = _growth_curves(cells, horizons)
    class_of_series = np.array([classes[s]["class"] for s in series_ids])
    decision = _order_up_to(
        by_origin, selection, horizons, units, sparse, method_of, cells, class_of_series, config
    )
    block = _assemble_block(
        dates,
        origins,
        selection,
        test,
        horizons,
        classes,
        sparse,
        method_of,
        per_horizon,
        bands,
        bootstrap,
        growth,
        decision,
        cells,
        series_ids,
        config,
    )
    figures = _figures(block, horizons, bands["json"])
    result = MultiStepResult(
        block=block,
        probabilistic_block=bands["json"],
        metadata_block=_metadata_block(block, config),
        figures=figures,
    )
    logger.info(
        "multistep: pooled MAE h1=%.3f -> h14=%.3f (champion), coverage pooled=%.3f (%s)",
        per_horizon[horizons[0]]["champion"]["mae"],
        per_horizon[horizons[-1]]["champion"]["mae"],
        bands["json"]["pooled_coverage"],
        bands["json"]["pooled_verdict"],
    )
    return result


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _route(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    n_series: int,
) -> np.ndarray:
    """Per-series method: best statistical candidate on SELECTION origins only.

    Property (tested): the choice reads no test-origin actual — shuffling the
    test window leaves every choice unchanged.
    """
    stat_err = {name: np.zeros(n_series) for name in STATISTICAL_METHODS}
    for o in selection:
        sc = by_origin[o]
        actual = np.column_stack([units[o + h] for h in horizons])
        for name in STATISTICAL_METHODS:
            stat_err[name] += np.abs(actual - sc.preds[name]).sum(axis=1)
    stack = np.stack([stat_err[name] for name in STATISTICAL_METHODS], axis=1)
    method_of = np.array(STATISTICAL_METHODS, dtype=object)[np.argmin(stack, axis=1)]
    method_of = method_of.copy()
    method_of[~sparse] = "direct_hgb"
    return method_of


# ---------------------------------------------------------------------------
# Per-horizon metric suite
# ---------------------------------------------------------------------------


def _metric_dict(cells: dict[str, Any], mask: np.ndarray, pred_key: str) -> dict[str, float]:
    """Pooled MAE/RMSE/MASE/bias/WAPE for one candidate over the masked cells."""
    y = cells["y"][mask]
    err = cells["pred"][pred_key][mask] - y
    abs_err = np.abs(err)
    scale_mask = cells["scale"][mask] > 0
    mase = (
        float(abs_err[scale_mask].sum() / cells["scale"][mask][scale_mask].sum())
        if scale_mask.any()
        else float("nan")
    )
    abs_y = float(np.abs(y).sum())
    return {
        "n": int(mask.sum()),
        "mae": float(abs_err.mean()),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mase": mase,
        "bias": float(err.mean()),
        "wape": float(abs_err.sum() / abs_y) if abs_y > 0 else float("nan"),
    }


def _per_horizon_metrics(cells: dict[str, Any], horizons: list[int]) -> dict[int, dict[str, Any]]:
    """Pooled MAE/RMSE/MASE/bias/WAPE/RMSSE per TRUE horizon (test origins).

    Errors now genuinely grow with h — the growth curve is the point.
    MASE divides the pooled |err| by the pooled per-series seasonal scale
    (zero-scale rows excluded); RMSSE is M5-style per series, reported pooled
    and volume-weighted. Champion and floor metrics are both carried.
    """
    out: dict[int, dict[str, Any]] = {}
    for h in horizons:
        mask = cells["h"] == h
        entry: dict[str, Any] = {
            "champion": _metric_dict(cells, mask, CHAMPION),
            "floor": _metric_dict(cells, mask, FLOOR),
        }
        err = cells["pred"][CHAMPION][mask] - cells["y"][mask]
        rmsse, wrmsse = rmsse_pooled(
            err, cells["scale2"][mask], cells["volume"][mask], cells["series"][mask]
        )
        entry["champion"]["rmsse"] = rmsse
        entry["champion"]["wrmsse"] = wrmsse
        out[h] = entry
    return out


# ---------------------------------------------------------------------------
# Bands: split-conformal per h (learner) + sparse P(sale)/ladder bands
# ---------------------------------------------------------------------------


def _bands(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    test: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    cells: dict[str, Any],
) -> dict[str, Any]:
    """Per-horizon bands on the test origins.

    Learner rows (smooth/erratic): ±q80 split-conformal width per h,
    calibrated on the selection origins' p50 residuals, zero-clipped and
    sorted. Sparse rows (routed): band [0, q90 of the training history] plus
    P(any sale) and a quantile ladder — it cannot collapse to zero width.
    Returns the per-h coverage/width table (metrics) plus the probabilistic.json
    block (keyed "json").
    """
    # conformal widths per h from selection-origin p50 residuals (learner rows)
    widths: dict[int, float] = {}
    for h in horizons:
        res: list[np.ndarray] = []
        for o in selection:
            sc = by_origin[o]
            j = horizons.index(h)
            res.append(units[o + h][~sparse] - sc.quantiles[0.5][~sparse, j])
        widths[h] = float(np.quantile(np.abs(np.concatenate(res)), TARGET_COVERAGE))

    units.shape[1]
    per_h: dict[int, dict[str, Any]] = {}
    sparse_band: dict[str, Any] = {}
    for h in horizons:
        mask = cells["h"] == h
        y = cells["y"][mask]
        lo = np.empty(mask.sum())
        hi = np.empty(mask.sum())
        # learner rows: p50 ± width, zero-clipped (sorting is then automatic)
        p50 = cells["p50"][mask]
        w = widths[h]
        lo[:] = np.clip(p50 - w, 0.0, None)
        hi[:] = p50 + w
        # sparse rows: [0, q90 of the training history up to the origin]
        sparse_rows = np.flatnonzero(cells["sparse"][mask])
        for r in sparse_rows:
            i = int(cells["series"][mask][r])
            o = int(cells["origin"][mask][r])
            hist = units[: o + 1, i]
            lo[r] = 0.0
            hi[r] = float(np.quantile(hist, TARGET_COVERAGE))
        covered = (y >= lo) & (y <= hi)
        per_h[h] = {
            "coverage": float(covered.mean()),
            "avg_width": float((hi - lo).mean()),
            "calibration_verdict": calibration_verdict(float(covered.mean()), TARGET_COVERAGE),
            "learner_coverage": float(covered[~cells["sparse"][mask]].mean())
            if (~cells["sparse"][mask]).any()
            else float("nan"),
            "sparse_coverage": float(covered[cells["sparse"][mask]].mean())
            if cells["sparse"][mask].any()
            else float("nan"),
        }

    # pinball loss of the learner quantiles per h (on learner rows)
    pinball: dict[int, dict[str, float]] = {}
    for h in horizons:
        mask = (cells["h"] == h) & (~cells["sparse"])
        pinball[h] = {
            f"pinball_p{int(q * 100)}": pinball_loss(
                cells["y"][mask], cells[f"p{int(q * 100)}"][mask], q
            )
            for q in QUANTILES_MS
        }

    # sparse band summary from the LAST test origin (dataset-level flavour)
    last_o = max(test)
    sparse_band = {
        "definition": (
            "P(any sale) = share of non-zero demand days in the training history "
            "up to the origin; quantile ladder over the same history"
        ),
        "ladder_levels": list(LADDER_LEVELS),
        "series": {
            str(i): {
                "p_sale": float(np.mean(units[: last_o + 1, i] > 0)),
                "ladder": [
                    float(np.quantile(units[: last_o + 1, i], lvl)) for lvl in LADDER_LEVELS
                ],
            }
            for i in np.flatnonzero(sparse)
        },
    }

    pooled_cov = float(np.mean([per_h[h]["coverage"] for h in horizons]))
    block = {
        "protocol": PROTOCOL,
        "target_coverage": TARGET_COVERAGE,
        "calibration_tolerance": CALIBRATION_TOL,
        "band_types": {
            "learner": "p50 ± q80 split-conformal width per horizon, calibrated on the "
            "selection origins, zero-clipped and sorted",
            "sparse": "P(any sale) + quantile ladder of the training history (no collapsing band)",
        },
        "conformal_widths_by_h": {str(h): widths[h] for h in horizons},
        "per_horizon": {str(h): {**per_h[h], **pinball[h]} for h in horizons},
        "pooled_coverage": pooled_cov,
        "pooled_verdict": calibration_verdict(pooled_cov, TARGET_COVERAGE),
        "sparse_band": sparse_band,
        "verdict_rule": "|coverage - target| <= 0.05 -> calibrated; above target -> "
        "conservative; below -> optimistic (per horizon and pooled)",
    }
    return {"per_h": per_h, "widths": widths, "json": block}


# ---------------------------------------------------------------------------
# Paired bootstrap suite
# ---------------------------------------------------------------------------


def _bootstrap_suite(
    cells: dict[str, Any], horizons: list[int], config: ForecastConfig
) -> dict[str, Any]:
    """95% cluster-bootstrap CIs on every headline comparison.

    Unit = (series x scored test origins): series are resampled with
    replacement, one shared draw per replication so differences stay paired.
    """
    seed = config.seed + 2002  # distinct stream from every other consumer
    classes = [str(c) for c in np.unique(cells["class"])]

    def _pair(mask: np.ndarray, a: str, b: str) -> dict[str, Any]:
        return _paired_bootstrap_mae(
            cells["pred"][a][mask] - cells["y"][mask],
            cells["pred"][b][mask] - cells["y"][mask],
            cells["series"][mask],
            config.bootstrap_reps,
            seed,
        )

    per_class: dict[str, Any] = {}
    for cls in classes:
        cls_mask = cells["class"] == cls
        entry: dict[str, Any] = {}
        for h in (7, 14):
            if h not in horizons:
                continue
            mask = cls_mask & (cells["h"] == h)
            if not mask.any():
                continue
            entry[f"h{h}"] = {
                "champion_mae": float(
                    np.abs(cells["pred"][CHAMPION][mask] - cells["y"][mask]).mean()
                ),
                "floor_mae": float(np.abs(cells["pred"][FLOOR][mask] - cells["y"][mask]).mean()),
                "champion_vs_floor": _pair(mask, CHAMPION, FLOOR),
                "champion_vs_naive_zero": _pair(mask, CHAMPION, NAIVE),
            }
        # routing before/after: all-HGB (unrouted) vs routed champion, all h
        entry["routing"] = _pair(cls_mask, "direct_hgb", CHAMPION)
        entry["n_series"] = len(np.unique(cells["series"][cls_mask]))
        per_class[cls] = entry

    # model ranks pooled over test origins and all horizons (with rank gaps)
    overall_mae = {
        name: float(np.abs(cells["pred"][name] - cells["y"]).mean()) for name in CANDIDATES
    }
    ranked = sorted(CANDIDATES, key=lambda n: overall_mae[n])
    rank_gaps: list[dict[str, Any]] = []
    for rank, name in enumerate(ranked[:5], start=1):
        gap: dict[str, Any] = {"rank": rank, "model": name, "mae": overall_mae[name]}
        if rank < len(ranked):
            nxt = ranked[rank]
            gap["gap_to_next"] = {
                "model": nxt,
                **_paired_bootstrap_mae(
                    cells["pred"][name] - cells["y"],
                    cells["pred"][nxt] - cells["y"],
                    cells["series"],
                    config.bootstrap_reps,
                    seed,
                ),
            }
        rank_gaps.append(gap)

    return {
        "method": "paired cluster bootstrap (series resampled with replacement, one shared "
        "draw per replication), percentile 95% CI over series x scored test origins",
        "unit": "series cluster x scored test origins",
        "n_boot": config.bootstrap_reps,
        "seed": seed,
        "per_class": per_class,
        "rank_gaps": rank_gaps,
    }


# ---------------------------------------------------------------------------
# Horizon growth curves
# ---------------------------------------------------------------------------


def _growth_curves(cells: dict[str, Any], horizons: list[int]) -> dict[str, Any]:
    """Pooled MAE by TRUE horizon for the champion, the floor and zero."""
    curves: dict[str, Any] = {"pooled": {}, "per_class": {}}
    for name in (CHAMPION, FLOOR, NAIVE):
        curves["pooled"][name] = {
            str(h): float(
                np.abs(cells["pred"][name][cells["h"] == h] - cells["y"][cells["h"] == h]).mean()
            )
            for h in horizons
        }
    for cls in np.unique(cells["class"]):
        cls_mask = cells["class"] == cls
        curves["per_class"][str(cls)] = {
            name: {
                str(h): float(
                    np.abs(
                        cells["pred"][name][cls_mask & (cells["h"] == h)]
                        - cells["y"][cls_mask & (cells["h"] == h)]
                    ).mean()
                )
                for h in horizons
            }
            for name in (CHAMPION, FLOOR)
        }
    return curves


# ---------------------------------------------------------------------------
# Decision metric: order-up-to policy simulation
# ---------------------------------------------------------------------------


def _routed_pred(sc: OriginScore, j: int, sparse: np.ndarray, method_of: np.ndarray) -> np.ndarray:
    out = sc.preds["direct_hgb"][:, j].copy()
    for name in STATISTICAL_METHODS:
        mask = sparse & (method_of == name)
        out[mask] = sc.preds[name][mask, j]
    return out


def _policy_residuals(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    h: int,
    class_mask: np.ndarray,
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    policy: str,
) -> np.ndarray:
    """Selection-origin residuals (actual - forecast) for one policy, one class.

    The class mask is per SERIES; residuals are pooled over selection origins.
    """
    j = horizons.index(h)
    res: list[np.ndarray] = []
    for o in selection:
        sc = by_origin[o]
        if policy == "champion":
            pred = _routed_pred(sc, j, sparse, method_of)
        else:
            pred = sc.preds["seasonal_naive"][:, j]
        res.append((units[o + h] - pred)[class_mask])
    return np.concatenate(res)


def _order_up_to(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    cells: dict[str, Any],
    class_of_series: np.ndarray,
    config: ForecastConfig,
) -> dict[str, Any]:
    """Order-up-to policy evaluation (simulation — no savings claims).

    Per series, service level τ: the order for (origin, h) is the τ-quantile
    of the policy's forecast distribution, approximated as
    ``point + q_τ(residuals)`` with residuals calibrated per (class, h) on the
    SELECTION origins. Cost per cell: ``holding · max(order - actual, 0) +
    stockout · max(actual - order, 0)``, summed over the scored test cells.
    Champion (routed) policy vs seasonal-naive policy, per demand class.
    """
    classes = [str(c) for c in np.unique(cells["class"])]
    out: dict[str, Any] = {
        "simulation": True,
        "label": "order-up-to policy simulation — cost assumptions documented, no savings claims",
        "cost_assumptions": {
            "holding_cost_per_unit": config.holding_cost,
            "stockout_cost_per_unit_short": config.stockout_cost,
            "cost_basis": "per scored cell (series x test origin x horizon)",
        },
        "service_levels": list(config.service_levels),
        "per_class": {},
    }
    for cls in classes:
        class_mask = class_of_series == cls  # per-series mask
        per_tau: dict[str, Any] = {}
        for tau in config.service_levels:
            totals: dict[str, float] = {}
            for policy in ("champion", "floor"):
                cost = 0.0
                demand = 0.0
                pred_key = CHAMPION if policy == "champion" else FLOOR
                for h in horizons:
                    cell_mask = (cells["h"] == h) & (cells["class"] == cls)
                    pred = cells["pred"][pred_key][cell_mask]
                    res = _policy_residuals(
                        by_origin,
                        selection,
                        horizons,
                        h,
                        class_mask,
                        units,
                        sparse,
                        method_of,
                        policy,
                    )
                    q_tau = float(np.quantile(res, tau))
                    order = np.maximum(pred + q_tau, 0.0)
                    y = cells["y"][cell_mask]
                    cost += order_up_to_cost(order, y, config.holding_cost, config.stockout_cost)
                    demand += float(y.sum())
                totals[policy] = cost
                totals[f"{policy}_per_unit_demand"] = cost / demand if demand > 0 else float("nan")
            per_tau[f"tau_{tau:.2f}"] = {
                **totals,
                "delta_champion_minus_floor": totals["champion"] - totals["floor"],
            }
        out["per_class"][cls] = per_tau
    return out


# ---------------------------------------------------------------------------
# Block assembly
# ---------------------------------------------------------------------------


def _assemble_block(
    dates: np.ndarray,
    origins: list[int],
    selection: list[int],
    test: list[int],
    horizons: list[int],
    classes: dict[str, dict[str, Any]],
    sparse: np.ndarray,
    method_of: np.ndarray,
    per_horizon: dict[int, dict[str, Any]],
    bands: dict[str, Any],
    bootstrap: dict[str, Any],
    growth: dict[str, Any],
    decision: dict[str, Any],
    cells: dict[str, Any],
    series_ids: list[str],
    config: ForecastConfig,
) -> dict[str, Any]:
    """The ``_multistep`` block of metrics.json (multi-step headline)."""
    del bands  # band numbers live in probabilistic.json (merged separately)
    counts = {
        cls: int(sum(1 for s in series_ids if classes[s]["class"] == cls))
        for cls in ("smooth", "erratic", "intermittent", "lumpy")
    }
    headline: dict[str, Any] = {}
    for cls, entry in bootstrap["per_class"].items():
        headline[cls] = {key: value for key, value in entry.items() if key.startswith("h")}
        headline[cls]["n_series"] = entry["n_series"]
    routing_choices = {sid: str(method_of[i]) for i, sid in enumerate(series_ids) if sparse[i]}
    overall = {name: float(np.abs(cells["pred"][name] - cells["y"]).mean()) for name in CANDIDATES}
    return {
        "protocol": PROTOCOL,
        "track_note": (
            "PRIMARY multi-step headline. The per-model blocks above are the retained "
            "frozen nowcast (one-day-ahead) track, rolling_origin_holdout_v1 — valid but "
            "never mixed into the multi-step leaderboard. Each multi-step row is a TRUE "
            "horizon-h forecast issued at the origin (no actual within h days of the "
            "target is referenced)."
        ),
        "horizons": horizons,
        "window_days": config.multistep_window_days,
        "candidates": list(CANDIDATES),
        "champion": CHAMPION,
        "champion_definition": "per-series routing: ADI>=1.32 (intermittent/lumpy) -> best "
        "statistical method on selection origins; smooth/erratic -> direct per-horizon HGB",
        "floor": FLOOR,
        "naive": NAIVE,
        "origins": {
            "n_origins": len(origins),
            "dates": [str(dates[o])[:10] for o in origins],
            "selection_dates": [str(dates[o])[:10] for o in selection],
            "test_dates": [str(dates[o])[:10] for o in test],
            "spacing_days": ORIGIN_SPACING_DAYS,
            "min_train_dates": config.min_train_size,
            "gap_days": 0,
            "cap_note": (
                f"weekly origins, capped at {config.multistep_n_origins} by dropping the "
                "oldest (exact weekly cadence kept) for runtime; the window starts the day "
                "AFTER the origin (no embargo gap)"
            ),
        },
        "demand_classes": {
            "method": "Syntetos-Boylan quadrants on ADI and CV^2 over the full panel",
            "thresholds": {"adi": ADI_THRESHOLD, "cv2": CV2_THRESHOLD},
            "counts": counts,
            "n_series": len(series_ids),
            "sparse_share": float(sparse.mean()),
            "series": {sid: classes[sid]["class"] for sid in series_ids},
        },
        "routing": {
            "rule": "sparse (ADI >= 1.32) series route to the best statistical method "
            "(zero/seasonal_naive/Croston/SBA/TSB) chosen per series on the selection "
            "origins ONLY; smooth/erratic series stay on the direct HGB",
            "method_choices": routing_choices,
            "per_class": {cls: entry["routing"] for cls, entry in bootstrap["per_class"].items()},
        },
        "headline_per_class": headline,
        "per_horizon": {str(h): per_horizon[h] for h in horizons},
        "horizon_growth": growth,
        "overall_mae_test": overall,
        "bootstrap": {
            "method": bootstrap["method"],
            "unit": bootstrap["unit"],
            "n_boot": bootstrap["n_boot"],
            "seed": bootstrap["seed"],
            "rank_gaps": bootstrap["rank_gaps"],
        },
        "decision_metric": decision,
    }


def _metadata_block(block: dict[str, Any], config: ForecastConfig) -> dict[str, Any]:
    """The ``multi_horizon`` block of evaluation_metadata.json (protocol v2)."""
    origins = block["origins"]
    return {
        "protocol": PROTOCOL,
        "track": "multi_step (primary); the top-level rolling_origin_holdout_v1 keys "
        "describe the retained frozen nowcast track",
        "horizons": block["horizons"],
        "window_days": block["window_days"],
        "origins": origins,
        "holdout_designation": (
            f"last {config.multistep_test_origins} origins = test (scored once); the "
            "earlier origins select (routing + conformal calibration) only"
        ),
        "selection_rule": "per-series routing method = lowest summed |error| over the "
        "selection origins among zero/seasonal_naive/Croston/SBA/TSB; never reads test "
        "actuals (property-tested by shuffling the test origins' actuals)",
        "feature_semantics": "direct per-horizon models: calendar of the target date + "
        "lags lag_h, lag_{h+7}, lag_{h+14} (>= h days old relative to the target — no "
        "actual within h days of the target is referenced); training rows use targets "
        "<= the origin only",
        "uncertainty": "per-horizon split-conformal (learner rows) and P(sale)+quantile "
        "ladder (sparse rows), both calibrated on selection origins",
        "metric_definitions": {
            "mae": "mean |actual - forecast| over series x scored test origins at horizon h",
            "mase": "pooled |err| / pooled per-series in-sample seasonal-naive-7 scale "
            "(zero-scale rows excluded)",
            "bias": "mean(forecast - actual) at horizon h",
            "wape": "sum|err| / sum|actual| at horizon h",
            "rmsse": "M5-style: per-series sqrt(MSE(err)/MSE(in-sample seasonal-naive-7)), "
            "averaged over series (zero-scale excluded)",
            "wrmsse": "volume-weighted RMSSE (weights = training-window demand)",
            "pinball_pXX": "mean pinball loss of the learner quantile at level XX",
            "coverage": "share of actuals inside the per-h band on the scored origins",
            "calibration_verdict": "|coverage - target| <= 0.05 -> calibrated; above -> "
            "conservative; below -> optimistic",
        },
    }


# ---------------------------------------------------------------------------
# Figures (unit-incompatible metrics never share an axis)
# ---------------------------------------------------------------------------


def _figures(
    block: dict[str, Any], horizons: list[int], prob_block: dict[str, Any]
) -> dict[str, go.Figure]:
    """The four multi-step figures (unit-incompatible metrics on separate axes)."""
    growth = block["horizon_growth"]["pooled"]
    per_class = block["headline_per_class"]
    hs = [str(h) for h in horizons]

    # (1) error vs horizon: MAE (units) and MASE (unitless) on SEPARATE panels.
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("MAE by true horizon (units)", "MASE by true horizon"),
    )
    for name in (CHAMPION, FLOOR, NAIVE):
        fig.add_scatter(
            x=hs, y=list(growth[name].values()), name=name, mode="lines+markers", row=1, col=1
        )
    for name, key in ((CHAMPION, "champion"), (FLOOR, "floor")):
        fig.add_scatter(
            x=hs,
            y=[block["per_horizon"][str(h)][key]["mase"] for h in horizons],
            name=f"{name} (MASE)",
            mode="lines+markers",
            row=1,
            col=2,
        )
    fig.update_layout(title="Multi-step error vs horizon — champion vs floor vs zero")
    add_takeaway(
        fig,
        "direct per-horizon models on the scored origins — error grows with the true "
        "horizon h now (the old nowcast h-index was chronological rank, not horizon)",
    )
    error_fig = apply_theme(fig)

    # (2) per-class scoreboard: MAE bars (units) + gap-with-CI panel (units).
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "champion vs floor MAE (units)",
            "champion - floor MAE gap with 95% CI (units)",
        ),
    )
    first = {"champion": True, "floor": True}
    for cls in sorted(per_class):
        for h in (7, 14):
            key = f"h{h}"
            if key not in per_class[cls]:
                continue
            e = per_class[cls][key]
            x_pos = f"{cls}<br>h={h}"
            for name, color in (("champion", "#2dd4bf"), ("floor", "#64748b")):
                fig.add_bar(
                    x=[x_pos],
                    y=[e[f"{name}_mae"]],
                    name=name,
                    marker_color=color,
                    legendgroup=name,
                    showlegend=first[name],
                    row=1,
                    col=1,
                )
                first[name] = False
            gap = e["champion_vs_floor"]
            fig.add_scatter(
                x=[x_pos],
                y=[gap["diff"]],
                name="gap",
                mode="markers",
                marker={"color": "#fbbf24", "size": 10},
                error_y={
                    "type": "data",
                    "array": [gap["ci95"][1] - gap["diff"]],
                    "arrayminus": [gap["diff"] - gap["ci95"][0]],
                },
                showlegend=False,
                row=1,
                col=2,
            )
    fig.add_shape(
        type="line",
        xref="x2 domain",
        x0=0,
        x1=1,
        yref="y2",
        y0=0.0,
        y1=0.0,
        line={"dash": "dot", "color": "#fbbf24"},
    )
    fig.update_layout(
        title="Multi-step class scoreboard at h=7/h=14",
        barmode="group",
    )
    add_takeaway(
        fig,
        "right panel: 95% paired cluster bootstrap over series x scored origins — "
        "a gap CI above zero means the champion beats the floor for that class",
    )
    scoreboard_fig = apply_theme(fig)

    # (3) routing: all-HGB minus routed MAE per class (units; positive = helps).
    fig = go.Figure()
    for cls in sorted(block["routing"]["per_class"]):
        r = block["routing"]["per_class"][cls]
        fig.add_bar(
            x=[cls],
            y=[r["diff"]],
            name="unrouted - routed MAE",
            marker_color="#2dd4bf",
            error_y={
                "type": "data",
                "array": [r["ci95"][1] - r["diff"]],
                "arrayminus": [r["diff"] - r["ci95"][0]],
            },
        )
    fig.add_shape(
        type="line",
        xref="paper",
        x0=0,
        x1=1,
        yref="y",
        y0=0.0,
        y1=0.0,
        line={"dash": "dot", "color": "#fbbf24"},
    )
    fig.update_layout(
        title="Routing effect per class — all-HGB MAE minus routed MAE (positive = routing helps)",
        yaxis_title="MAE difference (units)",
    )
    add_takeaway(
        fig,
        "whiskers = 95% paired bootstrap CI over series x scored origins; sparse "
        "classes should sit above zero — boosted trees overfit intermittent series",
    )
    routing_fig = apply_theme(fig)

    # (4) band calibration: coverage per h and width per h on SEPARATE panels.
    per_h = prob_block["per_horizon"]
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            f"empirical coverage per horizon (target {TARGET_COVERAGE:.0%})",
            "average band width per horizon (units)",
        ),
    )
    fig.add_scatter(
        x=hs,
        y=[per_h[str(h)]["coverage"] for h in horizons],
        name="coverage",
        mode="lines+markers",
        row=1,
        col=1,
    )
    fig.add_shape(
        type="line",
        xref="x domain",
        x0=hs[0],
        x1=hs[-1],
        yref="y",
        y0=TARGET_COVERAGE,
        y1=TARGET_COVERAGE,
        line={"dash": "dot", "color": "#fbbf24"},
        row=1,
        col=1,
    )
    fig.add_scatter(
        x=hs,
        y=[per_h[str(h)]["avg_width"] for h in horizons],
        name="avg width",
        mode="lines+markers",
        row=1,
        col=2,
    )
    fig.update_layout(title="Multi-step band calibration per horizon")
    add_takeaway(
        fig,
        f"verdict rule: |coverage - {TARGET_COVERAGE:.0%}| ≤ {CALIBRATION_TOL:.2f} calibrated, "
        "above conservative, below optimistic; sparse rows carry P(sale)+ladder bands",
    )
    band_fig = apply_theme(fig)

    return {
        "multistep_error_vs_horizon": error_fig,
        "multistep_class_scoreboard": scoreboard_fig,
        "multistep_routing": routing_fig,
        "multistep_band_calibration": band_fig,
    }


# ---------------------------------------------------------------------------
# Artifact merging (called from evaluate.py / probabilistic.py / cli.py)
# ---------------------------------------------------------------------------


def merge_metrics_json(settings: DemandSettings, result: MultiStepResult) -> None:
    """Add the ``_multistep`` block to the track's metrics.json.

    The per-model nowcast blocks (and ``_meta``) are untouched; keys starting
    with ``_`` are ignored by the demo payload's run parser, so the payload
    keeps working unchanged.
    """
    path = Path(settings.reports_dir) / "metrics.json"
    metrics: dict[str, Any] = json.loads(path.read_text())
    metrics["_multistep"] = result.block
    path.write_text(json.dumps(_json_safe(metrics), indent=2))
    logger.info("multistep metrics merged -> %s", path)


def merge_evaluation_metadata(settings: DemandSettings, result: MultiStepResult) -> None:
    """Add the ``multi_horizon`` protocol block to evaluation_metadata.json."""
    path = Path(settings.reports_dir) / "evaluation_metadata.json"
    meta: dict[str, Any] = json.loads(path.read_text())
    meta["multi_horizon"] = result.metadata_block
    path.write_text(json.dumps(_json_safe(meta), indent=2))
    logger.info("multistep evaluation metadata merged -> %s", path)


def probabilistic_multistep_block(result: MultiStepResult) -> dict[str, Any]:
    """The ``multistep`` key for probabilistic.json (merged by run_probabilistic)."""
    return result.probabilistic_block


def save_multistep_figures(settings: DemandSettings, result: MultiStepResult) -> None:
    """Persist the multi-step figure JSONs next to the other figures."""
    out_dir = Path(settings.reports_dir) / "figures"
    for name, fig in result.figures.items():
        save_json(fig, out_dir / f"{name}.json")
