"""Eval-suite smoke: the full 12-case suite passes against the fake model."""

from pathlib import Path

from agent_chat.config import Settings
from agent_chat.evals import CASES
from agent_chat.evals.runner import run_evals, write_report


def test_full_suite_passes_against_fake(settings: Settings) -> None:
    report = run_evals(settings=settings)
    assert len(report.cases) == len(CASES) == 12
    failures = [
        f"{case.name}:{grader}"
        for case in report.cases
        for grader, result in case.assertions.items()
        if not result.value
    ]
    assert not failures, f"grader failures: {failures}"


def test_report_is_written(settings: Settings, tmp_path: Path) -> None:
    report = run_evals(settings=settings, cases=[CASES[0]])
    path = write_report(report, tmp_path / "evals.md")
    content = path.read_text(encoding="utf-8")
    assert "calc-percent" in content
    assert "Passed" in content
