"""Task registry: 8 benchmark tasks, each implemented on all three engines.

The dimensions follow the canonical duckdb/polars/h2o group-by benchmark
family — IO (parquet/csv read, parquet write, multi-file partitioned read),
relational core (group-by aggregation, join, filtered scan) and analytics
(window function: top-N per group). Every implementation returns the same
canonical result for the same data (see ``data.canonical_rows``); the harness
times whatever work the engine must do to produce it.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import polars as pl
import pyarrow.parquet as pq

from data_engineering.data import DataBundle, TaskResult, canonical_rows

Category = Literal["io", "compute"]
Impl = Callable[[Any, DataBundle, Path], TaskResult]


@dataclass(frozen=True)
class Task:
    """One benchmark task: a contract name/category and one impl per engine."""

    name: str
    category: Category
    description: str
    impls: dict[str, Impl]

    @property
    def cold_measurable(self) -> bool:
        """IO tasks get a cold fresh-process read timed alongside warm repeats."""
        return self.category == "io"


def _frame(rows: dict[str, Any]) -> TaskResult:
    return TaskResult(rows=canonical_rows(pl.DataFrame(rows)))


# ---------------------------------------------------------------------------
# IO tasks
# ---------------------------------------------------------------------------


def _read_parquet_pandas(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    df = ad.read_parquet(str(bundle.trips_parquet))
    return _frame({"rows": [len(df)], "fare_sum": [df["fare_amount"].sum()]})


def _read_parquet_polars(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    out = ad.scan_parquet(str(bundle.trips_parquet)).select(
        pl.len().alias("rows"), pl.sum("fare_amount").alias("fare_sum")
    )
    return TaskResult(rows=canonical_rows(ad.to_polars(out.collect())))


def _read_parquet_duckdb(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    frame = ad.query(
        "SELECT count(*) AS rows, sum(fare_amount) AS fare_sum FROM read_parquet($1)",
        (str(bundle.trips_parquet),),
    )
    return TaskResult(rows=canonical_rows(frame))


def _read_csv_pandas(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    df = ad.read_csv(str(bundle.trips_csv))
    return _frame({"rows": [len(df)], "fare_sum": [df["fare_amount"].sum()]})


def _read_csv_polars(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    out = ad.scan_csv(str(bundle.trips_csv)).select(
        pl.len().alias("rows"), pl.sum("fare_amount").alias("fare_sum")
    )
    return TaskResult(rows=canonical_rows(ad.to_polars(out.collect())))


def _read_csv_duckdb(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    frame = ad.query(
        "SELECT count(*) AS rows, sum(fare_amount) AS fare_sum FROM read_csv_auto($1)",
        (str(bundle.trips_csv),),
    )
    return TaskResult(rows=canonical_rows(frame))


def _write_parquet_pandas(ad: Any, bundle: DataBundle, workdir: Path) -> TaskResult:
    df = ad.read_parquet(str(bundle.trips_parquet))
    out = workdir / "pandas_out.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    df.to_parquet(out)
    return _write_out(out)


def _write_parquet_polars(ad: Any, bundle: DataBundle, workdir: Path) -> TaskResult:
    out = workdir / "polars_out.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    ad.scan_parquet(str(bundle.trips_parquet)).sink_parquet(out)
    return _write_out(out)


def _write_parquet_duckdb(ad: Any, bundle: DataBundle, workdir: Path) -> TaskResult:
    out = workdir / "duckdb_out.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    ad.query(
        "COPY (SELECT * FROM read_parquet($1)) TO $2 (FORMAT PARQUET)",
        (str(bundle.trips_parquet), str(out)),
    )
    return _write_out(out)


def _write_out(out: Path) -> TaskResult:
    rows = pq.read_metadata(out).num_rows  # validates the file round-trips
    return TaskResult(
        rows=canonical_rows(pl.DataFrame({"rows": [rows]})),
        detail={"bytes_mb": round(out.stat().st_size / 1e6, 3)},
    )


def _partitioned_pandas(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    df = ad.read_partitioned(str(bundle.partitioned_dir))
    return _frame({"rows": [len(df)], "fare_sum": [df["fare_amount"].sum()]})


def _partitioned_polars(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    out = ad.scan_partitioned(str(bundle.partitioned_dir)).select(
        pl.len().alias("rows"), pl.sum("fare_amount").alias("fare_sum")
    )
    return TaskResult(rows=canonical_rows(ad.to_polars(out.collect())))


def _partitioned_duckdb(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    frame = ad.query(
        "SELECT count(*) AS rows, sum(fare_amount) AS fare_sum"
        " FROM read_parquet($1, hive_partitioning = true)",
        (str(bundle.partitioned_dir / "*/*.parquet"),),
    )
    return TaskResult(rows=canonical_rows(frame))


# ---------------------------------------------------------------------------
# Compute tasks
# ---------------------------------------------------------------------------


def _groupby_pandas(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    df = ad.read_parquet(str(bundle.trips_parquet))
    day = df["tpep_pickup_datetime"].dt.date.rename("day")
    out = df.groupby(day).agg(
        trips=("fare_amount", "size"),
        total_fare=("fare_amount", "sum"),
        mean_distance=("trip_distance", "mean"),
        mean_passengers=("passenger_count", "mean"),
    )
    return TaskResult(rows=canonical_rows(ad.to_polars(out.reset_index())))


def _groupby_polars(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    out = (
        ad.scan_parquet(str(bundle.trips_parquet))
        .group_by(pl.col("tpep_pickup_datetime").dt.date().alias("day"))
        .agg(
            pl.len().alias("trips"),
            pl.sum("fare_amount").alias("total_fare"),
            pl.mean("trip_distance").alias("mean_distance"),
            pl.mean("passenger_count").alias("mean_passengers"),
        )
    )
    return TaskResult(rows=canonical_rows(ad.to_polars(out.collect())))


def _groupby_duckdb(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    frame = ad.query(
        "SELECT CAST(tpep_pickup_datetime AS DATE) AS day, count(*) AS trips,"
        " sum(fare_amount) AS total_fare, avg(trip_distance) AS mean_distance,"
        " avg(passenger_count) AS mean_passengers"
        " FROM read_parquet($1) GROUP BY 1",
        (str(bundle.trips_parquet),),
    )
    return TaskResult(rows=canonical_rows(frame))


def _join_pandas(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    trips = ad.read_parquet(str(bundle.trips_parquet))
    # keep_default_na=False: the lookup's literal "N/A" borough must stay a
    # string — the default NA parsing would swallow it and groupby would
    # silently drop those rows (the parity contract caught exactly this).
    zones = pd.read_csv(bundle.zones_csv, keep_default_na=False)
    merged = trips.merge(zones, left_on="PULocationID", right_on="LocationID")
    out = merged.groupby("Borough").agg(
        trips=("fare_amount", "size"), total_fare=("fare_amount", "sum")
    )
    return TaskResult(rows=canonical_rows(ad.to_polars(out.reset_index())))


def _join_polars(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    zones = pl.scan_csv(str(bundle.zones_csv))
    out = (
        ad.scan_parquet(str(bundle.trips_parquet))
        .join(zones, left_on="PULocationID", right_on="LocationID")
        .group_by("Borough")
        .agg(pl.len().alias("trips"), pl.sum("fare_amount").alias("total_fare"))
    )
    return TaskResult(rows=canonical_rows(ad.to_polars(out.collect())))


def _join_duckdb(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    frame = ad.query(
        'SELECT z."Borough" AS "Borough", count(*) AS trips, sum(t.fare_amount) AS total_fare'
        " FROM read_parquet($1) t JOIN read_csv_auto($2) z"
        " ON t.PULocationID = z.LocationID GROUP BY 1",
        (str(bundle.trips_parquet), str(bundle.zones_csv)),
    )
    return TaskResult(rows=canonical_rows(frame))


def _window_pandas(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    df = ad.read_parquet(str(bundle.trips_parquet))
    day = df["tpep_pickup_datetime"].dt.date.rename("day")
    counts = (
        df.groupby([day, "PULocationID"])
        .size()
        .reset_index(name="trips")
        .rename(columns={"PULocationID": "pu"})
    )
    counts = counts.sort_values(["day", "trips", "pu"], ascending=[True, False, True])
    counts["rank"] = counts.groupby("day").cumcount() + 1
    out = counts.loc[counts["rank"] <= 5, ["day", "pu", "trips", "rank"]]
    return TaskResult(rows=canonical_rows(ad.to_polars(out.reset_index(drop=True))))


def _window_polars(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    counts = ad.scan_parquet(str(bundle.trips_parquet)).group_by(
        [pl.col("tpep_pickup_datetime").dt.date().alias("day"), pl.col("PULocationID").alias("pu")]
    )
    out = (
        counts.agg(pl.len().alias("trips"))
        .sort(["day", "trips", "pu"], descending=[False, True, False])
        .with_row_index("idx")
        .with_columns((pl.col("idx") - pl.min("idx").over("day") + 1).alias("rank"))
        .filter(pl.col("rank") <= 5)
        .select(["day", "pu", "trips", "rank"])
    )
    return TaskResult(rows=canonical_rows(ad.to_polars(out.collect())))


def _window_duckdb(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    frame = ad.query(
        "WITH counts AS ("
        " SELECT CAST(tpep_pickup_datetime AS DATE) AS day, PULocationID AS pu,"
        " count(*) AS trips FROM read_parquet($1) GROUP BY 1, 2),"
        " ranked AS ("
        " SELECT day, pu, trips,"
        " row_number() OVER (PARTITION BY day ORDER BY trips DESC, pu) AS rank"
        " FROM counts)"
        " SELECT day, pu, trips, rank FROM ranked WHERE rank <= 5",
        (str(bundle.trips_parquet),),
    )
    return TaskResult(rows=canonical_rows(frame))


def _filter_pandas(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    df = ad.read_parquet(str(bundle.trips_parquet))
    mask = (df["fare_amount"] > 50) & (df["trip_distance"] > 10)
    return _frame({"rows": [int(mask.sum())], "fare_sum": [df.loc[mask, "fare_amount"].sum()]})


def _filter_polars(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    out = (
        ad.scan_parquet(str(bundle.trips_parquet))
        .filter((pl.col("fare_amount") > 50) & (pl.col("trip_distance") > 10))
        .select(pl.len().alias("rows"), pl.sum("fare_amount").alias("fare_sum"))
    )
    return TaskResult(rows=canonical_rows(ad.to_polars(out.collect())))


def _filter_duckdb(ad: Any, bundle: DataBundle, _: Path) -> TaskResult:
    frame = ad.query(
        "SELECT count(*) AS rows, sum(fare_amount) AS fare_sum"
        " FROM read_parquet($1) WHERE fare_amount > 50 AND trip_distance > 10",
        (str(bundle.trips_parquet),),
    )
    return TaskResult(rows=canonical_rows(frame))


TASKS: tuple[Task, ...] = (
    Task(
        "read_parquet",
        "io",
        "Read the full-month parquet and reduce to row count + fare total.",
        {
            "pandas": _read_parquet_pandas,
            "polars": _read_parquet_polars,
            "duckdb": _read_parquet_duckdb,
        },
    ),
    Task(
        "read_csv",
        "io",
        "Read the full-month CSV (typed read: timestamp column parsed/inferred).",
        {"pandas": _read_csv_pandas, "polars": _read_csv_polars, "duckdb": _read_csv_duckdb},
    ),
    Task(
        "groupby",
        "compute",
        "Per-day aggregation: trips, total fare, mean distance, mean passengers.",
        {"pandas": _groupby_pandas, "polars": _groupby_polars, "duckdb": _groupby_duckdb},
    ),
    Task(
        "join",
        "compute",
        "Join trips to the zone lookup on pickup zone; aggregate fare by borough.",
        {"pandas": _join_pandas, "polars": _join_polars, "duckdb": _join_duckdb},
    ),
    Task(
        "window",
        "compute",
        "Top-5 pickup zones by trip count per day (window rank, deterministic ties).",
        {"pandas": _window_pandas, "polars": _window_polars, "duckdb": _window_duckdb},
    ),
    Task(
        "filter",
        "compute",
        "Filtered scan (predicate pushdown): fares > $50 and trips > 10 miles.",
        {"pandas": _filter_pandas, "polars": _filter_polars, "duckdb": _filter_duckdb},
    ),
    Task(
        "write_parquet",
        "io",
        "Write the full frame back to parquet in the engine's native path.",
        {
            "pandas": _write_parquet_pandas,
            "polars": _write_parquet_polars,
            "duckdb": _write_parquet_duckdb,
        },
    ),
    Task(
        "partitioned_read",
        "io",
        "Multi-file out-of-core style read: 31 per-day hive-partitioned parquet files.",
        {
            "pandas": _partitioned_pandas,
            "polars": _partitioned_polars,
            "duckdb": _partitioned_duckdb,
        },
    ),
)

TASKS_BY_NAME: dict[str, Task] = {t.name: t for t in TASKS}
