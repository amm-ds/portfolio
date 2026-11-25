"""Figures: the five committed chart types, all regenerable from metrics.json.

Every figure reads the committed ``metrics.json`` shape (task → engines →
numbers, plus the ``scalability`` block), so they rebuild offline from
artifacts. House style via ``portfolio_core.plotting`` (theme, takeaway
subtitle, save_json + save_html for the showcase API and the docs).

Chart diversity is deliberate — the first cut was all bar charts:

- ``task_times_dotplot`` — horizontal dot plot with min/max whiskers;
- ``speedup_overview`` — dot chart vs the pandas baseline, and vs sqlite for
  the SQL tasks;
- ``scalability_lines`` — growth-slope summary plus one detailed task panel;
- ``memory_lollipop`` — lollipop chart of fresh-process peak RSS;
- ``normalized_heatmap`` — per-task time normalized to the task minimum.
"""

import math
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from portfolio_core.plotting import add_takeaway, apply_theme

from data_engineering.metrics import ENGINE_ORDER
from data_engineering.tasks import TASKS

ENGINE_COLORS = {
    "pandas": "#fbbf24",
    "polars": "#38bdf8",
    "duckdb": "#34d399",
    "sqlite": "#a78bfa",
}
ENGINE_LABELS = {"pandas": "pandas", "polars": "Polars", "duckdb": "DuckDB", "sqlite": "sqlite"}
#: Horizontal dodge per engine when several share one task position.
_ENGINE_OFFSET = {"pandas": -0.27, "polars": -0.09, "duckdb": 0.09, "sqlite": 0.27}


def _task_names(metrics: dict[str, Any]) -> list[str]:
    return [t.name for t in TASKS if t.name in metrics["tasks"]]


def _block(metrics: dict[str, Any], task: str, engine: str) -> dict[str, Any]:
    block: dict[str, Any] = metrics["tasks"][task]["engines"][engine]
    return block


def build_figures(metrics: dict[str, Any]) -> dict[str, go.Figure]:
    """Build the committed figures from a metrics dict.

    ``scalability_lines`` needs the ``scalability`` block, so runs without it
    (the CI synthetic track) emit the four main-track figures only; the
    committed real-track metrics always carry the block and all five.
    """
    figures = {
        "task_times_dotplot": task_times_dotplot(metrics),
        "speedup_overview": speedup_overview(metrics),
        "memory_lollipop": memory_lollipop(metrics),
        "normalized_heatmap": normalized_heatmap(metrics),
    }
    if metrics.get("scalability"):
        figures["scalability_lines"] = scalability_lines(metrics)
    return figures


def _task_axis(fig: go.Figure, tasks: list[str]) -> None:
    fig.update_yaxes(
        tickvals=list(range(len(tasks))),
        ticktext=tasks,
        autorange="reversed",  # first task on top, reading order
    )


def task_times_dotplot(metrics: dict[str, Any]) -> go.Figure:
    """Median warm runtime per task x engine — dot + min/max whisker, log scale."""
    tasks = _task_names(metrics)
    fig = go.Figure()
    for engine in ENGINE_ORDER:
        if all(engine not in metrics["tasks"][t]["engines"] for t in tasks):
            continue
        positions, medians, highs, lows = [], [], [], []
        for i, task in enumerate(tasks):
            if engine not in metrics["tasks"][task]["engines"]:
                continue  # honest n/a cell (write_parquet/sqlite)
            times = _block(metrics, task, engine)["time_all_s"]
            median = _block(metrics, task, engine)["time_median_s"]
            positions.append(i + _ENGINE_OFFSET[engine])
            medians.append(median)
            highs.append(max(times) - median)
            lows.append(median - min(times))
        fig.add_scatter(
            x=medians,
            y=positions,
            mode="markers",
            name=ENGINE_LABELS[engine],
            marker={"color": ENGINE_COLORS[engine], "size": 10},
            error_x={
                "type": "data",
                "symmetric": False,
                "array": highs,
                "arrayminus": lows,
                "color": ENGINE_COLORS[engine],
                "thickness": 1.4,
                "width": 5,
            },
        )
    fastest = metrics["summary"]["fastest_engine_by_task"]
    counts: dict[str, int] = {}
    for engine in fastest.values():
        counts[engine] = counts.get(engine, 0) + 1
    tally = ", ".join(f"{ENGINE_LABELS[e]} fastest on {n}" for e, n in sorted(counts.items()))
    apply_theme(fig)
    fig.update_layout(
        title="Task time by engine — median dot, whiskers = min/max repeats (log scale)",
        xaxis_title="wall time (s, median of repeats)",
        yaxis_title="task",
        height=640,
        margin={"l": 150, "r": 140, "t": 110, "b": 70},
    )
    fig.update_xaxes(type="log")
    _task_axis(fig, tasks)
    add_takeaway(fig, f"{tally}; write_parquet is n/a for sqlite (no stdlib parquet writer).")
    return fig


