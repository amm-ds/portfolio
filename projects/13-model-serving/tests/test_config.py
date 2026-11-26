"""Config: params.yaml round-trip and validator behavior."""

from pathlib import Path

import pytest
from model_serving.config import BenchConfig, ServingConfig, load_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_params_yaml_round_trip() -> None:
    cfg = load_config(PROJECT_ROOT / "params.yaml")
    assert cfg.seed == 42
    assert cfg.lgbm.n_estimators == 1500
    assert cfg.lgbm.hpo_trials == 50
    assert cfg.lag_mode == "timestamp"
    assert cfg.pruning_rule == "keep_higher_mi"
    assert cfg.onnx_opset == 15
    assert cfg.bench.concurrency_levels == [1, 4, 16, 64]
    assert cfg.bench.batch_sizes == [1, 8, 32, 128]
    assert cfg.champion_expected_test_mae == pytest.approx(23.76360139335002)
    assert cfg.comparison_mlp_test_mae == pytest.approx(27.161182233265468)
    assert cfg.parity_tolerance == 1e-4


def test_bench_validators_reject_bad_grids() -> None:
    with pytest.raises(ValueError):
        BenchConfig(concurrency_levels=[0, 4])
    with pytest.raises(ValueError):
        BenchConfig(batch_sizes=[-1])
    cfg = BenchConfig(concurrency_levels=[8, 1, 4])
    assert cfg.concurrency_levels == [1, 4, 8]  # sorted+deduped


def test_image_ref() -> None:
    cfg = ServingConfig()
    assert cfg.image_ref == "portfolio-model-serving:13"
