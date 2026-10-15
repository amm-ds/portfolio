"""Config validation + params.yaml round-trip tests (offline)."""

from __future__ import annotations

from pathlib import Path

import yaml
from inference_serving.config import (
    BenchConfig,
    ModelSpec,
    load_config,
)


def test_load_config_defaults_when_file_missing(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "nope.yaml")
    assert [m.name for m in cfg.models] == [
        "qwen3.6:35b-a3b-q4_K_M",
        "gemma4:31b",
        "gpt-oss:20b",
    ]
    assert [m.name for m in cfg.full_models] == ["qwen3:32b"]
    assert len(cfg.quality_models) == 1 and cfg.quality_models[0].role == "quality"
    assert {m.name for m in cfg.engine_models} == {
        "gemma4:31b-it-q8_0",
        "gemma4:31b-mlx",
    }
    assert cfg.concurrency_default == [1, 4, 8]


def test_params_yaml_roundtrip() -> None:
    """Every field in params.yaml must be accepted by BenchConfig (ADR-0002)."""
    params_path = Path(__file__).parent.parent / "params.yaml"
    params = yaml.safe_load(params_path.read_text(encoding="utf-8"))
    cfg = load_config(params_path)
    for key in params:
        assert key in BenchConfig.model_fields, f"params.yaml key {key!r} not in BenchConfig"
    assert [m.name for m in cfg.models] == [m["name"] for m in params["models"]]
    assert cfg.cloud_usd_per_mtok_output["gpt-oss:20b"] == 0.40
    assert cfg.repeats == params["repeats"]


def test_plan_cells_bounded_and_full() -> None:
    from inference_serving.bench import plan_cells, plan_quality_cells

    params_path = Path(__file__).parent.parent / "params.yaml"
    cfg = load_config(params_path)
    bounded = plan_cells(cfg, full=False)
    assert len(bounded) == 3 * 3  # 3 primary models x 3 concurrency levels
    assert plan_cells(cfg, full=True) != bounded  # full adds the dense arm + c=2
    assert len(plan_cells(cfg, full=True)) == 4 * 4
    # quality cells only in full mode; engine cells in both
    assert len(plan_quality_cells(cfg, full=False)) == 2
    assert len(plan_quality_cells(cfg, full=True)) == 3


def test_modelspec_requires_name() -> None:
    try:
        ModelSpec(name="")
    except Exception:
        return
    raise AssertionError("empty model name must fail validation")
