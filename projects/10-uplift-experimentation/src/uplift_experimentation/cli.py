"""Typer CLI: prepare → train → evaluate → all.

Each command is a thin wrapper around a core function so ``all`` chains them
in-process (single interpreter for the full pipeline, minutes end-to-end).
"""

import json
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import polars as pl
import typer
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json

from uplift_experimentation.config import UpliftConfig, pd, threadpool_limits, yaml
from uplift_experimentation.data import (
    experiment_read,
    load_experiment_frame,
    load_experiment_frame_multi,
    segment_summary,
    write_contract,
)
from uplift_experimentation.demo_payload import write_demo_payload
from uplift_experimentation.eda import eda_segment_profile_figure
from uplift_experimentation.evaluate import evaluate_core
from uplift_experimentation.models import (
    cross_fit_arm_uplift,
    cross_fit_scores,
    fit_arm_uplift,
)

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

    # Three-arm frame for the secondary multi-treatment uplift read.
    multi = load_experiment_frame_multi(cfg)
    multi.write_parquet(cfg.data_dir / "hillstrom_multi.parquet")

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
        "prepare: %d rows | conversion treated %.4f control %.4f (ATE %+.5f) | "
        "multi-arm frame: %d rows",
        df.height,
        read["conv_rate_treated"],
        read["conv_rate_control"],
        read["ate"],
        multi.height,
    )
    return out


def fit_per_arm_scores(
    cfg: UpliftConfig, multi: pd.DataFrame, feature_cols: list[str]
) -> dict[str, np.ndarray]:
    """Cross-fitted per-arm T-learner uplift scores on the three-arm frame.

    Each arm is fit against the shared control on the arm/control pair
    (out-of-fold); the third arm's rows are scored by the pair model refit on
    all its rows — a deployment-style prediction for unseen customers, never an
    in-sample score. Both arms reuse the binary run's seed stream: for the arm
    matching ``cfg.treatment_segment`` the pair IS the two-arm frame, so its
    scores reproduce the committed T-learner exactly (continuity by
    construction, not a fresh draw); the other arm is the same machinery on
    its own pair. Deterministic under ``cfg.seed``.
    """
    y = multi["conversion"].to_numpy(dtype=int)
    results: dict[str, np.ndarray] = {}
    for arm, seg_name, tcol, refit_offset in (
        ("uplift_mens", "Mens E-Mail", "treated_mens", 500),
        ("uplift_womens", "Womens E-Mail", "treated_womens", 501),
    ):
        pair_mask = multi["segment"].isin([seg_name, cfg.control_segment]).to_numpy()
        x_pair = multi.loc[pair_mask, feature_cols]
        t_pair = multi.loc[pair_mask, tcol].to_numpy(dtype=int)
        y_pair = y[pair_mask]
        oof = cross_fit_arm_uplift(x_pair, t_pair, y_pair, cfg.cv_folds, cfg.seed)
        score_rest = fit_arm_uplift(x_pair, t_pair, y_pair, cfg.seed + refit_offset)
        full = np.full(len(multi), np.nan)
        full[pair_mask] = oof
        full[~pair_mask] = score_rest(multi.loc[~pair_mask, feature_cols])
        results[arm] = full
        log.info("train: %s cross-fitted (%d folds), %d rows scored", arm, cfg.cv_folds, len(multi))
    return results


def train_core(cfg: UpliftConfig) -> Path:
    """Cross-fit out-of-fold uplift scores for every policy; persist scores.

    Fits the binary two-arm policies (response / T-learner / X-learner,
    unchanged) plus per-arm T-learner scores (``uplift_mens`` /
    ``uplift_womens``) for the multi-treatment read.
    """
    frame_path = cfg.data_dir / "hillstrom.parquet"
    multi_path = cfg.data_dir / "hillstrom_multi.parquet"
    if not frame_path.exists() or not multi_path.exists():
        raise FileNotFoundError(
            f"{frame_path} / {multi_path} missing — run the prepare stage first "
            "(uv run python -m uplift_experimentation.cli prepare)"
        )
    df = pl.read_parquet(frame_path).to_pandas()
    multi = pl.read_parquet(multi_path).to_pandas()
    feature_cols = cfg.feature_cols
    X = df[feature_cols]
    treatment = df["treatment"].to_numpy(dtype=int)
    y = df["conversion"].to_numpy(dtype=int)

    # Single-threaded fits: OpenMP oversubscription slows HistGB substantially.
    with threadpool_limits(limits=1):
        scores = cross_fit_scores(X, treatment, y, folds=cfg.cv_folds, seed=cfg.seed)
        arm_scores = fit_per_arm_scores(cfg, multi, feature_cols)

    # The two-arm frame is the Mens/control subset of the multi frame (same raw
    # row order); verify before joining per-arm scores positionally.
    two_arm_mask = multi["segment"].isin([cfg.treatment_segment, cfg.control_segment]).to_numpy()
    if int(two_arm_mask.sum()) != len(df) or not np.all(
        multi.loc[two_arm_mask, "conversion"].to_numpy() == df["conversion"].to_numpy()
    ):
        raise ValueError("two-arm frame does not align with the multi-arm subset")

    out_df = pd.concat(
        [
            df[["treatment", "conversion", "visit", "spend", "log_history", "recency"]].reset_index(
                drop=True
            ),
            scores.reset_index(drop=True),
        ],
        axis=1,
    )
    out_df["uplift_mens"] = arm_scores["uplift_mens"][two_arm_mask]
    out_df["uplift_womens"] = arm_scores["uplift_womens"][two_arm_mask]
    out = cfg.data_dir / "scores.parquet"
    out_df.to_parquet(out)

    multi_out = pd.concat(
        [
            multi[
                [
                    "segment",
                    "treated_mens",
                    "treated_womens",
                    "conversion",
                    "visit",
                    "spend",
                    "log_history",
                    "recency",
                ]
            ].reset_index(drop=True),
            pd.DataFrame(
                {
                    "uplift_mens": arm_scores["uplift_mens"],
                    "uplift_womens": arm_scores["uplift_womens"],
                }
            ),
        ],
        axis=1,
    )
    multi_out.to_parquet(cfg.data_dir / "scores_multi.parquet")
    log.info(
        "train: %d rows cross-fitted (%d folds) + per-arm scores; scores -> %s",
        len(out_df),
        cfg.cv_folds,
        out,
    )
    return out


@app.command()
def prepare(params_file: OptParams = Path("params.yaml")) -> None:
    """Fetch + gate the Hillstrom data, persist the experiment frame + EDA."""
    prepare_core(load_config(params_file))


@app.command()
def train(params_file: OptParams = Path("params.yaml")) -> None:
    """Cross-fit OOF scores: response / T-learner / X-learner + per-arm uplift."""
    train_core(load_config(params_file))


@app.command()
def evaluate(params_file: OptParams = Path("params.yaml")) -> None:
    """Qini + profit evaluation, CUPED and power reads, figures and report."""
    evaluate_core(load_config(params_file))


@app.command("demo-payload")
def demo_payload(params_file: OptParams = Path("params.yaml")) -> Path:
    """Build the uplift-simulator demo payload (loads scores; no retraining)."""
    return write_demo_payload(load_config(params_file))


@app.command("all")
def run_all(params_file: OptParams = Path("params.yaml")) -> None:
    """Run the full pipeline: prepare → train → evaluate."""
    cfg = load_config(params_file)
    prepare_core(cfg)
    train_core(cfg)
    evaluate_core(cfg)


if __name__ == "__main__":
    app()
