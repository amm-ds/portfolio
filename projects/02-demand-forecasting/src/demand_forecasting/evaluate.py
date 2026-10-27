"""Honest backtest: expanding-window time CV + frozen final holdout + figures.

Leakage control (playbook: random splits mask drift):
- splits come from :class:`portfolio_core.timecv.TimeSeriesCV` (train strictly
  before validation, plus an embargo ``gap``),
- features were built with ``shift`` only (see features.py),
- metrics are pooled out-of-fold predictions — never in-sample readings.

Frozen holdout protocol (``rolling_origin_holdout_v1``, audit hardening):
the LAST chronological rolling-origin window is the **test window** — every
candidate model is scored on it exactly once and those are the committed
headline numbers. Model/feature selection (``best_model``, the champion pick)
is computed from folds 1..n-1 ONLY, so the test window can never influence
which model is promoted. The previous all-fold pooled headline is retained
per model under ``legacy_pooled_*`` for comparison.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_json, style_runs
from portfolio_core.timecv import TimeSeriesCV
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.ml import regression_metrics
from portfolio_eval.report import ReportBuilder

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.model import ModelSpec, model_specs, to_xy

logger = get_logger(__name__)

EXAMPLE_SERIES = ["store_0|product_0", "store_3|product_5"]

# Per-horizon metrics are reported over the final EVAL_HORIZON_DAYS of the
# test window: horizon h = the h-th day of that block per series (chronological
# rank), matching the demo payload's committed forecast window (14 days).
EVAL_HORIZON_DAYS = 14

METRIC_DEFINITIONS: dict[str, str] = {
    "mae": "mean |actual - forecast| over the test window (all series pooled)",
    "rmse": "root mean squared error over the test window",
    "mape_pct": "mean absolute percentage error over non-zero actuals only, in % — "
    "inflated by near-zero demand on intermittent series; not decision-grade",
    "mase": "MAE scaled by the per-series in-sample seasonal-naive-7 error of the "
    "test fold's training window; < 1 beats 'same day last week'",
    "bias": "mean(forecast - actual) over the test window — systematic over- or under-forecasting",
    "wape": "sum|actual - forecast| / sum|actual| over the test window "
    "(weighted absolute percentage error; null when the denominator is 0)",
    "fold_maes": "per-fold pooled MAE, folds 1..n (fold n is the test window)",
    "fold_mae_std": "population std of fold_maes across all folds",
    "fold_mae_range": "max - min of fold_maes across all folds",
    "horizon_mae": "per-horizon (h=1..14) mean |error| over the final 14 days "
    "of the test window, pooled over series",
    "horizon_mase": "per-horizon (h=1..14) mean |error|/seasonal scale over the "
    "final 14 days of the test window",
    "legacy_pooled_mae": "pre-holdout headline: pooled MAE over ALL folds "
    "(selection + test), kept for comparison",
    "legacy_pooled_rmse": "pre-holdout headline: pooled RMSE over all folds",
    "legacy_pooled_mape_pct": "pre-holdout headline: pooled MAPE over all folds",
    "legacy_pooled_mase": "pre-holdout headline: pooled MASE over all folds",
}


def _date_positions(features: pl.DataFrame) -> np.ndarray:
    """Map each row to the positional index of its date in the sorted unique dates."""
    dates = features["date"].to_numpy()
    uniq = np.unique(dates)
    return np.searchsorted(uniq, dates)


def cv_row_folds(
    features: pl.DataFrame, config: ForecastConfig
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Date-aligned (train_rows, val_rows) index arrays for each CV fold.

    Shared by the backtest and HPO so both optimise and evaluate on exactly
    the same expanding windows and embargo gap.
    """
    date_pos = _date_positions(features)
    n_dates = int(date_pos.max()) + 1
    cv = TimeSeriesCV(
        n_splits=config.n_splits, gap=config.gap, min_train_size=config.min_train_size
    )
    folds = []
    for fold in cv.split(n_dates):
        train_rows = np.flatnonzero(date_pos < fold.train_end)
        val_rows = np.flatnonzero(
            (date_pos >= fold.val_start) & (date_pos < fold.val_start + fold.val_idx.size)
        )
        folds.append((train_rows, val_rows))
    return folds


