"""Golden-set expansion, abstention metrics, failure taxonomy, bootstrap CIs (offline)."""

import json
from pathlib import Path
from typing import Any, cast

import pytest
from portfolio_core.llm import mock_model_for_tests
from portfolio_eval.rag import KeywordJudge
from rag_agent.agent import build_agent
from rag_agent.config import RAGConfig
from rag_agent.evaluate import load_questions, run, run_rag_eval, validate_golden_set
from rag_agent.index import Retriever
from rag_agent.reporting import (
    QuestionTrace,
    RetrievalScores,
    abstention_report,
    bootstrap_ci,
    classify_question,
    is_abstention,
    write_question_traces,
)
from rag_agent.schemas import EvalQuestion

CANNED_ANALYSIS_JSON = json.dumps(
    {
        "summary": "Test-only canned answer grounded in the context.",
        "citations": [
            {"chunk_id": "c", "article_id": "a", "title": "t", "excerpt": "e", "score": 1.0}
        ],
        "confidence": 0.8,
    }
)


def canned_analysis_model():  # FunctionModel, typed via pydantic-ai in helper
    return mock_model_for_tests(CANNED_ANALYSIS_JSON)


def _trace(**overrides: Any) -> QuestionTrace:
    base: dict[str, Any] = {
        "question": "q?",
        "category": "single_hop",
        "expected_behavior": "answer",
        "top_rank": 1,
        "retrieved_relevant": True,
        "cited_relevant": True,
        "faithfulness": 0.9,
        "abstained": False,
        "format_ok": True,
    }
    base.update(overrides)
    return QuestionTrace(**cast(Any, base))


def test_is_abstention_rule() -> None:
    assert is_abstention("No relevant evidence was found.", 0.9)
    assert is_abstention("There is no information about this in the context.", 0.9)
    assert not is_abstention("Photosynthesis converts light into chemical energy.", 0.9)
    assert is_abstention("Some partial answer.", 0.1)


def test_classify_question_rules() -> None:
    assert classify_question(_trace()) == "correct"
    assert classify_question(_trace(format_ok=False)) == "format-failure"
    assert classify_question(_trace(retrieved_relevant=False, top_rank=None)) == "retrieval-miss"
    assert classify_question(_trace(faithfulness=0.2)) == "unsupported-claim"
    # Unanswerable: abstaining is correct; answering is an unsupported claim.
    assert classify_question(_trace(expected_behavior="abstain", abstained=True)) == "correct"
    assert (
        classify_question(_trace(expected_behavior="abstain", abstained=False))
        == "unsupported-claim"
    )


def test_abstention_report() -> None:
    traces = [
        _trace(expected_behavior="abstain", abstained=True),
        _trace(expected_behavior="abstain", abstained=False),
        _trace(abstained=True, cited_relevant=False),
        _trace(),
    ]
    report = abstention_report(traces)
    assert report["n_unanswerable"] == 2
    assert report["refusal_accuracy"] == pytest.approx(0.5)
    assert report["cite_when_expected"] == pytest.approx(0.5)
    assert report["false_abstention_rate"] == pytest.approx(0.5)
    # Bootstrap CIs are seeded, bracket the point estimate, and cover 2 values.
    for key in ("refusal_accuracy_ci95", "cite_when_expected_ci95", "false_abstention_rate_ci95"):
        lo, hi = report[key]
        assert len(report[key]) == 2
        assert lo <= report[key.removesuffix("_ci95")] <= hi
    assert report["refusal_accuracy_ci95"] == abstention_report(traces)["refusal_accuracy_ci95"]


def test_bootstrap_ci_brackets_mean_and_is_seeded() -> None:
    values = [0.5, 0.7, 0.9, 1.0, 0.2, 0.4, 0.6, 0.8] * 3
    lo, hi = bootstrap_ci(values, n_resamples=1000, seed=42)
    mean = sum(values) / len(values)
    assert lo <= mean <= hi
    assert bootstrap_ci(values, n_resamples=1000, seed=42) == (lo, hi)
    empty_lo, empty_hi = bootstrap_ci([float("nan")])
    assert empty_lo != empty_lo and empty_hi != empty_hi  # NaN pair


def test_load_questions_supports_unanswerable(config: RAGConfig, tmp_path: Path) -> None:
    questions_path = tmp_path / "questions.json"
    questions_path.write_text(
        json.dumps(
            [
                {"question": "answerable?", "relevant_titles": ["Climate change"]},
                {
                    "question": "unanswerable?",
                    "category": "unanswerable",
                    "expected_behavior": "abstain",
                },
            ]
        ),
        encoding="utf-8",
    )
    config.eval_questions_path = questions_path
    questions = load_questions(config, [])  # titles unresolved; answerable skips
    assert len(questions) == 1
    assert questions[0].expected_behavior == "abstain"
    assert questions[0].relevant_article_ids == []


