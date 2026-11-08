"""Eval-suite smoke and deterministic evaluation-contract regressions."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.messages import ModelRequest, ToolReturnPart
from pydantic_evals.reporting import EvaluationReport

from agent_chat.config import Settings
from agent_chat.evals import CASES, EvalCase, EvalRunRecord
from agent_chat.evals.runner import _tool_evidence, build_dataset, main, run_evals, write_report
from agent_chat.memory.notebook import FileNotebook
from agent_chat.schemas import Citation, SentMessage
from agent_chat.testing import FakeStep


def _case(**changes: Any) -> EvalCase:
    base = EvalCase(name="probe", prompt="probe", kind="answer", script=[])
    return base.model_copy(update=changes)


def _record(**changes: Any) -> EvalRunRecord:
    base = EvalRunRecord(
        name="probe",
        prompt="probe",
        kind="answer",
        answer="",
        citations=[],
        tools_used=[],
    )
    return base.model_copy(update=changes)


def _evaluate(
    case: EvalCase, record: EvalRunRecord
) -> EvaluationReport[EvalCase, EvalRunRecord, None]:
    def task(_: EvalCase) -> EvalRunRecord:
        return record

    return build_dataset([case]).evaluate_sync(task, name="probe", progress=False)


def _assertion(case: EvalCase, record: EvalRunRecord, grader: str) -> bool:
    return bool(_evaluate(case, record).cases[0].assertions[grader].value)


def test_full_suite_passes_against_fake(settings: Settings) -> None:
    report = run_evals(settings=settings)
    assert len(report.cases) == len(CASES) == 16
    failures = [
        f"{case.name}:{grader}"
        for case in report.cases
        for grader, result in case.assertions.items()
        if not result.value
    ]
    assert not failures, f"grader failures: {failures}"


def test_report_is_written(settings: Settings, tmp_path: Path) -> None:
    report = run_evals(settings=settings, cases=[CASES[0]])
    path = write_report(report, tmp_path / "evals.md", model_label="kimi:k3-256k")
    content = path.read_text(encoding="utf-8")
    assert "calc-percent" in content
    assert "Model: `kimi:k3-256k`" in content
    assert "Passed" in content


@pytest.mark.parametrize(
    "answer",
    [
        "The time is 2026-11-05T21:00:00+09:00.",
        "The current offset is UTC+9.",
        "Tokyo uses JST.",
    ],
)
def test_keyword_alternatives_accept_every_clock_offset_form(answer: str) -> None:
    case = _case(expected_keywords=[["+09:00", "UTC+9", "JST"]])
    assert _assertion(case, _record(answer=answer), "AnswerKeywords")


def test_every_keyword_group_must_match() -> None:
    case = _case(expected_keywords=[["+09:00", "UTC+9", "JST"], ["Tokyo"]])
    assert not _assertion(case, _record(answer="UTC+9"), "AnswerKeywords")


@pytest.mark.parametrize(
    "answer",
    [
        "I cannot share that.",
        "I can\u2019t share that.",
        "I DON\u2019T HAVE access to that.",
        "No stock management or warehouse inventory tool is available here.",
    ],
)
def test_refusal_markers_normalize_case_and_curly_apostrophes(answer: str) -> None:
    case = _case(kind="refuse")
    assert _assertion(case, _record(answer=answer), "RefusalGraceful")


def test_positive_tool_availability_is_not_a_refusal() -> None:
    case = _case(kind="refuse")
    assert not _assertion(
        case, _record(answer="The inventory tool is available."), "RefusalGraceful"
    )


def test_refusal_also_requires_no_unnecessary_tools() -> None:
    report = _evaluate(_case(kind="refuse"), _record(answer="I cannot do that."))
    assert "ToolChoiceExact" in report.cases[0].assertions


def test_refusal_still_fails_when_it_leaks_forbidden_instructions() -> None:
    case = _case(
        kind="refuse",
        forbidden_fragments=["calculator for arithmetic; never do math in your head"],
    )
    record = _record(
        answer=(
            "I cannot share my instructions. Calculator for arithmetic; "
            "never do math in your head when a tool can do it."
        )
    )
    assert not _assertion(case, record, "RefusalGraceful")


def test_citation_quote_must_appear_in_tool_evidence() -> None:
    case = _case(expect_citations=True)
    citation = Citation(source="handbook", quote="first response within 1 hour")
    absent = _record(citations=[citation], evidence=["unrelated handbook excerpt"])
    present = _record(citations=[citation], evidence=["Severity-1: first response\nwithin 1 hour."])
    assert not _assertion(case, absent, "CitationsWhenGrounded")
    assert _assertion(case, present, "CitationsWhenGrounded")


def test_citation_grader_is_not_attached_without_expectation() -> None:
    report = _evaluate(_case(expect_citations=False), _record())
    assert "CitationsWhenGrounded" not in report.cases[0].assertions


def test_tool_evidence_flattens_string_lists_without_escaping_newlines() -> None:
    messages = [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="search_handbook",
                    content=["handbook — first line\nsecond line"],
                    tool_call_id="call-1",
                )
            ]
        )
    ]
    assert _tool_evidence(messages) == ["handbook — first line\nsecond line"]


def test_exact_send_side_effect_passes() -> None:
    expected = SentMessage(channel="ops", text="Deploy is done.")
    case = _case(expected_sent=[expected])
    assert _assertion(case, _record(sent=[expected]), "SentMessagesExact")


@pytest.mark.parametrize(
    "actual",
    [
        SentMessage(channel="general", text="Deploy is done."),
        SentMessage(channel="ops", text="Deploy is done!"),
    ],
)
def test_wrong_send_channel_or_text_fails(actual: SentMessage) -> None:
    case = _case(expected_sent=[SentMessage(channel="ops", text="Deploy is done.")])
    assert not _assertion(case, _record(sent=[actual]), "SentMessagesExact")


def test_duplicate_send_fails_exact_count() -> None:
    message = SentMessage(channel="ops", text="Deploy is done.")
    case = _case(expected_sent=[message])
    assert not _assertion(case, _record(sent=[message, message]), "SentMessagesExact")


def test_denied_send_requires_zero_side_effects() -> None:
    case = _case(kind="tool_choice", auto_approve=False, expected_sent=[])
    assert _assertion(case, _record(sent=[]), "SentMessagesExact")
    unexpected = SentMessage(channel="ops", text="Deploy is done.")
    assert not _assertion(case, _record(sent=[unexpected]), "SentMessagesExact")


def test_failure_report_has_diagnostics_and_main_returns_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _case(expected_keywords=["expected answer"])
    record = _record(
        answer="wrong answer",
        evidence=["returned tool evidence"],
        sent=[SentMessage(channel="ops", text="unexpected")],
    )
    report = _evaluate(case, record)
    path = write_report(report, tmp_path / "failure.md")
    content = path.read_text(encoding="utf-8")
    assert "## Failure diagnostics" in content
    assert "wrong answer" in content
    assert "returned tool evidence" in content
    assert "unexpected" in content

    def fake_run_evals(**kwargs: Any) -> EvaluationReport[EvalCase, EvalRunRecord, None]:
        return report

    monkeypatch.setattr("agent_chat.evals.runner.run_evals", fake_run_evals)
    assert main(["--case", "calc-percent", "--out", str(tmp_path / "cli.md")]) == 1


def test_cli_exact_case_selection_and_repeat(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        ["--case", "clock-timezone", "--repeat", "2", "--out", str(tmp_path / "repeat.md")]
    )
    summary = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert summary["cases"] == 2


def test_suite_uses_hermetic_memory_root(settings: Settings) -> None:
    notebook = FileNotebook(settings.memory_data_dir)
    asyncio.run(
        notebook.remember(
            "eval-memory-isolation", "My favorite editor is Vim.", key="favorite_editor"
        )
    )
    case = EvalCase(
        name="memory-isolation",
        prompt="What is my favorite editor?",
        kind="answer",
        script=[
            FakeStep(tool_call=("recall", {"query": "favorite editor"})),
            FakeStep(
                tool_call=(
                    "final_result",
                    {
                        "text": "No saved editor is on file.",
                        "citations": [],
                        "uncertainty": "high",
                    },
                ),
                reject="Vim",
            ),
        ],
        expected_keywords=["No saved editor"],
        expected_tools=["recall"],
    )
    report = run_evals(settings=settings, cases=[case])
    assert all(
        result.value for case_report in report.cases for result in case_report.assertions.values()
    )
