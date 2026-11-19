"""Rolling-origin check: does the MLP-vs-LightGBM tie hold across origins?

Q4f (next round 2), compute-only. The committed validation window (the
``val_weeks`` immediately before the frozen test weeks) is sliced into one
origin per week — a diagnostic decomposition of the existing fold, not a new
fold definition and no retraining. Both committed artifacts (``lightgbm.pkl``,
``mlp.pt`` + meta) are scored per origin on the committed features.

Identity check: full-window validation MAE for each model must equal
``reports/train_runs.json → val`` before any per-origin number is trusted.

Output: NEW files under ``reports/rolling_origin/`` only.
"""

from __future__ import annotations

import json
import pickle
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
import torch
from portfolio_core.logging import get_logger

from tabular_ml_lifecycle.config import LifecycleConfig
from tabular_ml_lifecycle.data import TARGET_COL
from tabular_ml_lifecycle.metrics import mae, paired_block_bootstrap_deltas
from tabular_ml_lifecycle.mlp import MLPRegressor, RentalMLP
from tabular_ml_lifecycle.stages import _load_split

log = get_logger(__name__)

ROWS_PER_WEEK = 24 * 7


def _load_committed_models(
    cfg: LifecycleConfig, selected: list[str], df: pd.DataFrame
) -> dict[str, np.ndarray]:
    """Load the persisted champion artifacts exactly as the test stage does."""
    models_dir = cfg.data_dir / "models"
    with (models_dir / "lightgbm.pkl").open("rb") as fh:
        lgbm = pickle.load(fh)  # noqa: S301 - pipeline artifact persisted by this stage
    lgbm_pred = np.asarray(lgbm.predict(df[selected]), dtype=float)

    meta = json.loads((models_dir / "mlp_meta.json").read_text())
    numeric: list[str] = meta["numeric_cols"]
    model = RentalMLP(
        n_numeric=len(numeric),
        embed_dim=cfg.mlp.embed_dim,
        hidden_dims=list(cfg.mlp.hidden_dims),
        dropout=cfg.mlp.dropout,
    )
    model.load_state_dict(torch.load(models_dir / "mlp.pt", weights_only=True))
    regressor = MLPRegressor(cfg, cfg.seed)
    regressor.model = model
    regressor.numeric_cols = numeric
    regressor.x_mean = np.asarray(meta["x_mean"], dtype=np.float64)
    regressor.x_std = np.asarray(meta["x_std"], dtype=np.float64)
    regressor.y_mean = float(meta["y_mean"])
    regressor.y_std = float(meta["y_std"])
    mlp_pred = np.asarray(regressor.predict(df[["hour", *selected]]), dtype=float)
    return {"lightgbm_hpo": lgbm_pred, "mlp": mlp_pred}


