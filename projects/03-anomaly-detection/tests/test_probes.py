"""Probe tests: rolling-median residual features vs. the base feature space."""

from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.features import build_features, feature_columns
from anomaly_detection.probes import run_residual_probe


def _tiny_frame() -> pl.DataFrame:
    """Self-contained copy of the fixture in test_features.py — test modules must
    not import each other (basename collisions across projects in workspace runs)."""
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


def test_residual_columns_added(tmp_path: Path) -> None:
    out = build_features(_tiny_frame(), [2, 3], residuals=True)
    cols = feature_columns([2, 3], residuals=True)
    assert "cpu_resmed2" in cols and "latency_ms_resmed3" in cols
    assert len(cols) == 18  # 12 base + 6 residual
    # cpu = [1..5]; rolling median w=2 of [2,3] is 2.5 -> residual 0.5 at cpu=3
    row = out.row(0, named=True)
    assert row["cpu_resmed2"] == pytest.approx(0.5)
    # rolling median w=3 of [1,2,3] is 2 -> residual 1.0 at cpu=3
    assert row["cpu_resmed3"] == pytest.approx(1.0)
    # constant signals have exactly zero residual
    assert row["mem_resmed2"] == pytest.approx(0.0)


def test_residual_probe_runs_and_reports(tmp_path: Path) -> None:
    config = AnomalyConfig(n=1_500, data_dir=str(tmp_path / "d"), reports_dir=str(tmp_path / "r"))
    result = run_residual_probe(config)
    assert set(result) >= {"base", "with_residuals", "verdict"}
    assert result["base"]["n_features"] == 12
    assert result["with_residuals"]["n_features"] == 18
    for side in ("base", "with_residuals"):
        assert 0.0 <= result[side]["roc_auc"] <= 1.0
        assert result[side]["anomaly_mean_kdist"] > 0
    assert result["verdict"] in ("residuals improved ranking", "residuals did not improve ranking")
    assert (tmp_path / "r" / "residual_probe.json").exists()
