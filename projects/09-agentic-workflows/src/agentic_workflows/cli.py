"""Command-line interface: one command per DVC stage plus interactive runs.

Typical session (from the project directory)::

    uv run python -m agentic_workflows.cli prepare       # materialize tasks.json
    uv run python -m agentic_workflows.cli run-all       # live suite run (Ollama/env LLM)
    uv run python -m agentic_workflows.cli evaluate      # offline grading → reports/
    uv run python -m agentic_workflows.cli run t05       # one suite task
    uv run python -m agentic_workflows.cli checkpoint request "Convert 10 km to miles"
    uv run python -m agentic_workflows.cli checkpoint approve
    uv run python -m agentic_workflows.cli checkpoint reject --feedback "Use fewer steps"
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from portfolio_core.llm_budget import get_ledger
from portfolio_core.logging import get_logger

from agentic_workflows import evals
from agentic_workflows.config import get_settings, load_config
from agentic_workflows.hitl import (
    describe_checkpoint,
    load_checkpoint,
    request_approval,
    resume,
    save_checkpoint,
)
from agentic_workflows.schemas import ApprovalDecision, WorkflowResult
from agentic_workflows.workflow import run_workflow

app = typer.Typer(help=__doc__, add_completion=False)
checkpoint_app = typer.Typer(help="Human-in-the-loop checkpoint: request/approve/reject.")
app.add_typer(checkpoint_app, name="checkpoint")
logger = get_logger(__name__)


def _echo_result(result: WorkflowResult) -> None:
    typer.echo(f"answer (confidence {result.confidence:.2f}): {result.answer}")
    typer.echo(f"steps: {' → '.join(result.steps_taken)}")
    typer.echo(f"tools used: {result.tools_used or 'none'}")
    typer.echo(
        f"tokens: {result.input_tokens} in / {result.output_tokens} out "
        f"(retries={result.retries}, critique_loops={result.critique_loops})"
    )


@app.command()
def prepare(config: str = "params.yaml") -> None:
    """Prepare stage: materialize the synthetic task suite into data/tasks.json."""
    cfg = load_config(Path(config))
    tasks = list(evals.TASK_SUITE)
    cfg.tasks_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.tasks_path.write_text(evals.tasks_json(tasks), encoding="utf-8")
    typer.echo(f"tasks ready: {len(tasks)} tasks at {cfg.tasks_path}")


@app.command()
def run(
    task_id: Annotated[str, typer.Argument(help="Suite task id (e.g. t05) or free-text prompt.")],
    config: str = "params.yaml",
) -> None:
    """Run one task through the workflow graph and print the structured result."""
    cfg = load_config(Path(config))
    prompt = task_id
    if Path(cfg.tasks_path).exists():
        for task in evals.parse_tasks(cfg.tasks_path.read_text(encoding="utf-8")):
            if task.id == task_id:
                prompt = task.prompt
                break
    result = run_workflow(
        prompt,
        max_execute_retries=cfg.max_execute_retries,
        max_critique_loops=cfg.max_critique_loops,
    )
    _echo_result(result)


@app.command(name="run-all")
def run_all(
    config: str = "params.yaml",
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Run only the first N suite tasks (wall-clock bound)."),
    ] = None,
    ids: Annotated[
        str | None,
        typer.Option("--ids", help="Comma-separated task ids to run (wall-clock bound)."),
    ] = None,
) -> None:
    """Run stage: execute suite tasks (live model) → data/run_records.json."""
    cfg = load_config(Path(config))
    tasks = (
        evals.parse_tasks(cfg.tasks_path.read_text(encoding="utf-8"))
        if cfg.tasks_path.exists()
        else list(evals.TASK_SUITE)
    )
    if ids is not None:
        wanted = [item.strip() for item in ids.split(",") if item.strip()]
        tasks = [task for task in tasks if task.id in wanted]
    elif limit is not None:
        tasks = tasks[:limit]
    records = evals.run_suite(cfg, tasks=tasks)
    evals.write_records(records, cfg.records_path)
    ok = sum(1 for record in records if record.status == "ok")
    over = sum(1 for record in records if record.status == "budget_exceeded")
    typer.echo(f"run-all complete: {ok}/{len(records)} tasks ok → {cfg.records_path}")
    if over:
        typer.echo(f"budget: {over} task(s) stopped at a budget cap (see records)")
    ledger = get_ledger(get_settings())
    total_in = sum(record.input_tokens for record in records)
    total_out = sum(record.output_tokens for record in records)
    typer.echo(
        f"ledger: {len(ledger.records)} metered calls, {total_in:,} in + {total_out:,} out tokens; "
        f"estimated spend ${ledger.spend_usd} of ${ledger.budget_usd} suite cap "
        f"(cloud-equivalent, labelled estimate)"
    )


@app.command()
def evaluate(config: str = "params.yaml") -> None:
    """Evaluate stage: grade run records (offline) → reports/metrics.json + figures."""
    cfg = load_config(Path(config))
    if not cfg.records_path.exists():
        raise typer.BadParameter(
            f"no run records at {cfg.records_path}; run `run-all` first (needs a live LLM)"
        )
    tasks = (
        evals.parse_tasks(cfg.tasks_path.read_text(encoding="utf-8"))
        if cfg.tasks_path.exists()
        else None
    )
    records = evals.load_records(cfg.records_path)
    report = evals.evaluate_records(records, tasks=tasks)
    evals.build_report(report, cfg)
    typer.echo(f"evaluation written: {cfg.reports_dir / 'report.html'}")


@checkpoint_app.command("request")
def checkpoint_request(
    task: Annotated[str, typer.Argument(help="Task to plan and pause on.")],
    config: str = "params.yaml",
) -> None:
    """Plan the task, then pause: serialize the checkpoint to data/checkpoint.json."""
    cfg = load_config(Path(config))
    checkpoint = request_approval(task)
    save_checkpoint(checkpoint, cfg.checkpoint_path)
    typer.echo(describe_checkpoint(checkpoint))
    typer.echo(f"\ncheckpoint saved: {cfg.checkpoint_path}")
    typer.echo("Review it, then `checkpoint approve` or `checkpoint reject --feedback ...`.")


@checkpoint_app.command("approve")
def checkpoint_approve(config: str = "params.yaml") -> None:
    """Approve the pending checkpoint and continue the workflow at Execute."""
    cfg = load_config(Path(config))
    checkpoint = load_checkpoint(cfg.checkpoint_path)
    result = resume(checkpoint, ApprovalDecision(approved=True))
    _echo_result(result)


@checkpoint_app.command("reject")
def checkpoint_reject(
    feedback: Annotated[str, typer.Option("--feedback", help="Why the plan was rejected.")] = "",
    config: str = "params.yaml",
) -> None:
    """Reject the pending checkpoint; feedback drives a re-plan, then execution."""
    cfg = load_config(Path(config))
    checkpoint = load_checkpoint(cfg.checkpoint_path)
    result = resume(checkpoint, ApprovalDecision(approved=False, feedback=feedback))
    _echo_result(result)


if __name__ == "__main__":
    app()
