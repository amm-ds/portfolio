"""DQ gates: pass on healthy data, halt loudly on broken data."""

import importlib.util
from pathlib import Path

import polars as pl
import pytest
from mobility.config import MobilityConfig
from mobility.validate import validate_all, validate_month
from portfolio_core.dq import DQGateError

_spec = importlib.util.spec_from_file_location(
    "mobility_test_helpers", Path(__file__).parent / "conftest.py"
)
assert _spec is not None and _spec.loader is not None
_helpers_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers_mod)
make_trips_frame = _helpers_mod.make_trips_frame


def test_validate_month_passes(cfg: MobilityConfig) -> None:
    report = validate_month("2024-01", cfg)
    assert report.passed
    assert report.n_rows == 480
    out = cfg.validated_dir / "2024-01.parquet"
    assert out.exists()
    assert pl.read_parquet(out).height == 480


def test_validate_halls_below_row_floor(cfg: MobilityConfig) -> None:
    cfg = cfg.model_copy(update={"min_rows_per_month": 10_000})
    with pytest.raises(DQGateError):
        validate_all(cfg)


def test_validate_halls_on_stale_month(cfg: MobilityConfig) -> None:
    """Trips only in early January must fail the freshness gate."""
    trips = make_trips_frame().with_columns(
        tpep_pickup_datetime=pl.datetime(2024, 1, 1)
        + (pl.int_range(0, 480) % 3) * pl.duration(hours=1),
        tpep_dropoff_datetime=pl.datetime(2024, 1, 1)
        + (pl.int_range(0, 480) % 3) * pl.duration(hours=1)
        + pl.duration(minutes=10),
    )
    trips.write_parquet(cfg.tlc_raw_dir / "yellow_tripdata_2024-01.parquet")
    report = validate_month("2024-01", cfg)
    assert not report.passed
    with pytest.raises(DQGateError):
        report.raise_if_failed()


def test_validate_halls_on_excessive_nulls(cfg: MobilityConfig) -> None:
    """A structurally broken file (mostly null locations) must not pass."""
    trips = make_trips_frame().with_columns(
        PULocationID=pl.when(pl.int_range(0, pl.len()) < 50)
        .then(None)
        .otherwise(pl.col("PULocationID"))
    )
    trips.write_parquet(cfg.tlc_raw_dir / "yellow_tripdata_2024-01.parquet")
    report = validate_month("2024-01", cfg)
    assert not report.passed
    assert any(c.name == "null_rate" and not c.passed for c in report.checks)


def test_validate_report_is_persisted(cfg: MobilityConfig) -> None:
    validate_month("2024-01", cfg)
    assert (cfg.reports_dir / "dq" / "yellow_2024-01.json").exists()
