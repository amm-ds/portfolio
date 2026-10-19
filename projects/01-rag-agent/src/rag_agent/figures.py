"""Plotly figure builders for the evaluation report.

Every figure is themed via ``portfolio_core.plotting`` and carries a
descriptive second title line (what is plotted, units, sample/scope) — the
conclusion lives in the story's ``figure_captions``, not in the chart.
Builders are pure: they take
measurements (from :mod:`rag_agent.reporting`) and return ``go.Figure`` objects;
writing to disk happens in :mod:`rag_agent.reporting`.
"""

import numpy as np
import plotly.graph_objects as go
from portfolio_core.plotting import add_takeaway, apply_theme, style_runs

from rag_agent.config import RAGConfig, RetrievalBest
from rag_agent.reporting import (
    TOP_K_VALUES,
    QuestionTrace,
    RetrievalScores,
    TopkData,
    classify_question,
    est_input_tokens_at,
    recall_at_k_from,
)
from rag_agent.schemas import Article, EvalQuestion


def _finish_themed(
    fig: go.Figure,
    *,
    takeaway: str | None = None,
    showlegend: bool | None = None,
) -> go.Figure:
    """Apply the shared theme; the takeaway rides as a second title line.

    ``add_takeaway`` renders the takeaway as a muted second line of the title
    itself (a separate annotation collides with the top-pinned title). Where a
    title already states the takeaway, callers pass no ``takeaway``. Margins
    and legend placement are the house standard's job (``apply_theme`` fills
    them); only genuinely exceptional figures set their own afterwards.
    Single-trace figures pass ``showlegend=False`` so the legend does not
    render a "trace 0" chip.
    """
    if takeaway:
        fig = add_takeaway(fig, takeaway)
    fig = apply_theme(fig)
    if showlegend is not None:
        fig.update_layout(showlegend=showlegend)
    return fig


