"""Engine adapters: pandas 2.x, Polars (lazy), DuckDB (SQL) behind one contract.

Every adapter exposes its ``name``/``version`` and the frame normalizer that
turns its native result into the polars interchange the canonical contract
uses. Task implementations (``tasks.py``) call the adapter's primitives so
each engine reads data the idiomatic way — ``pd.read_parquet``,
``pl.scan_parquet`` (+ ``collect``), ``duckdb.read_parquet`` — and idiomatic
typed reads: pandas parses the CSV timestamp column, Polars infers it,
DuckDB's ``read_csv_auto`` infers it.
"""

from typing import Any, Protocol

import duckdb
import pandas as pd
import polars as pl


class EngineAdapter(Protocol):
    """The engine handle a task implementation receives."""

    name: str

    @property
    def version(self) -> str: ...

    def to_polars(self, frame: Any) -> pl.DataFrame:
        """Normalize a native frame (pandas/polars/duckdb relation result)."""
        ...


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


_ADAPTERS: dict[str, type[PandasAdapter] | type[PolarsAdapter] | type[DuckDBAdapter]] = {
    "pandas": PandasAdapter,
    "polars": PolarsAdapter,
    "duckdb": DuckDBAdapter,
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
        "pyarrow": pyarrow.__version__,
    }


def _python_version() -> str:
    import platform as _platform

    return _platform.python_version()
