"""Training-path invariants on the synthetic twin (offline, deterministic)."""

import numpy as np
from model_serving.config import MLPConfig
from model_serving.data import TARGET_COL, make_synthetic_frame, split_windows
from model_serving.features import apply_split, build_features
from model_serving.mlp import MLPRegressor


def _toy_frame() -> tuple[object, object, object, object, object]:
    cfg = MLPConfig(hidden_dims=[8], embed_dim=4, max_epochs=4, patience=2, batch_size=64)
    df = make_synthetic_frame(seed=3, n_days=40)
    windows = split_windows(len(df), val_weeks=1, test_weeks=1)
    featured = build_features(df, [1, 24, 168])
    train_df, val_df, test_df = apply_split(featured, windows, 168)
    numeric = ["temp", "hum", "windspeed"]
    return cfg, train_df, val_df, test_df, numeric


def test_fit_is_deterministic_for_a_fixed_seed() -> None:
    cfg, train_df, val_df, _, numeric = _toy_frame()
    cols = ["hour", *numeric]
    common = dict(
        X_train=train_df[cols],
        y_train=train_df[TARGET_COL].astype(float),
        X_val=val_df[cols],
        y_val=val_df[TARGET_COL].astype(float),
        numeric_cols=numeric,
    )
    a = MLPRegressor(cfg, seed=11).fit(**common)
    b = MLPRegressor(cfg, seed=11).fit(**common)
    np.testing.assert_array_equal(a.predict(train_df[cols]), b.predict(train_df[cols]))
    assert a.history.train_loss == b.history.train_loss


def test_scaler_uses_train_statistics_only() -> None:
    cfg, train_df, _, _, numeric = _toy_frame()
    cols = ["hour", *numeric]
    reg = MLPRegressor(cfg, seed=11)
    reg.fit(
        train_df[cols],
        train_df[TARGET_COL].astype(float),
        train_df[cols].iloc[:50],
        train_df[TARGET_COL].astype(float).iloc[:50],
        numeric,
    )
    expected_mean = train_df[numeric].to_numpy(dtype=np.float64).mean(axis=0)
    expected_std = train_df[numeric].to_numpy(dtype=np.float64).std(axis=0) + 1e-8
    np.testing.assert_allclose(reg.x_mean, expected_mean)
    np.testing.assert_allclose(reg.x_std, expected_std)


def test_split_drops_only_the_lag_warmup_head() -> None:
    _, train_df, val_df, test_df, _ = _toy_frame()
    n_rows = len(make_synthetic_frame(seed=3, n_days=40))
    windows = split_windows(n_rows, 1, 1)
    assert len(train_df) == windows.n_train - 168
    assert len(val_df) == windows.n_val
    assert len(test_df) == windows.n_test
    assert not train_df["cnt_lag_168h"].isna().any()
