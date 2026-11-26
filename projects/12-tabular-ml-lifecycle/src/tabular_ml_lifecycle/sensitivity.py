"""Sensitivity arm for the v1 pruning and lag defects (pass-3 P1.2 / E4).

The v1 run carried two disclosed feature defects: correlated-pair pruning
dropped ``atemp`` (the higher-MI member of the ``temp``/``atemp`` pair), and
lags were positional shifts that drift across the series' 165 missing hours.
Pass 5 promoted the corrected recipe to v2 (option B); v1 is preserved under
``metrics.json previous_runs.v1`` and ``params_v1.yaml``, and this arm remains
the reproducible record of the comparison. It prices both defects without
touching any committed artifact:

1. **Reproduction gate (STOP condition).** The v1 recipe (``params_v1.yaml``)
   is re-derived in memory and its MLP test MAE must match the v1 record
   within ``REPRODUCTION_TOLERANCE`` — the same gate pattern project 13's
   train stage enforces before serving. A failure aborts the arm; nothing is
   written.
2. **Corrected variant.** The same ladder runs with ``params_variant.yaml``
   (= the committed v2 recipe): pruning keeps the higher-MI member, and lags
   join on ``timestamp - h`` with NaN for missing hours. NaN-lag rows are
   dropped from train/validation; the frozen test window keeps all 1,344 rows,
   with NaN lag cells median-imputed from the training window (counts
   disclosed in the artifact).
3. **Delta pricing.** Per-model paired block-bootstrap CIs of
   ``MAE(variant) - MAE(committed v1)`` on the same test hours (negative
   favors the variant), plus hourly/week-block sensitivity rows for the MLP.

The only outputs are ``reports/sensitivity_pruning_lags.json`` and the
``sensitivity_pruning_lags`` figure — the committed ``metrics.json`` is never
written by this stage.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from portfolio_core.logging import get_logger
from portfolio_core.plotting import save_html, save_json

from tabular_ml_lifecycle import figures
from tabular_ml_lifecycle.config import LifecycleConfig
from tabular_ml_lifecycle.data import TARGET_COL, TIMESTAMP_COL, split_windows
from tabular_ml_lifecycle.features import (
    apply_nan_lag_policy,
    apply_split,
    build_features,
    seasonal_naive_predict_mode,
    select_features,
)
from tabular_ml_lifecycle.metrics import (
    mae,
    paired_block_bootstrap_deltas,
    paired_bootstrap_deltas,
)
from tabular_ml_lifecycle.mlp import MLPRegressor
from tabular_ml_lifecycle.models import (
    rf_estimator,
    ridge_estimator,
    run_hpo,
    train_lgbm_final,
)

log = get_logger(__name__)

#: STOP-condition tolerance for the reproduction gate (pass-3 P1.2).
REPRODUCTION_TOLERANCE = 1e-4

#: Bootstrap seeds are offset from the committed evaluate stage's streams
#: (seed .. seed+3) so the delta resamples are an independent comparison.
SEED_OFFSET_DAY = 4
SEED_OFFSET_HOURLY = 5
SEED_OFFSET_WEEK = 6

MODEL_ORDER = ["seasonal_naive", "ridge", "random_forest", "lightgbm_hpo", "mlp"]


class ReproductionError(RuntimeError):
    """The re-derived committed recipe does not reproduce the committed MLP MAE."""


@dataclass
class ArmResult:
    """One in-memory ladder run (committed recipe or corrected variant)."""

    selected: list[str]
    pruned_pairs: list[dict[str, Any]]
    val_mae: dict[str, float]
    test_mae: dict[str, float]
    test_preds: dict[str, np.ndarray]
    y_test: np.ndarray
    nan_handling: dict[str, int] = field(default_factory=dict)


def run_ladder_arm(cfg: LifecycleConfig) -> ArmResult:
    """Run the full ladder in memory for one config; no artifacts are written.

    Mirrors ``features_core`` + the fitting half of ``train_core`` exactly
    (same seeds, same selection, same estimators, same NaN policy and floor
    helpers), minus figures, learning curves and ablations, which do not feed
    the test scores.
    """
    frame_path = cfg.data_dir / "hour.parquet"
    if not frame_path.exists():
        raise FileNotFoundError(
            f"{frame_path} missing — run the prepare stage first (the sensitivity "
            "arm reads the committed prepared frame, it does not fetch)."
        )
    df = pd.read_parquet(frame_path)
    windows = split_windows(len(df), cfg.val_weeks, cfg.test_weeks)
    featured = build_features(df, cfg.lag_hours, cfg.lag_mode)
    train, val, test = apply_split(featured, windows, cfg.max_lag)
    train, val, test, nan_handling = apply_nan_lag_policy(
        train, val, test, cfg.lag_hours, cfg.lag_mode
    )

    selection = select_features(cfg, train, val, windows)
    selected = selection.selected
    X_train, y_train = train[selected], train[TARGET_COL].astype(float)
    X_val, y_val = val[selected], val[TARGET_COL].astype(float)
    y_test = test[TARGET_COL].astype(float).to_numpy()

    floor_pred, floor_imputed = seasonal_naive_predict_mode(
        df, train, test[TIMESTAMP_COL], 168, cfg.lag_mode
    )
    nan_handling["floor_test_points_median_imputed"] = floor_imputed
    test_preds: dict[str, np.ndarray] = {"seasonal_naive": floor_pred}
    val_floor, _ = seasonal_naive_predict_mode(df, train, val[TIMESTAMP_COL], 168, cfg.lag_mode)
    val_mae: dict[str, float] = {"seasonal_naive": mae(y_val.to_numpy(), val_floor)}

    ridge = ridge_estimator(cfg, selected).fit(X_train, y_train)
    test_preds["ridge"] = np.asarray(ridge.predict(test[selected]), dtype=float)
    val_mae["ridge"] = mae(y_val.to_numpy(), np.asarray(ridge.predict(X_val), dtype=float))

    rf = rf_estimator(cfg, cfg.seed, selected).fit(X_train, y_train)
    test_preds["random_forest"] = np.asarray(rf.predict(test[selected]), dtype=float)
    val_mae["random_forest"] = mae(y_val.to_numpy(), np.asarray(rf.predict(X_val), dtype=float))

    hpo = run_hpo(cfg, X_train, y_train, X_val, y_val)
    lgbm = train_lgbm_final(cfg, X_train, y_train, X_val, y_val, hpo.best_params)
    test_preds["lightgbm_hpo"] = np.asarray(lgbm.predict(test[selected]), dtype=float)
    val_mae["lightgbm_hpo"] = mae(y_val.to_numpy(), np.asarray(lgbm.predict(X_val), dtype=float))

    mlp_cols = ["hour", *selected]  # raw hour feeds the embedding; never a candidate feature
    mlp = MLPRegressor(cfg, cfg.seed)
    mlp.fit(train[mlp_cols], y_train, val[mlp_cols], y_val, selected)
    test_preds["mlp"] = np.asarray(mlp.predict(test[mlp_cols]), dtype=float)
    val_mae["mlp"] = mae(y_val.to_numpy(), np.asarray(mlp.predict(val[mlp_cols]), dtype=float))

    test_mae = {name: mae(y_test, pred) for name, pred in test_preds.items()}
    log.info(
        "arm (%s/%s): test MAE floor=%.2f ridge=%.2f rf=%.2f lgbm=%.2f mlp=%.4f",
        cfg.lag_mode,
        cfg.pruning_rule,
        test_mae["seasonal_naive"],
        test_mae["ridge"],
        test_mae["random_forest"],
        test_mae["lightgbm_hpo"],
        test_mae["mlp"],
    )
    return ArmResult(
        selected=selected,
        pruned_pairs=selection.pruned_pairs,
        val_mae=val_mae,
        test_mae=test_mae,
        test_preds=test_preds,
        y_test=y_test,
        nan_handling=nan_handling,
    )


def run_sensitivity(
    cfg: LifecycleConfig,
    variant_cfg: LifecycleConfig,
    *,
    expected_mae: float | None = None,
    out_path: Path | None = None,
) -> Path:
    """Reproduce the committed v1 run, score the corrected variant, price the delta.

    ``expected_mae`` defaults to the v1 MLP MAE — read from
    ``metrics.json previous_runs.v1`` when present (post-promotion), else from
    the top-level ``mlp`` block; tests pass it explicitly. Writes only
    ``reports/sensitivity_pruning_lags.json`` and the matching figure —
    committed artifacts are never modified.
    """
    started = time.perf_counter()
    committed_metrics = json.loads((cfg.reports_dir / "metrics.json").read_text())
    # Post-promotion the committed metrics.json carries v2 at the top level and
    # the v1 run under previous_runs.v1; the E4 arm's baseline is v1.
    v1_metrics = committed_metrics.get("previous_runs", {}).get("v1", committed_metrics)
    expected = float(expected_mae) if expected_mae is not None else float(v1_metrics["mlp"]["mae"])
    committed_test_mae = {
        name: float(v1_metrics[name]["mae"]) for name in MODEL_ORDER if name in v1_metrics
    }

    # Gate 1 — reproduction of the committed run (STOP condition). Same
    # pattern as project 13's train-stage reproduction gate.
    baseline = run_ladder_arm(cfg)
    abs_diff = abs(baseline.test_mae["mlp"] - expected)
    reproduction = {
        "expected_test_mae": expected,
        "derived_test_mae": baseline.test_mae["mlp"],
        "abs_diff": abs_diff,
        "tolerance": REPRODUCTION_TOLERANCE,
        "passed": abs_diff <= REPRODUCTION_TOLERANCE,
        "pattern": "projects/13-model-serving train-stage reproduction gate",
    }
    if not reproduction["passed"]:
        raise ReproductionError(
            f"committed-run reproduction failed: derived {baseline.test_mae['mlp']:.6f} vs "
            f"expected {expected:.6f} (tolerance {REPRODUCTION_TOLERANCE}) — STOP, "
            "do not score the variant against a pipeline that no longer reproduces."
        )

    variant = run_ladder_arm(variant_cfg)

    # Gate 2 — the delta, per model: MAE(variant) - MAE(committed) on the same
    # test hours; negative favors the variant. Day blocks are the primary CI
    # (the committed run's serial-dependence sensitivity unit).
    delta_day: dict[str, dict[str, Any]] = {}
    for name in MODEL_ORDER:
        ci, _ = paired_block_bootstrap_deltas(
            baseline.y_test,
            baseline.test_preds[name],
            variant.test_preds[name],
            cfg.bootstrap_resamples,
            cfg.seed + SEED_OFFSET_DAY,
            block_size=24,
        )
        delta_day[name] = {"block_hours": 24, "seed": cfg.seed + SEED_OFFSET_DAY, **ci.to_dict()}
    mlp_hourly, _ = paired_bootstrap_deltas(
        baseline.y_test,
        baseline.test_preds["mlp"],
        variant.test_preds["mlp"],
        cfg.bootstrap_resamples,
        cfg.seed + SEED_OFFSET_HOURLY,
    )
    mlp_week, _ = paired_block_bootstrap_deltas(
        baseline.y_test,
        baseline.test_preds["mlp"],
        variant.test_preds["mlp"],
        cfg.bootstrap_resamples,
        cfg.seed + SEED_OFFSET_WEEK,
        block_size=168,
    )

    mlp_ci = delta_day["mlp"]
    honest_triggered = bool(mlp_ci["hi"] < 0.0)
    if honest_triggered:
        outcome = "variant_better"
    elif mlp_ci["lo"] > 0.0:
        outcome = "variant_worse"
    else:
        outcome = "no_measurable_difference"
    honest_note = {
        "condition": (
            "the variant beats the committed served model by more than its CI: "
            "the day-block CI of MAE(variant) - MAE(committed MLP) lies entirely "
            "below zero"
        ),
        "triggered": honest_triggered,
        "outcome": outcome,
        "defect_worth_mae": -float(mlp_ci["point"]) if honest_triggered else None,
        "required_wording": (
            "the committed headline carries a known defect worth X MAE"
            if honest_triggered
            else None
        ),
    }

    payload: dict[str, Any] = {
        "artifact": "sensitivity_pruning_lags",
        "generated_by": (
            "uv run python -m tabular_ml_lifecycle.cli sensitivity "
            "--params-file params_v1.yaml --variant-params-file params_variant.yaml"
        ),
        "question": (
            "What do the v1 pruning defect (drops atemp, the higher-MI member "
            "of the temp/atemp pair) and the positional-lag defect (lags drift across "
            "the 165 missing hours) cost the frozen test scores?"
        ),
        "seed": cfg.seed,
        "n_boot": cfg.bootstrap_resamples,
        "test_window_rows": len(baseline.y_test),
        "reproduction": reproduction,
        "committed": {
            "source": (
                "reports/metrics.json v1 blocks (previous_runs.v1 post-promotion; "
                "re-derived in memory for the paired delta)"
            ),
            "test_mae": committed_test_mae,
            "rederived_test_mae": baseline.test_mae,
            "rederived_max_abs_diff": max(
                abs(baseline.test_mae[name] - committed_test_mae[name])
                for name in committed_test_mae
            ),
        },
        "variant": {
            "params_file": "params_variant.yaml",
            "changes": [
                "correlated-pair pruning keeps the higher-MI member of a pair "
                "(pruning_rule: keep_higher_mi)",
                "lags join on timestamp minus h with NaN for missing hours "
                "(lag_mode: timestamp), instead of positional shifts",
            ],
            "selected_features": variant.selected,
            "pruned_pairs": variant.pruned_pairs,
            "nan_handling": {
                **variant.nan_handling,
                "rule": (
                    "NaN-lag rows are dropped from train/validation (complete-case); "
                    "the frozen 1,344-row test window is kept, and NaN lag cells are "
                    "median-imputed from the training window so every model — and the "
                    "paired delta — sees identical test hours."
                ),
            },
            "val_mae": variant.val_mae,
            "test_mae": variant.test_mae,
        },
        "delta_variant_minus_committed": {
            "metric": "MAE(variant) - MAE(committed), paired on the same test hours",
            "negative_favors": "variant",
            "day_block": delta_day,
            "mlp_sensitivity": {
                "hourly": {"seed": cfg.seed + SEED_OFFSET_HOURLY, **mlp_hourly.to_dict()},
                "week": {
                    "block_hours": 168,
                    "seed": cfg.seed + SEED_OFFSET_WEEK,
                    **mlp_week.to_dict(),
                },
            },
        },
        "honest_note": honest_note,
        "runtime_s": round(time.perf_counter() - started, 3),
    }

    out = out_path or cfg.reports_dir / "sensitivity_pruning_lags.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")

    fig = figures.sensitivity_pruning_lags_figure(payload)
    save_html(fig, cfg.reports_dir / "figures" / "sensitivity_pruning_lags.html")
    save_json(fig, cfg.reports_dir / "figures" / "sensitivity_pruning_lags.json")
    log.info(
        "sensitivity: reproduction |Δ|=%.2e | variant MLP MAE %.4f vs committed %.4f "
        "(day-block CI [%.4f, %.4f]) | honest note triggered=%s -> %s",
        abs_diff,
        variant.test_mae["mlp"],
        baseline.test_mae["mlp"],
        mlp_ci["lo"],
        mlp_ci["hi"],
        honest_triggered,
        out,
    )
    return out
