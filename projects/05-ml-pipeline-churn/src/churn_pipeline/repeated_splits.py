"""Repeated stratified splits: split-to-split uncertainty of the frozen policy.

The committed headline comes from ONE seed-42 split, and its paired bootstrap
CI isolates row-sampling noise at fixed thresholds. This side analysis re-runs
the frozen production config (``params.yaml``: XGBoost + isotonic calibration
+ stratified 3-fold OOF threshold selection) over N fresh stratified splits.
Each split re-selects the decision threshold from its own OOF predictions, so
the cost-delta spread includes threshold-selection uncertainty — the component
the bootstrap explicitly does not measure.

Reproduction gate (STOP condition): before any new split is priced, the
committed seed-42 split is re-run through the same code path and must match
``reports/metrics.json`` (calibrated cost, contact-everyone cost) within
``COST_TOLERANCE`` and ``data/operating_policy.json`` (calibrated threshold)
exactly. On mismatch ``ReproductionMismatchError`` aborts the run and nothing
is written.

Side analysis only: the single output is ``reports/repeated_splits.json``
(plus a re-render of the ``bootstrap_ci`` figure carrying the per-split strip;
existing traces are untouched). Committed metrics, models, and serving
artifacts are never written. Like ``sensitivity``, this command lives outside
the DVC graph; re-run it after any full pipeline refresh to restore the strip.
"""

import hashlib
import json
import pickle
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from numpy.typing import NDArray
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split

from churn_pipeline.config import ChurnConfig, pd, threadpool_limits
from churn_pipeline.evaluate import (
    DEFAULT_THRESHOLD,
    artifact_paths,
    bootstrap_ci_figure,
    business_cost,
    cost_curve,
    paired_bootstrap_cost_delta,
)
from churn_pipeline.hpo import build_estimator
from churn_pipeline.model import TARGET_COL, feature_cols, slice_cols, split_holdout

log = get_logger(__name__)

DEFAULT_N_SPLITS = 20
DEFAULT_BASE_SEED = 1000
COST_TOLERANCE = 0.5
M2M_CONTRACT = "month-to-month"


class ReproductionMismatchError(RuntimeError):
    """The seed-42 rerun failed to reproduce the committed headline numbers."""


def run_one_split(cfg: ChurnConfig, df: pd.DataFrame, seed: int) -> dict[str, Any]:
    """Price one fresh stratified split of the frozen pipeline config.

    Mirrors the frozen-config path of ``train_core`` (calibration carve-out,
    isotonic fit, 3-fold OOF threshold selection) without persisting artifacts
    or running the arms that do not affect the served policy (the logreg grid
    and the raw selected model consume no shared randomness). The holdout is
    scored once: calibrated policy at its OOF-frozen threshold, the fixed
    contact-everyone baseline, and the month-to-month contact rule.
    """
    split_cfg = cfg.model_copy(update={"seed": seed})
    X_train, X_test, y_train, y_test = split_holdout(split_cfg, df)
    # the calibrator refits inside CalibratedClassifierCV; the fit-only part
    # of the calibration carve-out is unused here (it trained the raw model)
    _X_fit, X_calib, _y_fit, y_calib = train_test_split(
        X_train,
        y_train,
        test_size=split_cfg.calib_frac,
        stratify=y_train,
        random_state=split_cfg.seed,
    )
    y_train_arr = np.asarray(y_train, dtype=int)
    y_test_arr = np.asarray(y_test, dtype=int)
    with threadpool_limits(limits=1):
        calibrated = CalibratedClassifierCV(
            estimator=build_estimator(
                split_cfg, split_cfg.model_family, dict(split_cfg.model_params)
            ),
            method="isotonic",
            cv=2,
        )
        calibrated.fit(X_calib, y_calib)
        cv = StratifiedKFold(n_splits=split_cfg.cv_folds, shuffle=True, random_state=split_cfg.seed)
        oof = cross_val_predict(
            CalibratedClassifierCV(
                estimator=build_estimator(
                    split_cfg, split_cfg.model_family, dict(split_cfg.model_params)
                ),
                method="isotonic",
                cv=2,
            ),
            X_train,
            y_train,
            cv=cv,
            method="predict_proba",
            n_jobs=1,
        )
    _costs, threshold = cost_curve(split_cfg, y_train_arr, np.asarray(oof[:, 1], dtype=float))
    proba = np.asarray(calibrated.predict_proba(X_test)[:, 1], dtype=float)
    calibrated_cost = business_cost(
        y_test_arr, proba, threshold, split_cfg.fp_cost, split_cfg.fn_cost
    )
    # Fixed contact-everyone baseline, same as evaluate.naive_majority_run.
    naive_cost = business_cost(
        y_test_arr,
        np.full(len(y_test_arr), float(y_train_arr.mean()), dtype=float),
        0.0,
        split_cfg.fp_cost,
        split_cfg.fn_cost,
    )
    # Rule baseline: contact exactly the month-to-month customers.
    rule_pred = (X_test["contract"].astype(str) == M2M_CONTRACT).to_numpy()
    rule_cost = business_cost(
        y_test_arr, rule_pred.astype(float), 0.5, split_cfg.fp_cost, split_cfg.fn_cost
    )
    return {
        "seed": seed,
        "n_train": len(X_train),
        "n_holdout": len(X_test),
        "holdout_churners": int(y_test_arr.sum()),
        "calibrated_opt": float(threshold),
        "calibrated_cost": float(calibrated_cost),
        "naive_cost": float(naive_cost),
        "cost_delta": float(calibrated_cost - naive_cost),
        "month_to_month_rule": {
            "cost": float(rule_cost),
            "n_contacted": int(rule_pred.sum()),
            "contacted_churners": int((rule_pred & (y_test_arr == 1)).sum()),
            "delta_vs_contact_everyone": float(rule_cost - naive_cost),
        },
    }


