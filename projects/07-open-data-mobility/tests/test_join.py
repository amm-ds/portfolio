"""Join stage: aggregation correctness, weather pivot, zone reference."""

import gzip
import importlib.util
from datetime import date
from pathlib import Path

import polars as pl
from mobility.config import MobilityConfig
from mobility.join import build_zone_hour_demand, load_weather, load_zones

_spec = importlib.util.spec_from_file_location(
    "mobility_test_helpers", Path(__file__).parent / "conftest.py"
)
assert _spec is not None and _spec.loader is not None
_helpers_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers_mod)
make_noaa_frame = _helpers_mod.make_noaa_frame


def test_zones_reference(cfg: MobilityConfig) -> None:
    zones = load_zones(cfg)
    assert zones.height == 2
    assert set(zones["borough"].to_list()) == {"Manhattan", "Queens"}
    assert cfg.zones_path.exists()


def test_weather_units_and_qflag(cfg: MobilityConfig, tmp_path: Path) -> None:
    src = tmp_path / "noaa.csv"
    make_noaa_frame(qflag_first_prcp=True).write_csv(src, include_header=False)
    # Repoint the raw NOAA file at the fixture (same gz interface).
    import shutil

    with (
        open(src, "rb") as f_in,
        gzip.open(cfg.raw_dir / "noaa_usw00094728_ghcn_daily.csv.gz", "wb") as f_out,
    ):
        shutil.copyfileobj(f_in, f_out)

    weather = load_weather(cfg)
    assert weather.height == 2
    row = weather.filter(pl.col("date") == date(2024, 1, 1)).row(0, named=True)
    assert row == {
        "date": date(2024, 1, 1),
        "prcp_mm": 0.0,
        "snow_mm": 0.0,
        "tmax_c": 10.0,
        "tmin_c": 0.0,
    }
    # 2024-01-02 PRCP (5.5 mm) carries a QC flag → must be null.
    flagged = weather.filter(pl.col("date") == date(2024, 1, 2)).row(0, named=True)
    assert flagged["prcp_mm"] is None
    assert flagged["tmax_c"] == 5.5
    assert flagged["tmin_c"] == -0.5


def test_zone_hour_counts(validated: MobilityConfig) -> None:
    cfg = validated
    """One valid trip per (zone, hour) → grid row per slot with count 1."""
    demand = build_zone_hour_demand(cfg)
    assert demand.height == 480
    assert demand["pickup_count"].to_list() == [1] * 480
    assert set(demand.columns) >= {
        "zone_id",
        "borough",
        "ts",
        "pickup_count",
        "prcp_mm",
        "tmax_c",
        "tmin_c",
        "snow_mm",
    }


def test_grid_fills_unobserved_hours_with_zero(validated: MobilityConfig) -> None:
    cfg = validated
    """A zone with no trips keeps its grid rows at pickup_count 0 (lag safety)."""
    trips = pl.read_parquet(cfg.validated_dir / "2024-01.parquet")
    zone2_only = trips.filter(pl.col("pulocation_id") == 2)
    zone2_only.write_parquet(cfg.validated_dir / "2024-01.parquet")
    demand = build_zone_hour_demand(cfg)
    assert demand.height == 480  # grid unchanged
    z1 = demand.filter(pl.col("zone_id") == 1)
    assert (z1["pickup_count"] == 0).all()


def test_duration_band_filters_trips(validated: MobilityConfig) -> None:
    cfg = validated
    """Sub-minute and over-4h trips are excluded; grid rows become zeros."""
    trips = pl.read_parquet(cfg.validated_dir / "2024-01.parquet")
    broken = trips.with_columns(duration_min=0.5)  # all trips: 15 min → 30 s
    broken.write_parquet(cfg.validated_dir / "2024-01.parquet")
    demand = build_zone_hour_demand(cfg)
    # empty pickups → fallback grid = full month (744 h) x 2 zones, all zero
    assert demand.height == 744 * 2
    assert (demand["pickup_count"] == 0).all()

    too_long = trips.with_columns(duration_min=300.0)  # 5 h > 4 h cap
    too_long.write_parquet(cfg.validated_dir / "2024-01.parquet")
    assert (build_zone_hour_demand(cfg)["pickup_count"] == 0).all()


def test_unknown_zone_ids_are_dropped(validated: MobilityConfig) -> None:
    cfg = validated
    trips = pl.read_parquet(cfg.validated_dir / "2024-01.parquet")
    trips.with_columns(pulocation_id=999).write_parquet(cfg.validated_dir / "2024-01.parquet")
    demand = build_zone_hour_demand(cfg)
    assert demand.height == 744 * 2
    assert (demand["pickup_count"] == 0).all()
