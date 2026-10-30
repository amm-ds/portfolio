"""Evaluation harness: synthetic task suites, typed graders, live runs.

The tuning suite (``TASK_SUITE``) is 15 tasks: 14 over the deterministic
research-ops corpus with exact ground truths — keyword checks the final answer
must contain and the exact set of tools a correct solution needs — plus one
cross-project lookup over project 01's real Wikipedia corpus via
``search_documents``. The held-out set (``HELDOUT_SUITE``, audit finding 6) is
19 unseen tasks over the same corpora, 6 of them designed-to-fail probes that
grade graceful refusal: the original 10 (audit wave) plus a 2026-10-30
expansion wave (+6 answer tasks across both corpora and all five categories,
+3 refusal probes covering the currency-conversion, missing-corpus-fact and
calculator-AST-limit axes). Grading runs through ``pydantic-evals``
(``Dataset`` + custom ``Evaluator`` subclasses); reports, figures and metrics
aggregation live in :mod:`agentic_workflows.report` and
:mod:`agentic_workflows.figures` (audit P1 split — re-exported here for
import stability).

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
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from portfolio_core.llm import build_model
from portfolio_core.llm_budget import (
    BudgetExceededError,
    budget_limits,
    get_ledger,
    meter_result,
    reset_ledger,
)
from portfolio_core.logging import get_logger
from pydantic_ai.models import Model
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext
from pydantic_evals.reporting import EvaluationReport

from agentic_workflows.config import EvalConfig, get_settings
from agentic_workflows.report import decompose_tooling, suite_averages
from agentic_workflows.schemas import EvalTask, TaskRunRecord
from agentic_workflows.workflow import run_workflow_async

logger = get_logger(__name__)


# Re-exported for import stability (audit P1 split: evals → figures/report).
from agentic_workflows.figures import suite_figures  # noqa: E402
from agentic_workflows.report import (  # noqa: E402
    build_report,
    heldout_detail,
    write_heldout_metrics,
)


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


__all__ = [
    "HELDOUT_SUITE",
    "TASK_SUITE",
    "AnswerSuccess",
    "LatencyBudget",
    "RefusalSuccess",
    "StepBudget",
    "ToolSelection",
    "build_dataset",
    "build_report",
    "decompose_tooling",
    "evaluate_records",
    "heldout_detail",
    "load_records",
    "parse_tasks",
    "run_suite",
    "suite_averages",
    "suite_figures",
    "tasks_json",
    "write_heldout_metrics",
    "write_records",
]


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
        prompt=(
            "What is the total daily energy yield of the solar array's panels in "
            "kWh, before inverter losses?"
        ),
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
    # gives 2022 — the multi-hop answer is the 119-year gap, computed with the
    # calculator like every other arithmetic step in the suite (tool-discipline
    # tuning wave: expected_tools widened to include calculator — the gap
    # subtraction is arithmetic, and exact-set grading must not demand
    # mental math of the model).
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
        expected_tools=["search_documents", "calculator"],
    ),
)

# ---------------------------------------------------------------------------
# Held-out suite: 19 unseen tasks over the same corpora (audit finding 6 +
# 2026-10-30 expansion wave). 13 answer tasks across all five categories and
# both corpora + 6 designed-to-fail probes that ask for what the tools cannot
# do; those grade graceful refusal, not success. Ground truths verified
# against tool outputs (see tests/test_evals.py and tests/test_documents.py).
# ---------------------------------------------------------------------------

HELDOUT_SUITE: tuple[EvalTask, ...] = (
    EvalTask(
        id="h01",
        prompt="What is the survey drone's maximum payload and its flight time per charge?",
        category="lookup",
        expected_keywords=["2.5", "42"],
        expected_tools=["search_handbook"],
    ),
    EvalTask(
        id="h02",
        prompt=(
            "According to the Wikipedia document corpus: who introduced the name "
            "'dropout' for randomly removing connections in a neural network, "
            "and in what year?"
        ),
        category="lookup",
        expected_keywords=["Hinton", "2012"],
        expected_tools=["search_documents"],
    ),
    EvalTask(
        id="h03",
        prompt=("How many hours can the generator run on a full 240 L tank at full load?"),
        category="calculation",
        expected_keywords=["133"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="h04",
        prompt=(
            "If the station ran the generator 8 hours per day, how many liters "
            "of diesel would it burn in a 30-day month?"
        ),
        category="calculation",
        expected_keywords=["432"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="h05",
        prompt="The drone's rated range is 8 km. How many miles is that?",
        category="conversion",
        expected_keywords=["4.97"],
        expected_tools=["unit_convert"],
    ),
    EvalTask(
        id="h06",
        prompt=(
            "How many satellite uplink windows open per week, and what is the "
            "total weekly transfer capacity in MB?"
        ),
        category="multi_step",
        expected_keywords=["14", "3500"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="h07",
        prompt=(
            "Record the weather station's calibration interval in the ops "
            "notebook, then state how often calibration is required."
        ),
        category="note_keeping",
        expected_keywords=["45"],
        expected_tools=["search_handbook", "note_store"],
    ),
    EvalTask(
        id="h08",
        prompt=(
            "Convert the battery bank's 24 kWh of usable capacity into liters "
            "of water so it can be compared with the water tanks."
        ),
        category="out_of_scope",
        expected_behavior="refuse",
    ),
    EvalTask(
        id="h09",
        prompt=(
            "Use the station inventory tool to check the current diesel stock "
            "and report how many liters remain in the generator tank right now."
        ),
        category="out_of_scope",
        expected_behavior="refuse",
    ),
    EvalTask(
        id="h10",
        prompt="Convert 40 kg of ration packs to liters for the water log.",
        category="out_of_scope",
        expected_behavior="refuse",
    ),
    # --- 2026-10-30 expansion wave (roadmap: expand held-out tasks and
    # refusal probes across more corpora and models) -----------------------
    # Answer tasks: unused handbook/Wikipedia facts, same exact grading.
    EvalTask(
        id="h11",
        prompt=(
            "What is the station's base call sign, and which radio channel is "
            "reserved for emergencies?"
        ),
        category="lookup",
        expected_keywords=["Atlas Base", "channel 1"],
        expected_tools=["search_handbook"],
    ),
    # Wikipedia arm, previously unexercised topic (photosynthesis): the top
    # hit "Chlorophyll a" (photosynthesis-091#c000) states the absorbed
    # wavelengths inside the 600-char excerpt (pinned against the real index
    # in tests/test_documents.py).
    EvalTask(
        id="h12",
        prompt=(
            "According to the Wikipedia document corpus: which form of "
            "chlorophyll is the main photosynthetic pigment in plants, and "
            "which ranges of light does it absorb most strongly?"
        ),
        category="lookup",
        expected_keywords=["chlorophyll a", "violet-blue", "orange-red"],
        expected_tools=["search_documents"],
    ),
    EvalTask(
        id="h13",
        prompt=(
            "Assuming no HVAC surge overnight, how many kWh of usable battery "
            "capacity remain in the battery bank after the 8-hour base load?"
        ),
        category="calculation",
        expected_keywords=["11.2"],
        expected_tools=["search_handbook", "calculator"],
    ),
    # Unit pair neither suite has used yet (ft -> m); the prompt is
    # self-contained, so the exact tool set is unit_convert alone.
    EvalTask(
        id="h14",
        prompt="The new antenna mast is 400 ft tall. Convert that height to meters.",
        category="conversion",
        expected_keywords=["121.92"],
        expected_tools=["unit_convert"],
    ),
    EvalTask(
        id="h15",
        prompt=(
            "If the survey drone flies one full-endurance mission per day, "
            "how many minutes of flight time does it log in one week?"
        ),
        category="multi_step",
        expected_keywords=["294"],
        expected_tools=["search_handbook", "calculator"],
    ),
    EvalTask(
        id="h16",
        prompt=(
            "Record the sample freezer's maximum sample-box capacity in the "
            "ops notebook for the storage audit, then state the capacity."
        ),
        category="note_keeping",
        expected_keywords=["180"],
        expected_tools=["search_handbook", "note_store"],
    ),
    # Refusal probes, three axes the original three did not cover: an unknown
    # unit the conversion table has no row for (currency), a fact absent from
    # the deterministic corpus, and an arithmetic request outside the AST
    # evaluator's bounded operations.
    EvalTask(
        id="h17",
        prompt=(
            "The resupply invoice totals $1,850. Convert the amount to euros "
            "for the accounting file."
        ),
        category="out_of_scope",
        expected_behavior="refuse",
    ),
    EvalTask(
        id="h18",
        prompt="Look up the Wi-Fi password in the ops handbook for the new field tablet.",
        category="out_of_scope",
        expected_behavior="refuse",
    ),
    EvalTask(
        id="h19",
        prompt="Use the calculator to compute 2^500 exactly.",
        category="out_of_scope",
        expected_behavior="refuse",
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


#: Substrings that mark a graceful refusal (any one suffices, case-insensitive).
REFUSAL_MARKERS: tuple[str, ...] = (
    "cannot",
    "can't",
    "not available",
    "no tool",
    "unable",
    "impossible",
    "not supported",
    "unsupported",
    "does not exist",
    "don't have",
    "no way",
    "not possible",
)


@dataclass
class RefusalSuccess(Evaluator[EvalTask, TaskRunRecord, None]):
    """Designed-to-fail probe declined gracefully: no crash, refusal stated.

    Only attached to ``expected_behavior == "refuse"`` cases. Passes when the
    record completed without a workflow error (status ``ok``) and the answer
    states the limitation in plain words — any refusal marker counts, so
    phrasing cannot flip the grade. A fabricated number, or a crash, fails.
    """

    def evaluate(self, ctx: EvaluatorContext[EvalTask, TaskRunRecord, None]) -> bool:
        if ctx.output.status != "ok":
            return False
        answer = ctx.output.answer.lower()
        return any(marker in answer for marker in REFUSAL_MARKERS)


SUITE_EVALUATORS: tuple[Evaluator[EvalTask, TaskRunRecord, None], ...] = (
    AnswerSuccess(),
    ToolSelection(),
    StepBudget(),
    LatencyBudget(),
)

#: Graders attached to designed-to-fail probes instead of the answer/tool pair.
REFUSE_EVALUATORS: tuple[Evaluator[EvalTask, TaskRunRecord, None], ...] = (
    RefusalSuccess(),
    StepBudget(),
    LatencyBudget(),
)


def _case_evaluators(task: EvalTask) -> list[Evaluator[EvalTask, TaskRunRecord, None]]:
    """Per-task grader set: probes grade refusal, everything else the suite."""
    if task.expected_behavior == "refuse":
        return list(REFUSE_EVALUATORS)
    return list(SUITE_EVALUATORS)


def build_dataset(tasks: list[EvalTask] | None = None) -> Dataset[EvalTask, TaskRunRecord, None]:
    """The suite as a pydantic-evals dataset with the graders attached."""
    selected = tasks or list(TASK_SUITE)
    return Dataset(
        name="agentic_workflows_suite",
        cases=[
            Case(name=task.id, inputs=task, expected_output=None, evaluators=_case_evaluators(task))
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


# Task (de)serialization
# ---------------------------------------------------------------------------


def tasks_json(tasks: list[EvalTask]) -> str:
    return json.dumps([json.loads(t.model_dump_json()) for t in tasks], indent=2) + "\n"


def parse_tasks(payload: str) -> list[EvalTask]:
    return [EvalTask.model_validate(item) for item in json.loads(payload)]


TaskRunner = Callable[[EvalTask], TaskRunRecord]
