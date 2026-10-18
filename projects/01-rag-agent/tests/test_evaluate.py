"""Evaluate tests: metric math, question loading, RAG run on synthetic rows."""

import json
from pathlib import Path

import pytest
from portfolio_eval.rag import KeywordJudge, RAGEvalResult
from pydantic_ai.models.function import FunctionModel
from rag_agent.agent import build_agent
from rag_agent.config import RAGConfig
from rag_agent.evaluate import (
    RAGRun,
    RetrievalScores,
    _write_reports,
    choose_retrieval_config,
    corpus_eda_figure,
    cost_telemetry,
    estimate_input_tokens,
    first_relevant_rank,
    frontier_figure,
    latency_figure,
    load_questions,
    mrr_at_5,
    query_prefixed,
    random_ranks,
    recall_at_k,
    run_rag_eval,
    sweep_figure,
    topk_run_for_size,
    write_cost_telemetry,
)
from rag_agent.index import EmbedFn, Retriever
from rag_agent.schemas import Article, Citation, EvalQuestion
from rag_agent.verify import KeywordEntailmentJudge

CANNED_ANALYSIS_JSON = json.dumps(
    {
        "summary": "Test-only canned answer.",
        "citations": [
            {"chunk_id": "c", "article_id": "a", "title": "t", "excerpt": "e", "score": 1.0}
        ],
        "confidence": 0.5,
    }
)


def canned_analysis_model() -> FunctionModel:
    from portfolio_core.llm import mock_model_for_tests

    return mock_model_for_tests(CANNED_ANALYSIS_JSON)


def test_recall_at_k_and_mrr() -> None:
    ranks: list[int | None] = [1, 3, None, 5, 10]
    assert recall_at_k(ranks, 5) == pytest.approx(0.6)
    assert recall_at_k(ranks, 10) == pytest.approx(0.8)  # None never counts
    assert recall_at_k(ranks, 1) == pytest.approx(0.2)
    assert mrr_at_5(ranks) == pytest.approx((1 / 1 + 1 / 3 + 1 / 5) / 5)
    assert mrr_at_5([]) != mrr_at_5([])  # NaN for empty input
    assert recall_at_k([], 5) != recall_at_k([], 5)


def test_first_relevant_rank() -> None:
    citations = [
        Citation(chunk_id="a#c000", article_id="a", title="t", excerpt="e"),
        Citation(chunk_id="b#c000", article_id="b", title="t", excerpt="e"),
    ]
    assert first_relevant_rank(citations, ["b"]) == 2
    assert first_relevant_rank(citations, ["x"]) is None


def _write_questions(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(rows), encoding="utf-8")


def test_load_questions_resolves_titles_and_skips_missing(
    config: RAGConfig, articles: list[Article]
) -> None:
    _write_questions(
        config.eval_questions_path,
        [
            {"question": "q1", "relevant_titles": ["Climate change", "Not in corpus"]},
            {"question": "q2", "relevant_titles": ["Also missing"]},
        ],
    )
    questions = load_questions(config, articles)
    assert len(questions) == 1
    assert questions[0].relevant_article_ids == ["climate-000"]


def test_load_questions_missing_file(config: RAGConfig) -> None:
    with pytest.raises(FileNotFoundError):
        load_questions(config, [])


def test_retrieval_scores_as_run() -> None:
    scores = RetrievalScores(
        chunk_size=50, recall_at_5=0.5, recall_at_10=0.75, mrr_at_5=0.4, n_questions=4
    )
    run = scores.as_run()
    assert run.name == "retrieval_chunks_50"
    recall = run.get("recall@5")
    assert recall is not None
    assert recall.value == 0.5


