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

No retraining or threshold selection happens here: the calibrated model and
its training-side OOF-frozen threshold come directly from the ``train``
stage's persisted artifacts. The holdout is used only to choose an example row.

The API (apps/showcase-api) loads exactly these two files; do not rename or
reshape without updating SERVING.md and the API in the same change.
"""

import json
import pickle
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
from portfolio_core.logging import get_logger

from churn_pipeline.config import ChurnConfig, pd
from churn_pipeline.evaluate import artifact_paths
from churn_pipeline.model import feature_cols

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
        return pickle.load(fh)  # noqa: S301 - serving artifact persisted by this pipeline


def _holdout_frame(cfg: ChurnConfig) -> pd.DataFrame:
    return pd.read_parquet(artifact_paths(cfg)["holdout"])


def select_decision_threshold(cfg: ChurnConfig) -> tuple[float, float]:
    """Load the calibrated policy's OOF-frozen threshold and training cost."""
    paths = artifact_paths(cfg)
    policy = json.loads(paths["operating_policy"].read_text())
    if policy["fp_cost"] != cfg.fp_cost or policy["fn_cost"] != cfg.fn_cost:
        raise ValueError("operating policy cost model does not match params.yaml")
    threshold = float(policy["thresholds"]["selected_calibrated"])
    training_cost = float(policy["training_costs"]["selected_calibrated"])
    logger.info("serving threshold: %.3f (training OOF cost %.0f)", threshold, training_cost)
    return threshold, training_cost


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
            "training_oof_min_cost": min_cost,
            "rule": "loaded from data/operating_policy.json; selected by argmin "
            "of FP·fp_cost + FN·fn_cost over params.yaml threshold_grid using "
            "training-side out-of-fold predictions before holdout scoring",
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
