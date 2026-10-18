"""Held-out golden set: loading, validation gates, and the --heldout run (offline)."""

import json
from pathlib import Path

import numpy as np
import pytest
from portfolio_core.llm import mock_model_for_tests
from portfolio_eval.rag import KeywordJudge
from rag_agent.config import RAGConfig, RetrievalBest
from rag_agent.evaluate import (
    load_heldout_questions,
    load_questions,
    run_heldout,
    validate_heldout_set,
)
from rag_agent.index import EmbedFn, Retriever
from rag_agent.schemas import Article, EvalQuestion
from rag_agent.verify import KeywordEntailmentJudge


def _keep_order_rerank(query: str, texts: list[str]) -> np.ndarray:
    """Deterministic fake reranker: descending scores preserve candidate order."""
    return np.arange(len(texts), 0, -1, dtype=np.float32)


CANNED_ANALYSIS_JSON = json.dumps(
    {
        "summary": "Test-only canned answer grounded in the context.",
        "citations": [
            {"chunk_id": "c", "article_id": "a", "title": "t", "excerpt": "e", "score": 1.0}
        ],
        "confidence": 0.8,
    }
)

HELDOUT_ROWS = [
    {
        "question": "how do solar panels generate electricity",
        "relevant_titles": ["Solar energy"],
        "category": "single_hop",
        "expected_behavior": "answer",
    },
    {
        "question": "who won the battle of hastings",
        "category": "unanswerable",
        "expected_behavior": "abstain",
        "absent_terms": ["hastings"],
    },
]


def _write_heldout(config: RAGConfig, rows: list[dict[str, object]]) -> None:
    config.heldout_questions_path.write_text(json.dumps(rows), encoding="utf-8")


def _chosen(config: RAGConfig) -> RetrievalBest:
    return RetrievalBest(
        embedding_model=config.embedding_model,
        embedding_slug="minilm",
        chunk_size=min(config.chunk_sizes),
        top_k=config.top_k,
        rerank=True,
    )


def test_load_heldout_questions_resolves_and_drops_absent_terms(
    config: RAGConfig, articles: list[Article]
) -> None:
    _write_heldout(config, HELDOUT_ROWS)
    questions = load_heldout_questions(config, articles)
    assert len(questions) == 2
    assert questions[0].relevant_article_ids == ["energy-000"]
    assert questions[1].expected_behavior == "abstain"
    assert questions[1].relevant_article_ids == []


def test_validate_heldout_set_passes_a_clean_set(
    config: RAGConfig, articles: list[Article], retriever: Retriever
) -> None:
    _write_heldout(config, HELDOUT_ROWS)
    config.eval_questions_path.write_text(
        json.dumps([{"question": "why are plants green", "relevant_titles": ["Photosynthesis"]}]),
        encoding="utf-8",
    )
    heldout = load_heldout_questions(config, articles)
    tuning = load_questions(config, articles)
    assert validate_heldout_set(config, heldout, tuning, retriever, articles) == []


def test_validate_heldout_set_flags_every_gate(
    config: RAGConfig, articles: list[Article], retriever: Retriever
) -> None:
    _write_heldout(
        config,
        [
            # absent term actually present in the fixture corpus ("solar")
            {
                "question": "how do solar panels fail",
                "category": "unanswerable",
                "expected_behavior": "abstain",
                "absent_terms": ["solar"],
            },
            # near-duplicate of a tuning question (Jaccard ≥ 0.5)
            {
                "question": "why are plants so green",
                "relevant_titles": ["Photosynthesis"],
                "category": "single_hop",
                "expected_behavior": "answer",
            },
        ],
    )
    config.eval_questions_path.write_text(
        json.dumps([{"question": "why are plants green", "relevant_titles": ["Photosynthesis"]}]),
        encoding="utf-8",
    )
    heldout = load_heldout_questions(config, articles)
    tuning = load_questions(config, articles)
    problems = validate_heldout_set(config, heldout, tuning, retriever, articles)
    assert any("absent term" in p for p in problems)
    assert any("too similar" in p for p in problems)


def test_validate_heldout_set_flags_missing_relevance(
    config: RAGConfig, articles: list[Article], retriever: Retriever
) -> None:
    heldout = [EvalQuestion(question="anything at all", relevant_article_ids=["nonexistent-000"])]
    config.heldout_questions_path.write_text("[]", encoding="utf-8")
    problems = validate_heldout_set(config, heldout, [], retriever, articles)
    assert len(problems) == 1
    assert "anything at all" in problems[0]


def test_run_heldout_end_to_end_offline(
    config: RAGConfig,
    articles: list[Article],
    embed_fn: EmbedFn,
    index_dir: Path,
) -> None:
    """Full held-out run on fakes: validation → retrieval → agent → metrics."""
    config.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with config.corpus_path.open("w", encoding="utf-8") as fh:
        for article in articles:
            fh.write(article.model_dump_json() + "\n")
    config.eval_questions_path.write_text(
        json.dumps(
            [
                {"question": "why are plants green", "relevant_titles": ["Photosynthesis"]},
                {
                    "question": "what is machine learning",
                    "relevant_titles": ["Machine learning"],
                },
            ]
        ),
        encoding="utf-8",
    )
    _write_heldout(config, HELDOUT_ROWS)
    config.retrieval_best = _chosen(config)

    payload = run_heldout(
        config,
        judge=KeywordJudge(),
        verifier=KeywordEntailmentJudge(),
        embed_fn=embed_fn,
        rerank_fn=_keep_order_rerank,
        model=mock_model_for_tests(CANNED_ANALYSIS_JSON),
        meter_active=False,
    )
    assert payload["n_questions"] == 2
    assert payload["retrieval"]["n_questions"] == 2
    assert 0.0 <= payload["retrieval"]["recall@5"] <= 1.0
    assert payload["retrieval"]["random_mrr@5"] < payload["retrieval"]["mrr@5"]
    lo, hi = payload["faithfulness"]["ci95"]
    assert lo <= payload["faithfulness"]["mean"] <= hi
    assert sum(payload["taxonomy"]["counts"].values()) == 2
    clo, chi = payload["taxonomy"]["correct_share_ci95"]
    assert clo <= payload["taxonomy"]["correct_share"] <= chi
    assert payload["meter"]["active"] is False  # local/fake provider: no spend

    metrics = json.loads((config.reports_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["detail"]["heldout"]["n_questions"] == 2
    assert (config.reports_dir / "question_traces_heldout.json").exists()


def test_run_heldout_refuses_to_score_invalid_set(
    config: RAGConfig, articles: list[Article], embed_fn: EmbedFn, index_dir: Path
) -> None:
    """Validation problems fail loudly: nothing is scored or written."""
    config.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with config.corpus_path.open("w", encoding="utf-8") as fh:
        for article in articles:
            fh.write(article.model_dump_json() + "\n")
    config.eval_questions_path.write_text("[]", encoding="utf-8")
    _write_heldout(
        config,
        [
            {
                "question": "how do solar panels fail",
                "category": "unanswerable",
                "expected_behavior": "abstain",
                "absent_terms": ["solar"],  # present in the fixture corpus → gate trips
            }
        ],
    )
    config.retrieval_best = _chosen(config)
    with pytest.raises(RuntimeError, match="held-out validation failed"):
        run_heldout(
            config,
            judge=KeywordJudge(),
            verifier=KeywordEntailmentJudge(),
            embed_fn=embed_fn,
            rerank_fn=_keep_order_rerank,
            model=mock_model_for_tests(CANNED_ANALYSIS_JSON),
        )
    assert not (config.reports_dir / "metrics.json").exists()
