"""Embedding, FAISS indexing and retrieval with cross-encoder reranking.

CPU-only by design (SLO: no GPU dependency). The embedding and rerank
functions are plain callables so tests can inject deterministic fakes without
downloading models (no network in tests). If the embedding model cannot be
downloaded/loaded, a loud :class:`EmbeddingModelError` is raised — there is no
silent degradation to keyword search.
"""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from portfolio_core.logging import get_logger
from pydantic import Field

from rag_agent.chunking import chunk_by_size, chunk_by_structure
from rag_agent.config import RAGConfig
from rag_agent.schemas import Article, Chunk, Citation

if TYPE_CHECKING:
    import faiss

logger = get_logger(__name__)


def _guard_torch_threads() -> None:
    """Pin torch to one intra-op thread when FAISS is (or will be) imported.

    ``faiss-cpu`` (OpenMP) and torch's parallel intra-op pool deadlock/segfault
    together on macOS ARM during batch encoding; a single torch thread avoids
    the nested OpenMP teams. Encoding stays fast enough (CPU-only SLO).
    """
    try:
        import torch

        torch.set_num_threads(1)
    except ImportError:  # pragma: no cover - torch always ships with sentence-transformers
        pass


EmbedFn = Callable[[Sequence[str]], np.ndarray]
RerankFn = Callable[[str, Sequence[str]], np.ndarray]

INDEX_FILE = "faiss.index"
CHUNKS_FILE = "chunks.jsonl"


class EmbeddingModelError(RuntimeError):
    """Embedding/reranker model unavailable — pipeline must fail loudly."""


class ChunkRecord(Chunk):
    """A chunk plus the metadata needed to render citations."""

    title: str = Field(min_length=1)
    topic: str = Field(min_length=1)


def chunk_articles(
    articles: Sequence[Article],
    size: int,
    overlap: int,
    chunk_mode: str = "size",
) -> list[ChunkRecord]:
    """Chunk every article at ``size``/``overlap`` and attach citation metadata.

    ``chunk_mode="structure"`` prefixes every chunk with the article title
    (entities retrieve far better when the name is in the chunk text; the
    corpus carries no section markers, verified across all articles).
    """
    records: list[ChunkRecord] = []
    for article in articles:
        if chunk_mode == "structure":
            chunks = chunk_by_structure(
                article.text, article.article_id, article.title, size=size, overlap=overlap
            )
        else:
            chunks = chunk_by_size(article.text, article.article_id, size=size, overlap=overlap)
        records.extend(
            ChunkRecord(
                chunk_id=c.chunk_id,
                article_id=c.article_id,
                text=c.text,
                token_count=c.token_count,
                title=article.title,
                topic=article.topic,
            )
            for c in chunks
        )
    return records


class SentenceTransformerEmbedder:
    """Lazy ``sentence-transformers`` embedder producing L2-normalized vectors."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - environment guard
                raise EmbeddingModelError(
                    "sentence-transformers is not installed; cannot build embeddings."
                ) from exc
            _guard_torch_threads()
            try:
                self._model = SentenceTransformer(self.model_name, device="cpu")
            except Exception as exc:  # broad: HF hub load failures vary; wrapped + chained
                raise EmbeddingModelError(
                    f"failed to load embedding model {self.model_name!r}: {exc}. "
                    "Check network access to huggingface.co (or HF_HOME/HF_HUB_OFFLINE)."
                ) from exc
        return self._model

    def __call__(self, texts: Sequence[str]) -> np.ndarray:
        model = self._load()
        vectors = model.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
        return np.asarray(vectors, dtype=np.float32)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"SentenceTransformerEmbedder({self.model_name!r})"


class CrossEncoderReranker:
    """Lazy cross-encoder reranker scoring (query, passage) pairs."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:  # pragma: no cover - environment guard
                raise EmbeddingModelError(
                    "sentence-transformers is not installed; cannot build reranker."
                ) from exc
            _guard_torch_threads()
            try:
                self._model = CrossEncoder(self.model_name, device="cpu")
            except Exception as exc:  # broad: HF hub load failures vary; wrapped + chained
                raise EmbeddingModelError(
                    f"failed to load reranker model {self.model_name!r}: {exc}. "
                    "Check network access to huggingface.co."
                ) from exc
        return self._model

    def __call__(self, query: str, texts: Sequence[str]) -> np.ndarray:
        model = self._load()
        pairs = [(query, text) for text in texts]
        scores = model.predict(pairs)
        return np.asarray(scores, dtype=np.float32)


def build_index(
    chunks: Sequence[ChunkRecord], embed_fn: EmbedFn, out_dir: Path, description: str = ""
) -> Path:
    """Embed ``chunks`` and persist a FAISS ``IndexFlatIP`` + metadata to ``out_dir``."""
    import faiss

    out_dir.mkdir(parents=True, exist_ok=True)
    texts = [c.text for c in chunks]
    logger.info("embedding %d chunks (%s) ...", len(texts), description or out_dir.name)
    vectors = np.ascontiguousarray(embed_fn(texts), dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
        raise ValueError(f"embed_fn returned shape {vectors.shape}, expected ({len(chunks)}, dim)")
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(out_dir / INDEX_FILE))
    with (out_dir / CHUNKS_FILE).open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(chunk.model_dump_json() + "\n")
    logger.info("index written: %s (%d vectors, dim=%d)", out_dir, index.ntotal, vectors.shape[1])
    return out_dir / INDEX_FILE


