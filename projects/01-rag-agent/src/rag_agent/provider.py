"""Shared runtime LLM provider helpers."""

from typing import TYPE_CHECKING

from portfolio_core.config import get_settings

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings


def using_ollama() -> bool:
    """True when the platform factory will resolve to local Ollama."""
    s = get_settings()
    return not (s.llm_api_key and s.llm_base_url)


def no_think_model_settings() -> "ModelSettings | None":
    """``model_settings`` that disable qwen3 thinking on local Ollama.

    Thinking roughly quadruples per-call latency on this machine; the wave-10
    evaluation trades reasoning depth for throughput and documents it. Returns
    None for env-configured providers (the parameter is Ollama-specific).
    """
    from pydantic_ai.settings import ModelSettings

    if using_ollama():
        return ModelSettings(extra_body={"think": False})
    return None
