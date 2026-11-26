"""Feature engineering + selection, vendored from experiment 12's v2 recipe.

Identical mathematics, re-implemented inside this package: cyclical calendar
encodings, date-aware timestamp lags, mutual-information ranking, validation
permutation importance, correlated-pair pruning that keeps the higher-MI
member. The leakage rules are 12's v2 contract, restated in the feature
contract this stage re-derives:

- lag features at time t read only rental counts strictly before t; validation
  and test lags legitimately read their own past, never the future;
- lags join on ``timestamp - h``: the lag reads the count at that exact
  wall-clock hour and is NaN when that hour is missing from the series;
- NaN-lag rows are dropped from train/validation (complete-case); the frozen
  test window keeps every row, its NaN lag cells median-imputed from the
  training window.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_regression
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from model_serving.config import ServingConfig
from model_serving.data import BINARY_COLS, NUMERIC_COLS, TARGET_COL, TIMESTAMP_COL, SplitWindows

#: Everything a model may see, in one explicit list (12's selection contract).
CANDIDATE_FEATURES = [
    *NUMERIC_COLS,
    "weathersit",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
    "month_sin",
    "month_cos",
    *BINARY_COLS,
    "cnt_lag_1h",
    "cnt_lag_24h",
    "cnt_lag_168h",
]
#: Columns the sklearn probe's StandardScaler fits (train statistics only).
SCALED_NUMERIC = [*NUMERIC_COLS, "weathersit", "cnt_lag_1h", "cnt_lag_24h", "cnt_lag_168h"]

LEAKAGE_POLICY = (
    "Lag features at time t read only rental counts strictly before t; "
    "validation and test lags read their own past, which is available at "
    "prediction time — never the future. The first max(lag_hours) training "
    "rows lose their NaN lag rows. Under the committed v2 recipe, lags join "
    "on timestamp minus h (date-aware): the lag reads the count at that exact "
    "wall-clock hour and is NaN when that hour is missing from the series "
    "(the UCI series has 165 missing hours, mostly early 2011 plus a 36-hour "
    "gap on 2012-10-29/30 inside validation). NaN-lag rows are dropped from "
    "train and validation (complete-case); the frozen test window keeps every "
    "row, its NaN lag cells median-imputed from the training window. The v1 "
    "run shifted lags positionally; it is preserved in 12's previous_runs.v1."
)


@dataclass
class FeatureSelection:
    """Selection evidence + the selected set, serialized as the feature contract."""

    candidates: list[str]
    selected: list[str]
    mi_scores: dict[str, float]
    perm_val_mae_increase: dict[str, float]
    pruned_pairs: list[dict[str, Any]]
    corr_threshold: float
    extra: dict[str, Any] = field(default_factory=dict)

    def to_contract(self, cfg: ServingConfig, windows: dict[str, Any]) -> dict[str, Any]:
        """The feature-selection contract the service schema validates against."""
        return {
            "leakage_policy": LEAKAGE_POLICY,
            "split": windows,
            "candidates": self.candidates,
            "selected": self.selected,
            "mi_scores": self.mi_scores,
            "permutation_val_mae_increase": self.perm_val_mae_increase,
            "pruned_pairs": self.pruned_pairs,
            "corr_threshold": self.corr_threshold,
            "model_input": {
                "family": "lightgbm",
                "numeric": self.selected,
            },
            "seed": cfg.seed,
            **self.extra,
        }


def build_features(
    df: pd.DataFrame, lag_hours: list[int], lag_mode: str = "timestamp"
) -> pd.DataFrame:
    """Cyclical hour/weekday/month encodings, calendar binaries, past-only lags.

    ``lag_mode="timestamp"`` (committed v2) joins on ``timestamp - h``: the lag
    reads the count at that exact wall-clock hour and is NaN when that hour is
    missing. ``lag_mode="positional"`` (v1) shifts over the observed sequence.
    """
    out = df.copy()
    for col, period in (("hour", 24), ("weekday", 7), ("month", 12)):
        angle = 2 * np.pi * out[col].astype(float) / period
        out[f"{col}_sin"] = np.sin(angle)
        out[f"{col}_cos"] = np.cos(angle)
    if lag_mode == "timestamp":
        by_ts = out.set_index(TIMESTAMP_COL)[TARGET_COL]  # unique per the DQ gate
        for lag in lag_hours:
            wanted = out[TIMESTAMP_COL] - pd.to_timedelta(lag, unit="h")
            out[f"cnt_lag_{lag}h"] = wanted.map(by_ts)  # NaN for missing hours
    else:
        for lag in lag_hours:
            # shift(k) aligns the count from k steps EARLIER with row t — past only.
            out[f"cnt_lag_{lag}h"] = out[TARGET_COL].shift(lag)
    return out


def apply_split(
    featured: pd.DataFrame, windows: SplitWindows, max_lag: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Cut train/val/test by time; drop only the NaN-lag head of training."""
    train = featured.iloc[windows.train].iloc[max_lag:].reset_index(drop=True)
    val = featured.iloc[windows.val].reset_index(drop=True)
    test = featured.iloc[windows.test].reset_index(drop=True)
    return train, val, test


