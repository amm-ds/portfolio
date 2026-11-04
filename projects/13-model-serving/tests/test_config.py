"""Config: params.yaml round-trip and validator behavior."""

from pathlib import Path

import pytest
from model_serving.config import BenchConfig, ServingConfig, load_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_params_yaml_round_trip() -> None:
    cfg = load_config(PROJECT_ROOT / "params.yaml")
    assert cfg.seed == 42
    assert cfg.mlp.hidden_dims == [64, 32]
    assert cfg.mlp.embed_dim == 8
    assert cfg.onnx_opset == 17
    assert cfg.bench.concurrency_levels == [1, 4, 16, 64]
    assert cfg.bench.batch_sizes == [1, 8, 32, 128]
    assert cfg.champion_expected_test_mae > 0
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
