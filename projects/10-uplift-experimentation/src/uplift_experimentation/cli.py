"""Typer CLI: prepare → train → evaluate → all.

Each command is a thin wrapper around a core function so ``all`` chains them
in-process (single interpreter for the full pipeline, minutes end-to-end).
"""

import json
from pathlib import Path
from typing import Annotated, Any

import polars as pl
import typer
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json

from uplift_experimentation.config import UpliftConfig, pd, threadpool_limits, yaml
from uplift_experimentation.data import (
    experiment_read,
    load_experiment_frame,
    segment_summary,
    write_contract,
)
from uplift_experimentation.eda import eda_segment_profile_figure
from uplift_experimentation.evaluate import evaluate_core
from uplift_experimentation.models import cross_fit_scores

app = typer.Typer(
    help="Uplift modeling & experimentation on the Hillstrom email dataset.",
    add_completion=False,
)
log = get_logger(__name__)

OptParams = Annotated[Path, typer.Option(help="YAML file with config keys.")]


def load_config(params_file: Path = Path("params.yaml")) -> UpliftConfig:
    """Build UpliftConfig from params.yaml (if present)."""
    data: dict[str, Any] = {}
    if params_file.exists():
        data = yaml.safe_load(params_file.read_text()) or {}
        log.info("load_config: %s (%d keys)", params_file, len(data))
    return UpliftConfig(**data)


def prepare_core(cfg: UpliftConfig) -> Path:
    """Fetch (checksum-pinned), gate, persist the modeling frame + EDA artifacts."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)

    df = load_experiment_frame(cfg)
    raw_path = cfg.data_dir / "raw" / "hillstrom.csv"
    write_contract(cfg, df, raw_path)

    # EDA on all three arms (raw view, before the two-arm restriction).
    raw = pl.read_csv(raw_path, schema_overrides={"spend": pl.Float64})
    summary = segment_summary(raw)
    (cfg.reports_dir / "segment_summary.json").write_text(json.dumps(summary.to_dicts(), indent=2))
    eda_fig = eda_segment_profile_figure(raw)
    save_html(eda_fig, cfg.reports_dir / "figures" / "eda_segment_profile.html")
    save_json(eda_fig, cfg.reports_dir / "figures" / "eda_segment_profile.json")

    out = cfg.data_dir / "hillstrom.parquet"
    df.write_parquet(out)
    read = experiment_read(df)
    log.info(
        "prepare: %d rows | conversion treated %.4f control %.4f (ATE %+.5f)",
        df.height,
        read["conv_rate_treated"],
        read["conv_rate_control"],
        read["ate"],
    )
    return out


def train_core(cfg: UpliftConfig) -> Path:
    """Cross-fit out-of-fold uplift scores for every policy; persist scores."""
    frame_path = cfg.data_dir / "hillstrom.parquet"
    if not frame_path.exists():
        raise FileNotFoundError(
            f"{frame_path} missing — run the prepare stage first "
            "(uv run python -m uplift_experimentation.cli prepare)"
        )
    df = pl.read_parquet(frame_path).to_pandas()
    feature_cols = cfg.feature_cols
    X = df[feature_cols]
    treatment = df["treatment"].to_numpy(dtype=int)
    y = df["conversion"].to_numpy(dtype=int)

    # Single-threaded fits: OpenMP oversubscription slows HistGB substantially.
    with threadpool_limits(limits=1):
        scores = cross_fit_scores(X, treatment, y, folds=cfg.cv_folds, seed=cfg.seed)

    out_df = pd.concat(
        [
            df[["treatment", "conversion", "visit", "spend", "log_history"]].reset_index(drop=True),
            scores.reset_index(drop=True),
        ],
        axis=1,
    )
    out = cfg.data_dir / "scores.parquet"
    out_df.to_parquet(out)
    log.info("train: %d rows cross-fitted (%d folds), scores -> %s", len(out_df), cfg.cv_folds, out)
    return out


@app.command()
def prepare(params_file: OptParams = Path("params.yaml")) -> None:
    """Fetch + gate the Hillstrom data, persist the experiment frame + EDA."""
    prepare_core(load_config(params_file))


@app.command()
def train(params_file: OptParams = Path("params.yaml")) -> None:
    """Cross-fit out-of-fold uplift scores (response / T-learner / X-learner)."""
    train_core(load_config(params_file))


@app.command()
def evaluate(params_file: OptParams = Path("params.yaml")) -> None:
    """Qini + profit evaluation, CUPED and power reads, figures and report."""
    evaluate_core(load_config(params_file))


@app.command("all")
def run_all(params_file: OptParams = Path("params.yaml")) -> None:
    """Run the full pipeline: prepare → train → evaluate."""
    cfg = load_config(params_file)
    prepare_core(cfg)
    train_core(cfg)
    evaluate_core(cfg)


if __name__ == "__main__":
    app()
