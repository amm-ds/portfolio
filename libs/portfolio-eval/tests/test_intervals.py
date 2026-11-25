"""Tests for deterministic shared interval helpers."""

import numpy as np
import pytest
from numpy.typing import NDArray
from portfolio_eval.intervals import cluster_bootstrap, paired_bootstrap, wilson_interval


def mean_delta(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
    return float(np.mean(a - b))


def test_wilson_interval_handles_all_successes() -> None:
    lo, hi = wilson_interval(20, 20)
    assert 0.0 < lo < 1.0
    assert hi == 1.0


def test_paired_bootstrap_is_reproducible() -> None:
    a = np.array([1.0, 2.0, 4.0, 8.0])
    b = np.array([0.5, 1.0, 2.0, 4.0])
    first = paired_bootstrap(a, b, mean_delta, n_resamples=100, seed=42)
    second = paired_bootstrap(a, b, mean_delta, n_resamples=100, seed=42)
    assert first == second


def test_identical_inputs_have_zero_width_delta_interval() -> None:
    values = np.array([1.0, 3.0, 2.0, 9.0])
    point, lo, hi = paired_bootstrap(values, values, mean_delta, n_resamples=100)
    assert point == 0.0
    assert lo == hi == 0.0


def test_cluster_bootstrap_keeps_cluster_rows_together() -> None:
    a = np.array([1.0, 1.0, 3.0, 3.0, 8.0, 8.0])
    b = np.zeros_like(a)
    clusters = np.array(["a", "a", "b", "b", "c", "c"])
    point, lo, hi = cluster_bootstrap(a, b, clusters, mean_delta, n_resamples=200)
    assert point == pytest.approx(4.0)
    assert 1.0 <= lo <= hi <= 8.0


def test_cluster_bootstrap_preserves_strata() -> None:
    a = np.array([0.0, 0.0, 0.0, 0.0, 10.0, 10.0, 10.0, 10.0])
    b = np.zeros_like(a)
    clusters = np.array(["a", "a", "b", "b", "c", "c", "d", "d"])
    strata = np.array(["low", "low", "low", "low", "high", "high", "high", "high"])
    point, lo, hi = cluster_bootstrap(a, b, clusters, mean_delta, n_resamples=200, strata=strata)
    assert point == 5.0
    assert lo == hi == 5.0


def test_bootstrap_rejects_misaligned_inputs() -> None:
    with pytest.raises(ValueError, match="same length"):
        paired_bootstrap([1.0], [1.0, 2.0], mean_delta)
    with pytest.raises(ValueError, match="aligned"):
        cluster_bootstrap([1.0], [1.0], ["a", "b"], mean_delta)
