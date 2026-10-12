"""Feature stage: exact lag values, next-hour target, temporal split discipline."""

import importlib.util
from datetime import datetime
from pathlib import Path

import polars as pl
from mobility.config import MobilityConfig
from mobility.features import build_features

_spec = importlib.util.spec_from_file_location(
    "mobility_test_helpers", Path(__file__).parent / "conftest.py"
)
assert _spec is not None and _spec.loader is not None
_helpers_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers_mod)
make_zone_hour_demand = _helpers_mod.make_zone_hour_demand


def test_lag_values_are_exact(curated: pl.DataFrame, cfg: MobilityConfig) -> None:
    """pickup_count = 2 everywhere → every lag equals 2, target equals 2."""
    train, test = build_features(cfg)
    combined = pl.concat([train, test])
    assert combined.height == 142  # 71 eligible slots per zone (see below)
    for lag in (1, 2, 24, 168):
        assert (combined[f"lag_{lag}"] == 2).all()
    assert (combined["target"] == 2).all()


def test_target_is_next_hour(cfg: MobilityConfig) -> None:
    """A single spike must appear as ``target`` on the previous hour's row."""
    demand = make_zone_hour_demand()
    spike = demand.with_columns(
        pickup_count=pl.when(pl.col("ts") == pl.datetime(2024, 1, 9, 10))
        .then(99)
        .otherwise(pl.col("pickup_count"))
    )
    spike.write_parquet(cfg.zone_hour_demand_path)
    train, test = build_features(cfg)
    combined = pl.concat([train, test])
    row = combined.filter(pl.col("ts") == pl.datetime(2024, 1, 9, 9)).row(0, named=True)
    assert row["target"] == 99
    assert row["lag_1"] == 2


def test_first_hours_are_dropped(curated: pl.DataFrame, cfg: MobilityConfig) -> None:
    """lag_168 needs 7 days of history and target needs t+1: slots 168..238
    survive per zone → 71 rows per zone in the 240h fixture."""
    train, _ = build_features(cfg)
    assert train.height == 71 * 2  # cutoff 2024-10-01 keeps the whole fixture


def test_temporal_cutoff_is_pure(cfg: MobilityConfig) -> None:
    """Every train ts < cutoff <= every test ts; no interleaving, no shuffle."""
    demand = make_zone_hour_demand().with_columns(
        ts=pl.col("ts") + pl.duration(days=265)  # shift to straddle 2024-10-01
    )
    demand.write_parquet(cfg.zone_hour_demand_path)
    train, test = build_features(cfg)
    cutoff = datetime(2024, 10, 1)
    assert (train["ts"] < cutoff).all()
    assert (test["ts"] >= cutoff).all()
    assert max(train["ts"].to_list()) < min(test["ts"].to_list())  # contiguous boundary
    assert train.height == 48 * 2  # eligible slots per zone before the cutoff
    assert test.height == 23 * 2
    # parquet round-trip exists for both matrices
    assert (cfg.features_dir / "train.parquet").exists()
    assert (cfg.features_dir / "test.parquet").exists()
