"""Evaluation orchestration: retrieval sweep, RAG quality, RAGAS, telemetry.

Coordinates the measurement pipeline, delegating figure construction to
:mod:`rag_agent.figures` and report/telemetry writing to
:mod:`rag_agent.reporting`. Everything is injectable (embed/rerank/agent) so
tests run with fakes offline.

Pipeline blocks, all writing into ``config.reports_dir``:

(a) retrieval eval — graded questions run against every chunk-size index;
    recall@5, recall@10, MRR@5 per size + a seeded random baseline.
(b) RAG eval — the agent answers each question with bounded output-retries on
    schema-invalid ``AnalysisResult`` (wave 15; retries counted in the trace);
    a rubric judge (provider model by default, keyword judge as CI floor)
    scores faithfulness / relevance / recall, and ``--ragas`` adds the RAGAS
    metric set with the active provider as evaluator.
(c) ops — per-query latency (p50/p95) and cost telemetry for the active
    backend. Hosted runs meter every LLM phase (agent / judge / verify / RAGAS)
    into the platform spend ledger (USD cap per run; wave 15); local inference
    stays $0 API cost.

A separate ``run_heldout`` (wave 16, ``evaluate --heldout``) measures a sealed
15-question held-out golden set — written fresh, never tuned against — and
reports it under ``metrics detail.heldout``, apart from the tuning set: the
same retrieval metrics plus one verify-on agent pass (agent + verify + rubric
judge, deliberately no RAGAS to bound hosted cost) with bootstrap CIs on
faithfulness and the failure taxonomy.
"""

import json
import random
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import plotly.graph_objects as go
from portfolio_core.llm_budget import BudgetExceededError, budget_limits
from portfolio_core.logging import get_logger
from portfolio_eval.rag import RAGEvalResult
from pydantic import ValidationError
from pydantic_ai import Agent, AgentRunResult
from pydantic_ai.exceptions import UnexpectedModelBehavior

if TYPE_CHECKING:
    from pydantic_ai.models import Model

from rag_agent.agent import build_agent
from rag_agent.config import RAGConfig, RetrievalBest
from rag_agent.corpus import load_corpus
from rag_agent.figures import (
    corpus_eda_figure,
    frontier_figure,
    hpo_frontier_figure,
    latency_figure,
    model_comparison_figure,
    retrieval_funnel_figure,
    sweep_figure,
    taxonomy_figure,
)
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
from rag_agent.judge import RubricJudge, build_judge
from rag_agent.lexical import lexical_ranks
from rag_agent.metering import get_meter, start_metering
from rag_agent.ragas_eval import RagasRow, ensure_ragas_importable, run_ragas
from rag_agent.reporting import (
    TOP_K_VALUES,
    QuestionTrace,
    RAGRun,
    RetrievalScores,
    TopkData,
    abstention_report,
    bootstrap_ci,
    classify_question,
    cost_telemetry,
    est_input_tokens_at,
    inference_backend,
    is_abstention,
    mrr_at_5,
    recall_at_k,
    recall_at_k_from,
    topk_run_for_size,
    write_cost_telemetry,
    write_question_traces,
)
from rag_agent.reporting import (
    write_reports as _write_reports,
)
from rag_agent.schemas import AnalysisResult, Article, Citation, EvalQuestion
from rag_agent.verify import ClaimJudge, VerifyReport, build_claim_judge, verify_result

__all__ = [
    "RAGRun",
    "RetrievalScores",
    "TopkData",
    "choose_retrieval_config",
    "corpus_eda_figure",
    "cost_telemetry",
    "est_input_tokens_at",
    "estimate_input_tokens",
    "first_relevant_rank",
    "frontier_figure",
    "hpo_frontier_figure",
    "inference_backend",
    "latency_figure",
    "load_heldout_questions",
    "load_questions",
    "model_comparison",
    "model_comparison_figure",
    "mrr_at_5",
    "query_prefixed",
    "random_ranks",
    "recall_at_k",
    "recall_at_k_from",
    "rerank_ablation",
    "retrieval_funnel_figure",
    "run",
    "run_heldout",
    "run_rag_eval",
    "run_retrieval_sweep",
    "sweep_figure",
    "topk_run_for_size",
    "topk_sweep",
    "validate_heldout_set",
    "write_cost_telemetry",
]

logger = get_logger(__name__)

# Wave 15: bounded output-retries for schema-invalid agent output. pydantic-ai
# validates ``AnalysisResult`` on every run; an invalid draft raises
# ``ValidationError`` inside the run, surfacing as ``UnexpectedModelBehavior``
# once the (here zeroed) internal regeneration budget is exhausted. The eval
# previously recorded that as a format-failure and never retried. Up to two
# call-site retries (the pattern of project 09's run_agent_with_retries) rerun
# the agent from scratch — the failed conversation is not reusable — and every
# retry is counted in the question trace.
MAX_OUTPUT_RETRIES = 2


