"""Eval runner and report generation.

``run_evals`` grades the suite through pydantic-evals. With ``model=None``
(the default) every case runs against its own scripted fake — deterministic,
no network, CI-safe. Pass a real model (``main --model real``) to grade the
actual deployment. Reports are markdown tables written next to the suite.
"""

import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import Model
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator
from pydantic_evals.reporting import EvaluationReport

from agent_chat.agent import build_agent, build_usage_limits
from agent_chat.approvals import AutoApproval, DenyAll
from agent_chat.config import Settings
from agent_chat.deps import ChatDeps
from agent_chat.evals.cases import CASES, EvalCase
from agent_chat.evals.graders import (
    AnswerKeywords,
    CitationsWhenGrounded,
    RefusalGraceful,
    SentMessagesExact,
    ToolChoiceExact,
)
from agent_chat.evals.records import EvalRunRecord
from agent_chat.memory.notebook import FileNotebook
from agent_chat.models import build_model, primary_model_name
from agent_chat.testing import scripted_model

#: Harness tools that are not domain behavior — excluded from tool grading.
_HARNESS_TOOLS = frozenset({"final_result", "load_capability"})


def _case_evaluators(case: EvalCase) -> list[Evaluator[EvalCase, EvalRunRecord, None]]:
    """Attach only graders that have a case-specific contract to check."""
    graders: list[Evaluator[EvalCase, EvalRunRecord, None]] = []
    if case.kind == "refuse":
        graders.extend([RefusalGraceful(), ToolChoiceExact()])
    else:
        if case.expected_keywords:
            graders.append(AnswerKeywords())
        graders.append(ToolChoiceExact())
    if case.expect_citations:
        graders.append(CitationsWhenGrounded())
    if case.expected_sent is not None:
        graders.append(SentMessagesExact())
    return graders


def build_dataset(
    cases: Sequence[EvalCase] | None = None,
) -> Dataset[EvalCase, EvalRunRecord, None]:
    """The suite as a pydantic-evals dataset with per-kind graders attached."""
    selected = list(cases or CASES)
    return Dataset(
        name="agent_chat_suite",
        cases=[
            Case(
                name=case.name,
                inputs=case,
                expected_output=None,
                evaluators=tuple(_case_evaluators(case)),
            )
            for case in selected
        ],
    )


def _tools_used(messages: list[ModelMessage]) -> list[str]:
    """Ordered domain-tool names across a run (harness calls excluded)."""
    names: list[str] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ToolCallPart) and part.tool_name not in _HARNESS_TOOLS:
                    names.append(part.tool_name)
    return names


def _retry_prompts(messages: list[ModelMessage]) -> list[str]:
    """Texts of retry prompts the model received — i.e. failed tool calls.

    A scripted run that "answers" after a failed call grades as an error: the
    suite must notice a tool was rejected, not just that a final answer came.
    """
    texts: list[str] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, RetryPromptPart):
                texts.append(str(part.content))
    return texts


def _tool_evidence(messages: Sequence[ModelMessage]) -> list[str]:
    """Return exact tool text, flattening string lists instead of repr-escaping them."""
    evidence: list[str] = []
    for message in messages:
        for part in message.parts:
            if not isinstance(part, ToolReturnPart):
                continue
            content = part.content
            if isinstance(content, list) and all(isinstance(item, str) for item in content):
                evidence.extend(content)
            else:
                evidence.append(str(content))
    return evidence


async def run_case(
    case: EvalCase,
    *,
    settings: Settings,
    model: Model | None,
) -> EvalRunRecord:
    """One case through the assembled agent; failures become failed records."""
    resolved = model if model is not None else scripted_model(case.script)
    agent = build_agent(model=resolved, settings=settings)
    notebook = FileNotebook(settings.memory_data_dir)
    deps = ChatDeps(
        approvals=AutoApproval() if case.auto_approve else DenyAll(),
        memory=notebook,
        session_id=f"eval-{case.name}",
    )
    messages: list[ModelMessage] = []
    try:
        result = await agent.run(
            case.prompt,
            deps=deps,
            usage_limits=build_usage_limits(settings),
        )
        messages = result.all_messages()
        if case.follow_up is not None:
            # A fresh conversation proves the notebook, not message history,
            # carries the fact into the later run.
            result = await agent.run(
                case.follow_up,
                deps=deps,
                usage_limits=build_usage_limits(settings),
            )
            messages = [*messages, *result.all_messages()]
        retries = _retry_prompts(messages)
        return EvalRunRecord(
            name=case.name,
            prompt=case.prompt,
            kind=case.kind,
            answer=result.output.text,
            citations=result.output.citations,
            tools_used=_tools_used(messages),
            evidence=_tool_evidence(messages),
            sent=list(deps.sent),
            error=f"tool call failed: {retries[0][:200]}" if retries else None,
        )
    except Exception as exc:  # broad: case boundary — failure becomes a failed record
        return EvalRunRecord(
            name=case.name,
            prompt=case.prompt,
            kind=case.kind,
            answer="",
            citations=[],
            tools_used=_tools_used(messages),
            evidence=_tool_evidence(messages),
            sent=list(deps.sent),
            error=f"{type(exc).__name__}: {exc}",
        )


