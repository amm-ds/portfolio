"""Dataset bundle + canonical result normalization.

A :class:`DataBundle` is the one handle every task receives: the prepared
layout (parquet, CSV, hive-partitioned per-day files, zone lookup) plus the
identity (row count, checksum, source) the harness records in
``evaluation_metadata.json``. Canonical rows are the cross-engine contract:
each engine returns its task result as a small polars frame, normalized here
to sorted, JSON-safe rows so correctness parity is an exact comparison.
"""

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pyarrow.parquet as pq


@dataclass(frozen=True)
class DataBundle:
    """Prepared dataset locations + identity for one track (real or synthetic)."""

    data_dir: Path
    n_rows: int
    checksum_sha256: str
    source: str
    license: str
    notes: str = ""
    #: False for lean bundles (scalability track) that carry no partitioned dir.
    with_partitioned: bool = True

    # -- prepared layout -----------------------------------------------------
    @property
    def trips_parquet(self) -> Path:
        return self.data_dir / "prepared" / "trips.parquet"

    @property
    def trips_csv(self) -> Path:
        return self.data_dir / "prepared" / "trips.csv"

    @property
    def partitioned_dir(self) -> Path:
        return self.data_dir / "prepared" / "partitioned"

    @property
    def zones_csv(self) -> Path:
        return self.data_dir / "raw" / "taxi_zone_lookup.csv"

    @property
    def contract_path(self) -> Path:
        return self.data_dir / "dataset_contract.json"

    def validate(self) -> None:
        """Fail loudly unless the prepared layout is complete and consistent."""
        for p in (self.trips_parquet, self.trips_csv, self.zones_csv):
            if not p.exists():
                raise FileNotFoundError(
                    f"dataset artifact missing: {p} — run `data_engineering fetch-data`"
                    " (real track) or evaluate with --synthetic."
                )
        actual_rows = pq.read_metadata(self.trips_parquet).num_rows
        if actual_rows != self.n_rows:
            raise ValueError(
                f"trips.parquet has {actual_rows} rows, contract expects {self.n_rows}"
                " — re-run fetch-data or regenerate the synthetic track."
            )
        if self.with_partitioned and not any(self.partitioned_dir.glob("day=*/part-0.parquet")):
            raise FileNotFoundError(f"no partitioned parts under {self.partitioned_dir}")

    # -- serialization for the cold/probe subprocess -------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "data_dir": str(self.data_dir),
            "n_rows": self.n_rows,
            "checksum_sha256": self.checksum_sha256,
            "source": self.source,
            "license": self.license,
            "notes": self.notes,
            "with_partitioned": self.with_partitioned,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DataBundle":
        return cls(
            data_dir=Path(d["data_dir"]),
            n_rows=int(d["n_rows"]),
            checksum_sha256=str(d["checksum_sha256"]),
            source=str(d["source"]),
            license=str(d["license"]),
            notes=str(d.get("notes", "")),
            with_partitioned=bool(d.get("with_partitioned", True)),
        )


def canonical_rows(frame: pl.DataFrame) -> list[dict[str, Any]]:
    """Normalize a result frame to sorted, JSON-safe rows (the parity contract).

    Dates become ISO strings; floats keep 6 significant digits — enough for
    every audit comparison here, and stable across the floating-point
    reordering a parallel engine (DuckDB) legitimately does between runs, so
    the determinism gate can stay exact. Rows sort by their stable JSON
    encoding so engine-specific row order never leaks into comparisons.
    """
    rows: list[dict[str, Any]] = []
    for row in frame.iter_rows(named=True):
        rows.append({k: _canonical_value(v) for k, v in row.items()})
    rows.sort(key=lambda r: json.dumps(r, sort_keys=True, default=str))
    return rows


def _canonical_value(v: Any) -> Any:
    if v is None or isinstance(v, bool | int | str):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        rounded = float(f"{v:.6g}")
        return 0.0 if rounded == 0 else rounded
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time().isoformat() == "00:00:00" else v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def rows_equal(a: list[dict[str, Any]], b: list[dict[str, Any]], rel_tol: float = 1e-5) -> bool:
    """Cross-engine canonical-row equality: ints/strings/dates exact, floats close.

    Canonical floats carry 6 significant digits, and a parallel engine may
    reorder float summation between runs — a sum sitting within an ulp of a
    rounding cliff flips one display bin (a ~4e-6 relative step on the rounded
    values while the raw values agree to ~1e-7). The 1e-5 band absorbs those
    cliff flips; anything beyond it is a real arithmetic difference.
    """
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b, strict=True):
        if ra.keys() != rb.keys():
            return False
        for key in ra:
            va, vb = ra[key], rb[key]
            if isinstance(va, float) and isinstance(vb, float):
                if not math.isclose(va, vb, rel_tol=rel_tol, abs_tol=1e-9):
                    return False
            elif va != vb:
                return False
    return True


def rows_fingerprint(rows: list[dict[str, Any]]) -> str:
    """Stable checksum of canonical rows (determinism gates, no timings)."""
    payload = json.dumps(rows, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class TaskResult:
    """One task run: canonical rows + non-comparable detail (e.g. file bytes)."""

    rows: list[dict[str, Any]]
    detail: dict[str, Any] = field(default_factory=dict)
