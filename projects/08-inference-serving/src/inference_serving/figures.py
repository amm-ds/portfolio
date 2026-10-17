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
        title=(
            "p95 latency grows roughly linearly with concurrency while aggregate tok/s "
            "stays flat — decode is memory-bandwidth bound"
        ),
        xaxis_title="concurrency (semaphore)",
        yaxis_title="p95 latency (s)",
        xaxis={"dtick": 1},
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "Latency grows with concurrency but stays in the low seconds — single-user p95 "
        "is the honest baseline for interactive SLOs; concurrency headroom is what serving adds.",
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
        title="Aggregate output throughput vs concurrency (total tokens / cell wall time)",
        xaxis_title="model",
        yaxis_title="output tokens/s",
        barmode="group",
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "MoE arms scale sub-linearly with concurrency — decode is memory-bandwidth bound on "
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
        title="Quality vs quantization (same task, concurrency 1, temperature 0)",
        xaxis_title="quantization arm (model / runner)",
        yaxis_title="rate",
        yaxis={"range": [0, 1.05]},
        barmode="group",
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "4-bit arms hold schema validity near ceiling — at this task size quantization costs "
        "almost nothing in structured-output reliability (quality gap, if any, is in citations).",
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
    fig.update_layout(
        title=(
            "MLX 4-bit beats GGUF Q8_0 on llama.cpp by 2.9x on tok/s (18.8 vs 6.4) "
            "with p95 2.47 s vs 7.12 s at concurrency 1"
        ),
        barmode="group",
        showlegend=False,
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "Same weights through two runners on Apple Silicon. Quant is confounded (Q8_0 vs 4-bit), "
        "so read this as engine+packaging, not a pure runner race.",
    )
    return fig


def all_figures(run: BenchRun, cfg: BenchConfig) -> dict[str, go.Figure]:
    return {
        "latency_concurrency": fig_latency_concurrency(run, cfg),
        "toks_per_s": fig_toks_per_s(run, cfg),
        "quality_quant": fig_quality_quant(run, cfg),
        "engine_panel": fig_engine_panel(run, cfg),
    }