def sweep_figure(
    scores: list[RetrievalScores],
    random_scores: list[RetrievalScores] | None = None,
    lexical_scores: list[RetrievalScores] | None = None,
) -> go.Figure:
    """Chunk-size sweep: grouped bars with value labels + the two retrieval floors.

    Readability contract (wave 16, viewer report "chunk size 600 has no bars"):
    the x-axis is **categorical** — chunk sizes are a deliberate 2x grid
    (200/400/800), no 600 configuration exists anywhere in the sweep, and a
    continuous axis left a suggestive void between bars. Every bar carries its
    value label, the chosen size is starred, and zero-valued random-floor points
    are labelled and annotated as measurements rather than left as empty space.

    Legend contract (wave 17, viewer report "legend unreadable on the title"):
    with the two-line title + subtitle annotation, the theme's top-pinned
    horizontal legend collides with the text — and the seven long series names
    ("random baseline recall@5 (seeded floor)") cannot fit the standard's
    140 px right margin. Deliberate exception: the legend stays **below**
    the plot, bottom-center, and the bottom margin carries it.
    """
    sizes = [s.chunk_size for s in scores]
    labels = [str(s) for s in sizes]
    chosen_size = max(scores, key=lambda s: s.mrr_at_5).chunk_size
    fig = go.Figure(
        data=[
            go.Bar(
                name="recall@5",
                x=labels,
                y=[s.recall_at_5 for s in scores],
                text=[f"{s.recall_at_5:.3f}" for s in scores],
                textposition="outside",
            ),
            go.Bar(
                name="recall@10",
                x=labels,
                y=[s.recall_at_10 for s in scores],
                text=[f"{s.recall_at_10:.3f}" for s in scores],
                textposition="outside",
            ),
            go.Bar(
                name="mrr@5",
                x=labels,
                y=[s.mrr_at_5 for s in scores],
                text=[f"{s.mrr_at_5:.3f}" for s in scores],
                textposition="outside",
            ),
        ]
    )
    if lexical_scores:
        # Deterministic word-match floor: the fair naive comparator a client
        # would ask about before buying embeddings (chance → lexical → embeddings).
        lex_recall = [s.recall_at_5 for s in lexical_scores]
        lex_mrr = [s.mrr_at_5 for s in lexical_scores]
        fig.add_trace(
            go.Scatter(
                name="lexical (word match) recall@5",
                x=labels,
                y=lex_recall,
                mode="lines+markers+text",
                text=[f"{v:.3f}" for v in lex_recall],
                textposition="top center",
                line={"dash": "dash", "color": "#a78bfa", "width": 2},
            )
        )
        fig.add_trace(
            go.Scatter(
                name="lexical (word match) mrr@5",
                x=labels,
                y=lex_mrr,
                mode="lines+markers+text",
                text=[f"{v:.3f}" for v in lex_mrr],
                textposition="bottom center",
                line={"dash": "dot", "color": "#34d399", "width": 2},
            )
        )
    if random_scores:
        # Flat dashed reference series so the embedding gain is visible.
        rnd_recall = [s.recall_at_5 for s in random_scores]
        rnd_mrr = [s.mrr_at_5 for s in random_scores]
        fig.add_trace(
            go.Scatter(
                name="random baseline recall@5 (seeded floor)",
                x=labels,
                y=rnd_recall,
                mode="lines+markers+text",
                text=[f"{v:.3f}" for v in rnd_recall],
                textposition="top center",
                line={"dash": "dash", "color": "#f472b6", "width": 2},
            )
        )
        fig.add_trace(
            go.Scatter(
                name="random baseline mrr@5 (seeded floor)",
                x=labels,
                y=rnd_mrr,
                mode="lines+markers+text",
                text=[f"{v:.3f}" for v in rnd_mrr],
                textposition="bottom center",
                line={"dash": "dot", "color": "#fbbf24", "width": 2},
            )
        )
        # A zero on the floor is a real measurement (chance found nothing), not
        # a missing bar — say so on the figure instead of leaving a void.
        zero_labels = [label for label, v in zip(labels, rnd_recall, strict=True) if v == 0.0]
        for label in zero_labels:
            fig.add_annotation(
                # Categorical-axis annotations must use the integer category
                # index: string coordinates break grouped-bar rendering
                # (verified against kaleido 1.5 / plotly.js, wave 16).
                x=labels.index(label),
                xref="x",
                y=0.0,
                yref="y",
                text="0 — seeded chance floor, not a missing bar",
                showarrow=True,
                arrowhead=2,
                ax=0,
                ay=-40,
                font={"size": 11, "color": "#fbbf24"},
                bgcolor="#0f172a",
                bordercolor="#fbbf24",
                borderwidth=1,
                borderpad=3,
            )
    fig.update_layout(
        barmode="group",
        title="Retrieval recall vs chunk size",
        xaxis={
            "type": "category",
            "categoryorder": "array",
            "categoryarray": labels,
            "title": "chunk size (tokens)",
        },
        yaxis={"title": "score", "range": [0, 1.0]},
    )
    tested = " / ".join(labels)
    fig.add_annotation(
        text=(
            f"Chunk sizes tested: {tested} (2x grid; chosen {chosen_size}). "
            "The axis is categorical — no 600-token configuration exists."
        ),
        xref="paper",
        yref="paper",
        x=0.02,
        # Above the two-line title: the deep bottom margin (legend below the
        # plot) shrinks the plot area, so 1.16 would land inside the title.
        y=1.30,
        xanchor="left",
        yanchor="bottom",
        showarrow=False,
        font={"size": 12, "color": "#e2e8f0"},
        align="left",
    )
    fig.add_annotation(
        text=f"★ chosen: {chosen_size}-token chunks",
        xref="x",
        x=labels.index(str(chosen_size)),
        yref="paper",
        y=0.97,
        showarrow=False,
        font={"size": 12, "color": "#2dd4bf"},
        xanchor="center",
    )
    fig = _finish_themed(
        fig,
        takeaway=(
            "recall@5, recall@10, MRR@5 — 65 golden questions; random + lexical floors dashed"
        ),
    )
    # Exceptional margins: the caption annotation sits ABOVE the two-line
    # title (deep bottom margin for the below-plot legend shrinks the plot
    # area, so y=1.30 would land inside the title) and the bottom-center
    # legend (deliberate exception — seven long series names cannot fit the
    # standard 140 px right margin) needs the deeper bottom band.
    fig.update_layout(margin={"t": 160, "b": 115})
    fig.update_layout(
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.24,
            "x": 0.5,
            "xanchor": "center",
        }
    )
    return fig


