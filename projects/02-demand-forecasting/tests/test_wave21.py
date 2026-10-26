"""Wave-21 candidates: price/trading-cycle features (leakage-safe), the
LightGBM family, the peak-weighted hurdle, the convex ensemble and the
per-series win-rate metric — hand-computed math on tiny cases plus
selection-origins-only proofs.
"""

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import ForecastConfig
from demand_forecasting.multihorizon import (
    ML_SPARSE,
    N_PRICE_FEATURES,
    PRICE_FEATURE_NAMES,
    OriginScore,
    _calendar_features,
    _design_pred,
    _design_train,
    _ensemble_pred,
    _fit_hurdle_lgbm_pair,
    _fit_lgbm,
    _score_origin,
    _win_rates,
    choose_peak_weight,
    ensemble_weights,
    panel_matrix,
    panel_price_matrix,
    peak_feature_tensor,
    peak_sample_weights,
    price_feature_tensor,
)

# Fast multi-step config for the _score_origin taint test (3 horizons).
MS_CONFIG = ForecastConfig(
    n_days=150,
    min_train_size=30,
    multistep_horizons=[1, 7, 14],
    multistep_n_origins=8,
    multistep_test_origins=2,
    bootstrap_reps=200,
)


@pytest.fixture
def ms_config() -> ForecastConfig:
    return MS_CONFIG


# ---------------------------------------------------------------------------
# Price feature tensor: hand-computed values + the taint contract
# ---------------------------------------------------------------------------


def test_price_feature_tensor_hand_computed() -> None:
    """One series, deterministic price path — every column pinned by hand."""
    price = np.full((30, 1), 0.5)
    price[:2, 0] = 1.0  # days 0-1 at 1.0, cut to 0.5 at day 2
    prf = price_feature_tensor(price)[:, 0, :]
    assert prf.shape == (30, N_PRICE_FEATURES)
    col = {name: i for i, name in enumerate(PRICE_FEATURE_NAMES)}
    # day 0: the first observed price counts as a change day (bounds the
    # feature; prev starts NaN so any first valid price differs)
    assert prf[0, col["days_since_price_change"]] == pytest.approx(0.0)
    # day 1: last price 1.0, one day since the day-0 observation
    assert prf[1, col["price_asof"]] == pytest.approx(1.0)
    assert prf[1, col["days_since_price_change"]] == pytest.approx(1.0)
    # day 2: the cut — asof 0.5, change day (distance 0), ratio still 1.0
    # (window [max(0, 2-27)..2] not full -> neutral), no drop flag
    assert prf[2, col["price_asof"]] == pytest.approx(0.5)
    assert prf[2, col["days_since_price_change"]] == pytest.approx(0.0)
    assert prf[2, col["price_ratio_28d"]] == pytest.approx(1.0)
    assert prf[2, col["price_drop"]] == pytest.approx(0.0)
    # day 3: one day since the change
    assert prf[3, col["days_since_price_change"]] == pytest.approx(1.0)
    # day 27: first full 28d window [0..27]: mean = (2*1.0 + 26*0.5)/28 = 15/28
    # ratio = 0.5 / (15/28) = 0.9333 -> no drop
    assert prf[27, col["price_ratio_28d"]] == pytest.approx(0.5 / (15.0 / 28.0))
    assert prf[27, col["price_drop"]] == pytest.approx(0.0)
    # a deep cut (0.39) DOES flag: ratio = 0.39 / ((2 + 26*0.39)/28) < 0.9
    deep = np.full((30, 1), 0.39)
    deep[:2, 0] = 1.0
    prf_deep = price_feature_tensor(deep)[:, 0, :]
    assert prf_deep[27, col["price_ratio_28d"]] == pytest.approx(
        0.39 / ((2.0 + 26.0 * 0.39) / 28.0)
    )
    assert prf_deep[27, col["price_drop"]] == pytest.approx(1.0)
    # never observed -> neutral asof 1.0, days_since = r+1
    never = np.zeros((30, 1))
    prf_never = price_feature_tensor(never)[:, 0, :]
    assert prf_never[5, col["price_asof"]] == pytest.approx(1.0)
    assert prf_never[5, col["days_since_price_change"]] == pytest.approx(6.0)


