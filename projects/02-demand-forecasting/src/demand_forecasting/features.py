"""Leakage-safe feature engineering for the hierarchical panel.

Every feature for day *t* is computable from information available **before**
day *t*: lags use ``shift`` (never the current row), calendar features are
deterministic functions of the date, and the trend counter *t* is the day index.
Rows whose lags are undefined (first ``max(lags)`` days of each series) are
dropped, so no model ever sees a missing or imputed lag.
"""

import math
from pathlib import Path

import polars as pl
from portfolio_core.logging import get_logger

from demand_forecasting.config import DemandSettings, ForecastConfig

logger = get_logger(__name__)

TARGET = "y"


def _calendar_expr() -> list[pl.Expr]:
    """Deterministic date-derived features (known in advance, leakage-free)."""
    date = pl.col("date")
    dow = date.dt.weekday()  # 1=Monday .. 7=Sunday (polars convention)
    return [
        dow.cast(pl.Int8).alias("dow"),
        (dow >= 6).cast(pl.Int8).alias("is_weekend"),
        date.dt.month().cast(pl.Int8).alias("month"),
        date.dt.week().cast(pl.Int8).alias("week"),
        (date.dt.ordinal_day() * math.tau / 365.25).sin().alias("doy_sin"),
        (date.dt.ordinal_day() * math.tau / 365.25).cos().alias("doy_cos"),
    ]


def build_features(panel: pl.DataFrame, config: ForecastConfig) -> pl.DataFrame:
    """Build the modelling frame: one row per series per day with lags + calendar.

    The frame is sorted by (date, series_id) so that a plain positional
    expanding-window split (``TimeSeriesCV`` over row indices) respects time.
    """
    series_id = (pl.col("store") + "|" + pl.col("product")).alias("series_id")
    lag_exprs = [
        pl.col("units").shift(lag).over("series_id").alias(f"lag_{lag}") for lag in config.lags
    ]
    df = (
        panel.with_columns(series_id)
        .with_columns(
            ((pl.col("date") - pl.col("date").min()).dt.total_days()).alias("t"),
            *lag_exprs,
            *_calendar_expr(),
        )
        .with_columns(pl.col("units").cast(pl.Float64).alias(TARGET))
        .drop_nulls(subset=[f"lag_{lag}" for lag in config.lags])
        .sort(["date", "series_id"])
    )
    logger.info(
        "features: %d rows x %d cols, %d series, %s..%s",
        df.height,
        df.width,
        df["series_id"].n_unique(),
        df["date"].min(),
        df["date"].max(),
    )
    return df


def save_features(features: pl.DataFrame, settings: DemandSettings) -> Path:
    """Persist the modelling frame to ``data/features.parquet``."""
    out = settings.data_dir / "features.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    features.write_parquet(out)
    logger.info("wrote %s", out)
    return out
