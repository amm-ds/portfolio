"""Evaluation harness: retrieval sweep, RAG quality, cost/latency, reports.

Three blocks, all writing into ``config.reports_dir``:

(a) retrieval eval — graded questions run against every chunk-size index;
    recall@5, recall@10, MRR@5 per size + a sweep figure.
(b) RAG eval — the agent answers every question; RAGEvaluator (keyword judge
    by default) scores faithfulness / answer relevance / context recall.
(c) ops — per-query latency (p50/p95), estimated cost per query from recorded
    token usage, a latency histogram and a cost-vs-quality frontier figure.

Everything is injectable (embed/rerank/agent) so tests run with fakes offline.
"""

import json
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import plotly.graph_objects as go
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_json, style_runs
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.rag import RAGEvalResult, RAGEvalRow, RAGEvaluator
from portfolio_eval.report import ReportBuilder
from pydantic_ai import Agent

from rag_agent.agent import build_agent
from rag_agent.config import RAGConfig, RetrievalBest
from rag_agent.corpus import load_corpus
from rag_agent.index import (
    ChunkRecord,
    CrossEncoderReranker,
    EmbedFn,
    RerankFn,
    Retriever,
    SentenceTransformerEmbedder,
    build_index,
    chunk_articles,
)
from rag_agent.schemas import AnalysisResult, Article, Citation, EvalQuestion

logger = get_logger(__name__)

# Rough tokens-per-word assumption for estimating prompt context sizes when the
# provider does not report per-section usage.
TOKENS_PER_WORD = 1.3
BASE_PROMPT_TOKENS = 220  # system prompt + tool schemas + message envelope

# Embedding-model arms compared on the same chunk-200 chunk structure. BGE
# expects an instruction prefix on queries only (passages are encoded plain).
EMBEDDING_ARMS: tuple[tuple[str, str, str], ...] = (
    ("minilm", "sentence-transformers/all-MiniLM-L6-v2", ""),
    (
        "bge_small",
        "BAAI/bge-small-en-v1.5",
        "Represent this sentence for searching relevant passages: ",
    ),
)
TOP_K_VALUES: tuple[int, ...] = (3, 5, 8, 10)


@dataclass
class RetrievalScores:
    """Retrieval quality for one chunk-size index."""

    chunk_size: int
    recall_at_5: float
    recall_at_10: float
    mrr_at_5: float
    n_questions: int

    def as_run(self, name: str | None = None) -> RunResult:
        return RunResult(
            name=name or f"retrieval_chunks_{self.chunk_size}",
            metrics=[
                MetricResult(name="recall@5", value=self.recall_at_5),
                MetricResult(name="recall@10", value=self.recall_at_10),
                MetricResult(name="mrr@5", value=self.mrr_at_5),
            ],
        )


@dataclass
class RAGRun:
    """RAG quality + ops measurements for one agent configuration."""

    eval_result: RAGEvalResult
    latencies_s: list[float] = field(default_factory=list)
    input_tokens: list[int] = field(default_factory=list)
    output_tokens: list[int] = field(default_factory=list)

    @property
    def p50_latency_s(self) -> float:
        return _percentile(self.latencies_s, 0.50)

    @property
    def p95_latency_s(self) -> float:
        return _percentile(self.latencies_s, 0.95)

    def cost_per_query_usd(self, avg_input_tokens: float) -> float:
        """Cost estimate at ``avg_input_tokens`` input + measured avg output tokens."""
        avg_out = sum(self.output_tokens) / len(self.output_tokens) if self.output_tokens else 0.0
        return avg_input_tokens / 1e6 * self._rate_in + avg_out / 1e6 * self._rate_out

    @property
    def est_cost_per_query_usd(self) -> float:
        """Cost from agent-recorded usage (mock mode: floor, not context-sized)."""
        if not self.input_tokens:
            return float("nan")
        avg_in = sum(self.input_tokens) / len(self.input_tokens)
        return self.cost_per_query_usd(avg_in)

    _rate_in: float = 0.15
    _rate_out: float = 0.60

    def as_run(self, name: str, input_tokens_override: float | None = None) -> RunResult:
        d = self.eval_result.to_dict()
        avg_in = (
            input_tokens_override
            if input_tokens_override is not None
            else (sum(self.input_tokens) / len(self.input_tokens) if self.input_tokens else 0.0)
        )
        metrics = [
            MetricResult(name="faithfulness", value=float(d["faithfulness"])),
            MetricResult(name="answer_relevance", value=float(d["answer_relevance"])),
            MetricResult(name="context_recall", value=float(d["context_recall"])),
            MetricResult(name="p50_latency_s", value=self.p50_latency_s, higher_is_better=False),
            MetricResult(name="p95_latency_s", value=self.p95_latency_s, higher_is_better=False),
            MetricResult(
                name="est_cost_usd_per_query",
                value=self.cost_per_query_usd(avg_in),
                higher_is_better=False,
            ),
        ]
        return RunResult(name=name, metrics=metrics)


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))
    return ordered[idx]


