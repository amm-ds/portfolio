"""Typer entrypoints: one command per DVC stage."""

import json
from pathlib import Path

import typer

from dynamic_pricing.benchmark import run_benchmark
from dynamic_pricing.calibrate import run_calibration
from dynamic_pricing.evaluate import run_sealed_evaluation
from dynamic_pricing.figures import run_figures
from dynamic_pricing.preregister import run_preregistration
from dynamic_pricing.train import run_smoke, run_training
from dynamic_pricing.tune import run_tuning

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]

app = typer.Typer(help="15-dynamic-pricing-rl pipeline CLI")


def _params_path(config: str) -> Path:
    path = Path(config)
    return path if path.is_absolute() else PROJECT_ROOT / path


@app.callback()
def main() -> None:
    """Run reproducible dynamic-pricing pipeline stages."""


@app.command()
def calibrate(config: str = "params.yaml") -> None:
    """Calibrate read-only from the pinned M5 parquet snapshot."""
    summary = run_calibration(PROJECT_ROOT, REPO_ROOT, _params_path(config))
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


@app.command("benchmark-env")
def benchmark_env(config: str = "params.yaml") -> None:
    """Benchmark DummyVecEnv and SubprocVecEnv on train-series episodes."""
    summary = run_benchmark(PROJECT_ROOT, REPO_ROOT, _params_path(config))
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


@app.command("tune-baselines")
def tune_baselines(config: str = "params.yaml") -> None:
    """Tune on train and select the comparator on validation episodes only."""
    summary = run_tuning(PROJECT_ROOT, REPO_ROOT, _params_path(config))
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


@app.command()
def preregister(config: str = "params.yaml") -> None:
    """Generate sealed specs and log the frozen protocol without evaluating them."""
    summary = run_preregistration(PROJECT_ROOT, REPO_ROOT, _params_path(config))
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


@app.command("train-smoke")
def train_smoke(config: str = "params.yaml") -> None:
    """Measure PPO throughput before choosing the full training budget."""
    summary = run_smoke(PROJECT_ROOT, REPO_ROOT, _params_path(config))
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


@app.command()
def train(config: str = "params.yaml", steps: int = 3_000_000) -> None:
    """Train seeds 0-2 and retain only the best validation checkpoint."""
    summary = run_training(PROJECT_ROOT, REPO_ROOT, _params_path(config), steps=steps)
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


@app.command("seal-read")
def seal_read(config: str = "params.yaml") -> None:
    """Consume the test and stress sets exactly once under the frozen protocol."""
    summary = run_sealed_evaluation(PROJECT_ROOT, REPO_ROOT, _params_path(config))
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


@app.command()
def figures(config: str = "params.yaml") -> None:
    """Rebuild figures and HTML without evaluating any policy."""
    summary = run_figures(PROJECT_ROOT, REPO_ROOT, _params_path(config))
    typer.echo(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    app()