@dataclass
class FoldRecord:
    """Out-of-fold predictions for one model on one CV fold."""

    model: str
    fold: int
    dates: np.ndarray
    series: np.ndarray
    y_true: np.ndarray
    y_pred: np.ndarray

    @property
    def mae(self) -> float:
        return float(np.mean(np.abs(self.y_true - self.y_pred)))


@dataclass
class BacktestResult:
    """All runs, all folds, and the figures for the report.

    Holdout protocol: folds ``0..n-2`` are the *selection* folds, the last
    fold is the *test window*. ``runs`` carry the test-window metrics as the
    headline (plus ``legacy_pooled_*``); champion selection only ever reads
    the selection folds. ``multistep`` optionally carries the direct
    multi-horizon track result (protocol ``direct_multihorizon_v1``) — the
    primary headline; the nowcast ladder above stays frozen and is never
    mixed into the multi-step leaderboard.
    """

    runs: list[RunResult] = field(default_factory=list)
    folds: list[FoldRecord] = field(default_factory=list)
    horizon_mae: dict[str, list[float]] = field(default_factory=dict)
    horizon_mase: dict[str, list[float]] = field(default_factory=dict)
    multistep: Any | None = None

    def last_fold(self, model: str) -> FoldRecord:
        recs = [f for f in self.folds if f.model == model]
        return recs[-1]

    def fold_maes(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for f in self.folds:
            out.setdefault(f.model, []).append(f.mae)
        return out

    def selection_fold_ids(self) -> list[int]:
        """Folds 1..n-1 (0-based 0..n-2) — the only folds selection may read."""
        ids = sorted({f.fold for f in self.folds})
        return ids[:-1]

    def test_fold_id(self) -> int:
        """The final rolling-origin window — scored once, never read for selection."""
        return max(f.fold for f in self.folds)

    def _records(self, model: str, fold_ids: set[int] | None = None) -> list[FoldRecord]:
        return [
            f for f in self.folds if f.model == model and (fold_ids is None or f.fold in fold_ids)
        ]

    def pooled_mae(self, model: str, fold_ids: set[int] | None = None) -> float:
        """Pooled MAE over the given folds (default: all) from out-of-fold records."""
        recs = self._records(model, fold_ids)
        total = sum(float(np.abs(r.y_true - r.y_pred).sum()) for r in recs)
        count = sum(r.y_true.size for r in recs)
        return total / count if count else float("nan")


def _mase_scale(
    y_hist: np.ndarray, series_hist: np.ndarray, season: int = 7
) -> tuple[np.ndarray, np.ndarray]:
    """Per-series MASE scale: mean in-sample |lag-season diff| over the history.

    Vectorized: rows of a series keep date order after a stable group-sort, so
    the seasonal difference within each contiguous segment is exactly the
    in-sample one-step seasonal-naive error. Series without ``season + 1``
    history points get scale 0 (excluded from MASE by the caller).
    """
    uniques, codes = np.unique(series_hist, return_inverse=True)
    order = np.argsort(codes, kind="stable")
    y_sorted = y_hist[order].astype(float)
    c_sorted = codes[order]
    starts = np.flatnonzero(np.r_[True, c_sorted[1:] != c_sorted[:-1]])
    counts = np.diff(np.r_[starts, len(c_sorted)])
    scales = np.zeros(len(uniques))
    for si, (start, cnt) in enumerate(zip(starts.tolist(), counts.tolist(), strict=True)):
        seg = y_sorted[start : start + cnt]
        if cnt > season:
            scales[si] = float(np.mean(np.abs(seg[season:] - seg[:-season])))
    return uniques, scales


def _fold_mase_parts(
    y_train: np.ndarray,
    series_train: np.ndarray,
    y_val: np.ndarray,
    series_val: np.ndarray,
    err_val: np.ndarray,
    season: int = 7,
) -> tuple[float, float]:
    """Pooled MASE numerator/denominator for one fold.

    Denominator is the fold's per-series in-sample seasonal-naive scale
    evaluated at the val rows; rows whose series lacks history are excluded.
    """
    uniques, scales = _mase_scale(y_train, series_train, season)
    idx = np.clip(np.searchsorted(uniques, series_val), 0, len(uniques) - 1)
    hit = uniques[idx] == series_val
    val_scale = np.where(hit, scales[idx], 0.0)
    mask = val_scale > 0
    return float(np.abs(err_val[mask]).sum()), float(val_scale[mask].sum())


def _horizon_metrics(
    dates: np.ndarray,
    series: np.ndarray,
    err: np.ndarray,
    scales: dict[str, float],
    n_horizons: int = EVAL_HORIZON_DAYS,
) -> tuple[list[float], list[float]]:
    """Per-horizon MAE/MASE over the final ``n_horizons`` days of a window.

    Horizon h = the h-th day of the evaluation block for each series
    (chronological rank within the block, rows arrive in date order) —
    identical to the demo payload's forecast-window convention. MASE divides
    each row's |error| by its series' in-sample seasonal scale (rows without
    a scale are excluded); a horizon with no rows yields NaN.
    """
    mae = [float("nan")] * n_horizons
    mase = [float("nan")] * n_horizons
    if dates.size == 0:
        return mae, mase
    block_start = dates.max() - np.timedelta64(n_horizons - 1, "D")
    position: dict[str, int] = {}
    err_sum = np.zeros(n_horizons)
    err_cnt = np.zeros(n_horizons)
    ratio_sum = np.zeros(n_horizons)
    ratio_cnt = np.zeros(n_horizons)
    for i in np.flatnonzero(dates >= block_start):
        sid = str(series[i])
        h = position.get(sid, 0)
        if h >= n_horizons:
            continue
        position[sid] = h + 1
        err_sum[h] += abs(float(err[i]))
        err_cnt[h] += 1
        scale = scales.get(sid, 0.0)
        if scale > 0:
            ratio_sum[h] += abs(float(err[i])) / scale
            ratio_cnt[h] += 1
    for h in range(n_horizons):
        if err_cnt[h]:
            mae[h] = float(err_sum[h] / err_cnt[h])
        if ratio_cnt[h]:
            mase[h] = float(ratio_sum[h] / ratio_cnt[h])
    return mae, mase


def backtest(
    features: pl.DataFrame, config: ForecastConfig, specs: list[ModelSpec] | None = None
) -> BacktestResult:
    """Run every model (or a chosen subset) through the expanding-window backtest.

    Splits are computed on *dates* (one expanding window shared by all series)
    and then mapped to row indices, so no date block is ever split across
    train/validation and the embargo ``gap`` holds at day granularity.

    Frozen holdout: the last rolling-origin window is the test window. Each
    run's headline metrics (mae/rmse/mape_pct/mase, plus bias/wape and the
    fold/horizon suite) are computed on that window only; the pre-holdout
    all-fold pooled values are kept as ``legacy_pooled_*``. Champion selection
    (:func:`best_model`) pools folds 1..n-1 only — never the test window.
    """
    result = BacktestResult()
    folds = cv_row_folds(features, config)
    n_folds = len(folds)
    logger.info("backtest: %d folds over the shared date grid (gap=%d)", n_folds, config.gap)

    for spec in specs if specs is not None else model_specs():
        x, y, dates, series = to_xy(features, config, spec)
        pooled_true: list[np.ndarray] = []
        pooled_pred: list[np.ndarray] = []
        fold_maes: list[float] = []
        mase_num, mase_den = 0.0, 0.0
        test_true: np.ndarray | None = None
        test_pred: np.ndarray | None = None
        test_dates: np.ndarray | None = None
        test_series: np.ndarray | None = None
        test_num, test_den = 0.0, 0.0
        test_scales: dict[str, float] = {}
        for k, (train_rows, val_rows) in enumerate(folds):
            model = spec.build(config)
            model.fit(x[train_rows], y[train_rows])
            y_pred = model.predict(x[val_rows])
            pooled_true.append(y[val_rows])
            pooled_pred.append(y_pred)
            fold_maes.append(float(np.mean(np.abs(y[val_rows] - y_pred))))
            num, den = _fold_mase_parts(
                y[train_rows],
                series[train_rows],
                y[val_rows],
                series[val_rows],
                y[val_rows] - y_pred,
            )
            mase_num += num
            mase_den += den
            if k == n_folds - 1:
                test_true, test_pred = y[val_rows], y_pred
                test_dates, test_series = dates[val_rows], series[val_rows]
                test_num, test_den = num, den
                uniq, sc = _mase_scale(y[train_rows], series[train_rows])
                test_scales = {str(s): float(v) for s, v in zip(uniq, sc, strict=True)}
            result.folds.append(
                FoldRecord(
                    model=spec.name,
                    fold=k,
                    dates=dates[val_rows],
                    series=series[val_rows],
                    y_true=y[val_rows],
                    y_pred=y_pred,
                )
            )
        if test_true is None or test_pred is None or test_dates is None or test_series is None:
            raise ValueError("backtest produced no test fold — n_splits must be >= 2")
        err_test = test_pred - test_true

        # Headline: test-window metrics (+ bias/wape), then the legacy pooled set.
        headline = regression_metrics(test_true.tolist(), test_pred.tolist())
        by_name = {m.name: m for m in headline}
        test_mase = test_num / test_den if test_den > 0 else float("nan")
        abs_actual = float(np.abs(test_true).sum())
        wape = float(np.abs(err_test).sum() / abs_actual) if abs_actual > 0 else float("nan")
        legacy = regression_metrics(
            np.concatenate(pooled_true).tolist(), np.concatenate(pooled_pred).tolist()
        )
        legacy_by_name = {m.name: m for m in legacy}
        legacy_mase = mase_num / mase_den if mase_den > 0 else float("nan")
        metrics = [
            by_name["mae"],
            by_name["rmse"],
            by_name["mape_pct"],
            MetricResult("mase", test_mase, higher_is_better=False),
            MetricResult("bias", float(np.mean(err_test)), higher_is_better=False),
            MetricResult("wape", wape, higher_is_better=False),
            MetricResult("fold_mae_std", float(np.std(fold_maes)), higher_is_better=False),
            MetricResult(
                "fold_mae_range",
                float(max(fold_maes) - min(fold_maes)),
                higher_is_better=False,
            ),
            MetricResult("legacy_pooled_mae", legacy_by_name["mae"].value, higher_is_better=False),
            MetricResult(
                "legacy_pooled_rmse", legacy_by_name["rmse"].value, higher_is_better=False
            ),
            MetricResult(
                "legacy_pooled_mape_pct", legacy_by_name["mape_pct"].value, higher_is_better=False
            ),
            MetricResult("legacy_pooled_mase", legacy_mase, higher_is_better=False),
        ]
        result.runs.append(RunResult(name=spec.name, metrics=metrics))
        h_mae, h_mase = _horizon_metrics(test_dates, test_series, err_test, test_scales)
        result.horizon_mae[spec.name] = h_mae
        result.horizon_mase[spec.name] = h_mase
        logger.info(
            "%s: test MAE=%.3f RMSE=%.3f MAPE=%.2f%% MASE=%.3f bias=%.3f wape=%.4f "
            "(legacy pooled MAE=%.3f)",
            spec.name,
            by_name["mae"].value,
            by_name["rmse"].value,
            by_name["mape_pct"].value,
            test_mase,
            float(np.mean(err_test)),
            wape,
            legacy_by_name["mae"].value,
        )
    return result


def _is_naive(name: str) -> bool:
    """Naive floors: ``naive_mean`` / ``naive_last`` / ``seasonal_naive``.

    Substring match (same hint list as :func:`portfolio_core.plotting.style_runs`):
    ``name.startswith("naive_")`` silently dropped ``seasonal_naive`` from the
    floor candidates.
    """
    return "naive" in name


def best_model(result: BacktestResult) -> str:
    """The non-naive model with the lowest pooled MAE over folds 1..n-1.

    Selection reads ONLY the selection folds — the test window never
    influences which model is promoted (frozen protocol, tested by shuffling
    the test fold's actuals and asserting the pick is unchanged).
    """
    selection = set(result.selection_fold_ids())
    candidates = [r.name for r in result.runs if not _is_naive(r.name)]
    return min(candidates, key=lambda n: result.pooled_mae(n, selection))


def strongest_naive(result: BacktestResult) -> str:
    """The naive baseline with the lowest pooled MAE over folds 1..n-1."""
    selection = set(result.selection_fold_ids())
    candidates = [r.name for r in result.runs if _is_naive(r.name)]
    return min(candidates, key=lambda n: result.pooled_mae(n, selection))


def _example_series(series: np.ndarray, y: np.ndarray, n: int, fallback: list[str]) -> list[str]:
    """Pick ``n`` representative series: ``fallback`` showcase ids when present
    in the data, topped up (or replaced) by the most active series — most
    non-zero days, ties broken by total volume.

    The synthetic panel uses the hard-coded ``store_k|product_k`` showcase
    picks; the UCI track names series ``country|stock_code``, which those ids
    never match — the activity ranking is what keeps the figure non-empty
    there.
    """
    picked: list[str] = []
    present = set(np.unique(series).tolist()) if series.size else set()
    picked.extend(s for s in fallback if s in present)
    if len(picked) < n:
        uniques, inv = np.unique(series, return_inverse=True)
        nonzero = np.bincount(inv, weights=(y > 0).astype(float))
        totals = np.bincount(inv, weights=np.asarray(y, dtype=float))
        order = np.lexsort((totals, nonzero))[::-1]
        for i in order:
            sid = str(uniques[i])
            if sid not in picked:
                picked.append(sid)
            if len(picked) >= n:
                break
    return picked[:n]


def _display_series(sids: list[str]) -> dict[str, str]:
    """Short legend labels: strip a shared ``store|`` prefix (on the UCI track
    every example series sits in the same top country, so the prefix carries
    no information but doubles the label length)."""
    if not (sids and all("|" in s for s in sids)):
        return {s: s for s in sids}
    prefix = sids[0]
    for sid in sids[1:]:
        while prefix and not sid.startswith(prefix):
            prefix = prefix[:-1]
    if prefix.endswith("|") and len(prefix) < min(len(s) for s in sids):
        return {s: s[len(prefix) :] for s in sids}
    return {s: s for s in sids}


def figure_forecast_vs_actual(result: BacktestResult) -> go.Figure:
    """Best model vs strongest naive on two representative series, test window.

    Overlaying the naive floor on the same axes makes the improvement
    (and where it comes from — structure the naive floor cannot see)
    visible at a glance. Both picks come from the selection folds only;
    the plotted window is the final holdout they never saw.
    """
    model = best_model(result)
    naive = strongest_naive(result)
    rec = result.last_fold(model)
    rec_n = result.last_fold(naive)
    fig = go.Figure()
    sids = _example_series(rec.series, rec.y_true, len(EXAMPLE_SERIES), EXAMPLE_SERIES)
    short = _display_series(sids)
    for sid in sids:
        mask = rec.series == sid
        if not mask.any():
            continue
        label = short[sid]
        fig.add_scatter(x=rec.dates[mask], y=rec.y_true[mask], name=f"{label} actual", mode="lines")
        fig.add_scatter(
            x=rec.dates[mask],
            y=rec.y_pred[mask],
            name=f"{label} {model}",
            mode="lines",
            line={"dash": "dash"},
        )
        fig.add_scatter(
            x=rec.dates[mask],
            y=rec_n.y_pred[mask],
            name=f"{label} {naive} (naive)",
            mode="lines",
            line={"dash": "dot"},
        )
    fig.update_layout(title="Forecast vs actual — champion vs strongest naive")
    # platform storytelling convention: naive floor demoted, best run promoted
    style_runs(fig, best=model)
    add_takeaway(
        fig,
        "two example series, final holdout window — units/day; actual solid, champion dashed, "
        "naive dotted; champion picked on folds 1..n-1 only",
    )
    return apply_theme(fig)


def figure_metrics_bars(result: BacktestResult) -> go.Figure:
    """Two-panel metric ladder: (a) MAE + RMSE in units; (b) MASE vs its 1.0
    in-sample-scale reference line.

    MAPE stays off the chart: its % scale is unit-incompatible with MAE/RMSE
    (and not decision-grade on zero-heavy demand) — it is reported in
    metrics.json and the docs results table instead. The MASE scale is the
    seasonal-naive's in-sample error, so 1.0 is only a scale reference — the
    naive itself lands wherever its own holdout error puts it.
    """
    runs = result.runs
    names = [r.name for r in runs]

    def _value(run: RunResult, metric: str) -> float:
        m = run.get(metric)
        return m.value if m is not None else float("nan")

    mae = [_value(r, "mae") for r in runs]
    rmse = [_value(r, "rmse") for r in runs]
    mase = [_value(r, "mase") for r in runs]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("MAE + RMSE (units)", "MASE vs the 1.0 in-sample-scale reference"),
    )
    fig.add_bar(x=names, y=mae, name="mae", row=1, col=1)
    fig.add_bar(x=names, y=rmse, name="rmse", row=1, col=1)
    fig.add_bar(
        x=names,
        y=mase,
        name="mase",
        row=1,
        col=2,
        showlegend=False,
        marker_color=["#2dd4bf" if v < 1 else "#64748b" for v in mase],
        text=[f"{v:.3f}" for v in mase],
        textposition="outside",
    )
    fig.add_shape(
        type="line",
        xref="x2 domain",
        x0=0,
        x1=1,
        yref="y2",
        y0=1.0,
        y1=1.0,
        line={"dash": "dot", "color": "#fbbf24"},
    )
    fig.update_layout(
        title="MAE, RMSE and MASE by run — final holdout window",
        barmode="group",
        yaxis_title="units",
        yaxis2_title="MASE",
    )
    fig.update_xaxes(tickangle=-30)
    apply_theme(fig)
    add_takeaway(
        fig,
        "bars = final holdout window (last origin), one score per run — MASE against "
        "its 1.0 in-sample-scale reference (the scale comes from a quieter in-sample "
        "period, so the seasonal-naive's own bar need not sit at 1.0); MAPE omitted: "
        "with ~89% zero-demand days, near-zero actuals inflate it (hundreds of %), so "
        "it is not decision-grade here",
    )
    return fig


