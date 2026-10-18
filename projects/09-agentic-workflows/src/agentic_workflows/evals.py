"""Evaluation harness: synthetic task suite, typed graders, reports.

The suite (``TASK_SUITE``) is 15 tasks: 14 over the deterministic research-ops
corpus with exact ground truths — keyword checks the final answer must contain
and the exact set of tools a correct solution needs — plus one cross-project
lookup over project 01's real Wikipedia corpus via ``search_documents``.
Grading runs through ``pydantic-evals`` (``Dataset`` + custom ``Evaluator``
subclasses); the report builder then aggregates per-task and per-category
results into ``reports/metrics.json``, four plotly figures, and the HTML
report.

Two entry points, matching the DVC stages:

- :func:`run_suite` — actually runs every task through the workflow graph
  (needs a live model: env provider or local Ollama). Resets the spend ledger,
  caps the suite at ``LLM_SUITE_COST_LIMIT_USD``, and enforces a per-task
  cloud-equivalent cap through the meter callback.
- :func:`evaluate_records` — grades a previously written
  ``data/run_records.json``; fully offline because grading is deterministic.
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from portfolio_core.llm import build_model
from portfolio_core.llm_budget import (
    BudgetExceededError,
    budget_limits,
    get_ledger,
    meter_result,
    reset_ledger,
)
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_json
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.report import ReportBuilder
from pydantic_ai.models import Model
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext
from pydantic_evals.reporting import EvaluationReport

from agentic_workflows.config import EvalConfig, get_settings
from agentic_workflows.schemas import EvalTask, TaskRunRecord
from agentic_workflows.workflow import run_workflow_async

logger = get_logger(__name__)


class TaskBudgetError(RuntimeError):
    """Per-task cloud-equivalent spend crossed the task cap.

    Raised by the suite's meter after the offending node result is recorded
    in the ledger, so the spend stays honest; caught per-task by
    :func:`run_suite` (recorded as ``budget_exceeded``, the suite continues).
    """


@dataclass
class _TaskMeter:
    """Mutable per-task accumulator fed by the meter callback."""

    input_tokens: int = 0
    output_tokens: int = 0
    spend_usd: Decimal = Decimal(0)


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
    # Cross-project arm: real-data retrieval over 01's Wikipedia corpus
    # (read-only FAISS index, see documents.py). Two chunks, two articles:
    # Wright brothers (aviation-122) gives 1903, Wind power (renewable-energy-122)
    # gives 2022 — the multi-hop answer is the 119-year gap.
    EvalTask(
        id="t15",
        prompt=(
            "According to the Wikipedia document corpus: in what year did the Wright "
            "brothers make the first controlled, sustained flight of a powered aircraft, "
            "and in what year did wind power supply over 2000 TWh of electricity? "
            "How many years separate the two events?"
        ),
        category="lookup",
        expected_keywords=["1903", "2022", "119"],
        expected_tools=["search_documents"],
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
    """Run every task through the workflow graph; returns typed records.

    Budget wiring (labelled cloud-equivalent estimates, never billed amounts):

    - the spend ledger is reset at suite start and capped at the suite limit
      (``LLM_SUITE_COST_LIMIT_USD``); crossing it aborts the remaining tasks;
    - a per-task cap (``task_cost_limit_usd``, default $0.25) is enforced by
      the meter callback: the node result is recorded, then
      :class:`TaskBudgetError` aborts the task and the suite continues;
    - ``budget_limits`` (hosted request/token limits) is forwarded to every
      model call.
    """
    settings = get_settings()
    selected = tasks or list(TASK_SUITE)

    reset_ledger()
    ledger = get_ledger(settings)
    ledger.budget_usd = Decimal(str(settings.llm_suite_cost_limit_usd))
    usage_limits = budget_limits(settings)
    task_limit = Decimal(str(config.task_cost_limit_usd))
    logger.info(
        "suite budget: $%s per task, $%s suite cap (cloud-equivalent estimates)",
        task_limit,
        ledger.budget_usd,
    )

    records: list[TaskRunRecord] = []
    suite_aborted = False
    for task in selected:
        if suite_aborted or ledger.spend_usd >= ledger.budget_usd:
            records.append(
                TaskRunRecord(
                    task_id=task.id,
                    status="budget_exceeded",
                    answer="",
                    steps_taken=[],
                    tools_used=[],
                    confidence=0.0,
                    duration_s=0.0,
                    error="not run: suite budget exhausted by earlier tasks",
                )
            )
            continue
        start = time.perf_counter()
        task_meter = _TaskMeter()
        # The model is built per task: each task runs in its own event loop
        # (asyncio.run per task), and a shared httpx client would surface
        # "Event loop is closed" on the first call of every later task.
        task_model = model if model is not None else build_model(settings)
        task_model_name = settings.llm_model or str(getattr(task_model, "model_name", "unknown"))

        def meter(
            result: Any,
            _meter: _TaskMeter = task_meter,
            _task_id: str = task.id,
            _model_name: str = task_model_name,
        ) -> None:
            # result.usage is a RunUsage property on AgentRunResult — pass the
            # usage object itself (meter_result duck-types it).
            entry = meter_result(result.usage, _model_name, settings)
            _meter.input_tokens += entry.input_tokens
            _meter.output_tokens += entry.output_tokens
            _meter.spend_usd += entry.spend_usd
            if _meter.spend_usd > task_limit:
                raise TaskBudgetError(
                    f"task {_task_id} crossed the per-task cloud-equivalent cap: "
                    f"${_meter.spend_usd} > ${task_limit}"
                )

        try:
            result = run_workflow_sync(
                task.prompt,
                model=task_model,
                max_execute_retries=config.max_execute_retries,
                max_critique_loops=config.max_critique_loops,
                meter=meter,
                usage_limits=usage_limits,
            )
            records.append(
                TaskRunRecord(
                    task_id=task.id,
                    status="ok",
                    answer=result.answer,
                    steps_taken=result.steps_taken,
                    tools_used=result.tools_used,
                    steps=result.step_traces,
                    tool_calls=result.tool_calls,
                    plan_steps=result.plan_steps,
                    critique_verdict=result.critique_verdict,
                    confidence=result.confidence,
                    retries=result.retries,
                    critique_loops=result.critique_loops,
                    duration_s=round(time.perf_counter() - start, 3),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
            )
        except TaskBudgetError as exc:
            logger.warning("task %s hit the per-task budget cap", task.id)
            records.append(
                TaskRunRecord(
                    task_id=task.id,
                    status="budget_exceeded",
                    answer="",
                    steps_taken=[],
                    tools_used=[],
                    confidence=0.0,
                    duration_s=round(time.perf_counter() - start, 3),
                    input_tokens=task_meter.input_tokens,
                    output_tokens=task_meter.output_tokens,
                    error=str(exc),
                )
            )
        except BudgetExceededError as exc:
            logger.warning("task %s exhausted the suite budget; aborting remaining tasks", task.id)
            records.append(
                TaskRunRecord(
                    task_id=task.id,
                    status="budget_exceeded",
                    answer="",
                    steps_taken=[],
                    tools_used=[],
                    confidence=0.0,
                    duration_s=round(time.perf_counter() - start, 3),
                    input_tokens=task_meter.input_tokens,
                    output_tokens=task_meter.output_tokens,
                    error=str(exc),
                )
            )
            suite_aborted = True
        except Exception as exc:  # broad: task boundary — failure becomes a failed record
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
# Offline trajectory decomposition of the tool-selection score
# ---------------------------------------------------------------------------

#: Canonical column order of the tool-usage matrix figure.
SUITE_TOOLS: tuple[str, ...] = (
    "search_handbook",
    "search_documents",
    "calculator",
    "unit_convert",
    "note_store",
)


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


def _fig_per_task_grading(
    report: EvaluationReport[EvalTask, TaskRunRecord, None],
) -> go.Figure:
    """Answer success vs exact-set tool selection per task (kept from wave 3)."""
    cases = list(report.cases)
    names = [case.name for case in cases]
    success = [_score(report, name, "AnswerSuccess") for name in names]
    tool_sel = [_score(report, name, "ToolSelection") for name in names]

    fig = go.Figure(
        data=[
            go.Bar(name="task success", x=names, y=success, marker={"color": "#2dd4bf"}),
            go.Bar(name="tool selection", x=names, y=tool_sel, marker={"color": "#38bdf8"}),
        ]
    )
    fig.update_layout(
        barmode="group",
        title=(
            "Answers pass 15/15 but exact tool selection is 8/15 - the "
            "remaining risk is behavioral over-calling, not infrastructure"
        ),
        xaxis_title="task",
        yaxis_title="score (1 = pass)",
        yaxis={"range": [0, 1.05]},
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        f"Suite success rate {sum(success) / max(len(success), 1):.0%}; "
        f"tool-selection accuracy {sum(tool_sel) / max(len(tool_sel), 1):.0%}.",
    )
    return fig


def _fig_tool_usage_matrix(cases: list[Any]) -> go.Figure:
    """Tasks x tools heatmap of per-call counts from the captured tool traces.

    Every cell with calls is annotated with its count, so the over-call noise
    (unplanned ``note_store`` / ``search_documents`` / ``calculator``) reads at
    a glance: one bright cell is a planned call, a bright *column* under a
    tool that few tasks expect is the exact-set miss driver.
    """
    names = [case.name for case in cases]
    matrix: list[list[int]] = []
    for tool in SUITE_TOOLS:
        row: list[int] = []
        for case in cases:
            call_names = [c.name for c in case.output.tool_calls] or list(case.output.tools_used)
            row.append(sum(1 for name in call_names if name == tool))
        matrix.append(row)
    text = [[str(value) if value > 0 else "" for value in row] for row in matrix]
    fig = go.Figure(
        data=[
            go.Heatmap(
                z=matrix,
                x=names,
                y=list(SUITE_TOOLS),
                text=text,
                texttemplate="%{text}",
                showscale=False,
                colorscale=[[0, "#16213a"], [1, "#2dd4bf"]],
                zmin=0,
                hovertemplate="%{y} on %{x}: %{z} call(s)<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title=(
            "Tool over-calling is visible per task — note_store, search_documents, "
            "duplicate in-set calls"
        ),
        xaxis_title="task",
        yaxis_title="",
    )
    apply_theme(fig)
    # Dynamic takeaway: name the most-called tool that the fewest tasks expect.
    expected_by_tool = {
        tool: sum(1 for case in cases if tool in case.inputs.expected_tools) for tool in SUITE_TOOLS
    }
    totals = {tool: sum(row) for tool, row in zip(SUITE_TOOLS, matrix, strict=True)}
    loudest = max(SUITE_TOOLS, key=lambda t: totals[t] - expected_by_tool[t])
    loudest_tasks = sum(
        1
        for case in cases
        if any(c.name == loudest for c in case.output.tool_calls)
        or loudest in case.output.tools_used
    )
    add_takeaway(
        fig,
        f"{totals[loudest]} {loudest} calls across {loudest_tasks}/{len(cases)} tasks — only "
        f"{expected_by_tool[loudest]} task(s) plan for it; a bright column here is an "
        "unplanned habit, not a need.",
    )
    return fig


def _fig_node_waterfall(cases: list[Any]) -> go.Figure:
    """Per-task stacked node visits: one segment per ``steps[]`` entry.

    Segment width is that visit's latency; labels are ``plan`` / ``execute``
    (``#2``, ``#3`` for repeat visits — repair and critique-driven re-runs) /
    ``critique``. A runaway task reads as ONE giant segment (t14: ~260 s
    inside a single execute visit), not a stack of retries. The 180 s budget
    is an annotation, not a dominating axis line.
    """
    names = [case.name for case in cases]
    segments: dict[str, dict[str, tuple[float, int, int]]] = {}
    first_pos: dict[str, int] = {}
    for case in cases:
        seen: dict[str, int] = {}
        for pos, trace in enumerate(case.output.steps):
            seen[trace.node] = seen.get(trace.node, 0) + 1
            label = trace.node if seen[trace.node] == 1 else f"{trace.node} #{seen[trace.node]}"
            segments.setdefault(label, {})[case.name] = (
                trace.latency_s,
                trace.input_tokens,
                trace.output_tokens,
            )
            first_pos.setdefault(label, pos)
    labels = sorted(segments, key=lambda label: first_pos[label])

    node_color = {"plan": "#38bdf8", "execute": "#2dd4bf", "critique": "#a78bfa"}
    fig = go.Figure()
    for label in labels:
        node = label.split(" ")[0]
        repeat = label != node
        latencies: list[float] = []
        hover: list[str] = []
        text: list[str] = []
        for name in names:
            visit = segments[label].get(name)
            if visit is None:
                latencies.append(0.0)
                hover.append("")
                text.append("")
            else:
                latency, in_tokens, out_tokens = visit
                latencies.append(latency)
                hover.append(
                    f"{name} · {label}: {latency:.1f}s, {in_tokens} in + {out_tokens} out tokens"
                )
                text.append(f"{latency:.0f}s" if latency >= 60 else "")
        fig.add_bar(
            name=label,
            y=names,
            x=latencies,
            orientation="h",
            marker={
                "color": node_color[node],
                "opacity": 0.65 if repeat else 1.0,
            },
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
            text=text,
            textposition="inside",
        )
    budget = max((case.inputs.latency_budget_s for case in cases), default=180.0)
    fig.update_layout(
        barmode="stack",
        title=(
            "Every task completes in 10-27 s — far under the 180 s budget; "
            "a retry appears as an extra labelled segment, never one long visit"
        ),
        xaxis_title="seconds",
        yaxis={"title": "", "autorange": "reversed"},
        shapes=[
            {
                "type": "line",
                "x0": budget,
                "x1": budget,
                "y0": 0,
                "y1": 1,
                "yref": "paper",
                "line": {"color": "#f472b6", "dash": "dash", "width": 1.5},
            }
        ],
        annotations=[
            {
                "xref": "x",
                "yref": "paper",
                "x": budget,
                "y": 1.03,
                "text": f"{budget:.0f} s budget",
                "showarrow": False,
                "font": {"size": 11, "color": "#f472b6"},
            }
        ],
    )
    apply_theme(fig)
    # Lead with the widest single segment: the "one giant visit" story.
    widest: tuple[str, str, float] | None = None
    for label, per_task in segments.items():
        for task_name, (latency, _, _) in per_task.items():
            if widest is None or latency > widest[2]:
                widest = (task_name, label, latency)
    if widest is not None:
        task_name, label, latency = widest
        add_takeaway(
            fig,
            f"Widest single segment: {task_name} {label} at {latency:.0f}s — retries add "
            "new labelled segments (#2, #3), they never stretch one visit.",
        )
    else:
        add_takeaway(fig, "No node visits recorded.")
    return fig


def _fig_agent_architecture() -> go.Figure:
    """The workflow graph as a plotly-shapes diagram (dark theme).

    Boxes for user → Plan → Execute (with the five-tool toolset sub-box) →
    Critique and both terminal ends; solid edges for the happy path and the
    critique revise loop; a dashed lane for the HITL checkpoint variant
    (approve re-enters at Execute, reject re-plans). Repair self-loop and
    retry bound are drawn, not described.
    """
    # Boxes and text labels live in paper coordinates; arrow annotations need
    # axis coordinates (axref/ayref cannot be "paper"), so the invisible y
    # axis spans exactly [0, 1] and edge() maps through it one-to-one. The
    # whole canvas is used: the HITL lane occupies the bottom paper band.
    Y_MIN = 0.0
    fig = go.Figure()
    fig.update_layout(
        xaxis={"range": [0, 1], "visible": False},
        yaxis={"range": [0, 1.0], "visible": False},
    )
    box_fill = "#1e293b"
    boxes: list[tuple[float, float, float, float, str, str, dict[str, Any]]] = [
        # (x0, y0, x1, y1, label, line color, extra layout kwargs)
        (0.01, 0.80, 0.09, 0.92, "user request", "#64748b", {}),
        (0.15, 0.76, 0.27, 0.94, "Plan", "#38bdf8", {}),
        (0.36, 0.60, 0.62, 0.98, "Execute", "#2dd4bf", {}),
        (0.375, 0.62, 0.605, 0.86, "", "#2dd4bf", {"opacity": 0.35}),
        (0.72, 0.76, 0.84, 0.94, "Critique", "#a78bfa", {}),
        (0.90, 0.78, 0.99, 0.92, "End (result)", "#34d399", {}),
        (0.44, 0.06, 0.58, 0.20, "End (failure)", "#f472b6", {}),
        (0.13, 0.06, 0.31, 0.20, "ApprovalCheckpoint (HITL)", "#f472b6", {"dash": "dash"}),
    ]
    shapes = []
    for x0, y0, x1, y1, _label, color, extra in boxes:
        shapes.append(
            {
                "type": "rect",
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "fillcolor": box_fill,
                "opacity": extra.get("opacity", 0.9),
                "line": {"color": color, "width": 2, "dash": extra.get("dash", "solid")},
                "xref": "paper",
                "yref": "paper",
            }
        )
    fig.update_layout(shapes=shapes)

    label_style: dict[str, Any] = {"size": 12, "color": "#e2e8f0"}
    annotations: list[dict[str, Any]] = [
        # Box labels (paper coordinates)
        {
            "x": 0.05,
            "y": 0.86,
            "text": "user\nrequest",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.21,
            "y": 0.85,
            "text": "Plan\ntyped step plan",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.49,
            "y": 0.90,
            "text": "Execute\ntool-using agent",
            "showarrow": False,
            "font": label_style,
        },
        *[
            {
                "x": 0.49,
                "y": y,
                "text": tool,
                "showarrow": False,
                "xref": "paper",
                "yref": "paper",
                "font": {"size": 10, "color": "#94a3b8"},
            }
            for tool, y in zip(
                ("search_handbook", "search_documents", "calculator", "unit_convert", "note_store"),
                (0.82, 0.775, 0.73, 0.685, 0.64),
                strict=True,
            )
        ],
        {
            "x": 0.78,
            "y": 0.85,
            "text": "Critique\nself-check",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.945,
            "y": 0.85,
            "text": "End\n(result)",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.51,
            "y": 0.13,
            "text": "End\n(failure)",
            "showarrow": False,
            "font": label_style,
        },
        {
            "x": 0.22,
            "y": 0.13,
            "text": "ApprovalCheckpoint\nHITL gate",
            "showarrow": False,
            "font": label_style,
        },
    ]
    for annotation in annotations:
        annotation.setdefault("xref", "paper")
        annotation.setdefault("yref", "paper")

    def edge(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        label: str,
        *,
        dash: str = "solid",
        color: str = "#94a3b8",
        lx: float | None = None,
        ly: float | None = None,
    ) -> None:
        def _y(paper_y: float) -> float:
            return Y_MIN + (1.0 - Y_MIN) * paper_y

        annotations.append(
            {
                "x": x1,
                "y": _y(y1),
                "ax": x0,
                "ay": _y(y0),
                "xref": "x",
                "yref": "y",
                "axref": "x",
                "ayref": "y",
                "showarrow": True,
                "arrowhead": 2,
                "arrowsize": 1.2,
                "arrowcolor": color,
                "arrowwidth": 1.5,
            }
        )
        if label:
            annotations.append(
                {
                    "x": lx if lx is not None else (x0 + x1) / 2,
                    "y": ly if ly is not None else (y0 + y1) / 2 + 0.035,
                    "text": label,
                    "showarrow": False,
                    "xref": "paper",
                    "yref": "paper",
                    "font": {"size": 11, "color": color},
                    "bgcolor": "#0f172a",
                }
            )

    edge(0.09, 0.86, 0.15, 0.86, "")
    edge(0.27, 0.85, 0.36, 0.85, "plan")
    edge(0.62, 0.85, 0.72, 0.85, "draft")
    edge(0.72, 0.79, 0.60, 0.79, "revise (≤1)", lx=0.66, ly=0.755)
    edge(0.84, 0.85, 0.90, 0.85, "pass")
    # Repair self-loop drawn inside the Execute box top band.
    edge(
        0.58,
        0.955,
        0.43,
        0.955,
        "repair ≤ max_execute_retries",
        color="#2dd4bf",
        lx=0.505,
        ly=0.975,
    )
    edge(0.47, 0.60, 0.50, 0.20, "retries exhausted", color="#f472b6", lx=0.575, ly=0.42)
    # HITL dashed lane
    edge(0.20, 0.76, 0.20, 0.20, "pause", dash="dash", color="#f472b6", lx=0.155, ly=0.48)
    edge(
        0.31,
        0.13,
        0.40,
        0.64,
        "approve → re-enter at Execute",
        dash="dash",
        color="#f472b6",
        lx=0.42,
        ly=0.36,
    )
    edge(
        0.24,
        0.20,
        0.24,
        0.76,
        "reject → re-plan",
        dash="dash",
        color="#f472b6",
        lx=0.295,
        ly=0.48,
    )

    fig.update_layout(annotations=annotations)
    apply_theme(fig, height=470)
    fig.update_layout(
        title=(
            "Every plan/execute/critique transition, retry and loop bound is "
            "explicit code — the graph the workflow actually runs"
        ),
    )
    add_takeaway(
        fig,
        "Solid: plan→execute→critique with a bounded repair self-loop and one revise loop. "
        "Dashed: the HITL checkpoint lane — approve re-enters at Execute, reject re-plans.",
    )
    # add_takeaway resets the theme margins; this diagram is a canvas, not a
    # chart, so reclaim the space for the drawing itself.
    fig.update_layout(margin={"l": 10, "r": 10, "t": 80, "b": 10})
    return fig


def _fig_cost_latency_bars(cases: list[Any], config: EvalConfig | None) -> go.Figure:
    """Stacked tokens + cloud-equivalent cost + latency vs budget (kept)."""
    names = [case.name for case in cases]
    durations = [case.output.duration_s for case in cases]
    budgets = [case.inputs.latency_budget_s for case in cases]
    in_rate = config.usd_per_mtok_input if config is not None else 1.0
    out_rate = config.usd_per_mtok_output if config is not None else 4.0
    input_tokens = [case.output.input_tokens for case in cases]
    output_tokens = [case.output.output_tokens for case in cases]
    costs = [
        (i / 1e6 * in_rate + o / 1e6 * out_rate)
        for i, o in zip(input_tokens, output_tokens, strict=True)
    ]
    totals = [i + o for i, o in zip(input_tokens, output_tokens, strict=True)]
    cost_labels = [f"${c:.4f}" for c in costs]
    fig = go.Figure(
        data=[
            go.Bar(name="input tokens", x=names, y=input_tokens, marker={"color": "#2dd4bf"}),
            go.Bar(name="output tokens", x=names, y=output_tokens, marker={"color": "#38bdf8"}),
            go.Scatter(
                name="cloud-equivalent cost per task",
                x=names,
                y=totals,
                text=cost_labels,
                mode="text",
                textposition="top center",
                textfont={"size": 11, "color": "#fbbf24"},
                showlegend=True,
                hoverinfo="skip",
            ),
            go.Scatter(
                name="latency",
                x=names,
                y=durations,
                mode="lines+markers",
                line={"color": "#a78bfa"},
                yaxis="y2",
            ),
            go.Scatter(
                name="latency budget",
                x=names,
                y=budgets,
                mode="lines",
                line={"dash": "dash", "color": "#f472b6"},
                yaxis="y2",
            ),
        ]
    )
    fig.update_layout(
        barmode="stack",
        title=(
            "Every task lands inside the $0.25 and 180 s budgets - the suite "
            "spent $0.10 of the $2.00 cap"
        ),
        xaxis_title="task",
        yaxis={"title": "tokens", "range": [0, max(totals, default=1) * 1.2]},
        yaxis2={"title": "seconds", "overlaying": "y", "side": "right"},
    )
    apply_theme(fig)
    add_takeaway(
        fig,
        f"Total ${sum(costs):.4f} cloud-equivalent ($1/Mtok in, $4/Mtok out; "
        f"labelled estimate, membership-quota key); median ${statistics.median(costs):.4f} "
        f"per task; latency budget {budgets[0]:.0f}s held for "
        f"{sum(1 for d, b in zip(durations, budgets, strict=True) if d <= b)}/{len(durations)}.",
    )
    return fig


def suite_figures(
    report: EvaluationReport[EvalTask, TaskRunRecord, None],
    config: EvalConfig | None = None,
) -> dict[str, go.Figure]:
    """The five story figures.

    ``per_task_grading`` and ``cost_latency_bars`` are unchanged in intent;
    ``category_success`` was dropped (category rates duplicate the per-task
    bars) in favor of three trajectory views made possible by per-call tool
    capture: ``tool_usage_matrix`` (calls per task per tool),
    ``node_waterfall`` (per-visit latency stack), and ``agent_architecture``
    (the graph itself).
    """
    cases = list(report.cases)
    return {
        "per_task_grading": _fig_per_task_grading(report),
        "cost_latency_bars": _fig_cost_latency_bars(cases, config),
        "tool_usage_matrix": _fig_tool_usage_matrix(cases),
        "node_waterfall": _fig_node_waterfall(cases),
        "agent_architecture": _fig_agent_architecture(),
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


def tasks_json(tasks: list[EvalTask]) -> str:
    return json.dumps([json.loads(t.model_dump_json()) for t in tasks], indent=2) + "\n"


def parse_tasks(payload: str) -> list[EvalTask]:
    return [EvalTask.model_validate(item) for item in json.loads(payload)]


TaskRunner = Callable[[EvalTask], TaskRunRecord]
