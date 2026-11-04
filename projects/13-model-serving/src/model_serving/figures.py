"""Committed figures for the serving study — the house plotly theme.

Four chart types, deliberately diverse (11's first cut was all bars):

- ``latency_concurrency_lines`` — p50/p95/p99 vs concurrency per backend,
  min/max band across repeats on the p95 (the SLO line);
- ``batch_throughput_curve`` — throughput rows/s and per-request p50 latency
  vs batch size, two panels;
- ``backend_comparison_slope`` — paired native→ONNX p50 slope graph per
  concurrency cell, annotated with the ratio;
- ``footprint_cost_bars`` — fresh-process RSS, image size breakdown, and the
  electricity cost per 1k predictions, three panels.
"""

from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from portfolio_core.plotting import add_takeaway, apply_theme

BACKEND_COLORS = {"native": "#38bdf8", "onnx": "#2dd4bf"}
BACKEND_LABELS = {"native": "native (torch)", "onnx": "ONNX Runtime"}
#: Repeat-min/max band fills, keyed by backend (matching line colors at 12%).
_BAND_RGBA = {"native": "rgba(56, 189, 248, 0.12)", "onnx": "rgba(45, 212, 191, 0.12)"}


def _backend_cells(metrics: dict[str, Any], backend: str, block: str) -> dict[str, Any]:
    cells: dict[str, Any] = metrics["serving"][backend][block]
    return cells


def latency_concurrency_lines(metrics: dict[str, Any]) -> go.Figure:
    """Median p50/p95/p99 latency vs concurrency; band = repeat min/max."""
    levels = [int(c[1:]) for c in metrics["serving"]["native"]["concurrency"]]
    fig = go.Figure()
    dash = {"p50_s": "solid", "p95_s": "dash", "p99_s": "dot"}
    for backend in ("native", "onnx"):
        cells = _backend_cells(metrics, backend, "concurrency")
        for metric in ("p50_s", "p95_s", "p99_s"):
            ys = [cells[f"c{c}"][metric] for c in levels]
            fig.add_scatter(
                x=levels,
                y=ys,
                mode="lines+markers",
                name=f"{BACKEND_LABELS[backend]} {metric[:3]}",
                line={"color": BACKEND_COLORS[backend], "dash": dash[metric], "width": 2},
                marker={"color": BACKEND_COLORS[backend], "size": 8},
            )
        lo = [cells[f"c{c}"]["p95_s_min"] for c in levels]
        hi = [cells[f"c{c}"]["p95_s_max"] for c in levels]
        fig.add_scatter(
            x=levels,
            y=hi,
            mode="lines",
            name="p95 repeat max",
            line={"color": BACKEND_COLORS[backend], "width": 0},
            showlegend=False,
        )
        fig.add_scatter(
            x=levels,
            y=lo,
            mode="lines",
            name="p95 repeat min",
            line={"color": BACKEND_COLORS[backend], "width": 0},
            fill="tonexty",
            fillcolor=_BAND_RGBA[backend],
            showlegend=False,
        )
    apply_theme(fig, height=620)
    fig.update_layout(
        title="Per-request latency vs concurrency — median of repeats, band = repeat min/max",
        xaxis_title="concurrency (clients)",
        yaxis_title="latency (s)",
        margin={"l": 90, "r": 140, "t": 110, "b": 70},
    )
    fig.update_xaxes(type="log")
    best = min(
        metrics["serving"], key=lambda b: metrics["serving"][b]["concurrency"]["c1"]["p50_s"]
    )
    add_takeaway(
        fig,
        f"Single uvicorn worker on one laptop: latency degrades gently to c=16, then queues. "
        f"Fastest single-request backend: {BACKEND_LABELS[best]}. Warm-up excluded; "
        f"median of {metrics['serving']['native']['concurrency']['c1']['repeats']} repeats.",
    )
    return fig


def batch_throughput_curve(metrics: dict[str, Any]) -> go.Figure:
    """Throughput (rows/s) and per-request p50 latency vs batch size."""
    sizes = [int(c[1:]) for c in metrics["serving"]["native"]["batch"]]
    fig = make_subplots(
        rows=1,
        cols=2,
        column_titles=["throughput (rows/s)", "per-request p50 latency (s)"],
        horizontal_spacing=0.09,
    )
    for backend in ("native", "onnx"):
        cells = _backend_cells(metrics, backend, "batch")
        fig.add_scatter(
            x=sizes,
            y=[cells[f"b{b}"]["throughput_rps"] for b in sizes],
            mode="lines+markers",
            name=BACKEND_LABELS[backend],
            legendgroup=backend,
            line={"color": BACKEND_COLORS[backend], "width": 2},
            marker={"color": BACKEND_COLORS[backend], "size": 8},
            row=1,
            col=1,
        )
        fig.add_scatter(
            x=sizes,
            y=[cells[f"b{b}"]["p50_s"] for b in sizes],
            mode="lines+markers",
            name=BACKEND_LABELS[backend],
            legendgroup=backend,
            showlegend=False,
            line={"color": BACKEND_COLORS[backend], "width": 2, "dash": "dash"},
            marker={"color": BACKEND_COLORS[backend], "size": 8},
            row=1,
            col=2,
        )
    apply_theme(fig, height=600)
    fig.update_layout(
        title="Batch endpoint — /predict/batch sizes 1 to 128 (median of repeats)",
        margin={"l": 90, "r": 140, "t": 110, "b": 70},
    )
    fig.update_xaxes(type="log", title_text="batch size (rows/request)", row=1, col=1)
    fig.update_xaxes(type="log", title_text="batch size (rows/request)", row=1, col=2)
    onnx_t = metrics["serving"]["onnx"]["batch"][f"b{sizes[-1]}"]["throughput_rps"]
    native_t = metrics["serving"]["native"]["batch"][f"b{sizes[-1]}"]["throughput_rps"]
    add_takeaway(
        fig,
        f"Batch cells run saturated (all {metrics['bench_protocol']['batch_requests_per_size']} "
        f"requests in flight), so per-request latency is queue-dominated and stays flat while "
        f"throughput scales ~linearly with batch size: {onnx_t:.0f} rows/s (onnx) vs "
        f"{native_t:.0f} (native) at size {sizes[-1]}.",
    )
    return fig