def test_price_features_ignore_post_reference_day_prices() -> None:
    """Taint contract: prices AFTER the reference day must not move any
    feature at or before it (the >= h-day aging, same as the peak block)."""
    rng = np.random.default_rng(3)
    price = rng.uniform(0.5, 3.0, (60, 4))
    price[10:20, 1] = np.nan  # holes exercise the forward-fill
    prf = price_feature_tensor(price)
    for origin in (28, 40, 50):
        tainted = price.copy()
        tainted[origin + 1 :] = 999.0
        prf_taint = price_feature_tensor(tainted)
        np.testing.assert_array_equal(prf[: origin + 1], prf_taint[: origin + 1])


def _priced_panel() -> pl.DataFrame:
    """4 lumpy series with a price column (cuts and hikes)."""
    dates = np.arange(
        np.datetime64("2024-01-01"), np.datetime64("2024-05-29"), dtype="datetime64[D]"
    )
    n = len(dates)
    rng = np.random.default_rng(7)
    frames = []
    for i in range(4):
        units = np.where(rng.random(n) < 0.2, rng.integers(1, 25, n), 0)
        price = np.where(rng.random(n) < 0.03, 0.5, 1.0)
        frames.append(
            pl.DataFrame(
                {
                    "date": dates,
                    "store": f"s{i % 2}",
                    "product": f"p{i}",
                    "units": units.astype(int),
                    "price": price,
                }
            )
        )
    return pl.concat(frames)


def test_origin_predictions_unchanged_by_tainting_prices_in_the_window(
    ms_config: ForecastConfig,
) -> None:
    """End-to-end price taint: an origin's scored predictions use no price
    past the origin — wild post-origin price moves change nothing."""
    panel = _priced_panel()
    dates, series_ids, units = panel_matrix(panel)
    price = panel_price_matrix(panel, dates, series_ids)
    cal = _calendar_features(dates)
    pf = peak_feature_tensor(units)
    prf = price_feature_tensor(price)
    origin, h = 70, 7
    x_train, y_train = _design_train(units, cal, pf, prf, origin, h)
    x_pred = _design_pred(units, cal, pf, prf, origin, h)
    tainted = price.copy()
    tainted[origin + 1 :] = 500.0
    prf_taint = price_feature_tensor(tainted)
    x_train_t, y_train_t = _design_train(units, cal, pf, prf_taint, origin, h)
    np.testing.assert_array_equal(x_train, x_train_t)
    np.testing.assert_array_equal(y_train, y_train_t)
    np.testing.assert_array_equal(x_pred, _design_pred(units, cal, pf, prf_taint, origin, h))
    clean = _score_origin(units, cal, origin, [1, 7, 14], ms_config, (), price)
    dirty = _score_origin(units, cal, origin, [1, 7, 14], ms_config, (), tainted)
    for name in clean.preds:
        np.testing.assert_allclose(clean.preds[name], dirty.preds[name], rtol=0, atol=0)


def test_trading_cycle_calendar_features() -> None:
    """is_month_end = the next calendar day starts a new month; week_of_month
    = (dom-1)//7 + 1. Pure functions of the target date."""
    dates = np.array(
        ["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-07", "2024-02-08"],
        dtype="datetime64[D]",
    )
    cal = _calendar_features(dates)
    is_month_end = cal[:, 7]
    week_of_month = cal[:, 8]
    assert is_month_end.tolist() == [0.0, 1.0, 0.0, 0.0, 0.0]  # only Jan 31
    assert week_of_month.tolist() == [5.0, 5.0, 1.0, 1.0, 2.0]  # Feb 8 is week 2


# ---------------------------------------------------------------------------
# peak_sample_weights + the peak-weight choice (selection origins only)
# ---------------------------------------------------------------------------


