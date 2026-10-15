"""Plotly figure builders for the routing-optimization showcase.

Every figure is themed via :mod:`portfolio_core.plotting` (``apply_theme``),
states its one-line takeaway (``add_takeaway``) and demotes baselines /
promotes the best run (``style_runs``, with a marker-color fallback for bar
traces, which reject ``line=`` styling). Builders are pure functions of
polars DataFrames / problem models so tests can exercise them without the
pipeline.
"""

import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from portfolio_core.plotting import (
    add_takeaway,
    apply_theme,
    is_baseline_run,
    style_runs,
)

from routing_optimization.schemas import Problem


def gap_figure(rows: pl.DataFrame) -> go.Figure:
    """Grouped bar: gap to best-known (%) per instance, one group per solver."""
    fig = px.bar(
        rows,
        x="instance",
        y="gap_pct",
        color="solver",
        barmode="group",
        title="Distance gap to published best-known solutions (%) — 56 Solomon instances",
        labels={"gap_pct": "gap %", "instance": "instance", "solver": "solver"},
    )
    fig.add_hline(y=0.0, line_color="#94a3b8", line_width=1)
    return apply_theme(fig)


def runtime_figure(rows: pl.DataFrame) -> go.Figure:
    """Grouped bar: solver runtime per instance (seconds, log scale)."""
    fig = px.bar(
        rows,
        x="instance",
        y="runtime_s",
        color="solver",
        barmode="group",
        log_y=True,
        title="Solver runtime per instance (s, log scale)",
        labels={"runtime_s": "runtime (s)", "instance": "instance", "solver": "solver"},
    )
    return apply_theme(fig)


def route_map_figure(problem: Problem, routes: list[list[int]], title: str) -> go.Figure:
    """Depot + customer scatter with route polylines colored per vehicle."""
    customers = problem.customers
    depot = problem.depot
    palette = px.colors.qualitative.Plotly
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[depot.x],
            y=[depot.y],
            mode="markers",
            name="depot",
            marker_symbol="star",
            marker_size=16,
            marker_color="#fbbf24",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[c.x for c in customers[1:]],
            y=[c.y for c in customers[1:]],
            mode="markers",
            name="customers",
            marker_size=5,
            marker_color="#64748b",
        )
    )
    for k, route in enumerate(routes):
        pts = [depot] + [customers[cid] for cid in route] + [depot]
        fig.add_trace(
            go.Scatter(
                x=[c.x for c in pts],
                y=[c.y for c in pts],
                mode="lines+markers",
                name=f"vehicle {k + 1}",
                line_color=palette[k % len(palette)],
                line_width=2,
                marker_size=4,
            )
        )
    fig.update_layout(title=title, showlegend=True)
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return apply_theme(fig, width=900, height=760)


def eda_instance_map_figure(problem: Problem) -> go.Figure:
    """Customer scatter colored by time-window tightness (``due - ready``).

    Narrow windows constrain route timing more than geography alone suggests;
    tight customers (small ``due - ready``) are the ones a solver must visit
    within a narrow time band. The depot is marked with a star.
    """
    customers = problem.customers
    depot = problem.depot
    tightness = [c.due_time - c.ready_time for c in customers[1:]]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[depot.x],
            y=[depot.y],
            mode="markers",
            name="depot",
            marker_symbol="star",
            marker_size=16,
            marker_color="#fbbf24",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[c.x for c in customers[1:]],
            y=[c.y for c in customers[1:]],
            mode="markers",
            name="customers",
            marker_size=7,
            marker_color=tightness,
            marker_colorscale="Plasma",
            marker_showscale=True,
            marker_colorbar={"title": "window width<br>(due - ready)"},
        )
    )
    fig.update_layout(
        title=f"{problem.name} — customer geography colored by time-window tightness",
        showlegend=True,
    )
    fig.update_yaxes(scaleanchor="x", scaleratio=1)
    return apply_theme(fig, width=900, height=760)


