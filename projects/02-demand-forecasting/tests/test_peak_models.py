"""Wave-20 peak-capable candidates: hand-computed math for the hurdle point
forecast, the tweedie estimator construction, the peak-feature tensor, the
window peak-capture metrics and the selection-origin zero-correction choice.
"""

import numpy as np
import pytest
from demand_forecasting.config import ForecastConfig
from demand_forecasting.multihorizon import (
    N_PEAK_FEATURES,
    N_PRICE_FEATURES,
    N_ROLLING_FEATURES,
    PEAK_FEATURE_NAMES,
    TWEEDIE_POWER,
    OriginScore,
    _fit_tweedie,
    _window_peak_arrays,
    apply_hurdle_correction,
    hurdle_point,
    peak_feature_tensor,
)
from sklearn._loss.loss import HalfTweedieLoss


def test_hurdle_point_hand_computed() -> None:
    # p=0.5, log_size=log(4) -> size = exp(log 4) - 1 = 3 -> point = 1.5
    out = hurdle_point(np.array([0.5, 0.25]), np.array([np.log(4.0), np.log(3.0)]))
    assert out[0] == pytest.approx(1.5)
    assert out[1] == pytest.approx(0.25 * 2.0)
    # negative sizes (log of a value < 1) clip at 0
    assert hurdle_point(np.array([0.9]), np.array([np.log(0.5)]))[0] == pytest.approx(0.0)
    # probabilities are clipped into [0, 1]
    assert hurdle_point(np.array([1.4]), np.array([np.log(2.0)]))[0] == pytest.approx(1.0)


def test_tweedie_estimator_construction() -> None:
    config = ForecastConfig()
    model = _fit_tweedie(config)
    assert isinstance(model.loss, HalfTweedieLoss)
    assert TWEEDIE_POWER == 1.5
    # sklearn keeps the variance power on the inner cy loss
    assert model.loss.closs.power == TWEEDIE_POWER
    n_num = 9 + 3 + N_PEAK_FEATURES + N_PRICE_FEATURES + N_ROLLING_FEATURES
    assert model.categorical_features == [n_num, n_num + 1]
    # tuned params flow from the config
    assert model.learning_rate == pytest.approx(config.multistep_tweedie.learning_rate)
    assert model.max_leaf_nodes == config.multistep_tweedie.max_leaf_nodes


def test_peak_feature_tensor_hand_computed() -> None:
    """One series, deterministic pattern — every column pinned by hand."""
    y = np.zeros((30, 1))
    y[3, 0] = 4.0
    y[7, 0] = 10.0
    y[8, 0] = 2.0
    y[20, 0] = 6.0
    pf = peak_feature_tensor(y)[:, 0, :]
    assert pf.shape == (30, N_PEAK_FEATURES)
    col = {name: i for i, name in enumerate(PEAK_FEATURE_NAMES)}
    # day 9, 7d window [3..9]: mean = (4+10+2)/7, max = 10
    assert pf[9, col["roll_mean_7"]] == pytest.approx(16.0 / 7.0)
    assert pf[9, col["roll_max_7"]] == pytest.approx(10.0)
    # 28d windows follow the full-window convention: undefined (0.0) before
    # day 27, so the 28d non-zero count at day 9 is 0, not the clipped count
    assert pf[9, col["nz_count_28"]] == pytest.approx(0.0)
    assert pf[9, col["days_since_last_nz"]] == pytest.approx(1.0)
    # day 0: no non-zero day yet -> days_since_last_nz = r + 1
    assert pf[0, col["days_since_last_nz"]] == pytest.approx(1.0)
    # day 29, 28d window [2..29]: mean = (4+10+2+6)/28, max = 10, 4 non-zero
    # days, last non-zero 9 days back
    assert pf[29, col["roll_mean_28"]] == pytest.approx(22.0 / 28.0)
    assert pf[29, col["roll_max_28"]] == pytest.approx(10.0)
    assert pf[29, col["peak_ratio_28"]] == pytest.approx(10.0 / (22.0 / 28.0))
    assert pf[29, col["nz_count_28"]] == pytest.approx(4.0)
    assert pf[29, col["days_since_last_nz"]] == pytest.approx(9.0)
    # all-zero 28d window -> peak ratio 0 (no division by zero)
    z = np.zeros((30, 1))
    pfz = peak_feature_tensor(z)[:, 0, :]
    assert pfz[29, col["peak_ratio_28"]] == pytest.approx(0.0)


