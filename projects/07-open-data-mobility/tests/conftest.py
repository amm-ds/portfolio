"""Synthetic fixtures for the mobility tests — strictly no network.

Builds a tiny world (2 zones x 48 hours) as real parquet/csv files under
``tmp_path`` so every stage is exercised against its true on-disk interface.
"""

import gzip
import shutil
from datetime import timedelta
from pathlib import Path

import polars as pl
import pytest
from mobility.config import MobilityConfig

ZONES = pl.DataFrame(
    {
        "location_id": [1, 2],
        "borough": ["Manhattan", "Queens"],
        "zone": ["Midtown Center", "JFK Airport"],
        "service_zone": ["Yellow Zone", "Airports"],
    }
)

#: Two zones x 240 hours (10 days) of hourly timestamps starting 2024-01-01.
#: 240h is the minimum span that exercises lag_168 (7 days) plus a next-hour
#: target while still straddlable across the temporal cutoff.
TIMESTAMPS = pl.datetime_range(
    pl.datetime(2024, 1, 1), pl.datetime(2024, 1, 10, 23), "1h", eager=True
)


def make_trips_frame() -> pl.DataFrame:
    """One trip per zone-hour row (240 trips per zone, 480 total), all valid.

    Column names mimic the raw TLC interface (validate.py does the rename).
    """
    rows = []
    for zid in (1, 2):
        for ts in TIMESTAMPS:
            rows.append(
                {
                    "tpep_pickup_datetime": ts,
                    "tpep_dropoff_datetime": ts + timedelta(minutes=15),
                    "PULocationID": zid,
                    "DOLocationID": zid,
                    "passenger_count": 1,
                    "trip_distance": 3.1,  # miles → ≈ 5.0 km after conversion
                    "fare_amount": 20.0,
                }
            )
    return pl.DataFrame(rows)


def make_zone_hour_demand() -> pl.DataFrame:
    """Curated grain fixture: exactly 2 pickups per (zone, hour) slot."""
    n = len(TIMESTAMPS)
    return pl.DataFrame(
        {
            "zone_id": [1] * n + [2] * n,
            "borough": ["Manhattan"] * n + ["Queens"] * n,
            "ts": pl.concat([TIMESTAMPS, TIMESTAMPS]),
            "pickup_count": [2] * (2 * n),
            "prcp_mm": [0.0] * (2 * n),
            "tmax_c": [10.0] * (2 * n),
            "tmin_c": [0.0] * (2 * n),
            "snow_mm": [0.0] * (2 * n),
        }
    )


def make_noaa_frame(qflag_first_prcp: bool = False) -> pl.DataFrame:
    """Two days of GHCN rows in the long by-station layout (tenths units)."""
    rows = [
        ("USW00094728", 20240101, "PRCP", 0, "", None, "", ""),
        ("USW00094728", 20240101, "SNOW", 0, "", None, "", ""),
        ("USW00094728", 20240101, "TMAX", 100, "", None, "", ""),
        ("USW00094728", 20240101, "TMIN", 0, "", None, "", ""),
        ("USW00094728", 20240102, "PRCP", 55, "", "X" if qflag_first_prcp else None, "", ""),
        ("USW00094728", 20240102, "SNOW", 0, "", None, "", ""),
        ("USW00094728", 20240102, "TMAX", 55, "", None, "", ""),
        ("USW00094728", 20240102, "TMIN", -5, "", None, "", ""),
    ]
    return pl.DataFrame(
        rows,
        schema={
            "station": pl.String,
            "date": pl.Int64,
            "element": pl.String,
            "value": pl.Int64,
            "mflag": pl.String,
            "qflag": pl.String,
            "sflag": pl.String,
            "obs_time": pl.String,
        },
        orient="row",
    )


@pytest.fixture()
def cfg(tmp_path: Path) -> MobilityConfig:
    """Config pointed at a temp workspace with the tiny fixtures on disk."""
    raw = tmp_path / "data" / "raw"
    (raw / "tlc").mkdir(parents=True)
    make_trips_frame().write_parquet(raw / "tlc" / "yellow_tripdata_2024-01.parquet")
    # Zone lookup under its raw TLC header (load_zones does the rename).
    ZONES.rename({"location_id": "LocationID", "borough": "Borough", "zone": "Zone"}).write_csv(
        raw / "taxi_zone_lookup.csv"
    )
    make_noaa_frame().write_csv(tmp_path / "noaa_src.csv", include_header=False)
    with (
        open(tmp_path / "noaa_src.csv", "rb") as f_in,
        gzip.open(raw / "noaa_usw00094728_ghcn_daily.csv.gz", "wb") as f_out,
    ):
        shutil.copyfileobj(f_in, f_out)
    for d in ("validated", "curated", "features"):
        (tmp_path / "data" / d).mkdir(parents=True, exist_ok=True)
    return MobilityConfig(
        months=["2024-01"],
        raw_dir=raw,
        validated_dir=tmp_path / "data" / "validated",
        curated_dir=tmp_path / "data" / "curated",
        features_dir=tmp_path / "data" / "features",
        reports_dir=tmp_path / "reports",
        min_rows_per_month=1,
        freshness_slack_days=21,  # fixture spans Jan 1-10 only
    )


@pytest.fixture()
def curated(cfg: MobilityConfig) -> pl.DataFrame:
    """Persist the curated fixtures so feature/evaluate stages can read them."""
    make_zone_hour_demand().write_parquet(cfg.zone_hour_demand_path)
    ZONES.select(["location_id", "borough", "zone"]).write_parquet(cfg.zones_path)
    return make_zone_hour_demand()


@pytest.fixture()
def validated(cfg: MobilityConfig) -> MobilityConfig:
    """Run the validate stage (yellow only) so join tests have their input."""
    from mobility.validate import validate_month

    validate_month(cfg.months[0], cfg, color="yellow")
    return cfg
