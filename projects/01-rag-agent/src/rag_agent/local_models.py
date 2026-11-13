"""Local Ollama model adapters (R7): embedding + reranking for the tournament.

Both are plain callables matching the project's ``EmbedFn`` / ``RerankFn``
protocols, so they slot into the existing retriever machinery unchanged.
Local inference only — no hosted spend. Models must be pulled first
(``ollama pull qwen3-embedding:0.6b`` / ``qwen3-reranker:0.6b``).
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Sequence
from typing import Any

import numpy as np

DEFAULT_BASE_URL = "http://127.0.0.1:11434"


class OllamaError(RuntimeError):
    """The local Ollama API is unreachable or returned an error."""


def _post(
    base_url: str, path: str, payload: dict[str, Any], timeout: float = 300.0
) -> dict[Any, Any]:
    req = urllib.request.Request(  # noqa: S310 - base_url defaults to localhost
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - localhost API only
            req, timeout=timeout
        ) as resp:
            return json.loads(resp.read().decode())  # type: ignore[no-any-return]
    except Exception as exc:  # broad: uniform local-API error
        raise OllamaError(f"ollama {path} failed: {exc}") from exc


class OllamaEmbedder:
    """``EmbedFn`` over Ollama's /api/embed (Qwen3-Embedding-0.6B and friends)."""

    def __init__(
        self, model: str = "qwen3-embedding:0.6b", base_url: str = DEFAULT_BASE_URL
    ) -> None:
        self.model = model
        self.base_url = base_url

    def __call__(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        try:
            return self._embed(list(texts))
        except OllamaError:
            # Some registries reject larger batches (observed: intermittent
            # 400s at batch 32 on ollama 0.40): halve and retry.
            if len(texts) <= 1:
                raise
            mid = len(texts) // 2
            return np.vstack([self.__call__(texts[:mid]), self.__call__(texts[mid:])])

    def _embed(self, texts: list[str]) -> np.ndarray:
        data = _post(self.base_url, "/api/embed", {"model": self.model, "input": texts})
        vectors = np.asarray(data["embeddings"], dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized: np.ndarray = np.divide(vectors, norms)
        return normalized


class OllamaReranker:
    """``RerankFn`` over Ollama's /api/rerank.

    NOTE (R7): qwen3-reranker is not in the Ollama model registry (404) as of
    this writing — use :class:`HfQwenReranker` for Qwen3-Reranker-0.6B. This
    adapter stays for registries that do serve reranker models.
    """

    def __init__(
        self, model: str = "qwen3-reranker:0.6b", base_url: str = DEFAULT_BASE_URL
    ) -> None:
        self.model = model
        self.base_url = base_url

    def __call__(self, query: str, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros(0, dtype=np.float32)
        data = _post(
            self.base_url,
            "/api/rerank",
            {"model": self.model, "query": query, "documents": list(texts)},
        )
        scores = {item["index"]: float(item["relevance_score"]) for item in data["results"]}
        out: np.ndarray = np.asarray(
            [scores.get(i, float("-inf")) for i in range(len(texts))], dtype=np.float32
        )
        return out


class HfQwenReranker:
    """``RerankFn`` for Qwen/Qwen3-Reranker-0.6B via sentence-transformers.

    The Ollama registry does not carry this model (verified 2026-11-13), so
    the local arm runs the official HF cross-encoder instead. First load
    downloads ~1.2GB; afterwards it is fully local.
    """

    def __init__(self, model: str = "Qwen/Qwen3-Reranker-0.6B") -> None:
        from sentence_transformers import CrossEncoder

        self._ce = CrossEncoder(model, trust_remote_code=True)

    def __call__(self, query: str, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            return np.zeros(0, dtype=np.float32)
        pairs = [(query, text) for text in texts]
        scores = self._ce.predict(pairs)
        out: np.ndarray = np.asarray(scores, dtype=np.float32)
        return out


def ollama_available(base_url: str = DEFAULT_BASE_URL) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=5) as resp:  # noqa: S310
            return bool(resp.status == 200)
    except OSError:
        return False
