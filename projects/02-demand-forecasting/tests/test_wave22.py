"""Wave-22: the ma_28 / ADIDA statistical candidates (hand-computed math),
the rolling-feature block (leakage taint + hand values), the hierarchy
anchoring allocation branches, the rmae / per-candidate rmsse blocks, the
newsvendor order-quantile cost layer, and the byte-determinism of the new
candidates — every formula pinned on a tiny case.
"""

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import ForecastConfig
from demand_forecasting.intermittent import STATISTICAL_METHODS, adida_forecast, ma_28_forecast
from demand_forecasting.multihorizon import (
    CANDIDATES,
    ML_SPARSE,
    N_ROLLING_FEATURES,
    ROLLING_FEATURE_NAMES,
    OriginScore,
    _calendar_features,
    _ladder_quantile,
    _newsvendor,
    _reconciled_pred,
    _rmae_cells,
    _rmsse_cells,
    _score_origin,
    _statistical_preds,
    panel_matrix,
    rolling_feature_tensor,
)

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


# ---------------------------------------------------------------------------
# ma_28: rolling 28-day mean, flat across the window
# ---------------------------------------------------------------------------


def test_ma_28_hand_computed() -> None:
    y = np.arange(1.0, 29.0)  # 1..28, mean 14.5
    out = ma_28_forecast(y, 4)
    np.testing.assert_array_equal(out, [14.5] * 4)
    # shorter windows average over what exists
    short = np.array([2.0, 4.0, 6.0])
    np.testing.assert_array_equal(ma_28_forecast(short, 2), [4.0, 4.0])
    # empty history -> zeros
    np.testing.assert_array_equal(ma_28_forecast(np.array([]), 3), [0.0, 0.0, 0.0])


# ---------------------------------------------------------------------------
# ADIDA: bucket alignment + SBA/TSB base + profile disaggregation + edges
# ---------------------------------------------------------------------------

# n = 28 daily points; bucket 7 aligned to the end gives 4 bucket totals
# [7, 0, 7, 0] (demand 7 at t=6 and t=20).
_ADIDA_Y = np.zeros(28)
_ADIDA_Y[6] = 7.0
_ADIDA_Y[20] = 7.0


def _sba_on_buckets() -> float:
    """SBA by hand on the bucket series [7, 0, 7, 0] with alpha = 0.1.

    sizes = [7, 7] -> SES level stays 7; intervals = [1, 2] -> SES level =
    0.1 x 2 + 0.9 x 1 = 1.1. Croston = 7 / 1.1; SBA scales by 1 - 0.1/2.
    """
    return (7.0 / 1.1) * 0.95


def _tsb_on_buckets() -> float:
    """TSB by hand on [7, 0, 7, 0] with alpha = 0.1: p seeded 1.0, z seeded 7.

    t=1: p = 0.9 x 1.0 = 0.9 (no demand); t=2: p = 0.1 + 0.9 x 0.9 = 0.91,
    z = 7; t=3: p = 0.9 x 0.91 = 0.819. Forecast = 0.819 x 7.
    """
    return 0.819 * 7.0


def test_adida_aggregation_alignment_and_profile() -> None:
    """Buckets are 7-day non-overlapping totals aligned to the END of the
    training window; the window abuts the origin so o+1..o+14 is exactly 2
    buckets. The profile assigns each forecast day the training demand share
    of its position class: demand sits at t ≡ 6 (mod 7), and (28 + k) % 7 ==
    k, so only profile position 6 is non-zero."""
    out = adida_forecast("sba", _ADIDA_Y, 14)
    base = _sba_on_buckets()
    expected = np.zeros(14)
    expected[6] = base  # bucket 0, position 6
    expected[13] = base  # bucket 1, position 6
    np.testing.assert_allclose(out, expected, rtol=0, atol=1e-12)
    # the two bucket totals are the whole forecast: sum = 2 x base
    assert out.sum() == pytest.approx(2 * base)
    # TSB base on the same buckets
    out_tsb = adida_forecast("tsb", _ADIDA_Y, 14)
    assert out_tsb[6] == pytest.approx(_tsb_on_buckets())
    assert out_tsb[13] == pytest.approx(_tsb_on_buckets())
    assert out_tsb.sum() == pytest.approx(2 * _tsb_on_buckets())
    # a horizon shorter than one bucket still disaggregates bucket 0 only
    out3 = adida_forecast("sba", _ADIDA_Y, 3)
    np.testing.assert_allclose(out3, [0.0, 0.0, 0.0], rtol=0, atol=0)
    # unknown base methods raise
    with pytest.raises(ValueError, match="base method"):
        adida_forecast("croston", _ADIDA_Y, 14)


