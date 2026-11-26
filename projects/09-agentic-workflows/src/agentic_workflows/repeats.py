"""Live repeat consistency (pass-4 E7): pass^5 / pass@5 across N live runs.

The committed ``reports/live_confirmation_20261119/`` run proved one all-hosted
pass of the 19-task held-out suite; this module aggregates the repeated runs
under ``reports/live_repeats_<date>/run<i>/`` (each produced by
``run_repeats.sh``: ``cli run-all --heldout`` + offline ``cli evaluate
--heldout``) into one ``repeats_summary.json`` plus the ``live_repeats``
story figure:

- per-task pass^5 (passes every run) and pass@5 (passes at least one run),
  where "pass" means every grader the task carries — answers: AnswerSuccess,
  ToolSelection, StepBudget, LatencyBudget; probes: RefusalSuccess,
  StepBudget, LatencyBudget;
- p50/p95 task latency pooled across runs (rounded-index percentile, the same
  convention as ``report.py``'s p95);
- per-run and total cloud-equivalent spend parsed from each run's ledger
  line (labelled estimates, never billed — the hosted key is membership
  quota).

Everything here is deterministic over the committed per-run artifacts: no
model calls, no timestamps, so the reconciliation test can rebuild the
summary byte-for-byte.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json

from agentic_workflows.config import EvalConfig
from agentic_workflows.schemas import EvalTask, TaskRunRecord

logger = get_logger(__name__)

SUMMARY_NAME = "repeats_summary.json"
RECORDS_NAME = "heldout_live_records.json"
GRADING_NAME = "live_grading_metrics.json"
RUN_LOG_NAME = "run.log"

#: Ledger line printed by ``cli run-all`` (see cli.run_all).
_LEDGER_RE = re.compile(
    r"ledger: (?P<calls>\d+) metered calls, (?P<in>[\d,]+) in \+ (?P<out>[\d,]+) out tokens; "
    r"estimated spend \$(?P<spend>[0-9.]+) of"
)


def _rounded_index_percentile(values: list[float], q: float) -> float:
    """Rounded-index percentile — the convention behind the article's p95."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def _load_run_dir(run_dir: Path) -> tuple[list[TaskRunRecord], dict[str, Any], str]:
    """One run's records + heldout grading block + ledger spend (from run.log)."""
    records = [
        TaskRunRecord.model_validate(item)
        for item in json.loads((run_dir / RECORDS_NAME).read_text(encoding="utf-8"))
    ]
    grading = json.loads((run_dir / GRADING_NAME).read_text(encoding="utf-8"))
    heldout = grading["detail"]["heldout"]
    matches = list(_LEDGER_RE.finditer((run_dir / RUN_LOG_NAME).read_text(encoding="utf-8")))
    if not matches:
        raise ValueError(f"no ledger line in {run_dir / RUN_LOG_NAME}")
    return records, heldout, matches[-1]["spend"]


def _task_verdicts(
    records: list[TaskRunRecord], heldout: dict[str, Any], tasks: list[EvalTask]
) -> dict[str, dict[str, Any]]:
    """Per-task pass verdict for ONE run: every applicable grader passed.

    Answer/tool/refusal scores come from the offline grading block; the step
    and latency budgets are re-derived from the raw record with the same rules
    as the ``StepBudget``/``LatencyBudget`` graders (the held-out per-task
    block does not carry them).
    """
    by_id = {record.task_id: record for record in records}
    per_task = heldout["per_task"]
    verdicts: dict[str, dict[str, Any]] = {}
    for task in tasks:
        record = by_id[task.id]
        graded = per_task[task.id]
        checks: dict[str, bool] = {
            "step_budget": len(record.steps_taken) <= task.max_steps,
            "latency_budget": record.duration_s <= task.latency_budget_s,
        }
        if task.expected_behavior == "refuse":
            checks["refusal_success"] = graded["refusal_success"] == 1.0
        else:
            checks["answer_success"] = graded["success"] == 1.0
            checks["tool_selection"] = graded["tool_selection"] == 1.0
        verdicts[task.id] = {
            "passed": all(checks.values()),
            "checks": checks,
            "duration_s": record.duration_s,
        }
    return verdicts


