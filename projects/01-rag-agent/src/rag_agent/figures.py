"""Plotly figure builders for the evaluation report.

Every figure is themed via ``portfolio_core.plotting`` and carries a one-line
takeaway where the insight is not obvious. Builders are pure: they take
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


def sweep_figure(
    scores: list[RetrievalScores], random_scores: list[RetrievalScores] | None = None
) -> go.Figure:
    """Chunk-size sweep: grouped bars with value labels + the seeded random floor.

    Readability contract (wave 16, viewer report "chunk size 600 has no bars"):
    the x-axis is **categorical** — chunk sizes are a deliberate 2x grid
    (200/400/800), no 600 configuration exists anywhere in the sweep, and a
    continuous axis left a suggestive void between bars. Every bar carries its
    value label, the chosen size is starred, and zero-valued random-floor points
    are labelled and annotated as measurements rather than left as empty space.
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
        title=(
            "Chunk size, not model size, sets retrieval recall — 200-token chunks "
            "hold full recall@5 at 65% lower context cost"
        ),
        xaxis={
            "type": "category",
            "categoryorder": "array",
            "categoryarray": labels,
            "title": "chunk size (tokens)",
        },
        yaxis={"title": "score", "range": [0, 1.0]},
        margin={"t": 128, "l": 60, "r": 30, "b": 50},
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
        y=1.16,
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
    fig = apply_theme(
        add_takeaway(
            fig,
            "Recall saturates at every size; smaller chunks rank sharper (MRR) at "
            "half the context cost — every bar clears the seeded random floor.",
        )
    )
    # add_takeaway pins margin t=90; the subtitle line above it needs more headroom.
    fig.update_layout(margin={"t": 128, "l": 60, "r": 30, "b": 50})
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
        title="MiniLM and BGE-small tie at recall@5 0.831 - the cheaper encoder wins",
        yaxis_title="score",
    )
    return apply_theme(
        add_takeaway(fig, "Both encoders saturate recall@5; ranking sharpness (MRR) decides.")
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
        title=(
            "Retrieval HPO finds the quality-cost knee: recall@5 0.831 at "
            "≈800 input tokens per query"
        ),
        xaxis_title="estimated input tokens per query",
        yaxis_title="recall@k",
    )
    return apply_theme(
        add_takeaway(
            fig,
            f"Chosen: {chosen.embedding_slug}, chunks={chosen.chunk_size}, "
            f"top_k={chosen.top_k}, rerank={'on' if chosen.rerank else 'off'} — "
            f"recall {chosen_y:.3f} at ≈{chosen_x:.0f} tokens.",
        )
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
    fig.update_layout(
        title=(
            f"Reranking funnels {n * n_candidates} embedding hits down to "
            f"{chosen.top_k} citations per question - {relevant}/{n} questions "
            f"({relevant / max(n, 1):.0%}) keep a relevant article"
        )
    )
    return apply_theme(
        add_takeaway(
            fig,
            f"{relevant}/{n} questions ({relevant / max(n, 1):.0%}) keep a relevant "
            "article after rerank.",
        )
    )


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
        title=(
            f"Five topics stay near-balanced ({len(articles)} articles total); "
            "the long article tail is capped at 12k chars"
        ),
        showlegend=False,
    )
    return apply_theme(
        add_takeaway(
            fig, "Five near-balanced topics; article lengths right-skewed, capped at 12k chars."
        )
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
        title="Verify-then-answer cuts unsupported claims from 60% to 47% of answers",
        xaxis_title="verdict",
        yaxis_title="questions",
    )
    return apply_theme(
        add_takeaway(fig, f"{counts['correct']}/{len(traces)} questions fully correct.")
    )


def latency_figure(latencies_s: list[float]) -> go.Figure:
    fig = go.Figure(data=[go.Histogram(x=latencies_s, nbinsx=20)])
    p50 = float(np.percentile(latencies_s, 50))
    p95 = float(np.percentile(latencies_s, 95))
    fig.update_layout(
        title=(
            f"Answers land at p50 {p50:.0f} s; the p95 {p95:.0f} s tail is one runaway tool loop"
        ),
        xaxis_title="latency (s)",
        yaxis_title="queries",
    )
    return apply_theme(fig)


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
    return apply_theme(fig)


