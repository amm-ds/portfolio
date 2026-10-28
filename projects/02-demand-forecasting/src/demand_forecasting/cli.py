"""Typer CLI: prepare → features → train → evaluate (or ``all`` in one go).

Each command is a thin orchestration layer over the library modules; dvc.yaml
stages mirror these entry points one-to-one. ``hpo`` is separate (minutes, not
seconds) and feeds the production ``hgb_tuned`` config.

``--data-source uci`` activates the real-data track; every artefact lands in
``data_uci/`` / ``reports_uci/`` so both tracks stay side by side. The
synthetic track remains the default (fully offline, CI-safe).
"""

import os

# Apple Accelerate (numpy's BLAS/LAPACK on macOS arm64) reads
# VECLIB_MAXIMUM_THREADS at library-init time and threadpoolctl cannot limit
# it (threadpool_info() is empty on this host). Accelerate's threaded BLAS
# reductions are NOT run-to-run reproducible, which makes any metric or
# report that flows through numpy/loky LAPACK byte-drift between runs — pin
# Accelerate to one thread BEFORE numpy loads so committed artefacts are
# byte-identical across runs. setdefault keeps an explicit user override.
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

from pathlib import Path
from typing import Annotated, Literal

import polars as pl
import typer

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.data import prepare
from demand_forecasting.evaluate import evaluate
from demand_forecasting.features import build_features, save_features
from demand_forecasting.model import fit_all, save_models
from demand_forecasting.probabilistic import run_probabilistic
from demand_forecasting.reconcile import reconcile_and_plot
from demand_forecasting.serving import build_serving_artifact

app = typer.Typer(
    help="Hierarchical demand forecasting on a synthetic retail hierarchy.", no_args_is_help=True
)


def _settings_and_config(
    data_dir: Annotated[Path | None, typer.Option(help="Override data dir.")] = None,
    reports_dir: Annotated[Path | None, typer.Option(help="Override reports dir.")] = None,
    data_source: Annotated[
        Literal["synthetic", "uci"], typer.Option(help="Panel track (uci needs network once).")
    ] = "synthetic",
) -> tuple[DemandSettings, ForecastConfig]:
    base = DemandSettings()
    root = Path.cwd()
    if data_source == "uci" and data_dir is None:
        data_dir = root / "data_uci"
    if data_source == "uci" and reports_dir is None:
        reports_dir = root / "reports_uci"
    settings = DemandSettings(
        data_dir=data_dir or base.data_dir,
        reports_dir=reports_dir or base.reports_dir,
    )
    # params.yaml overlay first, then the CLI flag wins (an explicit
    # --data-source must not be clobbered by the params default)
    config = _config_from_params(ForecastConfig())
    return settings, config.model_copy(update={"data_source": data_source})


def _config_from_params(config: ForecastConfig) -> ForecastConfig:
    """Overlay params.yaml onto the config (dvc param changes are real).

    Only keys that match ForecastConfig fields are applied; unknown keys are
    ignored so the file can carry comments and per-stage extras.
    """
    import yaml  # type: ignore[import-untyped]

    path = Path("params.yaml")
    if not path.exists():
        return config
    data = yaml.safe_load(path.read_text()) or {}
    known = {k: v for k, v in data.items() if k in ForecastConfig.model_fields}
    return ForecastConfig(**known) if known else config


