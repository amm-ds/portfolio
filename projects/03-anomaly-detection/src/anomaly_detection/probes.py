"""Wave-7 probes that are not part of the core run ladder.

- :func:`residual_probe` — do rolling-median residual features de-cluster the
  injected anomaly signature? Trains the same detector on base vs.
  residual-augmented features and reports ranking quality plus a k-NN
  distance de-clustering statistic for both spaces.
"""

import json
from typing import Any

import numpy as np
from portfolio_core.logging import get_logger
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neighbors import NearestNeighbors

from anomaly_detection.config import AnomalyConfig
from anomaly_detection.data import load_raw
from anomaly_detection.features import build_features
from anomaly_detection.model import feature_matrix, split_train_test

logger = get_logger(__name__)


def _fit_score(
    config: AnomalyConfig, residuals: bool
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Fit IsolationForest on the train window of the given feature space.

    Returns (test scores, test labels, train matrix, test matrix).
    """
    df = build_features(load_raw(config), config.windows, residuals=residuals)
    train, test = split_train_test(df, config.train_frac)
    model = IsolationForest(
        n_estimators=config.n_estimators,
        contamination=config.contamination,
        random_state=config.seed,
        n_jobs=-1,
    )
    x_train = feature_matrix(train, config, residuals=residuals)
    x_test = feature_matrix(test, config, residuals=residuals)
    model.fit(x_train)
    return (
        -model.decision_function(x_test),
        test["is_anomaly"].to_numpy().astype(int),
        x_train,
        x_test,
    )


def _knn_stats(
    x_train: np.ndarray, x_test: np.ndarray, y_test: np.ndarray, k: int = 20
) -> dict[str, float]:
    """Mean k-NN distance (against train) for anomalies vs. normals."""
    nn = NearestNeighbors(n_neighbors=k).fit(x_train)
    dist, _ = nn.kneighbors(x_test)
    kd = dist[:, -1]
    return {
        "knn_k": k,
        "anomaly_mean_kdist": float(kd[y_test == 1].mean()),
        "normal_mean_kdist": float(kd[y_test == 0].mean()),
    }


def residual_probe(config: AnomalyConfig) -> dict[str, Any]:
    """Compare base rolling features vs. +rolling-median residual features."""
    base_scores, y_test, base_train, base_test = _fit_score(config, residuals=False)
    res_scores, y_test_r, res_train, res_test = _fit_score(config, residuals=True)
    assert np.array_equal(y_test, y_test_r)

    result: dict[str, Any] = {
        "detector": "isolation_forest",
        "n_test": len(y_test),
        "prevalence": float(y_test.mean()),
        "base": {
            "n_features": int(base_train.shape[1]),
            "roc_auc": float(roc_auc_score(y_test, base_scores)),
            "pr_auc": float(average_precision_score(y_test, base_scores)),
            **_knn_stats(base_train, base_test, y_test),
        },
        "with_residuals": {
            "n_features": int(res_train.shape[1]),
            "roc_auc": float(roc_auc_score(y_test, res_scores)),
            "pr_auc": float(average_precision_score(y_test, res_scores)),
            **_knn_stats(res_train, res_test, y_test),
        },
    }
    verdict = (
        "residuals improved ranking"
        if result["with_residuals"]["roc_auc"] > result["base"]["roc_auc"]
        else "residuals did not improve ranking"
    )
    result["verdict"] = verdict
    logger.info(
        "residual probe: base AUC=%.4f -> with residuals AUC=%.4f (%s)",
        result["base"]["roc_auc"],
        result["with_residuals"]["roc_auc"],
        verdict,
    )
    return result


def run_residual_probe(config: AnomalyConfig) -> dict[str, Any]:
    """Probe stage: run and persist ``reports/residual_probe.json``."""
    result = residual_probe(config)
    out = config.reports_path / "residual_probe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    logger.info("wrote %s", out)
    return result
