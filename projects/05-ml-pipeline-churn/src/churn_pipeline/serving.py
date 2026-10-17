"""Serving artifact for the showcase API (contract: SERVING.md).

``build_serving_artifact`` persists the calibrated champion into
``reports/models/serving/``:

- ``model.joblib`` — dict with ``model`` (the isotonic-calibrated fitted
  pipeline from ``data/selected_model_calibrated.pkl``), ``feature_names``
  (raw input columns; preprocessing lives inside the pipeline), and
  ``decision`` — the operating point ``{"threshold", "fp_cost", "fn_cost"}``.
- ``meta.json`` — feature schema, build metadata, the persisted HPO
  model-selection summary, the threshold-selection rationale, and a worked
  example row.

No retraining happens here: the threshold is re-derived deterministically
from the persisted holdout with the same ``cost_curve`` the ``evaluate``
stage uses (FP·fp_cost + FN·fn_cost over ``cfg.threshold_grid``), and the
model is the artifact the ``train`` stage already fitted and calibrated.

The API (apps/showcase-api) loads exactly these two files; do not rename or
reshape without updating SERVING.md and the API in the same change.
"""

import json
import pickle
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from portfolio_core.logging import get_logger

from churn_pipeline.config import ChurnConfig, pd
from churn_pipeline.evaluate import artifact_paths, cost_curve
from churn_pipeline.model import TARGET_COL, feature_cols, slice_cols

logger = get_logger(__name__)

SERVING_DIR = "serving"


def _serving_dir(cfg: ChurnConfig) -> Path:
    return cfg.reports_dir / "models" / SERVING_DIR


def _load_calibrated(cfg: ChurnConfig) -> Any:
    path = artifact_paths(cfg)["selected_calibrated"]
    if not path.exists():
        raise FileNotFoundError(
            f"{path} missing — run the train stage before building the serving artifact"
        )
    with path.open("rb") as fh:
        return pickle.load(fh)


def _holdout_frame(cfg: ChurnConfig) -> pd.DataFrame:
    return pd.read_parquet(artifact_paths(cfg)["holdout"])


def select_decision_threshold(cfg: ChurnConfig) -> tuple[float, float]:
    """Cost-optimal decision threshold of the calibrated model on the holdout.

    Recomputes the exact business-cost curve the ``evaluate`` stage reports
    (pooled FP·fp_cost + FN·fn_cost across ``cfg.threshold_grid`` on the
    persisted holdout) and returns (optimal threshold, minimum cost). With the
    current artifacts this lands at t=0.175 (cost 601 at FP=1, FN=5).
    """
    model = _load_calibrated(cfg)
    holdout = _holdout_frame(cfg)
    cols = list(dict.fromkeys(feature_cols(cfg) + slice_cols(cfg)))
    proba = np.asarray(model.predict_proba(holdout[cols])[:, 1], dtype=float)
    y_true = np.asarray(holdout[TARGET_COL].astype(int))
    costs, optimal = cost_curve(cfg, y_true, proba)
    logger.info("serving threshold: %.3f (holdout cost %.0f)", optimal, costs.min())
    return optimal, float(costs.min())


def _example_row(cfg: ChurnConfig) -> dict[str, Any]:
    """One real, typical holdout row (nearest to the column medians).

    Fairness-slice columns and the label are dropped; numerics are rounded.
    The row is a genuine observation from the holdout, so it provably passes
    the pipeline's feature validation.
    """
    holdout = _holdout_frame(cfg)
    cols = feature_cols(cfg)
    numeric = [c for c in cols if c in holdout.select_dtypes(include="number").columns]
    medians = holdout[numeric].median()
    distances = ((holdout[numeric] - medians).abs() / (holdout[numeric].std() + 1e-9)).sum(axis=1)
    row = holdout.loc[int(distances.idxmin()), cols]
    example: dict[str, Any] = {}
    for col in cols:
        value = row[col]
        example[col] = round(float(value), 4) if col in numeric else str(value)
    return example


def build_serving_artifact(cfg: ChurnConfig | None = None) -> Path:
    """Persist model.joblib + meta.json per the SERVING contract (no retraining)."""
    cfg = cfg or ChurnConfig()
    model = _load_calibrated(cfg)
    threshold, min_cost = select_decision_threshold(cfg)
    features = feature_cols(cfg)
    example_row = _example_row(cfg)

    out = _serving_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, Any] = {
        "model": model,
        "feature_names": features,
        "decision": {
            "threshold": threshold,
            "fp_cost": cfg.fp_cost,
            "fn_cost": cfg.fn_cost,
        },
    }
    joblib.dump(bundle, out / "model.joblib")

    selection_path = cfg.data_dir / "model_selection.json"
    selection = json.loads(selection_path.read_text()) if selection_path.exists() else {}
    meta: dict[str, Any] = {
        "feature_names": features,
        "n_features": len(features),
        "built_at": datetime.now(UTC).isoformat(),
        "model_selection": selection,
        "threshold_selection": {
            "threshold": threshold,
            "holdout_min_cost": min_cost,
            "rule": "argmin of FP·fp_cost + FN·fn_cost over the params.yaml "
            "threshold_grid on the persisted holdout, scored by the "
            "isotonic-calibrated model — the same cost curve the evaluate "
            "stage reports",
        },
        "example_row": example_row,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    logger.info("serving artifact (t=%.3f) -> %s", threshold, out)
    return out


def load_serving_artifact(cfg: ChurnConfig | None = None) -> dict[str, Any] | None:
    """Round-trip loader used by tests (and mirrors the API's load path).

    Returns None when the artifact has not been built yet.
    """
    cfg = cfg or ChurnConfig()
    out = _serving_dir(cfg)
    if not (out / "model.joblib").exists():
        return None
    bundle = joblib.load(out / "model.joblib")
    meta = json.loads((out / "meta.json").read_text())
    return {"bundle": bundle, "meta": meta}
