"""Hierarchical reconciliation: bottom-up coherence vs a MinT-lite adjustment.

The hierarchy is store (parent) → store-product (children, ``n_products`` per
store). The tuned model forecasts children independently, so the sum of
children need not match a direct store-level forecast. This module:

1. fits the tuned HGB at store level on aggregated series (identical backtest),
2. measures the incoherence ``d = pred_store - sum(child preds)`` per store/day,
3. estimates a scalar shrinkage ``w`` on the second-to-last fold (grid search
   minimizing the reconciled store-level MAE — the data-driven MinT-lite
   choice; a precision-ratio variant is kept for comparison),
4. reconciles child forecasts on the last fold: ``child' = child + w * d / k``.

Coherence guarantee (tested): after reconciliation the remaining incoherence
is exactly ``(1 - w)`` times the original.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_html, save_json

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.evaluate import BacktestResult, backtest
from demand_forecasting.features import build_features
from demand_forecasting.model import CATEGORICAL_FEATURES, NUMERIC_FEATURES, ModelSpec

logger = get_logger(__name__)

MODEL = "hgb_tuned"


@dataclass
class ReconciliationResult:
    """Coherence metrics before/after the MinT-lite adjustment."""

    shrinkage: float
    store_mae_before: float
    store_mae_after: float
    incoherence_before: float
    incoherence_after: float
    eval_fold: int
    n_stores: int
    n_children: int


def apply_shrinkage(
    child_sums: np.ndarray, parent_preds: np.ndarray, w: float
) -> tuple[np.ndarray, np.ndarray]:
    """Reconcile summed children toward the parent forecast (pure function).

    Returns (reconciled sums, remaining incoherence) so the coherence property
    ``incoherence_after == (1 - w) * incoherence_before`` is exact and testable.
    """
    d = parent_preds - child_sums
    reconciled = child_sums + w * d
    return reconciled, (1.0 - w) * d


def fit_shrinkage(
    child_sums: np.ndarray, parent_preds: np.ndarray, parent_true: np.ndarray
) -> float:
    """Grid-estimate the scalar shrinkage on an embargoed estimation fold.

    Picks ``w`` minimizing the reconciled store-level MAE
    ``mean |child_sum + w * d - parent_true|`` over a 0..1 grid — the
    data-driven MinT-lite choice: trust the parent forecast exactly as much as
    it actually helps on data the estimator has seen.
    """
    d = parent_preds - child_sums
    grid = np.linspace(0.0, 1.0, 21)
    losses = [float(np.mean(np.abs(child_sums + w * d - parent_true))) for w in grid]
    return float(grid[int(np.argmin(losses))])


def estimate_shrinkage(
    child_sums: np.ndarray, parent_preds: np.ndarray, child_residual_vars: np.ndarray
) -> float:
    """Scalar MinT-lite shrinkage from residual variances (precision ratio).

    ``w = var(d) / (var(d) + mean child-residual variance)`` — the fraction of
    discrepancy variance that is genuine parent-level signal rather than
    child-level noise. Clamped to [0, 1].
    """
    d = parent_preds - child_sums
    var_d = float(np.var(d))
    var_child = float(np.mean(child_residual_vars))
    w = var_d / (var_d + var_child + 1e-12)
    return float(min(1.0, max(0.0, w)))


def _store_panel(panel: pl.DataFrame) -> pl.DataFrame:
    """Aggregate the panel to store level (parent series of the hierarchy)."""
    return (
        panel.group_by(["date", "store"])
        .agg(pl.col("units").sum().alias("units"))
        .with_columns(pl.lit("total").alias("product"), pl.lit(0.0).alias("price"))
        .select(["date", "store", "product", "units", "price"])
    )


def _fold_table(
    child_result: BacktestResult, store_result: BacktestResult, fold: int
) -> pl.DataFrame:
    """Per (date, store) row: child prediction sums, parent forecast and actual."""
    child: dict[tuple[np.datetime64, str], dict[str, Any]] = {}
    for rc in [f for f in child_result.folds if f.model == MODEL and f.fold == fold]:
        for d, sid, yt, yp in zip(rc.dates, rc.series, rc.y_true, rc.y_pred, strict=True):
            key = (np.datetime64(d), str(sid).split("|")[0])
            slot = child.setdefault(key, {"child_pred": 0.0, "res": []})
            slot["child_pred"] += float(yp)
            slot["res"].append(float(yt) - float(yp))
    parent: dict[tuple[np.datetime64, str], tuple[float, float]] = {}
    for rp in [f for f in store_result.folds if f.fold == fold]:
        for d, sid, yt, yp in zip(rp.dates, rp.series, rp.y_true, rp.y_pred, strict=True):
            parent[(np.datetime64(d), str(sid).split("|")[0])] = (float(yp), float(yt))

    rows: dict[str, list[Any]] = {
        "date": [],
        "store": [],
        "child_pred": [],
        "parent_pred": [],
        "parent_true": [],
        "residual_var": [],
    }
    for key in sorted(child):
        if key not in parent:
            continue
        yp, yt = parent[key]
        rows["date"].append(str(key[0])[:10])
        rows["store"].append(key[1])
        rows["child_pred"].append(child[key]["child_pred"])
        rows["parent_pred"].append(yp)
        rows["parent_true"].append(yt)
        rows["residual_var"].append(float(np.var(child[key]["res"])))
    return pl.DataFrame(
        rows,
        schema={
            "date": pl.Date,
            "store": pl.String,
            "child_pred": pl.Float64,
            "parent_pred": pl.Float64,
            "parent_true": pl.Float64,
            "residual_var": pl.Float64,
        },
    )


def run_reconciliation(
    settings: DemandSettings, config: ForecastConfig, child_result: BacktestResult
) -> tuple[ReconciliationResult, pl.DataFrame]:
    """Estimate shrinkage on fold n-2, evaluate coherence on the last fold.

    Returns the result plus the evaluation table (used by the figure).
    """
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    store_features = build_features(_store_panel(panel), config)
    store_spec = ModelSpec(name=MODEL, numeric=NUMERIC_FEATURES, categorical=CATEGORICAL_FEATURES)
    store_result = backtest(store_features, config, specs=[store_spec])

    n_folds = len({f.fold for f in child_result.folds})
    eval_fold = n_folds - 1
    est_fold = max(0, eval_fold - 1)

    est = _fold_table(child_result, store_result, est_fold)
    w = fit_shrinkage(
        est["child_pred"].to_numpy(),
        est["parent_pred"].to_numpy(),
        est["parent_true"].to_numpy(),
    )

    hold = _fold_table(child_result, store_result, eval_fold)
    cs = hold["child_pred"].to_numpy()
    pp = hold["parent_pred"].to_numpy()
    pt = hold["parent_true"].to_numpy()
    reconciled, remaining = apply_shrinkage(cs, pp, w)

    result = ReconciliationResult(
        shrinkage=w,
        store_mae_before=float(np.mean(np.abs(cs - pt))),
        store_mae_after=float(np.mean(np.abs(reconciled - pt))),
        incoherence_before=float(np.mean(np.abs(pp - cs))),
        incoherence_after=float(np.mean(np.abs(remaining))),
        eval_fold=eval_fold,
        n_stores=config.n_stores,
        n_children=config.n_products,
    )
    out = settings.reports_dir / "reconciliation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.__dict__, indent=2))
    logger.info(
        "reconciliation (fold %d, w=%.3f): store MAE %.3f -> %.3f | incoherence %.3f -> %.3f",
        result.eval_fold,
        result.shrinkage,
        result.store_mae_before,
        result.store_mae_after,
        result.incoherence_before,
        result.incoherence_after,
    )
    return result, hold


def figure_reconciliation(result: ReconciliationResult, hold: pl.DataFrame) -> go.Figure:
    """Per-store panel: parent actual vs summed children before/after."""
    stores = sorted(hold["store"].unique().to_list())
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[f"{s} — sum of {result.n_children} products" for s in stores],
    )
    for i, store in enumerate(stores[:4]):
        row, col = i // 2 + 1, i % 2 + 1
        sub = hold.filter(pl.col("store") == store).sort("date")
        xs = sub["date"].cast(pl.String).to_list()
        cs = sub["child_pred"].to_numpy()
        pp = sub["parent_pred"].to_numpy()
        reconciled, _ = apply_shrinkage(cs, pp, result.shrinkage)
        common = {"row": row, "col": col}
        fig.add_scatter(
            x=xs,
            y=sub["parent_true"].to_list(),
            name="store actual",
            legendgroup="actual",
            showlegend=(i == 0),
            **common,
        )
        fig.add_scatter(
            x=xs,
            y=cs.tolist(),
            name="Σ children (before)",
            legendgroup="before",
            line={"dash": "dash"},
            showlegend=(i == 0),
            **common,
        )
        fig.add_scatter(
            x=xs,
            y=reconciled.tolist(),
            name="Σ children (reconciled)",
            legendgroup="after",
            line={"dash": "dot"},
            showlegend=(i == 0),
            **common,
        )
    fig.update_layout(title=f"Reconciliation coherence — fold {result.eval_fold + 1}")
    return apply_theme(fig, width=1100, height=800)


def figure_coherence_heatmap(result: ReconciliationResult, hold: pl.DataFrame) -> go.Figure:
    """Per-store mean |incoherence| before/after as an annotated heatmap."""
    stores = sorted(hold["store"].unique().to_list())
    before, after = [], []
    for store in stores:
        sub = hold.filter(pl.col("store") == store)
        cs = sub["child_pred"].to_numpy()
        pp = sub["parent_pred"].to_numpy()
        _reconciled, remaining = apply_shrinkage(cs, pp, result.shrinkage)
        before.append(float(np.mean(np.abs(pp - cs))))
        after.append(float(np.mean(np.abs(remaining))))
    fig = go.Figure()
    fig.add_heatmap(
        z=[before, after],
        x=stores,
        y=["before", f"after (w={result.shrinkage:.2f})"],
        text=[[f"{v:.1f}" for v in before], [f"{v:.1f}" for v in after]],
        texttemplate="%{text}",
        colorscale="Blues",
        showscale=False,
    )
    fig.update_layout(title="Hierarchy coherence heatmap")
    add_takeaway(
        fig,
        "mean |parent - sum(children)| per store — incoherence shrinks by exactly (1-w)",
    )
    return apply_theme(fig, width=900, height=420)


def reconcile_and_plot(
    settings: DemandSettings, config: ForecastConfig, child_result: BacktestResult
) -> ReconciliationResult:
    """Run reconciliation and persist the coherence figures (html + json)."""
    result, hold = run_reconciliation(settings, config, child_result)
    fig = figure_reconciliation(result, hold)
    save_html(fig, Path(settings.reports_dir) / "figures" / "reconciliation_coherence.html")
    save_json(fig, Path(settings.reports_dir) / "figures" / "reconciliation_coherence.json")
    heat = figure_coherence_heatmap(result, hold)
    save_html(heat, Path(settings.reports_dir) / "figures" / "coherence_heatmap.html")
    save_json(heat, Path(settings.reports_dir) / "figures" / "coherence_heatmap.json")
    return result
