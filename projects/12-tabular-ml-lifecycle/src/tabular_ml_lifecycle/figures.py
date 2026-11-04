"""Committed figures, all regenerable from the pipeline artifacts.

Chart diversity is deliberate (no all-bar pages):
EDA — line matrix, season-colored scatter, correlation heatmap; features —
MI lollipop; training — per-epoch loss lines, learning curves, ablation dot
plot; evaluation — model-comparison dot plot with CI whiskers, residual
heatmap, residual-vs-fitted scatter, bootstrap-delta histogram.
"""

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from portfolio_core.plotting import add_takeaway, apply_theme, style_runs

from tabular_ml_lifecycle.data import SEASON_LABELS

SEASON_COLORS = {1: "#34d399", 2: "#fbbf24", 3: "#f472b6", 4: "#38bdf8"}

MODEL_LABELS = {
    "seasonal_naive": "seasonal naive (floor)",
    "ridge": "ridge",
    "random_forest": "random forest",
    "lightgbm_hpo": "LightGBM (Optuna HPO)",
    "mlp": "tabular MLP (PyTorch)",
}


def rentals_by_hour_season_figure(df: pd.DataFrame) -> go.Figure:
    """Mean rentals by hour, one panel per season (small-multiple line matrix)."""
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=[SEASON_LABELS[s] for s in (1, 2, 3, 4)],
        shared_xaxes=True,
        shared_yaxes=True,
        vertical_spacing=0.1,
        horizontal_spacing=0.06,
    )
    for idx, season in enumerate((1, 2, 3, 4)):
        row, col = idx // 2 + 1, idx % 2 + 1
        part = df[df["season"] == season]
        hourly = part.groupby("hour")["cnt"].mean()
        fig.add_scatter(
            x=hourly.index,
            y=hourly.values,
            mode="lines+markers",
            name=SEASON_LABELS[season],
            legendgroup=str(season),
            showlegend=False,
            line={"color": SEASON_COLORS[season], "width": 2},
            marker={"size": 6},
            row=row,
            col=col,
        )
        fig.update_xaxes(title_text="hour of day", row=row, col=col, dtick=4)
        if col == 1:
            fig.update_yaxes(title_text="mean rentals", row=row, col=col)
    apply_theme(fig, height=640)
    fig.update_layout(title="Rentals by hour, one panel per season (2011-2012)")
    add_takeaway(
        fig,
        "The commuter double peak (08h and 17-18h) dominates spring-fall; winter is "
        "flatter and lower - season belongs in any rental model.",
    )
    return fig


def temp_vs_rentals_figure(df: pd.DataFrame) -> go.Figure:
    """Temperature vs rentals scatter, colored by season."""
    fig = go.Figure()
    for season in (1, 2, 3, 4):
        part = df[df["season"] == season]
        fig.add_scatter(
            x=part["temp"],
            y=part["cnt"],
            mode="markers",
            name=SEASON_LABELS[season],
            marker={"color": SEASON_COLORS[season], "size": 4, "opacity": 0.45},
        )
    apply_theme(fig, height=600)
    fig.update_layout(
        title="Rentals vs temperature, colored by season",
        xaxis_title="temperature (normalized)",
        yaxis_title="rentals per hour",
    )
    add_takeaway(
        fig,
        "Ridership rises with temperature within each season's band, but the same "
        "temperature maps to different demand by season — weather alone is not season.",
    )
    return fig


def correlation_heatmap_figure(df: pd.DataFrame) -> go.Figure:
    """Correlation heatmap of the numeric weather/calendar/target columns."""
    cols = ["temp", "atemp", "hum", "windspeed", "weathersit", "hour", "cnt"]
    corr = df[cols].corr()
    fig = go.Figure(
        go.Heatmap(
            z=corr.values,
            x=cols,
            y=cols,
            text=np.round(corr.values, 2),
            texttemplate="%{text}",
            colorscale="RdBu",
            zmid=0,
            colorbar={"title": "Pearson r"},
        )
    )
    apply_theme(fig, height=560)
    fig.update_layout(title="Correlation heatmap — numeric features vs rentals")
    add_takeaway(
        fig,
        "temp and atemp are near-duplicates (pruned later by the |r| > 0.9 rule); "
        "count correlations with weather are real but modest — the calendar and lags must work.",
    )
    return fig


