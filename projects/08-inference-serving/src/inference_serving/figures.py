"""Plotly figures for the benchmark report (portfolio theme + takeaways)."""

from __future__ import annotations

import plotly.graph_objects as go
from portfolio_core.plotting import add_takeaway, apply_theme, style_runs

from inference_serving.config import BenchConfig
from inference_serving.schemas import BenchRun, CellResult


def _label(cell: CellResult) -> str:
    return f"{cell.model} ({cell.engine})"


def _primary_cells(run: BenchRun, cfg: BenchConfig) -> list[CellResult]:
    extra = {m.name for m in cfg.quality_models + cfg.engine_models}
    return [c for c in run.cells if c.model not in extra]


def fig_latency_concurrency(run: BenchRun, cfg: BenchConfig) -> go.Figure:
    """p95 latency vs concurrency, one trace per primary model (+runner)."""
    fig = go.Figure()
    cells = sorted(_primary_cells(run, cfg), key=lambda c: (c.model, c.concurrency))
    for model in sorted({c.model for c in cells}):
        subset = [c for c in cells if c.model == model]
        fig.add_scatter(
            x=[c.concurrency for c in subset],
            y=[c.p95_latency_s for c in subset],
            mode="lines+markers",
            name=next((_label(c) for c in subset), model),
        )
    fig.update_layout(
        title="p95 latency grows linearly with concurrency",
        xaxis_title="concurrency (semaphore)",
        yaxis_title="p95 latency (s)",
        xaxis={"dtick": 1},
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "aggregate tok/s stays flat — decode is memory-bandwidth bound; single-user p95 "
        "is the honest SLO baseline; concurrency headroom is what serving adds.",
    )
    return style_runs(fig)


def fig_toks_per_s(run: BenchRun, cfg: BenchConfig) -> go.Figure:
    """Aggregate output tok/s bars per model x concurrency."""
    fig = go.Figure()
    cells = _primary_cells(run, cfg)
    models = sorted({c.model for c in cells})
    levels = sorted({c.concurrency for c in cells})
    for level in levels:
        y = [
            next(
                (c.agg_tok_per_s for c in cells if c.model == m and c.concurrency == level),
                None,
            )
            for m in models
        ]
        fig.add_bar(x=models, y=y, name=f"c={level}")
    fig.update_layout(
        title="Throughput is flat-to-declining in concurrency",
        xaxis_title="model",
        yaxis_title="output tokens/s",
        barmode="group",
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "the 3B-active MoE serves ~7x dense tok/s — decode is memory-bandwidth bound on "
        "unified memory, so batching buys latency hiding, not free throughput.",
    )
    return fig


def fig_quality_quant(run: BenchRun, cfg: BenchConfig) -> go.Figure:
    """Schema-valid rate and keyword quality across quantization arms (c=1)."""
    wanted = [m.name for m in cfg.quality_models + cfg.engine_models]
    cells = [c for c in run.cells if c.model in wanted and c.concurrency == 1]
    cells.sort(key=lambda c: wanted.index(c.model))
    fig = go.Figure(
        [
            go.Bar(
                x=[_label(c) for c in cells],
                y=[c.schema_valid_rate for c in cells],
                name="schema-valid rate",
            ),
            go.Bar(
                x=[_label(c) for c in cells],
                y=[c.quality_rate for c in cells],
                name="keyword quality rate",
            ),
        ]
    )
    fig.update_layout(
        title="Schema-valid rate holds at 1.00 across quant arms",
        xaxis_title="quantization arm (model / runner)",
        yaxis_title="rate",
        yaxis={"range": [0, 1.05]},
        barmode="group",
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "4-bit and Q8_0 arms — quantization costs headroom, not quality; structured-output "
        "reliability sits near ceiling (any quality gap is in citations).",
    )
    return fig


def fig_engine_panel(run: BenchRun, cfg: BenchConfig) -> go.Figure:
    """llama.cpp vs MLX on the same model family (gemma4:31b weights)."""
    from plotly.subplots import make_subplots

    wanted = [m.name for m in cfg.engine_models]
    cells = [c for c in run.cells if c.model in wanted and c.concurrency == 1]
    cells.sort(key=lambda c: wanted.index(c.model))
    labels = [_label(c) for c in cells]
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("p95 latency (s)", "output tok/s"),
        shared_xaxes=True,
    )
    fig.add_bar(x=labels, y=[c.p95_latency_s for c in cells], row=1, col=1)
    fig.add_bar(x=labels, y=[c.agg_tok_per_s for c in cells], row=1, col=2)
    hw = "Apple Silicon (macOS arm64)" if "arm64" in run.platform else run.platform
    fig.update_layout(
        title="MLX 4-bit beats llama.cpp Q8_0 by 2.9x tok/s",
        barmode="group",
        showlegend=False,
    )
    apply_theme(fig)
    # Embedded-size readability (audit): bigger tick + panel-title fonts, and
    # the subtitle states hardware + quantization explicitly — not only in
    # the cryptic series names.
    fig.update_xaxes(tickfont={"size": 15})
    fig.update_yaxes(tickfont={"size": 14})
    fig.update_annotations(font_size=15)
    add_takeaway(
        fig,
        f"18.8 vs 6.4 tok/s, p95 2.47 s vs 7.12 s at c=1 — same gemma4:31b weights on "
        f"{hw}. Quant is confounded with packaging, not a pure runner race.",
    )
    return fig


def all_figures(run: BenchRun, cfg: BenchConfig) -> dict[str, go.Figure]:
    return {
        "latency_concurrency": fig_latency_concurrency(run, cfg),
        "toks_per_s": fig_toks_per_s(run, cfg),
        "quality_quant": fig_quality_quant(run, cfg),
        "engine_panel": fig_engine_panel(run, cfg),
    }