def convergence_figure(history: dict[str, list[float]], instance: str) -> go.Figure:
    """Best-found distance vs accepted-move count, tuned vs untuned overlay.

    ``history`` maps a solver label to its trace (index 0 is the construction
    start). The construction start is explicitly marked, and the tuned curve
    is promoted via :func:`portfolio_core.plotting.style_runs`.
    """
    fig = go.Figure()
    for label in ("untuned", "tuned"):
        values = history[label]
        fig.add_trace(
            go.Scatter(
                x=list(range(len(values))),
                y=values,
                mode="lines+markers",
                name="two_opt_tuned" if label == "tuned" else "two_opt",
            )
        )
    tuned = history["tuned"]
    fig.add_trace(
        go.Scatter(
            x=[0],
            y=[tuned[0]],
            mode="markers",
            name="construction start",
            marker_symbol="star",
            marker_size=14,
            marker_color="#fbbf24",
        )
    )
    reduction = (tuned[0] - tuned[-1]) / tuned[0] * 100.0
    style_runs(fig, best="two_opt_tuned")
    add_takeaway(
        fig,
        f"construction {tuned[0]:.1f} -> tuned {tuned[-1]:.1f} "
        f"(-{reduction:.1f}%) in {len(tuned) - 1} accepted moves",
    )
    fig.update_layout(
        title=f"{instance} — 2-opt convergence",
        xaxis_title="accepted moves",
        yaxis_title="total distance",
        showlegend=True,
    )
    return apply_theme(fig)


def _style_runs_safe(fig: go.Figure, best: str) -> go.Figure:
    """Apply the platform run-styling; fall back to marker colors for bar traces.

    ``style_runs`` sets ``line=`` which scatter traces accept but bar traces
    reject, so grouped-bar figures get the equivalent marker-color treatment
    (grey baselines, accent best) via the public ``is_baseline_run`` hint.
    """
    try:
        return style_runs(fig, best=best)
    except ValueError:
        for trace in fig.data:
            name = str(getattr(trace, "name", "") or "")
            if best.lower() in name.lower():
                trace.update(marker={"color": "#2dd4bf"})
            elif is_baseline_run(name):
                trace.update(marker={"color": "#64748b"})
        return fig


def solver_profile_figure(rows: pl.DataFrame) -> go.Figure:
    """Per-instance solver profile: grouped distance bars on a log scale.

    Baselines are visually demoted (grey) and the tuned run promoted, so the
    solver ladder reads instantly.
    """
    fig = px.bar(
        rows,
        x="instance",
        y="distance",
        color="solver",
        barmode="group",
        log_y=True,
        title="Solver profile per instance (total distance, log scale)",
        labels={"distance": "total distance", "instance": "instance", "solver": "solver"},
    )
    _style_runs_safe(fig, best="two_opt_tuned")
    add_takeaway(
        fig,
        "constraint-aware construction (savings) removes most of the randomized floor; "
        "tuned 2-opt closes a further few percent",
    )
    return apply_theme(fig)


def family_gap_figure(rows: pl.DataFrame) -> go.Figure:
    """Two-panel family view: mean distance gap (top) and mean vehicle-count
    delta vs published best-known solutions (bottom), per solver.

    Vehicle count is the Solomon benchmark's primary ranking criterion
    (SINTEF hierarchical objective); showing both panels side by side keeps
    the distance story honest.
    """
    from plotly.subplots import make_subplots

    solvers = sorted(rows["solver"].unique().to_list())
    palette = px.colors.qualitative.Plotly
    colors: dict[str, str] = {}
    ci = 0
    for s in solvers:
        if "alns" in s.lower():
            colors[s] = "#2dd4bf"
        elif is_baseline_run(s):
            colors[s] = "#64748b"
        else:
            colors[s] = palette[ci % len(palette)]
            ci += 1

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.62, 0.38],
        vertical_spacing=0.12,
        subplot_titles=(
            "distance gap to best-known (mean %)",
            "vehicle count delta vs best-known (mean; benchmark ranks vehicles first)",
        ),
    )
    for s in solvers:
        sub = rows.filter(pl.col("solver") == s)
        fig.add_trace(
            go.Bar(
                x=sub["family"].to_list(),
                y=sub["gap_pct"].to_list(),
                name=s,
                marker_color=colors[s],
                legendgroup=s,
            ),
            row=1,
            col=1,
        )
        veh = sub.filter(pl.col("veh_delta").is_not_null())
        fig.add_trace(
            go.Bar(
                x=veh["family"].to_list(),
                y=veh["veh_delta"].to_list(),
                name=s,
                marker_color=colors[s],
                legendgroup=s,
                showlegend=False,
            ),
            row=2,
            col=1,
        )
    fig.update_layout(
        barmode="group",
        title="Per-family comparison vs published best-known solutions (56 instances)",
        xaxis2_title="family",
    )
    add_takeaway(
        fig,
        "ALNS leads on both criteria — single-digit distance gaps and the fewest "
        "vehicles of our ladder; every solver still uses more vehicles than the "
        "hierarchical-optimizing references",
    )
    return apply_theme(fig, height=720)


# ---------------------------------------------------------------------------
# Pipeline stages (used by the CLI and dvc.yaml)
