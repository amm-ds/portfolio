"""DQ gate tests: gates pass on clean telemetry and fail loudly on violations."""

import polars as pl
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.data import generate
from anomaly_detection.validate import run_dq_gates, validate
from portfolio_core.dq import DQGateError


def test_gates_pass_on_synthetic(small_config: AnomalyConfig) -> None:
    report = run_dq_gates(generate(small_config), small_config)
    assert report.passed
    assert report.n_failed == 0
    # 5 null-rate checks (ts, cpu, mem, latency_ms, is_anomaly) + 3 range checks
    assert len(report.checks) == 8


def _inject_nulls(df: pl.DataFrame, column: str, frac: float) -> pl.DataFrame:
    every = max(1, round(1 / frac))
    return df.with_columns(
        pl.when(pl.int_range(pl.len()) % every == 0)
        .then(None)
        .otherwise(pl.col(column))
        .alias(column)
    )


def test_null_rate_gate_fails_loudly(small_config: AnomalyConfig) -> None:
    df = _inject_nulls(generate(small_config), "cpu", 0.05)  # 5% > 1% threshold
    report = run_dq_gates(df, small_config)
    assert not report.passed
    failed = [c for c in report.checks if not c.passed]
    assert any(c.column == "cpu" and c.name == "null_rate" for c in failed)
    with pytest.raises(DQGateError):
        report.raise_if_failed()


def test_range_gate_fails_on_cpu_overflow(small_config: AnomalyConfig) -> None:
    df = generate(small_config).with_columns((pl.col("cpu") * 1.5).alias("cpu"))
    report = run_dq_gates(df, small_config)
    assert not report.passed
    assert any(c.column == "cpu" and c.name == "range" for c in report.checks if not c.passed)


def test_range_gate_fails_on_nonpositive_latency(small_config: AnomalyConfig) -> None:
    df = generate(small_config).with_columns(
        pl.when(pl.col("latency_ms") > 200)
        .then(0.0)
        .otherwise(pl.col("latency_ms"))
        .alias("latency_ms")
    )
    report = run_dq_gates(df, small_config)
    assert not report.passed
    assert any(
        c.column == "latency_ms" and c.name == "range" for c in report.checks if not c.passed
    )


def test_validate_persists_report_and_raises(small_config: AnomalyConfig) -> None:
    df = _inject_nulls(generate(small_config), "mem", 0.02)
    with pytest.raises(DQGateError) as exc_info:
        validate(df, small_config)
    # the report is persisted even on failure so the artifact shows the violation
    assert small_config.dq_report_path.exists()
    assert "null_rate" in str(exc_info.value)


def test_validate_persists_passing_report(small_config: AnomalyConfig) -> None:
    validate(generate(small_config), small_config)
    html = small_config.dq_report_path.read_text()
    assert "DQ gates" in html
    assert "null_rate" in html
