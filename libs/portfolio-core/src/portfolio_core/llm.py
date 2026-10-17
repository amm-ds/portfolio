"""LLM provider factory (ADR-0004, amended wave 10).

Production priority:
1. Configured OpenAI-compatible endpoint via env (``LLM_BASE_URL``/``LLM_API_KEY``,
   e.g. Kimi/Moonshot) — unchanged.
2. **Local Ollama** (default): ``OLLAMA_MODEL`` (default ``qwen3.6:35b-a3b-q4_K_M``)
   against ``OLLAMA_BASE_URL`` (default ``http://localhost:11434/v1``). Local-first:
   $0 API cost, data never leaves the machine, structured-output support on
   self-hosted Ollama.

The deterministic mock is REMOVED from production paths — it survives only as
pydantic-ai ``FunctionModel`` helpers for unit tests (``mock_model_for_tests``).
Projects must not ship mock fallbacks in runtime code (owner directive, wave 10).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from portfolio_core.config import Settings

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings


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
        "`ollama pull qwen3.6:35b-a3b-q4_K_M`, or set LLM_BASE_URL + LLM_API_KEY in .env "
        "(see .env.example). Mock providers are test-only and intentionally not "
        "available at runtime."
    )


def is_hosted_provider(settings: Settings | None = None) -> bool:
    """True when a hosted OpenAI-compatible endpoint is configured (LLM_API_KEY set)."""
    from portfolio_core.config import get_settings

    s = settings or get_settings()
    return bool(s.llm_api_key and s.llm_base_url)


def hosted_model_settings() -> ModelSettings:
    """ModelSettings preset for the hosted Kimi coding endpoint.

    Empirically probed against ``https://api.kimi.com/coding/v1`` (wave 10):

    - Sampling is fixed server-side: ``temperature: 0`` is rejected
      ("only 1 is allowed"), and with thinking disabled even ``temperature: 1``
      is rejected ("only 0.6 is allowed for this model"). The only universally
      safe choice is to OMIT temperature — pydantic-ai omits unset keys from the
      request, so this preset sets none. Projects that currently pass
      ``temperature=0`` must merge via :func:`neutralize_hosted_model_settings`.
    - Thinking CAN be disabled: ``extra_body={"thinking": {"type": "disabled"}}``
      is accepted, drops ``reasoning_content`` and reasoning token burn. Without
      it the model always thinks (reasoning tokens are billed as output).
    """
    from pydantic_ai.settings import ModelSettings

    return ModelSettings(extra_body={"thinking": {"type": "disabled"}})


def neutralize_hosted_model_settings(settings: ModelSettings) -> ModelSettings:
    """Return a copy of ``settings`` safe for the hosted Kimi coding endpoint.

    Removes any ``temperature`` key (the endpoint fixes sampling and rejects
    explicit values) and merges in the thinking-disable body, preserving any
    caller-supplied ``extra_body`` entries.
    """
    existing_extra_body = settings.get("extra_body")
    merged_extra_body: dict[str, Any] = (
        dict(existing_extra_body) if isinstance(existing_extra_body, dict) else {}
    )
    merged_extra_body["thinking"] = {"type": "disabled"}
    neutralized: dict[str, Any] = {
        key: value for key, value in settings.items() if key != "temperature"
    }
    neutralized["extra_body"] = merged_extra_body
    return cast("ModelSettings", neutralized)


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
