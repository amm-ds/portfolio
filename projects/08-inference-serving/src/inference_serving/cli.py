"""Typer entrypoints: one command per DVC stage plus interactive runs.

Typical session (from the project directory, Ollama running)::

    uv run python -m inference_serving.cli prepare   # materialize prompts.json
    uv run python -m inference_serving.cli bench      # bounded run (~<45 min)
    uv run python -m inference_serving.cli bench --full  # + extra arms (~hours)
    uv run python -m inference_serving.cli report     # offline figures + report.html
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from inference_serving import bench as bench_mod
from inference_serving import report as report_mod
from inference_serving.config import load_config
from inference_serving.schemas import BenchRun, CellResult

app = typer.Typer(help=__doc__, add_completion=False)


@app.command()
def prepare(config: str = "params.yaml") -> None:
    """Prepare stage: materialize the fixed prompt suite into data/prompts.json."""
    cfg = load_config(Path(config))
    cfg.prompts_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [p.model_dump() for p in bench_mod.PROMPTS]
    cfg.prompts_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    typer.echo(f"prompts ready: {len(payload)} fixed prompts at {cfg.prompts_path}")


@app.command()
def bench(
    config: str = "params.yaml",
    full: Annotated[
        bool, typer.Option("--full", help="Run all arms incl. extra quants/engines.")
    ] = False,
) -> None:
    """Bench stage: async load benchmark against Ollama → data/bench_run.json."""
    cfg = load_config(Path(config))
    cells = bench_mod.plan_cells(cfg, full) + bench_mod.plan_quality_cells(cfg, full)
    typer.echo(
        f"bench: {len(cells)} cells "
        f"({len(set(m.name for m, _ in cells))} models), "
        f"concurrency {cfg.concurrency(full)}, {cfg.repeats} repeats/cell — starting"
    )

    def _show(cell: CellResult) -> None:
        typer.echo(
            f"  {cell.model} c={cell.concurrency}: p95={cell.p95_latency_s or -1:.2f}s "
            f"tok/s={cell.agg_tok_per_s or -1:.1f} valid={cell.schema_valid_rate:.2f} "
            f"fail={cell.n_failures}"
        )

    run = asyncio.run(bench_mod.run_bench(cfg, full=full, on_cell=_show))
    cfg.run_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.run_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"bench complete: {len(run.cells)} cells → {cfg.run_path}")


@app.command()
def report(config: str = "params.yaml") -> None:
    """Report stage (offline): figures + metrics.json + report.html from bench data."""
    cfg = load_config(Path(config))
    if not cfg.run_path.exists():
        raise typer.BadParameter(
            f"no bench run at {cfg.run_path}; run `bench` first (needs a live Ollama)"
        )
    run = BenchRun.model_validate_json(cfg.run_path.read_text(encoding="utf-8"))
    out = report_mod.build_report(run, cfg)
    typer.echo(f"report written: {out}")


if __name__ == "__main__":
    app()
