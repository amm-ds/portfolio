"""Streaming-detection tests: drift statistic, fixed vs. adaptive, artifacts."""

from pathlib import Path

import numpy as np
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.data import prepare
from anomaly_detection.features import build_features
from anomaly_detection.model import feature_matrix, fit_models, save_models, split_train_test
from anomaly_detection.stream import drift_z, run_detection


@pytest.fixture()
def stream_config(tmp_path: Path) -> AnomalyConfig:
    return AnomalyConfig(
        n=2_000,
        data_dir=str(tmp_path / "data"),
        reports_dir=str(tmp_path / "reports"),
    )


def _train_detectors(config: AnomalyConfig) -> None:
    df = build_features(prepare(config), config.windows)
    train, _ = split_train_test(df, config.train_frac)
    save_models(fit_models(feature_matrix(train, config), config), config)


def test_drift_z_robust_statistic() -> None:
    """Median shift in units of reference IQR; zero-IQR guard."""
    assert drift_z(np.array([0.0, 0.1, -0.1]), 0.0, 1.0) == pytest.approx(0.0)
    assert drift_z(np.array([3.0, 3.1, 2.9]), 0.0, 1.0) == pytest.approx(3.0)
    assert drift_z(np.array([1.0, 2.0]), 0.0, 0.0) == 0.0


def test_run_detection_fixed_vs_adaptive(stream_config: AnomalyConfig) -> None:
    _train_detectors(stream_config)
    result = run_detection(stream_config, chunk_rows=200, drift_z_max=1.0)
    # n=2 000 → 1 941 complete rows → 583 test rows → ceil(583/200) = 3 chunks
    assert result["n_chunks"] == 3
    assert result["fixed"]["flags"] > 0
    assert result["adaptive"]["flags"] > 0
    assert "recall" in result["fixed"] and "precision" in result["fixed"]
    assert isinstance(result["drift_events"], list)
    assert (stream_config.reports_path / "detect.json").exists()
    assert (stream_config.figures_dir / "adaptive_stream.json").exists()


def test_run_detection_fixed_mode_only(stream_config: AnomalyConfig) -> None:
    _train_detectors(stream_config)
    result = run_detection(stream_config, adaptive=False, chunk_rows=200)
    assert "adaptive" not in result
    assert "drift_events" not in result
    assert result["fixed"]["flags"] > 0
