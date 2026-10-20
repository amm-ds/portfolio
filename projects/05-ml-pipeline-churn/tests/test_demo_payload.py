"""Demo payload contract: deterministic lookup data for the churn sandbox UI."""

import json
import pickle

import numpy as np
import pytest
from churn_pipeline.config import ChurnConfig, pd, threadpool_limits
from churn_pipeline.demo_payload import DEMO_GRID, build_demo_payload, write_demo_payload
from churn_pipeline.evaluate import artifact_paths, business_cost
from churn_pipeline.model import (
    SCHEMES,
    TARGET_COL,
    build_pipeline,
    feature_cols,
    slice_cols,
    split_holdout,
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


@pytest.fixture
def payload(small_cfg: ChurnConfig, tiny_synthetic: pd.DataFrame) -> dict:
    """Payload built on the synthetic fixture frame with committed-metrics shape."""
    _fixture_context(small_cfg, tiny_synthetic)
    small_cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    metrics = {
        "naive_majority": {"business_cost": 1035.0},
        "selected_model_calibrated": {"roc_auc": 0.83, "ece": 0.02, "business_cost": 601.0},
        "_meta": {
            "cost_delta_ci": {
                "point": -416.0,
                "lo": -485.0,
                "hi": -343.0,
                "n_boot": 2000,
                "significant_95": True,
            },
            "selected_opt": 0.4,
        },
    }
    (small_cfg.reports_dir / "metrics.json").write_text(json.dumps(metrics))
    return build_demo_payload(small_cfg)


def test_payload_shape(payload: dict) -> None:
    assert payload["demo"] == "churn-threshold-sandbox"
    assert payload["thresholds"] == DEMO_GRID
    assert len(payload["overall"]) == len(DEMO_GRID)
    row = payload["overall"][0]
    assert set(row) == {"t", "tn", "fp", "fn", "tp"}
    # confusion counts partition the holdout at every threshold
    for r in payload["overall"]:
        assert r["tn"] + r["fp"] + r["fn"] + r["tp"] == payload["holdout_n"]


def test_payload_cost_matches_business_cost(small_cfg: ChurnConfig, payload: dict) -> None:
    """Grid counts must reproduce ``business_cost`` from the same artifacts."""
    with artifact_paths(small_cfg)["selected_calibrated"].open("rb") as fh:
        model = pickle.load(fh)
    holdout = pd.read_parquet(artifact_paths(small_cfg)["holdout"])
    cols = list(dict.fromkeys(feature_cols(small_cfg) + slice_cols(small_cfg)))
    proba = np.asarray(model.predict_proba(holdout[cols])[:, 1], dtype=float)
    y_true = holdout[TARGET_COL].astype(int).to_numpy()
    for entry in payload["overall"][::9]:  # spot-check every 9th threshold
        expected = business_cost(
            y_true,
            proba,
            entry["t"],
            payload["cost_model"]["fp_cost"],
            payload["cost_model"]["fn_cost"],
        )
        actual = (
            payload["cost_model"]["fp_cost"] * entry["fp"]
            + payload["cost_model"]["fn_cost"] * entry["fn"]
        )
        assert actual == expected


def test_payload_slices_match_contract_values(payload: dict) -> None:
    contracts = payload["slices"]["contract"]
    assert set(contracts) == {"month-to-month", "one-year", "two-year"}
    for rows in contracts.values():
        assert len(rows) == len(DEMO_GRID)


def test_payload_customers_scored(payload: dict) -> None:
    probs = [c["churn_probability"] for c in payload["customers"]]
    assert all(0.0 <= p <= 1.0 for p in probs)
    # the risky preset must score above the loyal one
    by_label = {c["label"]: c["churn_probability"] for c in payload["customers"]}
    assert by_label["new month-to-month fiber customer"] > by_label["loyal two-year DSL customer"]


def test_payload_feature_domains_match_scheme(payload: dict) -> None:
    # synthetic scheme: 4 numeric features + contract (no internet_service)
    domains = payload["feature_domains"]
    assert set(domains) == set(SCHEME["numeric"] + SCHEME["categorical"])
    assert set(domains["contract"]) == {"month-to-month", "one-year", "two-year"}
    for col in SCHEME["numeric"]:
        assert domains[col]["min"] <= domains[col]["max"]


SCHEME = SCHEMES["synthetic"]


def test_write_demo_payload_roundtrip(small_cfg: ChurnConfig, payload: dict) -> None:
    out = write_demo_payload(small_cfg)
    assert out.name == "demo_payload.json"
    on_disk = json.loads(out.read_text())
    assert on_disk["thresholds"] == payload["thresholds"]
    assert on_disk["overall"] == payload["overall"]
