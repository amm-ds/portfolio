"""Power analysis: formula exactness against a hand calculation."""

import pytest
from uplift_experimentation.power import required_n_per_arm, z_quantile


def test_z_quantile_known_values() -> None:
    assert z_quantile(0.975) == pytest.approx(1.959964, abs=1e-6)
    assert z_quantile(0.84) == pytest.approx(0.994458, abs=1e-5)
    assert z_quantile(0.5) == pytest.approx(0.0, abs=1e-9)


def test_required_n_per_arm_hand_calculation() -> None:
    # alpha=0.05 two-sided, power=0.8, p1=0.10, p0=0.08:
    # (1.959964 + 0.841621)^2 * (0.10*0.90 + 0.08*0.92) / 0.02^2 ~ 3,210
    n = required_n_per_arm(0.10, 0.08, alpha=0.05, power=0.8)
    z_sum = 1.959964 + 0.841621
    expected = z_sum**2 * (0.10 * 0.90 + 0.08 * 0.92) / 0.02**2
    assert n == pytest.approx(expected, rel=1e-4)
    assert 3200 < n < 3220


def test_required_n_grows_as_effect_shrinks() -> None:
    small = required_n_per_arm(0.09, 0.08, alpha=0.05, power=0.8)
    large = required_n_per_arm(0.12, 0.08, alpha=0.05, power=0.8)
    assert small > large > 0


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        required_n_per_arm(0.0, 0.08, alpha=0.05, power=0.8)
    with pytest.raises(ValueError):
        required_n_per_arm(0.10, 0.10, alpha=0.05, power=0.8)  # zero effect
    with pytest.raises(ValueError):
        required_n_per_arm(0.10, 0.08, alpha=0.5, power=0.8)
    with pytest.raises(ValueError):
        z_quantile(1.5)