def test_figures_render(scores_sample: list[RetrievalScores]) -> None:
    fig = sweep_figure(scores_sample)
    assert fig.data and len(fig.data) == 3
    fig_random = sweep_figure(scores_sample, scores_sample)  # reuse as random baseline
    assert len(fig_random.data) == 5  # 3 bars + 2 dashed reference series
    assert any("random" in trace.name for trace in fig_random.data)
    # Readability contract (viewer report "chunk size 600 has no bars"):
    # categorical axis (no implied 600 gap), value labels on every bar, an
    # explicit sizes-tested caption, and zero floor points annotated not voided.
    assert fig_random.layout.xaxis.type == "category"
    assert all(trace.text for trace in fig_random.data[:3])
    annotation_texts = [a.text for a in fig_random.layout.annotations]
    assert any("no 600" in t or "categorical" in t for t in annotation_texts)
    zero_random = sweep_figure(
        scores_sample,
        [
            RetrievalScores(
                chunk_size=s.chunk_size,
                recall_at_5=0.0,
                recall_at_10=0.0,
                mrr_at_5=0.0,
                n_questions=s.n_questions,
            )
            for s in scores_sample
        ],
    )
    zero_texts = [a.text for a in zero_random.layout.annotations]
    assert any("not a missing bar" in (t or "") for t in zero_texts)
    fig2 = latency_figure([0.1, 0.2, 0.3, 0.4])
    assert fig2.data


def test_random_ranks_are_seeded_and_bounded(config: RAGConfig, retriever: Retriever) -> None:
    questions = [
        EvalQuestion(question="q about climate", relevant_article_ids=["climate-000"]),
        EvalQuestion(question="q about algae", relevant_article_ids=["photo-000"]),
    ]
    first = random_ranks(config, questions, retriever.chunks)
    second = random_ranks(config, questions, retriever.chunks)
    assert first == second  # deterministic for a fixed config.seed
    assert all(r is None or 1 <= r <= len(retriever.chunks) for r in first)
    other = RAGConfig(seed=123)
    third = random_ranks(other, questions, retriever.chunks)
    assert third != first  # different seed → different draw


def test_corpus_eda_figure_renders(articles: list[Article]) -> None:
    fig = corpus_eda_figure(articles)
    assert len(fig.data) == 2  # bar + histogram
    assert sum(fig.data[0].y) == len(articles)


def test_query_prefixed_wraps_texts(embed_fn: EmbedFn) -> None:
    plain = query_prefixed(embed_fn, "")
    assert plain is embed_fn  # no prefix → same callable
    prefixed = query_prefixed(embed_fn, "Q: ")
    out = prefixed(["hello world"])
    assert out.shape == (1, 32)  # hashing embedder dim, prefix applied internally


def test_choose_retrieval_config_picks_best() -> None:
    config = RAGConfig()
    model_scores = {
        "minilm": RetrievalScores(
            chunk_size=200, recall_at_5=0.9, recall_at_10=1.0, mrr_at_5=0.8, n_questions=10
        ),
        "bge_small": RetrievalScores(
            chunk_size=200, recall_at_5=0.9, recall_at_10=1.0, mrr_at_5=0.7, n_questions=10
        ),
    }
    sweep_scores = [
        RetrievalScores(
            chunk_size=size, recall_at_5=0.9, recall_at_10=1.0, mrr_at_5=mrr, n_questions=10
        )
        for size, mrr in ((200, 0.8), (400, 0.6), (800, 0.5))
    ]
    topk = {
        200: {"ranks": [1, 2, 3, 4] * 6 + [1, 2], "token_sums": [[10] * 10] * 26, "n_chunks": 100},
        400: {"ranks": [1, 2, 3, 4] * 6 + [1, 2], "token_sums": [[10] * 10] * 26, "n_chunks": 50},
        800: {"ranks": [1, 2, 3, 4] * 6 + [1, 2], "token_sums": [[10] * 10] * 26, "n_chunks": 25},
    }
    chosen = choose_retrieval_config(config, model_scores, sweep_scores, topk)
    assert chosen.embedding_slug == "minilm"  # higher MRR
    assert chosen.chunk_size == 200  # best MRR
    assert chosen.top_k == 5  # recall@5 saturates (1.0) → smallest sufficient k
    assert chosen.rerank


def test_topk_run_for_size() -> None:
    data = {"ranks": [1, None, 3, 10], "token_sums": [[5] * 10] * 4, "n_chunks": 50}
    run = topk_run_for_size(200, data)
    assert run.name == "retrieval_topk_sweep_chunks_200"
    assert run.get("recall@3") is not None
    assert run.get("recall@10") is not None


