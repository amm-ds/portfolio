"""Lag-feature correctness: exact expected values, per-series shifts."""

from datetime import date, timedelta

import polars as pl
from demand_forecasting.config import ForecastConfig
from demand_forecasting.features import build_features


def _tiny_panel(values: list[int]) -> pl.DataFrame:
    """Single series with known integer demand and consecutive days."""
    dates = pl.date_range(
        pl.date(2024, 1, 1),
        pl.date(2024, 1, 1) + pl.duration(days=len(values) - 1),
        eager=True,
    )
    return pl.DataFrame(
        {
            "date": dates,
            "store": ["store_0"] * len(values),
            "product": ["product_0"] * len(values),
            "units": values,
            "price": [10.0] * len(values),
        }
    )


def test_lag_values_exact() -> None:
    """lag_1/lag_7 must equal the raw series shifted by exactly that many days."""
    units = list(range(1, 21))  # 1..20, so expected lags are trivially checkable
    config = ForecastConfig(n_days=30, n_stores=1, n_products=1, lags=[1, 7])
    frame = build_features(_tiny_panel(units), config)

    assert frame.height == 20 - 7  # first 7 rows dropped (max lag)
    # After sorting by (date, series_id) with a single series, row i is day i+7.
    for i, row in enumerate(frame.iter_rows(named=True)):
        day = i + 7  # 0-based index into the raw units array
        assert row["lag_1"] == float(units[day - 1])
        assert row["lag_7"] == float(units[day - 7])
        assert row["y"] == float(units[day])
        assert row["t"] == day


def test_no_lag_uses_current_row() -> None:
    """Frame starts at day max_lag and every lag is fully defined (no NaNs)."""
    units = [5, 5, 9, 9, 9, 2, 7, 3, 1, 8, 6, 4, 0, 9, 2, 1, 5, 6, 3, 4]
    config = ForecastConfig(n_days=30, n_stores=1, n_products=1, lags=[1, 7, 14])
    frame = build_features(_tiny_panel(units), config)
    assert frame.height == len(units) - config.max_lag  # 20 - 14 = 6
    assert frame["date"].min() == date(2024, 1, 1) + timedelta(days=config.max_lag)
    for lag in config.lags:
        assert frame[f"lag_{lag}"].null_count() == 0


def test_lags_shift_within_series_not_across(panel: pl.DataFrame, config: ForecastConfig) -> None:
    """Each series' lags come from its own history (shift over series_id)."""
    frame = build_features(panel, config)
    one = frame.filter(pl.col("series_id") == "store_0|product_0").sort("date")
    raw = (
        panel.filter((pl.col("store") == "store_0") & (pl.col("product") == "product_0"))
        .sort("date")["units"]
        .to_list()
    )
    lags = one["lag_1"].to_list()
    # frame starts at raw day max_lag (7), so lag_1 starts at raw[max_lag - 1]
    assert lags == [float(v) for v in raw[config.max_lag - 1 : config.max_lag - 1 + len(lags)]]


def test_calendar_features(features: pl.DataFrame) -> None:
    """Calendar features match the date semantics (polars weekday: 1=Mon .. 7=Sun)."""
    first_date = features.sort("date")["date"][0]
    row = features.sort("date").row(0, named=True)
    assert row["dow"] == first_date.weekday() + 1
    assert row["is_weekend"] == int(first_date.weekday() >= 5)
    assert -1.0 <= row["doy_sin"] <= 1.0
    assert -1.0 <= row["doy_cos"] <= 1.0