def test_eval_question_schema_requires_relevance_for_answerable() -> None:
    with pytest.raises(ValueError):
        EvalQuestion(question="q?", relevant_article_ids=[], expected_behavior="answer")
    EvalQuestion(question="q?", relevant_article_ids=[], expected_behavior="abstain")


def test_validate_golden_set_flags_missing_relevance(
    config: RAGConfig, retriever: Retriever
) -> None:
    ok = EvalQuestion(question="what is machine learning", relevant_article_ids=["ml-000"])
    # Tiny fixture index holds every chunk, so a miss is graded by pointing at
    # an article that does not exist in the index at all.
    miss = EvalQuestion(question="anything at all", relevant_article_ids=["nonexistent-000"])
    abstain = EvalQuestion(
        question="who won the world cup", expected_behavior="abstain", category="unanswerable"
    )
    problems = validate_golden_set(config, [ok, miss, abstain], retriever)
    assert len(problems) == 1
    assert "anything at all" in problems[0]


def test_run_rag_eval_traces_and_abstention_split(config: RAGConfig, retriever: Retriever) -> None:
    agent = build_agent(config, model=canned_analysis_model())
    questions = [
        EvalQuestion(question="why are plants green", relevant_article_ids=["photo-000"]),
        EvalQuestion(
            question="who won the world cup",
            relevant_article_ids=[],
            category="unanswerable",
            expected_behavior="abstain",
        ),
    ]
    rag_run = run_rag_eval(config, agent, retriever, questions, judge=KeywordJudge())
    assert len(rag_run.traces) == 2
    # Headline aggregate counts answerable questions only.
    assert rag_run.eval_result.n == 1
    assert len(rag_run.ragas_rows) == 1
    unanswerable_trace = next(t for t in rag_run.traces if t.expected_behavior == "abstain")
    assert unanswerable_trace.format_ok
    report = abstention_report(rag_run.traces)
    assert report["n_unanswerable"] == 1
    # Per-row judge scores are exposed for bootstrap CIs on the rag row.
    assert len(rag_run.faithfulness_rows) == rag_run.eval_result.n
    assert rag_run.retrieved_rows == [1.0]


def test_run_offline_end_to_end(
    config: RAGConfig, articles: list, embed_fn, tmp_path: Path
) -> None:
    """Offline run(): corpus + golden set + validation + reports, no LLM."""
    from rag_agent.index import build_index, chunk_articles

    config.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with config.corpus_path.open("w", encoding="utf-8") as fh:
        for article in articles:
            fh.write(article.model_dump_json() + "\n")
    config.eval_questions_path.write_text(
        json.dumps(
            [
                {"question": "what is machine learning", "relevant_titles": ["Machine learning"]},
                {
                    "question": "who won the world cup",
                    "category": "unanswerable",
                    "expected_behavior": "abstain",
                },
            ]
        ),
        encoding="utf-8",
    )
    chunks = chunk_articles(articles, size=50, overlap=10)
    build_index(chunks, embed_fn, config.index_path(50), description="offline test")

    run(config, offline=True, embed_fn=embed_fn, rerank_fn=None)

    metrics = json.loads((config.reports_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["detail"]["offline"] is True
    assert metrics["_meta"]["golden_set"] == {
        "single_hop/answer": 1,
        "unanswerable/abstain": 1,
    }
    assert (config.reports_dir / "report.html").exists()
    assert (config.reports_dir / "figures" / "chunk_size_sweep.html").exists()


def test_write_question_traces_artifact(config: RAGConfig) -> None:
    path = write_question_traces(config, [_trace(), _trace(format_ok=False)])
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert rows[0]["verdict"] == "correct"
    assert rows[1]["verdict"] == "format-failure"


def test_taxonomy_figure_renders() -> None:
    from rag_agent.figures import taxonomy_figure

    fig = taxonomy_figure([_trace(), _trace(format_ok=False), _trace(faithfulness=0.1)])
    assert len(fig.data) == 1
    # order: correct / retrieval-miss / unsupported-claim / format-failure
    assert list(fig.data[0].y) == [1, 0, 1, 1]


def test_write_reports_with_traces_and_meta(config: RAGConfig) -> None:
    from rag_agent.reporting import write_reports

    scores = [
        RetrievalScores(
            chunk_size=50, recall_at_5=0.5, recall_at_10=0.6, mrr_at_5=0.4, n_questions=4
        )
    ]
    write_reports(
        config,
        scores,
        None,
        {},
        {"n_questions": 4},
        traces=[_trace(), _trace(format_ok=False)],
        meta={"golden_set": {"single_hop/answer": 2}, "taxonomy": {"correct": 1}},
    )
    metrics = json.loads((config.reports_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["_meta"]["taxonomy"] == {"correct": 1}
    assert (config.reports_dir / "question_traces.json").exists()
    html = (config.reports_dir / "report.html").read_text(encoding="utf-8")
    assert "Per-question trace" in html