def speedup_overview(metrics: dict[str, Any]) -> go.Figure:
    """Speedup dot chart: vs pandas (all tasks), and vs sqlite (SQL tasks)."""
    tasks = _task_names(metrics)
    sql_tasks = [t for t in tasks if "sqlite" in metrics["tasks"][t]["engines"]]
    fig = make_subplots(
        rows=1,
        cols=2,
        shared_yaxes=True,
        column_titles=["vs pandas", "vs sqlite (SQL tasks)"],
        horizontal_spacing=0.06,
    )
    for col, (baseline, panel_tasks) in enumerate(
        [("pandas", tasks), ("sqlite", sql_tasks)], start=1
    ):
        for engine in ENGINE_ORDER:
            if engine == baseline or all(
                engine not in metrics["tasks"][t]["engines"] for t in panel_tasks
            ):
                continue
            xs, ys = [], []
            for pos, t in enumerate(panel_tasks):
                if engine not in metrics["tasks"][t]["engines"]:
                    continue  # honest n/a cell (write_parquet/sqlite)
                xs.append(_block(metrics, t, engine)[f"speedup_vs_{baseline}"])
                ys.append(pos + _ENGINE_OFFSET[engine])
            fig.add_scatter(
                x=xs,
                y=ys,
                mode="markers",
                name=ENGINE_LABELS[engine],
                legendgroup=engine,
                showlegend=col == 1,
                marker={"color": ENGINE_COLORS[engine], "size": 10},
                row=1,
                col=col,
            )
        fig.add_vline(x=1, line={"color": "#64748b", "dash": "dash"}, row=1, col=col)
    apply_theme(fig)
    fig.update_layout(
        title="Speedup vs the classical baselines (median wall time, log scale)",
        xaxis_title="x faster than baseline",
        height=640,
        margin={"l": 150, "r": 140, "t": 110, "b": 70},
    )
    fig.update_xaxes(type="log")
    _task_axis(fig, tasks)
    geo = metrics["summary"]["by_engine"]
    note = "; ".join(
        f"{ENGINE_LABELS[e]} geomean x{geo[e]['geomean_speedup_vs_pandas']}"
        for e in ENGINE_ORDER
        if e in geo and geo[e]["geomean_speedup_vs_pandas"] is not None
    )
    add_takeaway(fig, f"{note} — the reference engine sits at x1 by definition.")
    return fig


def scalability_lines(metrics: dict[str, Any]) -> go.Figure:
    """Compact growth-slope summary plus detailed group-by scaling curves."""
    scale = metrics.get("scalability")
    if not scale:
        raise ValueError("metrics.json carries no scalability block — run evaluate --scalability")
    tasks = [t for t in scale["tasks"] if t in metrics["tasks"]]
    sizes = [int(n) for n in scale["sizes"]]
    detail_task = "groupby" if "groupby" in scale["tasks"] else tasks[0]
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("growth exponent by task", f"{detail_task} detail"),
        horizontal_spacing=0.11,
        column_widths=[0.45, 0.55],
    )
    for engine in ENGINE_ORDER:
        slope_x: list[float] = []
        slope_y: list[str] = []
        for task in tasks:
            block = scale["tasks"][task]["engines"].get(engine)
            if block is not None:
                slope_x.append(block["loglog_slope"])
                slope_y.append(task)
        if slope_x:
            fig.add_scatter(
                x=slope_x,
                y=slope_y,
                mode="markers",
                name=ENGINE_LABELS[engine],
                legendgroup=engine,
                marker={"color": ENGINE_COLORS[engine], "size": 10},
                row=1,
                col=1,
            )
        detail = scale["tasks"][detail_task]["engines"].get(engine)
        if detail is not None:
            fig.add_scatter(
                x=sizes,
                y=[detail["by_size"][str(n)]["time_median_s"] for n in sizes],
                mode="lines+markers",
                name=ENGINE_LABELS[engine],
                legendgroup=engine,
                showlegend=False,
                line={"color": ENGINE_COLORS[engine], "width": 2},
                marker={"color": ENGINE_COLORS[engine], "size": 8},
                row=1,
                col=2,
            )
    fig.add_vline(x=1, line={"color": "#64748b", "dash": "dash"}, row=1, col=1)
    apply_theme(fig, height=540)
    fig.update_layout(
        title="Scalability — growth slopes and representative group-by detail",
        margin={"l": 100, "r": 120, "t": 105, "b": 70},
    )
    fig.update_xaxes(title_text="log-log slope (1 = linear)", range=[0.0, 1.25], row=1, col=1)
    fig.update_yaxes(title_text="task", autorange="reversed", row=1, col=1)
    fig.update_xaxes(
        type="log",
        title_text="rows",
        tickvals=sizes,
        ticktext=[f"{n // 1_000_000}M" if n >= 1_000_000 else str(n) for n in sizes],
        row=1,
        col=2,
    )
    fig.update_yaxes(type="log", title_text="median wall time (s)", row=1, col=2)
    slopes = scale["tasks"][detail_task]["engines"]
    note = "; ".join(
        f"{ENGINE_LABELS[e]} slope {slopes[e]['loglog_slope']:.2f}"
        for e in ENGINE_ORDER
        if e in slopes
    )
    add_takeaway(
        fig,
        f"left: growth slopes across 5 tasks; right: {detail_task} ({note})",
    )
    return fig


