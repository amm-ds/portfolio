"""G4 fix tests: agent-loop bounds (usage limits, top_k clamp, trace fields)."""

from __future__ import annotations

import pytest
from portfolio_core.config import Settings
from portfolio_core.llm_budget import budget_limits
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits
from rag_agent.agent import (
    agent_usage_limits,
    clamp_top_k,
    reset_top_k_clamps,
    top_k_clamps,
)
from rag_agent.config import RAGConfig
from rag_agent.reporting import QuestionTrace, classify_question, write_question_traces


@pytest.mark.parametrize(
    ("requested", "expected", "clamped"),
    [(0, 1, True), (1, 1, False), (5, 5, False), (10, 10, False), (11, 10, True), (1000, 10, True)],
)
def test_clamp_top_k_boundaries(requested: int, expected: int, clamped: bool) -> None:
    reset_top_k_clamps()
    assert clamp_top_k(requested) == expected
    assert top_k_clamps() == (1 if clamped else 0)


def test_clamp_counter_accumulates_and_resets() -> None:
    reset_top_k_clamps()
    clamp_top_k(0)
    clamp_top_k(100)
    clamp_top_k(5)
    assert top_k_clamps() == 2
    reset_top_k_clamps()
    assert top_k_clamps() == 0


def test_agent_usage_limits_read_from_config() -> None:
    config = RAGConfig()
    limits = agent_usage_limits(config)
    assert isinstance(limits, UsageLimits)
    assert limits.tool_calls_limit == 16  # Amendment 3 (2026-11-21): raised from 8
    assert limits.request_limit == 12
    assert limits.input_tokens_limit == 200_000
    assert limits.total_tokens_limit == 4_000_000

    custom = RAGConfig(
        agent_tool_calls_limit=3,
        agent_request_limit=4,
        agent_input_tokens_limit=50_000,
    )
    custom_limits = agent_usage_limits(custom)
    assert custom_limits.tool_calls_limit == 3
    assert custom_limits.request_limit == 4
    assert custom_limits.input_tokens_limit == 50_000


def test_local_budget_limits_are_finite() -> None:
    # G4 fix: the local path was None (unbounded); now finite per-answer limits.
    limits = budget_limits(Settings(LLM_API_KEY=None, LLM_BASE_URL=None))
    assert limits is not None
    assert limits.tool_calls_limit == 8
    assert limits.input_tokens_limit == 200_000


def _trace(**overrides: object) -> QuestionTrace:
    fields: dict[str, object] = {
        "question": "q?",
        "category": "single_hop",
        "expected_behavior": "answer",
        "top_rank": 1,
        "retrieved_relevant": True,
        "cited_relevant": True,
        "faithfulness": float("nan"),
        "abstained": False,
        "format_ok": False,
    }
    fields.update(overrides)
    return QuestionTrace(**fields)  # type: ignore[arg-type]


def test_usage_limit_error_classifies_as_budget_terminated() -> None:
    trace = _trace(
        error="UsageLimitExceeded: Exceeded the input_tokens_limit of 200000",
        budget_terminated=True,
        usage_limit_hit="Exceeded the input_tokens_limit of 200000 (input_tokens=201234)",
    )
    assert classify_question(trace) == "budget-terminated"


def test_usage_limit_hit_round_trips_in_trace_writer(tmp_path) -> None:
    import json

    config = RAGConfig(reports_dir=tmp_path)
    trace = _trace(
        error="UsageLimitExceeded: x",
        budget_terminated=True,
        usage_limit_hit="Exceeded the input_tokens_limit of 200000",
        top_k_clamps=2,
    )
    out = write_question_traces(config, [trace], path=tmp_path / "t.json")
    row = json.loads(out.read_text(encoding="utf-8"))[0]
    assert row["usage_limit_hit"] == "Exceeded the input_tokens_limit of 200000"
    assert row["top_k_clamps"] == 2
    assert row["verdict"] == "budget-terminated"


def test_answer_retry_records_usage_limit_hit() -> None:
    from rag_agent.evaluate import answer_with_output_retries

    class _StubAgent:
        def run_sync(self, *args: object, **kwargs: object) -> object:
            raise UsageLimitExceeded(
                "Exceeded the input_tokens_limit of 200000 (input_tokens=200001)"
            )

    result, retries, error, hit = answer_with_output_retries(
        _StubAgent(),  # type: ignore[arg-type]
        "q?",
        retriever=None,  # type: ignore[arg-type]
        config=RAGConfig(),
    )
    assert result is None
    assert retries == 0
    assert error.startswith("UsageLimitExceeded")
    assert hit is not None and "input_tokens_limit" in hit
