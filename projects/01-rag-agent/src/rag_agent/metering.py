"""Per-phase LLM spend metering for the hosted provider (companion to ADR-0004/0006).

Four phases are metered on every hosted call: ``agent`` (answer generation),
``judge`` (rubric verdicts), ``verify`` (claim verdicts + repairs) and
``ragas`` (RAGAS metric calls). Metering is active only when a hosted provider
is configured (:func:`portfolio_core.llm.is_hosted_provider`): local Ollama
stays $0 API cost and the phase table reports zeros.

All amounts are **labelled cloud-equivalent estimates** at the public
kimi-k2.8-preview reference card ($1/Mtok in, $4/Mtok out, cached reads at
30%) — the hosted key is membership-quota, never pay-per-token, so nothing
here is a billed amount. The platform :class:`~portfolio_core.llm_budget.SpendLedger`
is the enforceable USD cap: :func:`portfolio_core.llm_budget.meter_result`
raises :class:`~portfolio_core.llm_budget.BudgetExceededError` once cumulative
spend crosses ``LLM_COST_LIMIT_USD``, and that exception is deliberately
allowed to propagate (never swallowed into a fallback judge) so a run stops
cleanly at the cap.
"""

from decimal import Decimal
from typing import Any

from portfolio_core.llm_budget import (
    BudgetExceededError,
    cached_tokens_of,
    get_ledger,
    meter_result,
    reset_ledger,
)
from portfolio_core.logging import get_logger

logger = get_logger(__name__)

PHASES: tuple[str, ...] = ("agent", "judge", "verify", "ragas")

#: Human-readable cost basis for every figure this module reports.
COST_BASIS = (
    "cloud-equivalent estimate at the kimi-k2.8-preview reference card "
    "($1.00/Mtok input, $4.00/Mtok output, cached reads 30%); the hosted key is "
    "membership-quota, not pay-per-token — never a billed amount"
)


def hosted_model_name() -> str:
    """The model name the platform factory will use for hosted calls."""
    from portfolio_core.config import get_settings

    s = get_settings()
    return s.llm_model or "kimi-k2-0711-preview"


def _hosted_active() -> bool:
    from portfolio_core.llm import is_hosted_provider

    return is_hosted_provider()


def _extract_usage(result: Any) -> Any:
    """Usage object from a pydantic-ai result (or pass through a bare usage).

    Platform note (workaround, wave 15): ``AgentRunResult.usage`` is a
    **property** in pydantic-ai 2.55, so ``meter_result``'s
    ``callable(getattr(result, "usage", None))`` duck-typing never fires and
    would meter 0 tokens. Extracting here keeps the ledger truthful; the
    platform helper should accept property-style usage too.
    """
    usage = getattr(result, "usage", None)
    if usage is None or callable(usage):
        return result
    return usage


class PhaseMeter:
    """Per-phase call/token/spend counters over one evaluate run.

    ``active`` is resolved from the provider configuration unless overridden
    (tests force it). On activation the process-wide spend ledger is reset so
    the cumulative USD cap applies to this run alone; :meth:`record` meters
    every hosted call into the ledger (enforcing the cap) and into the
    per-phase table.
    """

    def __init__(self, active: bool | None = None) -> None:
        self.active = _hosted_active() if active is None else active
        self._totals: dict[str, dict[str, Any]] = {
            p: {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_input_tokens": 0,
                "spend_usd": Decimal("0"),
            }
            for p in PHASES
        }
        if self.active:
            # Fresh cumulative window: the ledger enforces LLM_COST_LIMIT_USD
            # per evaluate run.
            reset_ledger()

    def record(self, phase: str, result: Any, model_name: str | None = None) -> None:
        """Meter one model interaction (pydantic-ai result or raw usage).

        No-op when metering is inactive (local provider). Raises
        :class:`BudgetExceededError` when the cumulative USD cap is crossed —
        callers must let it propagate.
        """
        if not self.active:
            return
        if phase not in self._totals:
            raise KeyError(f"unknown metering phase {phase!r}")
        usage = _extract_usage(result)
        entry = meter_result(usage, model_name or hosted_model_name())
        totals = self._totals[phase]
        totals["calls"] += 1
        totals["input_tokens"] += entry.input_tokens
        totals["output_tokens"] += entry.output_tokens
        totals["cached_input_tokens"] += cached_tokens_of(usage)
        totals["spend_usd"] += entry.spend_usd

    def snapshot(self) -> dict[str, Any]:
        """JSON-safe per-phase breakdown plus the run total and ledger truth."""
        phases: dict[str, dict[str, Any]] = {}
        total = {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_input_tokens": 0,
            "spend_usd": 0.0,
        }
        for name, t in self._totals.items():
            spend = float(t["spend_usd"])
            phases[name] = {
                "calls": t["calls"],
                "input_tokens": t["input_tokens"],
                "output_tokens": t["output_tokens"],
                "cached_input_tokens": t["cached_input_tokens"],
                "spend_usd": spend,
            }
            for key in ("calls", "input_tokens", "output_tokens", "cached_input_tokens"):
                total[key] += t[key]
            total["spend_usd"] += spend
        snapshot: dict[str, Any] = {
            "active": self.active,
            "model": hosted_model_name() if self.active else None,
            "cost_basis": COST_BASIS if self.active else "local inference: $0 API cost",
            "phases": phases,
            "total": total,
        }
        if self.active:
            ledger = get_ledger()
            snapshot["ledger_spend_usd"] = float(ledger.spend_usd)
            snapshot["budget_usd"] = float(ledger.budget_usd)
        return snapshot


_meter: PhaseMeter | None = None


def start_metering(active: bool | None = None) -> PhaseMeter:
    """Reset and activate the run-wide meter (called once at evaluate start)."""
    global _meter
    _meter = PhaseMeter(active=active)
    return _meter


def get_meter() -> PhaseMeter:
    """The current meter, lazily created for direct run_rag_eval callers."""
    global _meter
    if _meter is None:
        _meter = PhaseMeter()
    return _meter


__all__ = [
    "COST_BASIS",
    "PHASES",
    "BudgetExceededError",
    "PhaseMeter",
    "get_meter",
    "hosted_model_name",
    "start_metering",
]
