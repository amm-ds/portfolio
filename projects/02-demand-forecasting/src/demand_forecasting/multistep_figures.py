"""Plotly figure builders for the multi-step track.

Unit-incompatible metrics never share an axis; every figure carries an
add_takeaway caption stating how to read it.
"""

import math
from typing import Any

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from portfolio_core.plotting import add_takeaway, apply_theme

from demand_forecasting.multistep_constants import CHAMPION, FLOOR, NAIVE
from demand_forecasting.multistep_metrics import PEAK_CANDIDATES
from demand_forecasting.probabilistic import CALIBRATION_TOL, TARGET_COVERAGE

# ---------------------------------------------------------------------------
# Figures (unit-incompatible metrics never share an axis)
# ---------------------------------------------------------------------------


def _peak_day_pairs(
    cells: dict[str, Any],
    test: list[int],
    horizons: list[int],
    n_series: int,
    candidate: str,
    max_points: int = 1500,
) -> tuple[np.ndarray, np.ndarray]:
    """(peak-day actual, forecast) pairs for one candidate on its windows'
    top-decile days — the scatter data behind multistep_peak_day_scatter."""
    n_o, n_h = len(test), len(horizons)
    y3 = cells["y"].reshape(n_o, n_h, n_series)
    pred3 = cells["pred"][candidate].reshape(n_o, n_h, n_series)
    k = max(1, math.ceil(0.1 * n_h))
    top_k = np.argsort(y3, axis=1)[:, ::-1][:, :k, :]
    arange_o = np.arange(n_o)[:, None, None]
    arange_s = np.arange(n_series)[None, None, :]
    actual = y3[arange_o, top_k, arange_s].reshape(-1)
    pred = pred3[arange_o, top_k, arange_s].reshape(-1)
    if actual.size > max_points:  # deterministic subsample for the JSON size
        step = int(np.ceil(actual.size / max_points))
        actual, pred = actual[::step], pred[::step]
    return actual, pred


def _figures(
    block: dict[str, Any],
    horizons: list[int],
    prob_block: dict[str, Any],
    cells: dict[str, Any],
    test: list[int],
    n_series: int,
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

    peak_fig = _figure_peak_capture(block)
    candidate_fig = _figure_candidate_comparison(block)
    scatter_fig = _figure_peak_day_scatter(cells, test, horizons, n_series)
    win_fig = _figure_win_rates(block)

    return {
        "multistep_error_vs_horizon": error_fig,
        "multistep_class_scoreboard": scoreboard_fig,
        "multistep_routing": routing_fig,
        "multistep_band_calibration": band_fig,
        "multistep_peak_capture": peak_fig,
        "multistep_candidate_comparison": candidate_fig,
        "multistep_peak_day_scatter": scatter_fig,
        "multistep_win_rates": win_fig,
    }


def _figure_win_rates(block: dict[str, Any]) -> go.Figure:
    """Per-series beats-floor win rates (wave 21 — the "EVERY time series"
    metric): share of series in each class beating the seasonal-naive floor
    per candidate at h=7 and h=14, with the cluster-bootstrap CI whiskers."""
    wr = block["win_rates"]["per_class"]
    classes_sorted = sorted(wr)
    fig = make_subplots(
        rows=len(classes_sorted),
        cols=2,
        subplot_titles=("win rate vs floor at h=7 (share of series)", "at h=14"),
        row_titles=classes_sorted,
    )
    for row, cls in enumerate(classes_sorted, start=1):
        for col, h in enumerate((7, 14), start=1):
            key = str(h)
            if key not in wr[cls]["per_horizon"]:
                continue
            entry = wr[cls]["per_horizon"][key]
            for cand in block["win_rates"]["candidates"]:
                item = entry[cand]
                color = "#2dd4bf" if cand == "routed" else "#64748b"
                fig.add_bar(
                    x=[f"{cls}<br>{cand}"],
                    y=[item["win_rate"]],
                    name=cand,
                    marker_color=color,
                    legendgroup=cand,
                    showlegend=row == 1 and col == 1,
                    row=row,
                    col=col,
                )
                fig.add_scatter(
                    x=[f"{cls}<br>{cand}"],
                    y=[item["win_rate"]],
                    name="95% CI",
                    mode="markers",
                    marker={"color": "#fbbf24", "size": 4},
                    error_y={
                        "type": "data",
                        "array": [item["ci95"][1] - item["win_rate"]],
                        "arrayminus": [item["win_rate"] - item["ci95"][0]],
                    },
                    showlegend=False,
                    row=row,
                    col=col,
                )
    fig.update_layout(
        title="Per-series beats-floor win rate per class (95% cluster-bootstrap CI)",
        barmode="group",
    )
    add_takeaway(
        fig,
        "the 'improve EVERY series' metric: pooled MAE can fall while most series lose — "
        "this panel counts, per class, how many series actually beat the seasonal-naive "
        "floor per candidate and horizon",
    )
    return apply_theme(fig)


def _figure_peak_capture(block: dict[str, Any]) -> go.Figure:
    """Peak capture per class: peak_recall and peak_mae differences vs the
    zero forecast with paired-bootstrap CIs (positive recall diff / negative
    MAE diff = better than zero)."""
    peak = block["peak_capture"]["per_class"]
    classes_sorted = sorted(peak)
    fig = make_subplots(
        rows=len(classes_sorted),
        cols=2,
        subplot_titles=(
            "peak_recall minus zero (share of top-5 peak days ranked top-5)",
            "peak_mae minus zero (units, on top-decile demand days)",
        ),
        row_titles=classes_sorted,
    )
    for row, cls in enumerate(classes_sorted, start=1):
        for col, metric in enumerate(("peak_recall", "peak_mae"), start=1):
            for cand in PEAK_CANDIDATES:
                item = peak[cls][cand]
                comp = item.get(f"{metric}_vs_zero")
                if comp is None:
                    continue
                color = "#2dd4bf" if cand == "routed" else "#64748b"
                fig.add_bar(
                    x=[f"{cls}<br>{cand}"],
                    y=[comp["diff"]],
                    name=cand,
                    marker_color=color,
                    legendgroup=cand,
                    showlegend=row == 1 and col == 1,
                    row=row,
                    col=col,
                )
                fig.add_scatter(
                    x=[f"{cls}<br>{cand}"],
                    y=[comp["diff"]],
                    name="95% CI",
                    mode="markers",
                    marker={"color": "#fbbf24", "size": 4},
                    error_y={
                        "type": "data",
                        "array": [comp["ci95"][1] - comp["diff"]],
                        "arrayminus": [comp["diff"] - comp["ci95"][0]],
                    },
                    showlegend=False,
                    row=row,
                    col=col,
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
        title="Peak capture per class — difference vs the zero forecast (95% paired bootstrap CI)",
        barmode="group",
    )
    add_takeaway(
        fig,
        "the user's headline question: do the peak-capable candidates rank the window's "
        "peak days better than the flat zero baseline? recall diff > 0 and MAE diff < 0 "
        "is a win; routed is the committed per-series router",
    )
    return apply_theme(fig)


def _figure_candidate_comparison(block: dict[str, Any]) -> go.Figure:
    """Pooled-over-h MAE per class for every ML/ensemble candidate with the
    gap CI vs the routed pipeline."""
    comp_block = block["candidate_comparison"]["per_class"]
    comp_cands = tuple(block["candidate_comparison"]["candidates"])
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("pooled MAE, all horizons (units)", "candidate minus routed MAE (95% CI)"),
    )
    for cls in sorted(comp_block):
        entry = comp_block[cls]
        x_pos = f"{cls}"
        for name, color in (("routed", "#2dd4bf"), ("zero", "#94a3b8")):
            key = "routed_mae" if name == "routed" else "zero_mae"
            fig.add_bar(
                x=[x_pos],
                y=[entry[key]],
                name=name,
                marker_color=color,
                legendgroup=name,
                showlegend=False,
                row=1,
                col=1,
            )
        for cand in comp_cands:
            fig.add_bar(
                x=[x_pos],
                y=[entry[cand]["mae"]],
                name=cand,
                marker_color="#64748b",
                legendgroup=cand,
                showlegend=False,
                row=1,
                col=1,
            )
            gap = entry[cand]["vs_routed"]
            fig.add_scatter(
                x=[f"{cls}<br>{cand}"],
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
        title="ML + ensemble candidates vs the routed pipeline — pooled multi-step MAE",
        barmode="group",
    )
    add_takeaway(
        fig,
        "right panel: candidate MAE minus routed MAE with 95% paired bootstrap CIs — "
        "negative means the candidate beats the committed router on pooled MAE",
    )
    return apply_theme(fig)


