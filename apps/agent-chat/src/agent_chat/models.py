"""Model provider factory — the only file that knows how to reach a model.

Adapters swap providers here (Ollama default, hosted OpenAI-compatible, a
:class:`~pydantic_ai.models.fallback.FallbackModel` chain when a fallback
model is configured) without the agent, tools, or API changing at all.

Tests never come through here: they inject a scripted ``FunctionModel``.
"""

from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from agent_chat.config import Settings


def _hosted_style_model(base_url: str, api_key: str, model_name: str) -> OpenAIChatModel:
    """An OpenAI-compatible chat model against ``base_url`` (Ollama or hosted)."""
    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    return OpenAIChatModel(model_name, provider=provider)


def primary_model_name(settings: Settings) -> str:
    """The configured primary model, exposed by health and eval reports."""
    if settings.provider == "ollama":
        return settings.ollama_model
    if settings.provider == "kimi":
        return settings.kimi_model
    return settings.hosted_model


def build_model(settings: Settings) -> Model:
    """Resolve the configured provider into a (possibly fallback-chained) model.

    Ollama, Kimi, and generic hosted providers expose OpenAI-compatible
    endpoints, so all branches share one client shape. A non-empty fallback
    composes a chain that fails over only on provider API errors.
    """
    if settings.provider == "hosted":
        primary = _hosted_style_model(
            settings.hosted_base_url,
            settings.hosted_api_key,
            settings.hosted_model,
        )
        if settings.hosted_fallback_model:
            fallback = _hosted_style_model(
                settings.hosted_base_url,
                settings.hosted_api_key,
                settings.hosted_fallback_model,
            )
            return FallbackModel(primary, fallback)
        return primary

    if settings.provider == "kimi":
        primary = _hosted_style_model(
            settings.kimi_base_url,
            settings.kimi_api_key,
            settings.kimi_model,
        )
        if settings.kimi_fallback_model:
            fallback = _hosted_style_model(
                settings.kimi_base_url,
                settings.kimi_api_key,
                settings.kimi_fallback_model,
            )
            return FallbackModel(primary, fallback)
        return primary

    ollama_url = settings.ollama_base_url.rstrip("/") + "/v1"
    primary = _hosted_style_model(ollama_url, "ollama", settings.ollama_model)
    if settings.ollama_fallback_model:
        fallback = _hosted_style_model(ollama_url, "ollama", settings.ollama_fallback_model)
        return FallbackModel(primary, fallback)
    return primary
