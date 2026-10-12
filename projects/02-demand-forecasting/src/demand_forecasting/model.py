"""Global per-series forecasting models (one-hot series identity).

Four models trained/evaluated on the pooled modelling frame:
- ``naive_mean``: global train-mean predictor — the "how hard can it be" floor.
- ``naive_last``: per-series persistence (yesterday's units, the ``lag_1``
  column) — the standard naive baseline for one-step-ahead forecasting.
- ``ridge``: linear baseline in a sklearn ``Pipeline`` — one-hot series id +
  ``StandardScaler`` on numeric features + :class:`Ridge`.
- ``hgb``: :class:`HistGradientBoostingRegressor` on the same features
  (native handling of one-hot columns, no scaling needed).

Global-with-one-hot was chosen over per-series models: one fitted artefact for
the whole hierarchy, shared strength across series, and trivially extensible to
new series via ``handle_unknown="ignore"`` (see DESIGN.md).
"""

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from portfolio_core.logging import get_logger
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from demand_forecasting.config import ForecastConfig
from demand_forecasting.features import TARGET

logger = get_logger(__name__)

CATEGORICAL_FEATURES = ["series_id"]
NUMERIC_FEATURES = ["t", "dow", "is_weekend", "month", "week", "doy_sin", "doy_cos"]


class NaiveMean:
    """Global train-mean predictor: one number for every series and day."""

    def __init__(self) -> None:
        self._value = 0.0

    def fit(self, x: np.ndarray, y: np.ndarray) -> "NaiveMean":
        """Memorise the training-set mean (the only state this model has)."""
        self._value = float(np.mean(y))
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Predict the train mean everywhere, regardless of series or date."""
        return np.full(x.shape[0], self._value)


class NaiveLast:
    """Per-series persistence: predict yesterday's units (the ``lag_1`` column).

    Honest one-step-ahead naive: the prediction for day *t* is the observed
    demand at *t-1* of the same series, taken from the leakage-safe ``shift``
    feature — no fitting, no future information.
    """

    def __init__(self, lag1_index: int) -> None:
        self._lag1_index = lag1_index

    def fit(self, x: np.ndarray, y: np.ndarray) -> "NaiveLast":
        """Persistence has nothing to learn from the training window."""
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Return the per-series previous-day value for every row."""
        return x[:, self._lag1_index].astype(float)


@dataclass(frozen=True)
class ModelSpec:
    """A named estimator factory plus its feature columns."""

    name: str
    numeric: list[str]
    categorical: list[str]

    def feature_names(self, config: ForecastConfig) -> list[str]:
        return self.numeric + [f"lag_{lag}" for lag in config.lags] + self.categorical

    def build(self, config: ForecastConfig) -> Any:
        """Instantiate the estimator for this spec.

        Columns are selected by position (X is a numpy array from
        :func:`to_xy`): numeric first, then lags, then the categorical id.
        """
        n_num = len(self.numeric) + len(config.lags)
        numeric_idx = list(range(n_num))
        cat_idx = [n_num]  # series_id is always the last column
        if self.name == "naive_mean":
            return NaiveMean()
        if self.name == "naive_last":
            # lag_1 sits directly after the numeric block
            return NaiveLast(lag1_index=len(self.numeric))
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        if self.name == "ridge":
            pre = ColumnTransformer(
                [("num", StandardScaler(), numeric_idx), ("cat", encoder, cat_idx)]
            )
            model: Pipeline = Pipeline(
                [("prep", pre), ("reg", Ridge(alpha=1.0, random_state=None))]
            )
        elif self.name == "hgb":
            pre = ColumnTransformer(
                [("num", "passthrough", numeric_idx), ("cat", encoder, cat_idx)]
            )
            model = Pipeline(
                [
                    ("prep", pre),
                    ("reg", HistGradientBoostingRegressor(max_iter=120, random_state=42)),
                ]
            )
        else:  # pragma: no cover - guarded by model_specs()
            raise ValueError(f"unknown model: {self.name}")
        logger.info("built model %s on %d features", self.name, n_num + len(cat_idx))
        return model


def model_specs() -> list[ModelSpec]:
    """All models, floor first: naives, linear baseline, then the tree ensemble."""
    return [
        ModelSpec(name="naive_mean", numeric=NUMERIC_FEATURES, categorical=CATEGORICAL_FEATURES),
        ModelSpec(name="naive_last", numeric=NUMERIC_FEATURES, categorical=CATEGORICAL_FEATURES),
        ModelSpec(name="ridge", numeric=NUMERIC_FEATURES, categorical=CATEGORICAL_FEATURES),
        ModelSpec(name="hgb", numeric=NUMERIC_FEATURES, categorical=CATEGORICAL_FEATURES),
    ]


def naive_specs() -> list[ModelSpec]:
    """The two naive baselines (the reference floor for improvement claims)."""
    return [s for s in model_specs() if s.name.startswith("naive_")]


def to_xy(
    frame: pl.DataFrame, config: ForecastConfig, spec: ModelSpec
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split the modelling frame into (X, y, dates, series_id) arrays."""
    cols = spec.feature_names(config)
    x_df = frame.select(
        [pl.col(c) if c != "series_id" else pl.col(c).cast(pl.String) for c in cols]
    )
    x = x_df.to_numpy()
    y = frame[TARGET].to_numpy()
    dates = frame["date"].to_numpy()
    series = frame["series_id"].to_numpy()
    return x, y, dates, series


def fit_all(frame: pl.DataFrame, config: ForecastConfig) -> dict[str, Any]:
    """Fit every model on the full history (post-backtest deployment artefacts)."""
    fitted: dict[str, Any] = {}
    for spec in model_specs():
        x, y, _, _ = to_xy(frame, config, spec)
        model = spec.build(config)
        model.fit(x, y)
        fitted[spec.name] = model
        logger.info("fitted %s on %d rows", spec.name, x.shape[0])
    return fitted


def save_models(models: dict[str, Any], path: Path) -> Path:
    """Persist fitted models with pickle (sklearn estimators are picklable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(models, f)
    logger.info("saved %d models -> %s", len(models), path)
    return path


def load_models(path: Path) -> dict[str, Any]:
    """Load models persisted by :func:`save_models`."""
    with open(path, "rb") as f:
        models: dict[str, Any] = pickle.load(f)
    return models
