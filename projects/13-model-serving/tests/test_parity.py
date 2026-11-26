"""Parity gate: the ONNX artifact computes the native function within tolerance."""

import numpy as np
import pytest
from model_serving.artifacts import ParityError, check_parity, probe_grid, raw_onnx_predict
from model_serving.config import ServingConfig


def test_parity_gate_passes_on_tiny_champion(parity_checked: dict[str, object]) -> None:
    """Native vs ONNX on the seeded probe grid stays inside the gated limit."""
    cfg = parity_checked["cfg"]
    assert isinstance(cfg, ServingConfig)
    max_abs = parity_checked["parity_max_abs"]
    assert isinstance(max_abs, float)
    # the gate is tolerance + float32 relative term on the raw prediction
    assert max_abs <= cfg.parity_tolerance + 1e-5 * 1e3


def test_check_parity_raises_beyond_tolerance() -> None:
    native = np.zeros(4)
    onnx = np.full(4, 2e-4)
    with pytest.raises(ParityError, match="parity gate failed"):
        check_parity(native, onnx, 1e-4)
    # Exactly at tolerance passes (gate is >, not >=).
    assert check_parity(native, np.full(4, 1e-4), 1e-4) == 1e-4


def test_check_parity_relative_term_covers_float32_noise() -> None:
    """An ill-scaled model (outputs O(100s)) is gated by the relative term."""
    native = np.full(4, 700.0)
    onnx = native + 1.5e-4  # float32-scale noise on a 700-rental output
    assert check_parity(native, onnx, 1e-4) == pytest.approx(1.5e-4)


def test_probe_grid_is_seeded_and_contract_ordered(
    tiny_models: dict[str, object],
) -> None:
    cfg = tiny_models["cfg"]
    selected = tiny_models["selected"]
    assert isinstance(cfg, ServingConfig)
    a = probe_grid(32, cfg.seed, selected)  # type: ignore[arg-type]
    b = probe_grid(32, cfg.seed, selected)  # type: ignore[arg-type]
    np.testing.assert_array_equal(a.to_numpy(), b.to_numpy())
    assert list(a.columns) == list(selected)  # type: ignore[arg-type]
    assert a["weathersit"].between(1, 4).all()
    assert a["atemp"].between(0, 1).all()


def test_onnx_matches_native_predictions_end_to_end(
    parity_checked: dict[str, object],
) -> None:
    """End-to-end (rentals scale) the two backends agree within float32 noise."""
    model = parity_checked["model"]
    cfg = parity_checked["cfg"]
    selected = parity_checked["selected"]
    assert isinstance(cfg, ServingConfig)
    grid = probe_grid(64, 123, selected)  # type: ignore[arg-type]
    native = model.predict(grid[selected])  # type: ignore[union-attr,index]
    onnx = raw_onnx_predict(parity_checked["models_dir"], grid, selected)  # type: ignore[arg-type]
    assert float(np.max(np.abs(native - onnx))) < 1e-2