def model_comparison_figure(model_scores: dict[str, RetrievalScores], best_slug: str) -> go.Figure:
    slugs = list(model_scores)
    metrics = ["recall@5", "recall@10", "mrr@5"]
    fig = go.Figure(
        data=[
            go.Scatter(
                name=slug,
                x=metrics,
                y=[
                    model_scores[slug].recall_at_5,
                    model_scores[slug].recall_at_10,
                    model_scores[slug].mrr_at_5,
                ],
                mode="lines+markers",
            )
            for slug in slugs
        ]
    )
    style_runs(fig, best=best_slug)
    fig.update_layout(
        title="Retrieval metrics by encoder",
        yaxis_title="score",
    )
    return _finish_themed(
        fig,
        takeaway=(
            "recall@5, recall@10, MRR@5 per encoder — 65 golden questions; "
            "grey = floors, accent = best"
        ),
    )


def hpo_frontier_figure(
    config: RAGConfig,
    questions: list[EvalQuestion],
    topk: dict[int, TopkData],
    chosen: RetrievalBest,
) -> go.Figure:
    """Quality-vs-cost frontier over the full (chunk size x top_k) grid."""
    fig = go.Figure()
    for size in config.chunk_sizes:
        fig.add_trace(
            go.Scatter(
                name=f"chunks={size}",
                x=[est_input_tokens_at(topk[size], questions, k) for k in TOP_K_VALUES],
                y=[recall_at_k_from(topk[size], k) for k in TOP_K_VALUES],
                mode="lines+markers+text",
                text=[f"k={k}" for k in TOP_K_VALUES],
                textposition="top center",
            )
        )
    chosen_x = est_input_tokens_at(topk[chosen.chunk_size], questions, chosen.top_k)
    chosen_y = recall_at_k_from(topk[chosen.chunk_size], chosen.top_k)
    fig.add_trace(
        go.Scatter(
            name="chosen config",
            x=[chosen_x],
            y=[chosen_y],
            mode="markers",
            marker={"symbol": "star", "size": 18, "color": "#f472b6"},
        )
    )
    fig.update_layout(
        title="Retrieval recall@k vs estimated input tokens",
        xaxis_title="estimated input tokens per query",
        yaxis_title="recall@k",
    )
    return _finish_themed(
        fig,
        takeaway=(
            f"★ = chosen config: {chosen.embedding_slug}, chunks={chosen.chunk_size}, "
            f"top_k={chosen.top_k}, rerank {'on' if chosen.rerank else 'off'}"
        ),
    )


def retrieval_funnel_figure(
    config: RAGConfig,
    questions: list[EvalQuestion],
    topk: dict[int, TopkData],
    chosen: RetrievalBest,
) -> go.Figure:
    """Aggregate retrieval funnel: candidates → after rerank → relevant."""
    size_data = topk[chosen.chunk_size]
    n = len(questions)
    n_candidates = min(size_data["n_chunks"], chosen.top_k * config.rerank_multiplier)
    relevant = sum(1 for r in size_data["ranks"] if r is not None and r <= chosen.top_k)
    fig = go.Figure(
        go.Funnel(
            y=[
                f"embedding candidates (top-{n_candidates})",
                f"after rerank (top-{chosen.top_k})",
                "relevant article in top-k",
            ],
            x=[n * n_candidates, n * chosen.top_k, relevant],
            textinfo="value+percent initial",
        )
    )
    fig.update_layout(title="Retrieval funnel: candidates→reranked→relevant")
    return _finish_themed(
        fig,
        takeaway=(
            f"aggregate over {n} questions — top-{n_candidates} candidates → "
            f"top-{chosen.top_k} after rerank → {relevant} relevant"
        ),
        showlegend=False,  # single unnamed trace → no "trace 0" chip
    ).update_layout(margin={"l": 240})  # long funnel stage labels need left room