def run_rolling_origin(cfg: LifecycleConfig) -> dict[str, Any]:
    """Score both committed models per weekly origin of the validation window."""
    train_runs = json.loads((cfg.reports_dir / "train_runs.json").read_text())
    selected: list[str] = train_runs["selected_features"]
    val_df = _load_split(cfg, "val")
    y = val_df[TARGET_COL].astype(float).to_numpy()
    preds = _load_committed_models(cfg, selected, val_df)

    committed_val = train_runs["val"]
    verification: dict[str, Any] = {}
    for name, pred in preds.items():
        full_mae = mae(y, pred)
        expected = float(committed_val[name]["mae"])
        verification[name] = {
            "recomputed_full_window_mae": full_mae,
            "committed_val_mae": expected,
            "matches": abs(full_mae - expected) < 1e-4,
        }
        if not verification[name]["matches"]:
            raise ValueError(f"{name} validation MAE drift: {full_mae} != {expected}")
    log.info("identity verified against committed validation MAEs")

    n_weeks = len(y) // ROWS_PER_WEEK
    origins: list[dict[str, Any]] = []
    for week in range(n_weeks):
        sl = slice(week * ROWS_PER_WEEK, (week + 1) * ROWS_PER_WEEK)
        y_o = y[sl]
        mlp_mae = mae(y_o, preds["mlp"][sl])
        lgbm_mae = mae(y_o, preds["lightgbm_hpo"][sl])
        ci, _deltas = paired_block_bootstrap_deltas(
            y_o,
            preds["mlp"][sl],
            preds["lightgbm_hpo"][sl],
            cfg.bootstrap_resamples,
            cfg.seed,
            block_size=24,
        )
        origins.append(
            {
                "origin_week_index": week,
                "n_rows": len(y_o),
                "mlp_mae": mlp_mae,
                "lightgbm_mae": lgbm_mae,
                "diff_mlp_minus_lightgbm": mlp_mae - lgbm_mae,
                "diff_ci95": [float(ci.lo), float(ci.hi)],
            }
        )
        log.info(
            "origin %d: mlp %.3f vs lightgbm %.3f (diff %+.3f)",
            week,
            mlp_mae,
            lgbm_mae,
            mlp_mae - lgbm_mae,
        )

    pooled_ci, _ = paired_block_bootstrap_deltas(
        y,
        preds["mlp"],
        preds["lightgbm_hpo"],
        cfg.bootstrap_resamples,
        cfg.seed,
        block_size=24,
    )
    report: dict[str, Any] = {
        "schema_version": "rolling-origin-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "data_source": "committed validation window (time-ordered; existing fold, sliced per week)",
        "rows_per_origin": ROWS_PER_WEEK,
        "n_origins": n_weeks,
        "verification": verification,
        "origins": origins,
        "pooled": {
            "diff_mlp_minus_lightgbm_mae": mae(y, preds["mlp"]) - mae(y, preds["lightgbm_hpo"]),
            "diff_ci95": [float(pooled_ci.lo), float(pooled_ci.hi)],
            "block_bootstrap_block_size_hours": 24,
            "note": (
                "per-origin intervals use 7 non-overlapping day blocks; few blocks, wide intervals"
            ),
        },
        "headline_check": {
            "tie_holds": bool(pooled_ci.lo <= 0 <= pooled_ci.hi),
            "reading": (
                "the committed validation tie (MLP 34.217 vs LightGBM 34.397 MAE) "
                "is a full-window summary; per-origin diffs below show where the "
                "gap comes from. No headline number changes."
            ),
        },
    }
    out_dir = cfg.reports_dir / "rolling_origin"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        "# Rolling-origin check — MLP vs LightGBM on the committed validation window",
        "",
        f"Generated: {report['generated_at']} - {n_weeks} weekly origins x "
        f"{ROWS_PER_WEEK} rows · committed artifacts, no retraining.",
        "",
        "Identity: full-window validation MAE recomputed == committed "
        "`train_runs.json` for both models.",
        "",
        "| origin week | MLP MAE | LightGBM MAE | diff (MLP - LGBM) | 95% CI |",
        "|---|---|---|---|---|",
    ]
    for o in origins:
        ci = o["diff_ci95"]
        lines.append(
            f"| {o['origin_week_index']} | {o['mlp_mae']:.3f} | {o['lightgbm_mae']:.3f} "
            f"| {o['diff_mlp_minus_lightgbm']:+.3f} | [{ci[0]:+.3f}, {ci[1]:+.3f}] |"
        )
    p = report["pooled"]
    lines += [
        "",
        f"Pooled across origins: diff {p['diff_mlp_minus_lightgbm_mae']:+.3f} "
        f"MAE [{p['diff_ci95'][0]:+.3f}, {p['diff_ci95'][1]:+.3f}] (day-block "
        "bootstrap, 24 h blocks).",
        f"Committed tie (both CIs include zero across the window) holds: "
        f"**{report['headline_check']['tie_holds']}**.",
        "",
        "New files only; `reports/metrics.json` untouched.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    log.info("wrote %s", out_dir)
    return report
