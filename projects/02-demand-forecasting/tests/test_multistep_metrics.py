"""Multi-step track math: pinball, RMSSE, coverage/width/verdict, bootstrap,
order-up-to cost — every formula pinned by a hand-computed case.
"""

import math

import numpy as np
import pytest
from demand_forecasting.multihorizon import (
    _paired_bootstrap_mae,
    order_up_to_cost,
    pinball_loss,
    rmsse_pooled,
)
from demand_forecasting.probabilistic import calibration_verdict


def test_pinball_hand_computed() -> None:
    y = np.array([0.0, 4.0])
    q = np.array([1.0, 2.0])
    # tau=0.5: max(0.5*(0-1), -0.5*(0-1)) = 0.5 ; max(0.5*2, -0.5*2) = 1.0
    assert pinball_loss(y, q, 0.5) == pytest.approx(0.75)
    # over-forecast at tau=0.9 costs 0.9*|miss|; under costs 0.1*|miss|
    assert pinball_loss(np.array([10.0]), np.array([0.0]), 0.9) == pytest.approx(9.0)
    assert pinball_loss(np.array([0.0]), np.array([10.0]), 0.9) == pytest.approx(1.0)


def test_rmsse_hand_computed() -> None:
    # two series, four cells each; scales and volumes known exactly
    series = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    err = np.array([1.0, -1.0, 2.0, 0.0, 3.0, 0.0, 0.0, 0.0])
    scale2 = np.array([4.0] * 4 + [9.0] * 4)
    volume = np.array([10.0] * 4 + [20.0] * 4)
    pooled, weighted = rmsse_pooled(err, scale2, volume, series)
    # series 0: MSE = (1+1+4+0)/4 = 1.5 -> sqrt(1.5/4)
    # series 1: MSE = 9/4 = 2.25 -> sqrt(2.25/9) = 0.5
    assert pooled == pytest.approx((math.sqrt(1.5 / 4) + 0.5) / 2)
    assert weighted == pytest.approx((math.sqrt(1.5 / 4) * 10 + 0.5 * 20) / 30)


def test_rmsse_excludes_zero_scale_series() -> None:
    series = np.array([0, 0, 1, 1])
    err = np.array([5.0, 5.0, 1.0, 1.0])
    scale2 = np.array([0.0] * 2 + [4.0] * 2)
    volume = np.ones(4)
    pooled, _ = rmsse_pooled(err, scale2, volume, series)
    assert pooled == pytest.approx(math.sqrt(1.0 / 4.0))


def test_calibration_verdict_rule() -> None:
    assert calibration_verdict(0.78) == "calibrated"
    assert calibration_verdict(0.80) == "calibrated"
    assert calibration_verdict(0.86) == "conservative"
    assert calibration_verdict(0.74) == "optimistic"


def test_coverage_width_verdict_on_hand_band() -> None:
    y = np.array([0.0, 1.0, 2.0, 5.0])
    lo = np.array([0.0, 0.0, 1.0, 1.0])
    hi = np.array([1.0, 2.0, 3.0, 4.0])  # sorted, zero-clipped
    covered = (y >= lo) & (y <= hi)
    assert covered.tolist() == [True, True, True, False]
    assert covered.mean() == pytest.approx(0.75)
    assert (hi - lo).mean() == pytest.approx(2.0)  # widths [1, 2, 2, 3]
    assert calibration_verdict(float(covered.mean())) == "optimistic"


def test_order_up_to_cost_hand_computed() -> None:
    order = np.array([2.0, 0.0, 7.0])
    y = np.array([1.0, 3.0, 5.0])
    # leftover: (2-1) + 0 + (7-5) = 3 units held; short: 0 + 3 + 0 = 3 units
    assert order_up_to_cost(order, y, holding_cost=0.25, stockout_cost=4.0) == pytest.approx(
        0.25 * 3 + 4.0 * 3
    )


def test_paired_bootstrap_establishes_and_missed_differences() -> None:
    rng = np.random.default_rng(7)
    n = 40
    series = np.repeat(np.arange(8), n // 8)
    y = rng.poisson(6.0, n).astype(float)
    same = _paired_bootstrap_mae(y - 1.0, y - 1.0, series, n_boot=500, seed=1)
    assert same["diff"] == pytest.approx(0.0)
    assert same["spans_zero"]
    # a clearly worse forecast must have a CI excluding zero
    worse = _paired_bootstrap_mae(y - 1.0, y + 4.0, series, n_boot=500, seed=1)
    assert worse["diff"] == pytest.approx(-5.0)
    assert not worse["spans_zero"]
    assert worse["ci95"][1] < 0.0


def test_paired_bootstrap_is_deterministic_under_seed() -> None:
    rng = np.random.default_rng(3)
    n = 32
    series = np.repeat(np.arange(4), 8)
    y = rng.poisson(4.0, n).astype(float)
    a = _paired_bootstrap_mae(y, y + 1.0, series, n_boot=200, seed=9)
    b = _paired_bootstrap_mae(y, y + 1.0, series, n_boot=200, seed=9)
    assert a == b
