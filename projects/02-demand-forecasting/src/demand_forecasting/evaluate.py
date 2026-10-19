"""Honest backtest: expanding-window time CV + platform metrics + figures.

Leakage control (playbook: random splits mask drift):
- splits come from :class:`portfolio_core.timecv.TimeSeriesCV` (train strictly
  before validation, plus an embargo ``gap``),
- features were built with ``shift`` only (see features.py),
- metrics are pooled out-of-fold predictions — never in-sample readings.
"""

from dataclasses import dataclass, field
from pathlib import Path

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
    """All runs, all folds, and the figures for the report."""

    runs: list[RunResult] = field(default_factory=list)
    folds: list[FoldRecord] = field(default_factory=list)

    def last_fold(self, model: str) -> FoldRecord:
        recs = [f for f in self.folds if f.model == model]
        return recs[-1]

    def fold_maes(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for f in self.folds:
            out.setdefault(f.model, []).append(f.mae)
        return out


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


def backtest(
    features: pl.DataFrame, config: ForecastConfig, specs: list[ModelSpec] | None = None
) -> BacktestResult:
    """Run every model (or a chosen subset) through the expanding-window backtest.

    Splits are computed on *dates* (one expanding window shared by all series)
    and then mapped to row indices, so no date block is ever split across
    train/validation and the embargo ``gap`` holds at day granularity.
    Reports MAE/RMSE/MAPE (platform metrics) plus MASE — MAE scaled by the
    fold's in-sample seasonal-naive error per series.
    """
    result = BacktestResult()
    folds = cv_row_folds(features, config)
    logger.info("backtest: %d folds over the shared date grid (gap=%d)", len(folds), config.gap)

    for spec in specs if specs is not None else model_specs():
        x, y, dates, series = to_xy(features, config, spec)
        pooled_true: list[np.ndarray] = []
        pooled_pred: list[np.ndarray] = []
        mase_num, mase_den = 0.0, 0.0
        for k, (train_rows, val_rows) in enumerate(folds):
            model = spec.build(config)
            model.fit(x[train_rows], y[train_rows])
            y_pred = model.predict(x[val_rows])
            pooled_true.append(y[val_rows])
            pooled_pred.append(y_pred)
            num, den = _fold_mase_parts(
                y[train_rows],
                series[train_rows],
                y[val_rows],
                series[val_rows],
                y[val_rows] - y_pred,
            )
            mase_num += num
            mase_den += den
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
        metrics = regression_metrics(
            np.concatenate(pooled_true).tolist(), np.concatenate(pooled_pred).tolist()
        )
        mase = mase_num / mase_den if mase_den > 0 else float("nan")
        metrics.append(MetricResult("mase", mase, higher_is_better=False))
        result.runs.append(RunResult(name=spec.name, metrics=metrics))
        logger.info(
            "%s: MAE=%.3f RMSE=%.3f MAPE=%.2f%% MASE=%.3f",
            spec.name,
            metrics[0].value,
            metrics[1].value,
            metrics[2].value,
            mase,
        )
    return result


def _mae(result: BacktestResult, name: str) -> float:
    m = next((r.get("mae") for r in result.runs if r.name == name), None)
    return m.value if m is not None else float("nan")


def _is_naive(name: str) -> bool:
    """Naive floors: ``naive_mean`` / ``naive_last`` / ``seasonal_naive``.

    Substring match (same hint list as :func:`portfolio_core.plotting.style_runs`):
    ``name.startswith("naive_")`` silently dropped ``seasonal_naive`` from the
    floor candidates.
    """
    return "naive" in name


def best_model(result: BacktestResult) -> str:
    """The non-naive model with the lowest pooled MAE."""
    candidates = [r.name for r in result.runs if not _is_naive(r.name)]
    return min(candidates, key=lambda n: _mae(result, n))


def strongest_naive(result: BacktestResult) -> str:
    """The naive baseline with the lowest pooled MAE (the honest floor)."""
    candidates = [r.name for r in result.runs if _is_naive(r.name)]
    return min(candidates, key=lambda n: _mae(result, n))


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
    """Best model vs strongest naive on two representative series, last fold.

    Overlaying the naive floor on the same axes makes the improvement
    (and where it comes from — structure the naive floor cannot see)
    visible at a glance.
    """
    model = best_model(result)
    naive = strongest_naive(result)
    rec = result.last_fold(model)
    rec_n = result.last_fold(naive)
    reduction = 1.0 - rec.mae / max(rec_n.mae, 1e-12)
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
    fig.update_layout(
        title=f"{model} clears the {naive} floor by {reduction:.0%} MAE — last CV fold"
    )
    # platform storytelling convention: naive floor demoted, best run promoted
    style_runs(fig, best=model)
    add_takeaway(
        fig,
        f"takeaway: {model} beats the {naive} floor by {reduction:.0%} MAE "
        "on this fold; the residual gap is day-over-day noise",
    )
    # six legend entries need a vertical legend on the right, not the theme's
    # horizontal strip (it would wrap over the two-line title)
    fig.update_layout(
        legend={"orientation": "v", "x": 1.01, "xanchor": "left", "y": 1.0, "yanchor": "top"},
        margin={"r": 200},
    )
    return apply_theme(fig)


def figure_metrics_bars(result: BacktestResult) -> go.Figure:
    """Two-panel metric ladder: (a) MAE + RMSE in units; (b) MASE vs parity.

    MAPE stays off the chart: its % scale is unit-incompatible with MAE/RMSE
    (and not decision-grade on zero-heavy demand) — it is reported in
    metrics.json and the docs results table instead.
    """
    runs = result.runs
    names = [r.name for r in runs]

    def _value(run: RunResult, metric: str) -> float:
        m = run.get(metric)
        return m.value if m is not None else float("nan")

    mae = [_value(r, "mae") for r in runs]
    rmse = [_value(r, "rmse") for r in runs]
    mase = [_value(r, "mase") for r in runs]
    below = [r.name for r in runs if (m := r.get("mase")) is not None and m.value < 1]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("MAE + RMSE (units)", "MASE — 1.0 = seasonal-naive parity"),
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
    head = (
        f"Only {below[0]} clears the seasonal-naive floor (MASE < 1)"
        if len(below) == 1
        else f"{len(below)} runs clear the seasonal-naive floor (MASE < 1)"
    )
    fig.update_layout(
        title=f"{head} — pooled out-of-fold ladder",
        barmode="group",
        yaxis_title="units",
        yaxis2_title="MASE",
    )
    fig.update_xaxes(tickangle=-30)
    apply_theme(fig)
    add_takeaway(
        fig,
        "takeaway: MAPE omitted here — its % scale is unit-incompatible with "
        "unit-scaled errors (and not decision-grade at 89% zeros); see metrics.json",
    )
    # two-line title + legend need more headroom than add_takeaway's default;
    # the rotated run-name ticks need the deeper bottom margin
    fig.update_layout(margin={"t": 125, "l": 60, "r": 30, "b": 90})
    return fig


def figure_fold_stability(result: BacktestResult) -> go.Figure:
    """MAE per CV fold per model — exposes drift/instability a mean would hide."""
    fig = go.Figure()
    maes = result.fold_maes()
    for model, values in maes.items():
        fig.add_scatter(
            x=list(range(1, len(values) + 1)), y=values, name=model, mode="lines+markers"
        )
    fig.update_layout(
        title="Every run degrades on later folds - trend drift the honest backtest prices in",
        xaxis_title="fold",
    )
    style_runs(fig, best=best_model(result))
    add_takeaway(
        fig,
        "takeaway: every run degrades on later folds (trend drift) — the honest "
        "backtest prices in drift a random split would hide",
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
        title="Trend and a clear weekly cycle are visible in raw units before any model runs",
        yaxis_title="units",
        # four full-length series ids wrap the theme's horizontal legend into
        # the title — give it its own row
        margin={"t": 100, "l": 60, "r": 30, "b": 50},
    )
    return apply_theme(fig)


def figure_eda_units_distribution(panel: pl.DataFrame) -> go.Figure:
    """Histogram of daily units over the whole panel (all series pooled)."""
    fig = go.Figure()
    fig.add_histogram(x=panel["units"].to_numpy(), nbinsx=60, name="units")
    fig.update_layout(
        title="Store-product levels differ by design - a single global mean posts MAE 31.8",
        xaxis_title="units",
    )
    return apply_theme(fig)


def evaluate(
    settings: DemandSettings, config: ForecastConfig, features_path: Path | None = None
) -> BacktestResult:
    """Run the full backtest, persist metrics.json + report.html + figures."""
    path = features_path or (settings.data_dir / "features.parquet")
    features = pl.read_parquet(path)
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    result = backtest(features, config)

    figures = {
        "eda_series_overview": figure_eda_series_overview(panel),
        "eda_units_distribution": figure_eda_units_distribution(panel),
        "forecast_vs_actual": figure_forecast_vs_actual(result),
        "metrics_bars": figure_metrics_bars(result),
        "fold_stability": figure_fold_stability(result),
    }
    builder = ReportBuilder(
        title="Hierarchical Demand Forecasting — evaluation",
        figures_dir=settings.reports_dir / "figures",
    )
    for run in result.runs:
        builder.add_run(run)
    builder.build(settings.reports_dir, figures=figures)
    for name, fig in figures.items():
        save_json(fig, Path(settings.reports_dir) / "figures" / f"{name}.json")
    logger.info(
        "report -> %s (metrics.json, report.html, figures/*.html+json)", settings.reports_dir
    )
    return result
