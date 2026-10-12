"""Feature engineering: raw signals + rolling aggregates, all in polars.

For each telemetry signal (``cpu``, ``mem``, ``latency_ms``) and each window
size we append a rolling mean and rolling standard deviation. Rows that do not
yet have a full window are dropped, so the feature matrix is complete (no
nulls) — detectors are fit on complete cases only.
"""

from pathlib import Path

import polars as pl
from portfolio_core.logging import get_logger

from anomaly_detection.config import SIGNALS, AnomalyConfig

logger = get_logger(__name__)

META_COLUMNS: tuple[str, ...] = ("ts", "is_anomaly")


def feature_columns(windows: list[int]) -> list[str]:
    """Names of the engineered feature columns for the given windows."""
    return [
        f"{sig}_rmean{w}" if kind == "mean" else f"{sig}_rstd{w}"
        for sig in SIGNALS
        for w in windows
        for kind in ("mean", "std")
    ]


def build_features(df: pl.DataFrame, windows: list[int]) -> pl.DataFrame:
    """Append rolling mean/std per signal and drop the warm-up rows.

    ``min_samples=window_size`` keeps the leading ``max(windows) - 1`` rows as
    null, and the ``drop_nulls`` removes them, guaranteeing a complete matrix.
    """
    exprs = [
        pl.col(sig).rolling_mean(window_size=w, min_samples=w).alias(f"{sig}_rmean{w}")
        for sig in SIGNALS
        for w in windows
    ] + [
        pl.col(sig).rolling_std(window_size=w, min_samples=w).alias(f"{sig}_rstd{w}")
        for sig in SIGNALS
        for w in windows
    ]
    out = df.select(*META_COLUMNS, *SIGNALS, *exprs).drop_nulls()
    logger.info(
        "built %d feature columns from %d rows -> %d complete rows",
        len(feature_columns(windows)),
        df.height,
        out.height,
    )
    return out


def save_features(df: pl.DataFrame, config: AnomalyConfig) -> Path:
    """Persist the feature matrix to parquet."""
    config.features_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(config.features_path)
    logger.info("wrote %s (%d rows)", config.features_path, df.height)
    return config.features_path


def load_features(config: AnomalyConfig) -> pl.DataFrame:
    """Load the feature matrix, building it from raw on first use."""
    if not config.features_path.exists():
        from anomaly_detection.data import load_raw

        save_features(build_features(load_raw(config), config.windows), config)
    return pl.read_parquet(config.features_path)
