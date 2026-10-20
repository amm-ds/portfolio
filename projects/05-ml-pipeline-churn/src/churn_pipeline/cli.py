"""Typer CLI: prepare → train → evaluate → all.

Each command is a thin wrapper around a core function so ``all`` can chain
them in-process (fast, single interpreter for the full pipeline).
"""

import json
import pickle
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated, Any, cast

import polars as pl
import typer
from portfolio_core import synthetic
from portfolio_core.dq import DQReport
from portfolio_core.io import fetch
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json
from portfolio_core.schemas import DatasetContract
from portfolio_eval.report import ReportBuilder
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split

from churn_pipeline.config import ChurnConfig, pd, threadpool_limits, yaml
from churn_pipeline.demo_payload import write_demo_payload
from churn_pipeline.eda import eda_churn_profile_figure
from churn_pipeline.evaluate import artifact_paths, evaluate_holdout
from churn_pipeline.hpo import ModelSelection, build_estimator, run_study
from churn_pipeline.model import (
    TARGET_COL,
    feature_cols,
    slice_cols,
    split_holdout,
    train_model,
)
from churn_pipeline.serving import build_serving_artifact

OptN = Annotated[int | None, typer.Option(help="Override n_samples from params.yaml.")]
OptSeed = Annotated[int | None, typer.Option(help="Override seed from params.yaml.")]
OptParams = Annotated[Path, typer.Option(help="YAML file with config keys.")]

app = typer.Typer(
    help="Churn modeling with production-grade sklearn pipelines.",
    add_completion=False,
)
log = get_logger(__name__)


def load_config(
    params_file: Path = Path("params.yaml"),
    n: int | None = None,
    seed: int | None = None,
) -> ChurnConfig:
    """Build ChurnConfig from params.yaml (if present), with CLI overrides."""
    data: dict[str, Any] = {}
    if params_file.exists():
        data = yaml.safe_load(params_file.read_text()) or {}
        log.info("load_config: %s (%d keys)", params_file, len(data))
    if n is not None:
        data["n_samples"] = n
    if seed is not None:
        data["seed"] = seed
    return ChurnConfig(**data)


_FLOAT_DTYPES = (pl.Float32, pl.Float64)


def _missing_rate(df: pl.DataFrame, col: str) -> float:
    """Null rate treating NaN as missing (the generator encodes gaps as NaN)."""
    s = df[col]
    n = int(s.is_null().sum())
    if s.dtype in _FLOAT_DTYPES:
        n += int(s.is_nan().sum())
    return n / df.height


def run_dq_gates(df: pl.DataFrame, dataset: str = "churn") -> DQReport:
    """Enforce the platform's data-quality gates before any modeling.

    Gates follow the columns actually present: null-rate caps on the numeric
    features, range checks (age only exists on the synthetic/CI path), and
    the target gate when labels exist.
    """
    report = DQReport(dataset=dataset, n_rows=df.height)
    numeric_features = ["age", "tenure_months", "monthly_charges", "support_calls"]
    for col in numeric_features:
        if col in df.columns:
            report.check_null_rate(col, _missing_rate(df, col), 0.05)

    def minmax(col: str) -> tuple[float, float]:
        """Missing/NaN-safe min/max: an all-missing column fails range cleanly."""
        s = df[col].drop_nulls()
        if s.dtype in _FLOAT_DTYPES:
            s = s.filter(~s.is_nan())
        if s.len() == 0:
            return float("nan"), float("nan")
        return float(cast(float, s.min())), float(cast(float, s.max()))

    if "age" in df.columns:
        report.check_range("age", *minmax("age"), 18.0, 90.0)
    report.check_range("tenure_months", *minmax("tenure_months"), 0.0, 240.0)
    report.check_range("monthly_charges", *minmax("monthly_charges"), 0.0, 10_000.0)
    if TARGET_COL in df.columns:  # unlabeled client extracts skip the target gate
        report.check_range("churned", *minmax("churned"), 0.0, 1.0)
    report.raise_if_failed()
    return report