def answer_with_output_retries(
    agent: Agent[Retriever, AnalysisResult],
    question: str,
    retriever: Retriever,
    max_retries: int = MAX_OUTPUT_RETRIES,
) -> tuple[AgentRunResult[AnalysisResult] | None, int, str]:
    """Run the agent with ≤ ``max_retries`` output-retries on invalid output.

    Returns ``(result, n_retries, error)``: a successful ``result`` (retries
    counted), or ``(None, n_retries, error)`` when every attempt failed — the
    caller keeps the format-failure taxonomy label in that case. The USD budget
    cap (:class:`BudgetExceededError`) always propagates: it must stop the run,
    never be recorded as a per-question failure.
    """
    retries = 0
    while True:
        try:
            result = agent.run_sync(
                question,
                deps=retriever,
                retries={"output": 0},  # retries are explicit and counted here
                usage_limits=budget_limits(),
            )
            return result, retries, ""
        except BudgetExceededError:
            raise
        except (ValidationError, UnexpectedModelBehavior) as exc:
            error = f"{type(exc).__name__}: {exc}"[:200]
            if retries >= max_retries:
                logger.warning("agent output invalid after %d retries: %s", retries, error)
                return None, retries, error
            retries += 1
            logger.warning("agent output invalid (retry %d/%d): %s", retries, max_retries, error)
        except Exception as exc:  # broad: not retryable; recorded and returned
            return None, retries, f"{type(exc).__name__}: {exc}"[:200]


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


def load_questions(config: RAGConfig, articles: list[Article]) -> list[EvalQuestion]:
    """Load graded questions, resolving expected titles to corpus article ids.

    Questions whose relevant titles are absent from the corpus are skipped with
    a warning so the eval degrades gracefully instead of scoring noise —
    except ``unanswerable`` questions, which intentionally cite no titles.
    """
    raw = json.loads(config.eval_questions_path.read_text(encoding="utf-8"))
    return _resolve_questions(raw, articles, source=str(config.eval_questions_path))


def load_heldout_questions(config: RAGConfig, articles: list[Article]) -> list[EvalQuestion]:
    """Load the sealed held-out golden set (same schema as the tuning set).

    The held-out file may carry ``absent_terms`` on unanswerable rows — those
    are authoring-time guarantees consumed by :func:`validate_heldout_set`,
    not part of :class:`EvalQuestion`.
    """
    raw = json.loads(config.heldout_questions_path.read_text(encoding="utf-8"))
    return _resolve_questions(raw, articles, source=str(config.heldout_questions_path))


def _resolve_questions(
    raw: list[dict[str, Any]], articles: list[Article], *, source: str
) -> list[EvalQuestion]:
    """Shared tuning/held-out loader: title resolution + skip-on-missing rules."""
    title_to_id = {a.title: a.article_id for a in articles}
    questions: list[EvalQuestion] = []
    for item in raw:
        behavior = item.get("expected_behavior", "answer")
        resolved = [title_to_id[t] for t in item.get("relevant_titles", []) if t in title_to_id]
        missing = [t for t in item.get("relevant_titles", []) if t not in title_to_id]
        if behavior == "answer" and not resolved:
            logger.warning(
                "skipping eval question (no relevant titles in corpus): %s", item["question"]
            )
            continue
        if missing:
            logger.warning(
                "eval question %r: titles not in corpus ignored: %s", item["question"], missing
            )
        questions.append(
            EvalQuestion(
                question=item["question"],
                relevant_article_ids=resolved,
                category=item.get("category", "single_hop"),
                expected_behavior=behavior,
            )
        )
    logger.info(
        "loaded %d eval questions from %s (%d skipped)",
        len(questions),
        source,
        len(raw) - len(questions),
    )
    return questions


# Words too generic to carry question identity in the freshness check.
_FRESHNESS_STOPWORDS = frozenset(
    {
        "what",
        "is",
        "are",
        "was",
        "were",
        "how",
        "does",
        "do",
        "did",
        "why",
        "where",
        "who",
        "whom",
        "whose",
        "which",
        "when",
        "that",
        "this",
        "the",
        "and",
        "or",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "from",
        "by",
        "as",
        "it",
        "its",
        "into",
        "like",
        "about",
        "between",
        "compared",
        "differ",
        "differed",
        "different",
        "differs",
    }
)


def _content_words(text: str) -> set[str]:
    """Lowercased alpha tokens len>3 minus stopwords — the freshness fingerprint."""
    words = {
        token
        for token in ("".join(c if c.isalpha() else " " for c in text.lower()).split())
        if len(token) > 3
    }
    return words - _FRESHNESS_STOPWORDS


def validate_heldout_set(
    config: RAGConfig,
    heldout: list[EvalQuestion],
    tuning: list[EvalQuestion],
    retriever: Retriever,
    articles: list[Article],
) -> list[str]:
    """Gate the held-out set before it is ever scored; every problem fails loudly.

    Three directions, all deterministic:

    1. **Answerable** — same rule as :func:`validate_golden_set`: a relevant
       chunk must sit in the production retriever's top-10, else the question
       grades retrieval noise.
    2. **Unanswerable** — every ``absent_terms`` entry must occur nowhere in
       the corpus (title or text, case-insensitive). If the term is anywhere,
       the question may be answerable after all and must be rewritten.
    3. **Fresh** — the content-word Jaccard overlap against every tuning-set
       question must stay below 0.5, so held-out questions are written fresh,
       not variations of the 65 the pipeline was tuned against.
    """
    problems = validate_golden_set(config, heldout, retriever)
    corpus_text = "\n".join(f"{a.title}\n{a.text}" for a in articles).lower()
    raw = json.loads(config.heldout_questions_path.read_text(encoding="utf-8"))
    absent_terms: dict[str, list[str]] = {}
    for item in raw:
        terms = [str(t).lower() for t in item.get("absent_terms", [])]
        if terms:
            absent_terms[item["question"]] = terms
    tuning_questions = {q.question.lower() for q in tuning}
    for question in heldout:
        if question.question.lower() in tuning_questions:
            problems.append(
                f"held-out question duplicates a tuning question: {question.question!r}"
            )
        terms = absent_terms.get(question.question, [])
        if question.expected_behavior == "abstain":
            if not terms:
                problems.append(
                    f"unanswerable question has no absent_terms guarantee: {question.question!r}"
                )
            for term in terms:
                if term in corpus_text:
                    problems.append(
                        f"absent term {term!r} occurs in the corpus — question may be "
                        f"answerable: {question.question!r}"
                    )
        held_words = _content_words(question.question)
        for other in tuning:
            other_words = _content_words(other.question)
            union = held_words | other_words
            if not union:
                continue
            overlap = len(held_words & other_words) / len(union)
            if overlap >= 0.5:
                problems.append(
                    f"held-out question too similar to tuning question "
                    f"(Jaccard {overlap:.2f}): {question.question!r} vs {other.question!r}"
                )
    return problems