@pytest.fixture
def scores_sample() -> list[RetrievalScores]:
    return [
        RetrievalScores(
            chunk_size=50, recall_at_5=0.5, recall_at_10=0.6, mrr_at_5=0.4, n_questions=4
        ),
        RetrievalScores(
            chunk_size=100, recall_at_5=0.6, recall_at_10=0.7, mrr_at_5=0.5, n_questions=4
        ),
    ]


def test_run_rag_eval_on_synthetic_rows(
    config: RAGConfig, retriever: Retriever, articles: list[Article]
) -> None:
    agent = build_agent(config, model=canned_analysis_model())
    questions = [
        EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"]),
        EvalQuestion(question="what is machine learning", relevant_article_ids=["ml-000"]),
    ]
    rag_run = run_rag_eval(
        config, agent, retriever, questions, judge=KeywordJudge(), verifier=KeywordEntailmentJudge()
    )
    assert rag_run.eval_result.n == 2
    assert 0.0 <= rag_run.eval_result.faithfulness <= 1.0
    assert len(rag_run.latencies_s) == 2
    assert len(rag_run.input_tokens) == 2
    assert rag_run.p50_latency_s >= 0.0
    assert rag_run.est_cost_per_query_usd > 0.0
    # Verification ran on both answers (config default: enabled).
    assert len(rag_run.verify_reports) == 2


