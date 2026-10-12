"""Evaluate tests: metric math, question loading, RAG run on synthetic rows."""

import json
from pathlib import Path
from typing import Any

import pytest
from portfolio_eval.rag import RAGEvalResult
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from rag_agent.agent import MOCK_ANALYSIS_JSON, build_agent
from rag_agent.config import RAGConfig
from rag_agent.evaluate import (
    RAGRun,
    RetrievalScores,
    _write_reports,
    corpus_eda_figure,
    estimate_input_tokens,
    first_relevant_rank,
    frontier_figure,
    latency_figure,
    load_questions,
    mrr_at_5,
    random_ranks,
    recall_at_k,
    run_rag_eval,
    sweep_figure,
)
from rag_agent.index import EmbedFn, Retriever
from rag_agent.schemas import Article, Citation, EvalQuestion


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
    def _respond(messages: list[Any], info: Any) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=MOCK_ANALYSIS_JSON)])

    agent = build_agent(config, model=FunctionModel(_respond))
    questions = [
        EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"]),
        EvalQuestion(question="what is machine learning", relevant_article_ids=["ml-000"]),
    ]
    rag_run = run_rag_eval(config, agent, retriever, questions)
    assert rag_run.eval_result.n == 2
    assert 0.0 <= rag_run.eval_result.faithfulness <= 1.0
    assert len(rag_run.latencies_s) == 2
    assert len(rag_run.input_tokens) == 2
    assert rag_run.p50_latency_s >= 0.0
    assert rag_run.est_cost_per_query_usd > 0.0


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
