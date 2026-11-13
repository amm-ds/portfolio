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


def test_run_stress_eval_r6_accounting_fields(
    config: RAGConfig,
    articles: list[Article],
    embed_fn: EmbedFn,
    index_dir: Path,
) -> None:
    """R6 payload: slices, claim accounting, budget count, audit run record."""
    _seed(config, articles)
    config.retrieval_best = _chosen(config)
    # schema-v2 canned output: one drafted claim with a verbatim span from the
    # Solar energy article (chunk energy-000#c000) → exercises the structured
    # verify path (deterministic span checks → judge → survival accounting).
    span_text = (
        "Solar energy is radiant light and heat from the Sun "
        "harnessed using a range of technologies"
    )
    v2_canned = json.dumps(
        {
            "summary": "Solar energy is radiant light and heat from the Sun.",
            "citations": [
                {
                    "chunk_id": "energy-000#c000",
                    "article_id": "energy-000",
                    "title": "Solar energy",
                    "excerpt": "Solar energy is radiant light and heat",
                    "score": 1.0,
                }
            ],
            "confidence": 0.8,
            "claims": [
                {
                    "text": f"{span_text}.",
                    "citation_chunk_ids": ["energy-000#c000"],
                    "spans": [
                        {
                            "chunk_id": "energy-000#c000",
                            "exact_text": span_text,
                        }
                    ],
                }
            ],
        }
    )
    payload = run_stress_eval(
        config,
        judge=KeywordJudge(),
        verifier=KeywordEntailmentJudge(),
        embed_fn=embed_fn,
        rerank_fn=_keep_order_rerank,
        model=mock_model_for_tests(v2_canned),
        meter_active=False,
    )
    # per-slice verdict breakdown, one entry per composition key
    assert set(payload["by_slice"]) == set(payload["composition"])
    for bucket in payload["by_slice"].values():
        assert bucket["n"] == sum(bucket["verdicts"].values())
        assert 0.0 <= bucket["correct_share"] <= 1.0
    # claim accounting over the verify reports (structured span path)
    accounting = payload["claim_accounting"]
    assert accounting is not None
    assert accounting["n_answers_verified"] >= 1
    assert accounting["n_drafted"] >= 1
    assert accounting["n_judged"] >= 1
    assert accounting["n_surviving"] >= 1
    assert accounting["n_mechanical_fail"] == 0
    assert accounting["mechanical_false_rejections"] == 0
    assert payload["budget_terminated"] == 0
    # audit run record: hash, thresholds, timestamp, cost
    run = payload["run"]
    assert run["questions_sha256"] and len(run["questions_sha256"]) == 64
    assert run["gate"]["min_coverage"] == config.evidence_gate.min_coverage
    assert run["verify"]["min_support"] == config.verify.min_support
    assert run["timestamp_utc"].endswith("+00:00")
    assert run["spend_usd"] == 0.0  # metering off in tests
    # traces carry the R6 gate fields
    traces = json.loads(
        (config.reports_dir / "question_traces_stress.json").read_text(encoding="utf-8")
    )
    for row in traces:
        assert "gate_coverage" in row and "budget_terminated" in row


def test_run_stress_eval_tagged_pass_writes_separate_artifacts(
    config: RAGConfig,
    articles: list[Article],
    embed_fn: EmbedFn,
    index_dir: Path,
) -> None:
    """A non-default sealed set (pass B) lands in its own traces + metrics key."""
    _seed(config, articles)
    config.retrieval_best = _chosen(config)
    set_b = config.corpus_path.parent / "golden_stress_b.json"
    set_b.write_text(
        json.dumps(
            [
                {
                    "question": "how do neural networks learn from data",
                    "relevant_titles": ["Machine learning"],
                    "category": "single_hop",
                    "expected_behavior": "answer",
                }
            ]
        ),
        encoding="utf-8",
    )
    payload = run_stress_eval(
        config,
        judge=KeywordJudge(),
        verifier=KeywordEntailmentJudge(),
        embed_fn=embed_fn,
        rerank_fn=_keep_order_rerank,
        model=mock_model_for_tests(CANNED_ANALYSIS_JSON),
        meter_active=False,
        questions_path=set_b,
        tag="_b",
    )
    assert payload["n_questions"] == 1
    assert payload["run"]["tag"] == "_b"
    metrics = json.loads((config.reports_dir / "metrics.json").read_text(encoding="utf-8"))
    # the tagged pass gets its own slot without touching the default key
    assert "stress_b" in metrics["detail"]
    assert "stress" not in metrics["detail"]
    tagged_traces = config.reports_dir / "question_traces_stress_b.json"
    assert tagged_traces.exists()
    assert not (config.reports_dir / "question_traces_stress.json").exists()
