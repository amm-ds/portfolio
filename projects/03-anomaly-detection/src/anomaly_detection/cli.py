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
from anomaly_detection.nab import run_nab
from anomaly_detection.nsl import run_nsl_probe
from anomaly_detection.probes import run_residual_probe
from anomaly_detection.stream import run_detection
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
def detect(
    adaptive: bool = typer.Option(True, "--adaptive/--fixed", help="Adaptive vs. fixed threshold."),
    chunk_rows: int = typer.Option(
        1440, "--chunk-rows", help="Stream chunk size in rows (1440 = 24h)."
    ),
    drift_z: float = typer.Option(
        1.0, "--drift-z", help="Drift z-score trigger (median shift in IQRs)."
    ),
) -> None:
    """Simulate streaming detection over the test window; compare thresholds."""
    config = get_config()
    result = run_detection(config, adaptive=adaptive, chunk_rows=chunk_rows, drift_z_max=drift_z)
    typer.echo(
        f"stream: {result['n_chunks']} chunks, {len(result.get('drift_events', []))} drift events; "
        f"fixed flags={result['fixed']['flags']} "
        + (
            f"adaptive flags={result['adaptive']['flags']}"
            if "adaptive" in result
            else "(fixed mode)"
        )
    )


@app.command()
def residuals() -> None:
    """Probe: do rolling-median residual features de-cluster the anomalies?"""
    config = get_config()
    result = run_residual_probe(config)
    typer.echo(
        f"residual probe: base AUC={result['base']['roc_auc']:.4f} -> "
        f"with residuals AUC={result['with_residuals']['roc_auc']:.4f} ({result['verdict']})"
    )


@app.command()
def nab() -> None:
    """NAB real-data primary track: 12 series, event-based metrics + figures."""
    config = get_config()
    result = run_nab(config)
    overall = result["overall"]
    detected, missed = overall["events_detected"], overall["events_missed"]
    typer.echo(
        f"NAB overall: PR-AUC={overall['pr_auc']:.3f} range-F1={overall['range_f1']:.3f} "
        f"({detected}/{detected + missed} events, {overall['alerts_fired']} alerts)"
    )


@app.command("nab-sweep")
def nab_sweep() -> None:
    """NAB detector-family x feature-set sweep + dedup/per-series budget metrics."""
    config = get_config()
    from anomaly_detection.nab_sweep import run_nab_sweep

    result = run_nab_sweep(config)
    best = max(
        result["grid"].items(),
        key=lambda kv: kv[1]["overall"]["pr_auc"] or 0.0,
    )
    st = best[1]["overall"]["streams"]
    typer.echo(
        f"NAB sweep: best pointwise config {best[0]} "
        f"(PR-AUC={best[1]['overall']['pr_auc']:.3f}); alert load raw "
        f"{st['raw']['alerts_fired']} -> budgeted {st['budgeted']['alerts_fired']} "
        f"(recall {st['raw']['range_recall']:.3f} -> {st['budgeted']['range_recall']:.3f})"
    )


@app.command("nab-tune")
def nab_tune() -> None:
    """Select per-family (threshold budget, cooldown) on train-side validation;
    score the NAB test window once per adopted operating point."""
    config = get_config()
    from anomaly_detection.nab_tune import run_nab_tune

    result = run_nab_tune(config)
    for detector, sel in result["selection"]["families"].items():
        typer.echo(
            f"{detector}: budget={sel['budget']:.3f} cooldown={sel['cooldown_hours']:.0f}h "
            f"adopted={sel['adopted']} "
            f"(val range-F1 {sel['val_range_f1']:.3f} vs default {sel['val_range_f1_default']:.3f})"
        )
    vs = result["vs_default_sweep_budgeted"]
    if vs.get("available"):
        for cell, row in vs["cells"].items():
            typer.echo(
                f"{cell}: budgeted alerts {row['default_budgeted']['alerts_fired']} -> "
                f"{row['tuned_budgeted']['alerts_fired']} "
                f"(range-F1 {row['default_budgeted']['range_f1']:.3f} -> "
                f"{row['tuned_budgeted']['range_f1']:.3f})"
            )


@app.command()
def nsl() -> None:
    """NSL-KDD production track: fetch, map, and run the transfer probe."""
    config = get_config()
    result = run_nsl_probe(config)
    typer.echo(
        f"NSL-KDD transfer probe: ROC-AUC={result['roc_auc']:.4f} "
        f"PR-AUC={result['pr_auc']:.4f} (test prevalence {result['test_anomaly_rate']:.1%})"
    )


@app.command()
def all() -> None:
    """Run the full pipeline incl. probes: prepare → validate → features →
    train → tune → evaluate → detect → residuals → nsl."""
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
    detection = run_detection(config)
    typer.echo(
        f"stream: {len(detection['drift_events'])} drift events; "
        f"fixed flags={detection['fixed']['flags']} adaptive flags={detection['adaptive']['flags']}"
    )
    probe = run_residual_probe(config)
    typer.echo(
        f"residual probe: base AUC={probe['base']['roc_auc']:.4f} -> "
        f"with residuals AUC={probe['with_residuals']['roc_auc']:.4f} ({probe['verdict']})"
    )
    nsl_result = run_nsl_probe(config)
    typer.echo(
        f"NSL-KDD transfer probe: ROC-AUC={nsl_result['roc_auc']:.4f} "
        f"PR-AUC={nsl_result['pr_auc']:.4f}"
    )
    nab_result = run_nab(config)
    overall = nab_result["overall"]
    detected, missed = overall["events_detected"], overall["events_missed"]
    typer.echo(
        f"NAB overall: PR-AUC={overall['pr_auc']:.3f} range-F1={overall['range_f1']:.3f} "
        f"({detected}/{detected + missed} events, {overall['alerts_fired']} alerts)"
    )


if __name__ == "__main__":
    app()