def validate_golden_set(
    config: RAGConfig, questions: list[EvalQuestion], retriever: Retriever
) -> list[str]:
    """Validate questions against the actual index before they ship.

    Answerable questions must have a relevant chunk within the top-10 hits of
    the production retriever (otherwise the question grades retrieval noise).
    Unanswerable questions are validated at authoring time — their topics must
    sit outside the corpus topics — and are accepted here on schema alone.
    """
    problems: list[str] = []
    for question in questions:
        if question.expected_behavior == "abstain":
            continue
        citations = retriever.search(question.question, top_k=10)
        if first_relevant_rank(citations, question.relevant_article_ids) is None:
            problems.append(f"no relevant chunk in top-10: {question.question!r}")
    return problems


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
        rng = random.Random(f"{config.seed}:{len(chunks)}:{qi}")  # noqa: S311 - seeded eval RNG, not crypto
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
) -> tuple[list[RetrievalScores], list[RetrievalScores], list[RetrievalScores], go.Figure]:
    """Score every chunk-size index on the graded question set + both floors.

    Returns (embedding scores, random-baseline scores, lexical-baseline
    scores, figure). Both baselines are computed per chunk size (different
    chunk counts → different granularity/draws): the seeded uniform-random
    floor quantifies chance, the deterministic word-matching floor
    (:mod:`rag_agent.lexical`) is the fair naive comparator embeddings must beat.
    """
    scores: list[RetrievalScores] = []
    random_scores: list[RetrievalScores] = []
    lexical_scores: list[RetrievalScores] = []
    for size in config.chunk_sizes:
        retriever = Retriever.from_index_dir(config, config.index_path(size), embed_fn, rerank_fn)
        ranks = [
            first_relevant_rank(retriever.search(q.question, top_k=10), q.relevant_article_ids)
            for q in questions
        ]
        scores.append(_score_ranks(ranks, len(questions), size))
        rnd = random_ranks(config, questions, retriever.chunks)
        random_scores.append(_score_ranks(rnd, len(questions), size))
        lex = lexical_ranks(retriever.chunks, questions)
        lexical_scores.append(_score_ranks(lex, len(questions), size))
        logger.info(
            "chunk_size=%d recall@5=%.3f recall@10=%.3f mrr@5=%.3f | "
            "random recall@5=%.3f mrr@5=%.3f | lexical recall@5=%.3f mrr@5=%.3f",
            size,
            scores[-1].recall_at_5,
            scores[-1].recall_at_10,
            scores[-1].mrr_at_5,
            random_scores[-1].recall_at_5,
            random_scores[-1].mrr_at_5,
            lexical_scores[-1].recall_at_5,
            lexical_scores[-1].mrr_at_5,
        )
    return (
        scores,
        random_scores,
        lexical_scores,
        sweep_figure(scores, random_scores, lexical_scores),
    )


