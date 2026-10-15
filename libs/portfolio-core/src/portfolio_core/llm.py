"""LLM provider factory (ADR-0004, amended wave 10).

Production priority:
1. Configured OpenAI-compatible endpoint via env (``LLM_BASE_URL``/``LLM_API_KEY``,
   e.g. Kimi/Moonshot) — unchanged.
2. **Local Ollama** (default): ``OLLAMA_MODEL`` (default ``qwen3:32b``) against
   ``OLLAMA_BASE_URL`` (default ``http://localhost:11434/v1``). Local-first:
   $0 API cost, data never leaves the machine, structured-output support on
   self-hosted Ollama.

The deterministic mock is REMOVED from production paths — it survives only as
pydantic-ai ``FunctionModel`` helpers for unit tests (``mock_model_for_tests``).
Projects must not ship mock fallbacks in runtime code (owner directive, wave 10).
"""

from typing import Any

from portfolio_core.config import Settings


class LLMProviderUnavailableError(RuntimeError):
    """No LLM provider available (no env credentials, Ollama not running)."""


DEFAULT_OLLAMA_MODEL = "qwen3.6:35b-a3b-q4_K_M"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"


def ollama_available(base_url: str = "http://localhost:11434") -> bool:
    """True when a local Ollama server answers /api/tags."""
    try:
        import httpx

        r = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        return r.status_code == 200
    except Exception:
        return False


def build_model(settings: Settings | None = None) -> Any:
    """Return a pydantic-ai ``Model``: env-configured provider, else local Ollama.

    Raises :class:`LLMProviderUnavailableError` with actionable guidance when
    neither is available.
    """
    from portfolio_core.config import get_settings

    s = settings or get_settings()
    if s.llm_api_key and s.llm_base_url:
        import httpx
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        http_client = httpx.AsyncClient(timeout=s.llm_timeout)
        provider = OpenAIProvider(
            base_url=s.llm_base_url, api_key=s.llm_api_key, http_client=http_client
        )
        return OpenAIChatModel(model_name=s.llm_model or "kimi-k2-0711-preview", provider=provider)

    import os

    ollama_base = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    if ollama_available(ollama_base.removesuffix("/v1")):
        import httpx
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.ollama import OllamaProvider

        model_name = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        # Explicit timeout + minimal retries: local inference can stall under
        # load; fail in <3 min and let callers retry, never hang indefinitely.
        ollama_http = httpx.AsyncClient(timeout=180.0)
        ollama_provider = OllamaProvider(
            base_url=ollama_base, api_key="ollama", http_client=ollama_http
        )
        return OpenAIChatModel(model_name=model_name, provider=ollama_provider)

    raise LLMProviderUnavailableError(
        "No LLM provider available. Either start Ollama (https://ollama.com) and "
        "`ollama pull qwen3:32b`, or set LLM_BASE_URL + LLM_API_KEY in .env "
        "(see .env.example). Mock providers are test-only and intentionally not "
        "available at runtime."
    )


def mock_model_for_tests(response: str) -> Any:
    """Deterministic FunctionModel for UNIT TESTS ONLY — never wire into runtime code."""
    from collections.abc import AsyncIterator

    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel

    def _respond(messages: list[Any], info: Any) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=response)])

    async def _stream(messages: list[Any], info: Any) -> AsyncIterator[str]:
        yield response

    return FunctionModel(_respond, stream_function=_stream)
