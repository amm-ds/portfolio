"""Data-stage tests: determinism, dtypes, and the dataset contract."""

import polars as pl
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.data import build_contract, generate, prepare


def test_generation_is_seeded_and_typed(small_config: AnomalyConfig) -> None:
    a, b = generate(small_config), generate(small_config)
    assert a.equals(b)
    assert a.height == small_config.n
    assert a.schema["ts"] == pl.Datetime(time_unit="us")
    assert a.schema["is_anomaly"] == pl.Boolean
    assert a.null_count().sum_horizontal().item() == 0
    cpu = a["cpu"].to_numpy()
    assert float(cpu.min()) >= 0 and float(cpu.max()) <= 100


def test_contract_describes_frame(small_config: AnomalyConfig) -> None:
    df = generate(small_config)
    contract = build_contract(df, small_config)
    assert contract.n_rows == df.height
    assert contract.source == "synthetic://portfolio_core.synthetic.telemetry"
    assert contract.snapshot_date == small_config.snapshot_date
    assert len(contract.checksum_sha256) == 64
    # checksum tracks content: a different frame gets a different identity
    other = build_contract(df.head(10), small_config)
    assert other.checksum_sha256 != contract.checksum_sha256


def test_prepare_persists_raw_and_contract(small_config: AnomalyConfig) -> None:
    prepare(small_config)
    assert small_config.raw_path.exists()
    assert small_config.contract_path.exists()
    reloaded = pl.read_parquet(small_config.raw_path)
    assert reloaded.height == small_config.n
