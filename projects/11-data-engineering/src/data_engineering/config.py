"""Project settings (env handling inherited from the platform, ADR-0002).

Every field mirrors ``params.yaml`` (the CLI and the DVC stages read that
file; DVC re-runs a stage when a tracked entry changes).
"""

from pathlib import Path

from portfolio_core.config import Settings
from pydantic import Field


class DEConfig(Settings):
    """Data-engineering benchmark settings."""

    # Real track: NYC TLC yellow taxi 2024-01 (registry-pinned snapshot family).
    trips_url: str = Field(
        default="https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet"
    )
    trips_sha256: str = Field(
        default="c4d59da7bbc8abaeeeb1727947ee93d9891a71acb42854bd80db1571b2030510",
        pattern=r"^[0-9a-f]{64}$",
    )
    zones_url: str = Field(
        default="https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"
    )
    zones_sha256: str = Field(
        default="1a99e105092230f8620f301edcca7f80d3080642ff404d28ed957d3fa222c8ed",
        pattern=r"^[0-9a-f]{64}$",
    )

    # Synthetic CI track: seeded generator scale.
    n_synthetic_rows: int = Field(default=30_000, gt=0)

    # Scalability study: seeded synthetic tracks at these row counts (the 5
    # most discriminating tasks, every engine, fewer repeats, no probes — the
    # time-vs-size curve committed in metrics.json under "scalability").
    scalability_rows: list[int] = Field(default=[1_000_000, 3_000_000, 10_000_000])
    scalability_repeats: int = Field(default=2, ge=2)

    # Harness protocol: in-process warm repeats (median wall time) + isolated
    # fresh-subprocess probes per task-by-engine cell for true peak RSS and cold
    # IO reads.
    repeats: int = Field(default=5, ge=1)
    memory_probes: int = Field(default=1, ge=0)

    # Layout (paths join onto data_dir / reports_dir from Settings).
    raw_dir: Path = Path("raw")
    prepared_dir: Path = Path("prepared")

    @property
    def raw_path(self) -> Path:
        return self.data_dir / self.raw_dir

    @property
    def prepared_path(self) -> Path:
        return self.data_dir / self.prepared_dir
