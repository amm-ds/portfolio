"""Statistical baselines: seasonal-naive exactness, MASE formula, ETS fallback."""

import numpy as np
from demand_forecasting.config import ForecastConfig
from demand_forecasting.evaluate import _fold_mase_parts
from demand_forecasting.model import ETSSeries, to_xy


def _xy(features, config, spec):
    return to_xy(features, config, spec)


def test_seasonal_naive_exactness(features, config: ForecastConfig) -> None:
    """seasonal_naive predictions must equal the lag_7 feature exactly."""
    from demand_forecasting.model import NUMERIC_FEATURES, ModelSpec

    spec = ModelSpec(name="seasonal_naive", numeric=NUMERIC_FEATURES, categorical=["series_id"])
    x, y, _, _ = _xy(features, config, spec)
    lag7_index = len(NUMERIC_FEATURES) + config.lags.index(7)
    model = spec.build(config).fit(x, y)
    np.testing.assert_allclose(model.predict(x), x[:, lag7_index].astype(float))


def test_mase_formula_hand_computed() -> None:
    """MASE = pooled |err| / pooled in-sample seasonal-naive scale."""
    # one series, 10 train points (weekly cycle), 2 val points
    y_train = np.array([10, 12, 9, 11, 10, 12, 9, 11, 10, 12], dtype=float)
    s_train = np.array(["a"] * 10)
    y_val = np.array([10.0, 12.0])
    s_val = np.array(["a", "a"])
    pred = np.array([11.0, 11.0])
    err = y_val - pred
    num, den = _fold_mase_parts(y_train, s_train, y_val, s_val, err, season=7)
    # scale = mean(|y[t] - y[t-7]|) over train = mean(1, 2, 3) = 2.0
    np.testing.assert_allclose(den, 4.0)  # 2 val rows x 2.0 scale each
    np.testing.assert_allclose(num, 2.0)  # |10-11| + |12-11|
    assert num / den == 0.5


def test_mase_excludes_series_without_history() -> None:
    """Val rows whose series has no train history are excluded (scale 0)."""
    y_train = np.array([1.0, 2, 3, 4, 5, 6, 7, 8])
    s_train = np.array(["a"] * 8)
    y_val = np.array([9.0, 100.0])
    s_val = np.array(["a", "ghost"])
    err = y_val - np.array([8.0, 0.0])
    num, den = _fold_mase_parts(y_train, s_train, y_val, s_val, err, season=7)
    # scale for "a" = mean(|8-1|) = 7 over its single in-sample diff
    assert den == 7.0
    assert num == 1.0  # only the "a" row's error


def test_ets_fallback_on_short_history() -> None:
    """Series with < MIN_HISTORY train points fall back to seasonal naive."""
    config = ForecastConfig(n_days=30)
    lag7 = 8 + config.lags.index(7)  # 8 NUMERIC_FEATURES + position in lags
    model = ETSSeries(lag7_index=lag7)
    rng = np.random.default_rng(0)
    n = 4 * 10  # 10 rows per series < MIN_HISTORY (16)
    stores = np.tile(np.array(["s0", "s1", "s2", "s3"]), 10)
    x = np.column_stack([rng.normal(size=(n, 11)), stores])  # 8 numeric + 3 lags
    y = rng.normal(20, 5, n)
    model.fit(x, y)
    assert model._models == {}
    assert len(model._fallback) == 4
    np.testing.assert_allclose(model.predict(x), x[:, lag7].astype(float))


def test_ets_fit_and_forecast() -> None:
    """Enough history → a real Holt-Winters model forecasts the horizon."""
    config = ForecastConfig(n_days=40)
    lag7 = 8 + config.lags.index(7)
    model = ETSSeries(lag7_index=lag7)
    t = np.arange(40)
    y = 20 + 5 * np.sin(2 * np.pi * t / 7) + 0.1 * t
    stores = np.array(["s0"] * 40)
    x = np.column_stack([np.zeros((40, 11)), stores])
    x[:, lag7] = np.roll(y, 7)
    model.fit(x, y)
    assert "s0" in model._models
    assert model._fallback == set()
    # 5 val rows → horizon-5 forecast, finite and near the series level
    xv = np.column_stack([np.zeros((5, 11)), np.array(["s0"] * 5)])
    xv[:, lag7] = y[-7:-2]
    pred = model.predict(xv)
    assert pred.shape == (5,)
    assert np.isfinite(pred).all()
    assert np.abs(pred.mean() - y[-5:].mean()) < 8.0


def test_ets_in_backtest_ladder(features, config: ForecastConfig) -> None:
    """ETS runs through the identical backtest and produces a sane MASE."""
    from demand_forecasting.evaluate import backtest
    from demand_forecasting.model import NUMERIC_FEATURES, ModelSpec

    spec = ModelSpec(name="ets", numeric=NUMERIC_FEATURES, categorical=["series_id"])
    result = backtest(features, config, specs=[spec])
    run = result.runs[0]
    mase = run.get("mase")
    assert mase is not None and np.isfinite(mase.value)
    assert result.pooled_mae("ets") > 0
