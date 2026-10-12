"""Metrics sanity: platform regression metrics on hand-checkable arrays."""

import math

from portfolio_eval.ml import regression_metrics


def test_perfect_forecast_zero_error() -> None:
    y = [10.0, 20.0, 30.0, 40.0]
    metrics = {m.name: m.value for m in regression_metrics(y, y)}
    assert metrics["mae"] == 0.0
    assert metrics["rmse"] == 0.0
    assert metrics["mape_pct"] == 0.0


def test_known_errors_exact() -> None:
    """MAE/RMSE over all rows; MAPE skips zero actuals."""
    y_true = [10.0, 20.0, 0.0, 40.0]
    y_pred = [12.0, 20.0, 5.0, 36.0]
    metrics = {m.name: m.value for m in regression_metrics(y_true, y_pred)}
    assert metrics["mae"] == (2.0 + 0.0 + 5.0 + 4.0) / 4
    assert metrics["rmse"] == math.sqrt((4.0 + 0.0 + 25.0 + 16.0) / 4)
    # MAPE over non-zero actuals only: mean(0.2, 0.0, 0.1) * 100
    assert metrics["mape_pct"] == (0.2 + 0.0 + 0.1) / 3 * 100


def test_regression_metrics_lower_is_better() -> None:
    for m in regression_metrics([1.0, 2.0], [1.5, 1.5]):
        assert m.higher_is_better is False


def test_mape_all_zeros_is_nan() -> None:
    metrics = {m.name: m.value for m in regression_metrics([0.0, 0.0], [1.0, 2.0])}
    assert math.isnan(metrics["mape_pct"])
