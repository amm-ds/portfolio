"""Evaluation harness: synthetic task suite, typed graders, reports.

The suite (``TASK_SUITE``) is 14 tasks over the deterministic research-ops
corpus with exact ground truths — keyword checks the final answer must contain
and the exact set of tools a correct solution needs. Grading runs through
``pydantic-evals`` (``Dataset`` + custom ``Evaluator`` subclasses); the report
builder then aggregates per-task and per-category results into
``reports/metrics.json``, three plotly figures, and the HTML report.

Two entry points, matching the DVC stages:

- :func:`run_suite` — actually runs every task through the workflow graph
  (needs a live model: env provider or local Ollama).
- :func:`evaluate_records` — grades a previously written
  ``data/run_records.json``; fully offline because grading is deterministic.
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from portfolio_core.llm import build_model
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_json
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.report import ReportBuilder
from pydantic_ai.models import Model
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext
from pydantic_evals.reporting import EvaluationReport

from agentic_workflows.config import EvalConfig
from agentic_workflows.schemas import EvalTask, TaskRunRecord
from agentic_workflows.workflow import run_workflow_async

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# The synthetic task suite — ground truths derived from tools.HANDBOOK
# ---------------------------------------------------------------------------

TASK_SUITE: tuple[EvalTask, ...] = (
    EvalTask(
        id="t01",
        prompt="What is the sample freezer setpoint and its alarm band?",
        category="lookup",
        expected_keywords=["-20", "3"],
        expected_tools=["search_handbook"],
    ),
    EvalTask(
        id="t02",
        prompt="Which radio channel and frequency are used for the hourly check-ins?",
        category="lookup",
        expected_keywords=["3", "146.46"],
        expected_tools=["search_handbook"],
    ),
    EvalTask(
        id="t03",
        prompt="How many liters of diesel does the generator burn in one week?",
        category="calculation",
        expected_keywords=["75.6"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="t04",
        prompt=(
            "After a typical 8-hour night (base load plus the HVAC surge), how many kWh of "
            "usable battery capacity remain in the battery bank?"
        ),
        category="calculation",
        expected_keywords=["8.5"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="t05",
        prompt="What is the total daily energy yield of the solar array in kWh?",
        category="calculation",
        expected_keywords=["38.4"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="t06",
        prompt=(
            "For how many full days does the station's total water storage last the crew "
            "at the budgeted consumption rate?"
        ),
        category="calculation",
        expected_keywords=["12"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="t07",
        prompt="Convert the 48 km one-way distance to the relay station to miles.",
        category="conversion",
        expected_keywords=["29.8258"],
        expected_tools=["unit_convert"],
    ),
    EvalTask(
        id="t08",
        prompt="Convert 25 kg of ration packs to pounds.",
        category="conversion",
        expected_keywords=["55.1156"],
        expected_tools=["unit_convert"],
    ),
    EvalTask(
        id="t09",
        prompt="What is -20 °C in Fahrenheit?",
        category="conversion",
        expected_keywords=["-4"],
        expected_tools=["unit_convert"],
    ),
    EvalTask(
        id="t10",
        prompt="How many MB can be transferred via satellite uplink per day in total?",
        category="multi_step",
        expected_keywords=["500"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="t11",
        prompt=(
            "How many ration packs are stored across both supply caches, and what is their "
            "combined weight in kg?"
        ),
        category="multi_step",
        expected_keywords=["65", "39"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="t12",
        prompt=(
            "Compute the station's total water storage in liters and record the figure in "
            "the ops notebook for the weekly log."
        ),
        category="note_keeping",
        expected_keywords=["6200"],
        expected_tools=["search_handbook", "calculator", "note_store"],
    ),
    EvalTask(
        id="t13",
        prompt="How many liters of diesel must be on hand to satisfy the fuel reserve policy?",
        category="calculation",
        expected_keywords=["129.6"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="t14",
        prompt=(
            "Can one satellite uplink window carry the compressed daily science data? "
            "Answer yes or no with the numbers."
        ),
        category="multi_step",
        expected_keywords=["450"],
        expected_tools=["search_handbook", "calculator"],
    ),
)


# ---------------------------------------------------------------------------
# Graders: deterministic Evaluator subclasses (no LLM in the judge)
# ---------------------------------------------------------------------------


@dataclass
class AnswerSuccess(Evaluator[EvalTask, TaskRunRecord, None]):
    """All expected ground-truth keywords appear in the final answer.

    Thousand separators are normalized away (``6,200`` matches ``6200``) so
    formatting alone cannot flip a substantively correct answer.
    """

    def evaluate(self, ctx: EvaluatorContext[EvalTask, TaskRunRecord, None]) -> bool:
        answer = ctx.output.answer.lower().replace(",", "")
        return all(keyword.lower() in answer for keyword in ctx.inputs.expected_keywords)


@dataclass
class ToolSelection(Evaluator[EvalTask, TaskRunRecord, None]):
    """Exact tool-set match: right tools called, no missing, no extras."""

    def evaluate(self, ctx: EvaluatorContext[EvalTask, TaskRunRecord, None]) -> bool:
        return set(ctx.output.tools_used) == set(ctx.inputs.expected_tools)


@dataclass
class StepBudget(Evaluator[EvalTask, TaskRunRecord, None]):
    """The workflow stayed within the task's step budget."""

    def evaluate(self, ctx: EvaluatorContext[EvalTask, TaskRunRecord, None]) -> bool:
        return len(ctx.output.steps_taken) <= ctx.inputs.max_steps


