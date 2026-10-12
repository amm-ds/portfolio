"""Modeling: three sklearn unsupervised detectors fit on the train window only.

All detectors expose a uniform convention here: ``anomaly_scores`` returns a
higher-is-more-anomalous score. Models are persisted with joblib so the
evaluate stage scores the held-out test window without refitting.
"""

from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
import polars as pl
from portfolio_core.logging import get_logger
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM

from anomaly_detection.config import ALLOWED_MODELS, AnomalyConfig
from anomaly_detection.features import feature_columns

logger = get_logger(__name__)


def split_train_test(df: pl.DataFrame, train_frac: float) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Time-ordered split: the first ``train_frac`` of rows are train."""
    n_train = int(df.height * train_frac)
    if not 0 < n_train < df.height:
        raise ValueError(f"train_frac={train_frac} yields an empty split for {df.height} rows")
    return df.head(n_train), df.tail(df.height - n_train)


def feature_matrix(df: pl.DataFrame, config: AnomalyConfig) -> np.ndarray:
    """Numeric feature matrix (raw signals + rolling aggregates), row-ordered."""
    cols = list(feature_columns(config.windows))
    return df.select(cols).to_numpy()


def make_model(name: str, config: AnomalyConfig) -> Any:
    """Instantiate one detector with config-driven hyperparameters."""
    if name == "isolation_forest":
        return IsolationForest(
            n_estimators=config.n_estimators,
            contamination=config.contamination,
            random_state=config.seed,
            n_jobs=-1,
        )
    if name == "lof":
        return LocalOutlierFactor(
            n_neighbors=config.lof_neighbors, contamination=config.contamination, novelty=False
        )
    if name == "ocsvm":
        return OneClassSVM(nu=config.ocsvm_nu or config.contamination, kernel="rbf", gamma="scale")
    raise ValueError(f"unknown model {name!r}; expected one of {ALLOWED_MODELS}")


def fit_models(x_train: np.ndarray, config: AnomalyConfig) -> dict[str, Any]:
    """Fit every configured detector on the train window only.

    LOF runs with ``novelty=False`` per spec, so its train-time labels come
    from ``fit_predict``; the other detectors use plain ``fit``.
    """
    fitted: dict[str, Any] = {}
    for name in config.models:
        logger.info("fitting %s on %d train rows", name, x_train.shape[0])
        model = make_model(name, config)
        if isinstance(model, LocalOutlierFactor):
            model.fit_predict(x_train)
        else:
            model.fit(x_train)
        fitted[name] = model
    return fitted


def _lof_test_scores(model: LocalOutlierFactor, x: np.ndarray) -> np.ndarray:
    """LOF factors for new points against the fitted training neighborhood.

    Mirrors the body of ``score_samples`` (blocked when ``novelty=False`` in
    sklearn>=1.9) using the attributes a non-novelty fit still exposes:
    ``kneighbors`` for the query graph, ``_local_reachability_density`` for
    the query LRD, and the stored training ``_lrd``. Returns the mean
    lrd-ratio — higher = more anomalous — which is ``-score_samples`` up to
    the constant ``offset_``.
    """
    distances, neighbor_idx = model.kneighbors(x, n_neighbors=model.n_neighbors_)
    x_lrd = model._local_reachability_density(distances, neighbor_idx)
    lrd_ratios = model._lrd[neighbor_idx] / x_lrd[:, np.newaxis]
    return np.mean(lrd_ratios, axis=1)


def anomaly_scores(model: Any, name: str, x: np.ndarray) -> np.ndarray:
    """Higher = more anomalous, uniform across the three detectors.

    ``decision_function`` for IsolationForest/OneClassSVM is oriented so
    positive = inlier, hence the negation. For novelty=False LOF the test
    scores come from :func:`_lof_test_scores`, consistent with the
    train-time ``fit_predict`` labeling.
    """
    if isinstance(model, LocalOutlierFactor):
        return np.asarray(_lof_test_scores(model, x), dtype=float)
    return -np.asarray(model.decision_function(x), dtype=float)


def save_models(fitted: dict[str, Any], config: AnomalyConfig) -> Path:
    """Persist fitted detectors under ``data/models/<name>.joblib``."""
    config.models_dir.mkdir(parents=True, exist_ok=True)
    for name, model in fitted.items():
        path = config.models_dir / f"{name}.joblib"
        joblib.dump(model, path)
        logger.info("wrote %s", path)
    return config.models_dir


def load_model(name: str, config: AnomalyConfig) -> Any:
    """Load a persisted detector."""
    path = config.models_dir / f"{name}.joblib"
    if not path.exists():
        raise FileNotFoundError(f"model artifact missing: {path}; run the train stage first")
    return joblib.load(path)