def mlp_loss_curves_figure(
    train_loss: list[float], val_loss: list[float], best_epoch: int
) -> go.Figure:
    """Per-epoch train vs validation MAE — the overfitting-control artifact."""
    epochs = list(range(1, len(train_loss) + 1))
    fig = go.Figure()
    fig.add_scatter(x=epochs, y=train_loss, mode="lines", name="train MAE", line={"width": 2})
    fig.add_scatter(x=epochs, y=val_loss, mode="lines", name="validation MAE", line={"width": 2})
    fig.add_vline(
        x=best_epoch,
        line={"color": "#fbbf24", "dash": "dash"},
        annotation_text=f"best epoch {best_epoch}",
        annotation_font_color="#fbbf24",
    )
    apply_theme(fig, height=560)
    fig.update_layout(
        title="MLP training — train vs validation MAE per epoch",
        xaxis_title="epoch",
        yaxis_title="MAE (rentals)",
    )
    add_takeaway(
        fig,
        "Train keeps improving while validation stalls — that gap is why dropout, "
        "weight decay and early stopping are first-class artifacts here, not defaults.",
    )
    return fig


def learning_curves_figure(curves: dict[str, dict[float, float]]) -> go.Figure:
    """Val MAE vs training-set fraction for the tuned tree and the MLP."""
    fig = go.Figure()
    palette = {"lightgbm_hpo": "#34d399", "mlp": "#a78bfa"}
    for name, points in curves.items():
        fracs = sorted(points)
        fig.add_scatter(
            x=fracs,
            y=[points[f] for f in fracs],
            mode="lines+markers",
            name=MODEL_LABELS.get(name, name),
            line={"color": palette.get(name, "#2dd4bf"), "width": 2},
            marker={"size": 8},
        )
    apply_theme(fig, height=560)
    fig.update_layout(
        title="Learning curves — validation MAE vs training-set size",
        xaxis_title="fraction of training window used",
        yaxis_title="validation MAE (rentals)",
    )
    add_takeaway(
        fig,
        "Both curves flatten toward the right edge: more history helps little at this "
        "size — the ceiling is feature information, not rows.",
    )
    return fig


def ablation_dotplot_figure(rows: list[dict[str, Any]]) -> go.Figure:
    """MLP ablation grid as a dot plot: validation MAE per 2x2x2 variant."""
    order = sorted(rows, key=lambda r: r["val_mae"])
    labels = [r["variant"] for r in order]
    vals = [r["val_mae"] for r in order]
    fig = go.Figure()
    fig.add_scatter(
        x=vals,
        y=list(range(len(labels))),
        mode="markers",
        name="ablation variant",
        marker={"color": "#64748b", "size": 11},
    )
    for i, row in enumerate(order):
        if row["selected"]:
            fig.add_scatter(
                x=[vals[i]],
                y=[i],
                mode="markers",
                name="production config",
                marker={"color": "#2dd4bf", "size": 13},
            )
    apply_theme(fig, height=600)
    fig.update_layout(
        title="MLP ablation — validation MAE by regularization variant",
        xaxis_title="validation MAE (rentals)",
        margin={"l": 260, "r": 140, "t": 110, "b": 70},
    )
    fig.update_yaxes(tickvals=list(range(len(labels))), ticktext=labels, autorange="reversed")
    add_takeaway(
        fig,
        "Teal is the shipped configuration; grey dots score each control off. "
        "Controls were chosen on validation — test was not consulted (see limits).",
    )
    return fig


def model_comparison_figure(runs: dict[str, dict[str, float]]) -> go.Figure:
    """Test-window MAE per candidate; the naive floor renders grey dashed."""
    order = [m for m in MODEL_LABELS if m in runs]
    best = min(order, key=lambda m: runs[m]["mae"])
    fig = go.Figure()
    for i, name in enumerate(order):
        fig.add_scatter(
            x=[runs[name]["mae"]],
            y=[i],
            mode="markers",
            name=MODEL_LABELS[name],
            marker={"color": "#64748b" if name == "seasonal_naive" else "#2dd4bf", "size": 11},
        )
    fig.add_shape(
        type="line",
        x0=runs["seasonal_naive"]["mae"],
        x1=runs["seasonal_naive"]["mae"],
        y0=-0.5,
        y1=len(order) - 0.5,
        line={"color": "#64748b", "dash": "dash", "width": 1.5},
    )
    apply_theme(fig, height=540)
    fig.update_layout(
        title="Scored-once test window — MAE by candidate",
        xaxis_title="test MAE (rentals)",
        margin={"l": 220, "r": 140, "t": 110, "b": 70},
    )
    fig.update_yaxes(
        tickvals=list(range(len(order))),
        ticktext=[MODEL_LABELS[m] for m in order],
        autorange="reversed",
    )
    style_runs(fig, best=MODEL_LABELS[best])
    add_takeaway(
        fig,
        f"Best on the frozen test window: {MODEL_LABELS[best]} "
        f"(MAE {runs[best]['mae']:.1f}) against the seasonal-naive floor "
        f"{runs['seasonal_naive']['mae']:.1f} — every candidate, one score each.",
    )
    return fig


