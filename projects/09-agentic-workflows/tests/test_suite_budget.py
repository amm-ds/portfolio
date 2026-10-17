"""Step-trace capture and suite budget-cap wiring (offline, no provider).

The step trace is asserted on a scripted-model workflow run; the budget paths
(per-task cap → ``budget_exceeded`` and suite continues; suite cap → abort)
are driven through ``run_suite`` with a stubbed meter, so no network and no
real pricing is involved.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from agentic_workflows import evals
from agentic_workflows.config import EvalConfig
from agentic_workflows.schemas import TaskRunRecord
from agentic_workflows.workflow import run_workflow
from portfolio_core.llm_budget import BudgetExceededError, UsdRecord

if TYPE_CHECKING:
    from conftest import ScriptedModelFactory


class TestStepTrace:
    def test_happy_path_records_plan_execute_critique_traces(
        self, make_scripted_model: ScriptedModelFactory
    ) -> None:
        result = run_workflow(
            "How many liters of diesel does the generator burn in one week?",
            model=make_scripted_model(),
        )
        nodes = [trace.node for trace in result.step_traces]
        assert nodes == ["plan", "execute", "critique"]
        for trace in result.step_traces:
            assert trace.latency_s >= 0.0
            assert trace.input_tokens >= 0
            assert trace.output_tokens >= 0

    def test_repair_path_records_one_trace_per_execute_visit(
        self, make_scripted_model: ScriptedModelFactory
    ) -> None:
        result = run_workflow(
            "weekly diesel?",
            model=make_scripted_model(fail_executions=4),
        )
        # a failed execute attempt raises inside the retry wrapper, so only the
        # recovered visit leaves a trace
        nodes = [trace.node for trace in result.step_traces]
        assert nodes == ["plan", "execute", "critique"]
        assert result.retries == 1

    def test_record_steps_round_trip(self, tmp_path, make_scripted_model) -> None:
        result = run_workflow("weekly diesel?", model=make_scripted_model())
        record = TaskRunRecord(
            task_id="t03",
            status="ok",
            answer=result.answer,
            steps_taken=result.steps_taken,
            tools_used=result.tools_used,
            steps=result.step_traces,
            confidence=result.confidence,
            duration_s=1.0,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        path = evals.write_records([record], tmp_path / "records.json")
        loaded = evals.load_records(path)
        assert loaded[0].steps == record.steps
        assert {t.node for t in loaded[0].steps} == {"plan", "execute", "critique"}

    def test_legacy_records_without_steps_field_load(self, tmp_path) -> None:
        legacy = (
            '[{"task_id": "t01", "status": "ok", "answer": "a", '
            '"steps_taken": [], "tools_used": [], "confidence": 0.5, '
            '"duration_s": 1.0, "input_tokens": 10, "output_tokens": 5}]'
        )
        path = tmp_path / "legacy.json"
        path.write_text(legacy)
        loaded = evals.load_records(path)
        assert loaded[0].steps == []


def _stub_meter(
    monkeypatch: Any,
    spend_per_call: Decimal,
    fail_with: type[Exception] | None = None,
    spend_after_calls: tuple[int, Decimal] | None = None,
) -> None:
    """Replace evals.meter_result with a deterministic stub.

    Records a fixed spend per call (real usage pricing is irrelevant to the
    wiring under test), optionally switching to a different spend after N
    calls (one scripted task meters exactly 3 node calls), and optionally
    raises ``fail_with`` from the third call onward.
    """

    calls = {"n": 0}

    def fake_meter(
        result: Any,
        model_name: str,
        settings: Any = None,
        _calls: dict[str, int] = calls,
    ) -> UsdRecord:
        _calls["n"] += 1
        if fail_with is not None and _calls["n"] > 2:
            raise fail_with("LLM budget cap reached: estimated $99 >= $2.00 (kimi-for-coding).")
        spend = spend_per_call
        if spend_after_calls is not None and _calls["n"] > spend_after_calls[0]:
            spend = spend_after_calls[1]
        return UsdRecord(
            model_name=model_name,
            input_tokens=100,
            output_tokens=50,
            reasoning_tokens=0,
            spend_usd=spend,
        )

    monkeypatch.setattr(evals, "meter_result", fake_meter)


class TestSuiteBudget:
    def test_per_task_cap_records_budget_exceeded_and_continues(
        self,
        monkeypatch: Any,
        make_scripted_model: ScriptedModelFactory,
    ) -> None:
        # task 1 spends $0.10/call (trips the $0.15 cap on its second metered
        # node); task 2 spends $0.01/call and completes under the cap
        _stub_meter(monkeypatch, Decimal("0.10"), spend_after_calls=(3, Decimal("0.01")))
        config = EvalConfig(task_cost_limit_usd=0.15)
        tasks = [evals.TASK_SUITE[0], evals.TASK_SUITE[1]]
        records = evals.run_suite(config, model=make_scripted_model(), tasks=tasks)
        assert [r.status for r in records] == ["budget_exceeded", "ok"]
        cut = records[0]
        assert cut.input_tokens > 0  # metered spend up to the cut is honest
        assert "per-task" in (cut.error or "")

    def test_suite_cap_aborts_remaining_tasks(
        self,
        monkeypatch: Any,
        make_scripted_model: ScriptedModelFactory,
    ) -> None:
        _stub_meter(monkeypatch, Decimal("0.10"), fail_with=BudgetExceededError)
        config = EvalConfig(task_cost_limit_usd=50.0)  # per-task cap never trips
        tasks = [evals.TASK_SUITE[0], evals.TASK_SUITE[1], evals.TASK_SUITE[2]]
        records = evals.run_suite(config, model=make_scripted_model(), tasks=tasks)
        # task 1 trips the suite cap on its 3rd metered call (the critique node);
        # remaining tasks are recorded as not run
        assert records[0].status == "budget_exceeded"
        assert "budget cap" in (records[0].error or "").lower()
        assert [r.status for r in records[1:]] == ["budget_exceeded", "budget_exceeded"]
        assert all("not run" in (r.error or "") for r in records[1:])

    def test_healthy_budget_all_tasks_ok(
        self,
        monkeypatch: Any,
        make_scripted_model: ScriptedModelFactory,
    ) -> None:
        _stub_meter(monkeypatch, Decimal("0.001"))
        config = EvalConfig(task_cost_limit_usd=0.25)
        tasks = [evals.TASK_SUITE[0]]
        records = evals.run_suite(config, model=make_scripted_model(), tasks=tasks)
        assert records[0].status == "ok"
        assert records[0].steps  # step traces are wired through the suite too