def reproduce_committed_split(cfg: ChurnConfig, df: pd.DataFrame) -> dict[str, Any]:
    """Re-run the committed seed-42 split and compare against committed numbers.

    Committed sources: ``reports/metrics.json`` (calibrated and
    contact-everyone business cost) and ``data/operating_policy.json``
    (calibrated threshold). Costs must match within ``COST_TOLERANCE``; the
    threshold must match exactly.
    """
    result = run_one_split(cfg, df, cfg.seed)
    metrics = json.loads((cfg.reports_dir / "metrics.json").read_text())
    policy = json.loads(artifact_paths(cfg)["operating_policy"].read_text())
    committed = {
        "calibrated_cost": float(metrics["selected_model_calibrated"]["business_cost"]),
        "naive_cost": float(metrics["naive_majority"]["business_cost"]),
        "calibrated_opt": float(policy["thresholds"]["selected_calibrated"]),
    }
    reproduced = {key: float(result[key]) for key in committed}
    matches = (
        abs(reproduced["calibrated_cost"] - committed["calibrated_cost"]) <= COST_TOLERANCE
        and abs(reproduced["naive_cost"] - committed["naive_cost"]) <= COST_TOLERANCE
        and reproduced["calibrated_opt"] == committed["calibrated_opt"]
    )
    return {
        "seed": cfg.seed,
        "committed": committed,
        "reproduced": reproduced,
        "cost_tolerance": COST_TOLERANCE,
        "threshold_match": "exact",
        "matches_committed": bool(matches),
    }


def _spread(values: NDArray[np.float64]) -> dict[str, float]:
    """Median, 2.5/97.5 percentiles (numpy linear), min and max."""
    lo, hi = np.percentile(values, [2.5, 97.5])
    return {
        "median": float(np.median(values)),
        "p2_5": float(lo),
        "p97_5": float(hi),
        "min": float(values.min()),
        "max": float(values.max()),
    }


def summarize(splits: list[dict[str, Any]]) -> dict[str, Any]:
    """Cross-split summary: cost delta, chosen thresholds, rule pricing."""
    deltas = np.asarray([s["cost_delta"] for s in splits], dtype=float)
    thresholds = [float(s["calibrated_opt"]) for s in splits]
    rule_costs = np.asarray([s["month_to_month_rule"]["cost"] for s in splits], dtype=float)
    rule_deltas = np.asarray(
        [s["month_to_month_rule"]["delta_vs_contact_everyone"] for s in splits], dtype=float
    )
    return {
        "cost_delta": {**_spread(deltas), "all_below_zero": bool((deltas < 0).all())},
        "calibrated_opt": {
            "median": float(np.median(thresholds)),
            "min": float(min(thresholds)),
            "max": float(max(thresholds)),
            "n_distinct": len(set(thresholds)),
        },
        "month_to_month_rule_cost": _spread(rule_costs),
        "month_to_month_rule_delta_vs_contact_everyone": _spread(rule_deltas),
        "percentile_method": "numpy.percentile (linear) over the per-split values",
    }


