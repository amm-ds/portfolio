"""Custom sklearn transformers, fully encapsulated inside the Pipeline.

Both transformers are plain ``BaseEstimator``/``TransformerMixin`` subclasses
so they compose with ``Pipeline``, ``ColumnTransformer``, ``GridSearchCV`` and
``permutation_importance`` without any leakage-prone preprocessing outside the
fitted estimator.
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_array, check_is_fitted

FloatArray = NDArray[np.float64]


class OutlierCapper(BaseEstimator, TransformerMixin):  # type: ignore[misc]
    """Clip numeric features at train-time quantiles (defaults: 1% / 99%).

    Caps are learned per column with ``np.nanquantile`` during ``fit`` and
    applied with ``np.clip`` during ``transform`` — the deliberate 9_999.0
    charge outlier in the synthetic churn data can therefore never influence
    scaling or the model.
    """

    def __init__(self, quantile_low: float = 0.01, quantile_high: float = 0.99) -> None:
        self.quantile_low = quantile_low
        self.quantile_high = quantile_high

    def fit(self, X: Any, y: Any = None) -> "OutlierCapper":
        """Learn per-column cap values from the training data."""
        X_ = check_array(X, dtype="float64", ensure_all_finite="allow-nan")
        if not 0.0 < self.quantile_low < self.quantile_high < 1.0:
            raise ValueError("require 0 < quantile_low < quantile_high < 1")
        self.lower_caps_ = np.nanquantile(X_, self.quantile_low, axis=0)
        self.upper_caps_ = np.nanquantile(X_, self.quantile_high, axis=0)
        self.n_features_in_ = X_.shape[1]
        return self

    def transform(self, X: Any) -> FloatArray:
        """Clip values outside the learned caps."""
        check_is_fitted(self)
        X_ = check_array(X, dtype="float64", ensure_all_finite="allow-nan")
        out: FloatArray = np.clip(X_, self.lower_caps_, self.upper_caps_)
        return out

    def get_feature_names_out(self, input_features: Any = None) -> Any:
        """Capper is a passthrough: feature names are unchanged."""
        return input_features


class MissingValueIndicator(BaseEstimator, TransformerMixin):  # type: ignore[misc]
    """Append ``<col>_was_missing`` 0/1 flags; original columns pass through.

    Flags are computed *before* imputation so the model can learn whether
    "missing" itself is signal (e.g. unreported support calls). Selecting a
    subset of columns is supported via 0-based indices, but the default
    (all columns) is what the churn pipeline uses.
    """

    def __init__(self, columns: list[int] | None = None) -> None:
        self.columns = columns

    def fit(self, X: Any, y: Any = None) -> "MissingValueIndicator":
        """Resolve the column indices that get indicator flags."""
        X_ = check_array(X, dtype="float64", ensure_all_finite="allow-nan")
        cols = self.columns if self.columns is not None else list(range(X_.shape[1]))
        if any(c < 0 or c >= X_.shape[1] for c in cols):
            raise ValueError(f"columns out of bounds for input with shape {X_.shape}")
        self.columns_ = list(cols)
        self.n_features_in_ = X_.shape[1]
        return self

    def transform(self, X: Any) -> FloatArray:
        """Horizontally stack the passthrough input with 0/1 missing flags."""
        check_is_fitted(self)
        X_ = check_array(X, dtype="float64", ensure_all_finite="allow-nan")
        flags = np.isnan(X_[:, self.columns_]).astype(float)
        return np.hstack([X_, flags])

    def get_feature_names_out(self, input_features: Any = None) -> Any:
        """Original names plus ``<name>_was_missing`` for flagged columns."""
        check_is_fitted(self)
        if input_features is None:
            raise ValueError("input_features is required to name the indicator columns")
        names = list(input_features)
        return np.array([*names, *(f"{names[c]}_was_missing" for c in self.columns_)])