def _figure_peak_day_scatter(
    cells: dict[str, Any], test: list[int], horizons: list[int], n_series: int
) -> go.Figure:
    """Forecast vs actual on each scored window's top-decile day (lumpy class
    — 98.6% of the panel), one panel per candidate (linear axes: the zero
    candidate's y=0 row is the point of the figure)."""
    lumpy_mask = cells["class"] == "lumpy"
    has_lumpy = bool(lumpy_mask.any())
    n_cand = len(PEAK_CANDIDATES)
    n_cols = 3
    n_rows = math.ceil(n_cand / n_cols)
    fig = make_subplots(
        rows=n_rows,
        cols=n_cols,
        subplot_titles=tuple(f"{c} (lumpy peak days)" for c in PEAK_CANDIDATES),
    )
    if has_lumpy:
        for pos, cand in enumerate(PEAK_CANDIDATES, start=1):
            row, col = (pos - 1) // n_cols + 1, (pos - 1) % n_cols + 1
            actual, pred = _peak_day_pairs(cells, test, horizons, n_series, cand)
            fig.add_scatter(
                x=actual,
                y=pred,
                name=cand,
                mode="markers",
                marker={"size": 4, "opacity": 0.5},
                showlegend=False,
                row=row,
                col=col,
            )
            hi = float(max(actual.max(), pred.max())) if actual.size else 1.0
            xref = "x domain" if pos == 1 else f"x{pos} domain"
            yref = "y" if pos == 1 else f"y{pos}"
            fig.add_shape(
                type="line",
                xref=xref,
                x0=0,
                x1=1,
                yref=yref,
                y0=0.0,
                y1=hi,
                line={"dash": "dot", "color": "#fbbf24"},
                row=row,
                col=col,
            )
    fig.update_xaxes(title="peak-day actual (units)")
    fig.update_yaxes(title="forecast (units)")
    fig.update_layout(title="Peak-day scatter — each scored window's top-decile demand day (lumpy)")
    add_takeaway(
        fig,
        "points on the dotted parity line nail the peak; a flat candidate (zero) hugs the "
        "bottom — this is the structural miss the peak-capable candidates were built for",
    )
    return apply_theme(fig)
