from portfolio_core.config import Settings
from portfolio_core.llm import (
    LLMProviderUnavailableError,
    build_model,
    mock_model_for_tests,
    ollama_available,
)


def test_mock_model_supports_streaming() -> None:
    """The test-only mock must work for run_stream (SSE chat), not just run."""
    import asyncio

    from pydantic_ai import Agent

    model = mock_model_for_tests("hello world")
    agent = Agent(model, output_type=str)

    async def collect() -> str:
        text = ""
        async with agent.run_stream("hi") as result:
            async for delta in result.stream_text():
                text += delta
        return text

    assert asyncio.run(collect()) == "hello world"


def test_env_provider_takes_priority() -> None:
    s = Settings(llm_api_key="sk-test", llm_base_url="https://example.com/v1")
    model = build_model(s)
    assert model is not None


def test_ollama_available_false_when_down(monkeypatch) -> None:
    import httpx

    def _boom(*a: object, **kw: object) -> None:
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(httpx, "get", _boom)
    assert ollama_available() is False


def test_build_model_raises_without_provider(monkeypatch) -> None:
    """No env credentials + no Ollama → clear, actionable error (no silent mock)."""
    monkeypatch.setattr("portfolio_core.llm.ollama_available", lambda *a, **k: False)
    try:
        # explicit None overrides a real .env in the working tree
        build_model(Settings(LLM_API_KEY=None, LLM_BASE_URL=None))
    except LLMProviderUnavailableError as e:
        assert "ollama pull" in str(e)
    else:  # pragma: no cover
        raise AssertionError("expected LLMProviderUnavailableError")
