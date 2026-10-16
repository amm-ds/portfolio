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


@dataclass
class RagasResult:
    """RAGAS aggregates plus the per-row scores used for bootstrap CIs."""

    scores: dict[str, float]
    per_row: dict[str, list[float]]


def run_ragas(config: RAGConfig, rows: list[RagasRow]) -> RagasResult:
    """Compute the RAGAS metric set on the eval rows with the local evaluator.

    Metrics: faithfulness, answer_relevancy, context_precision, context_recall.
    ``reference`` for context_recall is the graded relevant article's lead
    (synthesized upstream from the corpus, not from the answer).
    """
    if not rows:
        raise ValueError("no RAGAS rows provided")
    # ragas ships no type stubs: mypy reports the untyped module once per file,
    # so a single bare ignore on this combined import covers all submodules.
    from ragas import embeddings, evaluate, evaluation, llms, metrics, run_config  # type: ignore

    dataset = evaluation.EvaluationDataset.from_list(to_ragas_dicts(rows))
    # Local model calls can take minutes; default 60 s per-metric timeout is
    # too tight. Four workers overlap short verdicts without thrashing one
    # memory-bandwidth-bound Ollama instance.
    run_cfg = run_config.RunConfig(timeout=900, max_workers=4, max_retries=3, seed=config.seed)
    result = evaluate(
        dataset,
        metrics=[
            metrics.faithfulness,
            metrics.answer_relevancy,
            metrics.context_precision,
            metrics.context_recall,
        ],
        llm=llms.LangchainLLMWrapper(langchain_chat_model()),
        embeddings=embeddings.LangchainEmbeddingsWrapper(MiniLMEmbeddings(config.embedding_model)),
        run_config=run_cfg,
        raise_exceptions=False,
    )
    # EvaluationResult exposes per-row lists via __getitem__; aggregate here,
    # skipping NaN rows (raise_exceptions=False marks failed samples NaN).
    metric_names = [
        metrics.faithfulness.name,
        metrics.answer_relevancy.name,
        metrics.context_precision.name,
        metrics.context_recall.name,
    ]
    scores: dict[str, float] = {}
    per_row: dict[str, list[float]] = {}
    for name in metric_names:
        row_values = [float(v) for v in result[name]]
        per_row[name] = row_values
        values = [v for v in row_values if v == v]  # v != v filters NaN
        scores[name] = round(sum(values) / len(values), 4) if values else float("nan")
    logger.info("RAGAS: %s", scores)
    return RagasResult(scores=scores, per_row=per_row)


def ensure_ragas_importable() -> str:
    """Eager import guard: fail fast (with version) if the venv is pruned mid-run."""
    from ragas import __version__ as ragas_version

    return str(ragas_version)
