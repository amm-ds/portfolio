"""Report & metrics assembly: averages, tooling decomposition, metrics.json + HTML.

The offline half of the evaluate stage: per-grader averages, the trajectory
decomposition behind ``detail.tooling``, and the report builder that writes
``reports/metrics.json`` (+ ``detail``), the four figures (via
:mod:`agentic_workflows.figures`), and ``report.html``.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_json
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.report import ReportBuilder
from pydantic_evals.reporting import EvaluationReport

from agentic_workflows.config import EvalConfig
from agentic_workflows.figures import _score, suite_figures
from agentic_workflows.schemas import EvalTask, TaskRunRecord

logger = get_logger(__name__)

_GRADER_NAMES: tuple[str, ...] = ("AnswerSuccess", "ToolSelection", "StepBudget", "LatencyBudget")


def _case_score(
    report: EvaluationReport[EvalTask, TaskRunRecord, None], case_name: str, evaluator: str
) -> float | None:
    """The grader's score for a case, or None when that grader did not run there.

    Refuse probes carry a different grader set than answer tasks, so graders
    must average over the cases where they actually ran, not over all cases.
    """
    case = next((c for c in report.cases if c.name == case_name), None)
    if case is None:
        return None
    # Scalar evaluator outputs land in `assertions`; `scores` holds structured metrics.
    result = case.assertions.get(evaluator) or case.scores.get(evaluator)
    if result is None:
        return None
    value = result.value
    return float(value) if isinstance(value, int | float) else None


def suite_averages(report: EvaluationReport[EvalTask, TaskRunRecord, None]) -> dict[str, float]:
    """Mean pass rate per grader, averaged over the cases where it ran."""
    cases = list(report.cases)
    averages: dict[str, float] = {}
    for name in (*_GRADER_NAMES, "RefusalSuccess"):
        scores = [
            score for case in cases if (score := _case_score(report, case.name, name)) is not None
        ]
        if scores:
            averages[name] = sum(scores) / len(scores)
    return averages


# ---------------------------------------------------------------------------
# Offline trajectory decomposition of the tool-selection score
# ---------------------------------------------------------------------------


def decompose_tooling(pairs: list[tuple[EvalTask, TaskRunRecord]]) -> dict[str, Any]:
    """Decompose the exact-set tool-selection score from captured trajectories.

    Deterministic and offline: given each task's ``expected_tools`` and the
    record's ``tool_calls`` (falling back to the flat ``tools_used`` names —
    one call each — for records written before per-call capture), compute
    per-task extras/misses, per-tool call accounting (expected vs extra), an
    extra-call breakdown, and the expected-but-unused slots. This is what turns
    "3/15 exact-set" into an actionable statement about *which* tool is being
    over-called on *which* tasks.
    """
    per_task: dict[str, dict[str, Any]] = {}
    tool_calls: dict[str, int] = {}
    tool_expected_calls: dict[str, int] = {}
    tool_extra_calls: dict[str, int] = {}
    tool_tasks: dict[str, set[str]] = {}
    extra_tasks: dict[str, set[str]] = {}
    unused_expected: dict[str, list[str]] = {}

    n_calls = 0
    n_expected_calls = 0
    n_expected_slots = 0
    n_expected_hit = 0
    n_exact = 0

    for task, record in pairs:
        names = [call.name for call in record.tool_calls] or list(record.tools_used)
        expected = set(task.expected_tools)
        called = set(names)
        extra = sorted(called - expected)
        missing = sorted(expected - called)

        n_calls += len(names)
        n_expected_calls += sum(1 for name in names if name in expected)
        n_expected_slots += len(expected)
        n_expected_hit += len(expected & called)
        n_exact += int(not extra and not missing)

        for name in names:
            tool_calls[name] = tool_calls.get(name, 0) + 1
            tool_tasks.setdefault(name, set()).add(task.id)
            if name in expected:
                tool_expected_calls[name] = tool_expected_calls.get(name, 0) + 1
            else:
                tool_extra_calls[name] = tool_extra_calls.get(name, 0) + 1
                extra_tasks.setdefault(name, set()).add(task.id)
        if missing:
            unused_expected[task.id] = missing

        per_task[task.id] = {
            "expected": sorted(expected),
            "called": sorted(called),
            "extra": extra,
            "missing": missing,
            "n_calls": len(names),
            "exact_set": not extra and not missing,
        }

    per_tool = {
        name: {
            "calls": tool_calls[name],
            "expected_calls": tool_expected_calls.get(name, 0),
            "extra_calls": tool_extra_calls.get(name, 0),
            "tasks": sorted(tool_tasks[name]),
        }
        for name in sorted(tool_calls)
    }
    return {
        "n_tasks": len(pairs),
        "n_calls": n_calls,
        "n_expected_calls": n_expected_calls,
        # Call-level precision: share of all invocations that a correct plan
        # would have made. Task-level recall: share of expected tool slots
        # actually filled. Exact-set: the grader's own 3/15-style score.
        "call_precision": round(n_expected_calls / n_calls, 3) if n_calls else 0.0,
        "tool_recall": round(n_expected_hit / n_expected_slots, 3) if n_expected_slots else 0.0,
        "exact_set_rate": round(n_exact / len(pairs), 3) if pairs else 0.0,
        "per_tool": per_tool,
        "extra_calls": {
            name: {"calls": tool_extra_calls[name], "tasks": sorted(extra_tasks[name])}
            for name in sorted(extra_tasks)
        },
        "unused_expected": unused_expected,
        "per_task": per_task,
    }


def build_report(
    report: EvaluationReport[EvalTask, TaskRunRecord, None],
    config: EvalConfig,
) -> Path:
    """Write reports/metrics.json + figures + report.html from a graded report."""
    cases = list(report.cases)
    names = [case.name for case in cases]
    success = [_score(report, name, "AnswerSuccess") for name in names]
    tool_sel = [_score(report, name, "ToolSelection") for name in names]
    durations = [case.output.duration_s for case in cases]
    input_tokens = [case.output.input_tokens for case in cases]
    output_tokens = [case.output.output_tokens for case in cases]
    est_costs = [
        (i / 1e6 * config.usd_per_mtok_input + o / 1e6 * config.usd_per_mtok_output)
        for i, o in zip(input_tokens, output_tokens, strict=True)
    ]

    builder = ReportBuilder(
        title="09-agentic-workflows — evaluation report",
        figures_dir=config.reports_dir / "figures",
    )
    builder.add_run(
        RunResult(
            name="agentic_suite",
            metrics=[
                MetricResult(name="success_rate", value=sum(success) / max(len(success), 1)),
                MetricResult(
                    name="tool_selection_accuracy", value=sum(tool_sel) / max(len(tool_sel), 1)
                ),
                MetricResult(
                    name="avg_latency_s", value=statistics.mean(durations), higher_is_better=False
                ),
                MetricResult(
                    name="p95_latency_s",
                    value=sorted(durations)[
                        min(len(durations) - 1, round(0.95 * (len(durations) - 1)))
                    ],
                    higher_is_better=False,
                ),
                MetricResult(
                    name="avg_input_tokens",
                    value=statistics.mean(input_tokens),
                    higher_is_better=False,
                ),
                MetricResult(
                    name="avg_output_tokens",
                    value=statistics.mean(output_tokens),
                    higher_is_better=False,
                ),
                MetricResult(
                    name="est_cost_usd_per_task",
                    value=statistics.mean(est_costs),
                    higher_is_better=False,
                ),
            ],
        )
    )
    for case in cases:
        builder.add_run(
            RunResult(
                name=f"task_{case.name}",
                metrics=[
                    MetricResult(name="success", value=_score(report, case.name, "AnswerSuccess")),
                    MetricResult(
                        name="tool_selection", value=_score(report, case.name, "ToolSelection")
                    ),
                    MetricResult(
                        name="step_budget_ok", value=_score(report, case.name, "StepBudget")
                    ),
                    MetricResult(
                        name="latency_budget_ok", value=_score(report, case.name, "LatencyBudget")
                    ),
                    MetricResult(
                        name="latency_s", value=case.output.duration_s, higher_is_better=False
                    ),
                    MetricResult(
                        name="confidence", value=case.output.confidence, higher_is_better=False
                    ),
                ],
            )
        )

    figures = suite_figures(report, config)
    builder.build(config.reports_dir, figures=figures)
    for name, fig in figures.items():
        save_json(fig, config.reports_dir / "figures" / f"{name}.json")

    tooling = decompose_tooling([(case.inputs, case.output) for case in cases])
    detail = {
        "grader": "deterministic keyword + tool-set graders (pydantic-evals Evaluator subclasses)",
        "n_tasks": len(cases),
        "tooling": tooling,
        "per_task": {
            case.name: {
                "category": case.inputs.category,
                "success": _score(report, case.name, "AnswerSuccess"),
                "tool_selection": _score(report, case.name, "ToolSelection"),
                "step_budget_ok": _score(report, case.name, "StepBudget"),
                "latency_budget_ok": _score(report, case.name, "LatencyBudget"),
                "duration_s": case.output.duration_s,
                "confidence": case.output.confidence,
                "tools_used": case.output.tools_used,
                "tool_calls": [
                    json.loads(call.model_dump_json()) for call in case.output.tool_calls
                ],
                "plan_steps": case.output.plan_steps,
                "critique_verdict": case.output.critique_verdict,
                "answer": case.output.answer,
                "error": case.output.error,
            }
            for case in cases
        },
    }
    metrics_path = config.reports_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["detail"] = detail
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    _append_tooling_section(config.reports_dir / "report.html", tooling)
    logger.info("report written: %s", config.reports_dir / "report.html")
    return metrics_path


def _append_tooling_section(report_html: Path, tooling: dict[str, Any]) -> None:
    """Append the trajectory-decomposition section to report.html (in place).

    ``portfolio_eval``'s builder only knows runs + figures; the tooling
    section is this suite's own HTML, inserted before ``</body>`` so the
    library stays untouched.
    """
    if not report_html.exists():
        return

    def _row(cells: list[str], header: bool = False) -> str:
        tag = "th" if header else "td"
        return f"<tr>{''.join(f'<{tag}>{cell}</{tag}>' for cell in cells)}</tr>"

    header = _row(["tool", "calls", "expected", "extra", "tasks used on"], header=True)
    rows = "".join(
        _row(
            [
                f"<code>{name}</code>",
                str(stats["calls"]),
                str(stats["expected_calls"]),
                str(stats["extra_calls"]),
                ", ".join(stats["tasks"]),
            ]
        )
        for name, stats in tooling["per_tool"].items()
    )
    extra = (
        ", ".join(
            f"<code>{name}</code> on {stats['calls']} call(s), {len(stats['tasks'])} task(s)"
            for name, stats in tooling["extra_calls"].items()
        )
        or "none"
    )
    unused = (
        ", ".join(
            f"{task}: {'/'.join(tools)}" for task, tools in tooling["unused_expected"].items()
        )
        or "none"
    )
    section = (
        "<h2>Tooling decomposition</h2>"
        "<p>Offline trajectory decomposition of the exact-set tool-selection score from the "
        "captured per-call traces: call-level precision (share of invocations a correct plan "
        f"would make) <b>{tooling['call_precision']:.0%}</b>; task-level recall (expected tool "
        f"slots filled) <b>{tooling['tool_recall']:.0%}</b>; exact-set rate "
        f"<b>{tooling['exact_set_rate']:.0%}</b> over {tooling['n_calls']} calls on "
        f"{tooling['n_tasks']} tasks.</p>"
        f"<table>{header}{rows}</table>"
        f"<p><b>Extra calls:</b> {extra}.<br><b>Expected but unused:</b> {unused}.</p>"
    )
    html = report_html.read_text(encoding="utf-8")
    report_html.write_text(html.replace("</body>", f"{section}\n</body>"), encoding="utf-8")


# ---------------------------------------------------------------------------
# Held-out evaluation (audit finding 6): grade unseen tasks offline and merge
# the summary into reports/metrics.json under detail.heldout.
# ---------------------------------------------------------------------------


def heldout_detail(report: EvaluationReport[EvalTask, TaskRunRecord, None]) -> dict[str, Any]:
    """The held-out block for ``metrics.json detail.heldout``.

    Separates answer tasks (graded exactly like the tuning suite) from the
    designed-to-fail probes (graded by :class:`RefusalSuccess`), and keeps the
    same per-task tooling decomposition so held-out behavior can be compared
    with the tuning run call by call.
    """
    cases = list(report.cases)
    answer_cases = [c for c in cases if c.inputs.expected_behavior == "answer"]
    refuse_cases = [c for c in cases if c.inputs.expected_behavior == "refuse"]

    def _avg(selected: list[Any], grader: str) -> float:
        scores = [_case_score(report, c.name, grader) for c in selected]
        present = [s for s in scores if s is not None]
        return round(sum(present) / len(present), 3) if present else 0.0

    return {
        "n_tasks": len(cases),
        "n_answer": len(answer_cases),
        "n_should_fail": len(refuse_cases),
        # What the tuning set cannot measure: unseen prompts (prompt-overfit
        # check) and graceful-failure behavior on impossible requests.
        "answer_success": _avg(answer_cases, "AnswerSuccess"),
        "tool_selection": _avg(answer_cases, "ToolSelection"),
        "step_budget": _avg(cases, "StepBudget"),
        "latency_budget": _avg(cases, "LatencyBudget"),
        "should_fail_pass_rate": _avg(refuse_cases, "RefusalSuccess"),
        # Tooling decomposition is computed over answer tasks only: probes may
        # legitimately search the corpus before refusing (expected_tools is
        # empty for them, so any call would read as an "extra").
        "tooling": decompose_tooling([(case.inputs, case.output) for case in answer_cases]),
        "per_task": {
            case.name: {
                "category": case.inputs.category,
                "expected_behavior": case.inputs.expected_behavior,
                "success": _case_score(report, case.name, "AnswerSuccess"),
                "refusal_success": _case_score(report, case.name, "RefusalSuccess"),
                "tool_selection": _case_score(report, case.name, "ToolSelection"),
                "duration_s": case.output.duration_s,
                "tools_used": case.output.tools_used,
                "tool_calls": [
                    json.loads(call.model_dump_json()) for call in case.output.tool_calls
                ],
                "critique_verdict": case.output.critique_verdict,
                "answer": case.output.answer,
                "error": case.output.error,
            }
            for case in cases
        },
    }


def write_heldout_metrics(
    records: list[TaskRunRecord],
    tasks: list[EvalTask],
    config: EvalConfig,
) -> dict[str, Any]:
    """Grade held-out records offline and merge ``detail.heldout`` into metrics.json."""
    # Local import: evaluate_records lives in evals, which re-exports this
    # module — a module-level import would be circular.
    from agentic_workflows.evals import evaluate_records

    report = evaluate_records(records, tasks=tasks)
    detail = heldout_detail(report)
    metrics_path = config.reports_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    detail_block = metrics.setdefault("detail", {})
    detail_block["heldout"] = detail
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    logger.info("held-out metrics merged into %s", metrics_path)
    return detail


# ---------------------------------------------------------------------------
