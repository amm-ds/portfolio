"""Typer CLI: prepare → eda → features → train → evaluate → report.

``all`` chains every stage in-process (fast, single interpreter for the full
pipeline); each individual command is what ``dvc.yaml`` runs per stage.
"""

from pathlib import Path
from typing import Annotated, Any

import typer
from portfolio_core.logging import get_logger

from tabular_ml_lifecycle.config import LifecycleConfig, yaml
from tabular_ml_lifecycle.report import build_report
from tabular_ml_lifecycle.stages import (
    eda_core,
    evaluate_core,
    features_core,
    prepare_core,
    train_core,
)

OptSource = Annotated[str | None, typer.Option(help="Override data_source (uci|synthetic).")]
OptSeed = Annotated[int | None, typer.Option(help="Override seed from params.yaml.")]
OptParams = Annotated[Path, typer.Option(help="YAML file with config keys.")]

app = typer.Typer(
    help="Tabular ML + deep learning lifecycle on UCI Bike Sharing (hourly).",
    add_completion=False,
)
log = get_logger(__name__)


def load_config(
    params_file: Path = Path("params.yaml"),
    data_source: str | None = None,
    seed: int | None = None,
) -> LifecycleConfig:
    """Build LifecycleConfig from params.yaml (if present), with CLI overrides."""
    data: dict[str, Any] = {}
    if params_file.exists():
        data = yaml.safe_load(params_file.read_text()) or {}
        log.info("load_config: %s (%d keys)", params_file, len(data))
    if data_source is not None:
        data["data_source"] = data_source
    if seed is not None:
        data["seed"] = seed
    return LifecycleConfig(**data)


@app.command()
def prepare(
    data_source: OptSource = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Fetch the pinned UCI zip (or generate the synthetic twin) and run DQ gates."""
    prepare_core(load_config(params_file, data_source, seed))


@app.command()
def eda(
    data_source: OptSource = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Committed EDA figures: rentals-by-hour-by-season, weather, correlations."""
    eda_core(load_config(params_file, data_source, seed))


@app.command()
def features(
    data_source: OptSource = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Time split, lag features, MI + permutation selection, feature contract."""
    features_core(load_config(params_file, data_source, seed))


@app.command()
def train(
    data_source: OptSource = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Model-selection ladder: naive floor, ridge, RF, LightGBM HPO, PyTorch MLP."""
    train_core(load_config(params_file, data_source, seed))


@app.command()
def evaluate(
    data_source: OptSource = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Score every candidate once on the test window; paired-bootstrap the champion."""
    evaluate_core(load_config(params_file, data_source, seed))


@app.command()
def report(
    data_source: OptSource = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Assemble report.html + results.md from the committed artifacts."""
    cfg = load_config(params_file, data_source, seed)
    build_report(cfg.reports_dir, Path(__file__).resolve().parents[3])


@app.command("all")
def run_all(
    data_source: OptSource = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Run the full pipeline: prepare → eda → features → train → evaluate → report."""
    cfg = load_config(params_file, data_source, seed)
    prepare_core(cfg)
    eda_core(cfg)
    features_core(cfg)
    train_core(cfg)
    evaluate_core(cfg)
    build_report(cfg.reports_dir, Path(__file__).resolve().parents[3])


if __name__ == "__main__":
    app()