def build_repeats_summary(repeats_dir: Path, tasks: list[EvalTask]) -> dict[str, Any]:
    """Aggregate ``run<i>/`` artifacts under ``repeats_dir`` into the summary.

    Deterministic: run dirs sorted by index, tasks in suite order, no
    timestamps — rebuilding from the same artifacts returns the same dict.
    """
    run_dirs = sorted(
        (d for d in repeats_dir.iterdir() if d.is_dir() and d.name.startswith("run")),
        key=lambda d: int(d.name.removeprefix("run")),
    )
    if not run_dirs:
        raise ValueError(f"no run<i>/ directories under {repeats_dir}")

    runs: list[dict[str, Any]] = []
    per_task: dict[str, dict[str, Any]] = {
        task.id: {
            "category": task.category,
            "expected_behavior": task.expected_behavior,
            "passes": [],
            "durations_s": [],
        }
        for task in tasks
    }
    pooled_durations: list[float] = []
    spends: list[Decimal] = []
    for run_dir in run_dirs:
        records, heldout, spend = _load_run_dir(run_dir)
        verdicts = _task_verdicts(records, heldout, tasks)
        for task in tasks:
            entry = per_task[task.id]
            entry["passes"].append(verdicts[task.id]["passed"])
            entry["durations_s"].append(verdicts[task.id]["duration_s"])
            pooled_durations.append(verdicts[task.id]["duration_s"])
        spends.append(Decimal(spend))
        runs.append(
            {
                "run": run_dir.name,
                "records": f"{run_dir.name}/{RECORDS_NAME}",
                "grading": f"{run_dir.name}/{GRADING_NAME}",
                "answer_success": heldout["answer_success"],
                "tool_selection": heldout["tool_selection"],
                "step_budget": heldout["step_budget"],
                "latency_budget": heldout["latency_budget"],
                "should_fail_pass_rate": heldout["should_fail_pass_rate"],
                "tasks_passed": sum(1 for v in verdicts.values() if v["passed"]),
                "spend_usd": spend,
                "input_tokens": sum(r.input_tokens for r in records),
                "output_tokens": sum(r.output_tokens for r in records),
            }
        )

    n_runs = len(run_dirs)
    for entry in per_task.values():
        entry["pass_count"] = sum(entry["passes"])
        entry["pass_all_runs"] = entry["pass_count"] == n_runs
        entry["pass_any_run"] = entry["pass_count"] > 0

    pass5_tasks = sorted(task_id for task_id, e in per_task.items() if e["pass_all_runs"])
    pass_at_5_tasks = sorted(task_id for task_id, e in per_task.items() if e["pass_any_run"])
    n_tasks = len(per_task)
    summary: dict[str, Any] = {
        "suite": "heldout-19",
        "model": "kimi-for-coding",
        "provider": "hosted Kimi coding endpoint (OpenAI-compatible, membership quota)",
        "n_runs": n_runs,
        "n_tasks": n_tasks,
        "runs": runs,
        "per_task": per_task,
        "pass5": {
            "k": len(pass5_tasks),
            "n": n_tasks,
            "failing_tasks": sorted(set(per_task) - set(pass5_tasks)),
        },
        "pass_at_5": {"k": len(pass_at_5_tasks), "n": n_tasks},
        "latency": {
            "p50_s": round(_rounded_index_percentile(pooled_durations, 0.50), 3),
            "p95_s": round(_rounded_index_percentile(pooled_durations, 0.95), 3),
            "max_s": round(max(pooled_durations), 3),
            "n_observations": len(pooled_durations),
            "method": "rounded-index percentile over per-task durations pooled across runs",
        },
        "spend": {
            "per_run_usd": [str(s) for s in spends],
            "total_usd": str(sum(spends)),
            "note": (
                "cloud-equivalent estimates at the labelled rate card; "
                "membership-quota key, never billed"
            ),
        },
    }
    return summary


def write_repeats_report(repeats_dir: Path, config: EvalConfig) -> Path:
    """Write ``repeats_summary.json`` + the ``live_repeats`` figure (html+json).

    The figure lands in ``config.reports_dir / "figures"`` next to the other
    story figures; the summary stays inside the repeats folder with the
    per-run evidence it aggregates.
    """
    from agentic_workflows import evals  # local import: evals re-exports report

    tasks = (
        evals.parse_tasks(config.heldout_tasks_path.read_text(encoding="utf-8"))
        if config.heldout_tasks_path.exists()
        else list(evals.HELDOUT_SUITE)
    )
    summary = build_repeats_summary(repeats_dir, tasks)
    summary_path = repeats_dir / SUMMARY_NAME
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    from agentic_workflows.figures import live_repeats_figure

    fig = live_repeats_figure(summary)
    figures_dir = config.reports_dir / "figures"
    save_html(fig, figures_dir / "live_repeats.html")
    save_json(fig, figures_dir / "live_repeats.json")
    logger.info(
        "repeats summary written: %s (pass^5 %d/%d); figure: %s",
        summary_path,
        summary["pass5"]["k"],
        summary["pass5"]["n"],
        figures_dir / "live_repeats.json",
    )
    return summary_path
