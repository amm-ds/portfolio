"""Serving artifact contract (SERVING.md): build, load back, score sanely."""

import json
import pickle

import numpy as np
import pytest
from churn_pipeline.config import ChurnConfig, pd, threadpool_limits
from churn_pipeline.evaluate import artifact_paths
from churn_pipeline.model import TARGET_COL, build_pipeline, feature_cols, split_holdout
from churn_pipeline.serving import (
    build_serving_artifact,
    load_serving_artifact,
    select_decision_threshold,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split


def _fixture_context(cfg: ChurnConfig, frame: pd.DataFrame) -> None:
    """Minimal on-disk context: calibrated model, holdout, selection json."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    X_train, X_test, y_train, y_test = split_holdout(cfg, frame)

    _calib, X_calib, _y_fit, y_calib = train_test_split(
        X_train, y_train, test_size=cfg.calib_frac, stratify=y_train, random_state=cfg.seed
    )
    with threadpool_limits(limits=1):
        calibrated = CalibratedClassifierCV(
            estimator=build_pipeline(cfg, family="logreg"), method="isotonic", cv=2
        )
        calibrated.fit(X_calib, y_calib)

    paths = artifact_paths(cfg)
    with paths["selected_calibrated"].open("wb") as fh:
        pickle.dump(calibrated, fh)
    holdout = X_test.copy()
    holdout[TARGET_COL] = y_test.to_numpy()
    pd.DataFrame(holdout).to_parquet(paths["holdout"])
    (cfg.data_dir / "model_selection.json").write_text(
        json.dumps({"family": "logreg", "params": {"C": 0.1}, "objective": "cost"})
    )
    paths["operating_policy"].write_text(
        json.dumps(
            {
                "fp_cost": cfg.fp_cost,
                "fn_cost": cfg.fn_cost,
                "thresholds": {"selected_calibrated": 0.6},
                "training_costs": {"selected_calibrated": 123.0},
            }
        )
    )


def _expected_threshold(cfg: ChurnConfig) -> float:
    """Read the frozen threshold fixture, independently of serving."""
    policy = json.loads(artifact_paths(cfg)["operating_policy"].read_text())
    return float(policy["thresholds"]["selected_calibrated"])


def test_serving_artifact_roundtrip(small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame) -> None:
    cfg = small_cfg
    _fixture_context(cfg, tiny_synthetic)
    out = build_serving_artifact(cfg)
    assert (out / "model.joblib").exists()
    assert (out / "meta.json").exists()

    artifact = load_serving_artifact(cfg)
    assert artifact is not None
    bundle, meta = artifact["bundle"], artifact["meta"]
    features = feature_cols(cfg)

    # contract shape
    assert bundle["feature_names"] == features
    assert set(meta["example_row"]) == set(features)
    assert meta["model_selection"]["family"] == "logreg"
    assert meta["feature_names"] == features

    # threshold and cost come from the persisted training-side policy
    assert bundle["decision"]["threshold"] == _expected_threshold(cfg) == 0.6
    assert bundle["decision"]["threshold"] in cfg.threshold_grid
    assert bundle["decision"]["fp_cost"] == cfg.fp_cost
    assert bundle["decision"]["fn_cost"] == cfg.fn_cost
    assert meta["threshold_selection"]["threshold"] == bundle["decision"]["threshold"]
    assert meta["threshold_selection"]["training_oof_min_cost"] == 123.0

    # predict on the example exactly like the API does — finite probability
    example = meta["example_row"]
    row = pd.DataFrame([{f: example[f] for f in features}])
    proba = float(bundle["model"].predict_proba(row)[0, 1])
    assert np.isfinite(proba) and 0.0 <= proba <= 1.0

    # parity: bundle model IS the raw pickle — same input, same output
    with artifact_paths(cfg)["selected_calibrated"].open("rb") as fh:
        raw = pickle.load(fh)
    raw_proba = float(raw.predict_proba(row)[0, 1])
    assert proba == pytest.approx(raw_proba)


def test_serving_load_returns_none_when_absent(small_cfg: ChurnConfig) -> None:
    assert load_serving_artifact(small_cfg) is None


def test_serving_threshold_rule(
    small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Threshold loading cannot read or optimize against the holdout."""
    cfg = small_cfg
    _fixture_context(cfg, tiny_synthetic)
    monkeypatch.setattr(
        "churn_pipeline.serving._holdout_frame",
        lambda _cfg: pytest.fail("threshold selection read the holdout"),
    )
    threshold, training_cost = select_decision_threshold(cfg)
    assert threshold == _expected_threshold(cfg) == 0.6
    assert training_cost == 123.0