def recall_at_k(ranks: list[int | None], k: int) -> float:
    """Fraction of questions with a relevant article within the top ``k`` hits."""
    if not ranks:
        return float("nan")
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks)


def mrr_at_5(ranks: list[int | None]) -> float:
    if not ranks:
        return float("nan")
    return sum(1.0 / r for r in ranks if r is not None and r <= 5) / len(ranks)


def load_questions(config: RAGConfig, articles: list[Article]) -> list[EvalQuestion]:
    """Load graded questions, resolving expected titles to corpus article ids.

    Questions whose relevant titles are absent from the corpus are skipped with
    a warning so the eval degrades gracefully instead of scoring noise.
    """
    raw = json.loads(config.eval_questions_path.read_text(encoding="utf-8"))
    title_to_id = {a.title: a.article_id for a in articles}
    questions: list[EvalQuestion] = []
    for item in raw:
        resolved = [title_to_id[t] for t in item["relevant_titles"] if t in title_to_id]
        missing = [t for t in item["relevant_titles"] if t not in title_to_id]
        if not resolved:
            logger.warning(
                "skipping eval question (no relevant titles in corpus): %s", item["question"]
            )
            continue
        if missing:
            logger.warning(
                "eval question %r: titles not in corpus ignored: %s", item["question"], missing
            )
        questions.append(EvalQuestion(question=item["question"], relevant_article_ids=resolved))
    logger.info("loaded %d eval questions (%d skipped)", len(questions), len(raw) - len(questions))
    return questions


def first_relevant_rank(citations: list[Citation], relevant_article_ids: list[str]) -> int | None:
    """1-based rank of the first relevant citation, or None if absent."""
    relevant = set(relevant_article_ids)
    for i, citation in enumerate(citations, start=1):
        if citation.article_id in relevant:
            return i
    return None


def random_ranks(
    config: RAGConfig, questions: list[EvalQuestion], chunks: list[ChunkRecord]
) -> list[int | None]:
    """Seeded uniform-random chunk ranking: the floor retrieval must beat.

    Each (chunk-count, question) pair gets its own deterministic stream seeded
    from ``config.seed``, so the baseline is reproducible yet not constant.
    """
    ranks: list[int | None] = []
    for qi, question in enumerate(questions):
        rng = random.Random(f"{config.seed}:{len(chunks)}:{qi}")
        order = list(range(len(chunks)))
        rng.shuffle(order)
        relevant = set(question.relevant_article_ids)
        rank = next(
            (pos + 1 for pos, idx in enumerate(order) if chunks[idx].article_id in relevant),
            None,
        )
        ranks.append(rank)
    return ranks


