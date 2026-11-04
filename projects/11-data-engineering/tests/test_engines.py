"""Correctness parity: same canonical result across engines on one task set.

Every task implementation runs over the tiny synthetic bundle; the canonical
rows must be identical for pandas, Polars and DuckDB. This is the contract
that makes the timing comparison meaningful — the engines are timed on the
same work, not on three different interpretations of it.
"""

import pytest
from data_engineering.data import DataBundle, canonical_rows, rows_equal
from data_engineering.engines import adapter_names, build_adapter, engine_versions
from data_engineering.tasks import TASKS


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.name)
def test_parity_across_engines(task: object, tiny_bundle: DataBundle, tmp_path) -> None:
    """pandas / Polars / DuckDB return the same canonical rows for the task."""
    results: dict[str, list[dict]] = {}
    for engine in adapter_names():
        adapter = build_adapter(engine)
        result = task.impls[engine](adapter, tiny_bundle, tmp_path / task.name)
        results[engine] = result.rows
    reference = results["pandas"]
    for engine in ("polars", "duckdb"):
        assert rows_equal(reference, results[engine]), f"{task.name}/{engine}: parity drift"


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.name)
def test_results_are_canonical(task: object, tiny_bundle: DataBundle, tmp_path) -> None:
    """Canonical rows are JSON-safe, sorted and non-empty."""
    import json

    adapter = build_adapter("pandas")
    result = task.impls["pandas"](adapter, tiny_bundle, tmp_path / task.name)
    assert result.rows, f"{task.name}: empty result"
    json.dumps(result.rows)  # must not raise
    keys = [json.dumps(r, sort_keys=True) for r in result.rows]
    assert keys == sorted(keys), f"{task.name}: rows not canonically sorted"


def test_canonical_rows_normalizes_values() -> None:
    """Datetimes → ISO strings, NaN → None, ints/strings untouched."""
    import datetime

    import polars as pl

    frame = pl.DataFrame(
        {
            "d": [datetime.date(2024, 1, 5)],
            "ts": [datetime.datetime(2024, 1, 5, 7, 30)],
            "x": [float("nan")],
            "n": [3],
            "s": ["a"],
        }
    )
    rows = canonical_rows(frame)
    assert rows == [{"d": "2024-01-05", "n": 3, "s": "a", "ts": "2024-01-05T07:30:00", "x": None}]


def test_adapter_registry() -> None:
    """Three engines registered; unknown names fail loudly; versions present."""
    assert adapter_names() == ["pandas", "polars", "duckdb"]
    with pytest.raises(KeyError):
        build_adapter("spark")
    versions = engine_versions()
    for key in ("python", "pandas", "pandas_pyarrow", "polars", "duckdb", "pyarrow"):
        assert versions[key], f"missing version for {key}"


def test_pandas_join_keeps_na_borough(tmp_path) -> None:
    """Regression: pandas' default NA parsing must not swallow the literal "N/A"
    borough (it would silently drop those rows from the group-by)."""
    import polars as pl
    from data_engineering.data import DataBundle
    from data_engineering.synthetic import trips_frame, zones_frame
    from data_engineering.tasks import TASKS_BY_NAME

    na_id = 250
    zones = pl.concat(
        [
            zones_frame(),
            pl.DataFrame(
                {
                    "LocationID": [na_id],
                    "Borough": ["N/A"],
                    "Zone": ["Unmapped zone"],
                    "service_zone": [""],
                }
            ),
        ]
    )
    trips = trips_frame(42, 2_000).with_columns(
        pl.when(pl.int_range(0, pl.len()) % 7 == 0)
        .then(pl.lit(na_id))
        .otherwise(pl.col("PULocationID"))
        .cast(pl.Int32)
        .alias("PULocationID")
    )
    data_dir = tmp_path / "data"
    (data_dir / "prepared").mkdir(parents=True)
    (data_dir / "raw").mkdir(parents=True)
    trips.write_parquet(data_dir / "prepared" / "trips.parquet")
    zones.write_csv(data_dir / "raw" / "taxi_zone_lookup.csv")
    bundle = DataBundle(
        data_dir=data_dir,
        n_rows=len(trips),
        checksum_sha256="0" * 64,
        source="synthetic://na-regression",
        license="Synthetic",
    )

    task = TASKS_BY_NAME["join"]
    results = {}
    for engine in adapter_names():
        results[engine] = task.impls[engine](build_adapter(engine), bundle, tmp_path / engine)

    boroughs = {r["Borough"] for r in results["pandas"].rows}
    assert "N/A" in boroughs, f"pandas join dropped the N/A borough: {sorted(boroughs)}"
    assert rows_equal(results["pandas"].rows, results["polars"].rows)
    assert rows_equal(results["pandas"].rows, results["duckdb"].rows)
