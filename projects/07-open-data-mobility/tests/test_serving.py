"""Serving artifact contract (SERVING.md): build, load back, predict sanely."""

import importlib.util
import json
from pathlib import Path

import joblib
import numpy as np
import polars as pl
import pytest
from mobility.config import MobilityConfig
from mobility.features import FEATURE_COLUMNS
from mobility.gbm import _make_gbm, hpo_result
from mobility.schemas import ServingRegistry
from mobility.serving import (
    build_service_bundle,
    build_serving_artifact,
    load_service_bundle,
    load_serving_artifact,
    predict_service,
)
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
    """Minimal on-disk context: tiny tuned models, zones, yellow + green frames."""
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    cfg.features_dir.mkdir(parents=True, exist_ok=True)
    cfg.curated_dir.mkdir(parents=True, exist_ok=True)
    gbm, p90 = _tiny_models()
    joblib.dump(gbm, cfg.models_dir / "gbm_tuned.joblib")
    joblib.dump(p90, cfg.models_dir / "gbm_p90_tuned.joblib")
    (cfg.models_dir / "hpo_gbm.json").write_text(
        json.dumps({"kind": "gbm", "best_params": {}, "best_val_mae": 3.0})
    )
    pl.DataFrame(
        {"location_id": [1, 2], "borough": ["Manhattan", "Queens"], "zone": ["A", "B"]}
    ).write_parquet(cfg.zones_path)
    demand = make_zone_hour_demand()
    demand.write_parquet(cfg.green_zone_hour_demand_path)  # per-service fit input
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


def test_serving_arm_selection_rule(cfg: MobilityConfig) -> None:
    """A challenger replaces the incumbent only on strictly better val MAE."""
    import json as _json

    from mobility.serving import select_serving_arm

    _fixture_context(cfg)
    gbm, p90 = _tiny_models()
    joblib.dump(gbm, cfg.models_dir / "gbm_xgb_tuned.joblib")
    joblib.dump(p90, cfg.models_dir / "gbm_p90_xgb_tuned.joblib")

    def _hpo(kind: str, mae: float) -> None:
        (cfg.models_dir / f"hpo_{kind}.json").write_text(
            _json.dumps({"kind": kind, "best_params": {}, "best_val_mae": mae})
        )

    _hpo("gbm", 3.0)
    # challenger worse → incumbent stays
    _hpo("xgb", 3.5)
    assert select_serving_arm(cfg)[0] == "gbm_tuned"
    # challenger strictly better → switch
    _hpo("xgb", 2.5)
    run, stem, p90_stem = select_serving_arm(cfg)
    assert run == "gbm_xgb_tuned"
    assert (cfg.models_dir / f"{stem}.joblib").exists()
    assert (cfg.models_dir / f"{p90_stem}.joblib").exists()
    # tie keeps the incumbent (strict improvement required)
    _hpo("xgb", 3.0)
    assert select_serving_arm(cfg)[0] == "gbm_tuned"


def test_gbm_factory_matches_model_family(cfg: MobilityConfig) -> None:
    """mobility.gbm is the torch-free home of the default GBM family."""
    gbm = _make_gbm(cfg.gbm.model_dump(), seed=cfg.seed)
    assert isinstance(gbm, HistGradientBoostingRegressor)
    assert gbm.random_state == cfg.seed
    p90 = _make_gbm(cfg.gbm.model_dump(), seed=cfg.seed, quantile=0.9)
    assert p90.loss == "quantile" and p90.quantile == 0.9
    assert not (cfg.models_dir / "hpo_gbm.json").exists()
    assert hpo_result(cfg, "gbm") is None  # missing HPO file → None, no crash


# ---------------------------------------------------------------------------
# Wave 15: per-service (green) retraining bundle + typed registry/prediction
# ---------------------------------------------------------------------------


def test_per_service_green_bundle_roundtrip(cfg: MobilityConfig) -> None:
    _fixture_context(cfg)
    out = build_serving_artifact(cfg, zone_id=1)

    # root yellow bundle keeps the exact wave-7 three-file contract
    assert (out / "model.joblib").exists()
    assert (out / "meta.json").exists()
    assert (out / "zones.json").exists()

    # green sub-bundle in the identical contract shape
    green = out / "green"
    assert (green / "model.joblib").exists()
    assert (green / "meta.json").exists()
    assert (green / "zones.json").exists()

    # typed registry indexes both services
    registry = ServingRegistry.model_validate_json((out / "services.json").read_text())
    assert set(registry.services) == {"yellow", "green"}
    assert registry.services["yellow"].dir == "."
    assert registry.services["green"].dir == "green"
    assert registry.services["green"].train_runs == ["gbm_green_served"]
    assert registry.services["yellow"].n_features == len(FEATURE_COLUMNS)

    artifact = load_service_bundle(cfg, "green")
    bundle, meta, zones = artifact["bundle"], artifact["meta"], artifact["zones"]
    assert bundle["feature_names"] == FEATURE_COLUMNS
    assert bundle["target_transform"] is None
    assert meta["train_runs"] == ["gbm_green_served"]
    assert meta["service"] == "green"
    assert meta["fit"]["train_rows"] > 0
    assert set(meta["example"]["features"]) == set(FEATURE_COLUMNS)
    assert {z["location_id"] for z in zones} == {1, 2}
    # yellow loads through the same loader, unchanged run name
    assert load_service_bundle(cfg, "yellow")["meta"]["train_runs"] == ["gbm_tuned"]


def test_predict_service_typed(cfg: MobilityConfig) -> None:
    """predict_service is the typed reference the showcase API mirrors."""
    _fixture_context(cfg)
    build_serving_artifact(cfg, zone_id=1)

    green_example = load_service_bundle(cfg, "green")["meta"]["example"]
    forecast = predict_service(cfg, "green", 1, green_example["features"])
    assert forecast.service == "green"
    assert forecast.zone_id == 1
    assert forecast.borough == "Manhattan"  # zone 1 in the fixture
    assert forecast.zone == "A"
    assert np.isfinite(forecast.prediction) and forecast.prediction >= 0
    assert forecast.p90 >= forecast.prediction  # quantile band sits above the mean

    yellow_example = load_service_bundle(cfg, "yellow")["meta"]["example"]
    yellow_fc = predict_service(cfg, "yellow", 1, yellow_example["features"])
    assert yellow_fc.service == "yellow"
    assert yellow_fc.prediction >= 0 and yellow_fc.p90 >= yellow_fc.prediction

    with pytest.raises(ValueError, match="unknown zone_id"):
        predict_service(cfg, "green", 999, green_example["features"])
    with pytest.raises(ValueError, match="missing features"):
        predict_service(cfg, "green", 1, {"lag_1": 1.0})
    with pytest.raises(FileNotFoundError):
        predict_service(cfg, "fhv", 1, green_example["features"])


def test_build_service_bundle_rejects_unknown_service(cfg: MobilityConfig) -> None:
    _fixture_context(cfg)
    with pytest.raises(ValueError, match="no per-service fit"):
        build_service_bundle(cfg, "fhv")