def run_rag_eval(
    config: RAGConfig,
    agent: Agent[Retriever, AnalysisResult],
    retriever: Retriever,
    questions: list[EvalQuestion],
    judge: RubricJudge | None = None,
    verifier: ClaimJudge | None = None,
) -> RAGRun:
    """Run the agent over the question set; collect traces + judge verdicts.

    Per question we record a :class:`QuestionTrace` (the failure-taxonomy
    input). Per-row judge verdicts aggregate with exactly the formulas of
    ``RAGEvaluator.run`` (mean faithfulness, mean relevance over question+
    context, retrieval-recall fraction) — answerable questions only, since a
    correct refusal must not count as unfaithful. Unanswerable questions are
    scored by the abstention metrics instead. A schema-invalid agent run is
    retried up to twice (wave 15, counted in the trace) and only recorded as a
    format failure when every attempt fails, never propagated.

    When ``config.verify.enabled`` (the wave-14 verify-then-answer loop), each
    drafted answer is claim-verified against its cited chunks before judging:
    unsupported claims are repaired/dropped and low-support answers fall back
    to abstention. ``verifier`` overrides the claim judge (tests inject a
    scripted/keyword one); by default the provider model is used with the
    deterministic keyword judge as offline fallback.
    """
    selected = judge if judge is not None else build_judge()
    logger.info("RAG judge: %s", getattr(selected, "name", type(selected).__name__))
    claim_judge: ClaimJudge | None = None
    if config.verify.enabled:
        claim_judge = verifier if verifier is not None else build_claim_judge()
        logger.info("claim verifier: %s", getattr(claim_judge, "name", type(claim_judge).__name__))

    traces: list[QuestionTrace] = []
    ragas_rows: list[RagasRow] = []
    verify_reports: list[VerifyReport] = []
    latencies: list[float] = []
    input_tokens: list[int] = []
    output_tokens: list[int] = []
    faith_scores: list[float] = []
    relevance_scores: list[float] = []
    retrieved_flags: list[float] = []
    n_answerable = 0

    for question in questions:
        start = time.perf_counter()
        output: AnalysisResult | None = None
        output_retries = 0
        error = ""
        try:
            result, output_retries, error = answer_with_output_retries(
                agent, question.question, retriever
            )
            if result is not None:
                output = result.output
                get_meter().record("agent", result)
                input_tokens.append(int(result.usage.input_tokens))
                output_tokens.append(int(result.usage.output_tokens))
        except BudgetExceededError:  # the cap stops the run, never a per-question trace
            raise
        latencies.append(time.perf_counter() - start)

        # Wave 14: verify-then-answer — repair/drop unsupported claims, or fall
        # back to abstention, BEFORE the answer is judged / fed to RAGAS.
        if output is not None and claim_judge is not None:
            verify_reports.append(
                verify_result(question.question, output, retriever, config, claim_judge)
            )

        evidence = retriever.search(question.question, top_k=config.top_k)
        relevant = set(question.relevant_article_ids)
        top10 = retriever.search(question.question, top_k=10)
        top_rank = first_relevant_rank(top10, question.relevant_article_ids)
        retrieved_relevant = any(c.article_id in relevant for c in evidence)

        if output is None:
            traces.append(
                QuestionTrace(
                    question=question.question,
                    category=question.category,
                    expected_behavior=question.expected_behavior,
                    top_rank=top_rank,
                    retrieved_relevant=retrieved_relevant,
                    cited_relevant=False,
                    faithfulness=float("nan"),
                    abstained=False,
                    format_ok=False,
                    output_retries=output_retries,
                    error=error,
                )
            )
            continue

        summary = output.summary
        cited_relevant = any(c.article_id in relevant for c in output.citations)
        abstained = is_abstention(summary, output.confidence)
        context = "\n".join(c.excerpt for c in evidence)
        faith = selected.judge(question.question, context, summary).score
        relevance = selected.judge(
            question.question, question.question + " " + context, summary
        ).score
        traces.append(
            QuestionTrace(
                question=question.question,
                category=question.category,
                expected_behavior=question.expected_behavior,
                top_rank=top_rank,
                retrieved_relevant=retrieved_relevant,
                cited_relevant=cited_relevant,
                faithfulness=faith,
                abstained=abstained,
                format_ok=True,
                output_retries=output_retries,
            )
        )
        if question.expected_behavior == "answer":
            n_answerable += 1
            faith_scores.append(faith)
            relevance_scores.append(relevance)
            retrieved_flags.append(1.0 if retrieved_relevant else 0.0)
            # RAGAS sample: full retrieved chunk texts + the graded article lead.
            contexts: list[str] = []
            reference = ""
            for citation in evidence:
                chunk = retriever.get_chunk(citation.chunk_id)
                if chunk is not None:
                    contexts.append(chunk.text)
                    if not reference and chunk.article_id in relevant:
                        reference = chunk.text[:500]
            ragas_rows.append(
                RagasRow(
                    question=question.question,
                    answer=summary,
                    contexts=contexts,
                    reference=reference,
                )
            )

    def _mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else float("nan")

    rag_result = RAGEvalResult(
        n=n_answerable,
        faithfulness=_mean(faith_scores),
        answer_relevance=_mean(relevance_scores),
        context_recall=_mean(retrieved_flags),
    )
    logger.info("RAG eval: %s", rag_result.to_dict())
    return RAGRun(
        eval_result=rag_result,
        latencies_s=latencies,
        ragas_rows=ragas_rows,
        traces=traces,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        faithfulness_rows=faith_scores,
        relevance_rows=relevance_scores,
        retrieved_rows=retrieved_flags,
        verify_reports=verify_reports,
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
    embed_fn: EmbedFn | None = None,
) -> dict[str, RetrievalScores]:
    """Compare embedding models on the same chunk-200 chunk structure.

    The MiniLM arm reuses the existing production index; other arms get their
    own persisted index under ``data/index/chunks_200_<slug>/`` (built once,
    reused afterwards). ``embed_fn`` override is for tests: both arms then
    search the existing index with the injected encoder.
    """
    size = min(config.chunk_sizes)
    results: dict[str, RetrievalScores] = {}
    for slug, model_name, prefix in EMBEDDING_ARMS:
        embedder: EmbedFn = embed_fn or SentenceTransformerEmbedder(model_name)
        if embed_fn is not None:
            index_dir = config.index_path(size)
        else:
            index_dir = (
                config.index_path(size)
                if slug == "minilm"
                else config.index_dir / f"chunks_{size}_{slug}"
            )
        if embed_fn is None and slug != "minilm" and not (index_dir / "faiss.index").exists():
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
) -> dict[int, TopkData]:
    """Per chunk size: top-``max(k)`` search once, then derive every recall@k.

    Also records the cumulative citation-token sum per question so input-token
    (cost) estimates are available for every (size, k) point without re-search.
    """
    k_max = max(k_values)
    per_size: dict[int, TopkData] = {}
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
        per_size[size] = TopkData(
            ranks=ranks, token_sums=token_sums, n_chunks=len(retriever.chunks)
        )
    return per_size