# Architecture diagram lane colours (dark theme).
_LANE_COLORS = {
    "retrieval": "#2dd4bf",  # teal — CPU, unmetered
    "seam": "#a78bfa",  # violet — provider seam
    "agent": "#38bdf8",  # sky — metered: agent
    "verify": "#f472b6",  # pink — metered: verify + judge
    "answer": "#34d399",  # emerald — final artifact
}


def agent_pipeline_figure(config: RAGConfig, n_articles: int, chosen: RetrievalBest) -> go.Figure:
    """End-to-end architecture: question → retrieval → agent → verify → answer.

    Static diagram (no traces): boxes are layout shapes, arrows are annotations,
    all in ``x/y domain`` coordinates (0-1 fractions of the plot area), so it
    renders identically in kaleido PNG exports, the React showcase (plotly.js)
    and the HTML report. The provider seam (ADR-0004) and the hosted-metered
    phases are drawn as first-class lanes, not prose afterthoughts.
    """
    XREF, YREF = "x domain", "y domain"
    fig = go.Figure()
    fig.update_layout(
        xaxis={"visible": False},
        yaxis={"visible": False},
        margin={"t": 80, "l": 20, "r": 20, "b": 40},
        hovermode=False,
    )

    def box(
        x: float, y: float, w: float, h: float, label: str, color: str, *, size: int = 11
    ) -> None:
        fig.add_shape(
            type="rect",
            xref=XREF,
            yref=YREF,
            x0=x - w / 2,
            x1=x + w / 2,
            y0=y - h / 2,
            y1=y + h / 2,
            fillcolor="rgba(17, 28, 51, 0.9)",
            line={"color": color, "width": 1.6},
        )
        fig.add_annotation(
            x=x,
            y=y,
            xref=XREF,
            yref=YREF,
            text=label,
            showarrow=False,
            xanchor="center",
            yanchor="middle",
            font={"size": size, "color": "#e2e8f0"},
            align="center",
        )

    def arrow(x0: float, y0: float, x1: float, y1: float, color: str = "#94a3b8") -> None:
        fig.add_annotation(
            x=x1,
            y=y1,
            xref=XREF,
            yref=YREF,
            ax=x0,
            ay=y0,
            axref=XREF,
            ayref=YREF,
            showarrow=True,
            arrowhead=2,
            arrowsize=1.1,
            arrowwidth=1.4,
            arrowcolor=color,
        )

    def lane_header(x: float, y: float, text: str, color: str) -> None:
        fig.add_annotation(
            x=x,
            y=y,
            xref="paper",
            yref="paper",
            text=text,
            showarrow=False,
            xanchor="left",
            font={"size": 11, "color": color},
        )

    rerank_txt = "on" if chosen.rerank else "off"
    # --- Lane 1: retrieval (CPU, unmetered) ---------------------------------
    lane_header(0.02, 0.92, "RETRIEVAL · CPU-only · unmetered", _LANE_COLORS["retrieval"])
    y1 = 0.82
    box(0.075, y1, 0.115, 0.10, "User<br>question", _LANE_COLORS["retrieval"])
    box(0.26, y1, 0.15, 0.12, "Embed<br>MiniLM-L6-v2<br>(80 MB, CPU)", _LANE_COLORS["retrieval"])
    box(
        0.475,
        y1,
        0.185,
        0.12,
        f"FAISS IndexFlatIP<br>exact search - top {config.rerank_multiplier}x k<br>"
        f"({n_articles} articles)",
        _LANE_COLORS["retrieval"],
    )
    box(
        0.705,
        y1,
        0.185,
        0.12,
        f"Cross-encoder rerank<br>ms-marco MiniLM ({rerank_txt})<br>MRR@5 0.718→0.808",
        _LANE_COLORS["retrieval"],
        size=10,
    )
    box(0.915, y1, 0.135, 0.10, f"top-{chosen.top_k}<br>citations", _LANE_COLORS["retrieval"])
    arrow(0.135, y1, 0.183, y1)
    arrow(0.337, y1, 0.381, y1)
    arrow(0.569, y1, 0.616, y1)
    arrow(0.794, y1, 0.846, y1)

    # --- Provider seam (ADR-0004) -------------------------------------------
    # Narrow, left-aligned banner: the citations→agent arrow drops down the
    # right side and must not cross it.
    box(
        0.285,
        0.635,
        0.43,
        0.10,
        "LLM provider seam (ADR-0004) — spans the LLM lanes below:<br>"
        "env OpenAI-compatible endpoint (hosted kimi-for-coding, metered)<br>"
        "⇄ local Ollama qwen3.6 ($0 API) · one code path, no runtime mock",
        _LANE_COLORS["seam"],
        size=10,
    )

    # --- Lane 2: agent loop (metered: agent) --------------------------------
    lane_header(0.02, 0.55, "AGENT LOOP · metered phase: agent", _LANE_COLORS["agent"])
    y2 = 0.45
    box(
        0.115,
        y2,
        0.185,
        0.13,
        "Tools — the only corpus access:<br>search_documents /<br>read_excerpt",
        _LANE_COLORS["agent"],
    )
    box(
        0.41,
        y2,
        0.215,
        0.15,
        "Agent loop (pydantic-ai)<br>question + citations →<br>typed AnalysisResult<br>"
        "schema-invalid → loud failure<br>(≤2 output retries)",
        _LANE_COLORS["agent"],
        size=10,
    )
    box(
        0.70,
        y2,
        0.19,
        0.13,
        "Drafted AnalysisResult<br>summary + per-claim<br>citations + confidence",
        _LANE_COLORS["agent"],
    )
    arrow(0.915, 0.77, 0.47, 0.527, color=_LANE_COLORS["retrieval"])  # citations → agent
    arrow(0.26, y2, 0.308, y2, color=_LANE_COLORS["agent"])  # tools → agent
    arrow(0.308, y2 - 0.03, 0.26, y2 - 0.03, color=_LANE_COLORS["agent"])  # agent → tools
    arrow(0.512, y2, 0.604, y2, color=_LANE_COLORS["agent"])

    # --- Lane 3: verify loop (metered: verify + judge) -----------------------
    lane_header(0.02, 0.335, "VERIFY LOOP · metered phases: verify + judge", _LANE_COLORS["verify"])
    y3 = 0.24
    box(0.085, y3, 0.125, 0.09, "Claim<br>split", _LANE_COLORS["verify"])
    box(
        0.305,
        y3,
        0.185,
        0.11,
        "Entailment judge<br>vs full cited-chunk text<br>(keyword judge = CI floor)",
        _LANE_COLORS["verify"],
    )
    box(
        0.565,
        y3,
        0.195,
        0.11,
        f"Repair (≤{config.verify.max_repair_calls} calls) or<br>drop unsupported claims",
        _LANE_COLORS["verify"],
    )
    box(
        0.835,
        y3,
        0.175,
        0.11,
        f"Support floor {config.verify.min_support:.1f}<br>below → abstain",
        _LANE_COLORS["verify"],
    )
    arrow(0.70, y2 - 0.068, 0.085, y3 + 0.048, color=_LANE_COLORS["agent"])  # draft → split
    arrow(0.15, y3, 0.211, y3, color=_LANE_COLORS["verify"])
    arrow(0.40, y3, 0.466, y3, color=_LANE_COLORS["verify"])
    arrow(0.663, y3, 0.746, y3, color=_LANE_COLORS["verify"])

    # --- Final artifact ------------------------------------------------------
    y4 = 0.075
    box(
        0.835,
        y4,
        0.24,
        0.09,
        "Answer with per-claim citations<br>(or explicit refusal)",
        _LANE_COLORS["answer"],
    )
    arrow(0.835, y3 - 0.058, 0.835, y4 + 0.048, color=_LANE_COLORS["verify"])

    # --- Metered-phase legend -------------------------------------------------
    fig.add_annotation(
        x=0.02,
        y=0.145,
        xref="paper",
        yref="paper",
        text=(
            "Metered phases (hosted runs only): agent · verify · judge · ragas — "
            "per-phase calls/tokens/spend in the platform spend ledger, "
            "hard USD cap per run; local Ollama stays $0 API."
        ),
        showarrow=False,
        xanchor="left",
        font={"size": 11, "color": "#94a3b8"},
        align="left",
    )
    fig.update_layout(
        title=(
            "One pipeline, two seams: the provider swap (ADR-0004) and the "
            "verify-then-answer loop enforce grounding by construction"
        )
    )
    return apply_theme(fig, height=640)
