"""Plotly figures for the benchmark report (portfolio theme + takeaways)."""

from __future__ import annotations

import statistics

import plotly.graph_objects as go
from portfolio_core.plotting import add_takeaway, apply_theme, style_runs

from inference_serving.config import BenchConfig
from inference_serving.schemas import BenchRun, CellResult, RequestRecord


def _label(cell: CellResult) -> str:
    return f"{cell.model} ({cell.engine})"


def _primary_cells(run: BenchRun, cfg: BenchConfig) -> list[CellResult]:
    extra = {m.name for m in cfg.quality_models + cfg.engine_models}
    return [c for c in run.cells if c.model not in extra]


def _per_cell_records(run: BenchRun) -> list[list[RequestRecord]] | None:
    """Slice ``run.records`` into per-cell lists.

    ``run_bench`` extends records in cell order, so each cell owns the next
    ``cell.n_requests`` records. Returns None when the run carries no raw
    records (e.g. rebuilt from metrics.json) or the counts do not line up.
    """
    total = sum(c.n_requests for c in run.cells)
    if not run.records or len(run.records) != total:
        return None
    out: list[list[RequestRecord]] = []
    offset = 0
    for cell in run.cells:
        out.append(run.records[offset : offset + cell.n_requests])
        offset += cell.n_requests
    return out


def _req_tok_s_std(records: list[RequestRecord]) -> float | None:
    """Std-dev of per-request tok/s (output tokens / request latency)."""
    values = [r.output_tokens / r.latency_s for r in records if r.output_tokens and r.latency_s]
    return statistics.stdev(values) if len(values) >= 2 else None


def fig_latency_concurrency(run: BenchRun, cfg: BenchConfig) -> go.Figure:
    """p95 latency vs concurrency, one trace per primary model (+runner).

    Error bars span the committed p50-p99 percentile band around each p95
    point (nearest-rank, per 40-request cell) - the spread the benchmark
    artifact itself reports, not a model of the distribution.
    """
    fig = go.Figure()
    cells = sorted(_primary_cells(run, cfg), key=lambda c: (c.model, c.concurrency))
    for model in sorted({c.model for c in cells}):
        subset = [c for c in cells if c.model == model]
        error_y = None
        have_pct = all(
            c.p50_latency_s is not None
            and c.p95_latency_s is not None
            and c.p99_latency_s is not None
            for c in subset
        )
        if have_pct:
            error_y = {
                "type": "data",
                "array": [c.p99_latency_s - c.p95_latency_s for c in subset],  # type: ignore[operator]
                "arrayminus": [c.p95_latency_s - c.p50_latency_s for c in subset],  # type: ignore[operator]
            }
        fig.add_scatter(
            x=[c.concurrency for c in subset],
            y=[c.p95_latency_s for c in subset],
            mode="lines+markers",
            name=next((_label(c) for c in subset), model),
            error_y=error_y,
        )
    fig.update_layout(
        title="p95 latency vs concurrency by model",
        xaxis_title="concurrency (semaphore)",
        yaxis_title="p95 latency (s)",
        xaxis={"dtick": 1},
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "primary models; c = semaphore level; p95 per 40-request cell (8 prompts x 5 repeats); "
        "error bars span the p50-p99 band",
    )
    return style_runs(fig)


def fig_toks_per_s(run: BenchRun, cfg: BenchConfig) -> go.Figure:
    """Aggregate output tok/s bars per model x concurrency.

    Error bars are +/-1 std-dev of per-request tok/s across the cell's
    requests, computed from the committed run records; they are omitted when
    the run carries no raw records (e.g. rebuilt from metrics.json alone).
    """
    fig = go.Figure()
    cells = _primary_cells(run, cfg)
    models = sorted({c.model for c in cells})
    levels = sorted({c.concurrency for c in cells})
    per_cell = _per_cell_records(run)
    stds: dict[tuple[str, int], float | None] = {}
    if per_cell is not None:
        stds = {
            (cell.model, cell.concurrency): _req_tok_s_std(recs)
            for cell, recs in zip(run.cells, per_cell, strict=True)
        }
    for level in levels:
        y = [
            next(
                (c.agg_tok_per_s for c in cells if c.model == m and c.concurrency == level),
                None,
            )
            for m in models
        ]
        err = [stds.get((m, level)) for m in models] if per_cell is not None else None
        fig.add_bar(x=models, y=y, name=f"c={level}", error_y={"type": "data", "array": err})
    fig.update_layout(
        title="Output tok/s by model and concurrency",
        xaxis_title="model",
        yaxis_title="output tokens/s",
        barmode="group",
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "aggregate tok/s over cell wall time per concurrency; "
        "error bars: +/-1 std-dev of per-request tok/s per 40-request cell; "
        "single Apple-Silicon run",
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
        title="Schema & keyword quality by quantization arm",
        xaxis_title="quantization arm (model / runner)",
        yaxis_title="rate",
        yaxis={"range": [0, 1.05]},
        barmode="group",
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        "quantization + engine arms at c=1; keyword quality = expected-answer terms present",
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
    hw = "Apple Silicon" if "arm64" in run.platform else run.platform
    fig.update_layout(
        title="Engine panel: p95 latency & tok/s (gemma4:31b)",
        barmode="group",
        showlegend=False,
    )
    apply_theme(fig)
    # Embedded-size readability (audit): bigger tick + panel-title fonts, and
    # the subtitle states hardware explicitly — not only in the cryptic
    # series names.
    fig.update_xaxes(tickfont={"size": 15})
    fig.update_yaxes(tickfont={"size": 14})
    fig.update_annotations(font_size=15)
    add_takeaway(
        fig,
        f"same gemma4:31b weights on {hw} at c=1 — 18.8 vs 6.4 tok/s, p95 2.47 vs 7.12 s",
    )
    return fig


def all_figures(run: BenchRun, cfg: BenchConfig) -> dict[str, go.Figure]:
    return {
        "latency_concurrency": fig_latency_concurrency(run, cfg),
        "toks_per_s": fig_toks_per_s(run, cfg),
        "quality_quant": fig_quality_quant(run, cfg),
        "engine_panel": fig_engine_panel(run, cfg),
    }
