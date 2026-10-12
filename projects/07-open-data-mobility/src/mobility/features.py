"""Feature engineering on the curated zone-hour grain.

Target definition (DESIGN.md): **next-hour pickups** — the row at ``ts``
predicts demand in the hour starting at ``ts + 1h`` (``target =
pickup_count.shift(-1)`` within zone). Everything on the row precedes the
prediction instant, so no leakage.

- Lag features [1, 2, 24, 168] via vectorised ``shift().over(zone)`` — no
  Python loops, no cross-zone leakage (windowed per zone).
- Calendar features from ``ts`` (hour, day-of-week, month).
- Weather columns pass through from the join stage.
- The temporal cutoff is a pure ``ts`` predicate: train = before
  ``train_cutoff``, test = after. No random split anywhere.
"""

import polars as pl
from portfolio_core.logging import get_logger

from mobility.config import MobilityConfig, get_config
from mobility.schemas import DemandRow

logger = get_logger(__name__)

FEATURE_COLUMNS = [
    "lag_1",
    "lag_2",
    "lag_24",
    "lag_168",
    "hour",
    "day_of_week",
    "month",
    "prcp_mm",
    "tmax_c",
    "tmin_c",
    "snow_mm",
]


def _with_features(demand: pl.LazyFrame, cfg: MobilityConfig) -> pl.LazyFrame:
    sort = demand.sort(["zone_id", "ts"])
    lag_exprs = [
        pl.col("pickup_count").shift(lag).over("zone_id").alias(f"lag_{lag}") for lag in cfg.lags
    ]
    return sort.with_columns(
        [
            *lag_exprs,
            pl.col("pickup_count").shift(-1).over("zone_id").alias("target"),
            pl.col("ts").dt.hour().alias("hour"),
            pl.col("ts").dt.weekday().alias("day_of_week"),
            pl.col("ts").dt.month().alias("month"),
        ]
    ).drop_nulls(subset=[f"lag_{lag}" for lag in cfg.lags] + ["target"])


def build_features(cfg: MobilityConfig | None = None) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Split the feature matrix at the temporal cutoff → train/test parquet."""
    cfg = cfg or get_config()
    if not cfg.zone_hour_demand_path.exists():
        raise FileNotFoundError(f"missing {cfg.zone_hour_demand_path} — run `mobility join`")

    feats = (
        _with_features(pl.scan_parquet(cfg.zone_hour_demand_path), cfg)
        .drop("pickup_count")  # superseded by target; keeps the contract strict
        .collect(engine="streaming")
    )
    for row in feats.head(200).iter_rows(named=True):
        _ = DemandRow(**row)

    train = feats.filter(
        pl.col("ts")
        < pl.datetime(cfg.train_cutoff.year, cfg.train_cutoff.month, cfg.train_cutoff.day)
    )
    test = feats.filter(
        pl.col("ts")
        >= pl.datetime(cfg.train_cutoff.year, cfg.train_cutoff.month, cfg.train_cutoff.day)
    )

    cfg.features_dir.mkdir(parents=True, exist_ok=True)
    train.write_parquet(cfg.features_dir / "train.parquet", compression="zstd")
    test.write_parquet(cfg.features_dir / "test.parquet", compression="zstd")
    logger.info(
        "features: train %d rows (< %s), test %d rows (>= %s), %d feature cols",
        train.height,
        cfg.train_cutoff,
        test.height,
        cfg.train_cutoff,
        len(FEATURE_COLUMNS),
    )
    return train, test
