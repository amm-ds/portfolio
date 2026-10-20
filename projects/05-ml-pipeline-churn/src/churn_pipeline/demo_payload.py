"""Demo payload for the churn threshold sandbox (showcase demo A1).

Builds ``reports/demo_payload.json`` — a compact, fully precomputed lookup
that lets the showcase UI recompute business cost for **any** FP/FN cost
ratio client-side, without retraining or serving model inference:

- per-threshold confusion counts (tn/fp/fn/tp) of the isotonic-calibrated
  champion on the persisted 1,409-row holdout, on a fine threshold grid;
- the same counts per fairness slice (contract type) so the UI can show
  where the alarm burden lands;
- the binned reliability table and the committed cost-delta bootstrap CI;
- scored example customers (churn probability precomputed here) plus the
  value domains of the four model features for the sandbox form.

Everything is deterministic: the model and holdout are the committed train
artifacts, and probabilities are computed once at build time. The live
``/score`` endpoint in the showcase API scores free-form customer input at
request time; this payload only carries what that endpoint cannot provide
(the full cost curve and slices).
"""

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from portfolio_core.logging import get_logger
from sklearn.metrics import confusion_matrix, roc_auc_score

from churn_pipeline.config import ChurnConfig, pd
from churn_pipeline.evaluate import artifact_paths, binned_calibration
from churn_pipeline.model import TARGET_COL, feature_cols, slice_cols

logger = get_logger(__name__)

DEMO_PAYLOAD_NAME = "demo_payload.json"
# Fine grid: the UI recomputes cost for arbitrary cost ratios, so this is
# denser than params.yaml's threshold_grid (which optimizes one cost model).
DEMO_GRID = [round(0.02 + 0.02 * i, 2) for i in range(45)]  # 0.02 .. 0.90

# Example customers spanning the risk spectrum; scored at build time.
CUSTOMER_PRESETS: list[dict[str, Any]] = [
    {
        "label": "new month-to-month fiber customer",
        "features": {
            "tenure_months": 4.0,
            "monthly_charges": 95.5,
            "contract": "month-to-month",
            "internet_service": "fiber-optic",
        },
    },
    {
        "label": "loyal two-year DSL customer",
        "features": {
            "tenure_months": 58.0,
            "monthly_charges": 55.2,
            "contract": "two-year",
            "internet_service": "DSL",
        },
    },
    {
        "label": "mid-tenure one-year customer",
        "features": {
            "tenure_months": 29.0,
            "monthly_charges": 69.05,
            "contract": "one-year",
            "internet_service": "DSL",
        },
    },
]


def _confusion_counts(
    y_true: NDArray[np.int64], proba: NDArray[np.float64], threshold: float
) -> dict[str, int]:
    y_pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}


def build_demo_payload(cfg: ChurnConfig) -> dict[str, Any]:
    """Assemble the sandbox payload from committed train/evaluate artifacts."""
    paths = artifact_paths(cfg)
    with paths["selected_calibrated"].open("rb") as fh:
        model = pickle.load(fh)  # noqa: S301 - artifact persisted by this pipeline
    holdout = pd.read_parquet(paths["holdout"])

    cols = list(dict.fromkeys(feature_cols(cfg) + slice_cols(cfg)))
    X_test = holdout[cols]
    y_test = holdout[TARGET_COL].astype(int).to_numpy()
    proba = np.asarray(model.predict_proba(X_test)[:, 1], dtype=float)

    metrics = json.loads((cfg.reports_dir / "metrics.json").read_text())
    run = metrics["selected_model_calibrated"]
    naive = metrics["naive_majority"]
    delta_ci = metrics["_meta"]["cost_delta_ci"]

    overall = [{"t": t, **_confusion_counts(y_test, proba, t)} for t in DEMO_GRID]
    contract_col = "contract"
    slices: dict[str, dict[str, list[dict[str, Any]]]] = {contract_col: {}}
    for value in sorted(holdout[contract_col].unique()):
        mask = (holdout[contract_col] == value).to_numpy()
        slices[contract_col][str(value)] = [
            {"t": t, **_confusion_counts(y_test[mask], proba[mask], t)} for t in DEMO_GRID
        ]

    numeric_cols = [c for c in feature_cols(cfg) if c not in ("contract", "internet_service")]
    base_row = {
        c: (float(holdout[c].median()) if c in numeric_cols else str(holdout[c].mode()[0]))
        for c in feature_cols(cfg)
    }
    customers = []
    for preset in CUSTOMER_PRESETS:
        row = {**base_row, **{k: v for k, v in preset["features"].items() if k in base_row}}
        frame = pd.DataFrame([row])[feature_cols(cfg)]
        p = float(model.predict_proba(frame)[0, 1])
        customers.append({**preset, "churn_probability": round(p, 4)})

    feature_domains: dict[str, Any] = {}
    for col in feature_cols(cfg):
        if col == contract_col or col == "internet_service":
            feature_domains[col] = sorted(str(v) for v in holdout[col].unique())
        else:
            feature_domains[col] = {
                "min": float(holdout[col].min()),
                "max": float(holdout[col].max()),
            }

    return {
        "demo": "churn-threshold-sandbox",
        "project": "05-ml-pipeline-churn",
        "holdout_n": len(y_test),
        "model": {
            "name": "selected_model_calibrated",
            "roc_auc": run["roc_auc"],
            "ece": run["ece"],
            "threshold_default": 0.5,
            "threshold_selected": metrics["_meta"]["selected_opt"],
        },
        "cost_model": {
            "fp_cost": cfg.fp_cost,
            "fn_cost": cfg.fn_cost,
            "note": "cost = fp_cost·FP + fn_cost·FN per 1,000-customer holdout",
        },
        "headline": {
            "cost_naive": naive["business_cost"],
            "cost_selected": run["business_cost"],
            "delta_ci": {
                "point": delta_ci["point"],
                "lo": delta_ci["lo"],
                "hi": delta_ci["hi"],
                "significant_95": delta_ci["significant_95"],
            },
        },
        "thresholds": DEMO_GRID,
        "overall": overall,
        "slices": slices,
        "calibration": binned_calibration(y_test, proba, cfg.calibration_bins),
        "customers": customers,
        "feature_domains": feature_domains,
        "roc_auc": roc_auc_score(y_test, proba),
    }


def write_demo_payload(cfg: ChurnConfig) -> Path:
    """Build the payload and persist it to ``reports/demo_payload.json``."""
    payload = build_demo_payload(cfg)
    out = cfg.reports_dir / DEMO_PAYLOAD_NAME
    out.write_text(json.dumps(payload, indent=2))
    logger.info(
        "demo payload: %d thresholds, %d calibration bins, %d customers -> %s",
        len(payload["thresholds"]),
        len(payload["calibration"]),
        len(payload["customers"]),
        out,
    )
    return out
