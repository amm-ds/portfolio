"""Typer CLI for the anomaly-detection pipeline.

Commands mirror the DVC stages: prepare → validate → features → train →
tune → evaluate, plus ``dq-report`` (re-render the DQ report) and ``all``.
"""

import polars as pl
import typer
from portfolio_core.logging import get_logger

from anomaly_detection.config import PROJECT_ROOT, AnomalyConfig
from anomaly_detection.data import load_raw, prepare
from anomaly_detection.evaluate import run_evaluation
from anomaly_detection.features import build_features, load_features, save_features
from anomaly_detection.hpo import tune_all
from anomaly_detection.model import feature_matrix, fit_models, save_models, split_train_test
from anomaly_detection.validate import validate as run_validation

logger = get_logger(__name__)
app = typer.Typer(help="Anomaly Detection over Telemetry — pipeline CLI", add_completion=False)

PARAMS_PATH = PROJECT_ROOT / "params.yaml"


def get_config() -> AnomalyConfig:
    """Build the config from params.yaml when present, else defaults."""
    if PARAMS_PATH.exists():
        import yaml  # type: ignore[import-untyped]

        params = yaml.safe_load(PARAMS_PATH.read_text()) or {}
        return AnomalyConfig(**params)
    return AnomalyConfig()


def _require_raw(config: AnomalyConfig) -> pl.DataFrame:
    """Load the raw frame, preparing it first if the artifact is missing."""
    if not config.raw_path.exists():
        logger.info("raw data missing; running prepare first")
        prepare(config)
    return load_raw(config)


@app.command("prepare")
def prepare_data() -> None:
    """Generate seeded synthetic telemetry and register the dataset contract."""
    config = get_config()
    df = prepare(config)
    typer.echo(f"prepared {df.height} rows -> {config.raw_path}")


@app.command()
def validate() -> None:
    """Run DQ gates on the raw telemetry; fails loudly on any violation."""
    config = get_config()
    report = run_validation(_require_raw(config), config)
    typer.echo(f"DQ gates passed: {len(report.checks)} checks -> {config.dq_report_path}")


@app.command("dq-report")
def dq_report() -> None:
    """Re-run DQ gates and render the standalone HTML DQ report."""
    config = get_config()
    report = run_validation(_require_raw(config), config)
    typer.echo(f"DQ report -> {config.dq_report_path} (passed={report.passed})")


@app.command()
def features() -> None:
    """Build rolling-aggregate features from the raw telemetry."""
    config = get_config()
    df = build_features(_require_raw(config), config.windows)
    save_features(df, config)
    typer.echo(f"features: {df.height} rows -> {config.features_path}")


@app.command()
def train() -> None:
    """Fit the configured detectors on the train window only."""
    config = get_config()
    df = load_features(config)
    train_df, _ = split_train_test(df, config.train_frac)
    fitted = fit_models(feature_matrix(train_df, config), config)
    save_models(fitted, config)
    typer.echo(f"trained {len(fitted)} models -> {config.models_dir}")


@app.command()
def tune() -> None:
    """HPO (Optuna, seeded TPE) per family on a validation slice of the train window."""
    config = get_config()
    df = load_features(config)
    train_df, _ = split_train_test(df, config.train_frac)
    x_train = feature_matrix(train_df, config)
    y_train = train_df["is_anomaly"].to_numpy().astype(int)
    tuned = tune_all(config, x_train, y_train)
    typer.echo(f"tuned {len(tuned)} detectors -> {config.tuned_models_dir}")


@app.command()
def evaluate() -> None:
    """Score detectors on the test window; write metrics, report, and figures."""
    config = get_config()
    metrics, report_path = run_evaluation(config)
    for name, values in metrics.items():
        typer.echo(f"{name}: " + ", ".join(f"{k}={v:.4f}" for k, v in values.items()))
    typer.echo(f"report -> {report_path}")


@app.command()
def all() -> None:
    """Run the full pipeline: prepare → validate → features → train → tune → evaluate."""
    config = get_config()
    df = prepare(config)
    report = run_validation(df, config)
    typer.echo(f"DQ gates passed: {len(report.checks)} checks")
    feat = build_features(df, config.windows)
    save_features(feat, config)
    train_df, _ = split_train_test(feat, config.train_frac)
    x_train = feature_matrix(train_df, config)
    save_models(fit_models(x_train, config), config)
    tune_all(config, x_train, train_df["is_anomaly"].to_numpy().astype(int))
    metrics, report_path = run_evaluation(config)
    for name, values in metrics.items():
        typer.echo(f"{name}: " + ", ".join(f"{k}={v:.4f}" for k, v in values.items()))
    typer.echo(f"report -> {report_path}")


if __name__ == "__main__":
    app()
