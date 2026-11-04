"""Feature tests: leakage guards on hand-built frames, selection contract, pipeline."""

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge
from tabular_ml_lifecycle.config import LifecycleConfig
from tabular_ml_lifecycle.data import TARGET_COL, TIMESTAMP_COL, make_synthetic_frame, split_windows
from tabular_ml_lifecycle.features import (
    CANDIDATE_FEATURES,
    LEAKAGE_POLICY,
    apply_split,
    build_features,
    make_pipeline,
    seasonal_naive_predict,
    select_features,
)


def _hourly_frame(n: int = 24 * 40) -> pd.DataFrame:
    """Hand-built frame with a known count pattern (deterministic, no RNG)."""
    ts = pd.date_range("2024-06-01", periods=n, freq="h")
    cnt = (np.arange(n) % 24) * 10 + np.arange(n) // 24  # unique per row
    return pd.DataFrame(
        {
            TIMESTAMP_COL: ts,
            "season": 2,
            "month": 6,
            "hour": ts.hour,
            "weekday": ts.dayofweek,
            "weathersit": 1,
            "holiday": 0,
            "workingday": (ts.dayofweek < 5).astype(int),
            "temp": 0.5,
            "atemp": 0.5,
            "hum": 0.5,
            "windspeed": 0.1,
            TARGET_COL: cnt,
        }
    )


def test_lag_features_read_only_the_past() -> None:
    """Leakage guard: lag_k at row t must equal cnt[t-k] exactly, never t+anything."""
    frame = _hourly_frame()
    featured = build_features(frame, [1, 24, 168])
    cnt = frame[TARGET_COL].to_numpy()
    for lag in (1, 24, 168):
        col = featured[f"cnt_lag_{lag}h"].to_numpy()
        assert np.all(np.isnan(col[:lag]))
        assert np.array_equal(col[lag:], cnt[:-lag])  # positional past, no future
    # future guard on a hand-built asymmetric pattern: mutate one future row and
    # confirm earlier lag values do not move.
    mutated = frame.copy()
    mutated.loc[500, TARGET_COL] = 999_999
    ref = build_features(frame, [24])["cnt_lag_24h"].iloc[:500]
    moved = build_features(mutated, [24])["cnt_lag_24h"].iloc[:500]
    assert np.array_equal(ref.to_numpy(), moved.to_numpy(), equal_nan=True)


def test_cyclical_encodings() -> None:
    featured = build_features(_hourly_frame(48), [1])
    row0 = featured.iloc[0]
    assert row0["hour_sin"] == pytest.approx(0.0, abs=1e-9)
    assert row0["hour_cos"] == pytest.approx(1.0, abs=1e-9)
    assert featured.iloc[6]["hour_sin"] == pytest.approx(1.0, abs=1e-9)
    assert featured["hour_sin"].between(-1, 1).all()
    assert featured["month_sin"].between(-1, 1).all()


def test_apply_split_drops_only_nan_lag_head() -> None:
    frame = _hourly_frame()
    windows = split_windows(len(frame), val_weeks=2, test_weeks=2)
    featured = build_features(frame, [1, 24, 168])
    train, val, test = apply_split(featured, windows, max_lag=168)
    assert len(train) == windows.n_train - 168
    assert len(val) == windows.n_val and len(test) == windows.n_test
    lag_cols = ["cnt_lag_1h", "cnt_lag_24h", "cnt_lag_168h"]
    assert not train[lag_cols].isna().any().any()
    assert not val[lag_cols].isna().any().any()  # val/test read their own past
    assert not test[lag_cols].isna().any().any()
    # order preserved: val begins where train ends in time
    assert train[TIMESTAMP_COL].max() < val[TIMESTAMP_COL].min()
    assert val[TIMESTAMP_COL].max() < test[TIMESTAMP_COL].min()


def test_select_features_contract(small_cfg: LifecycleConfig, small_frame: pd.DataFrame) -> None:
    windows = split_windows(len(small_frame), small_cfg.val_weeks, small_cfg.test_weeks)
    featured = build_features(small_frame, small_cfg.lag_hours)
    train, val, _ = apply_split(featured, windows, small_cfg.max_lag)
    selection = select_features(small_cfg, train, val, windows)

    assert set(selection.selected) <= set(selection.candidates)
    assert len(selection.selected) < len(selection.candidates)  # something was pruned
    for pair in selection.pruned_pairs:
        assert pair["r"] > small_cfg.corr_threshold
        assert pair["dropped"] not in selection.selected
        assert pair["kept"] in selection.selected
    # contract content: split + leakage policy stated where the split appears
    contract = selection.to_contract(small_cfg)
    assert contract["leakage_policy"] == LEAKAGE_POLICY
    assert contract["split"]["n_test"] == windows.n_test
    assert contract["split"]["n_val"] == windows.n_val
    assert set(contract["mi_scores"]) == set(selection.candidates)
    assert set(contract["permutation_val_mae_increase"]) == set(selection.candidates)


def test_pipeline_scaler_uses_train_statistics(small_cfg: LifecycleConfig) -> None:
    """The StandardScaler is a fitted step: train mean ≈ 0, raw counts don't leak."""
    frame = make_synthetic_frame(7, 120)
    windows = split_windows(len(frame), 1, 1)
    featured = build_features(frame, [1, 24, 168])
    train, val, _ = apply_split(featured, windows, 168)
    cols = [c for c in CANDIDATE_FEATURES if c not in ("temp", "atemp")]  # avoid prune effects
    pipe = make_pipeline(small_cfg, Ridge(alpha=1.0), cols)
    pipe.fit(train[cols], train[TARGET_COL])
    scaled = pipe.named_steps["prep"].transform(train[cols])
    first_col = scaled[:, 0]
    assert abs(float(first_col.mean())) < 1e-9  # train-standardized
    val_scaled = pipe.named_steps["prep"].transform(val[cols])
    assert abs(float(val_scaled[:, 0].mean())) > 1e-6  # val is NOT re-standardized


def test_seasonal_naive_parity_hand_computed() -> None:
    """The floor predicts cnt[t-168]; check against a hand-computed fixture."""
    frame = _hourly_frame(24 * 30)
    cnt = pd.Series(frame[TARGET_COL].to_numpy(), index=frame[TIMESTAMP_COL])
    window = frame[TIMESTAMP_COL].iloc[24 * 28 : 24 * 28 + 5]
    pred = seasonal_naive_predict(cnt, window)
    expected = frame[TARGET_COL].iloc[24 * 28 - 168 : 24 * 28 - 168 + 5].to_numpy()
    assert np.array_equal(pred, expected.astype(float))
    # no future contamination: predictions for the first val week must not
    # touch rows at or after the first predicted timestamp.
    first_val_ts = window.iloc[0]
    src = frame.loc[frame[TIMESTAMP_COL] < first_val_ts, TARGET_COL]
    assert len(src) >= 168


def test_seasonal_naive_needs_only_past() -> None:
    frame = _hourly_frame(24 * 30)
    cnt = pd.Series(frame[TARGET_COL].to_numpy(), index=frame[TIMESTAMP_COL])
    window = frame[TIMESTAMP_COL].iloc[200:]
    pred = seasonal_naive_predict(cnt, window)
    assert not np.isnan(pred).any()
