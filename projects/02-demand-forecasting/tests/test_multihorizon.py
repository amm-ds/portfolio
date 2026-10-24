"""Direct multi-horizon track: leakage-proof features, origin layout, direct
model shapes, routing selection-on-train-only proof, per-class table sums and
run-to-run determinism.
"""

import itertools
import json
import math

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.multihorizon import (
    _calendar_features,
    _design_pred,
    _design_train,
    _score_origin,
    _seasonal_naive_pred,
    multistep_origin_indices,
    panel_matrix,
    run_multistep,
    split_origins,
)

# Fast multi-step config: 3 horizons, 8 origins (2 test), tiny bootstrap.
MS_CONFIG = ForecastConfig(
    n_days=150,
    n_stores=2,
    n_products=2,
    lags=[1, 7],
    n_splits=3,
    gap=3,
    min_train_size=30,
    multistep_horizons=[1, 7, 14],
    multistep_n_origins=8,
    multistep_test_origins=2,
    multistep_window_days=14,
    bootstrap_reps=200,
)


def _mixed_panel() -> pl.DataFrame:
    """4 series: two smooth (daily demand), one intermittent, one lumpy."""
    dates = np.arange(
        np.datetime64("2024-01-01"), np.datetime64("2024-05-29"), dtype="datetime64[D]"
    )
    n = len(dates)
    rng = np.random.default_rng(5)
    smooth_a = rng.poisson(8.0, n).astype(float)
    smooth_b = 5.0 + 3.0 * np.sin(np.arange(n) * 2 * np.pi / 7) + rng.poisson(2, n)
    intermittent = np.zeros(n)
    intermittent[::5] = 6.0  # every 5th day -> ADI = 5, CV^2 = 0
    lumpy = np.zeros(n)
    idx = np.flatnonzero(rng.random(n) < 0.15)
    lumpy[idx] = rng.integers(1, 30, idx.size).astype(float)
    frames = []
    for store, product, units in (
        ("s0", "p0", smooth_a),
        ("s0", "p1", smooth_b),
        ("s1", "p0", intermittent),
        ("s1", "p1", lumpy),
    ):
        frames.append(
            pl.DataFrame(
                {
                    "date": dates,
                    "store": store,
                    "product": product,
                    "units": units.astype(int),
                }
            )
        )
    return pl.concat(frames)


@pytest.fixture
def mixed_panel() -> pl.DataFrame:
    return _mixed_panel()


# ---------------------------------------------------------------------------
# Leakage-proof: features for horizon h never reference actuals within h days
# ---------------------------------------------------------------------------


def test_horizon_features_ignore_actuals_within_h_days(mixed_panel: pl.DataFrame) -> None:
    """Taint every day in (origin, origin+h] — the designs must not move."""
    dates, _, units = panel_matrix(mixed_panel)
    cal = _calendar_features(dates)
    origin = 60
    for h in (1, 7, 14):
        tainted = units.copy()
        tainted[origin + 1 : origin + h + 1] += 1000.0
        x_clean, y_clean = _design_train(units, cal, origin, h)
        x_taint, y_taint = _design_train(tainted, cal, origin, h)
        np.testing.assert_array_equal(x_clean, x_taint)
        np.testing.assert_array_equal(y_clean, y_taint)
        np.testing.assert_array_equal(
            _design_pred(units, cal, origin, h), _design_pred(tainted, cal, origin, h)
        )


def test_origin_predictions_unchanged_by_tainting_the_window(
    mixed_panel: pl.DataFrame,
) -> None:
    """End-to-end: an origin's scored predictions use nothing past the origin."""
    dates, _, units = panel_matrix(mixed_panel)
    cal = _calendar_features(dates)
    origin = 70
    horizons = [1, 7, 14]
    tainted = units.copy()
    tainted[origin + 1 : origin + 15] += 1000.0
    clean = _score_origin(units, cal, origin, horizons, MS_CONFIG)
    dirty = _score_origin(tainted, cal, origin, horizons, MS_CONFIG)
    for name in clean.preds:
        np.testing.assert_allclose(clean.preds[name], dirty.preds[name], rtol=0, atol=0)
    for q in clean.quantiles:
        np.testing.assert_allclose(clean.quantiles[q], dirty.quantiles[q], rtol=0, atol=0)


def test_training_targets_never_exceed_the_origin(
    mixed_panel: pl.DataFrame,
) -> None:
    """Training rows for (origin, h) end at target = origin, i.e. all actuals
    used are at least h days older than any training target."""
    dates, _, units = panel_matrix(mixed_panel)
    cal = _calendar_features(dates)
    for origin in (40, 80):
        for h in (1, 7, 14):
            x_train, y_train = _design_train(units, cal, origin, h)
            # every y value must appear among units[0..origin]
            known = np.isin(y_train, units[: origin + 1])
            assert known.all()
            # the largest training target is exactly `origin` days old at most
            lo = 14
            hi = origin - h
            assert y_train.size == units.shape[1] * (hi - lo + 1)
            del x_train


# ---------------------------------------------------------------------------
# Origin layout: weekly, capped, no embargo gap, last-N test
# ---------------------------------------------------------------------------


def test_weekly_origins_no_gap() -> None:
    config = ForecastConfig(
        n_days=400, min_train_size=60, multistep_n_origins=20, multistep_window_days=14
    )
    origins = multistep_origin_indices(400, config)
    assert len(origins) <= 20
    assert all(b - a == 7 for a, b in itertools.pairwise(origins))
    assert origins[0] >= 59  # min_train_size dates before the first origin
    assert origins[-1] <= 400 - 14 - 1  # the 14-day window fits
    selection, test = split_origins(origins, config)
    assert test == origins[-4:]
    assert selection == origins[:-4]
    # no embargo gap: window starts the day AFTER the origin
    for o in origins:
        assert o + 14 <= 399


