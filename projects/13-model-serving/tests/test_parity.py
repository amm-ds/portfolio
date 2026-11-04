"""Parity gate: the ONNX artifact computes the native function within 1e-4."""

import numpy as np
import pytest
from model_serving.artifacts import ParityError, check_parity, probe_grid, raw_onnx_predict
from model_serving.config import ServingConfig
from model_serving.mlp import MLPRegressor


def test_parity_gate_passes_on_tiny_champion(parity_checked: dict[str, object]) -> None:
    """Native vs ONNX on the seeded probe grid stays three orders under the gate."""
    assert parity_checked["parity_max_abs"] <= 1e-4


def test_check_parity_raises_beyond_tolerance() -> None:
    native = np.zeros(4)
    onnx = np.full(4, 2e-4)
    with pytest.raises(ParityError, match="parity gate failed"):
        check_parity(native, onnx, 1e-4)
    # Exactly at tolerance passes (gate is >, not >=).
    assert check_parity(native, np.full(4, 1e-4), 1e-4) == 1e-4


def test_probe_grid_is_seeded_and_contract_ordered(
    tiny_models: dict[str, object],
) -> None:
    cfg = tiny_models["cfg"]
    selected = tiny_models["selected"]
    assert isinstance(cfg, ServingConfig)
    a = probe_grid(32, cfg.seed, selected)  # type: ignore[arg-type]
    b = probe_grid(32, cfg.seed, selected)  # type: ignore[arg-type]
    np.testing.assert_array_equal(a.to_numpy(), b.to_numpy())
    assert list(a.columns) == ["hour", *selected]
    assert a["hour"].between(0, 23).all()
    assert a["weathersit"].between(1, 4).all()


def test_onnx_matches_native_predictions_end_to_end(
    parity_checked: dict[str, object],
) -> None:
    """End-to-end (rentals scale) the two backends agree within float32 noise."""
    reg = parity_checked["reg"]
    cfg = parity_checked["cfg"]
    selected = parity_checked["selected"]
    assert isinstance(reg, MLPRegressor) and isinstance(cfg, ServingConfig)
    grid = probe_grid(64, 123, selected)  # type: ignore[arg-type]
    native = reg.predict(grid)
    meta_y_std = reg.y_std
    onnx_scaled = raw_onnx_predict(parity_checked["models_dir"], grid, selected)  # type: ignore[arg-type]
    onnx = onnx_scaled * meta_y_std + reg.y_mean
    assert float(np.max(np.abs(native - onnx))) < 1e-2