def test_adida_all_zero_history_is_all_zero() -> None:
    """Edge case 1: an all-zero training profile -> an all-zero forecast."""
    z = np.zeros(28)
    for method in ("sba", "tsb"):
        np.testing.assert_array_equal(adida_forecast(method, z, 14), np.zeros(14))
    # shorter than one bucket: no fit possible -> zeros
    short = np.array([1.0, 0.0, 2.0])
    np.testing.assert_array_equal(adida_forecast("sba", short, 14), np.zeros(14))


def test_adida_positive_bucket_zero_profile_spreads_uniformly() -> None:
    """Edge case 2: a positive bucket forecast under an all-zero profile
    spreads uniformly (bucket_total / 7 per day). The branch lives in the pure
    disaggregation helper — through the public entry point a zero profile
    implies zero bucket totals (the all-zero-history guard fires first), so
    the helper is exercised directly here."""
    from demand_forecasting.intermittent import _adida_disaggregate

    out = _adida_disaggregate(np.array([14.0, 14.0]), np.zeros(7), 14, 7)
    np.testing.assert_allclose(out, [2.0] * 14, rtol=0, atol=1e-12)
    # a normal profile disaggregates per position (pinned above, rechecked
    # here at the helper boundary)
    prof = np.zeros(7)
    prof[6] = 1.0
    out2 = _adida_disaggregate(np.array([7.0]), prof, 9, 7)
    expected = np.zeros(9)
    expected[6] = 7.0
    np.testing.assert_allclose(out2, expected, rtol=0, atol=1e-12)


def test_statistical_preds_shape_matches_statistical_methods() -> None:
    """The multi-step engine emits one (n_series x window) matrix per
    statistical method, all deterministic and recomputable."""
    rng = np.random.default_rng(4)
    units = np.where(rng.random((60, 3)) < 0.2, rng.integers(1, 9, (60, 3)), 0).astype(float)
    preds = _statistical_preds(units, origin=50, window=14)
    for name in ("croston", "sba", "tsb", "ma_28", "adida_sba", "adida_tsb"):
        assert preds[name].shape == (3, 14)
    again = _statistical_preds(units, origin=50, window=14)
    for name, mat in preds.items():
        np.testing.assert_array_equal(mat, again[name])


# ---------------------------------------------------------------------------
# Rolling features: hand values + the leakage taint contract
# ---------------------------------------------------------------------------


def test_rolling_feature_tensor_hand_computed() -> None:
    y = np.zeros((30, 1))
    y[9, 0] = 7.0
    y[10, 0] = 3.0
    rf = rolling_feature_tensor(y)[:, 0, :]
    assert rf.shape == (30, N_ROLLING_FEATURES)
    col = {name: i for i, name in enumerate(ROLLING_FEATURE_NAMES)}
    # r=13, 7d window [7..13]: mean = 10/7
    assert rf[13, col["rmean7"]] == pytest.approx(10.0 / 7.0)
    # r=13, 14d window [0..13]: mean = 10/14; std (ddof 0) = sqrt(58/14 - (10/14)^2)
    assert rf[13, col["rmean14"]] == pytest.approx(10.0 / 14.0)
    assert rf[13, col["rstd14"]] == pytest.approx(np.sqrt(58.0 / 14.0 - (10.0 / 14.0) ** 2))
    # r=13, 28d window undefined (r < 27) -> 0.0
    assert rf[13, col["rmean28"]] == pytest.approx(0.0)
    assert rf[13, col["rstd28"]] == pytest.approx(0.0)
    # r=29, 28d window [2..29]: same two spikes -> mean 10/28
    assert rf[29, col["rmean28"]] == pytest.approx(10.0 / 28.0)
    # constant window -> std exactly 0
    c = np.full((30, 1), 5.0)
    rc = rolling_feature_tensor(c)[:, 0, :]
    assert rc[29, col["rstd28"]] == pytest.approx(0.0)


def test_rolling_features_ignore_post_reference_day_actuals() -> None:
    """Taint contract: demand AFTER the reference day must not move any
    rolling feature at or before it (the >= h-day aging, same as the lags)."""
    rng = np.random.default_rng(3)
    units = rng.integers(0, 12, (60, 4)).astype(float)
    rf = rolling_feature_tensor(units)
    for origin in (28, 40, 50):
        tainted = units.copy()
        tainted[origin + 1 :] = 999.0
        rf_taint = rolling_feature_tensor(tainted)
        np.testing.assert_array_equal(rf[: origin + 1], rf_taint[: origin + 1])


