"""Figures: runtime, memory, speedup and the IO cold/warm task profile.

All figures read the committed ``metrics.json`` shape (task → engines →
numbers), so they rebuild offline from artifacts. House style via
``portfolio_core.plotting`` (theme, takeaway subtitle, save_json + save_html
for the showcase API and the docs).
"""

from typing import Any

import plotly.graph_objects as go
from portfolio_core.plotting import add_takeaway, apply_theme

from data_engineering.metrics import ENGINE_ORDER
from data_engineering.tasks import TASKS

ENGINE_COLORS = {"pandas": "#fbbf24", "polars": "#38bdf8", "duckdb": "#34d399"}
ENGINE_LABELS = {"pandas": "pandas", "polars": "Polars", "duckdb": "DuckDB"}


def _task_names(metrics: dict[str, Any]) -> list[str]:
    return [t.name for t in TASKS if t.name in metrics["tasks"]]


def _engine_block(metrics: dict[str, Any], task: str, engine: str) -> dict[str, Any]:
    block: dict[str, Any] = metrics["tasks"][task]["engines"][engine]
    return block


def build_figures(metrics: dict[str, Any]) -> dict[str, go.Figure]:
    """Build the four committed figures from a metrics dict."""
    return {
        "runtime_by_task": runtime_by_task(metrics),
        "memory_by_task": memory_by_task(metrics),
        "speedup_vs_pandas": speedup_vs_pandas(metrics),
        "io_cold_warm": io_cold_warm(metrics),
    }


def runtime_by_task(metrics: dict[str, Any]) -> go.Figure:
    """Median warm runtime per task x engine (log scale)."""
    tasks = _task_names(metrics)
    fig = go.Figure()
    for engine in ENGINE_ORDER:
        if all(engine not in metrics["tasks"][t]["engines"] for t in tasks):
            continue
        fig.add_bar(
            x=tasks,
            y=[_engine_block(metrics, t, engine)["time_median_s"] for t in tasks],
            name=ENGINE_LABELS[engine],
            marker_color=ENGINE_COLORS[engine],
        )
    fastest = metrics["summary"]["fastest_engine_by_task"]
    counts = {e: list(fastest.values()).count(e) for e in set(fastest.values())}
    tally = ", ".join(f"{ENGINE_LABELS[e]} fastest on {n}" for e, n in sorted(counts.items()))
    apply_theme(fig)
    fig.update_layout(
        title="Task runtime by engine (median, log scale)",
        xaxis_title="task",
        yaxis_title="wall time (s, median of repeats)",
    )
    fig.update_yaxes(type="log")
    add_takeaway(fig, f"{tally}; every repeat's result hash matched within each cell.")
    return fig


def memory_by_task(metrics: dict[str, Any]) -> go.Figure:
    """Peak RSS per task x engine from the fresh-process probes."""
    tasks = _task_names(metrics)
    fig = go.Figure()
    for engine in ENGINE_ORDER:
        if all(engine not in metrics["tasks"][t]["engines"] for t in tasks):
            continue
        fig.add_bar(
            x=tasks,
            y=[(_engine_block(metrics, t, engine).get("peak_rss_mb") or 0.0) for t in tasks],
            name=ENGINE_LABELS[engine],
            marker_color=ENGINE_COLORS[engine],
        )
    apply_theme(fig)
    fig.update_layout(
        title="Peak RSS by task (fresh-process probe)",
        xaxis_title="task",
        yaxis_title="peak RSS (MB)",
    )
    add_takeaway(
        fig,
        "One fresh process per cell: the high-water mark is attributable to that cell alone, "
        "unlike deltas inside one long-lived process.",
    )
    return fig


def speedup_vs_pandas(metrics: dict[str, Any]) -> go.Figure:
    """Wall-time speedup vs pandas per task (pandas = 1 reference)."""
    tasks = _task_names(metrics)
    fig = go.Figure()
    for engine in ENGINE_ORDER:
        if all(engine not in metrics["tasks"][t]["engines"] for t in tasks):
            continue
        fig.add_bar(
            x=tasks,
            y=[_engine_block(metrics, t, engine)["speedup_vs_pandas"] for t in tasks],
            name=ENGINE_LABELS[engine],
            marker_color=ENGINE_COLORS[engine],
        )
    apply_theme(fig)
    fig.update_layout(
        title="Speedup vs pandas (median wall time, log scale)",
        xaxis_title="task",
        yaxis_title="x faster than pandas",
    )
    fig.update_yaxes(type="log")
    geo = metrics["summary"]["by_engine"]
    note = "; ".join(
        f"{ENGINE_LABELS[e]} geomean x{geo[e]['geomean_speedup_vs_pandas']}"
        for e in ENGINE_ORDER
        if e in geo and geo[e]["geomean_speedup_vs_pandas"] is not None
    )
    add_takeaway(fig, f"{note} — pandas sits at x1 by definition.")
    return fig


def io_cold_warm(metrics: dict[str, Any]) -> go.Figure:
    """IO task profile: cold fresh-process read vs warm in-process median."""
    io_tasks = [
        t.name
        for t in TASKS
        if t.name in metrics["tasks"] and metrics["tasks"][t.name]["category"] == "io"
    ]
    fig = go.Figure()
    for engine in ENGINE_ORDER:
        if all(engine not in metrics["tasks"][t]["engines"] for t in io_tasks):
            continue
        warm = [_engine_block(metrics, t, engine)["time_median_s"] for t in io_tasks]
        cold = [_engine_block(metrics, t, engine).get("cold_s") for t in io_tasks]
        fig.add_bar(
            x=io_tasks,
            y=warm,
            name=f"{ENGINE_LABELS[engine]} warm",
            marker_color=ENGINE_COLORS[engine],
        )
        fig.add_bar(
            x=io_tasks,
            y=[c if c is not None else 0.0 for c in cold],
            name=f"{ENGINE_LABELS[engine]} cold",
            marker_color=ENGINE_COLORS[engine],
            opacity=0.45,
        )
    apply_theme(fig)
    fig.update_layout(
        title="IO tasks: cold process read vs warm in-process median (log scale)",
        xaxis_title="task",
        yaxis_title="wall time (s)",
        barmode="group",
    )
    fig.update_yaxes(type="log")
    add_takeaway(
        fig,
        "Cold = one fresh interpreter per cell (library state cold; the OS page cache "
        "is not dropped — not portable). Warm = median of the in-process repeats.",
    )
    return fig