def run_evals(
    *,
    model: Model | None = None,
    settings: Settings | None = None,
    cases: Sequence[EvalCase] | None = None,
    repeat: int = 1,
) -> EvaluationReport[EvalCase, EvalRunRecord, None]:
    """Run and grade the suite with an isolated, suite-scoped notebook."""
    if repeat < 1:
        raise ValueError("repeat must be a positive integer")
    dataset = build_dataset(cases)
    with tempfile.TemporaryDirectory(prefix="agent-chat-evals-") as memory_root:
        resolved_settings = (settings or Settings()).model_copy(
            update={"memory_data_dir": Path(memory_root)}
        )

        async def run_one(case: EvalCase) -> EvalRunRecord:
            return await run_case(case, settings=resolved_settings, model=model)

        report: EvaluationReport[EvalCase, EvalRunRecord, None] = dataset.evaluate_sync(
            run_one,
            name="agent_chat_suite",
            repeat=repeat,
            progress=False,
            max_concurrency=1,
        )
    return report


def _report_failed(report: EvaluationReport[EvalCase, EvalRunRecord, None]) -> bool:
    return bool(report.failures) or any(
        case.output.error is not None
        or any(not result.value for result in case.assertions.values())
        for case in report.cases
    )


def write_report(
    report: EvaluationReport[EvalCase, EvalRunRecord, None],
    path: Path,
    *,
    model_label: str | None = None,
) -> Path:
    """A markdown summary with actionable diagnostics for every failed case."""
    lines = [f"# {report.name} — eval report", ""]
    if model_label is not None:
        lines += [f"Model: `{model_label}`", ""]
    lines += [
        "| case | kind | grader | verdict |",
        "|---|---|---|---|",
    ]
    passed = 0
    total = 0
    for case_report in report.cases:
        for grader_name, result in case_report.assertions.items():
            total += 1
            ok = bool(result.value)
            passed += 1 if ok else 0
            lines.append(
                f"| {case_report.name} | {case_report.inputs.kind} "
                f"| {grader_name} | {'pass' if ok else 'FAIL: ' + (result.reason or '')} |"
            )
    lines += ["", f"Passed {passed}/{total} grader assertions.", ""]

    failed_cases = [
        case
        for case in report.cases
        if case.output.error is not None
        or any(not result.value for result in case.assertions.values())
    ]
    if failed_cases:
        lines += ["## Failure diagnostics", ""]
    for case in failed_cases:
        failed_graders = [name for name, result in case.assertions.items() if not result.value]
        sent = [message.model_dump(mode="json") for message in case.output.sent]
        citations = [item.model_dump(mode="json") for item in case.output.citations]
        lines += [
            f"### {case.name}",
            "",
            f"- Failed graders: {', '.join(failed_graders) or 'run error'}",
            f"- Answer: {json.dumps(case.output.answer, ensure_ascii=False)}",
            f"- Error: {case.output.error or 'none'}",
            f"- Tools used: {json.dumps(case.output.tools_used)}",
            f"- Citations: {json.dumps(citations, ensure_ascii=False)}",
            f"- Sent: {json.dumps(sent, ensure_ascii=False)}",
            f"- Tool evidence: {json.dumps(case.output.evidence, ensure_ascii=False)}",
            "",
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    """Run selected cases and return 1 when any assertion or run fails."""
    parser = argparse.ArgumentParser(description="Run the agent-chat eval suite.")
    parser.add_argument("--model", choices=["fake", "real"], default="fake")
    parser.add_argument("--out", type=Path, default=Path("reports/evals.md"))
    parser.add_argument("--case", help="run only the case with this exact name")
    parser.add_argument("--repeat", type=int, default=1, help="runs per case (positive integer)")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be a positive integer")
    selected: Sequence[EvalCase] = CASES
    if args.case is not None:
        selected = [case for case in CASES if case.name == args.case]
        if not selected:
            parser.error(f"unknown case: {args.case!r}")

    settings = Settings()
    model = build_model(settings) if args.model == "real" else None
    report = run_evals(model=model, settings=settings, cases=selected, repeat=args.repeat)
    model_label = "fake" if model is None else f"{settings.provider}:{primary_model_name(settings)}"
    path = write_report(report, args.out, model_label=model_label)
    summary = {
        "cases": len(report.cases),
        "assertions_passed": sum(1 for c in report.cases for r in c.assertions.values() if r.value),
        "assertions_total": sum(len(c.assertions) for c in report.cases),
        "report": str(path),
    }
    print(json.dumps(summary))
    return 1 if _report_failed(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