def figure_fold_stability(result: BacktestResult) -> go.Figure:
    """MAE per CV fold per model — exposes drift/instability a mean would hide.

    The vertical line separates the selection folds (1..n-1 — the only folds
    the champion pick may read) from the final holdout window (fold n).
    """
    fig = go.Figure()
    maes = result.fold_maes()
    n_folds = max(len(values) for values in maes.values())
    for model, values in maes.items():
        fig.add_scatter(
            x=list(range(1, len(values) + 1)), y=values, name=model, mode="lines+markers"
        )
    fig.add_shape(
        type="line",
        xref="x",
        x0=n_folds - 0.5,
        x1=n_folds - 0.5,
        yref="paper",
        y0=0,
        y1=1,
        line={"dash": "dash", "color": "#fbbf24"},
    )
    fig.add_annotation(
        x=n_folds - 0.4,
        y=1,
        xref="x",
        yref="paper",
        text="test window",
        showarrow=False,
        yanchor="bottom",
    )
    fig.update_layout(
        title="MAE per CV fold, by run",
        xaxis_title="fold",
    )
    style_runs(fig, best=best_model(result))
    add_takeaway(
        fig,
        "expanding-window CV with 7-day embargo — folds 1..n-1 select the champion, "
        "the final fold is the one-shot test window",
    )
    return apply_theme(fig)


