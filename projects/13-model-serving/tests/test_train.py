"""Training-path invariants on the synthetic twin (offline, deterministic)."""

import numpy as np
import pandas as pd
from model_serving.config import LGBMConfig, ServingConfig
from model_serving.data import TARGET_COL, make_synthetic_frame, split_windows
from model_serving.features import apply_split, build_features
from model_serving.lgbm import lgbm_estimator


def _toy_frame() -> tuple[ServingConfig, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = ServingConfig(
        data_source="synthetic",
        lgbm=LGBMConfig(n_estimators=40, early_stopping=10, hpo_trials=5, hpo_time_budget_s=60),
    )
    df = make_synthetic_frame(seed=3, n_days=60)
    windows = split_windows(len(df), val_weeks=1, test_weeks=1)
    featured = build_features(df, [1, 24, 168], cfg.lag_mode)
    train_df, val_df, test_df = apply_split(featured, windows, 168)
    return cfg, train_df, val_df, test_df


def test_fit_is_deterministic_for_a_fixed_seed() -> None:
    cfg, train_df, _, _ = _toy_frame()
    cols = ["atemp", "hum", "windspeed"]
    y = train_df[TARGET_COL].astype(float)
    a = lgbm_estimator(cfg, seed=11, learning_rate=0.1).fit(train_df[cols], y)
    b = lgbm_estimator(cfg, seed=11, learning_rate=0.1).fit(train_df[cols], y)
    np.testing.assert_array_equal(a.predict(train_df[cols]), b.predict(train_df[cols]))


def test_split_drops_only_the_lag_warmup_head() -> None:
    _, train_df, val_df, test_df = _toy_frame()
    n_rows = len(make_synthetic_frame(seed=3, n_days=60))
    windows = split_windows(n_rows, 1, 1)
    assert len(train_df) == windows.n_train - 168
    assert len(val_df) == windows.n_val
    assert len(test_df) == windows.n_test
    # the synthetic twin has no missing hours, so timestamp lags are NaN only
    # in the warm-up head apply_split already cut
    assert not train_df["cnt_lag_168h"].isna().any()