def backend_comparison_slope(metrics: dict[str, Any]) -> go.Figure:
    """Paired native→ONNX p50 slope graph per concurrency cell."""
    levels = [int(c[1:]) for c in metrics["serving"]["native"]["concurrency"]]
    fig = go.Figure()
    for c in levels:
        native_p50 = metrics["serving"]["native"]["concurrency"][f"c{c}"]["p50_s"]
        onnx_p50 = metrics["serving"]["onnx"]["concurrency"][f"c{c}"]["p50_s"]
        ratio = onnx_p50 / native_p50 if native_p50 else float("nan")
        fig.add_scatter(
            x=[0, 1],
            y=[native_p50, onnx_p50],
            mode="lines+markers+text",
            name=f"c={c}",
            text=["", f"x{ratio:.2f}"],
            textposition="middle right",
            line={"width": 2},
            marker={"size": 10},
        )
    fig.add_annotation(x=0, y=1.02, yref="paper", text="native", showarrow=False)
    fig.add_annotation(x=1, y=1.02, yref="paper", text="onnx", showarrow=False)
    apply_theme(fig, height=600)
    fig.update_layout(
        title="Paired p50 latency, native → ONNX — identical request streams, seed 42",
        yaxis_title="p50 latency (s)",
        margin={"l": 90, "r": 160, "t": 110, "b": 70},
    )
    fig.update_xaxes(range=[-0.15, 1.25], showticklabels=False, title_text="backend")
    add_takeaway(
        fig,
        "x-labels are the ONNX/native p50 ratio per cell; below 1.0 the ONNX backend is "
        "faster on identical work. Deviation from a pure ratio marks per-backend scheduling "
        "noise, not a different model — parity is gated at the artifact level.",
    )
    return fig


def footprint_cost_bars(metrics: dict[str, Any]) -> go.Figure:
    """Three panels: RSS, image size breakdown, electricity cost per 1k preds."""
    fig = make_subplots(
        rows=1,
        cols=3,
        column_titles=[
            "fresh-process RSS (MB)",
            "image size (MB)",
            "cost per 1k predictions (USD)",
        ],
        horizontal_spacing=0.12,
    )
    backends = ["native", "onnx"]
    fig.add_bar(
        x=[BACKEND_LABELS[b] for b in backends],
        y=[metrics["serving"][b]["rss_mb"]["median"] for b in backends],
        marker={"color": [BACKEND_COLORS[b] for b in backends]},
        showlegend=False,
        row=1,
        col=1,
    )
    docker = metrics["docker"]
    if docker.get("measured"):
        fig.add_bar(
            x=["runtime base", "venv (deps)", "model"],
            y=[docker["base_python_slim_mb"], docker["venv_mb"], docker["models_mb"]],
            marker={"color": ["#64748b", "#a78bfa", "#2dd4bf"]},
            showlegend=False,
            row=1,
            col=2,
        )
    cost = metrics["cost"]["cost_per_1k_predictions_usd"]
    fig.add_bar(
        x=[BACKEND_LABELS[b] for b in backends],
        y=[cost[b] for b in backends],
        marker={"color": [BACKEND_COLORS[b] for b in backends]},
        showlegend=False,
        row=1,
        col=3,
    )
    apply_theme(fig, height=560)
    fig.update_layout(
        title="Footprint and cost — fresh process, baked image, declared 65 W / $0.30 per kWh",
        margin={"l": 90, "r": 140, "t": 110, "b": 70},
    )
    if docker.get("measured"):
        add_takeaway(
            fig,
            f"Image total {docker['total_mb']:.0f} MB — torch dominates the venv. Cost uses "
            f"measured throughput at concurrency 16; the wattage is a declared assumption "
            f"(no wall meter), the same framing as experiment 08.",
        )
    else:
        add_takeaway(
            fig,
            "Docker daemon unavailable at bench time — image size not measured; cost uses "
            "measured throughput at concurrency 16 (wattage declared, no wall meter).",
        )
    return fig


def build_figures(metrics: dict[str, Any]) -> dict[str, go.Figure]:
    """The committed figure set, keyed by filename stem."""
    return {
        "latency_concurrency_lines": latency_concurrency_lines(metrics),
        "batch_throughput_curve": batch_throughput_curve(metrics),
        "backend_comparison_slope": backend_comparison_slope(metrics),
        "footprint_cost_bars": footprint_cost_bars(metrics),
    }