EDA_SERIES = ["store_0|product_0", "store_0|product_5", "store_3|product_0", "store_3|product_5"]


def figure_eda_series_overview(panel: pl.DataFrame) -> go.Figure:
    """Sample of raw store-product daily series — trend and weekly seasonality."""
    df = panel.with_columns((pl.col("store") + "|" + pl.col("product")).alias("series_id"))
    fig = go.Figure()
    sids = _example_series(
        df["series_id"].to_numpy(), df["units"].to_numpy(), len(EDA_SERIES), EDA_SERIES
    )
    for sid in sids:
        sub = df.filter(pl.col("series_id") == sid).sort("date")
        fig.add_scatter(x=sub["date"].to_numpy(), y=sub["units"].to_numpy(), name=sid, mode="lines")
    fig.update_layout(
        title="Example store-product daily series",
        yaxis_title="units",
    )
    add_takeaway(fig, "raw units before any model runs — 4 example series across stores")
    return apply_theme(fig)


def figure_eda_units_distribution(panel: pl.DataFrame) -> go.Figure:
    """Histogram of daily units over the whole panel (all series pooled)."""
    fig = go.Figure()
    fig.add_histogram(x=panel["units"].to_numpy(), nbinsx=60, name="units")
    fig.update_layout(
        title="Daily-units distribution across the hierarchy",
        xaxis_title="units",
    )
    add_takeaway(fig, "all store-product series pooled — right-skewed levels differ by design")
    return apply_theme(fig)