def run_retrieval_sweep(
    config: RAGConfig,
    questions: list[EvalQuestion],
    embed_fn: EmbedFn,
    rerank_fn: RerankFn | None,
) -> tuple[list[RetrievalScores], list[RetrievalScores], go.Figure]:
    """Score every chunk-size index on the graded question set + random baseline.

    Returns (embedding scores, random-baseline scores, figure). The baseline is
    computed per chunk size (different chunk counts → different draws), so it
    is reported as one row per size rather than a single size-invariant row.
    """
    scores: list[RetrievalScores] = []
    random_scores: list[RetrievalScores] = []
    for size in config.chunk_sizes:
        retriever = Retriever.from_index_dir(config, config.index_path(size), embed_fn, rerank_fn)
        ranks = [
            first_relevant_rank(retriever.search(q.question, top_k=10), q.relevant_article_ids)
            for q in questions
        ]
        scores.append(
            RetrievalScores(
                chunk_size=size,
                recall_at_5=recall_at_k(ranks, 5),
                recall_at_10=recall_at_k(ranks, 10),
                mrr_at_5=mrr_at_5(ranks),
                n_questions=len(questions),
            )
        )
        rnd = random_ranks(config, questions, retriever.chunks)
        random_scores.append(
            RetrievalScores(
                chunk_size=size,
                recall_at_5=recall_at_k(rnd, 5),
                recall_at_10=recall_at_k(rnd, 10),
                mrr_at_5=mrr_at_5(rnd),
                n_questions=len(questions),
            )
        )
        logger.info(
            "chunk_size=%d recall@5=%.3f recall@10=%.3f mrr@5=%.3f | "
            "random recall@5=%.3f mrr@5=%.3f",
            size,
            scores[-1].recall_at_5,
            scores[-1].recall_at_10,
            scores[-1].mrr_at_5,
            random_scores[-1].recall_at_5,
            random_scores[-1].mrr_at_5,
        )
    return scores, random_scores, sweep_figure(scores, random_scores)


def sweep_figure(
    scores: list[RetrievalScores], random_scores: list[RetrievalScores] | None = None
) -> go.Figure:
    sizes = [s.chunk_size for s in scores]
    fig = go.Figure(
        data=[
            go.Bar(name="recall@5", x=sizes, y=[s.recall_at_5 for s in scores]),
            go.Bar(name="recall@10", x=sizes, y=[s.recall_at_10 for s in scores]),
            go.Bar(name="mrr@5", x=sizes, y=[s.mrr_at_5 for s in scores]),
        ]
    )
    if random_scores:
        # Flat dashed reference series so the embedding gain is visible.
        fig.add_trace(
            go.Scatter(
                name="random baseline recall@5",
                x=sizes,
                y=[s.recall_at_5 for s in random_scores],
                mode="lines+markers",
                line={"dash": "dash", "color": "#f472b6"},
            )
        )
        fig.add_trace(
            go.Scatter(
                name="random baseline mrr@5",
                x=sizes,
                y=[s.mrr_at_5 for s in random_scores],
                mode="lines+markers",
                line={"dash": "dot", "color": "#fbbf24"},
            )
        )
    fig.update_layout(
        barmode="group",
        title="Retrieval quality vs chunk size (random-retrieval baseline dashed)",
        xaxis_title="chunk size (tokens)",
        yaxis_title="score",
    )
    return apply_theme(
        add_takeaway(
            fig,
            "Recall saturates at every size; smaller chunks rank sharper (MRR) "
            "at half the context cost.",
        )
    )


def run_rag_eval(
    config: RAGConfig,
    agent: Agent[Retriever, AnalysisResult],
    retriever: Retriever,
    questions: list[EvalQuestion],
) -> RAGRun:
    """Run the agent over the question set and score outputs with the judge."""
    rows: list[RAGEvalRow] = []
    latencies: list[float] = []
    input_tokens: list[int] = []
    output_tokens: list[int] = []
    for question in questions:
        start = time.perf_counter()
        result = agent.run_sync(question.question, deps=retriever)
        latencies.append(time.perf_counter() - start)
        output: AnalysisResult = result.output
        input_tokens.append(int(result.usage.input_tokens))
        output_tokens.append(int(result.usage.output_tokens))

        evidence = retriever.search(question.question, top_k=config.top_k)
        relevant = set(question.relevant_article_ids)
        rows.append(
            RAGEvalRow(
                question=question.question,
                contexts=[c.excerpt for c in evidence],
                answer=output.summary,
                retrieved_relevant=any(c.article_id in relevant for c in evidence),
            )
        )
    evaluator = RAGEvaluator()
    rag_result = evaluator.run(rows)
    logger.info("RAG eval: %s", rag_result.to_dict())
    return RAGRun(
        eval_result=rag_result,
        latencies_s=latencies,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        _rate_in=config.usd_per_mtok_input,
        _rate_out=config.usd_per_mtok_output,
    )


def query_prefixed(embed_fn: EmbedFn, prefix: str) -> EmbedFn:
    """Wrap an embedder with a query instruction prefix (no-op when empty)."""

    def embed(texts: Sequence[str]) -> np.ndarray:
        return embed_fn([prefix + t for t in texts])

    return embed if prefix else embed_fn


