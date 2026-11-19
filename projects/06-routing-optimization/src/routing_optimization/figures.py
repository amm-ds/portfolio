"""Plotly figure builders for the routing-optimization showcase.

Every figure is themed via :mod:`portfolio_core.plotting` (``apply_theme``),
states its one-line takeaway (``add_takeaway``) and demotes baselines /
promotes the best run (``style_runs``, with a marker-color fallback for bar
traces, which reject ``line=`` styling). Builders are pure functions of
polars DataFrames / problem models so tests can exercise them without the
pipeline.
"""

import math
from typing import Any, TypedDict

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
    """Distribution of distance gap to best-known (%) for each solver."""
    alns = rows.filter(pl.col("solver") == "alns")
    n_under = alns.filter(pl.col("gap_pct") < 0).height
    n_inst = rows["instance"].n_unique()
    fig = px.box(
        rows,
        x="solver",
        y="gap_pct",
        color="solver",
        points="outliers",
        hover_data=["instance"],
        title="Distance-gap distribution by solver",
        labels={"gap_pct": "gap to best-known (%)", "solver": "solver"},
    )
    fig.add_hline(y=0.0, line_color="#94a3b8", line_width=1)
    fig.update_layout(showlegend=False)
    add_takeaway(
        fig,
        f"{n_inst} Solomon instances per solver; boxes show median and IQR, points show "
        f"outliers; {n_under} ALNS results undercut best-known references",
    )
    return apply_theme(fig)


def runtime_figure(rows: pl.DataFrame) -> go.Figure:
    """Distribution of solver runtime per instance (seconds, log scale)."""
    fig = px.box(
        rows,
        x="solver",
        y="runtime_s",
        color="solver",
        points="outliers",
        hover_data=["instance"],
        log_y=True,
        title="Solver-runtime distribution (s, log scale)",
        labels={"runtime_s": "runtime (s)", "solver": "solver"},
    )
    fig.update_layout(showlegend=False)
    add_takeaway(fig, "one distribution per solver; boxes show median and IQR across instances")
    return apply_theme(fig)


