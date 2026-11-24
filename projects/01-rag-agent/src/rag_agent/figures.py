"""Plotly figure builders for the evaluation report.

Every figure is themed via ``portfolio_core.plotting`` and carries a
descriptive second title line (what is plotted, units, sample/scope) — the
conclusion lives in the story's ``figure_captions``, not in the chart.
Builders are pure: they take
measurements (from :mod:`rag_agent.reporting`) and return ``go.Figure`` objects;
writing to disk happens in :mod:`rag_agent.reporting`.
"""

from typing import Any

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
    lexical_scores: list[RetrievalScores] | None = None,
) -> go.Figure:
    """Chunk-size sweep: grouped bars with value labels + the lexical floor.

    Readability contract (wave 16, viewer report "chunk size 600 has no bars"):
    the x-axis is **categorical** — chunk sizes are a deliberate 2x grid
    (200/400/800), no 600 configuration exists anywhere in the sweep, and a
    continuous axis left a suggestive void between bars. Every bar carries its
    value label.

    Baseline contract (wave 19, viewer report "the random baseline is useless
    [plotted] — and the amber bottom label is unreadable"): the plotted
    baseline is the **lexical (word-match) floor**, the comparator a client
    would ask about before buying embeddings. The seeded-random floor stays a
    **metric, not a line** — it reads 0.02-0.03 at every size (near-zero by
    construction at 593 articles), so it is tabulated in the conclusions'
    exact-numbers table and named in the takeaway instead of squashing two
    flat dashed lines and their labels into the plot's bottom edge.

    Readability contract (wave 18, viewer report "star unreadable on the
    bars"): the chosen marker rides in a dedicated band above the bar labels
    (the y-range is padded to 1.1 for it), and the legend follows the house
    standard (right).
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
        # would ask about before buying embeddings (lexical → embeddings).
        lex_recall = [s.recall_at_5 for s in lexical_scores]
        lex_mrr = [s.mrr_at_5 for s in lexical_scores]
        fig.add_trace(
            go.Scatter(
                name="lexical recall@5",
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
                name="lexical mrr@5",
                x=labels,
                y=lex_mrr,
                mode="lines+markers+text",
                text=[f"{v:.3f}" for v in lex_mrr],
                textposition="bottom center",
                line={"dash": "dot", "color": "#34d399", "width": 2},
            )
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
        # Padded to 1.1 so the chosen marker rides in a clear band above the
        # bar labels (wave 18: at paper-y 0.97 it sat on the bars).
        yaxis={"title": "score", "range": [0, 1.1]},
    )
    fig.add_annotation(
        text=f"★ chosen: {chosen_size}-token chunks",
        xref="x",
        x=labels.index(str(chosen_size)),
        yref="y",
        y=1.03,
        showarrow=False,
        font={"size": 12, "color": "#2dd4bf"},
        xanchor="center",
    )
    fig = _finish_themed(
        fig,
        takeaway=(
            f"recall@5, recall@10, MRR@5 — 65 golden questions; lexical "
            f"(word-match) floor dashed; seeded random floor 0.02-0.03 "
            f"tabulated in Exact numbers · categorical axis: "
            f"{' / '.join(labels)} only, no 600-token configuration exists"
        ),
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
    """Question-level top-k outcomes; candidate volumes belong in the caption."""
    del config  # the plotted units are questions, not retrieved passages
    size_data = topk[chosen.chunk_size]
    n = len(questions)
    hits = sum(1 for r in size_data["ranks"] if r is not None and r <= chosen.top_k)
    counts = [hits, n - hits]
    fig = go.Figure(
        go.Bar(
            x=["hit", "miss"],
            y=counts,
            text=[f"{count} ({count / n:.1%})" for count in counts],
            textposition="outside",
            marker_color=["#2dd4bf", "#f472b6"],
            hovertemplate="%{x}: %{y} questions<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"Questions with a relevant article in the reranked top-{chosen.top_k}",
        xaxis_title="top-k outcome",
        yaxis={"title": f"questions (n = {n})", "range": [0, n * 1.15], "dtick": 10},
    )
    return _finish_themed(
        fig,
        takeaway=(
            f"{n} tuning questions — {hits} hits and {n - hits} misses; one outcome per question"
        ),
        showlegend=False,
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


def taxonomy_figure(traces: list[QuestionTrace], *, scope: str = "hosted") -> go.Figure:
    """Failure-taxonomy breakdown: counts per deterministic verdict class.

    ``scope`` names the run in the takeaway line (``hosted`` for the
    provider-backed passes, ``final_v3 sealed pass`` for the committed
    final run).
    """
    order = [
        "correct",
        "retrieval-miss",
        "unsupported-claim",
        "format-failure",
        "empty-answer",
        "budget-terminated",
    ]
    counts = {label: 0 for label in order}
    for trace in traces:
        counts[classify_question(trace)] += 1
    fig = go.Figure(
        data=[
            go.Bar(
                x=order,
                y=[counts[label] for label in order],
                text=[counts[label] for label in order],
                textposition="outside",
                textfont={"size": 12},
                marker_color=[
                    "#34d399",
                    "#fbbf24",
                    "#f472b6",
                    "#a78bfa",
                    "#38bdf8",
                    "#94a3b8",
                ],
            )
        ]
    )
    fig.update_layout(
        title=f"Answer verdicts by category (n = {len(traces)})",
        xaxis_title="verdict",
        yaxis={"title": "questions", "range": [0, max(counts.values()) * 1.2]},
    )
    return _finish_themed(
        fig,
        takeaway=(f"counts per deterministic verdict class — {scope} {len(traces)}-question run"),
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


def fusion_arm_figure(block: dict[str, Any]) -> go.Figure:
    """Dense / BM25 / RRF(k=60) retrieval arms on the tuning and sealed sets.

    One panel per split, one bar group per metric — the three-way comparison
    the technical audit asked for (pass 4), computed retrieval-only so the
    arms isolate ranking quality from generation.
    """
    import plotly.express as px

    rows = []
    for split in ("tuning", "sealed"):
        for arm, scores in block[split].items():
            for metric in ("recall_at_5", "recall_at_10", "mrr_at_5", "ndcg_at_10"):
                rows.append(
                    {
                        "split": split,
                        "arm": arm,
                        "metric": metric.replace("_", "@", 1).replace("_", " "),
                        "value": scores[metric],
                    }
                )
    fig = px.bar(
        rows,
        x="metric",
        y="value",
        color="arm",
        barmode="group",
        facet_col="split",
        title="Retrieval arms: dense vs BM25 vs RRF (rerank off, no LLM)",
        labels={"value": "score", "metric": "metric", "arm": "arm"},
        category_orders={"arm": ["dense", "bm25", "rrf"]},
    )
    fig.update_yaxes(range=[0.0, 1.0])
    rrf_r5 = block["sealed"].get("rrf", {}).get("recall_at_5", 0.0)
    dense_r5 = block["sealed"].get("dense", {}).get("recall_at_5", 0.0)
    delta = rrf_r5 - dense_r5
    add_takeaway(
        fig,
        f"sealed set: RRF recall@5 {rrf_r5:.3f} vs dense {dense_r5:.3f} "
        f"({'+' if delta >= 0 else ''}{delta:.3f}) — fusion compared out of the box "
        "(k=60, no tuning); generation path unchanged",
    )
    return apply_theme(fig)


def retrieval_ladder_figure(rows: list[dict[str, Any]]) -> go.Figure:
    """Retrieval tournament ladder: R0-S3 arms across frozen splits.

    One group per split, one bar per arm. Left panel: recall@5 with the
    committed Wilson 95% whiskers; right panel: all_articles@5 (share of
    relevant articles with every chunk in the top 5). Cells that were never
    measured (S1/S2 on the consumed final_v3 set; all_articles under
    chunk-exact gold) are absent on purpose: the ladder plots committed
    measurements only.
    """
    from plotly.subplots import make_subplots

    arms = ["R0", "S1", "S2", "S3"]
    arm_names = {
        "R0": "R0 as-shipped",
        "S1": "S1 structure",
        "S2": "S2 +RRF",
        "S3": "S3 +cap (promoted)",
    }
    # Fixed colour per arm, identical in both panels: the promoted arm must be
    # recognisable at a glance, and missing cells must never shift the palette
    # (a per-panel colourway reassigns colours when a trace is absent).
    arm_colors = {
        "R0": "#94a3b8",  # slate — the as-shipped baseline
        "S1": "#38bdf8",  # sky
        "S2": "#a78bfa",  # violet
        "S3": "#2dd4bf",  # teal — the promoted arm
    }
    splits: list[str] = []
    for row in rows:
        if row["split"] not in splits:
            splits.append(row["split"])
    split_labels = {
        s: f"{s}<br>(n={next(r['n'] for r in rows if r['split'] == s)})" for s in splits
    }

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("recall@5 (Wilson 95% whiskers)", "all_articles@5"),
        horizontal_spacing=0.12,
    )
    for arm in arms:
        arm_rows = [r for r in rows if r["arm"] == arm]
        by_split = {r["split"]: r for r in arm_rows}
        fig.add_trace(
            go.Bar(
                name=arm_names[arm],
                x=[split_labels[s] for s in splits if s in by_split],
                y=[by_split[s]["recall_at_5"] for s in splits if s in by_split],
                text=[f"{by_split[s]['recall_at_5']:.3f}" for s in splits if s in by_split],
                textposition="outside",
                marker_color=arm_colors[arm],
                textfont={"size": 11},
                error_y={
                    "type": "data",
                    "array": [
                        by_split[s]["wilson95"][1] - by_split[s]["recall_at_5"]
                        for s in splits
                        if s in by_split
                    ],
                    "arrayminus": [
                        by_split[s]["recall_at_5"] - by_split[s]["wilson95"][0]
                        for s in splits
                        if s in by_split
                    ],
                    "color": "#94a3b8",
                    "thickness": 1.5,
                    "width": 5,
                },
            ),
            row=1,
            col=1,
        )
        aa_rows = [r for r in arm_rows if r.get("all_articles_at_5") is not None]
        if aa_rows:
            aa_by_split = {r["split"]: r for r in aa_rows}
            fig.add_trace(
                go.Bar(
                    name=arm_names[arm],
                    x=[split_labels[s] for s in splits if s in aa_by_split],
                    y=[aa_by_split[s]["all_articles_at_5"] for s in splits if s in aa_by_split],
                    text=[
                        f"{aa_by_split[s]['all_articles_at_5']:.3f}"
                        for s in splits
                        if s in aa_by_split
                    ],
                    textposition="outside",
                    marker_color=arm_colors[arm],
                    textfont={"size": 11},
                    showlegend=False,
                ),
                row=1,
                col=2,
            )
    fig.update_layout(
        barmode="group",
        title="Retrieval tournament ladder: R0 to S3 across frozen splits",
        xaxis={"type": "category", "title": "frozen split (answerable n)"},
        xaxis2={"type": "category", "title": "frozen split (answerable n)"},
        yaxis={"title": "recall@5", "range": [0, 1.15]},
        yaxis2={"title": "all_articles@5", "range": [0, 1.15]},
    )
    return _finish_themed(
        fig,
        takeaway=(
            "retrieval-only, no LLM calls; final_v3 measured for R0 and S3 only "
            "(set consumed). recall@5 on final_v3 = chunk-exact hit rate; on the "
            "development splits = article-level hit rate. Same fixed colour per "
            "arm in both panels. Sources: reports/retrieval_baseline + retrieval_sweeps"
        ),
    )


def final_outcome_figure(summary: dict[str, Any], slices: dict[str, tuple[int, int]]) -> go.Figure:
    """Final-pass outcome: answer/abstain confusion + per-slice correct shares.

    ``summary`` is the committed ``f1_summary.json`` (tp/fp/tn/fn); ``slices``
    maps slice name -> (correct, total) computed from the committed traces.
    """
    from plotly.subplots import make_subplots

    tp, fp, tn, fn = (summary[k] for k in ("tp", "fp", "tn", "fn"))
    n = tp + fp + tn + fn
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            f"answer vs abstain outcome (n={n})",
            "correct per slice",
        ),
        horizontal_spacing=0.14,
    )
    outcome_labels = [
        "TP<br>answered",
        "FP<br>budget stop<br>(no answer)",
        "TN<br>abstained",
        "FN<br>abstained",
    ]
    fig.add_trace(
        go.Bar(
            x=outcome_labels,
            y=[tp, fp, tn, fn],
            text=[tp, fp, tn, fn],
            textposition="outside",
            marker_color=["#2dd4bf", "#f472b6", "#34d399", "#fbbf24"],
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    slice_names = list(slices)
    fig.add_trace(
        go.Bar(
            name="correct",
            x=slice_names,
            y=[slices[s][0] for s in slice_names],
            text=[slices[s][0] for s in slice_names],
            textposition="outside",
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Bar(
            name="total",
            x=slice_names,
            y=[slices[s][1] for s in slice_names],
            text=[f"{slices[s][0]}/{slices[s][1]}" for s in slice_names],
            textposition="outside",
        ),
        row=1,
        col=2,
    )
    fig.update_layout(
        barmode="group",
        title="Final pass (final_v3): outcome counts and slice correctness",
        yaxis={"title": f"questions (n = {n})", "range": [0, n * 0.72]},
        yaxis2={"title": "questions", "range": [0, 80]},
    )
    return _finish_themed(
        fig,
        takeaway=(
            f"final_v3 run, {n} questions — F1 {summary['f1']:.4f} "
            f"(precision {summary['precision']:.4f}, recall {summary['recall']:.4f}); "
            "all 4 FPs are unanswerable rows that hit the tool budget before "
            "refusing, not wrong answers; "
            "slices: single-hop 60/68, multi-hop 20/24, unanswerable 24/28 correct. "
            "Source: reports/final_v3_e2e/f1_summary.json + question_traces_heldout.json"
        ),
    )


def verify_funnel_figure(verify: dict[str, Any]) -> go.Figure:
    """Claim verify-loop accounting for the final pass, as stage bars.

    Stages follow the loop's real flow: drafts lose mechanically broken rows
    before judging; supported claims are accepted, some originals dropped,
    some repaired back in (which is why accepted exceeds supported). A funnel
    chart would force a monotone shape the loop does not have.
    """
    stages = [
        ("drafted", verify["n_drafted"], "#38bdf8"),
        ("mechanical fail", verify["n_mechanical_fail"], "#fbbf24"),
        ("judged", verify["n_judged"], "#818cf8"),
        ("judge-supported", verify["n_judge_supported"], "#2dd4bf"),
        ("kept (orig+repaired)", verify["n_surviving"], "#34d399"),
        ("dropped", verify["n_dropped"], "#f472b6"),
    ]
    retention = verify["n_surviving"] / verify["n_drafted"]
    fig = go.Figure(
        go.Bar(
            x=[s[0] for s in stages],
            y=[s[1] for s in stages],
            text=[
                (
                    f"{s[1]} ({retention:.1%} of drafted kept)"
                    if s[0].startswith("kept")
                    else f"{s[1]}"
                )
                for s in stages
            ],
            textposition="outside",
            marker_color=[s[2] for s in stages],
            hovertemplate="%{x}: %{y} claims<extra></extra>",
        )
    )
    fig.update_layout(
        title="Claim verify loop: stage accounting for the final pass",
        xaxis_title="stage",
        yaxis={
            "title": f"claims (drafted n = {verify['n_drafted']})",
            "range": [0, verify["n_drafted"] * 1.18],
        },
    )
    return _finish_themed(
        fig,
        takeaway=(
            f"share of drafted claims kept: {retention:.1%} "
            f"({verify['n_surviving']}/{verify['n_drafted']}) — accepted = "
            f"{verify['n_accepted_original']} original + "
            f"{verify['n_accepted_repaired']} repaired; dropped = "
            f"{verify['n_dropped_original']} original + {verify['n_dropped_repaired']} "
            f"repaired after the repair rail; mean support "
            f"{verify['mean_support_fraction']:.4f}; repair rail ≤2 calls. "
            "Source: final_v3_e2e/metrics.json detail.final_v3.verify"
        ),
        showlegend=False,
    )