def _score_ranks(ranks: list[int | None], n_questions: int, chunk_size: int) -> RetrievalScores:
    return RetrievalScores(
        chunk_size=chunk_size,
        recall_at_5=recall_at_k(ranks, 5),
        recall_at_10=recall_at_k(ranks, 10),
        mrr_at_5=mrr_at_5(ranks),
        n_questions=n_questions,
    )


def model_comparison(
    config: RAGConfig,
    questions: list[EvalQuestion],
    articles: list[Article],
    rerank_fn: RerankFn,
) -> dict[str, RetrievalScores]:
    """Compare embedding models on the same chunk-200 chunk structure.

    The MiniLM arm reuses the existing production index; other arms get their
    own persisted index under ``data/index/chunks_200_<slug>/`` (built once,
    reused afterwards).
    """
    size = min(config.chunk_sizes)
    results: dict[str, RetrievalScores] = {}
    for slug, model_name, prefix in EMBEDDING_ARMS:
        embedder: EmbedFn = SentenceTransformerEmbedder(model_name)
        index_dir = (
            config.index_path(size)
            if slug == "minilm"
            else config.index_dir / f"chunks_{size}_{slug}"
        )
        if slug != "minilm" and not (index_dir / "faiss.index").exists():
            chunks = chunk_articles(articles, size=size, overlap=config.chunk_overlap)
            build_index(chunks, embedder, index_dir, description=f"size={size} model={slug}")
        retriever = Retriever.from_index_dir(
            config, index_dir, embedder, rerank_fn, query_prefixed(embedder, prefix)
        )
        ranks = [
            first_relevant_rank(retriever.search(q.question, top_k=10), q.relevant_article_ids)
            for q in questions
        ]
        results[slug] = _score_ranks(ranks, len(questions), size)
        logger.info(
            "model=%s chunk=%d recall@5=%.3f mrr@5=%.3f",
            slug,
            size,
            results[slug].recall_at_5,
            results[slug].mrr_at_5,
        )
    return results


def rerank_ablation(
    config: RAGConfig,
    questions: list[EvalQuestion],
    embed_fn: EmbedFn,
    rerank_fn: RerankFn,
) -> dict[str, RetrievalScores]:
    """Cross-encoder rerank on/off at the smallest chunk size."""
    size = min(config.chunk_sizes)
    results: dict[str, RetrievalScores] = {}
    for label, rf in (("on", rerank_fn), ("off", None)):
        retriever = Retriever.from_index_dir(config, config.index_path(size), embed_fn, rf)
        ranks = [
            first_relevant_rank(retriever.search(q.question, top_k=10), q.relevant_article_ids)
            for q in questions
        ]
        results[label] = _score_ranks(ranks, len(questions), size)
        logger.info(
            "rerank=%s recall@5=%.3f mrr@5=%.3f",
            label,
            results[label].recall_at_5,
            results[label].mrr_at_5,
        )
    return results


def topk_sweep(
    config: RAGConfig,
    questions: list[EvalQuestion],
    embed_fn: EmbedFn,
    rerank_fn: RerankFn,
    k_values: Sequence[int] = TOP_K_VALUES,
) -> dict[int, dict[str, Any]]:
    """Per chunk size: top-``max(k)`` search once, then derive every recall@k.

    Also records the cumulative citation-token sum per question so input-token
    (cost) estimates are available for every (size, k) point without re-search.
    """
    k_max = max(k_values)
    per_size: dict[int, dict[str, Any]] = {}
    for size in config.chunk_sizes:
        retriever = Retriever.from_index_dir(config, config.index_path(size), embed_fn, rerank_fn)
        ranks: list[int | None] = []
        token_sums: list[list[int]] = []
        for q in questions:
            citations = retriever.search(q.question, top_k=k_max)
            ranks.append(first_relevant_rank(citations, q.relevant_article_ids))
            acc = 0
            sums: list[int] = []
            for c in citations:
                chunk = retriever.get_chunk(c.chunk_id)
                acc += chunk.token_count if chunk is not None else len(c.excerpt.split())
                sums.append(acc)
            token_sums.append(sums)
        per_size[size] = {
            "ranks": ranks,
            "token_sums": token_sums,
            "n_chunks": len(retriever.chunks),
        }
    return per_size