@app.command("prepare")
def prepare_data(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> Path:
    """Build the panel (synthetic or UCI) and validate it through the DQ gates."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    return prepare(settings, config)


@app.command()
def features(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> Path:
    """Build leakage-safe lag + calendar features from the prepared panel."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    frame = build_features(panel, config)
    return save_features(frame, settings)


@app.command()
def train(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> Path:
    """Fit every model on the full history and persist them (deployment artefacts).

    Model selection is the honest time-CV backtest in ``evaluate``; this stage
    refits the chosen configuration on all available rows.
    """
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    frame = pl.read_parquet(settings.data_dir / "features.parquet")
    models = fit_all(frame, config)
    return save_models(models, settings.data_dir / "models.pkl")


@app.command()
def hpo(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    trials: Annotated[int | None, typer.Option(help="Override trial count.")] = None,
    model: Annotated[
        Literal[
            "hgb",
            "xgb",
            "lgbm",
            "multistep_tweedie",
            "multistep_lgbm_tweedie",
            "multistep_lgbm_poisson",
        ],
        typer.Option(help="Booster arm to tune."),
    ] = "hgb",
) -> None:
    """Run seeded Optuna HPO for a production booster config (slow; not in ``all``)."""
    if model == "multistep_tweedie":
        from demand_forecasting.hpo import tune_multistep_tweedie

        settings, config = _settings_and_config(data_dir, reports_dir)
        tune_multistep_tweedie(settings, config, n_trials=trials or 12)
        return
    if model in ("multistep_lgbm_tweedie", "multistep_lgbm_poisson"):
        from demand_forecasting.hpo import tune_multistep_lgbm

        settings, config = _settings_and_config(data_dir, reports_dir)
        tune_multistep_lgbm(
            settings, config, n_trials=trials or 12, objective_name=model.rsplit("_", 1)[-1]
        )
        return
    from demand_forecasting.hpo import run_hpo

    settings, config = _settings_and_config(data_dir, reports_dir)
    run_hpo(settings, config, model=model, n_trials=trials)


@app.command("evaluate")
def evaluate_cmd(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> None:
    """Backtest all models, reconcile, and compute probabilistic coverage."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    result = evaluate(settings, config)
    reconcile_and_plot(settings, config, result)
    run_probabilistic(settings, config, multistep=result.multistep)


@app.command("build-serving")
def build_serving(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> Path:
    """Build the showcase-API serving artifact (loads pickles; no retraining)."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    return build_serving_artifact(settings, config)


@app.command()
def all(
    data_dir: Annotated[Path | None, typer.Option()] = None,
    reports_dir: Annotated[Path | None, typer.Option()] = None,
    data_source: Annotated[Literal["synthetic", "uci"], typer.Option()] = "synthetic",
) -> None:
    """Run the full pipeline: prepare → features → train → evaluate (+extras)."""
    settings, config = _settings_and_config(data_dir, reports_dir, data_source)
    prepare(settings, config)
    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    frame = build_features(panel, config)
    save_features(frame, settings)
    save_models(fit_all(frame, config), settings.data_dir / "models.pkl")
    result = evaluate(settings, config)
    reconcile_and_plot(settings, config, result)
    run_probabilistic(settings, config, multistep=result.multistep)


@app.command("evaluate-m5")
def evaluate_m5(
    data_dir: Annotated[Path | None, typer.Option(help="M5 subset dir.")] = None,
    reports_dir: Annotated[Path | None, typer.Option(help="M5 reports dir.")] = None,
) -> None:
    """Run the M5 headline experiment (protocol m5_direct_v1) and write reports_m5/.

    Offline: reads the committed, checksum-pinned subset in data_m5/; writes
    metrics.json, probabilistic.json, evaluation_metadata.json, figures and
    report.html under reports_m5/ (minutes, not seconds — the real evaluate).
    """
    root = Path.cwd()
    data_dir = data_dir or root / "data_m5"
    reports_dir = reports_dir or root / "reports_m5"
    from demand_forecasting.m5_report import build_report
    from demand_forecasting.m5_track import run_m5_track, write_m5_artifacts

    result = run_m5_track(data_dir)
    write_m5_artifacts(result, reports_dir)
    build_report(reports_dir)


@app.command("build-report-m5")
def build_report_m5(
    reports_dir: Annotated[Path | None, typer.Option(help="M5 reports dir.")] = None,
) -> Path:
    """Rebuild reports_m5/report.html (+figures) from the committed artifacts only."""
    root = Path.cwd()
    reports_dir = reports_dir or root / "reports_m5"
    from demand_forecasting.m5_report import build_report

    return build_report(reports_dir)


@app.command("demo-payload-m5")
def demo_payload_m5(
    data_dir: Annotated[Path | None, typer.Option(help="M5 subset dir.")] = None,
    reports_dir: Annotated[Path | None, typer.Option(help="M5 reports dir.")] = None,
) -> Path:
    """Build the forecast-workbench demo payload (reports_m5/demo_payload.json, schema v4).

    Recomputes the per-series catalog curves with the m5_track functions on
    the committed subset (seconds-to-minutes, NOT the full ~22-min evaluate)
    and drift-guards the per-series candidates' pooled test WAPE against the
    committed metrics block at 1e-9.
    """
    root = Path.cwd()
    data_dir = data_dir or root / "data_m5"
    reports_dir = reports_dir or root / "reports_m5"
    from demand_forecasting.m5_demo_payload import write_demo_payload

    return write_demo_payload(data_dir, reports_dir)


if __name__ == "__main__":
    app()
