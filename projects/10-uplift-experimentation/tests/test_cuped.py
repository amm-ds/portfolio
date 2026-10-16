"""CUPED: variance reduction on a synthetic covariate, unbiasedness, edge cases."""

import numpy as np
import pytest
from uplift_experimentation.cuped import (
    cuped_adjust,
    cuped_theta,
    effect_and_se,
    variance_reduction,
)


def test_variance_reduction_positive_on_synthetic_covariate() -> None:
    # y = x + noise: a pre-period covariate explaining most of the variance.
    rng = np.random.default_rng(7)
    x = rng.normal(0.0, 1.0, 20_000)
    y = 0.1 + x + rng.normal(0.0, 0.2, 20_000)
    theta = cuped_theta(y, x)
    assert theta == pytest.approx(1.0, rel=0.05)
    y_adj = cuped_adjust(y, x, theta, float(x.mean()))
    reduction = variance_reduction(y, y_adj)
    assert 0.9 < reduction < 1.0  # ~96%: 1 - 0.04 in this construction


def test_cuped_preserves_the_mean() -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(5.0, 2.0, 5_000)
    y = rng.binomial(1, 0.05, 5_000)
    theta = cuped_theta(y, x)
    y_adj = cuped_adjust(y, x, theta, float(x.mean()))
    assert float(y_adj.mean()) == pytest.approx(float(y.mean()), abs=1e-9)


def test_cuped_effect_estimate_unchanged_on_randomized_data() -> None:
    # Randomized assignment: adjustment must not move the ATE, only the SE.
    rng = np.random.default_rng(11)
    n = 20_000
    treatment = rng.integers(0, 2, n)
    x = rng.normal(0.0, 1.0, n)
    y = rng.binomial(1, np.clip(0.1 + 0.02 * (x > 0) + treatment * 0.01, 0, 1))
    ate_naive, se_naive = effect_and_se(y, treatment)
    theta = cuped_theta(y, x)
    y_adj = cuped_adjust(y, x, theta, float(x.mean()))
    ate_adj, se_adj = effect_and_se(y_adj, treatment)
    # Randomization makes the shift pure Monte-Carlo noise, far inside one SE.
    assert abs(ate_adj - ate_naive) < 0.1 * se_naive
    assert se_adj < se_naive


def test_cuped_theta_exact_on_linear_relation() -> None:
    x = np.arange(100, dtype=float)
    y = 3.0 * x + 7.0
    assert cuped_theta(y, x) == pytest.approx(3.0)


def test_zero_variance_covariate_raises() -> None:
    with pytest.raises(ValueError, match="zero variance"):
        cuped_theta(np.ones(10), np.ones(10))


def test_zero_variance_outcome_raises() -> None:
    with pytest.raises(ValueError, match="zero variance"):
        variance_reduction(np.ones(10), np.ones(10) * 0.5)