CONTRACT_MAP = {"Month-to-month": "month-to-month", "One year": "one-year", "Two year": "two-year"}
TELCO_COLUMNS = [
    "tenure_months",
    "monthly_charges",
    "contract",
    "internet_service",
    "gender",
    "senior_citizen",
    "churned",
]


def load_telco_frame(source: str, sha256: str = "") -> pl.DataFrame:
    """Load the IBM telco churn CSV (canonical source or local path) canonically.

    Renames to the project's schema: tenure/monthly charges numeric, contract
    levels mapped to the synthetic vocabulary, demographics kept as fairness
    slices (gender, senior_citizen, contract). `TotalCharges` blanks are why
    the raw column is re-parsed as float-tolerant and then dropped (leaky and
    derivable from tenure x monthly charges).
    """
    if source.startswith("http://") or source.startswith("https://"):
        dest = Path(tempfile.gettempdir()) / "churn-telco.csv"
        fetch(source, dest, expected_sha256=sha256 or None)
        raw_path: Path = dest
    else:
        raw_path = Path(source)
    raw = pl.read_csv(
        raw_path,
        null_values=["", " "],
        schema_overrides={"TotalCharges": pl.Utf8, "SeniorCitizen": pl.Utf8},
    )
    missing = [c for c in ("tenure", "MonthlyCharges", "Contract", "Churn") if c not in raw.columns]
    if missing:
        raise ValueError(f"telco source is missing required columns: {', '.join(missing)}")
    df = raw.select(
        pl.col("tenure").cast(pl.Float64).alias("tenure_months"),
        pl.col("MonthlyCharges").alias("monthly_charges"),
        pl.col("Contract").replace_strict(CONTRACT_MAP, default=None).alias("contract"),
        pl.col("InternetService").cast(pl.Utf8).alias("internet_service"),
        pl.col("gender").cast(pl.Utf8).alias("gender"),
        pl.when(pl.col("SeniorCitizen") == "1")
        .then(pl.lit("yes"))
        .otherwise(pl.lit("no"))
        .alias("senior_citizen"),
        (pl.col("Churn") == "Yes").alias("churned"),
    )
    return df.select(TELCO_COLUMNS)


REQUIRED_CLIENT_COLS = ["age", "tenure_months", "monthly_charges", "support_calls", "contract"]


def _load_client_extract(input_csv: Path) -> pl.DataFrame:
    """Load a client CRM extract; same columns as the synthetic generator.

    `churned` is optional at ingest (inference-only extracts have no labels);
    DQ/EDA adapt, and training requires it downstream.
    """
    df = pl.read_csv(input_csv)
    missing = [c for c in REQUIRED_CLIENT_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"client extract is missing required columns: {', '.join(missing)}")
    df = df.with_columns(pl.col("contract").cast(pl.Utf8))
    if TARGET_COL in df.columns:
        df = df.with_columns(pl.col(TARGET_COL).cast(pl.Boolean))
    return df


