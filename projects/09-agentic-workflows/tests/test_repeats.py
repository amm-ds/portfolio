"""Live-repeat artifacts (pass-4 E7) must reconcile: records ↔ grading ↔ summary ↔ figure.

The five ``reports/live_repeats_20261126/run<i>/`` folders hold the raw live
records, the offline grading of those records, and the run log; the summary
and the ``live_repeats`` figure are derived artifacts. These tests recompute
the derived artifacts from the raw ones so no published pass^5/latency/spend
number can drift from the evidence.
"""

import json
from pathlib import Path

from agentic_workflows import evals
from agentic_workflows.repeats import (
    GRADING_NAME,
    RECORDS_NAME,
    build_repeats_summary,
)

PROJECT = Path(__file__).parents[1]
REPEATS_DIR = PROJECT / "reports" / "live_repeats_20261126"
FIGURE = PROJECT / "reports" / "figures" / "live_repeats.json"


def _tasks() -> list:
    tasks_path = PROJECT / "data" / "tasks_heldout.json"
    if tasks_path.exists():
        return evals.parse_tasks(tasks_path.read_text(encoding="utf-8"))
    return list(evals.HELDOUT_SUITE)


def _run_dirs() -> list[Path]:
    return sorted(
        (d for d in REPEATS_DIR.iterdir() if d.is_dir() and d.name.startswith("run")),
        key=lambda d: int(d.name.removeprefix("run")),
    )


def _summary() -> dict:
    return json.loads((REPEATS_DIR / "repeats_summary.json").read_text(encoding="utf-8"))


def test_five_run_dirs_with_complete_artifacts() -> None:
    run_dirs = _run_dirs()
    assert len(run_dirs) == 5
    for run_dir in run_dirs:
        for name in (RECORDS_NAME, GRADING_NAME, "run.log"):
            assert (run_dir / name).exists(), f"{run_dir.name} missing {name}"
        records = json.loads((run_dir / RECORDS_NAME).read_text(encoding="utf-8"))
        assert len(records) == 19, f"{run_dir.name} holds {len(records)} records, not 19"


def test_summary_reconciles_with_per_run_artifacts() -> None:
    """Rebuilding the summary from the committed run dirs returns it exactly."""
    committed = _summary()
    rebuilt = build_repeats_summary(REPEATS_DIR, _tasks())
    assert rebuilt == committed


def test_grading_files_reconcile_with_records() -> None:
    """Each run's grading block must agree with its raw records.

    The per-task durations and statuses come straight from the records; the
    aggregate rates must equal the mean of the per-task grader scores over the
    cases each grader applies to (answers vs probes).
    """
    tasks = {task.id: task for task in _tasks()}
    for run_dir in _run_dirs():
        records = {
            r["task_id"]: r
            for r in json.loads((run_dir / RECORDS_NAME).read_text(encoding="utf-8"))
        }
        heldout = json.loads((run_dir / GRADING_NAME).read_text(encoding="utf-8"))["detail"][
            "heldout"
        ]
        per_task = heldout["per_task"]
        assert set(per_task) == set(records) == set(tasks)
        for task_id, graded in per_task.items():
            assert graded["duration_s"] == records[task_id]["duration_s"]
            assert graded["status"] == records[task_id]["status"]
        answer_ids = [t.id for t in tasks.values() if t.expected_behavior == "answer"]
        refuse_ids = [t.id for t in tasks.values() if t.expected_behavior == "refuse"]
        assert heldout["n_answer"] == len(answer_ids)
        assert heldout["n_should_fail"] == len(refuse_ids)
        assert heldout["answer_success"] == round(
            sum(per_task[t]["success"] for t in answer_ids) / len(answer_ids), 3
        )
        assert heldout["tool_selection"] == round(
            sum(per_task[t]["tool_selection"] for t in answer_ids) / len(answer_ids), 3
        )
        assert heldout["should_fail_pass_rate"] == round(
            sum(per_task[t]["refusal_success"] for t in refuse_ids) / len(refuse_ids), 3
        )


def test_pass5_and_pass_at_5_math() -> None:
    summary = _summary()
    per_task = summary["per_task"]
    n_runs = summary["n_runs"]
    assert n_runs == 5
    for entry in per_task.values():
        assert len(entry["passes"]) == n_runs
        assert len(entry["durations_s"]) == n_runs
        assert entry["pass_count"] == sum(entry["passes"])
        assert entry["pass_all_runs"] is (entry["pass_count"] == n_runs)
        assert entry["pass_any_run"] is (entry["pass_count"] > 0)
    pass5 = [t for t, e in per_task.items() if e["pass_all_runs"]]
    pass_any = [t for t, e in per_task.items() if e["pass_any_run"]]
    assert summary["pass5"]["k"] == len(pass5)
    assert summary["pass5"]["n"] == len(per_task) == 19
    assert sorted(summary["pass5"]["failing_tasks"]) == sorted(set(per_task) - set(pass5))
    assert summary["pass_at_5"]["k"] == len(pass_any)


def test_latency_percentiles_match_pooled_durations() -> None:
    summary = _summary()
    pooled = sorted(
        duration for entry in summary["per_task"].values() for duration in entry["durations_s"]
    )
    assert len(pooled) == summary["latency"]["n_observations"] == 19 * summary["n_runs"]

    def pct(q: float) -> float:
        return round(pooled[min(len(pooled) - 1, round(q * (len(pooled) - 1)))], 3)

    assert summary["latency"]["p50_s"] == pct(0.50)
    assert summary["latency"]["p95_s"] == pct(0.95)
    assert summary["latency"]["max_s"] == round(max(pooled), 3)


def test_spend_reconciles_with_run_ledgers() -> None:
    summary = _summary()
    per_run = summary["spend"]["per_run_usd"]
    assert len(per_run) == summary["n_runs"]
    assert all(float(s) > 0 for s in per_run)
    assert float(summary["spend"]["total_usd"]) == round(sum(float(s) for s in per_run), 6)
    for run, spend in zip(summary["runs"], per_run, strict=True):
        assert run["spend_usd"] == spend


def test_live_repeats_figure_matches_summary() -> None:
    summary = _summary()
    payload = json.loads(FIGURE.read_text(encoding="utf-8"))
    bar = payload["data"][0]
    assert bar["type"] == "bar"
    per_task = summary["per_task"]
    names = sorted(per_task)
    assert list(bar["x"]) == names
    assert [int(v) for v in bar["y"]] == [per_task[name]["pass_count"] for name in names]
    title = payload["layout"]["title"]["text"]
    assert f"{summary['pass5']['k']} of {summary['n_tasks']} tasks pass all five live runs" in title
