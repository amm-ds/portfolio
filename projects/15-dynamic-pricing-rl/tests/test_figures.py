"""E2-9 figure contracts built from sealed artifacts without policy execution."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from dynamic_pricing.figures import build_figures
from portfolio_core.plotting import CATEGORICAL_PALETTE

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _artifacts() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    reports = PROJECT_ROOT / "reports"
    return (
        json.loads((reports / "metrics.json").read_text()),
        json.loads((reports / "test_episodes.json").read_text()),
        json.loads((PROJECT_ROOT / "data" / "calibration.json").read_text()),
    )


def test_figure_set_uses_sealed_evidence_and_shared_palette() -> None:
    metrics, episodes, calibration = _artifacts()
    figures = build_figures(metrics, episodes, calibration)
    assert set(figures) == {
        "profit_vs_baselines",
        "price_traces",
        "bound_share_by_rho",
        "calibration_overview",
    }
    profit = figures["profit_vs_baselines"]
    assert len(profit.data) == 6
    assert profit.data[4].marker.color in CATEGORICAL_PALETTE
    assert profit.data[4].x[0] == metrics["test"]["policies"]["RL"]["mean_normalised_profit"]
    assert profit.data[4].error_x.arrayminus[0] > 0
    lower = min(trace.x[0] - trace.error_x.arrayminus[0] for trace in profit.data)
    upper = max(trace.x[0] + trace.error_x.array[0] for trace in profit.data)
    assert profit.layout.xaxis.range[0] < lower
    assert profit.layout.xaxis.range[1] > upper


def test_price_traces_are_the_three_complete_fixed_seed_captures() -> None:
    metrics, episodes, calibration = _artifacts()
    figure = build_figures(metrics, episodes, calibration)["price_traces"]
    assert len(figure.data) == 6
    assert all(len(trace.x) == 91 for trace in figure.data)
    assert figure.layout.xaxis.range == (0, 90)
    assert figure.layout.yaxis.range == (0.68, 1.32)
    for trace in figure.data:
        assert np.min(trace.y) >= 0.70
        assert np.max(trace.y) <= 1.30


def test_calibration_histograms_cover_all_observed_values() -> None:
    metrics, episodes, calibration = _artifacts()
    figure = build_figures(metrics, episodes, calibration)["calibration_overview"]
    assert len(figure.data) == 3
    assert all(len(trace.x) == 600 for trace in figure.data)
    for trace, axis in zip(
        figure.data,
        (figure.layout.xaxis, figure.layout.xaxis2, figure.layout.xaxis3),
        strict=True,
    ):
        assert axis.range[0] == 0
        assert axis.range[1] > float(np.max(trace.x))