def test_split_origins_never_empty() -> None:
    config = ForecastConfig(min_train_size=30, multistep_test_origins=4)
    origins = list(range(29, 60, 7))
    selection, test = split_origins(origins, config)
    assert selection and test
    assert set(selection).isdisjoint(test)


# ---------------------------------------------------------------------------
# Full-run shape, classes, per-class sums, routing proof, determinism
# ---------------------------------------------------------------------------


def test_run_multistep_block_shape(mixed_panel: pl.DataFrame) -> None:
    result = run_multistep(settings=_settings(), config=MS_CONFIG, panel=mixed_panel)
    block = result.block
    assert block["protocol"] == "direct_multihorizon_v1"
    assert block["horizons"] == [1, 7, 14]
    assert block["floor"] == "seasonal_naive"
    assert len(block["origins"]["dates"]) == 8
    assert len(block["origins"]["test_dates"]) == 2
    for h in ("1", "7", "14"):
        assert "champion" in block["per_horizon"][h]
        assert "floor" in block["per_horizon"][h]
        assert "rmsse" in block["per_horizon"][h]["champion"]
    # growth curves over all horizons
    assert sorted(block["horizon_growth"]["pooled"]["routed"]) == ["1", "14", "7"]
    # coverage table present with verdicts
    prob = result.probabilistic_block
    for h in ("1", "7", "14"):
        assert "coverage" in prob["per_horizon"][h]
        assert prob["per_horizon"][h]["calibration_verdict"] in (
            "calibrated",
            "conservative",
            "optimistic",
        )


def test_per_class_table_sums(mixed_panel: pl.DataFrame) -> None:
    result = run_multistep(settings=_settings(), config=MS_CONFIG, panel=mixed_panel)
    block = result.block
    counts = block["demand_classes"]["counts"]
    assert sum(counts.values()) == 4
    assert len(block["routing"]["method_choices"]) == counts["intermittent"] + counts["lumpy"]
    # per-class series counts sum to n_series
    total = sum(entry["n_series"] for entry in block["headline_per_class"].values())
    assert total == 4
    # the mixed panel must actually contain sparse series (routing is live)
    assert counts["intermittent"] + counts["lumpy"] >= 2


def test_routing_uses_selection_origins_only(mixed_panel: pl.DataFrame) -> None:
    """Taint the LAST test window (permuting actuals across series) — that
    window is never a training row for any origin, so the fits are identical
    and the routing choice, conformal widths and every selection-origin number
    must not move, while the scored h=14 MAE does."""
    dates, series_ids, units = panel_matrix(mixed_panel)
    origins = multistep_origin_indices(len(dates), MS_CONFIG)
    _, test = split_origins(origins, MS_CONFIG)
    rng = np.random.default_rng(11)

    result = run_multistep(settings=_settings(), config=MS_CONFIG, panel=mixed_panel)
    block = result.block
    choices_before = dict(block["routing"]["method_choices"])
    widths_before = dict(result.probabilistic_block["conformal_widths_by_h"])

    tainted_units = units.copy()
    last = test[-1]
    window = tainted_units[last + 1 : last + 15].copy()
    tainted_units[last + 1 : last + 15] = rng.permutation(window.ravel()).reshape(window.shape)
    tainted_panel = _panel_from_matrix(dates, series_ids, tainted_units)
    result2 = run_multistep(settings=_settings(), config=MS_CONFIG, panel=tainted_panel)
    assert result2.block["routing"]["method_choices"] == choices_before
    assert result2.probabilistic_block["conformal_widths_by_h"] == widths_before
    # scored MAEs DID move (sanity: the taint actually changed the window)
    h14 = "14"
    assert (
        result2.block["per_horizon"][h14]["champion"]["mae"]
        != block["per_horizon"][h14]["champion"]["mae"]
    )


def test_two_runs_are_byte_identical(mixed_panel: pl.DataFrame) -> None:
    """Determinism: two full runs produce byte-identical JSON blocks."""
    a = run_multistep(settings=_settings(), config=MS_CONFIG, panel=mixed_panel)
    b = run_multistep(settings=_settings(), config=MS_CONFIG, panel=mixed_panel)
    assert json.dumps(a.block, sort_keys=True) == json.dumps(b.block, sort_keys=True)
    assert json.dumps(a.probabilistic_block, sort_keys=True) == json.dumps(
        b.probabilistic_block, sort_keys=True
    )


def test_seasonal_naive_reference_day_is_never_after_the_origin(
    mixed_panel: pl.DataFrame,
) -> None:
    _, _, units = panel_matrix(mixed_panel)
    for h in (1, 2, 3, 5, 7, 10, 14):
        k = math.ceil(h / 7)
        ref = 80 + h - 7 * k
        assert ref <= 80
        out = _seasonal_naive_pred(units, 80, [h])
        np.testing.assert_array_equal(out[:, 0], units[ref])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _settings() -> DemandSettings:
    """Settings are unused by run_multistep (merging is the caller's job)."""
    return DemandSettings()


def _panel_from_matrix(dates: np.ndarray, series_ids: list[str], units: np.ndarray) -> pl.DataFrame:
    frames = []
    for j, sid in enumerate(series_ids):
        store, _, product = sid.partition("|")
        frames.append(
            pl.DataFrame(
                {
                    "date": dates,
                    "store": store,
                    "product": product,
                    "units": units[:, j].astype(int),
                }
            )
        )
    return pl.concat(frames)
