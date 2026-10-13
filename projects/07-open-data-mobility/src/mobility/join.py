"""Join stage: validated trips → zone-hour demand, weather, zone reference.

Memory discipline (DESIGN.md §Scale): raw trips are never materialised.
Each validated month is aggregated to the (zone, hour) grain — three orders
of magnitude smaller — before entering memory; the monthly aggregates are
then concatenated and joined against the tiny weather and zone tables.

Also builds ``zones.parquet`` (zone x borough reference) and ``weather.parquet``
(daily GHCN observations, QC-failed values nulled, units converted).
"""

from pathlib import Path

import polars as pl
from portfolio_core.logging import get_logger

from mobility.config import MobilityConfig, get_config
from mobility.schemas import WeatherDay, Zone, ZoneHourDemand

logger = get_logger(__name__)

NOAA_COLUMNS = ["station", "date", "element", "value", "mflag", "qflag", "sflag", "obs_time"]
WEATHER_ELEMENTS = ["PRCP", "SNOW", "TMAX", "TMIN"]


def load_zones(cfg: MobilityConfig) -> pl.DataFrame:
    """Zone lookup validated against the ``Zone`` contract → zones.parquet."""
    raw = cfg.raw_dir / "taxi_zone_lookup.csv"
    if not raw.exists():
        raise FileNotFoundError(f"missing {raw} — run `mobility download`")
    df = (
        pl.scan_csv(raw)
        .select(
            pl.col("LocationID").cast(pl.Int64).alias("location_id"),
            pl.col("Borough").alias("borough"),
            pl.col("Zone").alias("zone"),
        )
        .filter(pl.col("location_id").is_between(1, 265))
        .collect(engine="streaming")
    )
    for row in df.iter_rows(named=True):
        _ = Zone(**row)
    cfg.curated_dir.mkdir(parents=True, exist_ok=True)
    df.write_parquet(cfg.zones_path, compression="zstd")
    logger.info("zones: %d rows -> %s", df.height, cfg.zones_path)
    return df


def load_weather(cfg: MobilityConfig) -> pl.DataFrame:
    """GHCN-Daily wide table: date x (prcp_mm, snow_mm, tmax_c, tmin_c).

    qflag non-empty ⇒ observation failed QC ⇒ null (dataset card). PRCP is
    tenths of mm, TMAX/TMIN tenths of °C, SNOW whole mm (GHCN-Daily units).
    """
    raw = cfg.raw_dir / "noaa_usw00094728_ghcn_daily.csv.gz"
    if not raw.exists():
        raise FileNotFoundError(f"missing {raw} — run `mobility download`")
    long = (
        pl.scan_csv(raw, has_header=False, new_columns=NOAA_COLUMNS)
        .filter(pl.col("element").is_in(WEATHER_ELEMENTS))
        .with_columns(
            date=pl.col("date").cast(pl.String).str.to_date("%Y%m%d"),
            # QC-failed observations become null before any unit conversion.
            value=pl.when(pl.col("qflag").is_null()).then(pl.col("value")),
        )
    )
    wide = (
        long.collect(engine="streaming")
        .pivot(on="element", index="date", values="value")
        .with_columns(
            prcp_mm=(pl.col("PRCP") / 10).round(2),
            snow_mm=pl.col("SNOW").cast(pl.Float64),
            tmax_c=(pl.col("TMAX") / 10).round(2),
            tmin_c=(pl.col("TMIN") / 10).round(2),
        )
        .drop(["PRCP", "SNOW", "TMAX", "TMIN"])
        .sort("date")
    )
    for row in wide.iter_rows(named=True):
        _ = WeatherDay(**row)
    cfg.curated_dir.mkdir(parents=True, exist_ok=True)
    wide.write_parquet(cfg.weather_path, compression="zstd")
    logger.info("weather: %d days -> %s", wide.height, cfg.weather_path)
    return wide


def _monthly_zone_hours(month_path: Path, cfg: MobilityConfig) -> pl.DataFrame:
    """Aggregate one validated month to (zone, hour) pickup counts."""
    valid_zones = pl.scan_parquet(cfg.zones_path).select("location_id")
    return (
        pl.scan_parquet(month_path)
        .filter(
            pl.col("duration_min").is_between(cfg.min_duration_min, cfg.max_duration_min),
        )
        .join(valid_zones, left_on="pulocation_id", right_on="location_id", how="semi")
        .join(valid_zones, left_on="dolocation_id", right_on="location_id", how="semi")
        .with_columns(ts=pl.col("pickup_ts").dt.truncate("1h").cast(pl.Datetime("us")))
        .group_by(["pulocation_id", "ts"])
        .agg(pl.len().alias("pickup_count"))
        .collect(engine="streaming")
    )


