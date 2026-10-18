"""Cross-project document retrieval: 09's ``search_documents`` over 01's corpus.

The roadmap's real-data arm: the research toolset gains a retrieval tool that
queries project 01's Wikipedia slice **read-only** — the FAISS index and chunk
metadata already materialized under ``projects/01-rag-agent/data/index/``. The
heavy lifting (index loading, embedding, ranking) is imported from
``rag_agent.index`` as a workspace dependency; nothing here re-indexes or
writes to 01's data directory.

Production retrieval config (01's HPO sweep winner, mirrored in its
``params.yaml``): all-MiniLM-L6-v2 embeddings, 200-token chunks, top-3 without
reranking for this tool (the workflow re-checks facts downstream anyway).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from portfolio_core.logging import get_logger

if TYPE_CHECKING:
    from rag_agent.index import Retriever

logger = get_logger(__name__)

# src/agentic_workflows/documents.py → project dir → projects/ → repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# 01's production index (chunks_200, all-MiniLM-L6-v2 per its params.yaml
# retrieval_best); read-only — this module never writes under 01's data dir.
DEFAULT_INDEX_DIR = _REPO_ROOT / "01-rag-agent" / "data" / "index" / "chunks_200"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 3


@lru_cache(maxsize=4)
def get_retriever(index_dir: Path | None = None) -> Retriever:
    """Load 01's persisted FAISS index + chunk metadata and build a Retriever.

    Cached per directory; the embedding model loads lazily on first query.
    Raises when the index is missing or the embedding model cannot load —
    there is no silent fallback to keyword search (01's EmbeddingModelError
    contract, ADR: fail loudly).
    """
    from rag_agent.config import RAGConfig
    from rag_agent.index import Retriever, SentenceTransformerEmbedder, load_index

    resolved = Path(index_dir) if index_dir is not None else DEFAULT_INDEX_DIR
    index, chunks = load_index(resolved)
    logger.info("loaded 01 corpus index: %s (%d chunks)", resolved, len(chunks))
    return Retriever(
        # 600-char excerpts: the tool answers multi-hop questions from two
        # chunks, so each snippet must carry its full key fact (200-token
        # chunks run ~1,300 chars; 600 covers the lead + first fact).
        RAGConfig(top_k=TOP_K, excerpt_chars=600),
        index,
        chunks,
        SentenceTransformerEmbedder(EMBEDDING_MODEL),
    )


def search_documents(query: str, top_k: int = TOP_K) -> list[str]:
    """Search the Wikipedia document corpus shared with project 01 (read-only).

    Dense retrieval over the FAISS index built by 01's RAG pipeline: the query
    is embedded with the same model that indexed the chunks, ranked by inner
    product, returned as formatted snippets "title — excerpt" with the chunk
    id, best match first. Use ONLY for questions about the Wikipedia document
    corpus; Atlas Valley station facts live in ``search_handbook``.

    Args:
        query: Natural-language question or topic.
        top_k: Maximum number of snippets to return (1-5).

    Returns:
        Formatted snippets with chunk ids, best match first.
    """
    k = max(1, min(top_k, 5))
    retriever = get_retriever()
    citations = retriever.search(query, top_k=k)
    return [f"{c.chunk_id} | {c.title} — {c.excerpt}" for c in citations]


def corpus_stats() -> dict[str, Any]:
    """Metadata about the loaded corpus (index size), for docs and tests."""
    retriever = get_retriever()
    return {
        "index_dir": str(DEFAULT_INDEX_DIR),
        "n_chunks": len(retriever.chunks),
        "top_k": TOP_K,
        "embedding_model": EMBEDDING_MODEL,
    }