def _json_safe(value: Any) -> Any:
    """Recursively replace non-finite floats with None for strict-JSON output."""
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _finalize_metrics_json(settings: DemandSettings, result: BacktestResult) -> None:
    """Augment the ReportBuilder's metrics.json with the metric-suite extras.

    Adds the list-valued metrics (``fold_maes``, ``horizon_mae``, ``horizon_mase``)
    that the platform MetricResult (float-only) cannot carry, plus the machine-
    checkable ``_meta`` protocol block. Existing float keys written by the
    ReportBuilder (headline test-window metrics + ``legacy_pooled_*``) stay.
    """
    path = Path(settings.reports_dir) / "metrics.json"
    metrics: dict[str, Any] = json.loads(path.read_text())
    fold_maes = result.fold_maes()
    for run in result.runs:
        block = metrics[run.name]
        block["fold_maes"] = fold_maes[run.name]
        block["horizon_mae"] = result.horizon_mae[run.name]
        block["horizon_mase"] = result.horizon_mase[run.name]
    n_folds = max(f.fold for f in result.folds) + 1
    metrics["_meta"] = {
        "protocol": "rolling_origin_holdout_v1",
        "best_model": best_model(result),
        "strongest_naive": strongest_naive(result),
        "selection_rule": "best_model = lowest pooled MAE over the selection folds "
        "(origins 1..n-1) only; the test window never influences selection",
        "selection_used_origins": list(range(1, n_folds)),
        "test_origin": n_folds,
        "horizon_days": EVAL_HORIZON_DAYS,
        "headline_semantics": "per-model mae/rmse/mape_pct/mase are final-holdout-window "
        "numbers (origin n, scored once); legacy_pooled_* retains the previous "
        "all-fold pooled headline for comparison",
    }
    path.write_text(json.dumps(_json_safe(metrics), indent=2))