def test_peak_sample_weights_hand_computed() -> None:
    """y is series-minor: reshape(-1, n_series) gives (rows, series)."""
    y = np.array([1.0, 5.0, 2.0, 9.0, 0.0, 3.0, 4.0, 8.0])  # 4 rows x 2 series
    w = peak_sample_weights(y, 2, 2.0)
    # series 0 positives [1, 2, 4]: q90 = 3.6 -> only the 4.0 row (index 6)
    # series 1 positives [5, 9, 3, 8]: q90 = 8.7 -> only the 9.0 row (index 3)
    expected = np.ones(8)
    expected[3] = 2.0
    expected[6] = 2.0
    np.testing.assert_array_equal(w, expected)
    # a series with no positives stays at weight 1; a series with positives
    # always has its top day weighted (the max reaches the q90 threshold)
    y2 = np.array([0.0, 1.0, 0.0, 2.0])
    np.testing.assert_array_equal(peak_sample_weights(y2, 2, 3.0), [1.0, 1.0, 1.0, 3.0])


def _pw_origin(origin: int, pw2: np.ndarray, pw3: np.ndarray) -> OriginScore:
    # pw arrays are (n_series x n_horizons)
    return OriginScore(
        origin=origin,
        preds={"hurdle_hgb": np.zeros_like(pw2)},
        quantiles={},
        pw_raw={2.0: pw2, 3.0: pw3},
    )


def test_choose_peak_weight_reads_selection_cells_only() -> None:
    """The weight is picked on the SELECTION origins' pooled |error|; a test
    origin where the other weight looks better must not influence the pick,
    and the winner's raw predictions become the candidate everywhere."""
    horizons = [1]  # origin o scores day o+1
    units = np.array(
        [
            [0.0, 0.0],
            [4.0, 4.0],  # origin 0 (selection): actuals
            [0.0, 0.0],
            [4.0, 4.0],  # origin 1 (test): actuals — must not be read
        ]
    )
    # selection: w=3 nails it (err 0), w=2 is off by 2 per cell
    by_origin = {
        0: _pw_origin(0, np.array([[6.0], [6.0]]), np.array([[4.0], [4.0]])),
        # test: the OPPOSITE — w=2 nails it, w=3 is terrible
        1: _pw_origin(1, np.array([[4.0], [4.0]]), np.array([[400.0], [400.0]])),
    }
    info = choose_peak_weight(by_origin, [0], horizons, units)
    assert info["chosen"] == 3.0
    assert info["selection_mae"]["3.0"] == pytest.approx(0.0)
    assert info["selection_mae"]["2.0"] == pytest.approx(2.0)
    # the winner's raw preds became the candidate at EVERY origin (incl. test)
    np.testing.assert_array_equal(by_origin[1].preds["peak_weighted_hgb"], [[400.0], [400.0]])
    np.testing.assert_array_equal(by_origin[1].hurdle_raw["peak_weighted_hgb"], [[400.0], [400.0]])


# ---------------------------------------------------------------------------
# Convex ensemble: hand case + selection-origins-only proof
# ---------------------------------------------------------------------------


def _col(a: float, b: float) -> np.ndarray:
    """A (2 series x 1 horizon) candidate column."""
    return np.array([[a], [b]])


def _ens_origin(preds: dict[str, np.ndarray]) -> OriginScore:
    return OriginScore(origin=0, preds=preds, quantiles={})


def _base_preds() -> dict[str, np.ndarray]:
    return {
        "direct_hgb": _col(9.0, 9.0),
        "seasonal_naive": _col(0.0, 0.0),
        "zero": _col(0.0, 0.0),
        "croston": _col(0.0, 0.0),
        "sba": _col(0.0, 0.0),
        "tsb": _col(0.0, 0.0),
        "hgb_tweedie": _col(2.0, 2.0),
        "hurdle_hgb": _col(3.0, 3.0),
        "lgbm_tweedie": _col(3.0, 3.0),
        "lgbm_poisson": _col(4.0, 4.0),
        "hurdle_lgbm": _col(3.0, 3.0),
        "peak_weighted_hgb": _col(3.0, 3.0),
    }


