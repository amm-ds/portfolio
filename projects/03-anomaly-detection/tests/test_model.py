"""Model-stage tests: split, scoring convention, persistence."""

from datetime import datetime

import numpy as np
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.data import generate
from anomaly_detection.features import build_features
from anomaly_detection.model import (
    anomaly_scores,
    feature_matrix,
    fit_models,
    load_model,
    make_model,
    save_models,
    split_train_test,
)


def test_split_is_time_ordered(small_config: AnomalyConfig) -> None:
    df = build_features(generate(small_config), small_config.windows)
    train, test = split_train_test(df, small_config.train_frac)
    assert train.height + test.height == df.height
    train_last: datetime = train.tail(1)["ts"].item()
    test_first: datetime = test.head(1)["ts"].item()
    assert train_last <= test_first
    assert set(train.columns) == set(df.columns)


def test_split_rejects_degenerate_fraction(small_config: AnomalyConfig) -> None:
    df = build_features(generate(small_config), small_config.windows)
    with pytest.raises(ValueError):
        split_train_test(df, 1.0)


def test_unknown_model_rejected(small_config: AnomalyConfig) -> None:
    with pytest.raises(ValueError, match="unknown model"):
        make_model("kmeans", small_config)


def test_all_configured_models_fit(small_config: AnomalyConfig) -> None:
    df = build_features(generate(small_config), small_config.windows)
    train, _ = split_train_test(df, small_config.train_frac)
    fitted = fit_models(feature_matrix(train, small_config), small_config)
    assert sorted(fitted) == ["isolation_forest", "lof", "ocsvm"]


def test_lof_scores_agree_with_fit_predict_labels(small_config: AnomalyConfig) -> None:
    """Anomaly scores must reproduce fit_predict labeling up to self-inclusion.

    ``fit_predict`` factors exclude each point from its own neighborhood,
    while novelty-style scoring (what we use on the test window) includes it
    — a documented sklearn caveat. The operating-point check: the points
    fit_predict flags must overwhelmingly sit in the top of our score
    ranking, and the two quantities must be strongly rank-correlated.
    """
    df = build_features(generate(small_config), small_config.windows)
    train, _ = split_train_test(df, small_config.train_frac)
    x_train = feature_matrix(train, small_config)
    fitted = fit_models(x_train, small_config)
    lof = fitted["lof"]
    labels = lof.fit_predict(x_train)  # -1 = outlier per spec (novelty=False)
    scores = anomaly_scores(lof, "lof", x_train)

    outlier_idx = np.flatnonzero(labels == -1)
    top = np.argsort(scores)[-len(outlier_idx) :]
    overlap = len(np.intersect1d(top, outlier_idx)) / len(outlier_idx)
    assert overlap >= 0.8

    def ranks(a: np.ndarray) -> np.ndarray:
        order = np.argsort(np.argsort(a))
        return order.astype(float)

    corr = np.corrcoef(ranks(scores), ranks(-lof.negative_outlier_factor_))[0, 1]
    assert corr > 0.9


def test_isolation_forest_scores_rank_injected_anomalies_higher(
    small_config: AnomalyConfig,
) -> None:
    df = build_features(generate(small_config), small_config.windows)
    train, test = split_train_test(df, small_config.train_frac)
    fitted = fit_models(feature_matrix(train, small_config), small_config)
    scores = anomaly_scores(
        fitted["isolation_forest"], "isolation_forest", feature_matrix(test, small_config)
    )
    y = test["is_anomaly"].to_numpy()
    assert scores[y].mean() > scores[~y].mean()


def test_model_persistence_roundtrip(small_config: AnomalyConfig) -> None:
    df = build_features(generate(small_config), small_config.windows)
    train, test = split_train_test(df, small_config.train_frac)
    fitted = fit_models(feature_matrix(train, small_config), small_config)
    save_models(fitted, small_config)
    x_test = feature_matrix(test, small_config)
    for name, model in fitted.items():
        loaded = load_model(name, small_config)
        np.testing.assert_allclose(
            anomaly_scores(model, name, x_test), anomaly_scores(loaded, name, x_test)
        )


def test_load_model_missing_artifact(small_config: AnomalyConfig) -> None:
    with pytest.raises(FileNotFoundError):
        load_model("lof", small_config)
