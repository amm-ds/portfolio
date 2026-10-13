"""Serving artifact for the showcase API (contract: SERVING.md).

``build_serving_artifact`` persists the tuned GBM pair into
``reports/models/serving/``:

- ``model.joblib`` — dict with ``gbm`` (mean), ``p90`` (quantile-0.9),
  ``feature_names`` (ordered input columns), ``target_transform`` (``None``
  here — GBMs are trained on raw counts; only the NN uses log1p).
- ``meta.json`` — feature schema, build metadata, and a worked example row
  (real zone_id + realistic feature values from the test window).
- ``zones.json`` — location_id/borough/zone reference for response enrichment.

The API (apps/showcase-api, GET/POST /projects/07-open-data-mobility/forecast)
loads exactly these three files; do not rename or reshape without updating
SERVING.md and the API in the same change.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import polars as pl
from portfolio_core.logging import get_logger

from mobility.config import MobilityConfig, get_config
from mobility.features import FEATURE_COLUMNS

logger = get_logger(__name__)

SERVING_DIR = "serving"


def _serving_dir(cfg: MobilityConfig) -> Path:
    return cfg.models_dir / SERVING_DIR


def _load_tuned_pair(cfg: MobilityConfig) -> tuple[Any, Any]:
    mean_path = cfg.models_dir / "gbm_tuned.joblib"
    p90_path = cfg.models_dir / "gbm_p90_tuned.joblib"
    if not (mean_path.exists() and p90_path.exists()):
        raise FileNotFoundError(
            f"missing {mean_path} / {p90_path} — run `mobility tune` + `mobility train-baselines`"
        )
    return joblib.load(mean_path), joblib.load(p90_path)


def _example_row(cfg: MobilityConfig, zone_id: int) -> dict[str, float]:
    """Realistic features: the median test-window row for ``zone_id``."""
    test = pl.read_parquet(cfg.features_dir / "test.parquet")
    rows = test.filter(pl.col("zone_id") == zone_id)
    if rows.height == 0:
        raise ValueError(f"zone {zone_id} not present in the test window")
    medians = rows.select([pl.col(f).median() for f in FEATURE_COLUMNS])
    return {f: round(float(medians[f][0]), 4) for f in FEATURE_COLUMNS}


def build_serving_artifact(cfg: MobilityConfig | None = None, zone_id: int = 132) -> Path:
    """Persist model.joblib + meta.json + zones.json per the SERVING contract."""
    cfg = cfg or get_config()
    gbm, p90 = _load_tuned_pair(cfg)

    zones = pl.read_parquet(cfg.zones_path).select(["location_id", "borough", "zone"])
    example_features = _example_row(cfg, zone_id)

    out = _serving_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, Any] = {
        "gbm": gbm,
        "p90": p90,
        "feature_names": list(FEATURE_COLUMNS),
        # GBMs predict raw pickup counts; the log1p transform applies only
        # to TemporalNet, which is not served here.
        "target_transform": None,
    }
    joblib.dump(bundle, out / "model.joblib")

    meta: dict[str, Any] = {
        "feature_names": list(FEATURE_COLUMNS),
        "n_features": len(FEATURE_COLUMNS),
        "built_at": datetime.now(UTC).isoformat(),
        "train_runs": ["gbm_tuned"],
        "example": {"zone_id": zone_id, "features": example_features},
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (out / "zones.json").write_text(json.dumps(zones.to_dicts(), indent=2) + "\n")
    logger.info(
        "serving artifact -> %s (example zone %d: %s)",
        out,
        zone_id,
        {k: example_features[k] for k in list(example_features)[:4]},
    )
    return out


def load_serving_artifact(cfg: MobilityConfig | None = None) -> dict[str, Any]:
    """Round-trip loader used by tests (and mirrors the API's load path)."""
    cfg = cfg or get_config()
    out = _serving_dir(cfg)
    bundle = joblib.load(out / "model.joblib")
    meta = json.loads((out / "meta.json").read_text())
    zones = json.loads((out / "zones.json").read_text())
    return {"bundle": bundle, "meta": meta, "zones": zones}