def test_ensemble_weights_hand_computed() -> None:
    """Two series, one selection origin, one horizon — the per-series best-ML
    pick and the weight grid argmin pinned by hand."""
    units = np.array(
        [
            [0.0, 0.0],
            [4.0, 1.0],  # origin 0, h=1 actuals: series 0 -> 4, series 1 -> 1
        ]
    )
    horizons = [1]
    by_origin = {0: _ens_origin(_base_preds())}
    method_of = np.array(["zero", "hgb_tweedie"], dtype=object)
    plan = ensemble_weights(by_origin, [0], horizons, units, np.array([True, True]), method_of, 2)
    # series 0: routed = zero (err 4); best ML = lgbm_poisson (err 0);
    #   err(w) = |w*0 + (1-w)*4 - 4| = 4w -> min at w = 0
    # series 1: routed = hgb_tweedie (err 1); best ML = hgb_tweedie (err 1);
    #   err(w) = 1 for every w -> argmin takes the first grid point, w = 0
    np.testing.assert_array_equal(plan["weights"], [0.0, 0.0])
    assert list(plan["ml_choice"]) == ["lgbm_poisson", "hgb_tweedie"]
    assert plan["selection_mae"]["routed"] == pytest.approx(2.5)
    assert plan["selection_mae"]["best_ml"] == pytest.approx(0.5)
    assert plan["selection_mae"]["ensemble"] == pytest.approx(0.5)
    # the blend itself: w=0 -> pure best-ML
    ml_idx = np.array([ML_SPARSE.index(str(m)) for m in plan["ml_choice"]])
    ens = _ensemble_pred(by_origin[0], np.array([0.0, 2.0]), plan["weights"], ml_idx, j=0)
    np.testing.assert_allclose(ens, [4.0, 2.0])


def test_ensemble_weights_ignore_test_windows() -> None:
    """The plan is derived from the SELECTION origins passed in — a second
    origin (a test origin) whose actuals flip the best choice never enters."""
    units = np.array(
        [
            [0.0, 0.0],
            [4.0, 1.0],  # selection origin 0
            [0.0, 0.0],
            [100.0, 100.0],  # test origin 1 (never passed as a selection origin)
        ]
    )
    by_origin = {0: _ens_origin(_base_preds()), 1: _ens_origin(_base_preds())}
    method_of = np.array(["zero", "hgb_tweedie"], dtype=object)
    plan = ensemble_weights(by_origin, [0], [1], units, np.array([True, True]), method_of, 2)
    np.testing.assert_array_equal(plan["weights"], [0.0, 0.0])


# ---------------------------------------------------------------------------
# Win-rate metric: hand-computed math
# ---------------------------------------------------------------------------


def _cells(y: np.ndarray, preds: dict[str, np.ndarray], h: int = 7) -> dict:
    """One origin, one horizon, len(y) series — a minimal cells dict."""
    n = y.size
    return {
        "series": np.arange(n),
        "origin": np.zeros(n, dtype=int),
        "h": np.full(n, h),
        "y": y.astype(float),
        "sparse": np.ones(n, dtype=bool),
        "class": np.array(["lumpy"] * n, dtype=object),
        "pred": preds,
    }


