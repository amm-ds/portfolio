"""Typer CLI: prepare → train → evaluate → all.

Each command is a thin wrapper around a core function so ``all`` can chain
them in-process (fast, single interpreter for the full pipeline).
"""

import json
import pickle
from datetime import date
from pathlib import Path
from typing import Annotated, Any, cast

import pandas as pd  # type: ignore[import-untyped]
import polars as pl
import typer
import yaml  # type: ignore[import-untyped]
from portfolio_core import synthetic
from portfolio_core.dq import DQReport
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json
from portfolio_core.schemas import DatasetContract
from portfolio_eval.report import ReportBuilder

from churn_pipeline.config import ChurnConfig
from churn_pipeline.eda import eda_churn_profile_figure
from churn_pipeline.evaluate import artifact_paths, evaluate_holdout
from churn_pipeline.model import (
    CATEGORICAL_COLS,
    NUMERIC_COLS,
    TARGET_COL,
    split_holdout,
    train_model,
)

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


def run_dq_gates(df: pl.DataFrame) -> DQReport:
    """Enforce the platform's data-quality gates before any modeling."""
    report = DQReport(dataset="churn_synthetic", n_rows=df.height)
    for col, cap in (("age", 0.05), ("support_calls", 0.05)):
        report.check_null_rate(col, _missing_rate(df, col), cap)

    def minmax(col: str) -> tuple[float, float]:
        """Missing/NaN-safe min/max: an all-missing column fails range cleanly."""
        s = df[col].drop_nulls()
        if s.dtype in _FLOAT_DTYPES:
            s = s.filter(~s.is_nan())
        if s.len() == 0:
            return float("nan"), float("nan")
        return float(cast(float, s.min())), float(cast(float, s.max()))

    report.check_range("age", *minmax("age"), 18.0, 90.0)
    report.check_range("tenure_months", *minmax("tenure_months"), 0.0, 240.0)
    report.check_range("monthly_charges", *minmax("monthly_charges"), 0.0, 10_000.0)
    report.check_range("churned", *minmax("churned"), 0.0, 1.0)
    report.raise_if_failed()
    return report


def prepare_core(cfg: ChurnConfig) -> Path:
    """Generate messy synthetic churn, gate it with DQ checks, persist artifacts."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)

    df = synthetic.churn(seed=cfg.seed, n=cfg.n_samples)
    report = run_dq_gates(df)

    (cfg.reports_dir / "dq_report.md").write_text(report.to_markdown())
    contract = DatasetContract(
        name="churn_synthetic",
        source="synthetic://portfolio_core.synthetic.churn",
        license="MIT",
        snapshot_date=date.today(),
        checksum_sha256=synthetic.checksum_of_frame(df),
        n_rows=df.height,
    )
    (cfg.data_dir / "dataset_contract.json").write_text(contract.model_dump_json(indent=2))

    out = cfg.data_dir / "churn.parquet"
    df.write_parquet(out)
    log.info(
        "prepare: %d rows, churn rate %.3f, %d/%d DQ checks passed",
        df.height,
        df["churned"].mean(),
        len(report.checks) - report.n_failed,
        len(report.checks),
    )

    eda_fig = eda_churn_profile_figure(df)
    save_html(eda_fig, cfg.reports_dir / "figures" / "eda_churn_profile.html")
    save_json(eda_fig, cfg.reports_dir / "figures" / "eda_churn_profile.json")
    log.info("prepare: EDA figure → reports/figures/eda_churn_profile.{html,json}")
    return out


def train_core(cfg: ChurnConfig) -> Path:
    """Stratified 80/20 split + GridSearchCV over C; persist model + holdout."""
    df = pl.read_parquet(cfg.data_dir / "churn.parquet").to_pandas()
    X_train, X_test, y_train, y_test = split_holdout(cfg, df)

    grid = train_model(cfg, X_train, y_train)
    best = float(grid.best_score_)
    log.info("train: best C=%s (cv f1=%.4f)", grid.best_params_["clf__C"], best)

    model_path, holdout_path = artifact_paths(cfg)
    with model_path.open("wb") as fh:
        pickle.dump(grid.best_estimator_, fh)
    holdout = X_test.copy()
    holdout[TARGET_COL] = y_test.to_numpy()
    pd.DataFrame(holdout).to_parquet(holdout_path)

    meta = {
        "best_params": {k: float(v) for k, v in grid.best_params_.items()},
        "cv_f1": best,
        "n_train": len(X_train),
        "n_holdout": len(X_test),
        "train_churn_rate": float(y_train.mean()),
    }
    (cfg.data_dir / "model_meta.json").write_text(json.dumps(meta, indent=2))
    return model_path


def evaluate_core(cfg: ChurnConfig) -> Path:
    """Holdout metrics + figures + HTML report; JSON figures for the showcase API."""
    model_path, holdout_path = artifact_paths(cfg)
    with model_path.open("rb") as fh:
        model = pickle.load(fh)
    holdout = pd.read_parquet(holdout_path)
    X_test = holdout[NUMERIC_COLS + CATEGORICAL_COLS]
    y_test = holdout[TARGET_COL].astype(int)
    meta = json.loads((cfg.data_dir / "model_meta.json").read_text())

    runs, figures, optimal = evaluate_holdout(
        cfg, model, X_test, y_test, train_base_rate=float(meta["train_churn_rate"])
    )

    builder = ReportBuilder(
        title="Churn Modeling — Holdout Evaluation", figures_dir=cfg.reports_dir / "figures"
    )
    for run in runs:
        builder.add_run(run)
    builder.build(cfg.reports_dir, figures=figures)
    for name, fig in figures.items():
        save_json(fig, cfg.reports_dir / "figures" / f"{name}.json")

    naive = runs[0].get("business_cost")
    tuned = runs[2].get("business_cost")
    log.info(
        "evaluate: optimal threshold %.3f, business cost %.0f (naive %.0f) vs t=0.5",
        optimal,
        tuned.value if tuned else float("nan"),
        naive.value if naive else float("nan"),
    )
    return cfg.reports_dir / "report.html"


@app.command()
def prepare(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Generate synthetic churn data and run DQ gates."""
    prepare_core(load_config(params_file, n, seed))


@app.command()
def train(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Train the pipeline with grid-searched C on a stratified split."""
    train_core(load_config(params_file, n, seed))


@app.command()
def evaluate(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Score the holdout: metrics, calibration, importance, cost curve."""
    evaluate_core(load_config(params_file, n, seed))


@app.command("all")
def run_all(
    n: OptN = None,
    seed: OptSeed = None,
    params_file: OptParams = Path("params.yaml"),
) -> None:
    """Run the full pipeline: prepare → train → evaluate."""
    cfg = load_config(params_file, n, seed)
    prepare_core(cfg)
    train_core(cfg)
    evaluate_core(cfg)


if __name__ == "__main__":
    app()
