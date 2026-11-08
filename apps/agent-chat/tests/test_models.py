"""Provider factory: Kimi uses the same OpenAI-compatible model seam."""

from typing import cast

import pytest
from pydantic_ai.models import Model

from agent_chat.config import Settings
from agent_chat.models import build_model, primary_model_name


def test_kimi_primary_uses_official_openai_compatible_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str]] = []
    sentinel = cast(Model, object())

    def fake_model(base_url: str, api_key: str, model_name: str) -> Model:
        calls.append((base_url, api_key, model_name))
        return sentinel

    monkeypatch.setattr("agent_chat.models._hosted_style_model", fake_model)
    settings = Settings(provider="kimi", kimi_api_key="secret", kimi_model="k3-256k")

    assert build_model(settings) is sentinel
    assert calls == [("https://api.kimi.com/coding/v1", "secret", "k3-256k")]
    assert primary_model_name(settings) == "k3-256k"


def test_kimi_fallback_reuses_endpoint_and_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str]] = []
    primary = cast(Model, object())
    secondary = cast(Model, object())
    models = iter([primary, secondary])
    fallback = cast(Model, object())

    def fake_model(base_url: str, api_key: str, model_name: str) -> Model:
        calls.append((base_url, api_key, model_name))
        return next(models)

    monkeypatch.setattr("agent_chat.models._hosted_style_model", fake_model)
    monkeypatch.setattr("agent_chat.models.FallbackModel", lambda *args: fallback)
    settings = Settings(
        provider="kimi",
        kimi_api_key="secret",
        kimi_model="k3-256k",
        kimi_fallback_model="kimi-for-coding",
    )

    assert build_model(settings) is fallback
    assert calls == [
        ("https://api.kimi.com/coding/v1", "secret", "k3-256k"),
        ("https://api.kimi.com/coding/v1", "secret", "kimi-for-coding"),
    ]
