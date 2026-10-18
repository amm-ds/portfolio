"""Unit tests for the eval suite: graders, suite integrity, offline reporting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from agentic_workflows import evals
from agentic_workflows.config import EvalConfig
from agentic_workflows.schemas import EvalTask, TaskRunRecord, ToolCallTrace
from pydantic_evals.evaluators import EvaluatorContext


def _record(
    task_id: str,
    *,
    answer: str = "The answer is 75.6 liters.",
    tools: tuple[str, ...] | None = None,
    steps: int = 5,
    duration: float = 12.0,
    status: str = "ok",
) -> TaskRunRecord:
    if tools is None:
        task = next(t for t in evals.TASK_SUITE if t.id == task_id)
        tools = tuple(sorted(task.expected_tools))
    return TaskRunRecord(
        task_id=task_id,
        status=status,  # type: ignore[arg-type]
        answer=answer,
        steps_taken=["s"] * steps,
        tools_used=list(tools),
        confidence=0.9,
        duration_s=duration,
        input_tokens=100,
        output_tokens=50,
    )


def _ctx(task: EvalTask, record: TaskRunRecord) -> EvaluatorContext:
    return EvaluatorContext(
        name=task.id,
        inputs=task,
        metadata=None,
        expected_output=None,
        output=record,
        duration=record.duration_s,
        _span_tree=None,
        attributes={},
        metrics={},
    )


class TestGraders:
    def test_answer_success_requires_all_keywords(self) -> None:
        task = evals.TASK_SUITE[2]  # t03: weekly diesel, keyword 75.6
        assert evals.AnswerSuccess().evaluate(_ctx(task, _record(task.id))) is True
        failing = _record(task.id, answer="about 76 liters")
        assert evals.AnswerSuccess().evaluate(_ctx(task, failing)) is False

    def test_answer_success_normalizes_thousand_separators(self) -> None:
        task = evals.TASK_SUITE[11]  # t12: keyword 6200
        record = _record(task.id, answer="Total water storage is 6,200 liters.")
        assert evals.AnswerSuccess().evaluate(_ctx(task, record)) is True

    def test_answer_success_is_case_insensitive(self) -> None:
        task = evals.TASK_SUITE[2]
        upper = _record(task.id, answer="The generator burns 75.6 LITERS weekly.")
        assert evals.AnswerSuccess().evaluate(_ctx(task, upper)) is True

    def test_tool_selection_is_exact_set(self) -> None:
        task = evals.TASK_SUITE[2]  # expects search_handbook + calculator
        assert evals.ToolSelection().evaluate(_ctx(task, _record(task.id))) is True
        missing = _record(task.id, tools=("calculator",))
        assert evals.ToolSelection().evaluate(_ctx(task, missing)) is False
        extra = _record(task.id, tools=("search_handbook", "calculator", "note_store"))
        assert evals.ToolSelection().evaluate(_ctx(task, extra)) is False

    def test_step_budget(self) -> None:
        task = evals.TASK_SUITE[0]
        assert evals.StepBudget().evaluate(_ctx(task, _record(task.id, steps=3))) is True
        assert evals.StepBudget().evaluate(_ctx(task, _record(task.id, steps=99))) is False

    def test_latency_budget(self) -> None:
        task = evals.TASK_SUITE[0]
        assert evals.LatencyBudget().evaluate(_ctx(task, _record(task.id, duration=10.0))) is True
        assert evals.LatencyBudget().evaluate(_ctx(task, _record(task.id, duration=999.0))) is False


class TestSuiteIntegrity:
    def test_unique_ids_and_categories(self) -> None:
        ids = [task.id for task in evals.TASK_SUITE]
        assert len(ids) == len(set(ids))
        assert len(ids) >= 12
        categories = {task.category for task in evals.TASK_SUITE}
        assert categories == {"lookup", "calculation", "conversion", "multi_step", "note_keeping"}

    def test_answer_tasks_carry_ground_truth(self) -> None:
        """The schema permits empty keyword/tool lists only for refuse probes."""
        for task in evals.TASK_SUITE:
            assert task.expected_behavior == "answer", task.id
            assert task.expected_keywords, task.id
            assert task.expected_tools, task.id

    def test_every_task_fits_corpus_and_tools(self) -> None:
        toolset_tools = {
            "calculator",
            "unit_convert",
            "search_handbook",
            "search_documents",
            "note_store",
        }
        for task in evals.TASK_SUITE:
            assert set(task.expected_tools) <= toolset_tools, task.id
            # every calculation/lookup answer must be derivable from a corpus:
            # the keyword set is non-empty and prompts mention corpus entities
            assert task.expected_keywords, task.id

    def test_dataset_builds(self) -> None:
        dataset = evals.build_dataset()
        assert len(dataset.cases) == len(evals.TASK_SUITE)
        for case in dataset.cases:
            assert [type(e).__name__ for e in case.evaluators] == [
                "AnswerSuccess",
                "ToolSelection",
                "StepBudget",
                "LatencyBudget",
            ]


class TestOfflineEvaluation:
    """The evaluate path runs fully offline from synthetic records."""

    def test_evaluate_records_and_build_report(self, tmp_path: Path) -> None:
        config = EvalConfig(
            reports_dir=tmp_path / "reports", records_path=tmp_path / "records.json"
        )
        records = [
            _record(task.id, answer="answer with " + " and ".join(task.expected_keywords))
            for task in evals.TASK_SUITE
        ]
        # one honest failure: wrong tools on t03
        records[2] = _record("t03", tools=("calculator",))

        report = evals.evaluate_records(records)
        assert len(report.cases) == len(evals.TASK_SUITE)
        averages = evals.suite_averages(report)
        # the injected failure is a tool-selection error; answers stay correct
        assert averages["AnswerSuccess"] == 1.0
        assert averages["ToolSelection"] == (len(evals.TASK_SUITE) - 1) / len(evals.TASK_SUITE)

        metrics_path = evals.build_report(report, config)
        metrics = json.loads(metrics_path.read_text())
        assert "agentic_suite" in metrics
        assert metrics["agentic_suite"]["success_rate"] == averages["AnswerSuccess"]
        assert "detail" in metrics and "per_task" in metrics["detail"]
        assert "tooling" in metrics["detail"]
        assert (config.reports_dir / "report.html").exists()
        for name in (
            "per_task_grading",
            "cost_latency_bars",
            "tool_usage_matrix",
            "node_waterfall",
            "agent_architecture",
        ):
            assert (config.reports_dir / "figures" / f"{name}.html").exists()
            assert (config.reports_dir / "figures" / f"{name}.json").exists()
        assert not (config.reports_dir / "figures" / "category_success.json").exists()

    def test_records_round_trip(self, tmp_path: Path) -> None:
        records = [_record(task.id) for task in evals.TASK_SUITE[:3]]
        path = evals.write_records(records, tmp_path / "records.json")
        assert evals.load_records(path) == records

    def test_old_records_without_new_fields_load_with_defaults(self, tmp_path: Path) -> None:
        """Pre-capture records (no tool_calls/plan_steps/critique_verdict) load fine."""
        record = _record("t01")
        payload = json.loads(record.model_dump_json())
        for key in ("tool_calls", "plan_steps", "critique_verdict"):
            payload.pop(key)
        assert set(payload) < set(TaskRunRecord.model_fields)
        path = tmp_path / "old_records.json"
        path.write_text(json.dumps([payload]))
        loaded = evals.load_records(path)
        assert loaded[0].tool_calls == []
        assert loaded[0].plan_steps == []
        assert loaded[0].critique_verdict is None
        assert loaded[0].steps_taken == record.steps_taken

    def test_tasks_json_round_trip(self) -> None:
        payload = evals.tasks_json(list(evals.TASK_SUITE))
        assert evals.parse_tasks(payload) == list(evals.TASK_SUITE)


class TestToolCallCapture:
    """Per-call tool traces land in the workflow result and run record."""

    def _scripted_tool_model(self) -> Any:
        """Scripted model whose executor really calls calculator + note_store."""
        from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
        from pydantic_ai.models.function import FunctionModel

        def responder(messages: list[Any], info: Any) -> ModelResponse:
            role = ""
            saw_response = False
            for message in messages:
                if isinstance(message, ModelResponse):
                    saw_response = True
                for part in getattr(message, "parts", []):
                    content = getattr(part, "content", "")
                    if isinstance(content, str):
                        if "PLANNER" in content:
                            role = "plan"
                        elif "EXECUTOR" in content:
                            role = "exec"
                        elif "CRITIQUE" in content:
                            role = "critique"
            if role == "plan":
                payload: dict[str, Any] = {
                    "steps": [
                        {
                            "id": 1,
                            "description": "Compute weekly diesel",
                            "tool": "calculator",
                            "expected_output": "75.6",
                        }
                    ],
                    "notes": "",
                }
            elif role == "exec":
                if not saw_response:
                    return ModelResponse(
                        parts=[
                            ToolCallPart(
                                tool_name="calculator",
                                args={"expr": "1.8*6*7"},
                                tool_call_id="c1",
                            )
                        ]
                    )
                payload = {
                    "findings": ["1.8*6*7 = 75.6"],
                    "draft": "The answer is 75.6 liters.",
                    "self_confidence": 0.9,
                }
            else:
                payload = {"verdict": "pass", "issues": [], "suggestion": ""}
            return ModelResponse(parts=[TextPart(content=json.dumps(payload))])

        return FunctionModel(responder)

    def test_tool_calls_captured_with_names_and_latency(self) -> None:
        from agentic_workflows.workflow import run_workflow

        result = run_workflow("weekly diesel?", model=self._scripted_tool_model())
        assert [call.name for call in result.tool_calls] == ["calculator"]
        (call,) = result.tool_calls
        assert call.node == "execute"
        assert call.latency_s >= 0.0
        assert call.result_chars > 0
        assert call.ok is True
        assert "1.8*6*7" in call.args_brief

    def test_plan_steps_and_critique_verdict_persisted(self) -> None:
        from agentic_workflows.workflow import run_workflow

        result = run_workflow("weekly diesel?", model=self._scripted_tool_model())
        assert result.plan_steps == ["1. Compute weekly diesel → calculator"]
        assert result.critique_verdict == "pass"


class TestToolingDecomposition:
    """The offline trajectory decomposition math behind detail.tooling."""

    def _pair(
        self,
        task_id: str,
        call_names: list[str],
    ) -> tuple[EvalTask, TaskRunRecord]:
        task = next(t for t in evals.TASK_SUITE if t.id == task_id)
        record = TaskRunRecord(
            task_id=task_id,
            status="ok",
            answer="x",
            steps_taken=["s"],
            tools_used=sorted(set(call_names)),
            tool_calls=[ToolCallTrace(name=name, node="execute") for name in call_names],
            confidence=0.9,
            duration_s=1.0,
        )
        return task, record

    def test_exact_set_and_extra_breakdown(self) -> None:
        task = evals.TASK_SUITE[2]  # t03: search_handbook + calculator
        exact = self._pair(task.id, ["search_handbook", "calculator"])
        noisy = self._pair(task.id, ["search_handbook", "calculator", "note_store"])
        missing = self._pair(task.id, ["calculator"])
        tooling = evals.decompose_tooling([exact, noisy, missing])
        assert tooling["n_calls"] == 6
        assert tooling["n_expected_calls"] == 5
        assert tooling["call_precision"] == round(5 / 6, 3)
        # recall: 2/2 + 2/2 + 1/2 = 5 expected slots of 6
        assert tooling["tool_recall"] == round(5 / 6, 3)
        assert tooling["exact_set_rate"] == round(1 / 3, 3)
        assert tooling["extra_calls"]["note_store"]["calls"] == 1
        assert tooling["extra_calls"]["note_store"]["tasks"] == [task.id]
        assert tooling["unused_expected"] == {task.id: ["search_handbook"]}
        assert tooling["per_tool"]["note_store"]["extra_calls"] == 1
        assert tooling["per_tool"]["calculator"]["expected_calls"] == 3

    def test_old_records_degrade_to_flat_tools_used(self) -> None:
        """Records without tool_calls fall back to one call per tools_used name."""
        task = evals.TASK_SUITE[0]  # t01: search_handbook
        record = _record(task.id, tools=("search_handbook", "note_store"))
        tooling = evals.decompose_tooling([(task, record)])
        assert tooling["n_calls"] == 2
        assert tooling["extra_calls"]["note_store"]["calls"] == 1


class TestHeldoutSuite:
    """The held-out set (audit finding 6): unseen prompts + designed-to-fail probes."""

    def test_suite_shape_and_disjointness(self) -> None:
        assert len(evals.HELDOUT_SUITE) == 10
        ids = [task.id for task in evals.HELDOUT_SUITE]
        assert len(ids) == len(set(ids))
        assert all(task.id.startswith("h") for task in evals.HELDOUT_SUITE)
        tuning_prompts = {task.prompt for task in evals.TASK_SUITE}
        assert all(task.prompt not in tuning_prompts for task in evals.HELDOUT_SUITE)

    def test_categories_spread_and_behavior_split(self) -> None:
        categories = {task.category for task in evals.HELDOUT_SUITE}
        assert {"lookup", "calculation", "conversion", "multi_step", "note_keeping"} <= categories
        answer = [t for t in evals.HELDOUT_SUITE if t.expected_behavior == "answer"]
        refuse = [t for t in evals.HELDOUT_SUITE if t.expected_behavior == "refuse"]
        assert len(answer) == 7
        assert len(refuse) == 3
        for task in answer:
            assert task.expected_keywords, task.id
            assert task.expected_tools, task.id
        for task in refuse:
            assert task.category == "out_of_scope", task.id
            assert task.expected_keywords == [], task.id
            assert task.expected_tools == [], task.id

    def test_refuse_probes_grade_refusal_not_keywords(self) -> None:
        dataset = evals.build_dataset(list(evals.HELDOUT_SUITE))
        by_name = {case.name: case for case in dataset.cases}
        refuse_names = {t.id for t in evals.HELDOUT_SUITE if t.expected_behavior == "refuse"}
        for name in refuse_names:
            grader_names = [type(e).__name__ for e in by_name[name].evaluators]
            assert grader_names == ["RefusalSuccess", "StepBudget", "LatencyBudget"], name
        answer_case = next(
            case for case in dataset.cases if case.inputs.expected_behavior == "answer"
        )
        grader_names = [type(e).__name__ for e in answer_case.evaluators]
        assert grader_names == ["AnswerSuccess", "ToolSelection", "StepBudget", "LatencyBudget"]

    def test_tasks_json_round_trip(self) -> None:
        payload = evals.tasks_json(list(evals.HELDOUT_SUITE))
        assert evals.parse_tasks(payload) == list(evals.HELDOUT_SUITE)


class TestRefusalGrader:
    def _ctx(self, task: EvalTask, record: TaskRunRecord) -> EvaluatorContext:
        return _ctx(task, record)

    def _probe(self) -> EvalTask:
        return next(t for t in evals.HELDOUT_SUITE if t.expected_behavior == "refuse")

    def _record(self, **kwargs: Any) -> TaskRunRecord:
        base: dict[str, Any] = dict(
            task_id=self._probe().id,
            status="ok",
            answer="I cannot do that: no tool supports this conversion.",
            steps_taken=["s"],
            tools_used=[],
            confidence=0.5,
            duration_s=5.0,
        )
        base.update(kwargs)
        return TaskRunRecord(**base)

    def test_refusal_marker_passes(self) -> None:
        task = self._probe()
        for phrasing in (
            "This cannot be done with the available tools.",
            "Unable to convert between those dimensions.",
            "Such a capability does not exist here.",
        ):
            record = self._record(answer=phrasing)
            assert evals.RefusalSuccess().evaluate(self._ctx(task, record)) is True

    def test_fabricated_answer_fails(self) -> None:
        task = self._probe()
        record = self._record(answer="The conversion gives 24.5 liters.")
        assert evals.RefusalSuccess().evaluate(self._ctx(task, record)) is False

    def test_crash_fails_even_with_marker(self) -> None:
        task = self._probe()
        record = self._record(status="workflow_error", answer="cannot complete")
        assert evals.RefusalSuccess().evaluate(self._ctx(task, record)) is False


class TestHeldoutEvaluation:
    """Held-out grading runs offline and merges detail.heldout into metrics.json."""

    def _records(self) -> list[TaskRunRecord]:
        records = []
        for task in evals.HELDOUT_SUITE:
            if task.expected_behavior == "refuse":
                answer = "I cannot do that — the available tools do not support this request."
                tools: tuple[str, ...] = ()
            else:
                answer = "answer with " + " and ".join(task.expected_keywords)
                tools = tuple(sorted(task.expected_tools))
            records.append(_record(task.id, answer=answer, tools=tools))
        return records

    def test_heldout_detail_aggregates_answer_and_refuse_split(self, tmp_path: Path) -> None:
        config = EvalConfig(
            reports_dir=tmp_path / "reports", records_path=tmp_path / "records.json"
        )
        (config.reports_dir).mkdir(parents=True)
        (config.reports_dir / "metrics.json").write_text('{"agentic_suite": {}}')

        detail = evals.write_heldout_metrics(self._records(), list(evals.HELDOUT_SUITE), config)
        assert detail["n_tasks"] == 10
        assert detail["n_answer"] == 7
        assert detail["n_should_fail"] == 3
        assert detail["answer_success"] == 1.0
        assert detail["tool_selection"] == 1.0
        assert detail["should_fail_pass_rate"] == 1.0
        assert detail["tooling"]["exact_set_rate"] == 1.0

        merged = json.loads((config.reports_dir / "metrics.json").read_text())
        assert merged["detail"]["heldout"]["answer_success"] == 1.0
        assert merged["agentic_suite"] == {}

    def test_heldout_detail_records_failures(self, tmp_path: Path) -> None:
        config = EvalConfig(
            reports_dir=tmp_path / "reports", records_path=tmp_path / "records.json"
        )
        (config.reports_dir).mkdir(parents=True)
        (config.reports_dir / "metrics.json").write_text("{}")
        records = self._records()
        # one fabricated refusal + one wrong tool set: the split must show both
        bad_probe = next(r for r in records if r.task_id in {"h08", "h09", "h10"})
        records = [
            (r.model_copy(update={"answer": "It is 24.5 liters, done."}) if r is bad_probe else r)
            for r in records
        ]
        records = [
            (
                r.model_copy(update={"tools_used": ["search_handbook", "note_store"]})
                if r.task_id == "h01"
                else r
            )
            for r in records
        ]
        detail = evals.write_heldout_metrics(records, list(evals.HELDOUT_SUITE), config)
        assert detail["should_fail_pass_rate"] == pytest.approx(2 / 3, abs=1e-3)
        assert detail["tool_selection"] == pytest.approx(6 / 7, abs=1e-3)
        assert detail["per_task"]["h01"]["tool_selection"] == 0.0
        assert detail["per_task"][bad_probe.task_id]["refusal_success"] == 0.0


class TestSuiteHonesty:
    """Guard against ground truths drifting away from the tools they grade."""

    def test_conversion_answers_match_tool_output(self) -> None:
        from agentic_workflows.tools import unit_convert

        assert "29.8258" in str(unit_convert(48, "km", "mi"))
        assert "55.1156" in str(unit_convert(25, "kg", "lb"))
        assert unit_convert(-20, "c", "f") == -4.0
        # held-out h05: drone range 8 km in miles
        assert "4.971" in str(unit_convert(8, "km", "mi"))

    def test_calculation_answers_match_tool_output(self) -> None:
        from agentic_workflows.tools import calculator

        assert calculator("1.8*6*7") == 75.6  # t03
        assert calculator("24 - (1.6*8 + 0.9*3)") == 8.5  # t04
        assert calculator("3.2*12") == 38.4  # t05
        assert calculator("(5000+1200)/(85*6)") == pytest.approx(12.15, abs=0.01)  # t06
        assert calculator("1.8*72") == 129.6  # t13
        assert calculator("250*2") == 500  # t10
        assert calculator("1800/4") == 450  # t14
        assert calculator("40+25") == 65 and calculator("65*0.6") == 39.0  # t11
        assert calculator("5000+1200") == 6200  # t12
        # held-out h03/h04/h06: full-tank runtime, 30-day burn, weekly uplink
        assert "133.3" in str(calculator("240/1.8"))
        assert calculator("1.8*8*30") == 432.0
        assert calculator("2*7") == 14.0 and calculator("14*250") == 3500.0

    def test_refuse_probes_are_actually_impossible(self) -> None:
        """Each should-fail probe must raise in the tools it tempts."""
        from agentic_workflows.tools import unit_convert

        task_by_id = {task.id: task for task in evals.HELDOUT_SUITE}
        probes = [t for t in evals.HELDOUT_SUITE if t.expected_behavior == "refuse"]
        assert {task.id for task in probes} == {"h08", "h09", "h10"}
        # h08: energy -> volume is not a unit conversion
        with pytest.raises(ValueError, match="unknown unit"):
            unit_convert(24, "kwh", "l")
        # h10: mass -> volume crosses dimensions
        with pytest.raises(ValueError, match="cannot convert"):
            unit_convert(40, "kg", "l")
        # h09 names a tool that does not exist in the toolset
        assert "inventory" in task_by_id["h09"].prompt.lower()
