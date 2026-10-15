"""RAGAS evaluation on the graded question set, scored by the LOCAL model.

The evaluator LLM is the same provider the agent uses (env-configured
OpenAI-compatible endpoint, else local Ollama — default ``qwen3:32b``), so the
RAGAS run costs $0 in API calls. Embeddings for ``answer_relevancy`` come from
the project's MiniLM encoder, not an external API.

RAGAS needs LangChain-facing wrappers; ``langchain_openai.ChatOpenAI`` points
at the same OpenAI-compatible endpoints pydantic-ai uses, so no extra
infrastructure is required.
"""

import os
from dataclasses import dataclass, field
from typing import Any

from portfolio_core.config import Settings, get_settings
from portfolio_core.llm import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL
from portfolio_core.logging import get_logger

from rag_agent.config import RAGConfig

logger = get_logger(__name__)


@dataclass
class RagasRow:
    """One sample in RAGAS shape (snake_case column names)."""

    question: str
    answer: str
    contexts: list[str] = field(default_factory=list)
    reference: str = ""


def to_ragas_dicts(rows: list[RagasRow]) -> list[dict[str, Any]]:
    """Convert rows to RAGAS ``EvaluationDataset`` column mapping."""
    return [
        {
            "user_input": r.question,
            "response": r.answer,
            "retrieved_contexts": r.contexts,
            "reference": r.reference,
        }
        for r in rows
    ]


def _settings_or_default() -> Settings:
    return get_settings()


def langchain_chat_model() -> Any:  # langchain_openai.ChatOpenAI (untyped lib)
    """Chat model for the RAGAS evaluator: env provider first, else local Ollama."""
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr

    s = _settings_or_default()
    if s.llm_api_key and s.llm_base_url:
        return ChatOpenAI(
            base_url=s.llm_base_url,
            api_key=SecretStr(s.llm_api_key),
            model=s.llm_model or "kimi-k2-0711-preview",
            temperature=0,
        )
    base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    return ChatOpenAI(
        base_url=base_url,
        api_key=SecretStr("ollama"),
        model=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        temperature=0,
        extra_body={"think": False},  # qwen3 thinking off: ~4x faster judging
    )


class MiniLMEmbeddings:
    """LangChain-embeddings protocol over the project's MiniLM encoder."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._embedder: Any = None

    def _load(self) -> Any:  # sentence_transformers.SentenceTransformer
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(self._model_name, device="cpu")
        return self._embedder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
        return [list(map(float, row)) for row in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def run_ragas(config: RAGConfig, rows: list[RagasRow]) -> dict[str, float]:
    """Compute the RAGAS metric set on the eval rows with the local evaluator.

    Metrics: faithfulness, answer_relevancy, context_precision, context_recall.
    ``reference`` for context_recall is the graded relevant article's lead
    (synthesized upstream from the corpus, not from the answer).
    """
    if not rows:
        raise ValueError("no RAGAS rows provided")
    from ragas import evaluate as ragas_evaluate  # type: ignore[import-untyped]
    from ragas.embeddings import LangchainEmbeddingsWrapper  # type: ignore[import-untyped]
    from ragas.evaluation import EvaluationDataset  # type: ignore[import-untyped]
    from ragas.llms import LangchainLLMWrapper  # type: ignore[import-untyped]
    from ragas.metrics import (  # type: ignore[import-untyped]
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )
    from ragas.run_config import RunConfig  # type: ignore[import-untyped]

    dataset = EvaluationDataset.from_list(to_ragas_dicts(rows))
    # Local 32B calls can take minutes; default 60 s per-metric timeout is too
    # tight. Two workers: parallel enough to overlap short verdicts, gentle
    # enough for one memory-bandwidth-bound Ollama instance.
    run_config = RunConfig(timeout=900, max_workers=4, max_retries=3, seed=config.seed)
    result = ragas_evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=LangchainLLMWrapper(langchain_chat_model()),
        embeddings=LangchainEmbeddingsWrapper(MiniLMEmbeddings(config.embedding_model)),
        run_config=run_config,
        raise_exceptions=False,
    )
    # EvaluationResult exposes per-row lists via __getitem__; aggregate here,
    # skipping NaN rows (raise_exceptions=False marks failed samples NaN).
    metric_names = [
        m.name for m in [faithfulness, answer_relevancy, context_precision, context_recall]
    ]
    scores: dict[str, float] = {}
    for name in metric_names:
        values = [float(v) for v in result[name] if v == v]  # v != v filters NaN
        scores[name] = round(sum(values) / len(values), 4) if values else float("nan")
    logger.info("RAGAS: %s", scores)
    return scores
