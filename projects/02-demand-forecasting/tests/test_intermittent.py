"""Hand-computed cases for the intermittent-demand toolkit.

Croston/SBA/TSB recursions are reproduced inline (independent loops written
against the documented update rules, not by calling the implementation) so a
regression in the library code fails here loudly.
"""

import numpy as np
import pytest
from demand_forecasting.intermittent import (
    classify_demand,
    croston_forecast,
    sba_forecast,
    statistical_forecast,
    tsb_forecast,
)

# Shared hand case: demand on days 2, 6, 11 with sizes 5, 3, 2.
Y = np.array([0, 0, 5, 0, 0, 0, 3, 0, 0, 0, 0, 2], dtype=float)
ALPHA = 0.5


def _ses_reference(values: list[float], alpha: float) -> float:
    """Reference SES written against the documented rule (level = first obs)."""
    level = values[0]
    for v in values[1:]:
        level = alpha * v + (1 - alpha) * level
    return level


def test_croston_hand_computed() -> None:
    sizes = [5.0, 3.0, 2.0]
    intervals = [3.0, 4.0, 5.0]  # gaps: day 2 (3rd day), then +4, +5
    z = _ses_reference(sizes, ALPHA)
    p = _ses_reference(intervals, ALPHA)
    expected = np.full(4, z / p)
    assert z == pytest.approx(3.0)
    assert p == pytest.approx(4.25)
    assert np.allclose(croston_forecast(Y, 4, alpha=ALPHA), expected)


def test_sba_is_croston_scaled() -> None:
    expected = croston_forecast(Y, 3, alpha=ALPHA) * (1 - ALPHA / 2)
    assert np.allclose(sba_forecast(Y, 3, alpha=ALPHA), expected)


def test_tsb_hand_computed() -> None:
    """Reference TSB loop: p updates every period, z on demand periods only."""
    alpha_d = alpha_p = ALPHA
    p = 1.0 if Y[0] > 0 else 0.0
    z = 5.0  # first non-zero size
    for t in range(1, Y.size):
        p = alpha_p * (1.0 if Y[t] > 0 else 0.0) + (1 - alpha_p) * p
        if Y[t] > 0:
            z = alpha_d * Y[t] + (1 - alpha_d) * z
    assert np.allclose(tsb_forecast(Y, 3, alpha_d=ALPHA, alpha_p=ALPHA), np.full(3, p * z))
    assert p * z == pytest.approx(1.5498046875)


def test_flat_methods_are_flat_and_zero_series_is_zero() -> None:
    for fn in (croston_forecast, sba_forecast):
        out = fn(Y, 6, alpha=ALPHA)
        assert out.shape == (6,)
        assert np.allclose(out, out[0])
    assert np.allclose(croston_forecast(np.zeros(10), 3), np.zeros(3))
    assert np.allclose(tsb_forecast(np.zeros(10), 3), np.zeros(3))
    assert np.allclose(statistical_forecast("zero", Y, 4), np.zeros(4))


def test_statistical_forecast_rejects_non_flat_method() -> None:
    with pytest.raises(ValueError, match="not a flat statistical"):
        statistical_forecast("seasonal_naive", Y, 4)


def test_classify_quadrants() -> None:
    smooth = np.array([3, 4, 2, 5, 3, 4, 2, 5, 3, 4], dtype=float)
    assert classify_demand(smooth)["class"] == "smooth"
    erratic = np.array([1, 10, 1, 10, 1, 10, 1, 10], dtype=float)
    assert classify_demand(erratic)["class"] == "erratic"
    # ADI = 15/11 ≈ 1.36 with low size variance: 11 non-zero days (mostly 4s)
    intermittent = np.array([4, 4, 0, 4, 4, 4, 0, 4, 4, 0, 4, 4, 0, 4, 4], dtype=float)
    entry = classify_demand(intermittent)
    assert entry["class"] == "intermittent"
    assert entry["adi"] == pytest.approx(15 / 11)
    assert entry["cv2"] == pytest.approx(0.3636, abs=1e-3)
    lumpy = np.array([8, 0, 0, 3, 0, 0, 0, 2, 0, 0, 0, 0], dtype=float)
    assert classify_demand(lumpy)["class"] == "lumpy"


def test_classify_all_zero_series() -> None:
    entry = classify_demand(np.zeros(8))
    assert entry["adi"] == pytest.approx(8.0)
    assert entry["cv2"] == float("inf")
    assert entry["class"] == "lumpy"