def corpus_eda_figure(articles: list[Article]) -> go.Figure:
    """EDA: articles per topic + article-length (words) distribution."""
    from plotly.subplots import make_subplots

    topics = sorted({a.topic for a in articles})
    counts = [sum(1 for a in articles if a.topic == t) for t in topics]
    lengths = [len(a.text.split()) for a in articles]

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Articles per topic", "Article length (words)"),
    )
    fig.add_trace(go.Bar(x=topics, y=counts, name="articles"), row=1, col=1)
    fig.add_trace(go.Histogram(x=lengths, nbinsx=40, name="article length"), row=1, col=2)
    fig.update_layout(
        title="Corpus composition",
        showlegend=False,
    )
    return _finish_themed(
        fig,
        takeaway=(
            f"articles per topic (left), word counts (right) — "
            f"{len(articles)} articles; tail capped at 12k chars"
        ),
    )


def taxonomy_figure(traces: list[QuestionTrace]) -> go.Figure:
    """Failure-taxonomy breakdown: counts per deterministic verdict class."""
    order = ["correct", "retrieval-miss", "unsupported-claim", "format-failure"]
    counts = {label: 0 for label in order}
    for trace in traces:
        counts[classify_question(trace)] += 1
    fig = go.Figure(
        data=[
            go.Bar(
                x=order,
                y=[counts[label] for label in order],
                marker_color=["#34d399", "#fbbf24", "#f472b6", "#a78bfa"],
            )
        ]
    )
    fig.update_layout(
        title="Answer verdicts by category",
        xaxis_title="verdict",
        yaxis_title="questions",
    )
    return _finish_themed(
        fig,
        takeaway=(f"counts per deterministic verdict class — hosted {len(traces)}-question run"),
        showlegend=False,  # single unnamed trace → no "trace 0" chip
    )


def latency_figure(latencies_s: list[float]) -> go.Figure:
    fig = go.Figure(data=[go.Histogram(x=latencies_s, nbinsx=20)])
    p50 = float(np.percentile(latencies_s, 50))
    p95 = float(np.percentile(latencies_s, 95))
    fig.update_layout(
        title="Answer latency distribution",
        xaxis_title="latency (s)",
        yaxis_title="queries",
    )
    return _finish_themed(
        fig,
        takeaway=f"per-query latency, hosted 65-question run — p50 {p50:.0f} s, p95 {p95:.0f} s",
        showlegend=False,  # single unnamed trace
    )


def frontier_figure(
    config: RAGConfig,
    scores: list[RetrievalScores],
    est_input_tokens_per_query: dict[int, float],
    avg_output_tokens: float,
    rag_quality_by_size: dict[int, float],
) -> go.Figure:
    """Cost-vs-quality frontier: one point per chunk size (legacy builder)."""
    points = []
    for s in scores:
        in_tok = est_input_tokens_per_query.get(s.chunk_size)
        quality = rag_quality_by_size.get(s.chunk_size)
        if in_tok is None or quality is None:
            continue
        cost = (
            in_tok / 1e6 * config.usd_per_mtok_input
            + avg_output_tokens / 1e6 * config.usd_per_mtok_output
        )
        points.append((cost, quality, s.chunk_size))
    fig = go.Figure(
        data=[
            go.Scatter(
                x=[p[0] for p in points],
                y=[p[1] for p in points],
                mode="markers+text",
                text=[f"chunks={p[2]}" for p in points],
                textposition="top center",
                marker={"size": 12},
            )
        ]
    )
    fig.update_layout(
        title="Cost vs quality frontier (estimated, per query)",
        xaxis_title="estimated cost per query (USD)",
        yaxis_title="answer relevance",
    )
    return _finish_themed(fig, showlegend=False)  # single unnamed trace