def test_win_rates_hand_computed() -> None:
    """Three series; the beat is a STRICT per-series summed-|error| comparison
    against the seasonal-naive floor."""
    y = np.array([10.0, 10.0, 10.0])
    floor = np.array([12.0, 8.0, 20.0])  # errs [2, 2, 10]
    routed = np.array([9.0, 12.0, 0.0])  # errs [1, 2, 10] -> wins: only series 0
    zero = np.array([0.0, 0.0, 0.0])  # errs [10, 10, 10] -> wins: none
    cells = _cells(
        y,
        {
            "routed": routed,
            "zero": zero,
            "seasonal_naive": floor,
            "hgb_tweedie": routed,
            "hurdle_hgb": routed,
            "lgbm_tweedie": routed,
            "lgbm_poisson": routed,
            "hurdle_lgbm": routed,
            "peak_weighted_hgb": routed,
            "ensemble_convex": routed,
        },
    )
    config = ForecastConfig(bootstrap_reps=200)
    wr = _win_rates(cells, [7], config)
    lumpy = wr["per_class"]["lumpy"]
    assert lumpy["n_series"] == 3
    entry = lumpy["per_horizon"]["7"]
    assert entry["routed"]["beats_floor_count"] == 1
    assert entry["routed"]["win_rate"] == pytest.approx(1.0 / 3.0)
    assert entry["zero"]["beats_floor_count"] == 0
    assert entry["zero"]["win_rate"] == pytest.approx(0.0)
    for cand in wr["candidates"]:
        lo, hi = entry[cand]["ci95"]
        assert 0.0 <= lo <= entry[cand]["win_rate"] <= hi <= 1.0
    # the tie does NOT count as a win (series 1: 2 vs 2)
    assert entry["routed"]["beats_floor_count"] == 1


# ---------------------------------------------------------------------------
# LightGBM candidate construction (determinism contract)
# ---------------------------------------------------------------------------


def test_lgbm_candidate_construction() -> None:
    config = ForecastConfig()
    tw = _fit_lgbm(config, "tweedie")
    assert tw.objective == "tweedie"
    assert tw.tweedie_variance_power == pytest.approx(1.5)
    ps = _fit_lgbm(config, "poisson")
    assert ps.objective == "poisson"
    for model in (tw, ps):
        assert model.random_state == config.seed
        # deterministic stays OFF (degenerate-split assert in LightGBM 4.7's
        # deterministic splitter); reproducibility comes from force_row_wise +
        # n_jobs=1 + the fixed seed (byte-identity-tested). It is not passed
        # to the constructor at all — assert it never enters the params.
        assert "deterministic" not in model.get_params()
        assert model.force_row_wise
        assert model.n_jobs == 1  # origin-level workers already fill the cores
        assert model.learning_rate == pytest.approx(config.multistep_lgbm.learning_rate)
        assert model.num_leaves == config.multistep_lgbm.num_leaves
    with pytest.raises(ValueError):
        _fit_lgbm(config, "binary")
    clf, reg = _fit_hurdle_lgbm_pair(config)
    assert clf.random_state == config.seed and "deterministic" not in clf.get_params()
    assert clf.n_jobs == 1 and reg.n_jobs == 1
    assert reg.random_state == config.seed and "deterministic" not in reg.get_params()


def test_lgbm_candidates_fit_and_are_deterministic() -> None:
    """Tiny fit smoke: the hi/lo categoricals are accepted and two seeded
    fits are bit-identical (the evaluate-run determinism contract)."""
    rng = np.random.default_rng(0)
    x = rng.normal(size=(400, 25))
    x[:, -2] = np.tile(np.arange(4), 100) // 2  # hi
    x[:, -1] = np.tile(np.arange(4), 100) % 2  # lo
    y = np.where(rng.random(400) < 0.3, rng.integers(1, 20, 400), 0).astype(float)
    cat = [23, 24]
    config = ForecastConfig()
    a = _fit_lgbm(config, "tweedie")
    b = _fit_lgbm(config, "tweedie")
    a.fit(x, y, categorical_feature=cat)
    b.fit(x, y, categorical_feature=cat)
    np.testing.assert_array_equal(a.predict(x), b.predict(x))
    ca, ra = _fit_hurdle_lgbm_pair(config)
    cb, rb = _fit_hurdle_lgbm_pair(config)
    pos = y > 0
    ca.fit(x, pos.astype(int), categorical_feature=cat)
    cb.fit(x, pos.astype(int), categorical_feature=cat)
    ra.fit(x[pos], np.log1p(y[pos]), categorical_feature=cat)
    rb.fit(x[pos], np.log1p(y[pos]), categorical_feature=cat)
    np.testing.assert_array_equal(ca.predict_proba(x), cb.predict_proba(x))
    np.testing.assert_array_equal(ra.predict(x), rb.predict(x))


