"""Data preparation: seeded synthetic telemetry + versioned dataset contract.

The generator lives in ``portfolio_core.synthetic`` so every project shares one
seedable, offline data source. The prepared frame is persisted as parquet and
described by a :class:`DatasetContract` (ADR-0002).
"""

from pathlib import Path

import polars as pl
from portfolio_core.logging import get_logger
from portfolio_core.schemas import DatasetContract
from portfolio_core.synthetic import checksum_of_frame, telemetry

from anomaly_detection.config import AnomalyConfig

logger = get_logger(__name__)

RAW_COLUMNS: tuple[str, ...] = ("ts", "cpu", "mem", "latency_ms", "is_anomaly")


def generate(config: AnomalyConfig) -> pl.DataFrame:
    """Generate seeded synthetic telemetry and normalise dtypes.

    ``ts`` is parsed to datetime here so downstream polars ops (rolling,
    sorting) and the DQ freshness semantics work on real timestamps.
    """
    logger.info(
        "generating telemetry n=%d anomaly_rate=%.3f seed=%d",
        config.n,
        config.anomaly_rate,
        config.seed,
    )
    df = telemetry(seed=config.seed, n=config.n, anomaly_rate=config.anomaly_rate)
    return df.with_columns(
        pl.col("ts").str.to_datetime(),
        pl.col("is_anomaly").cast(pl.Boolean),
    ).select(list(RAW_COLUMNS))


def save_raw(df: pl.DataFrame, config: AnomalyConfig) -> Path:
    """Persist the prepared frame to parquet; returns the artifact path."""
    config.data_path.mkdir(parents=True, exist_ok=True)
    config.raw_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(config.raw_path)
    logger.info("wrote %s (%d rows)", config.raw_path, df.height)
    return config.raw_path


def load_raw(config: AnomalyConfig) -> pl.DataFrame:
    """Load the prepared raw frame, generating it on first use."""
    if not config.raw_path.exists():
        logger.info("raw parquet missing; generating")
        save_raw(generate(config), config)
    return pl.read_parquet(config.raw_path)


def build_contract(df: pl.DataFrame, config: AnomalyConfig) -> DatasetContract:
    """Identity card for the prepared dataset (checksum over canonical bytes)."""
    return DatasetContract(
        name="telemetry",
        source="synthetic://portfolio_core.synthetic.telemetry",
        license="MIT",
        snapshot_date=config.snapshot_date,
        checksum_sha256=checksum_of_frame(df),
        n_rows=df.height,
    )


def save_contract(contract: DatasetContract, config: AnomalyConfig) -> Path:
    """Persist the dataset contract as JSON next to the data."""
    config.contract_path.parent.mkdir(parents=True, exist_ok=True)
    config.contract_path.write_text(contract.model_dump_json(indent=2))
    logger.info("wrote %s", config.contract_path)
    return config.contract_path


def prepare(config: AnomalyConfig) -> pl.DataFrame:
    """Full prepare step: generate, persist, and register the contract."""
    df = generate(config)
    save_raw(df, config)
    save_contract(build_contract(df, config), config)
    return df
