"""Reconciliation: coherence property and shrinkage estimation."""

import numpy as np
import polars as pl
from demand_forecasting.config import ForecastConfig
from demand_forecasting.reconcile import (
    _store_panel,
    apply_shrinkage,
    estimate_shrinkage,
    fit_shrinkage,
)


def test_coherence_property_exact() -> None:
    """Reconciled incoherence is exactly (1 - w) times the original."""
    rng = np.random.default_rng(0)
    child_sums = rng.normal(100, 10, 200)
    parent_preds = child_sums + rng.normal(0, 5, 200)  # incoherent forecasts
    for w in (0.0, 0.25, 0.5, 0.9, 1.0):
        reconciled, remaining = apply_shrinkage(child_sums, parent_preds, w)
        incoherence_before = np.mean(np.abs(parent_preds - child_sums))
        incoherence_after = np.mean(np.abs(remaining))
        np.testing.assert_allclose(incoherence_after, (1 - w) * incoherence_before, rtol=1e-12)
        # reconciliation moves sums toward the parent, never past it
        assert np.all(np.abs(parent_preds - reconciled) <= np.abs(parent_preds - child_sums) + 1e-9)


def test_shrinkage_precision_ratio() -> None:
    """Discrepancy dominated by signal → w near 1; dominated by noise → w small."""
    rng = np.random.default_rng(1)
    child_sums = rng.normal(100, 10, 500)
    # signal-dominated: discrepancy variance >> child residual variance
    parent_sig = child_sums + rng.normal(0, 30, 500)
    res_small = rng.normal(0, 1, (500, 4))
    w_sig = estimate_shrinkage(child_sums, parent_sig, np.var(res_small, axis=1))
    assert w_sig > 0.9
    # noise-dominated: discrepancy tiny relative to child residuals
    parent_noisy = child_sums + rng.normal(0, 0.5, 500)
    res_large = rng.normal(0, 20, (500, 4))
    w_noise = estimate_shrinkage(child_sums, parent_noisy, np.var(res_large, axis=1))
    assert 0.0 <= w_noise < 0.1


def test_shrinkage_is_clamped() -> None:
    """Degenerate inputs (zero variances) must not escape [0, 1]."""
    const = np.ones(10) * 50.0
    w = estimate_shrinkage(const, const, np.zeros(10))
    assert 0.0 <= w <= 1.0


def test_fit_shrinkage_prefers_accurate_parent() -> None:
    """Grid shrinkage trusts an accurate parent (w→1) and ignores a noisy one (w→0)."""
    rng = np.random.default_rng(2)
    true = rng.normal(200, 20, 300)
    child_sums = true + rng.normal(0, 8, 300)  # decent children
    good_parent = true + rng.normal(0, 2, 300)  # better than children
    bad_parent = true + rng.normal(0, 40, 300)  # much worse
    assert fit_shrinkage(child_sums, good_parent, true) >= 0.9
    assert fit_shrinkage(child_sums, bad_parent, true) <= 0.1


def test_store_panel_aggregation(panel: pl.DataFrame, config: ForecastConfig) -> None:
    """Store-level aggregation sums the products per (date, store)."""
    store_panel = _store_panel(panel)
    assert store_panel.height == config.n_days * config.n_stores
    one_day = store_panel.filter(
        (pl.col("date") == panel["date"][0]) & (pl.col("store") == "store_0")
    )["units"][0]
    expected = panel.filter((pl.col("date") == panel["date"][0]) & (pl.col("store") == "store_0"))[
        "units"
    ].sum()
    assert one_day == expected
