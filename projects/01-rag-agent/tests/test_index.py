"""Index + retriever tests against a tiny in-memory FAISS index (fake embeddings)."""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest
from rag_agent.config import RAGConfig
from rag_agent.index import (
    EmbeddingModelError,
    EmbedFn,
    Retriever,
    build_index,
    chunk_articles,
    load_index,
)
from rag_agent.schemas import Article, Citation


def test_chunk_articles_attaches_metadata(articles: list[Article]) -> None:
    chunks = chunk_articles(articles, size=50, overlap=10)
    assert len(chunks) > len(articles)  # articles exceed 50 tokens -> several chunks each
    assert all(c.title and c.topic for c in chunks)
    by_article = {c.article_id for c in chunks}
    assert by_article == {a.article_id for a in articles}
    # ids deterministic: chunk sequence starts at c000 per article
    assert any(c.chunk_id.endswith("#c000") for c in chunks)


def test_build_and_load_index_roundtrip(
    config: RAGConfig, articles: list[Article], embed_fn: EmbedFn, index_dir: Path
) -> None:
    index, chunks = load_index(index_dir)
    assert index.ntotal == len(chunks) > 0
    assert chunks[0].title == articles[0].title


def test_build_index_rejects_bad_embedding_shape(
    config: RAGConfig, articles: list[Article]
) -> None:
    def bad_embed(texts: Sequence[str]) -> np.ndarray:
        return np.zeros((1, 8), dtype=np.float32)  # wrong row count whatever the input

    chunks = chunk_articles(articles[:1], size=50, overlap=10)
    with pytest.raises(ValueError, match="expected"):
        build_index(chunks, bad_embed, config.index_path(50))


def test_search_returns_typed_citations(retriever: Retriever) -> None:
    citations = retriever.search("how do solar panels generate electricity?", top_k=3)
    assert len(citations) == 3
    assert all(isinstance(c, Citation) for c in citations)
    assert all(c.excerpt and c.title and c.chunk_id for c in citations)
    # excerpt truncation adds an ellipsis marker when the chunk is longer
    assert all(len(c.excerpt) <= config_excerpt_limit() for c in citations)


def config_excerpt_limit() -> int:
    from rag_agent.config import RAGConfig

    return RAGConfig().excerpt_chars + 10  # rsplit + " …" slack


def test_search_finds_relevant_article(retriever: Retriever) -> None:
    citations = retriever.search("why do plants appear green chlorophyll", top_k=3)
    assert any(c.article_id == "photo-000" for c in citations)


def test_rerank_fn_controls_order(config: RAGConfig, index_dir: Path, embed_fn: EmbedFn) -> None:
    def length_rerank(query: str, texts: Sequence[str]) -> np.ndarray:
        return np.array([float(len(t)) for t in texts], dtype=np.float32)

    retriever = Retriever.from_index_dir(config, index_dir, embed_fn, length_rerank)
    citations = retriever.search("anything at all", top_k=3)
    resolved = [retriever.get_chunk(c.chunk_id) for c in citations]
    assert all(chunk is not None for chunk in resolved)
    lengths = [len(chunk.text) for chunk in resolved if chunk is not None]
    assert lengths == sorted(lengths, reverse=True)


def test_get_chunk_unknown_id_returns_none(retriever: Retriever) -> None:
    assert retriever.get_chunk("nope#c999") is None
    known = retriever.chunks[0]
    assert retriever.get_chunk(known.chunk_id) == known


def test_failing_embed_fn_raises_loudly(config: RAGConfig, index_dir: Path) -> None:
    def broken_embed(texts: Sequence[str]) -> np.ndarray:
        raise RuntimeError("network is down")

    retriever = Retriever.from_index_dir(config, index_dir, broken_embed)
    with pytest.raises(EmbeddingModelError, match="embedding"):
        retriever.search("query")


def test_embed_fn_shape_mismatch_raises_loudly(config: RAGConfig, index_dir: Path) -> None:
    def bad_shape_embed(texts: Sequence[str]) -> np.ndarray:
        return np.zeros((3, 4), dtype=np.float32)

    retriever = Retriever.from_index_dir(config, index_dir, bad_shape_embed)
    with pytest.raises(EmbeddingModelError, match="shape"):
        retriever.search("query")
