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
from portfolio_core.logging import get_logger
from portfolio_core.plotting import apply_theme, save_json
from portfolio_core.timecv import TimeSeriesCV
from portfolio_eval.metrics import RunResult
from portfolio_eval.ml import RunComparison, regression_metrics
from portfolio_eval.report import ReportBuilder

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.model import model_specs, to_xy

logger = get_logger(__name__)

EXAMPLE_SERIES = ["store_0|product_0", "store_3|product_5"]


def _date_positions(features: pl.DataFrame) -> np.ndarray:
    """Map each row to the positional index of its date in the sorted unique dates."""
    dates = features["date"].to_numpy()
    uniq = np.unique(dates)
    return np.searchsorted(uniq, dates)


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


def backtest(features: pl.DataFrame, config: ForecastConfig) -> BacktestResult:
    """Run every model through the expanding-window backtest.

    Splits are computed on *dates* (one expanding window shared by all series)
    and then mapped to row indices, so no date block is ever split across
    train/validation and the embargo ``gap`` holds at day granularity.
    """
    result = BacktestResult()
    date_pos = _date_positions(features)
    n_dates = int(date_pos.max()) + 1
    cv = TimeSeriesCV(
        n_splits=config.n_splits, gap=config.gap, min_train_size=config.min_train_size
    )
    folds = list(cv.split(n_dates))
    logger.info("backtest: %d folds over %d dates (gap=%d)", len(folds), n_dates, config.gap)

    for spec in model_specs():
        x, y, dates, series = to_xy(features, config, spec)
        pooled_true: list[np.ndarray] = []
        pooled_pred: list[np.ndarray] = []
        for k, fold in enumerate(folds):
            train_rows = np.flatnonzero(date_pos < fold.train_end)
            val_rows = np.flatnonzero(
                (date_pos >= fold.val_start) & (date_pos < fold.val_start + fold.val_idx.size)
            )
            model = spec.build(config)
            model.fit(x[train_rows], y[train_rows])
            y_pred = model.predict(x[val_rows])
            pooled_true.append(y[val_rows])
            pooled_pred.append(y_pred)
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
        result.runs.append(RunResult(name=spec.name, metrics=metrics))
        logger.info(
            "%s: MAE=%.3f RMSE=%.3f MAPE=%.2f%%",
            spec.name,
            metrics[0].value,
            metrics[1].value,
            metrics[2].value,
        )
    return result


def _mae(result: BacktestResult, name: str) -> float:
    m = next((r.get("mae") for r in result.runs if r.name == name), None)
    return m.value if m is not None else float("nan")


def best_model(result: BacktestResult) -> str:
    """The non-naive model with the lowest pooled MAE."""
    candidates = [r.name for r in result.runs if not r.name.startswith("naive_")]
    return min(candidates, key=lambda n: _mae(result, n))


def strongest_naive(result: BacktestResult) -> str:
    """The naive baseline with the lowest pooled MAE (the honest floor)."""
    candidates = [r.name for r in result.runs if r.name.startswith("naive_")]
    return min(candidates, key=lambda n: _mae(result, n))


def figure_forecast_vs_actual(result: BacktestResult) -> go.Figure:
    """Best model vs strongest naive on two example series, last fold.

    Overlaying the naive floor on the same axes makes the improvement
    (and where it comes from — weekday structure the naive cannot see)
    visible at a glance.
    """
    model = best_model(result)
    naive = strongest_naive(result)
    rec = result.last_fold(model)
    rec_n = result.last_fold(naive)
    fig = go.Figure()
    for sid in EXAMPLE_SERIES:
        mask = rec.series == sid
        fig.add_scatter(x=rec.dates[mask], y=rec.y_true[mask], name=f"{sid} actual", mode="lines")
        fig.add_scatter(
            x=rec.dates[mask],
            y=rec.y_pred[mask],
            name=f"{sid} {model}",
            mode="lines",
            line={"dash": "dash"},
        )
        fig.add_scatter(
            x=rec.dates[mask],
            y=rec_n.y_pred[mask],
            name=f"{sid} {naive} (naive)",
            mode="lines",
            line={"dash": "dot"},
        )
    fig.update_layout(title=f"Actual vs forecast — last CV fold ({model} vs {naive})")
    return apply_theme(fig)


def figure_metrics_bars(result: BacktestResult) -> go.Figure:
    """Grouped bar chart of MAE / RMSE / MAPE across all runs (naives included)."""
    fig = RunComparison(result.runs).figure()
    fig.update_layout(title="Per-model metrics (pooled out-of-fold)")
    return fig


def figure_fold_stability(result: BacktestResult) -> go.Figure:
    """MAE per CV fold per model — exposes drift/instability a mean would hide."""
    fig = go.Figure()
    maes = result.fold_maes()
    for model, values in maes.items():
        fig.add_scatter(
            x=list(range(1, len(values) + 1)), y=values, name=model, mode="lines+markers"
        )
    fig.update_layout(title="Fold stability (MAE per fold)", xaxis_title="fold")
    return apply_theme(fig)


EDA_SERIES = ["store_0|product_0", "store_0|product_5", "store_3|product_0", "store_3|product_5"]


def figure_eda_series_overview(panel: pl.DataFrame) -> go.Figure:
    """Sample of raw store-product daily series — trend and weekly seasonality."""
    df = panel.with_columns((pl.col("store") + "|" + pl.col("product")).alias("series_id"))
    fig = go.Figure()
    for sid in EDA_SERIES:
        sub = df.filter(pl.col("series_id") == sid).sort("date")
        fig.add_scatter(x=sub["date"].to_numpy(), y=sub["units"].to_numpy(), name=sid, mode="lines")
    fig.update_layout(
        title="Raw daily units — sample series across the hierarchy", yaxis_title="units"
    )
    return apply_theme(fig)


def figure_eda_units_distribution(panel: pl.DataFrame) -> go.Figure:
    """Histogram of daily units over the whole panel (all series pooled)."""
    fig = go.Figure()
    fig.add_histogram(x=panel["units"].to_numpy(), nbinsx=60, name="units")
    fig.update_layout(title="Daily-units distribution (all series)", xaxis_title="units")
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