def write_evaluation_metadata(
    settings: DemandSettings, config: ForecastConfig, result: BacktestResult
) -> Path:
    """Persist the frozen evaluation protocol as machine-checkable JSON.

    ``reports*/evaluation_metadata.json`` states the rolling-origin spec, the
    holdout designation, the exact origins used for selection vs the single
    test origin, the within-train-window preprocessing guarantee, and every
    metric definition — the audit anchor for the headline numbers.
    """
    n_folds = max(f.fold for f in result.folds) + 1
    test_rec = result.last_fold(best_model(result))
    test_dates = np.sort(np.unique(test_rec.dates))
    origin_spacing = (
        int((np.datetime64(test_dates[-1]) - np.datetime64(test_dates[0])) / np.timedelta64(1, "D"))
        + 1
    )
    meta: dict[str, Any] = {
        "protocol": "rolling_origin_holdout_v1",
        "rolling_origin": {
            "n_origins": n_folds,
            "origin_spacing_days": origin_spacing,
            "horizon_days": EVAL_HORIZON_DAYS,
            "embargo_gap_days": config.gap,
            "min_train_size_dates": config.min_train_size,
            "test_window": {
                "origin": n_folds,
                "start": str(test_dates[0])[:10],
                "end": str(test_dates[-1])[:10],
                "n_days": origin_spacing,
            },
        },
        "holdout_designation": "last origin = test; selection used origins 1..n-1 only",
        "selection_used_origins": list(range(1, n_folds)),
        "test_origin": n_folds,
        "selection_rule": "champion (best_model) = lowest pooled MAE over origins 1..n-1; "
        "all candidates are then scored exactly once on the test window and those "
        "are the committed headline metrics",
        "preprocessing_statement": "Feature engineering uses shift-only lags and "
        "deterministic calendar encodings (no statistic is estimated on future rows); "
        "every model, the ridge StandardScaler, the MASE seasonal denominator and the "
        "conformal calibration widths are fit within the training window of each fold; "
        "the test window is scored once and never read for selection",
        "metric_definitions": METRIC_DEFINITIONS,
        "best_model": best_model(result),
        "strongest_naive": strongest_naive(result),
    }
    out = Path(settings.reports_dir) / "evaluation_metadata.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_json_safe(meta), indent=2))
    logger.info("evaluation metadata -> %s", out)
    return out


