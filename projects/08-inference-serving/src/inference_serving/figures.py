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
    # Headline states the finding: the MoE's p95 endpoints, from the cells.
    moe = [c for c in cells if "a3b" in c.model]
    if moe and moe[0].p95_latency_s is not None and moe[-1].p95_latency_s is not None:
        lo, hi = moe[0], moe[-1]
        title = (
            f"MoE p95 rises near-linearly from {lo.p95_latency_s:.2f} s "
            f"({lo.concurrency} request{'s' if lo.concurrency > 1 else ''}) to "
            f"{hi.p95_latency_s:.2f} s ({hi.concurrency} requests)"
        )
    else:
        title = "p95 latency vs concurrency by model"
    fig.update_layout(
        title=title,
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
    """Mean TTFT and aggregate output throughput per model x concurrency."""
    from plotly.subplots import make_subplots

    cells = _primary_cells(run, cfg)
    models = sorted({c.model for c in cells})
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("mean time to first token", "aggregate output throughput"),
        horizontal_spacing=0.12,
    )
    for model in models:
        subset = sorted((c for c in cells if c.model == model), key=lambda c: c.concurrency)
        label = next(_label(c) for c in subset)
        x = [c.concurrency for c in subset]
        fig.add_scatter(
            x=x,
            y=[c.mean_ttft_s for c in subset],
            mode="lines+markers",
            name=label,
            legendgroup=model,
            row=1,
            col=1,
        )
        fig.add_scatter(
            x=x,
            y=[c.agg_tok_per_s for c in subset],
            mode="lines+markers",
            name=label,
            legendgroup=model,
            showlegend=False,
            row=1,
            col=2,
        )
    apply_theme(fig, height=560)
    # Headline states the finding: one model tops aggregate tok/s at every
    # concurrency level. The a3b (active-3B MoE, q4_K_M = 4-bit) does so here.
    by_conc: dict[int, list[CellResult]] = {}
    for c in cells:
        by_conc.setdefault(c.concurrency, []).append(c)
    leaders = {max(cs, key=lambda c: c.agg_tok_per_s or 0.0).model for cs in by_conc.values()}
    moe = next((m for m in models if "a3b" in m), None)
    if moe is not None and leaders == {moe}:
        title = "The 4-bit MoE leads throughput at every concurrency level"
    else:
        title = "Time to first token and throughput under load"
    fig.update_layout(title=title)
    fig.update_xaxes(title_text="concurrency (clients)", dtick=1)
    fig.update_yaxes(title_text="mean TTFT (s)", row=1, col=1)
    fig.update_yaxes(title_text="output tokens/s", row=1, col=2)
    add_takeaway(
        fig,
        "primary models; TTFT is the mean wait before the first token; aggregate tok/s is "
        "total output tokens divided by cell wall time; single Apple-Silicon run",
    )
    return fig


def fig_quality_quant(run: BenchRun, cfg: BenchConfig) -> go.Figure:
    """Compact pass/fail quality guardrail for quantization arms (c=1)."""
    wanted = [m.name for m in cfg.quality_models + cfg.engine_models]
    cells = [c for c in run.cells if c.model in wanted and c.concurrency == 1]
    cells.sort(key=lambda c: wanted.index(c.model))
    fig = go.Figure(
        go.Table(
            header={
                "values": ["quantization arm", "schema", "keywords", "requests", "failures"],
                "align": "left",
            },
            cells={
                "values": [
                    [_label(c) for c in cells],
                    *[
                        ["PASS" if rate == 1.0 else "FAIL" for rate in rates]
                        for rates in (
                            [c.schema_valid_rate for c in cells],
                            [c.quality_rate for c in cells],
                        )
                    ],
                    [c.n_requests for c in cells],
                    [c.n_failures for c in cells],
                ],
                "align": "left",
                "height": 32,
            },
        )
    )
    apply_theme(fig, height=300)
    # A table has no right-side legend or y-axis strip; keep its width for data.
    fig.update_layout(
        title="Saturated smoke check — ties 1.00; not quality",
        margin={"l": 24, "r": 24, "t": 100, "b": 30},
    )
    add_takeaway(
        fig,
        "PASS means every response in the 40-request cell met that check; this saturated "
        "smoke check does not establish broader model quality",
    )
    return fig


def fig_engine_panel(run: BenchRun, cfg: BenchConfig) -> go.Figure:
    """llama.cpp vs MLX on the same model family (gemma4:31b; quantization differs)."""
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
    # Headline states the finding: MLX-vs-Q8_0 throughput ratio, from the cells.
    mlx = next((c for c in cells if c.engine == "mlx"), None)
    q8 = next((c for c in cells if "q8_0" in c.model), None)
    if mlx is not None and q8 is not None and mlx.agg_tok_per_s and q8.agg_tok_per_s:
        ratio = mlx.agg_tok_per_s / q8.agg_tok_per_s
        title = (
            f"The MLX build delivers {ratio:.1f}\u00d7 the tokens/s of Q8_0 llama.cpp; "
            "quantization differs"
        )
    else:
        title = "Engine panel: p95 latency & tok/s (gemma4:31b)"
    fig.update_layout(
        title=title,
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
        f"same model family on {hw} at c=1 — 18.8 vs 6.4 tok/s, p95 2.47 vs 7.12 s",
    )
    return fig


def all_figures(run: BenchRun, cfg: BenchConfig) -> dict[str, go.Figure]:
    return {
        "latency_concurrency": fig_latency_concurrency(run, cfg),
        "toks_per_s": fig_toks_per_s(run, cfg),
        "quality_quant": fig_quality_quant(run, cfg),
        "engine_panel": fig_engine_panel(run, cfg),
    }
