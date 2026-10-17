"""Serving artifact for the showcase API (contract: SERVING.md).

``build_serving_artifact`` persists the backtest champion into
``reports/models/serving/``:

- ``model.joblib`` — dict with ``model`` (the fitted champion from
  ``data/models.pkl``), ``feature_names`` (ordered input columns, series_id
  last), and ``target_transform`` (``None`` — all served arms predict raw
  units; no target transform is applied anywhere in this project).
- ``meta.json`` — feature schema, build metadata, the model-selection
  summary (which arm won and why), and a worked example row.

No retraining happens here: the champion is the fitted model already
persisted by the ``train`` stage, and the selection rule reads the HPO
validation MAEs from the ``hpo`` stage's ``data/hpo_best*.json`` artifacts
(the same numbers the ``evaluate`` stage reports in ``reports/metrics.json``).

The API (apps/showcase-api) loads exactly these two files; do not rename or
reshape without updating SERVING.md and the API in the same change.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import polars as pl
from portfolio_core.logging import get_logger

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.model import load_models, model_specs

logger = get_logger(__name__)

SERVING_DIR = "serving"

#: Booster-arm registry: arm → (hpo json stem, fitted-model key in models.pkl).
#: The fitted model key is what the ``train`` stage persisted for that arm's
#: production config.
_ARMS: dict[str, tuple[str, str]] = {
    "hgb": ("hpo_best", "hgb_tuned"),
    "xgb": ("hpo_best_xgb", "xgb_tuned"),
    "lgbm": ("hpo_best_lgbm", "lgbm_tuned"),
}


def _serving_dir(settings: DemandSettings) -> Path:
    return settings.reports_dir / "models" / SERVING_DIR


def _arm_val_mae(settings: DemandSettings, arm: str) -> float | None:
    """Validation (CV) MAE of one arm from its persisted HPO study, if present."""
    stem, _ = _ARMS[arm]
    path = settings.data_dir / f"{stem}.json"
    if not path.exists():
        return None
    return float(json.loads(path.read_text())["best_cv_mae"])


def select_serving_arm(settings: DemandSettings) -> tuple[str, dict[str, float]]:
    """Pick the served arm by HPO validation MAE; ties keep the incumbent.

    Rule: the champion is the arm with the lowest ``best_cv_mae`` across the
    persisted HPO studies (hgb → xgb → lgbm iteration order, strict
    improvement required), i.e. exactly the selection the evaluate stage
    surfaces in ``reports/metrics.json``. Arms without a persisted HPO
    artifact are skipped. Returns (model key in ``data/models.pkl``,
    {arm: val MAE} for every arm seen).
    """
    best_arm: str | None = None
    best_mae = float("inf")
    maes: dict[str, float] = {}
    for arm in _ARMS:
        mae = _arm_val_mae(settings, arm)
        if mae is None:
            continue
        maes[arm] = mae
        if mae < best_mae:
            best_mae = mae
            best_arm = arm
    if best_arm is None:
        raise FileNotFoundError("no servable arm — run the hpo stage first")
    _, model_key = _ARMS[best_arm]
    logger.info("serving arm: %s (val MAE %.4f)", model_key, best_mae)
    return model_key, maes


def _example_row(
    settings: DemandSettings, config: ForecastConfig, feature_names: list[str]
) -> dict[str, Any]:
    """A typical real input: per-feature medians over the modelling frame.

    Numeric features and lags are rounded medians; ``series_id`` is a real
    series from the panel (identities are synthetic store-product keys, not
    personal data).
    """
    frame = pl.read_parquet(settings.data_dir / "features.parquet")
    numeric = [f for f in feature_names if f != "series_id"]
    medians = frame.select([pl.col(f).median() for f in numeric])
    example: dict[str, Any] = {f: round(float(medians[f][0]), 4) for f in numeric}
    example["series_id"] = str(frame["series_id"][0])
    return example


def _known_series(settings: DemandSettings) -> list[str]:
    """All series identities the serving panel was trained on (sorted, unique)."""
    frame = pl.read_parquet(settings.data_dir / "features.parquet")
    return sorted(frame["series_id"].unique().to_list())


def build_serving_artifact(
    settings: DemandSettings | None = None, config: ForecastConfig | None = None
) -> Path:
    """Persist model.joblib + meta.json per the SERVING contract (no retraining)."""
    settings = settings or DemandSettings()
    config = config or ForecastConfig()
    model_key, maes = select_serving_arm(settings)
    model = load_models(settings.data_dir / "models.pkl")[model_key]
    spec = next(s for s in model_specs() if s.name == model_key)
    feature_names = spec.feature_names(config)
    example_row = _example_row(settings, config, feature_names)

    out = _serving_dir(settings)
    out.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, Any] = {
        "model": model,
        "feature_names": feature_names,
        # All served arms predict raw daily units; no target transform applies.
        "target_transform": None,
    }
    joblib.dump(bundle, out / "model.joblib")

    meta: dict[str, Any] = {
        "feature_names": feature_names,
        "n_features": len(feature_names),
        "built_at": datetime.now(UTC).isoformat(),
        "train_runs": [model_key],
        "model_selection": {
            "champion": model_key,
            "val_mae_by_arm": maes,
            "rule": "lowest HPO CV MAE (data/hpo_best*.json) across the tuned "
            "booster arms; ties keep the earlier (hgb) incumbent; the fitted "
            "champion is loaded from data/models.pkl — no retraining",
        },
        "example_row": example_row,
        "series": _known_series(settings),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    logger.info("serving artifact (%s) -> %s", model_key, out)
    return out


def load_serving_artifact(settings: DemandSettings | None = None) -> dict[str, Any] | None:
    """Round-trip loader used by tests (and mirrors the API's load path).

    Returns None when the artifact has not been built yet.
    """
    settings = settings or DemandSettings()
    out = _serving_dir(settings)
    if not (out / "model.joblib").exists():
        return None
    bundle = joblib.load(out / "model.joblib")
    meta = json.loads((out / "meta.json").read_text())
    return {"bundle": bundle, "meta": meta}
