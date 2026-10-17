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
"""

import json
import random
import time
from collections.abc import Sequence
from typing import Any

import numpy as np
import plotly.graph_objects as go
from portfolio_core.llm_budget import BudgetExceededError, budget_limits
from portfolio_core.logging import get_logger
from portfolio_eval.rag import RAGEvalResult
from pydantic import ValidationError
from pydantic_ai import Agent, AgentRunResult
from pydantic_ai.exceptions import UnexpectedModelBehavior

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
    "run_rag_eval",
    "run_retrieval_sweep",
    "sweep_figure",
    "topk_run_for_size",
    "topk_sweep",
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
        except Exception as exc:  # non-validation failure: record, don't retry
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
    logger.info("loaded %d eval questions (%d skipped)", len(questions), len(raw) - len(questions))
    return questions


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
        scores.append(_score_ranks(ranks, len(questions), size))
        rnd = random_ranks(config, questions, retriever.chunks)
        random_scores.append(_score_ranks(rnd, len(questions), size))
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

    # --- Retrieval HPO: chunk sweep + random floor --------------------------
    scores, random_scores, sweep_fig = run_retrieval_sweep(config, questions, embed_fn, rerank_fn)
    # --- Ablations: embedding model, rerank on/off, top_k grid --------------
    model_scores = model_comparison(config, questions, articles, rerank_fn, embed_fn=embed_fn)
    rerank_scores = rerank_ablation(config, questions, embed_fn, rerank_fn)
    topk = topk_sweep(config, questions, embed_fn, rerank_fn)
    chosen = choose_retrieval_config(config, model_scores, scores, topk)
    logger.info("chosen retrieval config: %s", chosen.model_dump())

    # --- RAG eval at the chosen retrieval config (skipped when --offline) ---
    run_start = time.perf_counter()
    rag_run: RAGRun | None = None
    ragas_scores: dict[str, float] | None = None
    ragas_ci: dict[str, Any] | None = None
    # Golden-set validation against the production index (embed-only, works offline).
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
    if not offline:
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
        else:
            ragas_ci = None
    wall_time_s = time.perf_counter() - run_start

    abstention = abstention_report(rag_run.traces, seed=config.seed) if rag_run else None
    verify_stats: dict[str, Any] | None = None
    if rag_run and rag_run.verify_reports:
        v_reports = rag_run.verify_reports
        total_verify_s = sum(r.latency_s for r in v_reports)
        total_answer_s = sum(rag_run.latencies_s)
        verify_stats = {
            "enabled": config.verify.enabled,
            "min_support": config.verify.min_support,
            "max_repair_calls": config.verify.max_repair_calls,
            "n_answers_verified": len(v_reports),
            "n_verify_abstentions": sum(1 for r in v_reports if r.abstained),
            "n_verify_skipped": sum(1 for r in v_reports if r.skipped),
            "total_repair_calls": sum(r.n_repair_calls for r in v_reports),
            "mean_support_fraction": round(
                sum(r.support_fraction for r in v_reports) / len(v_reports), 4
            ),
            "mean_verify_latency_s": round(total_verify_s / len(v_reports), 3),
            "verify_latency_share_of_answer": (
                round(total_verify_s / total_answer_s, 4) if total_answer_s > 0 else None
            ),
        }
    rag_ci: dict[str, Any] | None = None
    if rag_run:
        rag_ci = {
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
    taxonomy_counts: dict[str, int] = {}
    if rag_run:
        for trace in rag_run.traces:
            label = classify_question(trace)
            taxonomy_counts[label] = taxonomy_counts.get(label, 0) + 1

    avg_output_tokens = (
        sum(rag_run.output_tokens) / len(rag_run.output_tokens)
        if rag_run and rag_run.output_tokens
        else 0.0
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

    latency_fig = latency_figure(rag_run.latencies_s) if rag_run else None
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
    }
    if latency_fig is not None:
        figures["latency_histogram"] = latency_fig
    if rag_run and rag_run.traces:
        figures["failure_taxonomy"] = taxonomy_figure(rag_run.traces)
    golden_counts: dict[str, int] = {}
    for q in questions:
        key = f"{q.category}/{q.expected_behavior}"
        golden_counts[key] = golden_counts.get(key, 0) + 1
    meta = {
        "golden_set": golden_counts,
        "abstention": abstention,
        "rag_ci": rag_ci,
        "taxonomy": taxonomy_counts,
        "ragas_ci": ragas_ci,
    }
    random_by_size = {s.chunk_size: s for s in random_scores}
    extra = {
        "n_questions": len(questions),
        "rag_n_questions": len(rag_questions),
        "offline": offline,
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
    if rag_run is not None:
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
            ragas_scores=ragas_scores,
            traces=rag_run.traces,
            meta=meta,
        )
        write_cost_telemetry(config, rag_run, wall_time_s, phases=get_meter().snapshot())
    else:
        _write_reports(
            config,
            scores,
            None,
            figures,
            extra,
            random_scores=random_scores,
            model_scores=model_scores,
            rerank_scores=rerank_scores,
            topk_runs=[topk_run_for_size(size, topk[size]) for size in config.chunk_sizes],
            meta=meta,
        )
