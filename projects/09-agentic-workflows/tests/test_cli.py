"""CLI tests: prepare/evaluate run offline against synthetic records."""

from __future__ import annotations

import json
from pathlib import Path

from agentic_workflows import evals
from agentic_workflows.cli import app
from agentic_workflows.schemas import TaskRunRecord
from typer.testing import CliRunner

runner = CliRunner()


def _synthetic_records() -> list[TaskRunRecord]:
    return [
        TaskRunRecord(
            task_id=task.id,
            status="ok",
            answer="Result: " + ", ".join(task.expected_keywords),
            steps_taken=["plan (1 steps)", "execute (attempt 1)", "critique: pass"],
            tools_used=sorted(task.expected_tools),
            confidence=0.9,
            duration_s=10.0,
            input_tokens=120,
            output_tokens=60,
        )
        for task in evals.TASK_SUITE
    ]


def test_prepare_writes_tasks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["prepare"])
    assert result.exit_code == 0, result.output
    tasks_path = tmp_path / "data" / "tasks.json"
    assert tasks_path.exists()
    tasks = evals.parse_tasks(tasks_path.read_text())
    assert len(tasks) == len(evals.TASK_SUITE)


def test_evaluate_without_records_fails_cleanly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["prepare"])
    assert result.exit_code == 0
    result = runner.invoke(app, ["evaluate"])
    assert result.exit_code != 0
    assert "run-all" in result.output


def test_prepare_then_evaluate_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["prepare"]).exit_code == 0
    evals.write_records(_synthetic_records(), tmp_path / "data" / "run_records.json")

    result = runner.invoke(app, ["evaluate"])
    assert result.exit_code == 0, result.output
    metrics = json.loads((tmp_path / "reports" / "metrics.json").read_text())
    assert metrics["agentic_suite"]["success_rate"] == 1.0
    assert metrics["agentic_suite"]["tool_selection_accuracy"] == 1.0
    assert (tmp_path / "reports" / "report.html").exists()
