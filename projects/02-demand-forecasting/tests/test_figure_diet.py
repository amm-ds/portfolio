"""Regression tests for compact, non-duplicated forecast figures."""

import polars as pl
import pytest
from demand_forecasting.evaluate import figure_eda_units_distribution
from demand_forecasting.m5_full import CANDIDATES
from demand_forecasting.m5_full_figures import fig_pooling_panel


def test_units_distribution_is_prebinned() -> None:
    units = [0, 0, 1, 2, 3, 5, 8, 13]
    fig = figure_eda_units_distribution(pl.DataFrame({"units": units}))

    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"
    assert len(fig.data[0].x) == 60
    assert sum(fig.data[0].y) == len(units)
    assert fig.data[0].customdata.shape == (60, 2)


def test_pooling_panel_uses_full_panel_bias_and_zero_day_metrics() -> None:
    test = {
        candidate: {
            "bias": index / 100.0,
            "zero_day_accuracy": 0.5 + index / 100.0,
            "zero_day_accuracy_intermittent": 0.6 + index / 100.0,
        }
        for index, candidate in enumerate(CANDIDATES)
    }
    fig = fig_pooling_panel({"test": test})

    assert len(fig.data) == 3
    assert fig.data[0].name == "bias"
    assert list(fig.data[0].y) == pytest.approx(list(range(len(CANDIDATES))))
    assert fig.data[1].name == "all zero-actual days"
    assert fig.data[2].name == "intermittent series"
    assert "Forecast bias and quiet-day accuracy" in str(fig.layout.title.text)
