"""Typer CLI: the pipeline as subcommands (mirrors dvc.yaml stages)."""

import json

import typer
from portfolio_core.logging import get_logger, setup_logging

from mobility import config as config_mod
from mobility.config import MobilityConfig
from mobility.download import download_all
from mobility.drift import MonthUnavailableError, run_drift_check
from mobility.evaluate import build_report
from mobility.features import build_features
from mobility.join import join_all
from mobility.model import train_baselines, train_nn
from mobility.serving import build_serving_artifact
from mobility.transfer import evaluate_transfer
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


@app.command("train-arms")
def train_arms_cmd() -> None:
    """Tune + fit the xgb/lgbm challenger arms (runs in a torch-free subprocess)."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "from mobility.arms import fit_arms; fit_arms()"],
        check=True,
    )
    typer.echo(f"train-arms exit={result.returncode}")


@app.command("train-nn")
def train_nn_cmd() -> None:
    """Train TemporalNet (hand-written loop) and persist test predictions."""
    preds = train_nn(_cfg())
    typer.echo(f"predictions: {preds.height} test rows")


@app.command("build-serving-artifact")
def build_serving_artifact_cmd() -> None:
    """Persist the yellow GBM pair + per-service (green) bundle + registry."""
    out = build_serving_artifact(_cfg())
    typer.echo(f"serving artifact -> {out} (yellow root + green/ per-service bundle)")


@app.command("transfer")
def transfer_cmd() -> None:
    """Evaluate yellow-trained GBMs on green-taxi demand (bounded 3-month slice)."""
    result = evaluate_transfer(_cfg())
    typer.echo(json.dumps(result["overall"], indent=2))


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


@app.command("drift-check")
def drift_check_cmd(
    month: str = typer.Option(
        ..., "--month", "-m", help="TLC month to score (YYYY-MM); must be published upstream."
    ),
    fail_on_regression: bool = typer.Option(
        False,
        "--fail-on-regression",
        help="Exit 1 when the month's MAE regresses beyond tolerance "
        "(the scheduled Action sets this).",
    ),
    tolerance: float | None = typer.Option(
        None,
        "--tolerance",
        help="Regression tolerance override (default: params drift.tolerance = 0.15).",
    ),
) -> None:
    """Score one published TLC month against the pinned serving model (drift observatory).

    Exit codes (contract: .github/workflows/drift-observatory.yml):
    0 = within tolerance (also without --fail-on-regression on a regression —
    the report is still written, for manual runs); 1 = regression beyond
    tolerance (only with --fail-on-regression); 2 = month not published yet
    (HTTP 404/403) or bad --month — the Action treats 2 as skip-worthy, no
    issue opened.
    """
    try:
        result = run_drift_check(month, _cfg(), tolerance=tolerance)
    except MonthUnavailableError as e:
        typer.echo(f"drift-check skipped: {e}", err=True)
        raise typer.Exit(2) from None
    except ValueError as e:
        # Bad --month format is a skip (exit 2); anything else is a real failure.
        if "expected YYYY-MM" in str(e):
            typer.echo(f"drift-check: {e}", err=True)
            raise typer.Exit(2) from None
        raise

    status = "REGRESSION" if result.regressed else "within tolerance"
    typer.echo(
        f"{month}: MAE {result.month_mae:.4f} vs pinned {result.pinned_mae:.4f} "
        f"({result.regression_ratio:+.2%}, tolerance ±{result.tolerance:.0%}) → {status}"
    )
    typer.echo(f"report -> {result.report_path}")
    if result.regressed and fail_on_regression:
        raise typer.Exit(1)


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
    train_arms_cmd()
    train_nn_cmd()
    transfer_cmd()
    build_serving_artifact_cmd()
    evaluate_cmd()


def main() -> None:
    setup_logging("INFO")
    app()


if __name__ == "__main__":
    main()