def test_finite_demand_pred_guard() -> None:
    """Non-finite log-link forecasts are mapped deterministically: NaN -> 0,
    +inf -> the series' training-window max (>= 1), -inf -> 0; finite cells
    pass through byte-identical (observed on UCI: lgbm_poisson overflows the
    exponential link on ~11% of a scored origin's cells, with finite garbage
    up to ~1e283 elsewhere — hence the poisson-only hard_clip cap)."""
    from demand_forecasting.multihorizon import _finite_demand_pred

    train = np.array(
        [
            [0.0, 3.0],
            [5.0, 0.0],
            [0.0, 0.0],
        ]
    )  # (days, series)
    pred = np.array(
        [
            [np.inf, 2.5],
            [np.nan, np.inf],
            [-np.inf, 0.0],
        ]
    )
    out = _finite_demand_pred(pred, train)
    np.testing.assert_array_equal(
        out,
        np.array(
            [
                [5.0, 2.5],
                [0.0, 3.0],
                [0.0, 0.0],
            ]
        ),
    )
    finite = np.array([[1.5, 2.5], [3.5, 4.5]])
    np.testing.assert_array_equal(_finite_demand_pred(finite, train), finite)
    # hard_clip caps finite overflow garbage at the training max
    garbage = np.array([[1e283, 2.5], [3.5, 99.0]])
    np.testing.assert_array_equal(
        _finite_demand_pred(garbage, train, hard_clip=True),
        np.array([[5.0, 2.5], [3.5, 3.0]]),
    )


def test_lgbm_fit_safe_fallback_ladder(monkeypatch: pytest.MonkeyPatch) -> None:
    """The degenerate-split retry ladder is deterministic: a first-fit
    LightGBMError mentioning right_count retries with min_sum_hessian_in_leaf
    set; a second failure also drops num_leaves; unrelated errors propagate."""
    import lightgbm.basic
    from demand_forecasting.multihorizon import _lgbm_fit_safe

    calls: list[dict] = []

    class FakeModel:
        def __init__(self, failures: list[str]) -> None:
            self._failures = list(failures)
            self.params: dict = {}

        def set_params(self, **kw):
            self.params.update(kw)
            return self

        def fit(self, x, y, categorical_feature=None):
            calls.append(dict(self.params))
            if self._failures:
                raise lightgbm.basic.LightGBMError(self._failures.pop(0))
            return self

    ok = _lgbm_fit_safe(FakeModel([]), np.zeros((4, 2)), np.zeros(4), [0, 1])
    assert isinstance(ok, FakeModel) and calls == [{}]  # untouched path

    # one degenerate-split failure -> min_sum_hessian_in_leaf retry succeeds
    m1 = FakeModel(["Check failed: (best_split_info.right_count) > (0) ..."])
    _lgbm_fit_safe(m1, np.zeros((4, 2)), np.zeros(4), [0, 1])
    assert calls[-2] == {} and calls[-1] == {"min_sum_hessian_in_leaf": 1.0}

    # two failures -> the ladder also pins num_leaves=8
    m2 = FakeModel(["Check failed: (right_count) > (0)", "Check failed: (right_count) > (0)"])
    _lgbm_fit_safe(m2, np.zeros((4, 2)), np.zeros(4), [0, 1])
    assert calls[-1] == {"min_sum_hessian_in_leaf": 1.0, "num_leaves": 8}

    # an unrelated LightGBMError propagates untouched
    with pytest.raises(lightgbm.basic.LightGBMError, match="out of memory"):
        _lgbm_fit_safe(FakeModel(["out of memory"]), np.zeros((4, 2)), np.zeros(4), [0, 1])
