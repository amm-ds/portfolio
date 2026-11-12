"""Stress pass: gate-free validation (the methodological point) + the run."""

import json
from pathlib import Path

import numpy as np
from portfolio_core.llm import mock_model_for_tests
from portfolio_eval.rag import KeywordJudge
from rag_agent.config import RAGConfig, RetrievalBest
from rag_agent.evaluate import load_stress_questions, run_stress_eval, validate_stress_set
from rag_agent.index import EmbedFn
from rag_agent.schemas import Article
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


def _chosen(config: RAGConfig) -> RetrievalBest:
    return RetrievalBest(
        embedding_model=config.embedding_model,
        embedding_slug="minilm",
        chunk_size=min(config.chunk_sizes),
        top_k=config.top_k,
        rerank=True,
    )


STRESS_ROWS = [
    {
        "question": "how do solar panels generate electricity",
        "relevant_titles": ["Solar energy"],
        "category": "single_hop",
        "expected_behavior": "answer",
    },
    {
        "question": "what is the largest wind turbine ever built",
        "relevant_titles": [],
        "category": "ambiguous",
        "expected_behavior": "abstain",
    },
    {
        "question": "who won the battle of hastings",
        "category": "unanswerable",
        "expected_behavior": "abstain",
        "absent_terms": ["hastings"],
    },
]


def _seed(config: RAGConfig, articles: list[Article]) -> None:
    config.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with config.corpus_path.open("w", encoding="utf-8") as fh:
        for article in articles:
            fh.write(article.model_dump_json() + "\n")
    config.eval_questions_path.write_text(
        json.dumps([{"question": "why are plants green", "relevant_titles": ["Photosynthesis"]}]),
        encoding="utf-8",
    )
    config.heldout_questions_path.write_text("[]", encoding="utf-8")
    config.stress_questions_path.write_text(json.dumps(STRESS_ROWS), encoding="utf-8")


def _write_stress(config: RAGConfig, rows: list[dict[str, object]]) -> None:
    config.stress_questions_path.write_text(json.dumps(rows), encoding="utf-8")


def test_validation_needs_no_retriever_gate(
    config: RAGConfig,
    articles: list[Article],
    embed_fn: EmbedFn,
    index_dir: Path,
) -> None:
    """The stress admission deliberately ignores production-retriever presence:
    article-level support is the only criterion (audits' methodological fix)."""
    _seed(config, articles)
    stress = load_stress_questions(config, articles)
    tuning = []  # tuning not needed for the gate claim; empty keeps it minimal
    problems = validate_stress_set(config, stress, tuning, [], articles)
    assert problems == []


def test_validation_flags_duplicates_absent_terms_and_similarity(
    config: RAGConfig, articles: list[Article]
) -> None:
    _seed(config, articles)
    _write_stress(
        config,
        [
            # duplicate of a tuning question (Jaccard 1.0) + unanswerable without terms
            {
                "question": "why are plants green",
                "category": "unanswerable",
                "expected_behavior": "abstain",
            },
            {
                "question": "how do solar panels generate electricity",
                "relevant_titles": ["Solar energy"],
                "category": "single_hop",
                "expected_behavior": "answer",
            },
        ],
    )
    stress = load_stress_questions(config, articles)
    # pass the set itself as the prior: the duplicate row must be flagged
    problems = validate_stress_set(config, stress, stress, [], articles)
    assert any("too similar" in p or "duplicates" in p for p in problems)
    assert any("absent_terms" in p for p in problems)


def test_ambiguous_abstain_needs_no_absent_terms(
    config: RAGConfig, articles: list[Article]
) -> None:
    _seed(config, articles)
    stress = load_stress_questions(config, articles)
    ambiguous = [q for q in stress if q.category == "ambiguous"]
    assert len(ambiguous) == 1 and ambiguous[0].expected_behavior == "abstain"
    problems = validate_stress_set(config, stress, [], [], articles)
    assert not any("absent_terms" in p for p in problems)


def test_run_stress_eval_end_to_end_offline(
    config: RAGConfig,
    articles: list[Article],
    embed_fn: EmbedFn,
    index_dir: Path,
) -> None:
    _seed(config, articles)
    config.retrieval_best = _chosen(config)
    payload = run_stress_eval(
        config,
        judge=KeywordJudge(),
        verifier=KeywordEntailmentJudge(),
        embed_fn=embed_fn,
        rerank_fn=_keep_order_rerank,
        model=mock_model_for_tests(CANNED_ANALYSIS_JSON),
        meter_active=False,
    )
    assert payload["n_questions"] == 3
    assert payload["meter"]["active"] is False
    assert payload["composition"]["ambiguous/abstain"] == 1
    metrics = json.loads((config.reports_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "stress" in metrics["detail"]
    assert "heldout" not in metrics["detail"]
    assert (config.reports_dir / "question_traces_stress.json").exists()
