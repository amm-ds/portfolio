"""Shared fixtures: a tiny seeded synthetic bundle and a fast config."""

from pathlib import Path

import pytest
from data_engineering.config import DEConfig
from data_engineering.data import DataBundle
from data_engineering.synthetic import (
    synthetic_checksum,
    trips_frame,
    write_synthetic_dataset,
)

TINY_N = 3_000


@pytest.fixture(scope="session")
def tiny_bundle(tmp_path_factory: pytest.TempPathFactory) -> DataBundle:
    """Prepared synthetic layout (3k rows) — small but multi-day, multi-zone."""
    out_dir = tmp_path_factory.mktemp("de11-tiny") / "synthetic"
    trips, _zones = write_synthetic_dataset(seed=42, n=TINY_N, out_dir=out_dir)
    bundle = DataBundle(
        data_dir=out_dir,
        n_rows=len(trips),
        checksum_sha256=synthetic_checksum(42, TINY_N),
        source=f"synthetic://trips_frame?seed=42&n={TINY_N}",
        license="Synthetic (seeded generator)",
    )
    bundle.validate()
    return bundle


@pytest.fixture()
def fast_cfg(tmp_path: Path) -> DEConfig:
    """Minimal-config: no network, no probes, one repeat (unit-level tests)."""
    return DEConfig(
        seed=42,
        n_synthetic_rows=TINY_N,
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        repeats=1,
        memory_probes=0,
    )


@pytest.fixture()
def tiny_trips() -> object:
    """The raw generator frame (determinism tests)."""
    return trips_frame(42, TINY_N)