def prepare_core(cfg: ChurnConfig, input_csv: Path | None = None) -> Path:
    """Generate messy synthetic churn (or ingest a client extract), gate, persist."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)

    if input_csv is not None:
        df = _load_client_extract(input_csv)
        source = f"client://{input_csv.name}"
        name = "churn_client_extract"
        dataset = "churn_client_extract"
        license_ = "LicenseRef-Client-Contract"
        log.info("prepare: ingested client extract %s (%d rows)", input_csv, df.height)
    elif cfg.data_source == "telco":
        df = load_telco_frame(cfg.telco_source, cfg.telco_sha256)
        source = cfg.telco_source
        name = "churn_telco"
        dataset = "churn_telco"
        license_ = "IBM sample data (see data-registry/telco-churn.md)"
        log.info("prepare: loaded IBM telco churn (%d rows)", df.height)
    else:
        df = synthetic.churn(seed=cfg.seed, n=cfg.n_samples)
        source = "synthetic://portfolio_core.synthetic.churn"
        name = "churn_synthetic"
        dataset = "churn_synthetic"
        license_ = "MIT"
    report = run_dq_gates(df, dataset=dataset)

    (cfg.reports_dir / "dq_report.md").write_text(report.to_markdown())
    contract = DatasetContract(
        name=name,
        source=source,
        license=license_,
        snapshot_date=date.today(),
        checksum_sha256=synthetic.checksum_of_frame(df),
        n_rows=df.height,
    )
    (cfg.data_dir / "dataset_contract.json").write_text(contract.model_dump_json(indent=2))

    out = cfg.data_dir / "churn.parquet"
    df.write_parquet(out)
    churn_rate = "n/a (no labels)"
    if TARGET_COL in df.columns:
        churn_rate = f"{float(cast(float, df['churned'].mean())):.3f}"
    log.info(
        "prepare: %d rows, churn rate %s, %d/%d DQ checks passed",
        df.height,
        churn_rate,
        len(report.checks) - report.n_failed,
        len(report.checks),
    )

    if TARGET_COL in df.columns:
        eda_fig = eda_churn_profile_figure(df)
        save_html(eda_fig, cfg.reports_dir / "figures" / "eda_churn_profile.html")
        save_json(eda_fig, cfg.reports_dir / "figures" / "eda_churn_profile.json")
        log.info("prepare: EDA figure -> reports/figures/eda_churn_profile.{html,json}")
    else:
        log.info("prepare: no churned column - EDA figure skipped (inference-only extract)")
    return out


def _write_production_config(params_file: Path, family: str, params: dict[str, Any]) -> None:
    """Record the selected config in params.yaml (idempotent on reruns)."""

    def _clean(value: float) -> float | int:
        return int(value) if float(value).is_integer() else float(value)

    data: dict[str, Any] = yaml.safe_load(params_file.read_text()) or {}
    data["model_family"] = family
    data["model_params"] = {k: _clean(v) for k, v in sorted(params.items())}
    params_file.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


def train_core(cfg: ChurnConfig, params_file: Path = Path("params.yaml")) -> Path:
    """Split + wave-2 grid search + Optuna selection + calibration; persist artifacts."""
    df = pl.read_parquet(cfg.data_dir / "churn.parquet").to_pandas()
    X_train, X_test, y_train, y_test = split_holdout(cfg, df)

    grid = train_model(cfg, X_train, y_train)
    best = float(grid.best_score_)
    log.info("train: wave-2 logreg best C=%s (cv f1=%.4f)", grid.best_params_["clf__C"], best)

    # Model selection: HPO only when the config says 'auto'; else use the
    # production config already recorded in params.yaml.
    if cfg.model_family == "auto":
        selection = run_study(cfg, X_train, y_train)
        _write_production_config(params_file, selection.family, selection.params)
    else:
        selection = ModelSelection(
            family=cfg.model_family,
            params=dict(cfg.model_params),
            best_score=float("nan"),
            objective=cfg.hpo_objective,
            n_trials=0,
        )
        log.info("train: using production config from %s", params_file)

    X_fit, X_calib, y_fit, y_calib = train_test_split(
        X_train,
        y_train,
        test_size=cfg.calib_frac,
        stratify=y_train,
        random_state=cfg.seed,
    )
    # Single-threaded fits: OpenMP oversubscription slows HistGB ~200x here.
    with threadpool_limits(limits=1):
        selected = build_estimator(cfg, selection.family, selection.params)
        selected.fit(X_fit, y_fit)
        calibrated = CalibratedClassifierCV(
            estimator=build_estimator(cfg, selection.family, selection.params),
            method="isotonic",
            cv=2,
        )
        calibrated.fit(X_calib, y_calib)

    paths = artifact_paths(cfg)
    with paths["logreg"].open("wb") as fh:
        pickle.dump(grid.best_estimator_, fh)
    with paths["selected"].open("wb") as fh:
        pickle.dump(selected, fh)
    with paths["selected_calibrated"].open("wb") as fh:
        pickle.dump(calibrated, fh)
    holdout = X_test.copy()
    holdout[TARGET_COL] = y_test.to_numpy()
    pd.DataFrame(holdout).to_parquet(paths["holdout"])

    (cfg.data_dir / "model_selection.json").write_text(
        json.dumps(
            {
                "family": selection.family,
                "params": {k: float(v) for k, v in selection.params.items()},
                "objective": selection.objective,
                "best_score": selection.best_score,
                "n_trials": selection.n_trials,
                "family_scores": selection.family_scores,
            },
            indent=2,
        )
    )
    meta = {
        "best_params": {k: float(v) for k, v in grid.best_params_.items()},
        "cv_f1": best,
        "n_train": len(X_train),
        "n_holdout": len(X_test),
        "train_churn_rate": float(y_train.mean()),
    }
    (cfg.data_dir / "model_meta.json").write_text(json.dumps(meta, indent=2))
    return paths["logreg"]


def evaluate_core(cfg: ChurnConfig) -> Path:
    """Holdout metrics + figures + HTML report; JSON figures for the showcase API."""
    paths = artifact_paths(cfg)
    models = {}
    for key in ("logreg", "selected", "selected_calibrated"):
        with paths[key].open("rb") as fh:
            models[key] = pickle.load(fh)  # noqa: S301 - serving artifact persisted by this pipeline
    holdout = pd.read_parquet(paths["holdout"])
    X_test = holdout[list(dict.fromkeys(feature_cols(cfg) + slice_cols(cfg)))]
    y_test = holdout[TARGET_COL].astype(int)
    meta = json.loads((cfg.data_dir / "model_meta.json").read_text())

    runs, figures, summary = evaluate_holdout(
        cfg, models, X_test, y_test, train_base_rate=float(meta["train_churn_rate"])
    )

    builder = ReportBuilder(
        title="Churn Modeling — Holdout Evaluation", figures_dir=cfg.reports_dir / "figures"
    )
    for run in runs:
        builder.add_run(run)
    builder.build(cfg.reports_dir, figures=figures)
    for name, fig in figures.items():
        save_json(fig, cfg.reports_dir / "figures" / f"{name}.json")

    # Annotate metrics.json with run-level metadata (bootstrap CI etc.).
    metrics_path = cfg.reports_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text())
    metrics["_meta"] = {
        "cost_delta_ci": summary["cost_delta_ci"],
        "selected_opt": summary["selected_opt"],
        "naive_opt": summary["naive_opt"],
        "slices": summary["slices"],
    }
    metrics_path.write_text(json.dumps(metrics, indent=2))

    log.info(
        "evaluate: selected t=%.3f cost=%.0f (ece %.3f) | isotonic t=%.3f cost=%.0f (ece %.3f) "
        "| naive %.0f | calibration_helps=%s",
        summary["selected_opt"],
        summary["selected_cost"],
        summary["selected_ece"],
        summary["calibrated_opt"],
        summary["calibrated_cost"],
        summary["calibrated_ece"],
        summary["naive_cost"],
        summary["calibration_helps"],
    )
    return cfg.reports_dir / "report.html"


OptInput = Annotated[
    Path | None,
    typer.Option(
        "--input", help="Optional client CRM extract CSV (same columns as the synthetic data)."
    ),
]


@app.command()
def prepare(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
    input_csv: OptInput = None,
) -> None:
    """Generate synthetic churn (or ingest a client extract) and run DQ gates."""
    prepare_core(load_config(params_file, n, seed), input_csv=input_csv)


@app.command()
def train(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Train the pipeline with grid-searched C on a stratified split."""
    train_core(load_config(params_file, n, seed), params_file=params_file)


@app.command()
def evaluate(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Score the holdout: metrics, calibration, importance, cost curve."""
    evaluate_core(load_config(params_file, n, seed))


@app.command("build-serving")
def build_serving(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> Path:
    """Build the showcase-API serving artifact (loads pickles; no retraining)."""
    return build_serving_artifact(load_config(params_file, n, seed))


@app.command("demo-payload")
def demo_payload(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> Path:
    """Build the churn-sandbox demo payload (loads pickles; no retraining)."""
    return write_demo_payload(load_config(params_file, n, seed))


@app.command("all")
def run_all(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Run the full pipeline: prepare → train → evaluate."""
    cfg = load_config(params_file, n, seed)
    prepare_core(cfg)
    train_core(cfg, params_file=params_file)
    evaluate_core(cfg)


if __name__ == "__main__":
    app()
