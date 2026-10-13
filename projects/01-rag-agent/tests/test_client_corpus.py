"""Client-corpus onboarding: JSONL intake → contract → index → retrieval eval."""

import json
from pathlib import Path

import pytest
from rag_agent.config import RAGConfig
from rag_agent.corpus import (
    load_client_records,
    prepare_client_corpus,
    write_example_client_corpus,
)
from rag_agent.evaluate import first_relevant_rank, recall_at_k
from rag_agent.index import EmbedFn, Retriever, build_index, chunk_articles
from rag_agent.schemas import EvalQuestion


def test_example_client_corpus_roundtrip(config: RAGConfig, tmp_path: Path) -> None:
    client_dir = tmp_path / "client"
    path = write_example_client_corpus(client_dir)
    records = load_client_records(client_dir)
    assert len(records) == 3
    assert all({"title", "text"} <= set(r) for r in records)
    assert path.exists()


def test_prepare_client_corpus_contract(config: RAGConfig, tmp_path: Path) -> None:
    client_dir = tmp_path / "client"
    write_example_client_corpus(client_dir)
    contract = prepare_client_corpus(config, client_dir, license_name="MIT")
    assert contract.name == "client-corpus"
    assert contract.source == f"client://{client_dir}"
    assert contract.license == "MIT"
    assert contract.n_rows == 3
    # Contract artifact mirrors the model.
    persisted = json.loads(config.contract_path.read_text(encoding="utf-8"))
    assert persisted["checksum_sha256"] == contract.checksum_sha256


def test_prepare_client_corpus_requires_files(config: RAGConfig, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        prepare_client_corpus(config, empty, license_name="MIT")


def test_client_corpus_runs_through_index_and_eval(
    config: RAGConfig, tmp_path: Path, embed_fn: EmbedFn
) -> None:
    """The eval harness machinery works unchanged on a client corpus."""
    client_dir = tmp_path / "client"
    write_example_client_corpus(client_dir)
    prepare_client_corpus(config, client_dir, license_name="MIT")

    from rag_agent.corpus import load_corpus

    articles = load_corpus(config)
    assert len(articles) == 3
    chunks = chunk_articles(articles, size=50, overlap=10)
    index_dir = config.index_path(50)
    build_index(chunks, embed_fn, index_dir, description="client test")
    retriever = Retriever.from_index_dir(config, index_dir, embed_fn)

    question = EvalQuestion(
        question="how many requests per minute are free tier tokens allowed",
        relevant_article_ids=["api-000"],
    )
    citations = retriever.search(question.question, top_k=3)
    rank = first_relevant_rank(citations, question.relevant_article_ids)
    assert rank is not None  # the relevant client doc is retrieved within top-k
    assert recall_at_k([rank], 3) == 1.0
