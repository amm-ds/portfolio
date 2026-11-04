"""Feature engineering + selection: cyclical calendar encodings, past-only lags,
mutual-information ranking, validation permutation importance, correlated-pair
pruning — all inside a time-based split contract.

Leakage rules enforced here and restated in the feature-selection contract:

- lag features at time t read only rental counts strictly before t; validation
  and test lags legitimately read their own past (information available at
  prediction time), never the future;
- the first ``max(lag_hours)`` training rows lose their NaN lag rows;
- standardization is a fitted sklearn step (train statistics only), never a
  whole-frame transform.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from portfolio_core.plotting import add_takeaway, apply_theme
from sklearn.feature_selection import mutual_info_regression
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from tabular_ml_lifecycle.config import LifecycleConfig
from tabular_ml_lifecycle.data import (
    BINARY_COLS,
    NUMERIC_COLS,
    TARGET_COL,
    SplitWindows,
)

#: Everything a model may see, in one explicit list (the selection contract).
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
#: Columns the StandardScaler fits (counts dominate raw — scale them, not binaries).
SCALED_NUMERIC = [*NUMERIC_COLS, "weathersit", "cnt_lag_1h", "cnt_lag_24h", "cnt_lag_168h"]
PASSTHROUGH = [c for c in CANDIDATE_FEATURES if c not in SCALED_NUMERIC]

LEAKAGE_POLICY = (
    "Lag features at time t read only rental counts strictly before t (pandas "
    "shift); validation and test lags read their own past, which is available "
    "at prediction time — never the future. The first max(lag_hours) training "
    "rows lose their NaN lag rows. Standardization is fitted on the training "
    "window inside the sklearn Pipeline (train statistics only). Lags are "
    "positional over the observed sequence: the UCI series has ~1% missing "
    "hours (January 2011 outages), so a positional 168-step lag is 'same hour "
    "last week' give or take the outage gaps."
)


@dataclass
class FeatureSelection:
    """Selection evidence + the selected set, serialized as the feature contract."""

    candidates: list[str]
    selected: list[str]
    mi_scores: dict[str, float]
    perm_val_mae_increase: dict[str, float]
    pruned_pairs: list[dict[str, Any]]
    windows: dict[str, Any]
    corr_threshold: float
    extra: dict[str, Any] = field(default_factory=dict)

    def to_contract(self, cfg: LifecycleConfig) -> dict[str, Any]:
        """The feature-selection contract every downstream stage validates against."""
        return {
            "dataset_contract": "data/dataset_contract.json",
            "leakage_policy": LEAKAGE_POLICY,
            "split": self.windows,
            "candidates": self.candidates,
            "selected": self.selected,
            "mi_scores": self.mi_scores,
            "permutation_val_mae_increase": self.perm_val_mae_increase,
            "pruned_pairs": self.pruned_pairs,
            "corr_threshold": self.corr_threshold,
            "scaled_numeric": SCALED_NUMERIC,
            "passthrough": PASSTHROUGH,
            "seed": cfg.seed,
            **self.extra,
        }


def build_features(df: pd.DataFrame, lag_hours: list[int]) -> pd.DataFrame:
    """Cyclical hour/weekday/month encodings, calendar binaries, past-only lags."""
    out = df.copy()
    for col, period in (("hour", 24), ("weekday", 7), ("month", 12)):
        angle = 2 * np.pi * out[col].astype(float) / period
        out[f"{col}_sin"] = np.sin(angle)
        out[f"{col}_cos"] = np.cos(angle)
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


def _xy(split_df: pd.DataFrame, features: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    return split_df[features], split_df[TARGET_COL].astype(float)


def make_pipeline(cfg: LifecycleConfig, model: Any, features: list[str] | None = None) -> Pipeline:
    """Standardized numeric + passthrough cyclical/binary features → estimator.

    The scaler is a fitted step (train statistics only), so this Pipeline is
    the whole preprocessing contract — the same one the MLP mirrors with its
    own train-fitted scaler. ``features`` defaults to the full candidate set;
    after correlation pruning it is the selected subset actually present.
    """
    from sklearn.compose import ColumnTransformer

    cols = list(features) if features is not None else list(CANDIDATE_FEATURES)
    scaled = [c for c in SCALED_NUMERIC if c in cols]
    passthrough = [c for c in cols if c not in scaled]
    ct = ColumnTransformer(
        [
            ("num", StandardScaler(), scaled),
            ("pass", "passthrough", passthrough),
        ]
    )
    return Pipeline([("prep", ct), ("model", model)])


def select_features(
    cfg: LifecycleConfig, train: pd.DataFrame, val: pd.DataFrame, windows: SplitWindows
) -> FeatureSelection:
    """MI ranking (train) + permutation importance (ridge on validation) +
    correlated-pair pruning (|r| > threshold keeps the higher-MI member)."""
    X_train, y_train = _xy(train, CANDIDATE_FEATURES)
    X_val, y_val = _xy(val, CANDIDATE_FEATURES)

    mi = mutual_info_regression(X_train, y_train, random_state=cfg.seed)
    mi_scores = {name: float(score) for name, score in zip(CANDIDATE_FEATURES, mi, strict=True)}

    probe = make_pipeline(cfg, Ridge(alpha=cfg.ridge_alpha), list(CANDIDATE_FEATURES))
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
    # Strongest correlations resolve first; the higher-MI member survives each
    # pair (a survivor can still lose to a stronger-correlated, higher-MI peer).
    pruned_pairs: list[dict[str, Any]] = []
    pruned: set[str] = set()
    for r, a, b in sorted(pairs, key=lambda p: p[0], reverse=True):
        if r <= cfg.corr_threshold or a in pruned or b in pruned:
            continue
        drop, keep = (a, b) if mi_scores[a] >= mi_scores[b] else (b, a)
        pruned.add(drop)
        pruned_pairs.append({"dropped": drop, "kept": keep, "r": round(r, 4)})
    selected = [c for c in CANDIDATE_FEATURES if c not in pruned]

    win = {
        "scheme": "time-based",
        "val_weeks": cfg.val_weeks,
        "test_weeks": cfg.test_weeks,
        "n_train": windows.n_train - cfg.max_lag,
        "n_val": windows.n_val,
        "n_test": windows.n_test,
        "note": (
            "test = the final test_weeks of the series (24x7 rows per week), "
            "scored once; val = the val_weeks immediately before it; everything "
            "earlier is training. Windows are contiguous row blocks, strictly "
            "time-ordered, non-overlapping — whole calendar weeks on the "
            "complete synthetic grid, approximately on the real series."
        ),
    }
    return FeatureSelection(
        candidates=list(CANDIDATE_FEATURES),
        selected=selected,
        mi_scores=mi_scores,
        perm_val_mae_increase=perm_scores,
        pruned_pairs=pruned_pairs,
        windows=win,
        corr_threshold=cfg.corr_threshold,
    )


def mi_lollipop_figure(selection: FeatureSelection) -> Any:
    """MI ranking as a lollipop/dot plot (diverse chart types — no all-bar pages)."""
    import plotly.graph_objects as go

    ranked = sorted(selection.mi_scores.items(), key=lambda kv: kv[1])
    names = [k for k, _ in ranked]
    values = [v for _, v in ranked]
    pruned = {p["dropped"] for p in selection.pruned_pairs}
    colors = ["#64748b" if n in pruned else "#2dd4bf" for n in names]
    fig = go.Figure()
    for i, (_name, value) in enumerate(ranked):
        fig.add_scatter(
            x=[0, value, None] if i < len(ranked) - 1 else [0, value],
            y=[i, i, None] if i < len(ranked) - 1 else [i, i],
            mode="lines",
            line={"color": colors[i], "width": 2},
            showlegend=False,
            hoverinfo="skip",
        )
    fig.add_scatter(
        x=values,
        y=list(range(len(names))),
        mode="markers",
        marker={"color": colors, "size": 11},
        name="mutual information",
    )
    apply_theme(fig, height=620)
    fig.update_layout(
        title="Feature ranking — mutual information with hourly rentals",
        xaxis_title="mutual information (nats, training window)",
        margin={"l": 140, "r": 140, "t": 110, "b": 70},
    )
    fig.update_yaxes(
        tickvals=list(range(len(names))),
        ticktext=names,
        autorange="reversed",
    )
    add_takeaway(
        fig,
        f"Grey stems were pruned as the lower-MI member of a correlated pair "
        f"(|r| > {selection.corr_threshold}); lags and temperature carry the signal.",
    )
    return fig


def seasonal_naive_predict(cnt: pd.Series, index: pd.Index, lag: int = 168) -> np.ndarray:
    """Seasonal-naive floor: same hour last week — cnt[t - 168].

    ``cnt`` is the full series in time order; ``index`` picks the rows to
    score (validation or test). Values needed are always strictly in the past.
    """
    values: np.ndarray = cnt.shift(lag).loc[index].to_numpy(dtype=float)
    return values