@dataclass
class LatencyBudget(Evaluator[EvalTask, TaskRunRecord, None]):
    """The run finished within the task's latency budget."""

    def evaluate(self, ctx: EvaluatorContext[EvalTask, TaskRunRecord, None]) -> bool:
        return ctx.output.duration_s <= ctx.inputs.latency_budget_s


SUITE_EVALUATORS: tuple[Evaluator[EvalTask, TaskRunRecord, None], ...] = (
    AnswerSuccess(),
    ToolSelection(),
    StepBudget(),
    LatencyBudget(),
)


def build_dataset(tasks: list[EvalTask] | None = None) -> Dataset[EvalTask, TaskRunRecord, None]:
    """The suite as a pydantic-evals dataset with the graders attached."""
    selected = tasks or list(TASK_SUITE)
    return Dataset(
        name="agentic_workflows_suite",
        cases=[
            Case(name=task.id, inputs=task, expected_output=None, evaluators=list(SUITE_EVALUATORS))
            for task in selected
        ],
    )


# ---------------------------------------------------------------------------
# Running the suite (live model) — DVC `run` stage
# ---------------------------------------------------------------------------


def run_suite(
    config: EvalConfig,
    *,
    model: Model | None = None,
    tasks: list[EvalTask] | None = None,
) -> list[TaskRunRecord]:
    """Run every task through the workflow graph; returns typed records."""
    selected = tasks or list(TASK_SUITE)
    resolved_model = model if model is not None else build_model()
    records: list[TaskRunRecord] = []
    for task in selected:
        start = time.perf_counter()
        try:
            result = run_workflow_sync(
                task.prompt,
                model=resolved_model,
                max_execute_retries=config.max_execute_retries,
                max_critique_loops=config.max_critique_loops,
            )
            records.append(
                TaskRunRecord(
                    task_id=task.id,
                    status="ok",
                    answer=result.answer,
                    steps_taken=result.steps_taken,
                    tools_used=result.tools_used,
                    confidence=result.confidence,
                    retries=result.retries,
                    critique_loops=result.critique_loops,
                    duration_s=round(time.perf_counter() - start, 3),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
            )
        except Exception as exc:
            logger.exception("task %s failed", task.id)
            records.append(
                TaskRunRecord(
                    task_id=task.id,
                    status="workflow_error",
                    answer="",
                    steps_taken=[],
                    tools_used=[],
                    confidence=0.0,
                    duration_s=round(time.perf_counter() - start, 3),
                    error=str(exc),
                )
            )
        logger.info(
            "task %s done in %.1fs (tools: %s)",
            task.id,
            records[-1].duration_s,
            records[-1].tools_used,
        )
    return records


def run_workflow_sync(task_prompt: str, *, model: Model, **kwargs: Any) -> Any:
    """Sync bridge so the suite driver stays sync without a nested event loop."""
    import asyncio

    return asyncio.run(
        run_workflow_async(task_prompt, model=model, **kwargs),
    )


def _normalize_record(record: TaskRunRecord) -> TaskRunRecord:
    """Strip the structured-output tool call (`final_result`) from tools_used."""
    cleaned = [name for name in record.tools_used if name != "final_result"]
    if cleaned != record.tools_used:
        return record.model_copy(update={"tools_used": cleaned})
    return record


def write_records(records: list[TaskRunRecord], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [json.loads(_normalize_record(record).model_dump_json()) for record in records]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("wrote %d run records to %s", len(records), path)
    return path


def load_records(path: Path) -> list[TaskRunRecord]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [_normalize_record(TaskRunRecord.model_validate(item)) for item in raw]


# ---------------------------------------------------------------------------
# Grading recorded runs (offline) — DVC `evaluate` stage
# ---------------------------------------------------------------------------


def evaluate_records(
    records: list[TaskRunRecord],
    *,
    tasks: list[EvalTask] | None = None,
) -> EvaluationReport[EvalTask, TaskRunRecord, None]:
    """Grade run records with pydantic-evals; no model involved."""
    by_id = {record.task_id: record for record in records}
    selected = tasks or list(TASK_SUITE)
    dataset = build_dataset(selected)

    async def lookup(task: EvalTask) -> TaskRunRecord:
        record = by_id.get(task.id)
        if record is None:
            raise KeyError(f"no run record for task {task.id}")
        return record

    report = dataset.evaluate_sync(lookup, name="agentic_workflows_suite")
    logger.info("suite averages: %s", suite_averages(report))
    return report


_GRADER_NAMES: tuple[str, ...] = ("AnswerSuccess", "ToolSelection", "StepBudget", "LatencyBudget")


def suite_averages(report: EvaluationReport[EvalTask, TaskRunRecord, None]) -> dict[str, float]:
    """Mean pass rate per grader across all cases (derived from case assertions)."""
    cases = list(report.cases)
    return {
        name: (sum(_score(report, case.name, name) for case in cases) / max(len(cases), 1))
        for name in _GRADER_NAMES
    }


# ---------------------------------------------------------------------------
# Report: metrics.json + figures + HTML
# ---------------------------------------------------------------------------


def _score(
    report: EvaluationReport[EvalTask, TaskRunRecord, None], case_name: str, evaluator: str
) -> float:
    case = next((c for c in report.cases if c.name == case_name), None)
    if case is None:
        return 0.0
    # Scalar evaluator outputs land in `assertions`; `scores` holds structured metrics.
    result = case.assertions.get(evaluator) or case.scores.get(evaluator)
    if result is None:
        return 0.0
    value = result.value
    return float(value) if isinstance(value, int | float) else 0.0


def suite_figures(
    report: EvaluationReport[EvalTask, TaskRunRecord, None],
) -> dict[str, go.Figure]:
    """The three story figures: success, tool selection, latency per task."""
    cases = list(report.cases)
    names = [case.name for case in cases]
    success = [_score(report, name, "AnswerSuccess") for name in names]
    tool_sel = [_score(report, name, "ToolSelection") for name in names]

    fig_success = go.Figure(
        data=[
            go.Bar(name="task success", x=names, y=success, marker={"color": "#2dd4bf"}),
            go.Bar(name="tool selection", x=names, y=tool_sel, marker={"color": "#38bdf8"}),
        ]
    )
    fig_success.update_layout(
        barmode="group",
        title="Per-task grading: answer success vs tool selection",
        xaxis_title="task",
        yaxis_title="score (1 = pass)",
        yaxis={"range": [0, 1.05]},
    )
    apply_theme(fig_success)
    add_takeaway(
        fig_success,
        f"Suite success rate {sum(success) / max(len(success), 1):.0%}; "
        f"tool-selection accuracy {sum(tool_sel) / max(len(tool_sel), 1):.0%}.",
    )

    durations = [case.output.duration_s for case in cases]
    budgets = [case.inputs.latency_budget_s for case in cases]
    fig_latency = go.Figure(
        data=[
            go.Bar(name="observed latency", x=names, y=durations, marker={"color": "#a78bfa"}),
            go.Scatter(
                name="latency budget",
                x=names,
                y=budgets,
                mode="lines",
                line={"dash": "dash", "color": "#f472b6"},
            ),
        ]
    )
    fig_latency.update_layout(
        title="Per-task workflow latency vs budget",
        xaxis_title="task",
        yaxis_title="seconds",
    )
    apply_theme(fig_latency)
    within = sum(1 for d, b in zip(durations, budgets, strict=True) if d <= b)
    add_takeaway(
        fig_latency,
        f"Median {statistics.median(durations):.1f}s per task on the local 32B model; "
        f"{within}/{len(durations)} runs inside the {budgets[0]:.0f}s budget.",
    )

    categories = sorted({case.inputs.category for case in cases})
    cat_success = []
    for category in categories:
        idx = [i for i, case in enumerate(cases) if case.inputs.category == category]
        cat_success.append(sum(success[i] for i in idx) / len(idx))
    fig_category = go.Figure(
        data=[go.Bar(name="success rate", x=categories, y=cat_success, marker={"color": "#34d399"})]
    )
    fig_category.update_layout(
        title="Answer success rate by task category",
        xaxis_title="category",
        yaxis_title="success rate",
        yaxis={"range": [0, 1.05]},
    )
    apply_theme(fig_category)
    add_takeaway(
        fig_category,
        "Lookup and conversion are single-tool tasks; calculations need the "
        "search→calculator pairing the plan step is built for.",
    )

    return {
        "per_task_grading": fig_success,
        "per_task_latency": fig_latency,
        "category_success": fig_category,
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

    figures = suite_figures(report)
    builder.build(config.reports_dir, figures=figures)
    for name, fig in figures.items():
        save_json(fig, config.reports_dir / "figures" / f"{name}.json")

    detail = {
        "grader": "deterministic keyword + tool-set graders (pydantic-evals Evaluator subclasses)",
        "n_tasks": len(cases),
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
    logger.info("report written: %s", config.reports_dir / "report.html")
    return metrics_path


def tasks_json(tasks: list[EvalTask]) -> str:
    return json.dumps([json.loads(t.model_dump_json()) for t in tasks], indent=2) + "\n"


def parse_tasks(payload: str) -> list[EvalTask]:
    return [EvalTask.model_validate(item) for item in json.loads(payload)]


TaskRunner = Callable[[EvalTask], TaskRunRecord]
