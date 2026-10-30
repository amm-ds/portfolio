"""Cost metering and budget caps for LLM usage (companion to ADR-0004).

Costs are **labelled cloud-equivalent estimates**: the hosted Kimi coding key
is membership-quota, not pay-per-token, so nothing here is a billed amount. The
reference rate card is the public ``kimi-k2.8-preview`` price
($1.00/Mtok input, $4.00/Mtok output), used as the reference class for
``kimi-for-coding``. Prompt-cache reads are discounted to 30% of the input rate
(public rate card ~$0.16-0.30/Mtok cached); the estimate is labelled either way.

Design note - why the USD cap lives in :class:`SpendLedger` and NOT in
pydantic-ai ``UsageLimits.cost_limit`` (verified against pydantic-ai 2.55.0,
``pydantic_ai/usage.py``): ``UsageLimits.check_cost`` only raises when
``usage.cost is not None``, and ``usage.cost`` is priced by genai-prices.
genai-prices (data snapshot shipped with pydantic-ai 2.55.0) knows Moonshot's
``kimi-k2*``/``kimi-k3`` cards but NOT ``kimi-for-coding`` /
``kimi-for-coding-highspeed``, so ``usage.cost`` is ``None`` for the hosted
coding endpoint and a ``cost_limit`` would be silently inert (at best a
``CostNotFoundWarning``). The USD cap is therefore enforced in the ledger:
:meth:`SpendLedger.record` raises :class:`BudgetExceededError` once cumulative
spend crosses the cap. ``budget_limits`` uses ``UsageLimits`` only for the
request/token limits, where pydantic-ai tracks the counters natively.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from portfolio_core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Public kimi-k2.8-preview rate card, used as the cloud-equivalent reference
# class for kimi-for-coding (membership key: labelled estimate, never billed).
_KIMI_INPUT_MTORK_USD = Decimal("1.00")
_KIMI_OUTPUT_MTORK_USD = Decimal("4.00")
# Prompt-cache read discount vs the input rate (rate card ~$0.16-0.30/Mtok).
_CACHED_TOKEN_PRICE_FRACTION = Decimal("0.30")

# Name-based local-model heuristic: any marker match prices the model at $0
# (cloud-equivalent reference label). Covers Ollama tags ("qwen3:32b" — the
# ":" marker), local-runner model ids ("local-model" from the LM Studio
# preset in .env.example), and the usual open-weights families served
# locally. Hosted models with these substrings are practically nonexistent;
# an unknown name that misses every marker falls through to the kimi
# reference card with a warning (see model_rate_card).
_LOCAL_MODEL_MARKERS = (":", "local", "qwen", "llama", "mistral", "gemma", "deepseek")


class BudgetExceededError(RuntimeError):
    """Cumulative estimated spend crossed the configured USD cap."""


@dataclass(frozen=True)
class RateCard:
    """Labelled per-million-token price card."""

    usd_per_mtok_input: Decimal
    usd_per_mtok_output: Decimal
    label: str


@dataclass(frozen=True)
class UsdRecord:
    """One metered model interaction (cumulative ledger entry)."""

    model_name: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    spend_usd: Decimal


def _model_is_local(model_name: str) -> bool:
    lowered = model_name.lower()
    return any(marker in lowered for marker in _LOCAL_MODEL_MARKERS)


def model_rate_card(model_name: str, settings: Settings | None = None) -> RateCard:
    """Rate card for a model name, with optional Settings price overrides.

    Defaults: kimi coding models and unknown hosted models → the kimi-k2.8-preview
    reference card (unknown models also log a warning); Ollama-style local models
    → $0 with a separate labelled cloud-equivalent card. ``USD_PER_MTOK_INPUT`` /
    ``USD_PER_MTOK_OUTPUT`` in Settings override the table when set.
    """
    s = settings or get_settings()
    if s.usd_per_mtok_input is not None or s.usd_per_mtok_output is not None:
        return RateCard(
            usd_per_mtok_input=(
                Decimal(str(s.usd_per_mtok_input))
                if s.usd_per_mtok_input is not None
                else _KIMI_INPUT_MTORK_USD
            ),
            usd_per_mtok_output=(
                Decimal(str(s.usd_per_mtok_output))
                if s.usd_per_mtok_output is not None
                else _KIMI_OUTPUT_MTORK_USD
            ),
            label="env override (USD_PER_MTOK_INPUT/OUTPUT)",
        )
    if _model_is_local(model_name):
        return RateCard(
            usd_per_mtok_input=Decimal("0"),
            usd_per_mtok_output=Decimal("0"),
            label=(
                "local ollama (cloud-equivalent reference: kimi-for-coding $1.00/$4.00 per Mtok)"
            ),
        )
    if not model_name.startswith(("kimi", "k3")):
        logger.warning(
            "No rate card for model %r; assuming kimi-k2.8-preview reference "
            "($1.00/$4.00 per Mtok)",
            model_name,
        )
    return RateCard(
        usd_per_mtok_input=_KIMI_INPUT_MTORK_USD,
        usd_per_mtok_output=_KIMI_OUTPUT_MTORK_USD,
        label="kimi-k2.8-preview reference card (cloud-equivalent estimate)",
    )


def _tokens(usage: Any, attr: str) -> int:
    """Duck-typed token count: 0 for missing/None (OpenAI objects use None)."""
    value = getattr(usage, attr, None)
    return value if isinstance(value, int) else 0


def reasoning_tokens_of(usage: Any) -> int:
    """Reasoning tokens from a usage object, if the provider reports them.

    Accepts pydantic-ai ``RequestUsage``/``RunUsage`` (``details['reasoning_tokens']``)
    and OpenAI-style objects (``usage.completion_tokens_details.reasoning_tokens``).
    Reasoning burns output tokens, so this is informational only — it is already
    inside ``output_tokens`` and priced there.
    """
    details = getattr(usage, "details", None)
    if isinstance(details, dict):
        value = details.get("reasoning_tokens")
        if isinstance(value, int):
            return value
    completion_details = getattr(usage, "completion_tokens_details", None)
    if completion_details is not None:
        value = getattr(completion_details, "reasoning_tokens", None)
        if isinstance(value, int):
            return value
    return 0


def cached_tokens_of(usage: Any) -> int:
    """Prompt-cache-read tokens (included in ``input_tokens`` by convention)."""
    value = getattr(usage, "cache_read_tokens", None)
    if isinstance(value, int):
        return value
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    if prompt_details is not None:
        value = getattr(prompt_details, "cached_tokens", None)
        if isinstance(value, int):
            return value
    return 0


def usage_cost(usage: Any, model_name: str, settings: Settings | None = None) -> Decimal:
    """Labelled cloud-equivalent USD estimate for one usage object.

    ``input_tokens`` (minus cached reads, discounted to 30% of the input rate)
    x input price + ``output_tokens`` (reasoning included) x output price, per
    million tokens. Never a billed amount.
    """
    card = model_rate_card(model_name, settings)
    input_tokens = _tokens(usage, "input_tokens")
    output_tokens = _tokens(usage, "output_tokens")
    cached = min(cached_tokens_of(usage), input_tokens)
    fresh_input = input_tokens - cached
    cost = (
        Decimal(fresh_input) * card.usd_per_mtok_input
        + Decimal(cached) * card.usd_per_mtok_input * _CACHED_TOKEN_PRICE_FRACTION
        + Decimal(output_tokens) * card.usd_per_mtok_output
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))


@dataclass
class SpendLedger:
    """Per-process cumulative spend tracker with a hard USD cap.

    Records every metered interaction; logs at 50% and 90% of ``budget_usd``
    (``warn_at`` fractions); raises :class:`BudgetExceededError` once cumulative
    spend reaches the cap. Use :func:`get_ledger` for the process singleton.
    """

    budget_usd: Decimal
    warn_at: tuple[float, ...] = (0.5, 0.9)
    spend_usd: Decimal = Decimal("0")
    records: list[UsdRecord] = field(default_factory=list)
    _warned: set[float] = field(default_factory=set)

    def record(self, model_name: str, usage: Any) -> UsdRecord:
        """Meter one usage object, enforce the cap, emit threshold log lines."""
        record = UsdRecord(
            model_name=model_name,
            input_tokens=_tokens(usage, "input_tokens"),
            output_tokens=_tokens(usage, "output_tokens"),
            reasoning_tokens=reasoning_tokens_of(usage),
            spend_usd=usage_cost(usage, model_name),
        )
        self.spend_usd += record.spend_usd
        self.records.append(record)
        logger.info(
            "llm spend: %s cost=$%s (cumulative est. $%s of $%s cap) %s",
            model_name,
            record.spend_usd,
            self.spend_usd,
            self.budget_usd,
            model_rate_card(model_name).label,
        )
        for fraction in sorted(self.warn_at):
            if fraction not in self._warned and self.spend_usd >= self.budget_usd * Decimal(
                str(fraction)
            ):
                self._warned.add(fraction)
                logger.warning(
                    "llm budget %d%% consumed: $%s of $%s (cloud-equivalent estimate)",
                    int(fraction * 100),
                    self.spend_usd,
                    self.budget_usd,
                )
        if self.spend_usd >= self.budget_usd:
            raise BudgetExceededError(
                f"LLM budget cap reached: estimated ${self.spend_usd} >= ${self.budget_usd} "
                f"({model_name}). Raise LLM_COST_LIMIT_USD or reduce scope."
            )
        return record


_ledger: SpendLedger | None = None


def get_ledger(settings: Settings | None = None) -> SpendLedger:
    """Process-wide :class:`SpendLedger` singleton, budgeted from Settings."""
    global _ledger
    if _ledger is None:
        s = settings or get_settings()
        _ledger = SpendLedger(budget_usd=Decimal(str(s.llm_cost_limit_usd)))
    return _ledger


def reset_ledger() -> None:
    """Drop the singleton (tests and long-running processes starting a new wave)."""
    global _ledger
    _ledger = None


def is_hosted_active(settings: Settings | None = None) -> bool:
    """True when a hosted provider (LLM_API_KEY + LLM_BASE_URL) is configured."""
    s = settings or get_settings()
    return bool(s.llm_api_key and s.llm_base_url)


def budget_limits(settings: Settings | None = None) -> Any | None:
    """pydantic-ai ``UsageLimits`` for the hosted provider, else ``None``.

    Request/token limits only — pydantic-ai tracks those counters natively. The
    USD cap is deliberately NOT mapped to ``UsageLimits.cost_limit``: genai-prices
    has no card for ``kimi-for-coding``, so pydantic-ai cannot price the run and
    the cap would be inert (see module docstring). Use :func:`get_ledger` /
    :func:`meter_result` for the enforceable USD cap. Local Ollama stays
    unlimited → ``None``.
    """
    if not is_hosted_active(settings):
        return None
    from pydantic_ai.usage import UsageLimits

    s = settings or get_settings()
    return UsageLimits(
        request_limit=s.llm_max_requests,
        total_tokens_limit=s.llm_total_tokens_limit,
    )


def meter_result(result: Any, model_name: str, settings: Settings | None = None) -> UsdRecord:
    """Meter a pydantic-ai agent result (or raw usage object) into the ledger.

    Accepts anything exposing ``.usage`` — either a method (``AgentRunResult``
    in older pydantic-ai) or a property returning a usage object (2.55+) — or
    a bare usage object; prices it via :func:`usage_cost` and records it in
    the process singleton ledger. Raises :class:`BudgetExceededError` at the
    cap.
    """
    usage_attr = getattr(type(result), "usage", None)
    if isinstance(usage_attr, property):
        usage = result.usage
    else:
        usage_fn = getattr(result, "usage", None)
        usage = usage_fn() if callable(usage_fn) else result
    return get_ledger(settings).record(model_name, usage)