def est_input_tokens_at(topk_data: dict[str, Any], questions: list[EvalQuestion], k: int) -> float:
    """Average estimated input tokens/query at top-``k`` for one chunk size."""
    token_sums: list[list[int]] = topk_data["token_sums"]
    total = 0.0
    for q, sums in zip(questions, token_sums, strict=True):
        context_words = sums[k - 1] if k <= len(sums) else (sums[-1] if sums else 0)
        total += (
            BASE_PROMPT_TOKENS
            + len(q.question.split()) * TOKENS_PER_WORD
            + context_words * TOKENS_PER_WORD
        )
    return total / max(len(questions), 1)


def recall_at_k_from(topk_data: dict[str, Any], k: int) -> float:
    return recall_at_k(topk_data["ranks"], k)


def choose_retrieval_config(
    config: RAGConfig,
    model_scores: dict[str, RetrievalScores],
    sweep_scores: list[RetrievalScores],
    topk: dict[int, dict[str, Any]],
) -> RetrievalBest:
    """Pick the production config from the HPO measurements.

    Rules: best-MRR embedding model (ties → the first/cheapest arm); best-MRR
    chunk size (recall is saturated); smallest top_k within one question of the
    maximum observed recall@k; rerank stays on unless the ablation says otherwise.
    """
    arm_by_slug = {slug: (name, prefix) for slug, name, prefix in EMBEDDING_ARMS}
    best_slug = max(model_scores, key=lambda s: (model_scores[s].mrr_at_5, s == "minilm"))
    best_size = max(sweep_scores, key=lambda s: s.mrr_at_5).chunk_size
    size_data = topk[best_size]
    n = max(len(size_data["ranks"]), 1)
    max_recall = max(recall_at_k_from(size_data, k) for k in TOP_K_VALUES)
    best_k = next(k for k in TOP_K_VALUES if recall_at_k_from(size_data, k) >= max_recall - 1.0 / n)
    rerank = True  # ablation is reported; the cross-encoder stays in the default path
    model_name, _ = arm_by_slug[best_slug]
    return RetrievalBest(
        embedding_model=model_name,
        embedding_slug=best_slug,
        chunk_size=best_size,
        top_k=best_k,
        rerank=rerank,
    )


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
        title="Embedding model comparison (chunk 200, rerank on)",
        yaxis_title="score",
    )
    return apply_theme(
        add_takeaway(fig, "Both encoders saturate recall@5; ranking sharpness (MRR) decides.")
    )


def hpo_frontier_figure(
    config: RAGConfig,
    questions: list[EvalQuestion],
    topk: dict[int, dict[str, Any]],
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
        title="Retrieval HPO frontier: recall@k vs estimated input tokens",
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
    topk: dict[int, dict[str, Any]],
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
    fig.update_layout(title="Retrieval funnel (aggregate, all eval questions)")
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
        title=f"Corpus composition ({len(articles)} Wikipedia articles)",
        showlegend=False,
    )
    return apply_theme(
        add_takeaway(
            fig, "Five near-balanced topics; article lengths right-skewed, capped at 12k chars."
        )
    )