def test_estimate_input_tokens(
    config: RAGConfig, embed_fn: EmbedFn, index_dir: Path, articles: list[Article]
) -> None:
    questions = [EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"])]
    estimates = estimate_input_tokens(config, questions, embed_fn, None)
    assert set(estimates) == {50}
    assert estimates[50] > 0.0


def test_frontier_figure_renders(config: RAGConfig, scores_sample: list[RetrievalScores]) -> None:
    est = {50: 1000.0, 100: 2000.0}
    quality = {50: 0.5, 100: 0.6}
    fig = frontier_figure(
        config, scores_sample, est, avg_output_tokens=100.0, rag_quality_by_size=quality
    )
    assert len(fig.data[0].x) == 2


def _synthetic_rag_run() -> RAGRun:
    return RAGRun(
        eval_result=RAGEvalResult(n=2, faithfulness=0.8, answer_relevance=0.7, context_recall=0.5),
        latencies_s=[0.1, 0.2],
        input_tokens=[100, 120],
        output_tokens=[50, 60],
        _rate_in=0.15,
        _rate_out=0.60,
    )


def test_write_reports_produces_all_artifacts(
    config: RAGConfig, scores_sample: list[RetrievalScores]
) -> None:
    figures = {"chunk_size_sweep": sweep_figure(scores_sample)}
    rag_run = _synthetic_rag_run()
    extra = {"n_questions": 2, "rag": rag_run.eval_result.to_dict()}
    _write_reports(config, scores_sample, rag_run, figures, extra, random_scores=scores_sample)

    metrics = json.loads((config.reports_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "retrieval_chunks_50" in metrics
    assert "retrieval_random_chunks_50" in metrics
    assert metrics["retrieval_random_chunks_50"]["recall@5"] == 0.5
    assert metrics["detail"]["n_questions"] == 2
    assert (config.reports_dir / "report.html").exists()
    assert (config.reports_dir / "figures" / "chunk_size_sweep.html").exists()
    assert (config.reports_dir / "figures" / "chunk_size_sweep.json").exists()
    html = (config.reports_dir / "report.html").read_text(encoding="utf-8")
    assert "figures/chunk_size_sweep.html" in html


def test_cost_telemetry_shape_and_write(config: RAGConfig) -> None:
    rag_run = _synthetic_rag_run()  # 2 queries: in [100, 120], out [50, 60]
    payload = cost_telemetry(config, rag_run, wall_time_s=120.0)
    assert payload["backend"].startswith(("ollama:", "env:"))
    if payload["backend"].startswith("ollama:"):
        assert payload["api_cost_usd"] == 0.0
    assert payload["n_queries"] == 2
    assert payload["total_input_tokens"] == 220
    assert payload["total_output_tokens"] == 110
    assert payload["eval_wall_time_s"] == 120.0
    assert len(payload["per_query"]) == 2
    expected = 100 / 1e6 * 0.15 + 50 / 1e6 * 0.60
    hypo = payload["rate_card_hypothetical_cost_usd"]
    assert hypo["mean"] > 0
    assert round(hypo["mean"], 8) == round((expected + (120 / 1e6 * 0.15 + 60 / 1e6 * 0.60)) / 2, 8)

    path = write_cost_telemetry(config, rag_run, wall_time_s=60.0)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["n_queries"] == 2
    assert written["eval_wall_time_s"] == 60.0
    assert written["backend"] == payload["backend"]


def test_to_ragas_dicts_column_mapping() -> None:
    from rag_agent.ragas_eval import RagasRow, to_ragas_dicts

    rows = [
        RagasRow(question="q?", answer="a", contexts=["c1", "c2"], reference="ref"),
        RagasRow(question="q2?", answer="a2", contexts=[], reference=""),
    ]
    dicts = to_ragas_dicts(rows)
    assert dicts[0] == {
        "user_input": "q?",
        "response": "a",
        "retrieved_contexts": ["c1", "c2"],
        "reference": "ref",
    }
    assert dicts[1]["retrieved_contexts"] == []
    assert set(dicts[0]) == {"user_input", "response", "retrieved_contexts", "reference"}


# --- Wave 15: bounded output-retries on schema-invalid agent output ----------

INVALID_ANALYSIS_JSON = json.dumps(
    {
        "summary": "",  # violates min_length=1 → ValidationError
        "citations": [
            {"chunk_id": "c", "article_id": "a", "title": "t", "excerpt": "e", "score": 1.0}
        ],
        "confidence": 0.9,
    }
)


def _sequenced_model(responses: list[str]) -> FunctionModel:
    """FunctionModel that replays ``responses`` one per call."""
    from pydantic_ai.messages import ModelResponse, TextPart

    calls = {"n": 0}

    def respond(messages: list, info: object) -> ModelResponse:
        calls["n"] += 1
        content = responses[min(calls["n"] - 1, len(responses) - 1)]
        return ModelResponse(parts=[TextPart(content=content)])

    model = FunctionModel(respond)
    model.calls = calls  # type: ignore[attr-defined]
    return model


def test_output_retry_recovers_invalid_then_valid(config: RAGConfig, retriever: Retriever) -> None:
    from rag_agent.metering import start_metering

    start_metering(active=False)  # retries only; metering covered elsewhere
    model = _sequenced_model([INVALID_ANALYSIS_JSON, CANNED_ANALYSIS_JSON])
    agent = build_agent(config, model=model)
    questions = [EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"])]
    rag_run = run_rag_eval(
        config, agent, retriever, questions, judge=KeywordJudge(), verifier=KeywordEntailmentJudge()
    )
    trace = rag_run.traces[0]
    assert trace.format_ok
    assert trace.output_retries == 1
    assert model.calls["n"] == 2  # invalid attempt + one retry
    assert rag_run.eval_result.n == 1


def test_output_retry_gives_up_and_keeps_format_failure_label(
    config: RAGConfig, retriever: Retriever
) -> None:
    from rag_agent.metering import start_metering
    from rag_agent.reporting import classify_question

    start_metering(active=False)
    model = _sequenced_model([INVALID_ANALYSIS_JSON])
    agent = build_agent(config, model=model)
    questions = [EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"])]
    rag_run = run_rag_eval(
        config, agent, retriever, questions, judge=KeywordJudge(), verifier=KeywordEntailmentJudge()
    )
    trace = rag_run.traces[0]
    assert not trace.format_ok
    assert trace.output_retries == 2  # both allowed retries spent
    assert classify_question(trace) == "format-failure"
    assert model.calls["n"] == 3  # initial attempt + 2 retries
    assert "ValidationError" in trace.error or "UnexpectedModelBehavior" in trace.error
