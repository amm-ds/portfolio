"""Engine adapters: pandas 2.x, Polars (lazy), DuckDB (SQL), sqlite3 behind one contract.

Every adapter exposes its ``name``/``version`` and the frame normalizer that
turns its native result into the polars interchange the canonical contract
uses. Task implementations (``tasks.py``) call the adapter's primitives so
each engine reads data the idiomatic way — ``pd.read_parquet``,
``pl.scan_parquet`` (+ ``collect``), ``duckdb.read_parquet`` — and idiomatic
typed reads: pandas parses the CSV timestamp column, Polars infers it,
DuckDB's ``read_csv_auto`` infers it. sqlite3 (Python stdlib) is the honest
classical baseline — the engine every Python install already has: it cannot
read parquet or CSV itself, so each task loads the prepared files into a
per-call in-memory database via pandas and then runs SQL; the load is part of
the timed cell, exactly the conversion tax a sqlite workflow pays.
"""

import sqlite3
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import polars as pl

# numpy scalars reach sqlite through itertuples; bind them as native Python
# numbers (np.int32/np.int64 are not int subclasses and would raise).
sqlite3.register_adapter(np.int32, int)
sqlite3.register_adapter(np.int64, int)
sqlite3.register_adapter(np.float32, float)


class PandasAdapter:
    """pandas 2.x on the pyarrow parquet engine (the repo's default pairing)."""

    name = "pandas"

    @property
    def version(self) -> str:
        return str(pd.__version__)

    def read_parquet(self, path: str) -> pd.DataFrame:
        return pd.read_parquet(path, engine="pyarrow")

    def read_csv(self, path: str) -> pd.DataFrame:
        return pd.read_csv(path, parse_dates=["tpep_pickup_datetime"])

    def read_partitioned(self, path: str) -> pd.DataFrame:
        return pd.read_parquet(path, engine="pyarrow")

    def to_polars(self, frame: pd.DataFrame) -> pl.DataFrame:
        return pl.from_pandas(frame)


class PolarsAdapter:
    """Polars lazy: scans build a plan, ``collect`` executes at the boundary."""

    name = "polars"

    @property
    def version(self) -> str:
        return str(pl.__version__)

    def scan_parquet(self, path: str) -> pl.LazyFrame:
        return pl.scan_parquet(path)

    def scan_csv(self, path: str) -> pl.LazyFrame:
        return pl.scan_csv(path)

    def scan_partitioned(self, path: str) -> pl.LazyFrame:
        return pl.scan_parquet(f"{path}/day=*/part-0.parquet")

    def to_polars(self, frame: pl.DataFrame) -> pl.DataFrame:
        return frame


class DuckDBAdapter:
    """DuckDB SQL over ``read_parquet`` / ``read_csv_auto`` table functions."""

    name = "duckdb"

    def __init__(self) -> None:
        self._con = duckdb.connect(database=":memory:")

    @property
    def version(self) -> str:
        return str(duckdb.__version__)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> pl.DataFrame:
        frame = pl.from_arrow(self._con.sql(sql, params=params).to_arrow_table())
        if not isinstance(frame, pl.DataFrame):
            raise TypeError(f"expected polars DataFrame, got {type(frame).__name__}")
        return frame

    def to_polars(self, frame: pl.DataFrame) -> pl.DataFrame:
        return frame