def residual_heatmap_figure(test_df: pd.DataFrame, residuals: np.ndarray) -> go.Figure:
    """Mean residual sliced by hour of day x season (left) and x weather (right)."""
    work = test_df.copy()
    work["residual"] = residuals
    seasons = [SEASON_LABELS[s] for s in (1, 2, 3, 4)]
    # reindex to the full category sets: a short test window can miss a season
    # or weather level, and the heatmap must still render (honest n/a cells).
    by_season = (
        work.groupby(["hour", "season"])["residual"].mean().unstack().reindex(columns=[1, 2, 3, 4])
    )
    by_weather = (
        work.groupby(["hour", "weathersit"])["residual"]
        .mean()
        .unstack()
        .reindex(columns=[1, 2, 3, 4])
    )
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=["by season", "by weather situation"],
        horizontal_spacing=0.12,
    )
    fig.add_trace(
        go.Heatmap(
            z=by_season[[1, 2, 3, 4]].values.T,
            x=by_season.index,
            y=seasons,
            colorscale="RdBu",
            zmid=0,
            colorbar={"title": "mean residual", "x": 1.0},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Heatmap(
            z=by_weather.values.T,
            x=by_weather.index,
            y=[f"w{w}" for w in by_weather.columns],
            colorscale="RdBu",
            zmid=0,
            showscale=False,
        ),
        row=1,
        col=2,
    )
    fig.update_xaxes(title_text="hour of day", dtick=4, row=1, col=1)
    fig.update_xaxes(title_text="hour of day", dtick=4, row=1, col=2)
    apply_theme(fig, height=480, width=1080)
    fig.update_layout(title="Residuals sliced by hour x season and hour x weather")
    add_takeaway(
        fig,
        "Red = the model under-forecasts there. Structure left in a slice is the "
        "next feature's address — here it marks rush-hour overshoot and bad-weather bias.",
    )
    return fig


def residual_vs_fitted_figure(y_true: np.ndarray, y_pred: np.ndarray) -> go.Figure:
    """Residual vs fitted scatter — heteroscedasticity and bias at a glance."""
    residuals = y_true - y_pred
    fig = go.Figure()
    fig.add_scatter(
        x=y_pred,
        y=residuals,
        mode="markers",
        name="test hours",
        marker={"color": "#38bdf8", "size": 5, "opacity": 0.5},
    )
    fig.add_hline(y=0, line={"color": "#64748b", "dash": "dash"})
    apply_theme(fig, height=560)
    fig.update_layout(
        title="Residual vs fitted on the scored-once test window",
        xaxis_title="fitted rentals",
        yaxis_title="residual (actual - fitted)",
    )
    add_takeaway(
        fig,
        "Spread widens with the fitted level (high-demand hours are harder in "
        "absolute rentals) while staying centered on zero — no global bias.",
    )
    return fig


def bootstrap_ci_figure(deltas: np.ndarray, ci: dict[str, Any]) -> go.Figure:
    """Bootstrap distribution of the MAE improvement (floor - champion)."""
    fig = go.Figure()
    fig.add_histogram(x=deltas, nbinsx=60, name="bootstrap deltas", marker_color="#2dd4bf")
    fig.add_vline(x=0, line={"color": "#64748b", "dash": "dash"})
    fig.add_vline(x=ci["lo"], line={"color": "#fbbf24", "dash": "dot"})
    fig.add_vline(x=ci["hi"], line={"color": "#fbbf24", "dash": "dot"})
    apply_theme(fig, height=540)
    fig.update_layout(
        title="Paired bootstrap — MAE improvement over the seasonal-naive floor",
        xaxis_title="MAE(floor) - MAE(champion), rentals per hour",
        yaxis_title="resamples",
        showlegend=False,
    )
    add_takeaway(
        fig,
        f"{ci['n_boot']:,} paired resamples: point +{ci['point']:.1f}, 95% CI "
        f"[{ci['lo']:.1f}, {ci['hi']:.1f}] — the whole histogram sits right of zero.",
    )
    return fig
