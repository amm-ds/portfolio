"""LLM provider factory (ADR-0004). One entry point, three modes.

- Configured: OpenAI-compatible endpoint via env (e.g. Kimi/Moonshot).
- Mock: deterministic canned response when no key is configured (CI/offline).
- Tests: pydantic-ai TestModel/FunctionModel injected directly by callers.

Projects must not import LLM SDKs; they depend on this factory and their
pydantic output models only.
"""

from collections.abc import AsyncIterator
from typing import Any

from portfolio_core.config import Settings


class MockProviderUnsetError(RuntimeError):
    """A live provider was requested but LLM credentials are not configured."""


def build_model(settings: Settings | None = None, mock_response: str | None = None) -> Any:
    """Return a pydantic-ai ``Model``.

    When ``LLM_API_KEY`` + ``LLM_BASE_URL`` are set, returns an OpenAI-compatible
    chat model bound to that endpoint. Otherwise returns a deterministic
    ``FunctionModel`` returning ``mock_response``.
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

    if mock_response is None:
        raise MockProviderUnsetError(
            "No LLM credentials configured and no mock_response provided. "
            "Set LLM_BASE_URL/LLM_API_KEY (see .env.example) or pass mock_response."
        )
    return _function_model(mock_response)


def _function_model(response: str) -> Any:
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel

    def _respond(messages: list[Any], info: Any) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content=response)])

    async def _stream(messages: list[Any], info: Any) -> AsyncIterator[str]:
        # Single-chunk stream is enough: SSE clients get one text event + result.
        yield response

    return FunctionModel(_respond, stream_function=_stream)
