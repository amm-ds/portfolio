"""Unit tests for the eval suite: graders, suite integrity, offline reporting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentic_workflows import evals
from agentic_workflows.config import EvalConfig
from agentic_workflows.schemas import EvalTask, TaskRunRecord
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
        assert (config.reports_dir / "report.html").exists()
        for name in ("per_task_grading", "per_task_latency", "category_success"):
            assert (config.reports_dir / "figures" / f"{name}.html").exists()
            assert (config.reports_dir / "figures" / f"{name}.json").exists()

    def test_records_round_trip(self, tmp_path: Path) -> None:
        records = [_record(task.id) for task in evals.TASK_SUITE[:3]]
        path = evals.write_records(records, tmp_path / "records.json")
        assert evals.load_records(path) == records

    def test_tasks_json_round_trip(self) -> None:
        payload = evals.tasks_json(list(evals.TASK_SUITE))
        assert evals.parse_tasks(payload) == list(evals.TASK_SUITE)


class TestSuiteHonesty:
    """Guard against ground truths drifting away from the tools they grade."""

    def test_conversion_answers_match_tool_output(self) -> None:
        from agentic_workflows.tools import unit_convert

        assert "29.8258" in str(unit_convert(48, "km", "mi"))
        assert "55.1156" in str(unit_convert(25, "kg", "lb"))
        assert unit_convert(-20, "c", "f") == -4.0

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
