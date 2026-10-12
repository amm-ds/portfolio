"""ChurnConfig validation tests."""

import pytest
from churn_pipeline.config import ChurnConfig
from pydantic import ValidationError


def test_defaults_match_spec() -> None:
    cfg = ChurnConfig()
    assert cfg.n_samples == 5000
    assert cfg.test_frac == 0.2
    assert cfg.seed == 42
    assert len(cfg.threshold_grid) == 41
    assert cfg.threshold_grid[0] == 0.0 and cfg.threshold_grid[-1] == 1.0
    assert cfg.fp_cost == 1.0 and cfg.fn_cost == 5.0


def test_rejects_bad_test_frac() -> None:
    with pytest.raises(ValidationError):
        ChurnConfig(test_frac=0.8)


def test_rejects_empty_c_grid() -> None:
    with pytest.raises(ValidationError):
        ChurnConfig(c_grid=[])


def test_rejects_non_positive_c_grid() -> None:
    with pytest.raises(ValidationError):
        ChurnConfig(c_grid=[0.0, 1.0])


def test_rejects_threshold_outside_unit_interval() -> None:
    with pytest.raises(ValidationError):
        ChurnConfig(threshold_grid=[0.1, 1.5])


def test_rejects_unsorted_threshold_grid() -> None:
    with pytest.raises(ValidationError):
        ChurnConfig(threshold_grid=[0.8, 0.2, 0.5])


def test_rejects_non_positive_costs() -> None:
    with pytest.raises(ValidationError):
        ChurnConfig(fn_cost=0.0)


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        ChurnConfig(**{"surprise": 1})  # type: ignore[arg-type]