class SqliteAdapter:
    """sqlite3 (stdlib) SQL over a per-call in-memory database.

    sqlite has no parquet/CSV reader, so a task first loads the prepared file
    into ``:memory:`` via pandas (the documented conversion step — no new
    dependencies) and then runs plain SQL. The ingest is deliberately inside
    the timed region: it is the honest per-task cost of answering from files
    with the classical engine. Compute tasks ingest only the columns their
    query touches, matching the column pruning Polars/DuckDB scans already
    do; the raw scan tasks (``read_parquet``/``read_csv``/``partitioned_read``)
    ingest the full working projection, as the pandas comparison reads it.
    """

    name = "sqlite"

    def __init__(self) -> None:
        self._con = sqlite3.connect(":memory:")
        # Sort-heavy SQL (window ranking, ORDER BY rollups) otherwise spills
        # temp b-trees to disk even though the database itself is in memory.
        self._con.execute("PRAGMA temp_store=MEMORY")

    @property
    def version(self) -> str:
        return sqlite3.sqlite_version

    def load_parquet(self, path: str, table: str, columns: list[str] | None = None) -> None:
        """Ingest a parquet file (optionally column-pruned) into ``table``."""
        frame = pd.read_parquet(path, engine="pyarrow", columns=columns)
        self._ingest(frame, table)

    def load_csv(
        self,
        path: str,
        table: str,
        columns: list[str] | None = None,
        *,
        parse_dates: list[str] | None = None,
        keep_strings: bool = False,
    ) -> None:
        """Ingest a CSV file into ``table`` (typed where the task needs it).

        ``keep_strings`` disables NA inference so literal strings such as the
        zone lookup's "N/A" borough survive as values (the pandas join rule).
        """
        frame = pd.read_csv(
            path,
            usecols=columns,
            parse_dates=parse_dates,
            keep_default_na=not keep_strings,
        )
        self._ingest(frame, table)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> pl.DataFrame:
        """Run SQL and return the small result as the polars interchange."""
        cursor = self._con.execute(sql, params)
        names = [d[0] for d in cursor.description or []]
        data = cursor.fetchall()
        return pl.DataFrame({name: [row[i] for row in data] for i, name in enumerate(names)})

    def _ingest(self, frame: pd.DataFrame, table: str) -> None:
        """Create ``table`` from ``frame`` and bulk-insert its rows."""
        columns = list(frame.columns)
        ddl = ", ".join(f'"{c}" {self._sql_type(frame[c].dtype)}' for c in columns)
        self._con.execute(f'DROP TABLE IF EXISTS "{table}"')
        self._con.execute(f'CREATE TABLE "{table}" ({ddl})')
        to_insert = (
            frame.assign(
                tpep_pickup_datetime=frame["tpep_pickup_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
            )
            if "tpep_pickup_datetime" in frame.columns
            else frame
        )
        marks = ", ".join("?" * len(columns))
        # Identifiers are internal (task-defined column names / fixed table
        # names), never caller text; values are bound parameters.
        self._con.executemany(
            f'INSERT INTO "{table}" ({", ".join(columns)}) VALUES ({marks})',  # noqa: S608
            to_insert[columns].itertuples(index=False, name=None),
        )

    @staticmethod
    def _sql_type(dtype: Any) -> str:
        if pd.api.types.is_float_dtype(dtype):
            return "REAL"
        if pd.api.types.is_integer_dtype(dtype) or pd.api.types.is_bool_dtype(dtype):
            return "INTEGER"
        return "TEXT"  # strings + the strftime-ed pickup timestamp

    def to_polars(self, frame: pl.DataFrame) -> pl.DataFrame:
        return frame


_AdapterT = type[PandasAdapter] | type[PolarsAdapter] | type[DuckDBAdapter] | type[SqliteAdapter]
_ADAPTERS: dict[str, _AdapterT] = {
    "pandas": PandasAdapter,
    "polars": PolarsAdapter,
    "duckdb": DuckDBAdapter,
    "sqlite": SqliteAdapter,
}


def adapter_names() -> list[str]:
    return list(_ADAPTERS)


def build_adapter(name: str) -> Any:
    """Instantiate the adapter registered under ``name`` (loud on typos)."""
    if name not in _ADAPTERS:
        raise KeyError(f"unknown engine {name!r}; registered: {sorted(_ADAPTERS)}")
    return _ADAPTERS[name]()


def engine_versions() -> dict[str, str]:
    """Runtime versions recorded in evaluation_metadata.json."""
    import pyarrow

    return {
        "python": _python_version(),
        "pandas": pd.__version__,
        "pandas_pyarrow": pyarrow.__version__,
        "polars": pl.__version__,
        "duckdb": duckdb.__version__,
        "sqlite": sqlite3.sqlite_version,
        "pyarrow": pyarrow.__version__,
    }


def _python_version() -> str:
    import platform as _platform

    return _platform.python_version()
