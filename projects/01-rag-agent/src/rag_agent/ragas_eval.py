"""RAGAS evaluation on the graded question set, scored by the active provider.

The evaluator LLM is the same provider the agent uses (env-configured
OpenAI-compatible endpoint, else local Ollama — default ``qwen3.6:35b-a3b-q4_K_M``).
Embeddings for ``answer_relevancy`` come from the project's MiniLM encoder, not
an external API.

RAGAS needs LangChain-facing wrappers; ``langchain_openai.ChatOpenAI`` points
at the same OpenAI-compatible endpoints pydantic-ai uses, so no extra
infrastructure is required. Two provider caveats are handled in
:class:`MeteredChatOpenAI`:

- **temperature** — RAGAS mutates ``llm.temperature`` per call, but the hosted
  Kimi coding endpoint fixes sampling server-side and rejects any explicit
  value, so every ``generate_prompt`` call resets it to ``None`` (omitted from
  the request).
- **spend metering** — per-call token usage is read from the returned
  ``LLMResult.llm_output["token_usage"]`` and metered into the "ragas" phase.
  RAGAS's own cost callbacks only recognize genuine OpenAI clients, not this
  OpenAI-compatible endpoint, so metering at this wrapped-call boundary is the
  reliable source (thinking stays disabled via ``extra_body`` here, unlike the
  pydantic-ai phases, so reasoning-token burn is already avoided).
"""

import os
from dataclasses import dataclass, field
from typing import Any

from portfolio_core.config import Settings, get_settings
from portfolio_core.llm import DEFAULT_OLLAMA_BASE_URL, DEFAULT_OLLAMA_MODEL
from portfolio_core.logging import get_logger

from rag_agent.config import RAGConfig
from rag_agent.metering import get_meter

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


def _metered_chat_openai_class() -> Any:
    """``ChatOpenAI`` subclass that meters usage and neutralizes temperature.

    Defined in a factory because ``langchain_openai`` is an optional import at
    module scope in some environments; the class is created once.
    """
    from langchain_openai import ChatOpenAI

    class _MeteredChatOpenAI(ChatOpenAI):
        """ChatOpenAI that (a) never sends an explicit temperature and (b)
        meters per-call token usage into the "ragas" phase."""

        def _neutralize_sampling(self) -> None:
            # RAGAS sets .temperature (and .n) on the model before each call;
            # the hosted endpoint rejects explicit sampling params, so drop them.
            self.temperature = None
            self.n = 1

        def generate_prompt(self, prompts: Any, **kwargs: Any) -> Any:  # type: ignore[override]
            self._neutralize_sampling()
            result = super().generate_prompt(prompts, **kwargs)
            _meter_llm_result(result)
            return result

        async def agenerate_prompt(self, prompts: Any, **kwargs: Any) -> Any:  # type: ignore[override]
            self._neutralize_sampling()
            result = await super().agenerate_prompt(prompts, **kwargs)
            _meter_llm_result(result)
            return result

    return _MeteredChatOpenAI


def _meter_llm_result(result: Any) -> None:
    """Meter one langchain ``LLMResult`` via its ``token_usage`` llm_output."""
    llm_output = getattr(result, "llm_output", None) or {}
    token_usage = llm_output.get("token_usage") if isinstance(llm_output, dict) else None
    if not token_usage:
        return
    get_meter().record("ragas", _usage_from_openai_dict(token_usage))


def _usage_from_openai_dict(token_usage: dict[str, Any]) -> Any:
    """Duck-typed usage object the platform meter understands (cached reads incl.)."""
    from types import SimpleNamespace

    details = token_usage.get("prompt_tokens_details") or {}
    return SimpleNamespace(
        input_tokens=token_usage.get("prompt_tokens") or token_usage.get("input_tokens") or 0,
        output_tokens=token_usage.get("completion_tokens") or token_usage.get("output_tokens") or 0,
        prompt_tokens_details=SimpleNamespace(
            cached_tokens=details.get("cached_tokens") or details.get("cache_read") or 0
        ),
    )


def langchain_chat_model() -> Any:  # langchain_openai.ChatOpenAI (untyped lib)
    """Chat model for the RAGAS evaluator: env provider first, else local Ollama.

    Hosted: thinking disabled via ``extra_body`` (the pydantic-ai phases use the
    platform ``hosted_model_settings`` preset; RAGAS speaks langchain, so the
    same body is set here) and NO temperature — the endpoint rejects explicit
    sampling values, and :class:`MeteredChatOpenAI` enforces omission per call.
    Local: qwen3 thinking off via the documented ``think: False`` extra body.
    """
    from pydantic import SecretStr

    s = _settings_or_default()
    cls = _metered_chat_openai_class()
    if s.llm_api_key and s.llm_base_url:
        return cls(
            base_url=s.llm_base_url,
            api_key=SecretStr(s.llm_api_key),
            model=s.llm_model or "kimi-k2-0711-preview",
            extra_body={"thinking": {"type": "disabled"}},
        )
    base_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    return cls(
        base_url=base_url,
        api_key=SecretStr("ollama"),
        model=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
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
    """Compute the RAGAS metric set on the eval rows with the active provider.

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
