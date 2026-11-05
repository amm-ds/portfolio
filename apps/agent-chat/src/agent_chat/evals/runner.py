"""Eval runner and report generation.

``run_evals`` grades the suite through pydantic-evals. With ``model=None``
(the default) every case runs against its own scripted fake — deterministic,
no network, CI-safe. Pass a real model (``main --model real``) to grade the
actual deployment. Reports are markdown tables written next to the suite.
"""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic_ai.messages import ModelMessage, ModelResponse, RetryPromptPart, ToolCallPart
from pydantic_ai.models import Model
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator
from pydantic_evals.reporting import EvaluationReport

from agent_chat.agent import build_agent, build_usage_limits
from agent_chat.approvals import AutoApproval
from agent_chat.config import Settings
from agent_chat.deps import ChatDeps
from agent_chat.evals.cases import CASES, EvalCase
from agent_chat.evals.graders import (
    AnswerKeywords,
    CitationsWhenGrounded,
    RefusalGraceful,
    ToolChoiceExact,
)
from agent_chat.evals.records import EvalRunRecord
from agent_chat.models import build_model
from agent_chat.testing import scripted_model

#: Harness tools that are not domain behavior — excluded from tool grading.
_HARNESS_TOOLS = frozenset({"final_result", "load_capability"})


def _case_evaluators(case: EvalCase) -> list[Evaluator[EvalCase, EvalRunRecord, None]]:
    """Refusal probes grade the refusal; everything else grades the answer."""
    if case.kind == "refuse":
        return [RefusalGraceful()]
    if case.kind == "tool_choice":
        return [AnswerKeywords(), ToolChoiceExact()]
    return [AnswerKeywords(), ToolChoiceExact(), CitationsWhenGrounded()]


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


async def run_case(
    case: EvalCase,
    *,
    settings: Settings,
    model: Model | None,
) -> EvalRunRecord:
    """One case through the assembled agent; failures become failed records."""
    resolved = model if model is not None else scripted_model(case.script)
    agent = build_agent(model=resolved, settings=settings)
    try:
        result = await agent.run(
            case.prompt,
            deps=ChatDeps(approvals=AutoApproval()),
            usage_limits=build_usage_limits(settings),
        )
        messages = result.all_messages()
        retries = _retry_prompts(messages)
        if retries:
            return EvalRunRecord(
                name=case.name,
                prompt=case.prompt,
                kind=case.kind,
                answer=result.output.text,
                citations=result.output.citations,
                tools_used=_tools_used(messages),
                error=f"tool call failed: {retries[0][:200]}",
            )
        return EvalRunRecord(
            name=case.name,
            prompt=case.prompt,
            kind=case.kind,
            answer=result.output.text,
            citations=result.output.citations,
            tools_used=_tools_used(messages),
        )
    except Exception as exc:  # broad: case boundary — failure becomes a failed record
        return EvalRunRecord(
            name=case.name,
            prompt=case.prompt,
            kind=case.kind,
            answer="",
            citations=[],
            tools_used=[],
            error=f"{type(exc).__name__}: {exc}",
        )


def run_evals(
    *,
    model: Model | None = None,
    settings: Settings | None = None,
    cases: Sequence[EvalCase] | None = None,
) -> EvaluationReport[EvalCase, EvalRunRecord, None]:
    """Run and grade the suite. ``model=None`` runs scripted fakes (CI mode)."""
    resolved_settings = settings or Settings()
    dataset = build_dataset(cases)

    async def run_one(case: EvalCase) -> EvalRunRecord:
        return await run_case(case, settings=resolved_settings, model=model)

    report: EvaluationReport[EvalCase, EvalRunRecord, None] = dataset.evaluate_sync(
        run_one, name="agent_chat_suite"
    )
    return report


def write_report(report: EvaluationReport[EvalCase, EvalRunRecord, None], path: Path) -> Path:
    """A small markdown summary: per-case grader verdicts plus totals."""
    lines = [
        f"# {report.name} — eval report",
        "",
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv: Sequence[str] | None = None) -> None:
    """CLI: ``python -m agent_chat.evals.runner [--model fake|real] [--out PATH]``."""
    parser = argparse.ArgumentParser(description="Run the agent-chat eval suite.")
    parser.add_argument("--model", choices=["fake", "real"], default="fake")
    parser.add_argument("--out", type=Path, default=Path("reports/evals.md"))
    args = parser.parse_args(argv)

    settings = Settings()
    model = build_model(settings) if args.model == "real" else None
    report = run_evals(model=model, settings=settings)
    path = write_report(report, args.out)
    summary = {
        "cases": len(report.cases),
        "assertions_passed": sum(1 for c in report.cases for r in c.assertions.values() if r.value),
        "assertions_total": sum(len(c.assertions) for c in report.cases),
        "report": str(path),
    }
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
