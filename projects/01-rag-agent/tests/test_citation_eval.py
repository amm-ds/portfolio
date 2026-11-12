"""Citation-correctness pass (``evaluate --citations``): records, aggregates, gates."""

import json
from pathlib import Path

import numpy as np
import pytest
from portfolio_core.llm import mock_model_for_tests
from portfolio_eval.rag import KeywordJudge
from rag_agent.config import RAGConfig, RetrievalBest
from rag_agent.evaluate import run_citation_eval
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


def _seed_corpus(config: RAGConfig, articles: list[Article]) -> None:
    config.corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with config.corpus_path.open("w", encoding="utf-8") as fh:
        for article in articles:
            fh.write(article.model_dump_json() + "\n")
    config.eval_questions_path.write_text(
        json.dumps([{"question": "why are plants green", "relevant_titles": ["Photosynthesis"]}]),
        encoding="utf-8",
    )


def test_run_citation_eval_end_to_end_offline(
    config: RAGConfig,
    articles: list[Article],
    embed_fn: EmbedFn,
    index_dir: Path,
) -> None:
    """Full citation pass on fakes: gate → pass → records + metrics section."""
    _seed_corpus(config, articles)
    _write_heldout(config, HELDOUT_ROWS)
    config.retrieval_best = _chosen(config)

    payload = run_citation_eval(
        config,
        judge=KeywordJudge(),
        verifier=KeywordEntailmentJudge(),
        embed_fn=embed_fn,
        rerank_fn=_keep_order_rerank,
        model=mock_model_for_tests(CANNED_ANALYSIS_JSON),
        meter_active=False,
    )
    assert payload["n_questions"] == 2
    assert payload["meter"]["active"] is False  # local/fake provider: no spend

    claims = payload["claims"]
    assert claims["drafted"] == sum(
        len(r["claims"])
        for r in json.loads(
            (config.reports_dir / "citation_records_heldout.json").read_text(encoding="utf-8")
        )
    )
    assert claims["drafted"] >= 1
    assert 0 <= claims["support_rate_first_check"] <= 1
    assert claims["surviving"] <= claims["supported_first_check"] + claims["repaired"]
    assert claims["dropped"] + claims["surviving"] <= claims["drafted"]
    lo, hi = claims["support_rate_first_check_ci95"]
    assert lo <= claims["support_rate_first_check"] <= hi

    answers = payload["answers"]
    # R6 evidence gate: the unanswerable row ("who won the battle of hastings")
    # is refused BEFORE generation — its evidence shares no content word with
    # the question — so only the answerable row reaches verification.
    assert answers["n_verified"] == 1
    assert answers["floor"] == config.verify.min_support
    slo, shi = answers["mean_support_fraction_ci95"]
    assert slo <= answers["mean_support_fraction"] <= shi
    assert 0.0 <= answers["share_at_or_above_floor"] <= 1.0
    assert sum(v["n_answers"] for v in payload["by_verdict"].values()) == answers["n_verified"]

    records = json.loads(
        (config.reports_dir / "citation_records_heldout.json").read_text(encoding="utf-8")
    )
    assert len(records) == answers["n_verified"]  # gate-refused rows produce no record
    first = records[0]
    assert first["question"] == HELDOUT_ROWS[0]["question"]  # the answered row only
    assert first["citations"] == [{"chunk_id": "c", "article_id": "a"}]
    assert {"claim", "supported", "reason", "repaired", "dropped"} <= set(first["claims"][0])
    assert {r["verdict"] for r in records} == set(payload["by_verdict"])

    # The headline section is never created or touched by this pass.
    metrics = json.loads((config.reports_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "heldout_citations" in metrics["detail"]
    assert "heldout" not in metrics["detail"]


def test_run_citation_eval_refuses_to_score_invalid_set(
    config: RAGConfig,
    articles: list[Article],
    embed_fn: EmbedFn,
    index_dir: Path,
) -> None:
    """Validation problems fail loudly: nothing is scored or written."""
    _seed_corpus(config, articles)
    _write_heldout(
        config,
        [
            {
                "question": "how do solar panels fail",
                "category": "unanswerable",
                "expected_behavior": "abstain",
                "absent_terms": ["solar"],  # present in the fixture corpus
            },
        ],
    )
    config.retrieval_best = _chosen(config)
    with pytest.raises(RuntimeError, match="held-out validation failed"):
        run_citation_eval(
            config,
            judge=KeywordJudge(),
            verifier=KeywordEntailmentJudge(),
            embed_fn=embed_fn,
            rerank_fn=_keep_order_rerank,
            model=mock_model_for_tests(CANNED_ANALYSIS_JSON),
            meter_active=False,
        )
    assert not (config.reports_dir / "metrics.json").exists()
    assert not (config.reports_dir / "citation_records_heldout.json").exists()