def build_zone_hour_demand(cfg: MobilityConfig | None = None) -> pl.DataFrame:
    """All months → curated zone-hour demand joined with weather + borough."""
    cfg = cfg or get_config()
    zones = load_zones(cfg)
    weather = load_weather(cfg)

    monthly_paths = sorted(cfg.validated_dir.glob("*.parquet"))
    if not monthly_paths:
        raise FileNotFoundError(f"no validated months in {cfg.validated_dir}")
    demand = _assemble_demand(monthly_paths, cfg, zones, weather, cfg.months)
    demand.write_parquet(cfg.zone_hour_demand_path, compression="zstd")
    logger.info(
        "zone_hour_demand: %d rows, %d zones, %s -> %s",
        demand.height,
        demand["zone_id"].n_unique(),
        demand["ts"].min(),
        cfg.zone_hour_demand_path,
    )

    green_paths = sorted((cfg.validated_dir / "green").glob("*.parquet"))
    if green_paths:
        green = _assemble_demand(green_paths, cfg, zones, weather, cfg.green_months)
        green.write_parquet(cfg.green_zone_hour_demand_path, compression="zstd")
        logger.info(
            "green_zone_hour_demand: %d rows, %d zones -> %s",
            green.height,
            green["zone_id"].n_unique(),
            cfg.green_zone_hour_demand_path,
        )
    else:
        logger.info("no validated green months — skipping green demand table")
    return demand


def _assemble_demand(
    monthly_paths: list[Path],
    cfg: MobilityConfig,
    zones: pl.DataFrame,
    weather: pl.DataFrame,
    months: list[str],
) -> pl.DataFrame:
    """Aggregate validated months onto the full zone x hour grid + weather."""
    frames = [_monthly_zone_hours(p, cfg) for p in monthly_paths]
    pickups = (
        pl.concat(frames, how="vertical")
        .group_by(["pulocation_id", "ts"])
        .agg(pl.col("pickup_count").sum())
    )

    # Reindex onto the complete zone x hour grid. Sparse zones (airports,
    # suburbs) have hours with zero pickups; without explicit zero rows the
    # feature stage's shift() would treat "previous observed hour" as t-1h
    # and misalign the lags.
    if pickups.height > 0:
        ts_min, ts_max = pickups.select(
            pl.min("ts").alias("ts_min"), pl.max("ts").alias("ts_max")
        ).row(0)
    else:  # no surviving trips: keep the configured months' full hour range
        from datetime import datetime, timedelta

        first = months[0].split("-")
        last = months[-1].split("-")
        ts_min = datetime(int(first[0]), int(first[1]), 1)
        end_month = 1 if last[1] == "12" else int(last[1]) + 1
        end_year = int(last[0]) + (1 if last[1] == "12" else 0)
        ts_max = datetime(end_year, end_month, 1) - timedelta(hours=1)
    hours = pl.DataFrame(
        {"ts": pl.datetime_range(ts_min, ts_max, "1h", eager=True, time_unit="us")}
    )
    zone_ids = pl.DataFrame({"zone_id": zones["location_id"]})
    grid = zone_ids.join(hours, how="cross")
    demand = (
        grid.join(
            pickups.rename({"pulocation_id": "zone_id"}),
            on=["zone_id", "ts"],
            how="left",
        )
        .with_columns(pickup_count=pl.col("pickup_count").fill_null(0).cast(pl.Int64))
        .join(
            zones.select(["location_id", "borough"]),
            left_on="zone_id",
            right_on="location_id",
        )
        .with_columns(date=pl.col("ts").dt.date())
        .join(weather, on="date", how="left")
        .drop("date")
        .sort(["zone_id", "ts"])
    )
    for row in demand.head(200).iter_rows(named=True):
        _ = ZoneHourDemand(**row)
    cfg.curated_dir.mkdir(parents=True, exist_ok=True)
    return demand


def join_all(cfg: MobilityConfig | None = None) -> pl.DataFrame:
    """Join stage entry point (zones + weather rebuilt, then the fact table)."""
    return build_zone_hour_demand(cfg)
