"""Rolling-feature correctness on a hand-computable tiny frame."""

from datetime import datetime, timedelta

import polars as pl
import pytest
from anomaly_detection.features import build_features, feature_columns

WINDOWS = [2, 3]


def _tiny_frame() -> pl.DataFrame:
    base = datetime(2024, 1, 1)
    return pl.DataFrame(
        {
            "ts": [base + timedelta(minutes=i) for i in range(5)],
            "cpu": [1.0, 2.0, 3.0, 4.0, 5.0],
            "mem": [10.0, 10.0, 10.0, 10.0, 10.0],
            "latency_ms": [5.0, 5.0, 5.0, 5.0, 5.0],
            "is_anomaly": [False, False, False, False, False],
        }
    )


def test_warmup_rows_dropped_and_alignment_kept() -> None:
    out = build_features(_tiny_frame(), WINDOWS)
    # max window = 3 -> the first 2 rows have null aggregates and are dropped
    assert out.height == 3
    assert out["cpu"].to_list() == [3.0, 4.0, 5.0]
    assert out["ts"].to_list()[0] == datetime(2024, 1, 1, 0, 2)
    assert out["is_anomaly"].to_list() == [False, False, False]
    assert out.null_count().sum_horizontal().item() == 0


def test_rolling_mean_values() -> None:
    out = build_features(_tiny_frame(), WINDOWS)
    # row 3 (cpu=4): mean(3,4)=3.5 over w=2; mean(2,3,4)=3 over w=3
    row = out.row(1, named=True)
    assert row["cpu_rmean2"] == pytest.approx(3.5)
    assert row["cpu_rmean3"] == pytest.approx(3.0)
    # row 5 (cpu=5): mean(4,5)=4.5; mean(3,4,5)=4
    row = out.row(2, named=True)
    assert row["cpu_rmean2"] == pytest.approx(4.5)
    assert row["cpu_rmean3"] == pytest.approx(4.0)


def test_rolling_std_values() -> None:
    out = build_features(_tiny_frame(), WINDOWS)
    row = out.row(1, named=True)
    # std(3,4) ddof=1 = sqrt(0.5); std(2,3,4) ddof=1 = 1
    assert row["cpu_rstd2"] == pytest.approx(0.7071067811865476)
    assert row["cpu_rstd3"] == pytest.approx(1.0)
    # constant signals have exactly zero rolling std
    assert row["mem_rstd2"] == pytest.approx(0.0)
    assert row["latency_ms_rstd3"] == pytest.approx(0.0)


def test_feature_column_naming() -> None:
    cols = feature_columns(WINDOWS)
    assert len(cols) == 3 * len(WINDOWS) * 2
    assert "cpu_rmean10" not in cols
    assert "cpu_rmean2" in cols and "latency_ms_rstd3" in cols


def test_single_window() -> None:
    out = build_features(_tiny_frame(), [2])
    assert out.height == 4
    assert "cpu_rmean2" in out.columns
    assert "cpu_rmean3" not in out.columns
