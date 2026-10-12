"""Shared fixtures: small configs rooted in tmp dirs (never the repo)."""

from pathlib import Path

import pytest
from anomaly_detection.config import AnomalyConfig


@pytest.fixture()
def small_config(tmp_path: Path) -> AnomalyConfig:
    """Fast config: 2k rows, artifacts under pytest's tmp_path."""
    return AnomalyConfig(
        n=2_000,
        data_dir=str(tmp_path / "data"),
        reports_dir=str(tmp_path / "reports"),
    )