def memory_lollipop(metrics: dict[str, Any]) -> go.Figure:
    """Fresh-process peak RSS per task x engine — lollipop chart."""
    tasks = _task_names(metrics)
    fig = go.Figure()
    for engine in ENGINE_ORDER:
        if all(engine not in metrics["tasks"][t]["engines"] for t in tasks):
            continue
        xs, ys, stems_x, stems_y = [], [], [], []
        for i, task in enumerate(tasks):
            block = metrics["tasks"][task]["engines"].get(engine)
            if block is None:
                continue  # honest n/a cell (write_parquet/sqlite)
            rss = block.get("peak_rss_mb")
            if rss is None:
                continue
            x = i + _ENGINE_OFFSET[engine]
            xs.append(x)
            ys.append(rss)
            stems_x.extend([x, x, None])
            stems_y.extend([0.0, rss, None])
        fig.add_scatter(
            x=stems_x,
            y=stems_y,
            mode="lines",
            name=f"{ENGINE_LABELS[engine]} stem",
            legendgroup=engine,
            showlegend=False,
            line={"color": ENGINE_COLORS[engine], "width": 1.6},
            hoverinfo="skip",
        )
        fig.add_scatter(
            x=xs,
            y=ys,
            mode="markers",
            name=ENGINE_LABELS[engine],
            legendgroup=engine,
            marker={"color": ENGINE_COLORS[engine], "size": 11},
        )
    apply_theme(fig)
    fig.update_layout(
        title="Peak RSS by task — fresh-process probe (lollipop)",
        yaxis_title="peak RSS (MB)",
        height=600,
    )
    fig.update_xaxes(
        tickvals=list(range(len(tasks))),
        ticktext=tasks,
    )
    add_takeaway(
        fig,
        "One fresh process per cell: the high-water mark is attributable to that cell "
        "alone, unlike deltas inside one long-lived process.",
    )
    return fig


def normalized_heatmap(metrics: dict[str, Any]) -> go.Figure:
    """Per-task median time normalized to the task minimum (log color scale)."""
    tasks = _task_names(metrics)
    engines = [e for e in ENGINE_ORDER if any(e in metrics["tasks"][t]["engines"] for t in tasks)]
    z: list[list[float | None]] = []
    text: list[list[str]] = []
    slowest_counts: dict[str, int] = {}
    for task in tasks:
        row: list[float | None] = []
        row_text: list[str] = []
        present = metrics["tasks"][task]["engines"]
        fastest = min(present[e]["time_median_s"] for e in present)
        slowest = max(present, key=lambda e: present[e]["time_median_s"])
        slowest_counts[slowest] = slowest_counts.get(slowest, 0) + 1
        for engine in engines:
            block = present.get(engine)
            if block is None:
                row.append(None)
                row_text.append("n/a")
            else:
                ratio = block["time_median_s"] / fastest
                row.append(math.log10(ratio))
                row_text.append(f"x{ratio:.1f}")
        z.append(row)
        text.append(row_text)
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[ENGINE_LABELS[e] for e in engines],
            y=tasks,
            text=text,
            texttemplate="%{text}",
            colorscale=[
                [0.0, "#132238"],
                [0.25, "#155e75"],
                [0.5, "#0d9488"],
                [0.75, "#2dd4bf"],
                [1.0, "#a7f3d0"],
            ],
            zmin=0,
            colorbar={"title": "log10(x slower than task best)"},
        )
    )
    apply_theme(fig)
    fig.update_layout(
        title="Normalized task time — each task scaled to its fastest engine",
        height=640,
        margin={"l": 150, "r": 140, "t": 110, "b": 70},
    )
    fig.update_yaxes(autorange="reversed")
    slow_note = ", ".join(
        f"{ENGINE_LABELS[e]} slowest in {n}" for e, n in sorted(slowest_counts.items())
    )
    add_takeaway(fig, f"Dark = task best; {slow_note}.")
    return fig
