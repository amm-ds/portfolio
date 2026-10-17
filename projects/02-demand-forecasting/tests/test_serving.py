"""Serving artifact contract (SERVING.md): build, load back, predict sanely."""

import json

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.model import load_models, model_specs, save_models, to_xy
from demand_forecasting.serving import (
    build_serving_artifact,
    load_serving_artifact,
    select_serving_arm,
)

ARMS = ("hgb_tuned", "xgb_tuned", "lgbm_tuned")
HPO_JSON = {
    "hgb_tuned": "hpo_best.json",
    "xgb_tuned": "hpo_best_xgb.json",
    "lgbm_tuned": "hpo_best_lgbm.json",
}


def _fixture_context(
    settings: DemandSettings, config: ForecastConfig, features: pl.DataFrame
) -> None:
    """Minimal on-disk context: fitted tuned arms, HPO MAE jsons, features."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    fitted = {}
    for name in ARMS:
        spec = next(s for s in model_specs() if s.name == name)
        x, y, _, _ = to_xy(features, config, spec)
        model = spec.build(config)
        model.fit(x, y)
        fitted[name] = model
    save_models(fitted, settings.data_dir / "models.pkl")
    features.write_parquet(settings.data_dir / "features.parquet")
    maes = {"hgb_tuned": 3.0, "xgb_tuned": 2.5, "lgbm_tuned": 2.8}
    for name, stem in HPO_JSON.items():
        (settings.data_dir / stem).write_text(
            json.dumps({"best_params": {}, "best_cv_mae": maes[name]})
        )


def _predict_row(model: object, example: dict[str, object], feature_names: list[str]) -> float:
    """Score one example row through the champion, exactly like the API does."""
    row = np.array(
        [[float(example[f]) for f in feature_names if f != "series_id"] + [example["series_id"]]],
        dtype=object,
    )
    return float(model.predict(row)[0])  # type: ignore[attr-defined]


def test_serving_artifact_roundtrip(
    settings: DemandSettings, config: ForecastConfig, features: pl.DataFrame
) -> None:
    _fixture_context(settings, config, features)
    out = build_serving_artifact(settings, config)
    assert (out / "model.joblib").exists()
    assert (out / "meta.json").exists()

    artifact = load_serving_artifact(settings)
    assert artifact is not None
    bundle, meta = artifact["bundle"], artifact["meta"]

    spec = next(s for s in model_specs() if s.name == "xgb_tuned")
    feature_names = spec.feature_names(config)

    # contract shape: xgb_tuned has the strictly-best fabricated MAE (2.5)
    assert bundle["target_transform"] is None
    assert bundle["feature_names"] == feature_names
    assert meta["feature_names"] == feature_names
    assert meta["train_runs"] == ["xgb_tuned"]
    assert meta["model_selection"]["champion"] == "xgb_tuned"
    assert meta["model_selection"]["val_mae_by_arm"] == {
        "hgb": 3.0,
        "xgb": 2.5,
        "lgbm": 2.8,
    }
    example = meta["example_row"]
    assert set(example) == set(feature_names)

    # predict on the example exactly like the API does — finite, non-negative
    pred = _predict_row(bundle["model"], example, feature_names)
    assert np.isfinite(pred) and pred >= 0

    # parity: the bundle model IS the fitted champion from data/models.pkl
    raw = load_models(settings.data_dir / "models.pkl")["xgb_tuned"]
    raw_pred = _predict_row(raw, example, feature_names)
    assert pred == pytest.approx(raw_pred)


def test_serving_load_returns_none_when_absent(settings: DemandSettings) -> None:
    assert load_serving_artifact(settings) is None


def test_serving_arm_selection_rule(
    settings: DemandSettings, config: ForecastConfig, features: pl.DataFrame
) -> None:
    """A challenger replaces the incumbent only on strictly better val MAE."""
    _fixture_context(settings, config, features)

    def _hpo(name: str, mae: float) -> None:
        (settings.data_dir / HPO_JSON[name]).write_text(
            json.dumps({"best_params": {}, "best_cv_mae": mae})
        )

    # challengers worse → incumbent (hgb) stays
    _hpo("xgb_tuned", 3.5)
    _hpo("lgbm_tuned", 3.6)
    assert select_serving_arm(settings)[0] == "hgb_tuned"
    # challenger strictly better → switch
    _hpo("xgb_tuned", 2.5)
    assert select_serving_arm(settings)[0] == "xgb_tuned"
    # tie keeps the incumbent (strict improvement required)
    _hpo("xgb_tuned", 3.0)
    assert select_serving_arm(settings)[0] == "hgb_tuned"
    # missing arm jsons are skipped, not fatal
    (settings.data_dir / HPO_JSON["lgbm_tuned"]).unlink()
    _hpo("xgb_tuned", 2.5)
    model_key, maes = select_serving_arm(settings)
    assert model_key == "xgb_tuned"
    assert set(maes) == {"hgb", "xgb"}
