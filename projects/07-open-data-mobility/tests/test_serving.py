"""Serving artifact contract (SERVING.md): build, load back, predict sanely."""

import importlib.util
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from mobility.config import MobilityConfig
from mobility.features import FEATURE_COLUMNS
from mobility.serving import build_serving_artifact, load_serving_artifact
from sklearn.ensemble import HistGradientBoostingRegressor

_spec = importlib.util.spec_from_file_location(
    "mobility_test_helpers", Path(__file__).parent / "conftest.py"
)
assert _spec is not None and _spec.loader is not None
_helpers_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers_mod)
make_zone_hour_demand = _helpers_mod.make_zone_hour_demand


def _tiny_models() -> tuple[HistGradientBoostingRegressor, HistGradientBoostingRegressor]:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, len(FEATURE_COLUMNS))).astype(np.float32)
    y = np.abs(X[:, 0] * 5 + 10)
    gbm = HistGradientBoostingRegressor(max_iter=20, random_state=42).fit(X, y)
    p90 = HistGradientBoostingRegressor(
        loss="quantile", quantile=0.9, max_iter=20, random_state=42
    ).fit(X, y)
    return gbm, p90


def _fixture_context(cfg: MobilityConfig) -> None:
    """Minimal on-disk context: tiny tuned models, zones, test features."""
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    cfg.features_dir.mkdir(parents=True, exist_ok=True)
    cfg.curated_dir.mkdir(parents=True, exist_ok=True)
    gbm, p90 = _tiny_models()
    joblib.dump(gbm, cfg.models_dir / "gbm_tuned.joblib")
    joblib.dump(p90, cfg.models_dir / "gbm_p90_tuned.joblib")
    pl.DataFrame(
        {"location_id": [1, 2], "borough": ["Manhattan", "Queens"], "zone": ["A", "B"]}
    ).write_parquet(cfg.zones_path)
    demand = make_zone_hour_demand()
    demand.select(
        [
            "zone_id",
            "borough",
            "ts",
            pl.col("pickup_count").alias("target"),
            pl.col("pickup_count").alias("lag_1"),
            pl.col("pickup_count").alias("lag_2"),
            pl.col("pickup_count").alias("lag_24"),
            pl.col("pickup_count").alias("lag_168"),
            pl.lit(12).alias("hour"),
            pl.lit(1).alias("day_of_week"),
            pl.lit(1).alias("month"),
            pl.col("prcp_mm"),
            pl.col("tmax_c"),
            pl.col("tmin_c"),
            pl.col("snow_mm"),
        ]
    ).write_parquet(cfg.features_dir / "test.parquet")


def test_serving_artifact_roundtrip(cfg: MobilityConfig) -> None:
    _fixture_context(cfg)
    out = build_serving_artifact(cfg, zone_id=1)
    assert (out / "model.joblib").exists()
    assert (out / "meta.json").exists()
    assert (out / "zones.json").exists()

    artifact = load_serving_artifact(cfg)
    bundle, meta, zones = artifact["bundle"], artifact["meta"], artifact["zones"]

    # contract shape
    assert bundle["feature_names"] == FEATURE_COLUMNS
    assert bundle["target_transform"] is None
    assert meta["n_features"] == len(FEATURE_COLUMNS)
    assert meta["train_runs"] == ["gbm_tuned"]
    assert meta["example"]["zone_id"] == 1
    assert set(meta["example"]["features"]) == set(FEATURE_COLUMNS)
    assert {z["location_id"] for z in zones} == {1, 2}

    # predict on the example exactly like the API does
    feats = meta["example"]["features"]
    row = np.array([[float(feats[f]) for f in bundle["feature_names"]]])
    pred = float(bundle["gbm"].predict(row)[0])
    band = float(bundle["p90"].predict(row)[0])
    assert np.isfinite(pred) and np.isfinite(band)
    assert pred >= 0 and band >= pred  # quantile band sits above the mean