# ---------------------------------------------------------------------------
# Hierarchy anchoring: the allocation branches pinned by hand
# ---------------------------------------------------------------------------


def _score_stub(origin: int, preds: dict[str, np.ndarray]) -> OriginScore:
    shape = next(iter(preds.values()))
    full = {
        "direct_hgb": np.zeros_like(shape),
        "seasonal_naive": np.zeros_like(shape),
        **{name: np.zeros_like(shape) for name in (*STATISTICAL_METHODS, *ML_SPARSE)},
        **preds,
    }
    return OriginScore(origin=origin, preds=full, quantiles={})


def _reconcile_fixture(routed_key: str, routed_col: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """3 series: countries A, A, B; origin 20; horizons [7] (j=0, reference
    day 20). Returns (units, out)."""
    units = np.zeros((21, 3))
    units[20] = [10.0, 0.0, 4.0]
    # training-window means [2, 1, 3]: sum over rows 0..20 = 21 * mean,
    # minus the row-20 contribution
    units[0, 0] = 2.0 * 21 - 10.0  # 32
    units[1, 1] = 1.0 * 21  # 21 (row 20 is 0 for series 1)
    units[2, 2] = 3.0 * 21 - 4.0  # 59
    country_of = np.array(["A", "A", "B"], dtype=object)
    sparse = np.array([True, True, True])
    method_of = np.array([routed_key] * 3, dtype=object)
    sc = _score_stub(20, {routed_key: routed_col.reshape(3, 1)})
    out = _reconciled_pred(units, sc, 0, sparse, method_of, country_of, [7])
    return units, out


def test_reconciled_proportional_allocation() -> None:
    """Routed forecasts [1, 3] in country A: anchor 10, sum 4, discrepancy 6
    allocated 1:3 -> [1 + 1.5, 3 + 4.5] = [2.5, 7.5]; country B's single
    member takes the full discrepancy -> 2 + (4 - 2) = 4."""
    _, out = _reconcile_fixture("sba", np.array([1.0, 3.0, 2.0]))
    np.testing.assert_allclose(out, [2.5, 7.5, 4.0], rtol=0, atol=1e-12)


def test_reconciled_all_zero_forecasts_fall_back_to_train_means() -> None:
    """All member forecasts zero: the discrepancy allocates proportionally to
    the training-window means (2:1 in country A, 3 in country B)."""
    _, out = _reconcile_fixture("zero", np.array([0.0, 0.0, 0.0]))
    np.testing.assert_allclose(out, [20.0 / 3.0, 10.0 / 3.0, 4.0], rtol=0, atol=1e-12)


def test_reconciled_zero_forecast_member_gets_nothing() -> None:
    """A zero-forecast member with a positive block sum receives no share of
    the discrepancy (0:4 split in country A)."""
    _, out = _reconcile_fixture("sba", np.array([0.0, 4.0, 0.0]))
    np.testing.assert_allclose(out, [0.0, 10.0, 4.0], rtol=0, atol=1e-12)


def test_reconciled_all_zero_block_gets_no_adjustment() -> None:
    """Anchor zero, forecasts zero, training means zero -> no adjustment
    (the all-zero fallback branch)."""
    units = np.zeros((21, 3))
    country_of = np.array(["A", "A", "B"], dtype=object)
    sparse = np.array([True, True, True])
    method_of = np.array(["zero"] * 3, dtype=object)
    sc = _score_stub(20, {"zero": np.zeros((3, 1))})
    out = _reconciled_pred(units, sc, 0, sparse, method_of, country_of, [7])
    np.testing.assert_array_equal(out, np.zeros(3))


# ---------------------------------------------------------------------------
# rmae + per-candidate rmsse: hand-computed cases
# ---------------------------------------------------------------------------


def _metric_cells(y: np.ndarray, pred: dict[str, np.ndarray]) -> dict:
    n = y.size
    return {
        "series": np.repeat(np.arange(2), n // 2),
        "origin": np.zeros(n, dtype=int),
        "h": np.ones(n, dtype=int),
        "y": y,
        "class": np.array(["lumpy"] * n, dtype=object),
        "scale2": np.array([4.0] * (n // 2) + [9.0] * (n // 2)),
        "volume": np.array([10.0] * (n // 2) + [20.0] * (n // 2)),
        "pred": pred,
    }


def test_rmae_hand_computed() -> None:
    """rmae = candidate pooled MAE / floor pooled MAE over the same cells."""
    y = np.array([10.0, 10.0, 10.0, 10.0])
    floor = np.array([12.0, 8.0, 20.0, 10.0])  # errs [2, 2, 10, 0] -> MAE 3.5
    cand = np.array([9.0, 12.0, 0.0, 10.0])  # errs [1, 2, 10, 0] -> MAE 13/4
    cells = _metric_cells(y, {"seasonal_naive": floor, "routed": cand})
    full = np.ones(4, dtype=bool)
    assert _rmae_cells(cells, full, "seasonal_naive") == pytest.approx(1.0)
    assert _rmae_cells(cells, full, "routed") == pytest.approx((13.0 / 4.0) / 3.5)
    # per-class mask behaves identically on a single-class panel
    assert _rmae_cells(cells, cells["class"] == "lumpy", "routed") == pytest.approx(
        (13.0 / 4.0) / 3.5
    )


def test_rmsse_cells_hand_computed() -> None:
    """M5 convention on two (series x origin) units:
    series 0: MSE = (0 + 4)/2 = 2 over scale2 = 4 -> sqrt(0.5)
    series 1: MSE = (4 + 0)/2 = 2 over scale2 = 9 -> sqrt(2/9)."""
    y = np.array([2.0, 4.0, 1.0, 1.0])
    cand = np.array([2.0, 6.0, 3.0, 1.0])
    cells = _metric_cells(y, {"routed": cand})
    full = np.ones(4, dtype=bool)
    pooled, weighted = _rmsse_cells(cells, full, "routed")
    s0 = np.sqrt(2.0 / 4.0)
    s1 = np.sqrt(2.0 / 9.0)
    assert pooled == pytest.approx((s0 + s1) / 2)
    assert weighted == pytest.approx((s0 * 10.0 + s1 * 20.0) / 30.0)
    # zero-scale units are excluded, not infinite
    cells_z = _metric_cells(y, {"routed": cand})
    cells_z["scale2"] = np.array([0.0, 0.0, 9.0, 9.0])
    pooled_z, _ = _rmsse_cells(cells_z, full, "routed")
    assert pooled_z == pytest.approx(s1)


# ---------------------------------------------------------------------------
# Newsvendor: band-ladder interpolation + the cost hand case
# ---------------------------------------------------------------------------


def test_ladder_quantile_hand_computed() -> None:
    p10 = np.array([1.0, 2.0])
    p50 = np.array([3.0, 4.0])
    p90 = np.array([5.0, 6.0])
    # q=0.8: p50 + 0.3 x (p90-p50)/0.4
    np.testing.assert_allclose(_ladder_quantile(0.8, p10, p50, p90), [4.5, 5.5])
    # q=0.95: extrapolation above p90 with the p50->p90 slope
    np.testing.assert_allclose(_ladder_quantile(0.95, p10, p50, p90), [5.25, 6.25])
    # q=0.5 = p50; below p50 uses the p10->p50 slope (3 - 0.2 x 5 = 2)
    np.testing.assert_allclose(_ladder_quantile(0.5, p10, p50, p90), [3.0, 4.0])
    np.testing.assert_allclose(_ladder_quantile(0.3, p10, p50, p90), [2.0, 3.0])
    # zero-clipped
    p10n = np.array([-4.0])
    np.testing.assert_allclose(_ladder_quantile(0.3, p10n, np.array([0.0]), np.array([2.0])), [0.0])


def _newsvendor_fixture() -> tuple[np.ndarray, dict, np.ndarray, np.ndarray, ForecastConfig]:
    """One sparse lumpy series (demand 2 at t=0 and t=7 only) + one dense
    erratic series (all-zero demand, band ladder p10=1/p50=3/p90=5). Two scored
    cells on the sparse series (origin 14, h=1 with y=4; h=2 with y=0) and one
    on the dense series (h=1, y=6). 2024-01-01 is a Monday: targets t=15 (Tue)
    and t=16 (Wed) have all-zero weekday histories for the sparse series."""
    dates = np.arange(
        np.datetime64("2024-01-01"), np.datetime64("2024-01-21"), dtype="datetime64[D]"
    )
    units = np.zeros((20, 2))
    units[0, 0] = 2.0
    units[7, 0] = 2.0
    cells: dict = {
        "series": np.array([0, 0, 1]),
        "origin": np.array([14, 14, 14]),
        "h": np.array([1, 2, 1]),
        "y": np.array([4.0, 0.0, 6.0]),
        "class": np.array(["lumpy", "lumpy", "erratic"], dtype=object),
        # per-SERIES sparsity (series 0 lumpy/sparse, series 1 erratic/dense)
        "sparse": np.array([True, False]),
        "p10": np.array([0.0, 0.0, 1.0]),
        "p50": np.array([0.0, 0.0, 3.0]),
        "p90": np.array([0.0, 0.0, 5.0]),
    }
    sparse = cells.pop("sparse")
    config = ForecastConfig(bootstrap_reps=200)
    return dates, cells, units, sparse, config


def test_newsvendor_hand_computed() -> None:
    dates, cells, units, sparse, config = _newsvendor_fixture()
    out = _newsvendor(dates, cells, units, sparse, config)
    assert out["simulation"] is True
    assert out["cost_assumptions"]["holding_cost_per_unit_ordered_unsold_per_day"] == 1.0
    assert out["cost_assumptions"]["stockout_cost_per_unit_short_per_day"] == 3.0
    lumpy = out["per_class"]["lumpy"]
    erratic = out["per_class"]["erratic"]
    # sparse orders = history quantiles: q95 of [2,0,...0] (15 values) = 2;
    # the floor's weekday-filtered history (Tue/Wed) is all zero
    q95 = lumpy["q_0.95"]
    assert q95["routed_cost_per_unit_demand"] == pytest.approx(2.0)  # (6 + 2) / 4
    assert q95["floor_cost_per_unit_demand"] == pytest.approx(3.0)  # 12 / 4
    assert q95["routed_minus_floor"]["diff"] == pytest.approx(-1.0)
    assert q95["routed_minus_floor"]["n_boot"] == 200
    # dense orders interpolate the band ladder: q80 -> 4.5, q95 -> 5.25
    e80 = erratic["q_0.80"]
    assert e80["routed_cost_per_unit_demand"] == pytest.approx(4.5 / 6.0)
    assert e80["floor_cost_per_unit_demand"] == pytest.approx(3.0)  # 18 / 6
    e95 = erratic["q_0.95"]
    assert e95["routed_cost_per_unit_demand"] == pytest.approx(2.25 / 6.0)
    for cls in ("lumpy", "erratic"):
        for q in ("q_0.80", "q_0.90", "q_0.95"):
            item = out["per_class"][cls][q]
            assert isinstance(item["routed_minus_floor"]["spans_zero"], bool)


# ---------------------------------------------------------------------------
# Determinism of the new candidates (byte-identity across fits)
# ---------------------------------------------------------------------------


def _tiny_panel() -> pl.DataFrame:
    dates = np.arange(
        np.datetime64("2024-01-01"), np.datetime64("2024-05-29"), dtype="datetime64[D]"
    )
    n = len(dates)
    rng = np.random.default_rng(5)
    frames = []
    for i in range(3):
        units = np.where(rng.random(n) < 0.2, rng.integers(1, 25, n), 0)
        frames.append(
            pl.DataFrame(
                {
                    "date": dates,
                    "store": f"s{i % 2}",
                    "product": f"p{i}",
                    "units": units.astype(int),
                }
            )
        )
    return pl.concat(frames)


def test_new_candidates_are_byte_deterministic() -> None:
    """Two full origin fits must reproduce the wave-22 candidates bit-for-bit
    (the byte-identity determinism contract covers the new code paths —
    statistical fits, rolling features, and the score-origin body)."""
    dates, _sids, units = panel_matrix(_tiny_panel())
    cal = _calendar_features(dates)
    a = _score_origin(units, cal, 70, [1, 7, 14], MS_CONFIG)
    b = _score_origin(units, cal, 70, [1, 7, 14], MS_CONFIG)
    for name in ("ma_28", "adida_sba", "adida_tsb"):
        np.testing.assert_array_equal(a.preds[name], b.preds[name], err_msg=name)
    for s in a.shocked:
        for name in ("ma_28", "adida_sba", "adida_tsb"):
            np.testing.assert_array_equal(a.shocked[s][name], b.shocked[s][name])
    # every committed candidate is produced at the origin (the routed-family
    # keys are assembled downstream: peak_weighted_hgb by choose_peak_weight,
    # routed/ensemble_convex/routed_reconciled from routing inputs)
    for name in CANDIDATES:
        if name in ("routed", "ensemble_convex", "routed_reconciled", "peak_weighted_hgb"):
            continue
        assert name in a.preds, name