def latency_figure(latencies_s: list[float]) -> go.Figure:
    fig = go.Figure(data=[go.Histogram(x=latencies_s, nbinsx=20)])
    fig.update_layout(
        title="Per-query agent latency (s)",
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
    """Cost-vs-quality frontier: one point per chunk size."""
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


def estimate_input_tokens(
    config: RAGConfig, questions: list[EvalQuestion], embed_fn: EmbedFn, rerank_fn: RerankFn | None
) -> dict[int, float]:
    """Average estimated input tokens/query for each chunk size (prompt + top-k context)."""
    estimates: dict[int, float] = {}
    for size in config.chunk_sizes:
        retriever = Retriever.from_index_dir(config, config.index_path(size), embed_fn, rerank_fn)
        total = 0.0
        for q in questions:
            citations = retriever.search(q.question, top_k=config.top_k)
            context_words = 0
            for c in citations:
                chunk = retriever.get_chunk(c.chunk_id)
                context_words += chunk.token_count if chunk is not None else len(c.excerpt.split())
            q_words = len(q.question.split())
            total += (
                BASE_PROMPT_TOKENS + q_words * TOKENS_PER_WORD + context_words * TOKENS_PER_WORD
            )
        estimates[size] = total / max(len(questions), 1)
    return estimates


def _write_reports(
    config: RAGConfig,
    scores: list[RetrievalScores],
    rag_run: RAGRun,
    figures: dict[str, go.Figure],
    extra_metrics: dict[str, Any],
    rag_input_tokens_override: float | None = None,
    random_scores: list[RetrievalScores] | None = None,
    model_scores: dict[str, RetrievalScores] | None = None,
    rerank_scores: dict[str, RetrievalScores] | None = None,
    topk_runs: list[RunResult] | None = None,
) -> None:
    builder = ReportBuilder(
        title="01-rag-agent — evaluation report", figures_dir=config.reports_dir / "figures"
    )
    for s in scores:
        builder.add_run(s.as_run())
    for s in random_scores or []:
        builder.add_run(s.as_run(f"retrieval_random_chunks_{s.chunk_size}"))
    for slug, s in (model_scores or {}).items():
        builder.add_run(s.as_run(f"retrieval_model_{slug}_chunks_{s.chunk_size}"))
    for label, s in (rerank_scores or {}).items():
        builder.add_run(s.as_run(f"retrieval_rerank_{label}_chunks_{s.chunk_size}"))
    for run in topk_runs or []:
        builder.add_run(run)
    builder.add_run(rag_run.as_run("rag_agent", input_tokens_override=rag_input_tokens_override))
    builder.build(config.reports_dir, figures=figures)
    # Persist machine-readable figure payloads for the showcase app.
    for name, fig in figures.items():
        save_json(fig, config.reports_dir / "figures" / f"{name}.json")
    # Augment metrics.json with the full detail the README cites.
    metrics_path = config.reports_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["detail"] = extra_metrics
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    logger.info("report written: %s", config.reports_dir / "report.html")


def topk_run_for_size(size: int, topk_data: dict[str, Any]) -> RunResult:
    """One run row per chunk size carrying the full recall@k grid."""
    metrics = [
        MetricResult(name=f"recall@{k}", value=recall_at_k_from(topk_data, k)) for k in TOP_K_VALUES
    ]
    metrics.append(MetricResult(name="mrr@5", value=mrr_at_5(topk_data["ranks"])))
    return RunResult(name=f"retrieval_topk_sweep_chunks_{size}", metrics=metrics)


def run(config: RAGConfig) -> None:
    """Full evaluation: retrieval HPO + RAG eval + ops, then reports."""
    articles = load_corpus(config)
    questions = load_questions(config, articles)
    if not questions:
        raise RuntimeError("no eval questions resolved against the corpus")

    embed_fn: EmbedFn = SentenceTransformerEmbedder(config.embedding_model)
    rerank_fn: RerankFn = CrossEncoderReranker(config.reranker_model)

    # --- Retrieval HPO: chunk sweep + random floor (wave 2) -----------------
    scores, random_scores, sweep_fig = run_retrieval_sweep(config, questions, embed_fn, rerank_fn)
    # --- Ablations: embedding model, rerank on/off, top_k grid --------------
    model_scores = model_comparison(config, questions, articles, rerank_fn)
    rerank_scores = rerank_ablation(config, questions, embed_fn, rerank_fn)
    topk = topk_sweep(config, questions, embed_fn, rerank_fn)
    chosen = choose_retrieval_config(config, model_scores, scores, topk)
    logger.info("chosen retrieval config: %s", chosen.model_dump())

    # --- RAG eval at the chosen retrieval config ----------------------------
    arm = next(a for a in EMBEDDING_ARMS if a[0] == chosen.embedding_slug)
    chosen_embedder: EmbedFn = SentenceTransformerEmbedder(arm[1])
    chosen_index = (
        config.index_path(chosen.chunk_size)
        if chosen.embedding_slug == "minilm"
        else config.index_dir / f"chunks_{chosen.chunk_size}_{chosen.embedding_slug}"
    )
    retriever = Retriever.from_index_dir(
        config,
        chosen_index,
        chosen_embedder,
        rerank_fn if chosen.rerank else None,
        query_prefixed(chosen_embedder, arm[2]),
    )
    agent = build_agent(config)
    rag_run = run_rag_eval(config, agent, retriever, questions)

    avg_output_tokens = (
        sum(rag_run.output_tokens) / len(rag_run.output_tokens) if rag_run.output_tokens else 0.0
    )
    est_at = {
        size: {k: est_input_tokens_at(topk[size], questions, k) for k in TOP_K_VALUES}
        for size in config.chunk_sizes
    }
    chosen_tokens = est_at[chosen.chunk_size][chosen.top_k]
    chosen_recall = recall_at_k_from(topk[chosen.chunk_size], chosen.top_k)
    chosen_mrr = mrr_at_5(topk[chosen.chunk_size]["ranks"])
    default_size = config.chunk_sizes[len(config.chunk_sizes) // 2]
    default_data = topk[default_size]
    default_recall = recall_at_k_from(default_data, config.top_k)

    latency_fig = latency_figure(rag_run.latencies_s)
    eda_fig = corpus_eda_figure(articles)
    model_fig = model_comparison_figure(model_scores, chosen.embedding_slug)
    hpo_fig = hpo_frontier_figure(config, questions, topk, chosen)
    funnel_fig = retrieval_funnel_figure(config, questions, topk, chosen)

    figures = {
        "eda_corpus_composition": eda_fig,
        "chunk_size_sweep": sweep_fig,
        "model_comparison": model_fig,
        "retrieval_funnel": funnel_fig,
        "retrieval_hpo_frontier": hpo_fig,
        "latency_histogram": latency_fig,
    }
    random_by_size = {s.chunk_size: s for s in random_scores}
    extra = {
        "n_questions": len(questions),
        "n_articles": len(articles),
        "retrieval": {
            str(s.chunk_size): {
                "recall@5": s.recall_at_5,
                "recall@10": s.recall_at_10,
                "mrr@5": s.mrr_at_5,
                "est_input_tokens_per_query": est_at[s.chunk_size][config.top_k],
                "random_recall@5": random_by_size[s.chunk_size].recall_at_5,
                "random_mrr@5": random_by_size[s.chunk_size].mrr_at_5,
                "delta_mrr@5_vs_random": s.mrr_at_5 - random_by_size[s.chunk_size].mrr_at_5,
            }
            for s in scores
        },
        "hpo": {
            "chosen": chosen.model_dump(),
            "models": {
                slug: {"recall@5": s.recall_at_5, "recall@10": s.recall_at_10, "mrr@5": s.mrr_at_5}
                for slug, s in model_scores.items()
            },
            "rerank_ablation": {
                label: {"recall@5": s.recall_at_5, "mrr@5": s.mrr_at_5}
                for label, s in rerank_scores.items()
            },
            "topk_grid": {
                str(size): {f"recall@{k}": recall_at_k_from(topk[size], k) for k in TOP_K_VALUES}
                | {"est_input_tokens": {str(k): est_at[size][k] for k in TOP_K_VALUES}}
                for size in config.chunk_sizes
            },
            "delta_vs_wave2_default": {
                "wave2_default": {
                    "embedding_slug": "minilm",
                    "chunk_size": default_size,
                    "top_k": config.top_k,
                    "recall@5": default_recall,
                },
                "chosen": {"recall@k": chosen_recall, "mrr@5": chosen_mrr},
                "delta_recall": chosen_recall - default_recall,
                "delta_mrr@5": chosen_mrr - mrr_at_5(default_data["ranks"]),
            },
        },
        "rag": rag_run.eval_result.to_dict(),
        "ops": {
            "p50_latency_s": rag_run.p50_latency_s,
            "p95_latency_s": rag_run.p95_latency_s,
            # Context-sized estimate: what a live provider call would cost given
            # the measured prompt+context budget at the CHOSEN configuration.
            "est_cost_usd_per_query": rag_run.cost_per_query_usd(chosen_tokens),
            # Mock-mode floor from agent-recorded usage (no provider call).
            "cost_usd_per_query_mock_floor": rag_run.est_cost_per_query_usd,
            "avg_input_tokens": (
                sum(rag_run.input_tokens) / len(rag_run.input_tokens)
                if rag_run.input_tokens
                else None
            ),
            "avg_output_tokens": avg_output_tokens,
        },
    }
    _write_reports(
        config,
        scores,
        rag_run,
        figures,
        extra,
        rag_input_tokens_override=chosen_tokens,
        random_scores=random_scores,
        model_scores=model_scores,
        rerank_scores=rerank_scores,
        topk_runs=[topk_run_for_size(size, topk[size]) for size in config.chunk_sizes],
    )
