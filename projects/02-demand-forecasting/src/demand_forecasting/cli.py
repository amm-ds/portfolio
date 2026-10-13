"""Typer CLI: prepare → features → train → evaluate (or ``all`` in one go).

Each command is a thin orchestration layer over the library modules; dvc.yaml
stages mirror these entry points one-to-one. ``hpo`` is separate (minutes, not
seconds) and feeds the production ``hgb_tuned`` config.
"""

from pathlib import Path
from typing import Annotated

import polars as pl
import typer

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.data import prepare
from demand_forecasting.evaluate import evaluate
from demand_forecasting.features import build_features, save_features
from demand_forecasting.model import fit_all, save_models
from demand_forecasting.reconcile import reconcile_and_plot

app = typer.Typer(
    help="Hierarchical demand forecasting on a synthetic retail hierarchy.", no_args_is_help=True
)


def _settings_and_config(
    data_dir: Annotated[Path | None, typer.Option(help="Override data dir.")] = None,
    reports_dir: Annotated[Path | None, typer.Option(help="Override reports dir.")] = None,
) -> tuple[DemandSettings, ForecastConfig]:
    base = DemandSettings()
    settings = DemandSettings(
        data_dir=data_dir or base.data_dir,
        reports_dir=reports_dir or base.reports_dir,
    )
    return settings, ForecastConfig()


@app.command("prepare")
def prepare_data(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
) -> Path:
    """Generate the synthetic hierarchy and validate it through the DQ gates."""
    settings, config = _settings_and_config(data_dir, reports_dir)
    return prepare(settings, config)


@app.command()
def features(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
) -> Path:
    """Build leakage-safe lag + calendar features from the prepared panel."""
    settings, config = _settings_and_config(data_dir, reports_dir)
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    frame = build_features(panel, config)
    return save_features(frame, settings)


@app.command()
def train(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
) -> Path:
    """Fit both models on the full history and persist them (deployment artefacts).

    Model selection is the honest time-CV backtest in ``evaluate``; this stage
    refits the chosen configuration on all available rows.
    """
    settings, config = _settings_and_config(data_dir, reports_dir)
    frame = pl.read_parquet(settings.data_dir / "features.parquet")
    models = fit_all(frame, config)
    return save_models(models, settings.data_dir / "models.pkl")


@app.command()
def hpo(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    trials: Annotated[int | None, typer.Option(help="Override trial count.")] = None,
) -> None:
    """Run seeded Optuna HPO for the production HGB config (slow; not part of ``all``)."""
    from demand_forecasting.hpo import run_hpo

    settings, config = _settings_and_config(data_dir, reports_dir)
    run_hpo(settings, config, n_trials=trials)


@app.command("evaluate")
def evaluate_cmd(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Backtest all models with expanding-window time CV and write the report."""
    settings, config = _settings_and_config(data_dir, reports_dir)
    result = evaluate(settings, config)
    reconcile_and_plot(settings, config, result)


@app.command()
def all(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Run the full pipeline: prepare → features → train → evaluate (+reconcile)."""
    settings, config = _settings_and_config(data_dir, reports_dir)
    prepare(settings, config)
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    frame = build_features(panel, config)
    save_features(frame, settings)
    save_models(fit_all(frame, config), settings.data_dir / "models.pkl")
    result = evaluate(settings, config)
    reconcile_and_plot(settings, config, result)


if __name__ == "__main__":
    app()
