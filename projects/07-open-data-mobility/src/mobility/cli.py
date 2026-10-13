"""Typer CLI: the pipeline as subcommands (mirrors dvc.yaml stages)."""

import typer
from portfolio_core.logging import get_logger, setup_logging

from mobility import config as config_mod
from mobility.config import MobilityConfig
from mobility.download import download_all
from mobility.evaluate import build_report
from mobility.features import build_features
from mobility.join import join_all
from mobility.model import train_baselines, train_nn
from mobility.tune import tune_all
from mobility.validate import load_dq_reports, persist_dq_summary, validate_all

logger = get_logger(__name__)
app = typer.Typer(add_completion=False, help="Urban Mobility Demand Intelligence pipeline")


def _cfg() -> MobilityConfig:
    return config_mod.get_config()


@app.command("download")
def download_cmd() -> None:
    """Fetch TLC + NOAA raw files (checksum-pinned, idempotent)."""
    contracts = download_all(_cfg())
    typer.echo(f"downloaded {len(contracts)} files")


@app.command("validate")
def validate_cmd() -> None:
    """Run per-month DQ gates and write cleaned parquets."""
    reports = validate_all(_cfg())
    typer.echo(f"{len(reports)} months passed DQ gates")


@app.command("join")
def join_cmd() -> None:
    """Aggregate to zone-hour demand and join weather + boroughs."""
    demand = join_all(_cfg())
    typer.echo(f"zone_hour_demand: {demand.height} rows")


@app.command("features")
def features_cmd() -> None:
    """Build lag/calendar/weather features with a temporal train/test split."""
    train, test = build_features(_cfg())
    typer.echo(f"train {train.height} rows, test {test.height} rows")


@app.command("tune")
def tune_cmd() -> None:
    """Optuna HPO for GBM + TemporalNet (embargoed train-side validation only)."""
    results = tune_all(_cfg())
    for kind, res in results.items():
        typer.echo(f"{kind}: best val MAE {res['best_val_mae']:.4f} <- {res['best_params']}")


@app.command("train-baselines")
def train_baselines_cmd() -> None:
    """Fit GBM mean + p90 quantile models and persist test predictions."""
    preds = train_baselines(_cfg())
    typer.echo(f"predictions: {preds.height} test rows")


@app.command("train-nn")
def train_nn_cmd() -> None:
    """Train TemporalNet (hand-written loop) and persist test predictions."""
    preds = train_nn(_cfg())
    typer.echo(f"predictions: {preds.height} test rows")


@app.command("evaluate")
def evaluate_cmd() -> None:
    """Metrics, figures, and the HTML report from persisted predictions."""
    path = build_report(_cfg())
    typer.echo(f"report -> {path}")


@app.command("dashboard")
def dashboard_cmd() -> None:
    """Reassemble the HTML report/figures (dvc 'dashboard' stage)."""
    path = build_report(_cfg())
    typer.echo(f"dashboard -> {path}")


@app.command("dq-report")
def dq_report_cmd() -> None:
    """Print and re-persist the latest data-quality digest."""
    cfg = _cfg()
    reports = load_dq_reports(cfg)
    persist_dq_summary(cfg, reports)
    typer.echo(f"{len(reports)} monthly reports: {sum(r.n_rows for r in reports):,} rows total")
    for r in reports:
        typer.echo(f"  {r.dataset}: {r.n_rows:,} rows, {len(r.checks)} checks, {r.n_failed} failed")


@app.command("all")
def all_cmd() -> None:
    """Run the full pipeline end to end (including HPO tuning)."""
    download_cmd()
    validate_cmd()
    join_cmd()
    features_cmd()
    tune_cmd()
    train_baselines_cmd()
    train_nn_cmd()
    evaluate_cmd()


def main() -> None:
    setup_logging("INFO")
    app()


if __name__ == "__main__":
    main()
