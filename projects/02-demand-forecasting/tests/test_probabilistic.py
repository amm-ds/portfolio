"""Probabilistic forecasts: coverage metrics and conformal calibration."""

import json

import numpy as np
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.probabilistic import coverage, run_probabilistic


def test_coverage_exact() -> None:
    """Empirical coverage is the fraction of points inside the band."""
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert coverage(y, np.array([0.0, 0.0, 0.0, 0.0]), np.array([5.0, 5.0, 5.0, 5.0])) == 1.0
    assert coverage(y, np.array([1.5, 1.5, 1.5, 1.5]), np.array([2.5, 2.5, 2.5, 2.5])) == 0.25
    assert (
        coverage(y, np.array([10.0, 10.0, 10.0, 10.0]), np.array([11.0, 11.0, 11.0, 11.0])) == 0.0
    )


def test_run_probabilistic_on_fixture(
    settings: DemandSettings, config: ForecastConfig, features
) -> None:
    """End-to-end on the small fixture: coverages near target, artefacts written."""
    from demand_forecasting.features import save_features

    save_features(features, settings)
    result = run_probabilistic(settings, config)

    pooled = result["quantile_band"]["coverage_pooled"]
    assert 0.5 <= pooled <= 1.0  # loose: small-sample fixture
    assert result["split_conformal"]["q80"] >= 0.0
    assert 0.0 <= result["split_conformal"]["coverage_last_fold"] <= 1.0
    # conformal band always contains its own p50 centre
    assert result["split_conformal"]["q80"] >= 0.0

    persisted = json.loads((settings.reports_dir / "probabilistic.json").read_text())
    assert persisted["target_coverage"] == 0.8
    conf = persisted["split_conformal"]
    assert len(conf["horizon_coverage"]) == 14 == len(conf["horizon_avg_width"])
    assert conf["calibration_verdict"] in {"calibrated", "conservative", "optimistic"}
    assert 0.0 <= conf["coverage_horizon_set"] <= 1.0
    assert conf["avg_width_horizon_set"] >= 0.0
    assert (settings.reports_dir / "figures" / "probabilistic_band.html").exists()
    assert (settings.reports_dir / "figures" / "probabilistic_band.json").exists()


def test_conformal_band_covers_calibration_target() -> None:
    """On exchangeable noise, split-conformal coverage approaches the target."""
    rng = np.random.default_rng(0)
    n = 6000
    y = 50 + rng.normal(0, 10, n)
    resid = np.abs(rng.normal(0, 10, n))
    q80 = float(np.quantile(resid[:4000], 0.8))
    # imperfect but exchangeable centre forecast on the holdout
    centre = y[4000:] + rng.normal(0, 10, n - 4000)
    cov = coverage(y[4000:], centre - q80, centre + q80)
    assert 0.75 <= cov <= 0.85