def load_index(index_dir: Path) -> "tuple[faiss.Index, list[ChunkRecord]]":
    """Load a persisted index and its chunk metadata (order-aligned with ids)."""
    import faiss

    index = faiss.read_index(str(index_dir / INDEX_FILE))
    with (index_dir / CHUNKS_FILE).open(encoding="utf-8") as fh:
        chunks = [ChunkRecord.model_validate_json(line) for line in fh if line.strip()]
    if index.ntotal != len(chunks):
        raise ValueError(
            f"index/chunks mismatch in {index_dir}: ntotal={index.ntotal} chunks={len(chunks)}"
        )
    return index, chunks


class Retriever:
    """Embed the query, search FAISS, optionally rerank, return citations."""

    def __init__(
        self,
        config: RAGConfig,
        index: "faiss.Index",
        chunks: Sequence[ChunkRecord],
        embed_fn: EmbedFn,
        rerank_fn: RerankFn | None = None,
        query_embed_fn: EmbedFn | None = None,
    ) -> None:
        self.config = config
        self.index = index
        self.chunks = list(chunks)
        self.embed_fn = embed_fn
        self.rerank_fn = rerank_fn
        # Some encoders (e.g. BGE) require an instruction prefix on queries
        # but not on indexed passages — hence a separate query encoder.
        self.query_embed_fn = query_embed_fn or embed_fn
        self._by_id = {c.chunk_id: c for c in self.chunks}
        # Lazy hybrid fusion index (built only when fusion_rrf is enabled).
        self._bm25: Any = None

    def _bm25_index(self) -> Any:
        if self._bm25 is None:
            from rag_agent.lexical import Bm25Index

            self._bm25 = Bm25Index(self.chunks)
        return self._bm25

    @classmethod
    def from_index_dir(
        cls,
        config: RAGConfig,
        index_dir: Path,
        embed_fn: EmbedFn,
        rerank_fn: RerankFn | None = None,
        query_embed_fn: EmbedFn | None = None,
    ) -> "Retriever":
        index, chunks = load_index(index_dir)
        return cls(config, index, chunks, embed_fn, rerank_fn, query_embed_fn)

    def get_chunk(self, chunk_id: str) -> ChunkRecord | None:
        return self._by_id.get(chunk_id)

    def _embed_query(self, query: str) -> np.ndarray:
        try:
            vector = np.asarray(self.query_embed_fn([query]), dtype=np.float32)
        except EmbeddingModelError:
            raise
        except Exception as exc:  # broad: embed call failures vary; wrapped + chained
            raise EmbeddingModelError(f"embedding the query failed: {exc}") from exc
        if vector.ndim != 2 or vector.shape[0] != 1:
            raise EmbeddingModelError(f"embed_fn returned shape {vector.shape}, expected (1, dim)")
        return vector

    def search(self, query: str, top_k: int | None = None) -> list[Citation]:
        """Return the ``top_k`` most relevant citations for ``query``.

        Candidate pipeline: dense FAISS top-``n_candidates`` (or an RRF fusion
        of dense + BM25 over ``rrf_pool_size`` when ``config.fusion_rrf``),
        optional cross-encoder rerank, then the per-article diversity cap
        with score-order backfill when ``config.max_per_article`` is set.
        """
        k = top_k or self.config.top_k
        n_candidates = min(len(self.chunks), k * self.config.rerank_multiplier)
        vector = self._embed_query(query)

        if self.config.fusion_rrf:
            from rag_agent.lexical import reciprocal_rank_fusion

            pool = min(len(self.chunks), max(n_candidates, self.config.rrf_pool_size))
            _, dense_ids = self.index.search(vector, pool)
            dense = [self.chunks[int(i)].chunk_id for i in dense_ids[0] if int(i) >= 0]
            bm25 = self._bm25_index().ranking(query)[:pool]
            fused = reciprocal_rank_fusion([dense, bm25], k=60)
            candidates = [self._by_id[cid] for cid in fused[:n_candidates] if cid in self._by_id]
        else:
            _, ids = self.index.search(vector, n_candidates)
            candidates = [self.chunks[int(i)] for i in ids[0] if int(i) >= 0]

        if self.rerank_fn is not None and len(candidates) > k:
            scores = np.asarray(
                self.rerank_fn(query, [c.text for c in candidates]), dtype=np.float32
            )
            order = np.argsort(-scores)
            candidates = [candidates[int(i)] for i in order]

        if self.config.max_per_article and self.config.max_per_article > 0:
            candidates = self._cap_per_article(candidates, k)

        return [self._to_citation(c) for c in candidates[:k]]

    def _cap_per_article(self, candidates: list[ChunkRecord], k: int) -> list[ChunkRecord]:
        """Per-article diversity cap with score-order backfill.

        Accept chunks in reranked (score) order while an article is under the
        cap; overflow chunks are deferred. If fewer than ``k`` were selected,
        backfill from the deferred list in score order up to ``k`` so the
        answer context always reaches the requested depth.
        """
        cap = self.config.max_per_article
        if cap is None or cap < 1:
            return candidates
        counts: dict[str, int] = {}
        selected: list[ChunkRecord] = []
        deferred: list[ChunkRecord] = []
        for chunk in candidates:
            if counts.get(chunk.article_id, 0) < cap:
                selected.append(chunk)
                counts[chunk.article_id] = counts.get(chunk.article_id, 0) + 1
            else:
                deferred.append(chunk)
        if len(selected) < k:
            selected.extend(deferred[: k - len(selected)])
        return selected

    def _to_citation(self, chunk: ChunkRecord) -> Citation:
        excerpt = chunk.text[: self.config.excerpt_chars].strip()
        if len(chunk.text) > self.config.excerpt_chars:
            excerpt = excerpt.rsplit(" ", 1)[0] + " …"
        return Citation(
            chunk_id=chunk.chunk_id,
            article_id=chunk.article_id,
            title=chunk.title,
            excerpt=excerpt,
            score=1.0,  # score is informational; ranking is what matters downstream
        )