def test_window_peak_metrics_hand_computed() -> None:
    """One window (1 origin x 7 horizons x 2 series) with known peaks; all
    window values distinct so the top-k rankings are unambiguous."""
    y3 = np.array(
        [[[1.0, 1.0], [2.0, 2.0], [9.0, 3.0], [4.0, 4.0], [5.0, 5.0], [0.0, 6.0], [3.0, 7.0]]]
    )
    pred3 = np.array(
        [[[1.0, 7.0], [2.0, 6.0], [8.0, 5.0], [4.0, 4.0], [6.0, 3.0], [0.0, 2.0], [3.0, 1.0]]]
    )
    peak_mae, recall = _window_peak_arrays(y3, pred3, k=1)
    # series 0: top-1 actual day is h-index 2 (9.0); |8-9| = 1
    # series 1: top-1 actual day is h-index 6 (7.0); |1-7| = 6
    assert peak_mae[0, 0] == pytest.approx(1.0)
    assert peak_mae[0, 1] == pytest.approx(6.0)
    # series 0: top-5 actual {2,4,6,3,1} (values 9,5,3,4,2); forecast top-5
    # {2,4,6,3,1} (values 8,6,3,4,2) -> recall 1.0
    assert recall[0, 0] == pytest.approx(1.0)
    # series 1: top-5 actual {6,5,4,3,2}; forecast top-5 {0,1,2,3,4}
    # (values 7,6,5,4,3) -> intersection {2,3,4} -> recall 0.6
    assert recall[0, 1] == pytest.approx(0.6)


def test_zero_correction_picks_the_selection_origin_winner() -> None:
    """Identity / scalar / isotonic compared on selection origins only; the
    min-MAE mapping wins and is applied to every origin (incl. test)."""
    horizons = [1, 3]  # origin 0 scores days 1,3; origin 1 scores days 2,4 (disjoint)
    units = np.array(
        [
            [0.0, 0.0],
            [0.0, 0.0],  # origin 0, h=1 (selection)
            [4.0, 2.0],  # origin 1, h=1 (test — must not be read)
            [2.0, 0.0],  # origin 0, h=3 (selection)
            [2.0, 0.0],  # origin 1, h=3 (test)
        ]
    )

    def _score(origin: int, raw: np.ndarray) -> OriginScore:
        return OriginScore(
            origin=origin,
            preds={"hurdle_hgb": raw.copy()},
            quantiles={},
            hurdle_raw={"hurdle_hgb": raw.copy()},
        )

    # raw over-predicts everywhere; the scalar shrink (sum y / sum raw on the
    # SELECTION cells = 2/16 = 0.125) is the best fix and beats identity
    raw = np.array([[4.0, 4.0], [4.0, 4.0]])  # both horizons, both series
    by_origin = {0: _score(0, raw), 1: _score(1, np.array([[100.0, 100.0], [100.0, 100.0]]))}
    info = apply_hurdle_correction(by_origin, [0], horizons, units, ("hurdle_hgb",))
    assert info["hurdle_hgb"]["chosen"] == "scalar"
    assert info["hurdle_hgb"]["scalar_factor"] == pytest.approx(0.125)
    assert (
        info["hurdle_hgb"]["selection_mae"]["scalar"]
        < info["hurdle_hgb"]["selection_mae"]["identity"]
    )
    # the test origin's stored preds were corrected by the same mapping
    np.testing.assert_allclose(by_origin[1].preds["hurdle_hgb"], 12.5)

    # perfect raw forecasts on the selection window -> identity wins (the
    # "test, don't assume" branch: no correction when none helps)
    raw2 = np.array([[0.0, 0.0], [2.0, 0.0]])
    by_origin2 = {0: _score(0, raw2), 1: _score(1, raw2)}
    info2 = apply_hurdle_correction(by_origin2, [0], horizons, units, ("hurdle_hgb",))
    assert info2["hurdle_hgb"]["chosen"] == "identity"
    assert info2["hurdle_hgb"]["selection_mae"]["identity"] == pytest.approx(0.0)