def refresh_bootstrap_figure(cfg: ChurnConfig, split_deltas: list[float]) -> Path:
    """Re-render ``bootstrap_ci`` with the repeated-splits strip.

    Rebuilds the committed figure from the persisted artifacts (the seeded
    bootstrap reproduces the committed resample distribution bit-for-bit) and
    appends the per-split strip; the committed traces are not altered. This is
    the same render ``evaluate_core`` produces when ``repeated_splits.json``
    is present, so both regeneration paths stay in sync.
    """
    paths = artifact_paths(cfg)
    with paths["selected_calibrated"].open("rb") as fh:
        model = pickle.load(fh)  # noqa: S301 - serving artifact persisted by this pipeline
    holdout = pd.read_parquet(paths["holdout"])
    X_test = holdout[list(dict.fromkeys(feature_cols(cfg) + slice_cols(cfg)))]
    y_test = np.asarray(holdout[TARGET_COL].astype(int), dtype=int)
    policy = json.loads(paths["operating_policy"].read_text())
    proba = np.asarray(model.predict_proba(X_test)[:, 1], dtype=float)
    delta = paired_bootstrap_cost_delta(
        cfg,
        y_test,
        proba,
        np.ones(len(y_test), dtype=float),
        float(policy["thresholds"]["selected_calibrated"]),
        DEFAULT_THRESHOLD,
    )
    fig = bootstrap_ci_figure(
        delta, "calibrated model", "contact everyone", split_deltas=split_deltas
    )
    out = save_json(fig, cfg.reports_dir / "figures" / "bootstrap_ci.json")
    save_html(fig, cfg.reports_dir / "figures" / "bootstrap_ci.html")
    return out


def _git_head() -> str | None:
    """HEAD sha for provenance (read-only); None outside a git worktree."""
    proc = subprocess.run(
        ["/usr/bin/env", "git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def repeated_splits_core(
    cfg: ChurnConfig,
    n_splits: int = DEFAULT_N_SPLITS,
    base_seed: int = DEFAULT_BASE_SEED,
    params_file: Path = Path("params.yaml"),
) -> Path:
    """Run the reproduction gate, then N repeated splits; write the JSON report.

    Aborts before writing anything when the committed seed-42 split does not
    reproduce (STOP condition). Seeds are ``base_seed + i`` so the committed
    seed 42 stays the headline split and the replication seeds are disjoint
    from it.
    """
    if cfg.model_family == "auto":
        raise ValueError(
            "repeated-splits prices the frozen production config; "
            "params.yaml still has model_family: auto (run train first)"
        )
    df = pl.read_parquet(cfg.data_dir / "churn.parquet").to_pandas()

    reproduction = reproduce_committed_split(cfg, df)
    log.info(
        "repeated-splits: reproduction seed %d -> %s (committed %s)",
        cfg.seed,
        reproduction["reproduced"],
        reproduction["committed"],
    )
    if not reproduction["matches_committed"]:
        raise ReproductionMismatchError(
            "seed-42 rerun does not reproduce the committed split: "
            f"reproduced {reproduction['reproduced']} vs committed "
            f"{reproduction['committed']} (cost tolerance ±{COST_TOLERANCE}, "
            "threshold exact) — STOP, do not run the repeated splits"
        )

    seeds = [base_seed + i for i in range(n_splits)]
    splits = []
    for seed in seeds:
        split = run_one_split(cfg, df, seed)
        splits.append(split)
        log.info(
            "repeated-splits: seed %d t*=%.3f calibrated=%.0f naive=%.0f delta=%.0f rule=%.0f",
            seed,
            split["calibrated_opt"],
            split["calibrated_cost"],
            split["naive_cost"],
            split["cost_delta"],
            split["month_to_month_rule"]["cost"],
        )

    out: dict[str, Any] = {
        "schema_version": 1,
        "note": (
            "Repeated stratified splits of the frozen production config "
            "(params.yaml): each split re-fits the selected model with isotonic "
            "calibration on its own training rows and re-selects the decision "
            "threshold from its own stratified 3-fold OOF predictions before one "
            "holdout scoring, so the cost-delta spread includes "
            "threshold-selection uncertainty (the committed paired bootstrap "
            "holds thresholds fixed and does not). The reproduction block "
            "re-runs the committed seed-42 split first and must match "
            "reports/metrics.json and data/operating_policy.json before any new "
            "split is priced. Side analysis only: metrics.json and the served "
            "artifacts are untouched."
        ),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_sha": _git_head(),
        "config": {
            "params_file": params_file.name,
            "params_sha256": hashlib.sha256(params_file.read_bytes()).hexdigest()
            if params_file.is_file()
            else None,
            "data_source": cfg.data_source,
            "model_family": cfg.model_family,
            "model_params": {k: float(v) for k, v in cfg.model_params.items()},
            "test_frac": cfg.test_frac,
            "calib_frac": cfg.calib_frac,
            "cv_folds": cfg.cv_folds,
            "fp_cost": cfg.fp_cost,
            "fn_cost": cfg.fn_cost,
            "threshold_grid_points": len(cfg.threshold_grid),
            "n_rows": len(df),
        },
        "reproduction": reproduction,
        "n_splits": n_splits,
        "seeds": seeds,
        "splits": splits,
        "summary": summarize(splits),
    }
    out_path = cfg.reports_dir / "repeated_splits.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    log.info("repeated-splits: wrote %s (%d splits)", out_path, n_splits)
    refresh_bootstrap_figure(cfg, [float(s["cost_delta"]) for s in splits])
    log.info("repeated-splits: bootstrap_ci figure re-rendered with the split strip")
    return out_path
