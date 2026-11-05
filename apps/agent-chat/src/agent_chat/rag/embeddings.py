"""The Embedder protocol and its two shipped implementations.

``Embedder`` is the seam an adopter replaces to plug in any embedding service.
The default is a local MiniLM (sentence-transformers — install the
``embeddings`` extra); a deterministic hashing embedder needs no dependencies
and keeps the template runnable end-to-end without torch.
"""

import asyncio
import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

from agent_chat.config import Settings

_WORD_RE = re.compile(r"[a-z0-9]+")

MINILM_DIM = 384


class Embedder(Protocol):
    """Turn texts into dense vectors. ``dim`` must match the vector store."""

    @property
    def dim(self) -> int: ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class MiniLMEmbedder:
    """Local ``sentence-transformers/all-MiniLM-L6-v2`` (384-dim, on CPU).

    Import is lazy and guarded so the base install stays light; install with
    ``uv sync --extra embeddings`` (or set ``AGENT_CHAT_EMBEDDER=hashing``).
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise RuntimeError(
                "MiniLMEmbedder needs the embeddings extra: uv sync --extra embeddings, "
                "or set AGENT_CHAT_EMBEDDER=hashing"
            ) from exc
        self._model = SentenceTransformer(model_name)

    @property
    def dim(self) -> int:
        return MINILM_DIM

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = await asyncio.to_thread(self._model.encode, list(texts))
        return [list(map(float, row)) for row in vectors]


class HashingEmbedder:
    """Deterministic bag-of-words hashing into ``dim`` dimensions.

    Not semantic — it ranks by lexical overlap. It exists so ingest, the
    retrieve tool, and the whole stack run with zero model downloads (tests
    and the docker quickstart use it). Adopters switch to MiniLM in prod.
    """

    def __init__(self, dim: int = MINILM_DIM) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        for token in _WORD_RE.findall(text.lower()):
            # crude suffix stemming so "refunds" matches "refund" — lexical,
            # not semantic; MiniLM is the semantic path.
            if len(token) > 3 and token.endswith("s"):
                token = token[:-1]
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm > 0 else vector


def build_embedder(settings: Settings) -> Embedder:
    """Resolve the configured embedder."""
    if settings.embedder == "hashing":
        return HashingEmbedder()
    return MiniLMEmbedder(settings.embedding_model)
