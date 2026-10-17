"""Tests for llm_budget + hosted provider preset. No network: all usage is fake."""

from decimal import Decimal

import pytest
from portfolio_core.config import Settings
from portfolio_core.llm import (
    hosted_model_settings,
    is_hosted_provider,
    neutralize_hosted_model_settings,
)
from portfolio_core.llm_budget import (
    BudgetExceededError,
    RateCard,
    SpendLedger,
    budget_limits,
    cached_tokens_of,
    get_ledger,
    meter_result,
    model_rate_card,
    reasoning_tokens_of,
    reset_ledger,
    usage_cost,
)


class FakeOpenAIUsage:
    """Minimal stand-in for an OpenAI chat completion usage object."""

    def __init__(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int = 0,
        cached_tokens: int = 0,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.completion_tokens_details = (
            type("D", (), {"reasoning_tokens": reasoning_tokens})() if reasoning_tokens else None
        )
        self.prompt_tokens_details = (
            type("D", (), {"cached_tokens": cached_tokens})() if cached_tokens else None
        )

    # pydantic-ai-style aliases used by llm_budget duck-typing
    @property
    def input_tokens(self) -> int:
        return self.prompt_tokens

    @property
    def output_tokens(self) -> int:
        return self.completion_tokens


def fake_pydantic_usage(
    input_tokens: int, output_tokens: int, reasoning_tokens: int = 0, cached: int = 0
) -> object:
    """RequestUsage-shaped object without importing provider internals."""
    return type(
        "U",
        (),
        {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cached,
            "details": {"reasoning_tokens": reasoning_tokens} if reasoning_tokens else {},
        },
    )()


class TestRateCard:
    def test_kimi_models_use_reference_card(self) -> None:
        for model in ("kimi-for-coding", "kimi-for-coding-highspeed", "k3", "k3-256k"):
            card = model_rate_card(model, Settings())
            assert card.usd_per_mtok_input == Decimal("1.00")
            assert card.usd_per_mtok_output == Decimal("4.00")
            assert "reference" in card.label

    def test_ollama_models_are_free_with_cloud_equivalent_label(self) -> None:
        card = model_rate_card("qwen3.6:35b-a3b-q4_K_M", Settings())
        assert card.usd_per_mtok_input == Decimal("0")
        assert card.usd_per_mtok_output == Decimal("0")
        assert "cloud-equivalent" in card.label

    def test_unknown_model_warns_and_uses_reference_card(self, caplog) -> None:
        import logging

        with caplog.at_level(logging.WARNING, logger="portfolio_core.llm_budget"):
            card = model_rate_card("gpt-99-unknown", Settings())
        assert card.usd_per_mtok_input == Decimal("1.00")
        assert any("gpt-99-unknown" in r.message for r in caplog.records)

    def test_settings_overrides_take_precedence(self) -> None:
        s = Settings(USD_PER_MTOK_INPUT=2.5, USD_PER_MTOK_OUTPUT=8.0)
        card = model_rate_card("kimi-for-coding", s)
        assert card.usd_per_mtok_input == Decimal("2.5")
        assert card.usd_per_mtok_output == Decimal("8.0")
        assert "override" in card.label

    def test_partial_override_falls_back_to_table(self) -> None:
        s = Settings(USD_PER_MTOK_OUTPUT=10.0)
        card = model_rate_card("kimi-for-coding", s)
        assert card.usd_per_mtok_input == Decimal("1.00")
        assert card.usd_per_mtok_output == Decimal("10.0")


class TestUsageCost:
    def test_input_output_math(self) -> None:
        usage = fake_pydantic_usage(input_tokens=1_000_000, output_tokens=250_000)
        assert usage_cost(usage, "kimi-for-coding", Settings()) == Decimal(
            "2.000000"  # 1M * $1 + 0.25M * $4
        )

    def test_reasoning_tokens_are_priced_inside_output(self) -> None:
        """Reasoning burns output tokens: 100 output incl. 40 reasoning → output price only."""
        usage = fake_pydantic_usage(
            input_tokens=100_000, output_tokens=100_000, reasoning_tokens=40_000
        )
        assert reasoning_tokens_of(usage) == 40_000
        # no double-counting: 0.1M*$1 + 0.1M*$4 = $0.50
        assert usage_cost(usage, "kimi-for-coding", Settings()) == Decimal("0.500000")

    def test_openai_shape_with_reasoning_details(self) -> None:
        usage = FakeOpenAIUsage(prompt_tokens=1_000, completion_tokens=500, reasoning_tokens=300)
        assert reasoning_tokens_of(usage) == 300
        assert usage_cost(usage, "kimi-for-coding", Settings()) == Decimal("0.003000")

    def test_cached_tokens_get_discount(self) -> None:
        usage = fake_pydantic_usage(input_tokens=1_000_000, output_tokens=0, cached=900_000)
        assert cached_tokens_of(usage) == 900_000
        # 0.1M fresh * $1 + 0.9M cached * $1 * 0.3 = $0.37
        assert usage_cost(usage, "kimi-for-coding", Settings()) == Decimal("0.370000")

    def test_ollama_usage_costs_zero(self) -> None:
        usage = fake_pydantic_usage(input_tokens=9_000_000, output_tokens=9_000_000)
        assert usage_cost(usage, "qwen3.6:35b-a3b-q4_K_M", Settings()) == Decimal("0")


class TestSpendLedger:
    def test_accumulates_records(self) -> None:
        ledger = SpendLedger(budget_usd=Decimal("10"))
        ledger.record("kimi-for-coding", fake_pydantic_usage(1_000_000, 0))
        ledger.record("kimi-for-coding", fake_pydantic_usage(0, 250_000))
        assert ledger.spend_usd == Decimal("2.000000")
        assert len(ledger.records) == 2
        assert ledger.records[1].output_tokens == 250_000

    def test_warns_once_at_50_and_90_percent(self, caplog) -> None:
        import logging

        ledger = SpendLedger(budget_usd=Decimal("1"))
        with caplog.at_level(logging.WARNING, logger="portfolio_core.llm_budget"):
            ledger.record("kimi-for-coding", fake_pydantic_usage(600_000, 0))  # $0.60 → 50%
            ledger.record("kimi-for-coding", fake_pydantic_usage(350_000, 0))  # $0.95 → 90%
            ledger.record("kimi-for-coding", fake_pydantic_usage(10_000, 0))  # no re-warn
        warnings = [r for r in caplog.records if "budget" in r.message]
        assert len(warnings) == 2
        assert "50%" in warnings[0].message
        assert "90%" in warnings[1].message

    def test_raises_at_cap(self) -> None:
        ledger = SpendLedger(budget_usd=Decimal("1"))
        ledger.record("kimi-for-coding", fake_pydantic_usage(900_000, 0))  # $0.90, ok
        with pytest.raises(BudgetExceededError, match="cap reached"):
            ledger.record("kimi-for-coding", fake_pydantic_usage(200_000, 0))  # $1.10

    def test_singleton_roundtrip(self) -> None:
        reset_ledger()
        ledger = get_ledger(Settings(LLM_COST_LIMIT_USD=5.0))
        assert ledger.budget_usd == Decimal("5.0")
        assert get_ledger() is ledger
        reset_ledger()
        assert get_ledger() is not ledger


class TestBudgetLimits:
    def test_hosted_returns_request_and_token_limits(self) -> None:
        limits = budget_limits(Settings(LLM_API_KEY="k", LLM_BASE_URL="https://x/v1"))
        assert limits is not None
        assert limits.request_limit == 400
        assert limits.total_tokens_limit == 4_000_000
        assert limits.cost_limit is None  # USD cap enforced by SpendLedger instead

    def test_local_returns_none(self) -> None:
        # explicit None overrides a real .env in the working tree
        assert budget_limits(Settings(LLM_API_KEY=None, LLM_BASE_URL=None)) is None

    def test_env_defaults(self) -> None:
        s = Settings()
        assert s.llm_cost_limit_usd == 3.0
        assert s.llm_suite_cost_limit_usd == 2.0
        assert s.llm_max_requests == 400
        assert s.llm_total_tokens_limit == 4_000_000
        assert s.usd_per_mtok_input is None


class TestMeterResult:
    def test_meters_agent_style_result(self) -> None:
        class FakeResult:
            def usage(self) -> object:
                return fake_pydantic_usage(
                    input_tokens=500_000, output_tokens=125_000, reasoning_tokens=25_000
                )

        reset_ledger()
        record = meter_result(FakeResult(), "kimi-for-coding", Settings(LLM_COST_LIMIT_USD=3.0))
        assert record.input_tokens == 500_000
        assert record.output_tokens == 125_000
        assert record.reasoning_tokens == 25_000
        assert record.spend_usd == Decimal("1.000000")  # 0.5M*$1 + 0.125M*$4
        assert get_ledger().spend_usd == Decimal("1.000000")
        reset_ledger()

    def test_meters_raw_usage_object(self) -> None:
        reset_ledger()
        usage = FakeOpenAIUsage(prompt_tokens=2_000_000, completion_tokens=0)
        record = meter_result(usage, "kimi-for-coding", Settings(LLM_COST_LIMIT_USD=3.0))
        assert record.spend_usd == Decimal("2.000000")
        reset_ledger()

    def test_meters_property_style_usage(self) -> None:
        """pydantic-ai 2.55 exposes AgentRunResult.usage as a property; a
        callable-only duck-type silently meters $0 (wave-16 regression)."""

        class FakeResult:
            @property
            def usage(self) -> object:
                return fake_pydantic_usage(input_tokens=100_000, output_tokens=50_000)

        reset_ledger()
        record = meter_result(FakeResult(), "kimi-for-coding", Settings(LLM_COST_LIMIT_USD=3.0))
        assert record.input_tokens == 100_000
        assert record.spend_usd == Decimal("0.300000")  # 0.1M*$1 + 0.05M*$4
        reset_ledger()


class TestHostedModelSettings:
    def test_preset_omits_temperature_and_disables_thinking(self) -> None:
        settings = hosted_model_settings()
        assert "temperature" not in settings
        assert settings["extra_body"] == {"thinking": {"type": "disabled"}}

    def test_neutralize_strips_zero_temperature(self) -> None:
        from pydantic_ai.settings import ModelSettings

        neutralized = neutralize_hosted_model_settings(ModelSettings(temperature=0))
        assert "temperature" not in neutralized
        assert neutralized["extra_body"] == {"thinking": {"type": "disabled"}}

    def test_neutralize_preserves_other_keys_and_merges_extra_body(self) -> None:
        from pydantic_ai.settings import ModelSettings

        neutralized = neutralize_hosted_model_settings(
            ModelSettings(temperature=0.7, max_tokens=512, extra_body={"custom": 1})
        )
        assert "temperature" not in neutralized
        assert neutralized["max_tokens"] == 512
        assert neutralized["extra_body"] == {"custom": 1, "thinking": {"type": "disabled"}}

    def test_is_hosted_provider(self) -> None:
        assert is_hosted_provider(Settings(LLM_API_KEY="k", LLM_BASE_URL="https://x/v1"))
        # explicit None overrides a real .env in the working tree
        no_creds = Settings(LLM_API_KEY=None, LLM_BASE_URL=None)
        assert not is_hosted_provider(no_creds)
        assert not is_hosted_provider(Settings(LLM_API_KEY="k", LLM_BASE_URL=None))


class TestModuleContracts:
    def test_rate_card_is_frozen_dataclass(self) -> None:
        card = RateCard(Decimal("1"), Decimal("4"), "test")
        with pytest.raises(AttributeError):
            card.label = "nope"  # type: ignore[misc]