def route_map_figure(
    problem: Problem, routes: list[list[int]], title: str, takeaway: str | None = None
) -> go.Figure:
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
    fig.update_layout(
        title=title,
        showlegend=True,
    )
    if takeaway is not None:
        add_takeaway(fig, takeaway)
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
        title="C101 customers colored by time-window width",
        showlegend=True,
    )
    add_takeaway(
        fig,
        f"{problem.name}: 100 customers + depot (star); color = window width (due - ready)",
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
    """Apply run styling, with marker colors for traces that reject lines.

    ``style_runs`` sets ``line=`` which scatter traces accept but bars and boxes
    reject, so those figures get equivalent marker-color treatment (grey
    baselines, accent best) via the public ``is_baseline_run`` hint.
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
    """Route-distance distribution per solver on a log scale.

    Baselines are visually demoted (grey) and ALNS promoted. Boxes summarize
    the 56 instances without drawing an unreadable bar for every run.
    """
    fig = px.box(
        rows,
        x="solver",
        y="distance",
        color="solver",
        points="outliers",
        hover_data=["instance"],
        log_y=True,
        title="Route-distance distribution by solver",
        labels={"distance": "total distance (log scale)", "solver": "solver"},
    )
    _style_runs_safe(fig, best="alns")
    fig.update_layout(showlegend=False)
    add_takeaway(
        fig,
        "56 Solomon instances per solver; boxes show median and IQR, points show outliers; "
        "grey = baselines, accent = ALNS",
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
        title="Distance gap and vehicle delta by Solomon family",
        xaxis2_title="family",
    )
    add_takeaway(
        fig,
        "mean gap % (top) and mean vehicle delta (bottom) vs best-known over all 56 instances",
    )
    return apply_theme(fig, height=720)


def pareto_figure(rows: pl.DataFrame) -> go.Figure:
    """Runtime-vs-gap Pareto across ALL solvers (means over instances).

    One marker per solver: x = mean runtime (s, log), y = mean distance gap
    to best-known (%); lower-left is better. The external CP-SAT reference is
    marked distinct from the hand-written ladder, and the vehicle-count delta
    is annotated so the two benchmark criteria stay visible on one chart.
    """
    fig = px.scatter(
        rows,
        x="mean_runtime_s",
        y="mean_gap_pct",
        color="solver",
        log_x=True,
        title="Mean runtime vs mean distance gap by solver",
        labels={
            "mean_runtime_s": "mean runtime (s, log)",
            "mean_gap_pct": "mean gap to best-known (%)",
            "solver": "solver",
        },
    )
    for trace in fig.data:
        trace.update(marker_size=12)
    # Vehicle-delta labels, placed in DATA space so they cannot collide: the
    # fast heuristics share the leftmost log-decades and the ALNS arms sit on
    # nearly identical points, so a pixel yshift stacked them. Process bottom-up
    # (ascending gap) and force each label at least one clear step above every
    # already-placed label in its x-window. The legend carries solver names.
    placed: list[tuple[float, float]] = []
    gaps = [float(g) for g in rows["mean_gap_pct"]]
    y_step = max((max(gaps) - min(gaps)) * 0.07, 1.0)
    for row in rows.sort("mean_gap_pct").iter_rows(named=True):
        delta = row["mean_veh_delta"]
        delta_txt = f"{delta:+.2f}" if delta is not None else "n/a"
        # On a log axis plotly interprets annotation x as log10(position)
        # — pass log10(runtime) so the label lands on its marker.
        lx = math.log10(row["mean_runtime_s"])
        y = row["mean_gap_pct"]
        eff = y
        for prev_x, prev_eff in placed:
            if abs(lx - prev_x) < 0.5:
                eff = max(eff, prev_eff + y_step)
        placed.append((lx, eff))
        fig.add_annotation(
            x=lx,
            y=eff,
            text=f"veh Δ {delta_txt}",
            showarrow=False,
            yshift=10,
            font_size=11,
        )
    style_runs(fig, best="alns")
    add_takeaway(
        fig,
        "means over 56 instances; annotation = mean vehicle delta vs best-known; lower-left better",
    )
    return apply_theme(fig, height=640)


class AlnsConvergenceHistory(TypedDict, total=False):
    """Checkpoint-sampled ALNS trace + per-segment destroy-operator weights."""

    iterations: list[float]
    best: list[float]
    segments: list[float]
    destroy_weights: list[list[float]]


def alns_convergence_figure(history: AlnsConvergenceHistory, instance: str) -> go.Figure:
    """Two-panel ALNS convergence on one instance.

    Top frame: best-found distance vs iteration at the recorded checkpoints.
    Bottom frame: destroy-operator weights per adapted segment (random /
    worst / Shaw) — why the search moved where it did.
    """
    from plotly.subplots import make_subplots

    iterations = history["iterations"]
    best = history["best"]
    segments = history.get("segments", [])
    weights = history.get("destroy_weights", [])

    fig = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.6, 0.4],
        vertical_spacing=0.14,
        subplot_titles=(
            "best distance vs ALNS iteration (checkpoints)",
            "destroy-operator weights per segment (random / worst / Shaw)",
        ),
    )
    fig.add_trace(
        go.Scatter(
            x=iterations,
            y=best,
            mode="lines+markers",
            name="alns best distance",
            marker_color="#2dd4bf",
        ),
        row=1,
        col=1,
    )
    reduction = (best[0] - best[-1]) / best[0] * 100.0 if best[0] else 0.0
    labels = ["random", "worst", "shaw"]
    palette = px.colors.qualitative.Plotly
    for k in range(3):
        fig.add_trace(
            go.Scatter(
                x=segments,
                y=[w[k] for w in weights],
                mode="lines+markers",
                name=f"destroy: {labels[k]}",
                marker_color=palette[k % len(palette)],
                showlegend=bool(weights),
            ),
            row=2,
            col=1,
        )
    fig.update_layout(
        title=f"Destroy+repair convergence on {instance}",
        xaxis2_title="segment",
        yaxis_title="total distance",
        yaxis2_title="operator weight",
    )
    add_takeaway(
        fig,
        f"best {best[0]:.1f} -> {best[-1]:.1f} (-{reduction:.1f}%) over "
        f"{iterations[-1]} iterations; weights re-balanced every segment",
    )
    return apply_theme(fig, height=720)


def frontier_figure(block: dict[str, Any]) -> go.Figure:
    """Gap-vs-time anytime frontier: ALNS vs hinted CP-SAT at fixed buckets.

    Median gap% across instances with the mean as a faint second series —
    the shape of the trade (who answers first, who finishes lower) is the
    point, not any single bucket.
    """
    buckets = block["buckets_s"]
    fig = go.Figure()
    for key, label, color in (
        ("alns", "ALNS (hand-written)", "#2dd4bf"),
        ("cp_sat", "CP-SAT (hinted)", "#fbbf24"),
    ):
        series = block[key]
        fig.add_scatter(
            x=buckets,
            y=series["median"],
            mode="lines+markers",
            name=f"{label} — median",
            line={"color": color, "width": 2.5},
        )
        fig.add_scatter(
            x=buckets,
            y=series["mean"],
            mode="lines",
            name=f"{label} — mean",
            line={"color": color, "width": 1, "dash": "dot"},
            showlegend=False,
        )
    fig.update_layout(
        title="Anytime frontier: gap to best-known vs wall-clock",
        xaxis_title="wall-clock budget (s, log scale)",
        yaxis_title="gap to best-known (%)",
        xaxis_type="log",
    )
    alns_median = block["alns"]["median"]
    final_median = next((g for g in reversed(alns_median) if g == g), float("nan"))
    cp_median = block["cp_sat"]["median"]
    cp_final = next((g for g in reversed(cp_median) if g == g), float("nan"))
    add_takeaway(
        fig,
        f"{block['n_instances']} instances, same {block['time_cap_s']:.0f}s cap per solver, "
        "median across instances — at the cap: "
        f"ALNS {final_median:.2f}% vs CP-SAT {cp_final:.2f}%. "
        "A performance artifact (machine-tagged), not a determinism claim; "
        "the headline numbers use iteration budgets.",
    )
    return apply_theme(fig)


# ---------------------------------------------------------------------------
# Pipeline stages (used by the CLI and dvc.yaml)
