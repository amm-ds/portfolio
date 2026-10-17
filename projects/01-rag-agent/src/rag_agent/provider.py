"""Shared runtime LLM provider helpers."""

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings


def using_ollama() -> bool:
    """True when the platform factory will resolve to local Ollama."""
    from portfolio_core.config import get_settings

    s = get_settings()
    return not (s.llm_api_key and s.llm_base_url)


def model_settings_for_provider(base: "ModelSettings | None" = None) -> "ModelSettings | None":
    """Model-settings preset for the active provider, merged over ``base``.

    Hosted (``LLM_BASE_URL``/``LLM_API_KEY`` set): the platform
    :func:`portfolio_core.llm.hosted_model_settings` preset — thinking disabled,
    and **temperature neutralized**. The hosted Kimi coding endpoint fixes
    sampling server-side and rejects any explicit ``temperature``, so any
    caller-supplied value is dropped here (ADR-0004 preset, wave 15).

    Local Ollama: ``extra_body={"think": False}`` (qwen3 thinking off, ~4x
    faster per call — the wave-10 documented latency/depth trade-off), plus any
    caller-supplied settings untouched.
    """
    from portfolio_core.llm import is_hosted_provider, neutralize_hosted_model_settings
    from pydantic_ai.settings import ModelSettings

    if is_hosted_provider():
        merged = cast("ModelSettings", dict(base or {}))
        return neutralize_hosted_model_settings(merged)
    if base is not None:
        return base
    return ModelSettings(extra_body={"think": False})