def choose_retrieval_config(
    config: RAGConfig,
    model_scores: dict[str, RetrievalScores],
    sweep_scores: list[RetrievalScores],
    topk: dict[int, TopkData],
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


def estimate_input_tokens(
    config: RAGConfig, questions: list[EvalQuestion], embed_fn: EmbedFn, rerank_fn: RerankFn | None
) -> dict[int, float]:
    """Average estimated input tokens/query for each chunk size (prompt + top-k context)."""
    from rag_agent.reporting import BASE_PROMPT_TOKENS, TOKENS_PER_WORD

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


@dataclass(frozen=True)
class RetrievalHpoResult:
    """Outputs of the retrieval-HPO stage (runs offline-safe)."""

    scores: list[RetrievalScores]
    random_scores: list[RetrievalScores]
    lexical_scores: list[RetrievalScores]
    sweep_fig: go.Figure
    model_scores: dict[str, RetrievalScores]
    rerank_scores: dict[str, RetrievalScores]
    topk: dict[int, TopkData]
    est_at: dict[int, dict[int, float]]
    chosen: RetrievalBest


@dataclass(frozen=True)
class RagStageResult:
    """Outputs of the agent/judge (+RAGAS) stage; empty when ``offline``."""

    rag_run: RAGRun | None
    ragas_scores: dict[str, float] | None
    ragas_ci: dict[str, Any] | None
    wall_time_s: float


def _run_retrieval_hpo(
    config: RAGConfig,
    questions: list[EvalQuestion],
    articles: list[Article],
    embed_fn: EmbedFn,
    rerank_fn: RerankFn,
) -> RetrievalHpoResult:
    """Chunk sweep + random/lexical floors + model/rerank/top-k ablations → chosen config."""
    scores, random_scores, lexical_scores, sweep_fig = run_retrieval_sweep(
        config, questions, embed_fn, rerank_fn
    )
    model_scores = model_comparison(config, questions, articles, rerank_fn, embed_fn=embed_fn)
    rerank_scores = rerank_ablation(config, questions, embed_fn, rerank_fn)
    topk = topk_sweep(config, questions, embed_fn, rerank_fn)
    chosen = choose_retrieval_config(config, model_scores, scores, topk)
    logger.info("chosen retrieval config: %s", chosen.model_dump())
    est_at = {
        size: {k: est_input_tokens_at(topk[size], questions, k) for k in TOP_K_VALUES}
        for size in config.chunk_sizes
    }
    return RetrievalHpoResult(
        scores=scores,
        random_scores=random_scores,
        lexical_scores=lexical_scores,
        sweep_fig=sweep_fig,
        model_scores=model_scores,
        rerank_scores=rerank_scores,
        topk=topk,
        est_at=est_at,
        chosen=chosen,
    )


def _validate_golden_set_stage(
    config: RAGConfig,
    questions: list[EvalQuestion],
    embed_fn: EmbedFn,
    rerank_fn: RerankFn,
) -> None:
    """Golden-set validation against the production index (embed-only, offline-safe)."""
    validation_retriever = Retriever.from_index_dir(
        config,
        config.index_path(min(config.chunk_sizes)),
        embed_fn,
        rerank_fn,
    )
    problems = validate_golden_set(config, questions, validation_retriever)
    for problem in problems:
        logger.warning("golden-set validation: %s", problem)
    if problems:
        logger.warning("golden-set validation found %d problem(s)", len(problems))


def _run_agent_stage(
    config: RAGConfig,
    chosen: RetrievalBest,
    rag_questions: list[EvalQuestion],
    offline: bool,
    ragas: bool,
    embed_fn: EmbedFn,
    rerank_fn: RerankFn,
) -> RagStageResult:
    """Agent + rubric judge (+ optional RAGAS) at the chosen retrieval config."""
    run_start = time.perf_counter()
    if offline:
        return RagStageResult(
            rag_run=None,
            ragas_scores=None,
            ragas_ci=None,
            wall_time_s=time.perf_counter() - run_start,
        )
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
    rag_run = run_rag_eval(config, agent, retriever, rag_questions)
    ragas_scores: dict[str, float] | None = None
    ragas_ci: dict[str, Any] | None = None
    if ragas:
        ragas_result = run_ragas(config, rag_run.ragas_rows)
        ragas_scores = ragas_result.scores
        ragas_ci = {
            name: {
                "mean": ragas_result.scores[name],
                "ci95": list(bootstrap_ci(values, seed=config.seed)),
            }
            for name, values in ragas_result.per_row.items()
        }
    return RagStageResult(
        rag_run=rag_run,
        ragas_scores=ragas_scores,
        ragas_ci=ragas_ci,
        wall_time_s=time.perf_counter() - run_start,
    )


def _verify_stats(config: RAGConfig, rag_run: RAGRun | None) -> dict[str, Any] | None:
    """Aggregate verify-then-answer stats over the answered questions."""
    if rag_run is None or not rag_run.verify_reports:
        return None
    reports = rag_run.verify_reports
    total_verify_s = sum(r.latency_s for r in reports)
    total_answer_s = sum(rag_run.latencies_s)
    return {
        "enabled": config.verify.enabled,
        "min_support": config.verify.min_support,
        "max_repair_calls": config.verify.max_repair_calls,
        "n_answers_verified": len(reports),
        "n_verify_abstentions": sum(1 for r in reports if r.abstained),
        "n_verify_skipped": sum(1 for r in reports if r.skipped),
        "total_repair_calls": sum(r.n_repair_calls for r in reports),
        "mean_support_fraction": round(sum(r.support_fraction for r in reports) / len(reports), 4),
        "mean_verify_latency_s": round(total_verify_s / len(reports), 3),
        "verify_latency_share_of_answer": (
            round(total_verify_s / total_answer_s, 4) if total_answer_s > 0 else None
        ),
    }


def _rag_ci(config: RAGConfig, rag_run: RAGRun) -> dict[str, Any]:
    """Mean + bootstrap-95% CI for the three RAG metrics."""
    return {
        "faithfulness": {
            "mean": rag_run.eval_result.faithfulness,
            "ci95": list(bootstrap_ci(rag_run.faithfulness_rows, seed=config.seed)),
        },
        "answer_relevance": {
            "mean": rag_run.eval_result.answer_relevance,
            "ci95": list(bootstrap_ci(rag_run.relevance_rows, seed=config.seed)),
        },
        "context_recall": {
            "mean": rag_run.eval_result.context_recall,
            "ci95": list(bootstrap_ci(rag_run.retrieved_rows, seed=config.seed)),
        },
    }


def _taxonomy_counts(rag_run: RAGRun | None) -> dict[str, int]:
    """Failure-taxonomy histogram over the per-question traces."""
    counts: dict[str, int] = {}
    if rag_run:
        for trace in rag_run.traces:
            label = classify_question(trace)
            counts[label] = counts.get(label, 0) + 1
    return counts


def _build_figures(
    config: RAGConfig,
    articles: list[Article],
    questions: list[EvalQuestion],
    hpo: RetrievalHpoResult,
    rag_run: RAGRun | None,
) -> dict[str, go.Figure]:
    """Every report figure, in report order (latency/taxonomy appended last)."""
    figures: dict[str, go.Figure] = {
        "eda_corpus_composition": corpus_eda_figure(articles),
        "chunk_size_sweep": hpo.sweep_fig,
        "model_comparison": model_comparison_figure(hpo.model_scores, hpo.chosen.embedding_slug),
        "retrieval_funnel": retrieval_funnel_figure(config, questions, hpo.topk, hpo.chosen),
        "retrieval_hpo_frontier": hpo_frontier_figure(config, questions, hpo.topk, hpo.chosen),
    }
    if rag_run is not None:
        figures["latency_histogram"] = latency_figure(rag_run.latencies_s)
        if rag_run.traces:
            figures["failure_taxonomy"] = taxonomy_figure(rag_run.traces)
    return figures


def _run_meta(
    config: RAGConfig,
    questions: list[EvalQuestion],
    rag_run: RAGRun | None,
    rag_ci: dict[str, Any] | None,
    ragas_ci: dict[str, Any] | None,
) -> dict[str, Any]:
    """Report metadata: golden-set composition, abstention, CIs, taxonomy."""
    golden_counts: dict[str, int] = {}
    for q in questions:
        key = f"{q.category}/{q.expected_behavior}"
        golden_counts[key] = golden_counts.get(key, 0) + 1
    abstention = abstention_report(rag_run.traces, seed=config.seed) if rag_run else None
    return {
        "golden_set": golden_counts,
        "abstention": abstention,
        "rag_ci": rag_ci,
        "taxonomy": _taxonomy_counts(rag_run),
        "ragas_ci": ragas_ci,
    }


def _extra_payload(
    config: RAGConfig,
    questions: list[EvalQuestion],
    rag_questions: list[EvalQuestion],
    offline: bool,
    hpo: RetrievalHpoResult,
    rag_run: RAGRun | None,
    ragas_scores: dict[str, float] | None,
    verify_stats: dict[str, Any] | None,
    chosen_tokens: float,
) -> dict[str, Any]:
    """The ``detail`` block of ``metrics.json``: retrieval HPO + RAG + ops."""
    avg_output_tokens = (
        sum(rag_run.output_tokens) / len(rag_run.output_tokens)
        if rag_run and rag_run.output_tokens
        else 0.0
    )
    chosen = hpo.chosen
    chosen_recall = recall_at_k_from(hpo.topk[chosen.chunk_size], chosen.top_k)
    chosen_mrr = mrr_at_5(hpo.topk[chosen.chunk_size]["ranks"])
    default_size = config.chunk_sizes[len(config.chunk_sizes) // 2]
    default_data = hpo.topk[default_size]
    default_recall = recall_at_k_from(default_data, config.top_k)
    random_by_size = {s.chunk_size: s for s in hpo.random_scores}
    lexical_by_size = {s.chunk_size: s for s in hpo.lexical_scores}
    return {
        "n_questions": len(questions),
        "rag_n_questions": len(rag_questions),
        "offline": offline,
        "retrieval": {
            str(s.chunk_size): {
                "recall@5": s.recall_at_5,
                "recall@10": s.recall_at_10,
                "mrr@5": s.mrr_at_5,
                "est_input_tokens_per_query": hpo.est_at[s.chunk_size][config.top_k],
                "random_recall@5": random_by_size[s.chunk_size].recall_at_5,
                "random_mrr@5": random_by_size[s.chunk_size].mrr_at_5,
                "delta_mrr@5_vs_random": s.mrr_at_5 - random_by_size[s.chunk_size].mrr_at_5,
                "lexical_recall@5": lexical_by_size[s.chunk_size].recall_at_5,
                "lexical_mrr@5": lexical_by_size[s.chunk_size].mrr_at_5,
                "delta_recall@5_vs_lexical": (
                    s.recall_at_5 - lexical_by_size[s.chunk_size].recall_at_5
                ),
            }
            for s in hpo.scores
        },
        "hpo": {
            "chosen": chosen.model_dump(),
            "models": {
                slug: {"recall@5": s.recall_at_5, "recall@10": s.recall_at_10, "mrr@5": s.mrr_at_5}
                for slug, s in hpo.model_scores.items()
            },
            "rerank_ablation": {
                label: {"recall@5": s.recall_at_5, "mrr@5": s.mrr_at_5}
                for label, s in hpo.rerank_scores.items()
            },
            "topk_grid": {
                str(size): {
                    f"recall@{k}": recall_at_k_from(hpo.topk[size], k) for k in TOP_K_VALUES
                }
                | {"est_input_tokens": {str(k): hpo.est_at[size][k] for k in TOP_K_VALUES}}
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
        "rag": rag_run.eval_result.to_dict() if rag_run else None,
        "ragas": ragas_scores,
        "verify": verify_stats,
        "ops": {
            "backend": inference_backend() if rag_run else None,
            "p50_latency_s": rag_run.p50_latency_s if rag_run else None,
            "p95_latency_s": rag_run.p95_latency_s if rag_run else None,
            "est_cost_usd_per_query": (
                rag_run.cost_per_query_usd(chosen_tokens) if rag_run else None
            ),
            "avg_input_tokens": (
                sum(rag_run.input_tokens) / len(rag_run.input_tokens)
                if rag_run and rag_run.input_tokens
                else None
            ),
            "avg_output_tokens": avg_output_tokens,
        },
    }


def _write_reports_stage(
    config: RAGConfig,
    hpo: RetrievalHpoResult,
    rag_run: RAGRun | None,
    figures: dict[str, go.Figure],
    extra: dict[str, Any],
    meta: dict[str, Any],
    ragas_scores: dict[str, float] | None,
    chosen_tokens: float,
    wall_time_s: float,
) -> None:
    """Write report.html + metrics.json (+ cost telemetry when the agent ran)."""
    topk_runs = [topk_run_for_size(size, hpo.topk[size]) for size in config.chunk_sizes]
    _write_reports(
        config,
        hpo.scores,
        rag_run,
        figures,
        extra,
        rag_input_tokens_override=chosen_tokens if rag_run is not None else None,
        random_scores=hpo.random_scores,
        lexical_scores=hpo.lexical_scores,
        model_scores=hpo.model_scores,
        rerank_scores=hpo.rerank_scores,
        topk_runs=topk_runs,
        ragas_scores=ragas_scores,
        traces=rag_run.traces if rag_run is not None else None,
        meta=meta,
    )
    if rag_run is not None:
        write_cost_telemetry(config, rag_run, wall_time_s, phases=get_meter().snapshot())


def run(
    config: RAGConfig,
    ragas: bool = False,
    offline: bool = False,
    max_questions: int | None = None,
    verify: bool | None = None,
    embed_fn: EmbedFn | None = None,
    rerank_fn: RerankFn | None = None,
) -> None:
    """Full evaluation: retrieval HPO always; RAG/RAGAS/telemetry need a provider.

    ``offline=True`` skips every model-dependent part (agent, judges, RAGAS,
    telemetry) and reports retrieval quality only — the CI-safe path.
    ``ragas=True`` additionally computes the RAGAS metric set with the local
    model as evaluator. ``max_questions`` bounds ONLY the LLM phases (agent +
    RAGAS) to the first N graded questions — retrieval metrics always use the
    full set; local model inference makes the unbounded run multi-hour.
    ``verify`` overrides ``config.verify.enabled`` (``--verify``/``--no-verify``
    A/B); None keeps the params.yaml value.
    ``embed_fn``/``rerank_fn`` overrides are for tests (deterministic fakes).
    """
    if verify is not None:
        config.verify.enabled = verify
    if ragas:
        # Fail fast if the venv is pruned mid-run.
        ensure_ragas_importable()
    # Fresh spend-ledger window for this run: the hosted USD cap applies per
    # evaluate invocation (no-op when the local provider is active).
    start_metering()

    articles = load_corpus(config)
    questions = load_questions(config, articles)
    if not questions:
        raise RuntimeError("no eval questions resolved against the corpus")
    rag_questions = questions[:max_questions] if max_questions else questions
    if len(rag_questions) < len(questions):
        logger.warning(
            "LLM phases bounded to first %d of %d questions (local inference wall clock)",
            len(rag_questions),
            len(questions),
        )

    if embed_fn is None:
        embed_fn = SentenceTransformerEmbedder(config.embedding_model)
    if rerank_fn is None:
        rerank_fn = CrossEncoderReranker(config.reranker_model)

    # --- Retrieval HPO: chunk sweep + ablations → chosen config -------------
    hpo = _run_retrieval_hpo(config, questions, articles, embed_fn, rerank_fn)
    _validate_golden_set_stage(config, questions, embed_fn, rerank_fn)

    # --- Agent/judge stage (+ RAGAS), skipped when --offline ----------------
    rag_stage = _run_agent_stage(
        config, hpo.chosen, rag_questions, offline, ragas, embed_fn, rerank_fn
    )
    rag_run = rag_stage.rag_run
    rag_ci = _rag_ci(config, rag_run) if rag_run else None
    verify_stats = _verify_stats(config, rag_run)
    chosen_tokens = hpo.est_at[hpo.chosen.chunk_size][hpo.chosen.top_k]

    # --- Reporting: meta/detail blocks, figures, reports ---------------------
    meta = _run_meta(config, questions, rag_run, rag_ci, rag_stage.ragas_ci)
    extra = _extra_payload(
        config,
        questions,
        rag_questions,
        offline,
        hpo,
        rag_run,
        rag_stage.ragas_scores,
        verify_stats,
        chosen_tokens,
    )
    figures = _build_figures(config, articles, questions, hpo, rag_run)
    _write_reports_stage(
        config,
        hpo,
        rag_run,
        figures,
        extra,
        meta,
        rag_stage.ragas_scores,
        chosen_tokens,
        rag_stage.wall_time_s,
    )


def run_heldout(
    config: RAGConfig,
    judge: RubricJudge | None = None,
    verifier: ClaimJudge | None = None,
    embed_fn: EmbedFn | None = None,
    rerank_fn: RerankFn | None = None,
    model: "Model | None" = None,
    meter_active: bool | None = None,
) -> dict[str, Any]:
    """Evaluate the sealed held-out golden set (``evaluate --heldout``).

    Runs apart from the tuning-set eval so the tuning numbers are never
    overwritten: retrieval metrics (recall@5/10, MRR@5 + seeded random floor)
    at the production config, then ONE verify-on agent pass — agent + claim
    verify + rubric judge, deliberately **no RAGAS** so a hosted run stays
    cheap. Bootstrap 95% CIs are reported on faithfulness and on the
    failure-taxonomy correct share. The result is merged into the existing
    ``reports/metrics.json`` under ``detail.heldout`` (created if absent) and
    per-question traces go to ``reports/question_traces_heldout.json``.

    The gate runs first: :func:`validate_heldout_set` problems raise
    :class:`RuntimeError` — a held-out set that is not provably answerable /
    unanswerable / fresh is never scored.

    ``judge``/``verifier``/``embed_fn``/``rerank_fn``/``model``/``meter_active``
    overrides are for tests (deterministic fakes, metering off); production
    resolves provider judges by default and auto-detects hosted metering.
    """
    start_metering(active=meter_active)  # fresh spend-ledger window for this run
    articles = load_corpus(config)
    tuning = load_questions(config, articles)
    heldout = load_heldout_questions(config, articles)
    if not heldout:
        raise RuntimeError("no held-out questions resolved against the corpus")
    chosen = config.retrieval_best
    if chosen is None:
        raise RuntimeError("config.retrieval_best is required for the held-out run")

    embed_fn_override = embed_fn is not None
    if embed_fn is None:
        embed_fn = SentenceTransformerEmbedder(chosen.embedding_model)
    if rerank_fn is None:
        rerank_fn = CrossEncoderReranker(config.reranker_model)
    arm = next(a for a in EMBEDDING_ARMS if a[0] == chosen.embedding_slug)
    if embed_fn_override:
        # Test override: search the fixture index for the chosen chunk size.
        index_dir = config.index_path(chosen.chunk_size)
    else:
        index_dir = (
            config.index_path(chosen.chunk_size)
            if chosen.embedding_slug == "minilm"
            else config.index_dir / f"chunks_{chosen.chunk_size}_{chosen.embedding_slug}"
        )
    retriever = Retriever.from_index_dir(
        config,
        index_dir,
        embed_fn,
        rerank_fn if chosen.rerank else None,
        query_prefixed(embed_fn, arm[2]),
    )

    problems = validate_heldout_set(config, heldout, tuning, retriever, articles)
    if problems:
        for problem in problems:
            logger.error("held-out validation: %s", problem)
        raise RuntimeError(
            f"held-out validation failed with {len(problems)} problem(s); refusing to score it"
        )

    ranks = [
        first_relevant_rank(retriever.search(q.question, top_k=10), q.relevant_article_ids)
        for q in heldout
    ]
    retrieval = {
        "recall@5": recall_at_k(ranks, 5),
        "recall@10": recall_at_k(ranks, 10),
        "mrr@5": mrr_at_5(ranks),
        "n_questions": len(heldout),
    }
    rnd_ranks = random_ranks(config, heldout, retriever.chunks)
    retrieval["random_recall@5"] = recall_at_k(rnd_ranks, 5)
    retrieval["random_mrr@5"] = mrr_at_5(rnd_ranks)
    retrieval["delta_mrr@5_vs_random"] = retrieval["mrr@5"] - retrieval["random_mrr@5"]
    logger.info("heldout retrieval: %s", retrieval)

    agent = build_agent(config, model=model)
    rag_run = run_rag_eval(config, agent, retriever, heldout, judge=judge, verifier=verifier)

    correct_flags = [1.0 if classify_question(t) == "correct" else 0.0 for t in rag_run.traces]
    taxonomy = _taxonomy_counts(rag_run)
    composition: dict[str, int] = {}
    for q in heldout:
        key = f"{q.category}/{q.expected_behavior}"
        composition[key] = composition.get(key, 0) + 1
    traces_path = write_question_traces(
        config, rag_run.traces, path=config.reports_dir / "question_traces_heldout.json"
    )
    payload: dict[str, Any] = {
        "n_questions": len(heldout),
        "composition": composition,
        "retrieval": retrieval,
        "rag": rag_run.eval_result.to_dict(),
        "faithfulness": {
            "mean": rag_run.eval_result.faithfulness,
            "ci95": list(bootstrap_ci(rag_run.faithfulness_rows, seed=config.seed)),
        },
        "taxonomy": {
            "counts": taxonomy,
            "correct_share": (sum(correct_flags) / len(correct_flags) if correct_flags else 0.0),
            "correct_share_ci95": list(bootstrap_ci(correct_flags, seed=config.seed)),
        },
        "abstention": abstention_report(rag_run.traces, seed=config.seed),
        "verify": _verify_stats(config, rag_run),
        "ops": {
            "backend": inference_backend(),
            "p50_latency_s": rag_run.p50_latency_s,
            "p95_latency_s": rag_run.p95_latency_s,
        },
        "meter": get_meter().snapshot(),
        "traces_path": str(traces_path),
        "note": (
            "sealed held-out set, reported separately from the tuning set; "
            "verify-on pass without RAGAS to bound hosted cost"
        ),
    }

    metrics_path = config.reports_dir / "metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    else:
        metrics = {"detail": {}}
    metrics.setdefault("detail", {})["heldout"] = payload
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    meter = payload["meter"]
    logger.info(
        "heldout run written: %s (backend=%s, metered spend=%.4f USD cloud-equivalent)",
        metrics_path,
        payload["ops"]["backend"],
        meter["total"]["spend_usd"] if meter["active"] else 0.0,
    )
    return payload