def apply_nan_lag_policy(
    train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, lag_hours: list[int], lag_mode: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Complete-case train/validation + frozen-test median imputation (v2).

    Timestamp lags are NaN where the reference hour is missing from the
    series. Those rows leave the fitting windows; the frozen test window keeps
    every row, its NaN lag cells median-imputed from the training window so
    every backend sees identical test hours. Positional mode (v1) is a no-op.
    """
    counts = {"train_rows_dropped": 0, "val_rows_dropped": 0, "test_lag_cells_median_imputed": 0}
    if lag_mode != "timestamp":
        return train, val, test, counts
    lag_cols = [f"cnt_lag_{k}h" for k in lag_hours]
    counts["train_rows_dropped"] = int(train[lag_cols].isna().any(axis=1).sum())
    train = train.dropna(subset=lag_cols).reset_index(drop=True)
    counts["val_rows_dropped"] = int(val[lag_cols].isna().any(axis=1).sum())
    val = val.dropna(subset=lag_cols).reset_index(drop=True)
    medians = train[lag_cols].median()
    counts["test_lag_cells_median_imputed"] = int(test[lag_cols].isna().sum().sum())
    test = test.copy()
    test[lag_cols] = test[lag_cols].fillna(medians)
    return train, val, test, counts


def _xy(split_df: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    return split_df[features], split_df[TARGET_COL].astype(float)


def make_probe_pipeline(cfg: ServingConfig, features: list[str]) -> Pipeline:
    """Standardized numeric + passthrough features → ridge probe (12's probe)."""
    from sklearn.compose import ColumnTransformer

    cols = list(features)
    scaled = [c for c in SCALED_NUMERIC if c in cols]
    passthrough = [c for c in cols if c not in scaled]
    ct = ColumnTransformer(
        [
            ("num", StandardScaler(), scaled),
            ("pass", "passthrough", passthrough),
        ]
    )
    return Pipeline([("prep", ct), ("model", Ridge(alpha=cfg.ridge_alpha))])


def select_features(cfg: ServingConfig, train: pd.DataFrame, val: pd.DataFrame) -> FeatureSelection:
    """MI ranking (train) + permutation importance (ridge on validation) +
    correlated-pair pruning (|r| > threshold keeps the higher-MI member).

    Identical recipe to experiment 12's committed v2 run: the only expected
    difference from its committed contract is floating-point noise, and none
    is expected at all on the same pinned data with the same seed.
    """
    X_train, y_train = _xy(train, CANDIDATE_FEATURES)
    X_val, y_val = _xy(val, CANDIDATE_FEATURES)

    mi = mutual_info_regression(X_train, y_train, random_state=cfg.seed)
    mi_scores = {name: float(score) for name, score in zip(CANDIDATE_FEATURES, mi, strict=True)}

    probe = make_probe_pipeline(cfg, list(CANDIDATE_FEATURES))
    probe.fit(X_train, y_train)
    perm = permutation_importance(
        probe, X_val, y_val, scoring="neg_mean_absolute_error", n_repeats=5, random_state=cfg.seed
    )
    perm_scores = {
        name: float(-m) for name, m in zip(CANDIDATE_FEATURES, perm.importances_mean, strict=True)
    }

    corr = X_train.corr().abs()
    pairs = [
        (float(corr.loc[a, b]), a, b)
        for i, a in enumerate(CANDIDATE_FEATURES)
        for b in CANDIDATE_FEATURES[i + 1 :]
    ]
    pruned_pairs: list[dict[str, Any]] = []
    pruned: set[str] = set()
    for r, a, b in sorted(pairs, key=lambda p: p[0], reverse=True):
        if r <= cfg.corr_threshold or a in pruned or b in pruned:
            continue
        if cfg.pruning_rule == "keep_higher_mi":
            drop, keep = (b, a) if mi_scores[a] >= mi_scores[b] else (a, b)
        else:
            drop, keep = (a, b) if mi_scores[a] >= mi_scores[b] else (b, a)
        pruned.add(drop)
        pruned_pairs.append({"dropped": drop, "kept": keep, "r": round(r, 4)})
    selected = [c for c in CANDIDATE_FEATURES if c not in pruned]

    return FeatureSelection(
        candidates=list(CANDIDATE_FEATURES),
        selected=selected,
        mi_scores=mi_scores,
        perm_val_mae_increase=perm_scores,
        pruned_pairs=pruned_pairs,
        corr_threshold=cfg.corr_threshold,
    )