def evaluate(
    settings: DemandSettings, config: ForecastConfig, features_path: Path | None = None
) -> BacktestResult:
    """Run the full backtest, persist metrics.json + report.html + figures.

    Runs both tracks: the frozen nowcast ladder (rolling_origin_holdout_v1)
    and the primary direct multi-horizon track (direct_multihorizon_v1,
    multihorizon.py) — merged into the same artifact files under ``_multistep``
    / ``multi_horizon`` keys so the nowcast numbers stay intact and the demo
    payload keeps working.
    """
    path = features_path or (settings.data_dir / "features.parquet")
    features = pl.read_parquet(path)
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    result = backtest(features, config)

    # Primary multi-step track: direct per-horizon models on weekly origins.
    from demand_forecasting.multihorizon import (
        merge_evaluation_metadata,
        merge_metrics_json,
        run_multistep,
        save_multistep_figures,
    )

    ms_result = run_multistep(settings, config, panel)
    result.multistep = ms_result

    figures = {
        "eda_series_overview": figure_eda_series_overview(panel),
        "eda_units_distribution": figure_eda_units_distribution(panel),
        "forecast_vs_actual": figure_forecast_vs_actual(result),
        "metrics_bars": figure_metrics_bars(result),
        "fold_stability": figure_fold_stability(result),
        **ms_result.figures,
    }
    builder = ReportBuilder(
        # EvalReport appends "— evaluation report" itself.
        title="Hierarchical Demand Forecasting",
        figures_dir=settings.reports_dir / "figures",
    )
    for run in result.runs:
        builder.add_run(run)
    builder.build(settings.reports_dir, figures=figures)
    _finalize_metrics_json(settings, result)
    merge_metrics_json(settings, ms_result)
    write_evaluation_metadata(settings, config, result)
    merge_evaluation_metadata(settings, ms_result)
    save_multistep_figures(settings, ms_result)
    for name, fig in figures.items():
        save_json(fig, Path(settings.reports_dir) / "figures" / f"{name}.json")
    logger.info(
        "report -> %s (metrics.json, evaluation_metadata.json, report.html, figures/*.html+json)",
        settings.reports_dir,
    )
    return result
