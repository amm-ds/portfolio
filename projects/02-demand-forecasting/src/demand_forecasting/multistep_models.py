"""Design matrices, estimator factories and the per-origin fit-and-predict engine.

``_design_train`` / ``_design_pred`` build the direct per-horizon feature
rows; the ``_fit_*`` factories construct the HGB / tweedie / hurdle /
LightGBM / peak-weighted candidates on the committed tunings;
``_score_origin`` fits every candidate issued at one origin and returns the
predictions bundled in :class:`OriginScore`.
"""

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]  # re-exported

from demand_forecasting.config import ForecastConfig
from demand_forecasting.intermittent import statistical_forecast
from demand_forecasting.multistep_constants import QUANTILES_MS
from demand_forecasting.multistep_features import (
    MIN_LAG_ORIGIN,
    N_PEAK_FEATURES,
    N_PRICE_FEATURES,
    N_ROLLING_FEATURES,
    neutral_price_tensor,
    peak_feature_tensor,
    price_feature_tensor,
    rolling_feature_tensor,
)

# Target-relative lag ages: lag_h, lag_{h+7}, lag_{h+14} (all ≥ h days old).
LAG_AGES = (0, 7, 14)


# Tweedie variance power: sklearn's HalfTweedieLoss fixes the compound-Poisson
# regime 1 < p < 2; p = 1.5 is the standard peak-tolerant choice.
TWEEDIE_POWER = 1.5


# Sample-weight grid for peak_weighted_hgb (top-decile demand days up-weighted
# by w in the hurdle fits); the winner is chosen on the selection origins.
PEAK_WEIGHTS = (2.0, 3.0)


# ---------------------------------------------------------------------------
# Per-origin computation
# ---------------------------------------------------------------------------


def _design_train(
    units: np.ndarray,
    cal: np.ndarray,
    pf: np.ndarray,
    prf: np.ndarray,
    rf: np.ndarray,
    origin: int,
    h: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Training matrix for the direct model of horizon h issued at ``origin``.

    Rows are (candidate origin o', series i) pairs with
    ``o' ∈ [MIN_LAG_ORIGIN, origin - h]`` — every training target date is ≤
    the issue date, so the fit never reads beyond the origin. Features:
    calendar of the target date o'+h, the peak block at the reference day o'
    (see :func:`peak_feature_tensor` — every entry ≥ h days older than the
    target), the price block at the same reference day (see
    :func:`price_feature_tensor` — same aging), the rolling block at the same
    reference day (see :func:`rolling_feature_tensor` — same aging), the lag
    trio units(o'), units(o'-7), units(o'-14), and the series identity as a
    hi/lo PAIR of native categoricals (HGB caps categorical cardinality at
    255; the pair (i // 64, i % 64) identifies the series exactly and keeps
    both cardinalities small). Column order matches :func:`_design_pred`.
    """
    n_series = units.shape[1]
    lo, hi = MIN_LAG_ORIGIN, origin - h
    m = hi - lo + 1
    tgt = lo + h + np.arange(m)
    base = np.repeat(cal[tgt], n_series, axis=0)
    lag0 = units[lo : hi + 1].reshape(-1)
    lag7 = units[lo - 7 : hi + 1 - 7].reshape(-1)
    lag14 = units[lo - 14 : hi + 1 - 14].reshape(-1)
    peak = pf[lo : hi + 1].reshape(-1, N_PEAK_FEATURES)
    price = prf[lo : hi + 1].reshape(-1, N_PRICE_FEATURES)
    roll = rf[lo : hi + 1].reshape(-1, N_ROLLING_FEATURES)
    codes = np.tile(np.arange(n_series), m)
    x = np.column_stack([base, lag0, lag7, lag14, peak, price, roll, codes // 64, codes % 64])
    y = units[tgt].reshape(-1)
    return x, y


def _design_pred(
    units: np.ndarray,
    cal: np.ndarray,
    pf: np.ndarray,
    prf: np.ndarray,
    rf: np.ndarray,
    origin: int,
    h: int,
) -> np.ndarray:
    """Prediction matrix for (origin, h): one row per series, target origin+h."""
    n_series = units.shape[1]
    base = np.repeat(cal[origin + h : origin + h + 1], n_series, axis=0)
    codes = np.arange(n_series)
    return np.column_stack(
        [
            base,
            units[origin],
            units[origin - 7],
            units[origin - 14],
            pf[origin],
            prf[origin],
            rf[origin],
            codes // 64,
            codes % 64,
        ]
    )


def _n_numeric_features() -> int:
    """Numeric column count: calendar + lag trio + peak + price + rolling."""
    return 9 + len(LAG_AGES) + N_PEAK_FEATURES + N_PRICE_FEATURES + N_ROLLING_FEATURES


def _fit_hgb(config: ForecastConfig, quantile: float | None) -> HistGradientBoostingRegressor:
    """Champion-config HGB; series identity enters as two native categoricals
    (hi/lo pair, see :func:`_design_train`)."""
    kwargs: dict[str, Any] = config.hgb_tuned.estimator_kwargs()
    kwargs["random_state"] = config.seed
    if quantile is not None:
        kwargs["loss"] = "quantile"
        kwargs["quantile"] = quantile
    n_num = _n_numeric_features()
    return HistGradientBoostingRegressor(categorical_features=[n_num, n_num + 1], **kwargs)


def _fit_tweedie(config: ForecastConfig) -> HistGradientBoostingRegressor:
    """Peak-capable tweedie HGB: compound-Poisson deviance (variance power
    1.5) with the seeded multi-step tuning (lr/depth/leaves tuned on the
    SELECTION origins only — see hpo.tune_multistep_tweedie)."""
    from sklearn._loss.loss import HalfTweedieLoss

    kwargs: dict[str, Any] = config.multistep_tweedie.estimator_kwargs()
    kwargs["random_state"] = config.seed
    n_num = _n_numeric_features()
    return HistGradientBoostingRegressor(
        loss=HalfTweedieLoss(power=TWEEDIE_POWER),
        categorical_features=[n_num, n_num + 1],
        **kwargs,
    )


def _fit_hurdle_pair(
    config: ForecastConfig,
) -> tuple[HistGradientBoostingClassifier, HistGradientBoostingRegressor]:
    """Two-stage hurdle pair on the champion HGB config: a classifier for
    P(sale) (log loss) and a regressor on log1p(non-zero sizes). Same hi/lo
    categorical encoding as every direct model."""
    kwargs: dict[str, Any] = config.hgb_tuned.estimator_kwargs()
    kwargs["random_state"] = config.seed
    n_num = _n_numeric_features()
    cat = [n_num, n_num + 1]
    return (
        HistGradientBoostingClassifier(categorical_features=cat, **kwargs),
        HistGradientBoostingRegressor(categorical_features=cat, **kwargs),
    )


def _fit_lgbm(config: ForecastConfig, objective: str) -> Any:
    """Global LightGBM candidate (wave 21) on the multi-step LGBM tuning:
    tweedie (compound-Poisson, variance power 1.5) or poisson count objective.
    ``force_row_wise=True`` + ``n_jobs=1`` + the fixed seed make fits
    reproducible; the series identity enters as the same hi/lo categorical
    pair via ``categorical_feature`` at fit time."""
    from lightgbm import LGBMRegressor

    kwargs: dict[str, Any] = config.multistep_lgbm.estimator_kwargs()
    kwargs.update(
        random_state=config.seed,
        # deterministic=True is deliberately OFF: LightGBM 4.7's deterministic
        # splitter hits a degenerate-split assert (serial_tree_learner.cpp:870)
        # on some training windows; force_row_wise + n_jobs=1 + the fixed seed
        # keep fits reproducible (byte-identity-tested) without that path
        force_row_wise=True,
        verbosity=-1,
        n_jobs=1,  # origin-level joblib workers already fill the cores
    )
    if objective == "tweedie":
        return LGBMRegressor(objective="tweedie", tweedie_variance_power=TWEEDIE_POWER, **kwargs)
    if objective == "poisson":
        return LGBMRegressor(objective="poisson", **kwargs)
    raise ValueError(f"unknown lgbm objective: {objective!r}")


def _fit_hurdle_lgbm_pair(config: ForecastConfig) -> tuple[Any, Any]:
    """Two-stage hurdle on LightGBM halves (wave 21): LGBMClassifier for
    P(sale) + LGBMRegressor on log1p(non-zero sizes), both on the multi-step
    LGBM tuning. Same raw point math and the same selection-origin
    zero-correction as the HGB hurdle."""
    from lightgbm import LGBMClassifier, LGBMRegressor

    kwargs: dict[str, Any] = config.multistep_lgbm.estimator_kwargs()
    kwargs.update(
        random_state=config.seed,
        # deterministic=True is deliberately OFF: LightGBM 4.7's deterministic
        # splitter hits a degenerate-split assert (serial_tree_learner.cpp:870)
        # on some training windows; force_row_wise + n_jobs=1 + the fixed seed
        # keep fits reproducible (byte-identity-tested) without that path
        force_row_wise=True,
        verbosity=-1,
        n_jobs=1,  # origin-level joblib workers already fill the cores
    )
    return LGBMClassifier(**kwargs), LGBMRegressor(**kwargs)


def _lgbm_fit_safe(model: Any, x: np.ndarray, y: np.ndarray, cat: list[int]) -> Any:
    """Fit one LightGBM estimator with a deterministic degenerate-split
    fallback.

    On strongly zero-inflated panels the tweedie/poisson objectives can
    produce near-zero-hessian histogram bins whose counts round to zero,
    tripping LightGBM's ``best_split_info.right_count > 0`` assert
    (serial_tree_learner.cpp:870 — a hard crash, not a warning). The retry
    ladder (``min_sum_hessian_in_leaf=1.0``, then ``num_leaves=8``) only
    engages on those windows, so identical runs take identical branches —
    the byte-identity determinism contract is unchanged. Any OTHER error
    propagates unchanged.
    """
    from lightgbm.basic import LightGBMError

    try:
        model.fit(x, y, categorical_feature=cat)
        return model
    except LightGBMError as exc:
        if "right_count" not in str(exc) and "Check failed" not in str(exc):
            raise
    model.set_params(min_sum_hessian_in_leaf=1.0)
    try:
        model.fit(x, y, categorical_feature=cat)
        return model
    except LightGBMError:
        model.set_params(num_leaves=8)
        model.fit(x, y, categorical_feature=cat)
        return model


def _finite_demand_pred(
    pred: np.ndarray, train_units: np.ndarray, hard_clip: bool = False
) -> np.ndarray:
    """Guard a log-link LightGBM forecast matrix against overflowed cells.

    The tweedie/poisson objectives can overflow the exponential link on
    zero-inflated panels: lgbm_poisson on UCI produced literal +inf on ~11%
    of one scored origin's cells AND finite values up to ~1e283 elsewhere,
    either of which poisons every pooled metric. NaN -> 0, +inf -> the
    series' training-window max (>= 1), -inf -> 0. With ``hard_clip``
    (poisson only) finite cells are also capped at that training max — the
    pure-exp link diverges under the HPO'd step size, so an
    above-historical-peak poisson forecast is overflow garbage, not signal.
    The mapping is deterministic, so the byte-identity contract between
    runs is unchanged.
    """
    cap = np.maximum(train_units.max(axis=0), 1.0)
    out: np.ndarray = np.nan_to_num(pred, nan=0.0, posinf=cap, neginf=0.0)
    if hard_clip:
        out = np.minimum(out, cap)
    return out


def peak_sample_weights(y: np.ndarray, n_series: int, weight: float) -> np.ndarray:
    """Training-row weights up-weighting each series' top-decile demand days.

    ``y`` is series-minor (``y.reshape(-1, n_series)`` gives (rows, series) —
    the multi-step training layouts are built that way). Every positive
    training target at or above its own series' 90th percentile of positive
    demand gets ``weight``; everything else gets 1. Pure numpy, hand-testable.
    """
    w = np.ones(y.shape[0])
    w2 = w.reshape(-1, n_series)
    y2 = y.reshape(-1, n_series)
    for i in range(n_series):
        col = y2[:, i]
        pos = col[col > 0]
        if pos.size:
            thr = float(np.quantile(pos, 0.9))
            w2[col >= thr, i] = weight
    return w


def hurdle_point(p_hat: np.ndarray, log_size: np.ndarray) -> np.ndarray:
    """The hurdle point forecast — pure math, hand-testable:
    ``p_hat * max(exp(y_reg) - 1, 0)`` (``exp(y) - 1`` inverts the log1p target).
    """
    p = np.clip(np.asarray(p_hat, dtype=float), 0.0, 1.0)
    size = np.clip(np.expm1(np.asarray(log_size, dtype=float)), 0.0, None)
    return np.asarray(p * size, dtype=float)


def _seasonal_naive_pred(units: np.ndarray, origin: int, horizons: list[int]) -> np.ndarray:
    """Direct multi-step seasonal naive: the most recent same-weekday actual.

    For horizon h the reference day is ``origin + h - 7·⌈h/7⌉`` — the newest
    day sharing the target's weekday that is still ≤ the origin (leakage-free
    by construction).
    """
    n_series = units.shape[1]
    out = np.zeros((n_series, len(horizons)))
    for j, h in enumerate(horizons):
        k = math.ceil(h / 7)
        out[:, j] = units[origin + h - 7 * k]
    return out


def _statistical_preds(units: np.ndarray, origin: int, window: int) -> dict[str, np.ndarray]:
    """Flat/varied statistical forecasts per series, fit on days 0..origin only.

    Covers the Croston family (croston/sba/tsb), the wave-22 rolling-mean
    baseline (ma_28, flat) and the ADIDA pair (adida_sba/adida_tsb — bucket
    totals via SBA/TSB, within-week-profile disaggregation, so the 14-day
    window is exactly two 7-day buckets; see intermittent.adida_forecast).
    """
    hist = units[: origin + 1]
    names = ("croston", "sba", "tsb", "ma_28", "adida_sba", "adida_tsb")
    return {
        name: np.array(
            [statistical_forecast(name, hist[:, i], window) for i in range(hist.shape[1])]
        )
        for name in names
    }


@dataclass
class OriginScore:
    """Predictions for every candidate at one origin (n_series x n_horizons)."""

    origin: int
    preds: dict[str, np.ndarray]
    quantiles: dict[float, np.ndarray]  # learner p10/p50/p90
    # Raw hurdle point forecasts (p̂ x size, before the selection-origin
    # zero-correction is applied globally by apply_hurdle_correction), keyed
    # by hurdle candidate (hurdle_hgb / hurdle_lgbm / peak_weighted_hgb —
    # the last one appears only after choose_peak_weight picked a variant).
    hurdle_raw: dict[str, np.ndarray] = field(default_factory=dict)
    # Raw peak_weighted_hgb variants keyed by the sample-weight multiplier
    # (both variants are fit everywhere; the weight is chosen on the
    # selection origins only).
    pw_raw: dict[float, np.ndarray] = field(default_factory=dict)
    # Optional what-if predictions under demand shocks: shock factor -> method
    # -> (n_series x n_horizons). A shock scales the last 7 days before the
    # origin (the demand signal every candidate reads: the statistical methods
    # re-fit on the shocked window, the boosted models re-predict on their
    # shocked features). Only the demo payload builder passes shock factors;
    # the committed track never does, so committed metrics are untouched.
    shocked: dict[float, dict[str, np.ndarray]] = field(default_factory=dict)


def _hurdle_predict(
    clf: Any,
    reg: Any,
    x: np.ndarray,
    has_positives: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """(p_hat, raw point forecast) of one fitted hurdle pair on design rows.

    A training window with no positive target rows yields p̂ ≡ 0 (a classifier
    that has seen a single class); the regressor prediction is undefined in
    that case and the size is 0.
    """
    if len(clf.classes_) < 2:
        p_hat = np.zeros(x.shape[0])
    else:
        p_hat = np.asarray(clf.predict_proba(x)[:, 1], dtype=float)
    if has_positives:
        size = hurdle_point(np.ones(x.shape[0]), np.asarray(reg.predict(x), dtype=float))
    else:
        size = np.zeros(x.shape[0])
    return p_hat, p_hat * size


def _lgbm_cat_cols() -> list[int]:
    """Column indices of the hi/lo series-identity pair for LightGBM."""
    n_num = _n_numeric_features()
    return [n_num, n_num + 1]


def _score_origin(
    units: np.ndarray,
    cal: np.ndarray,
    origin: int,
    horizons: list[int],
    config: ForecastConfig,
    shock_factors: tuple[float, ...] = (),
    price: np.ndarray | None = None,
) -> OriginScore:
    """Fit every direct model issued at ``origin`` and predict the window.

    One thread per estimator: parallelism comes from the caller (joblib
    workers across origins, which carry OMP_NUM_THREADS=1 via
    parallel_config); a 16-thread OpenMP pool inside a single fit measures
    20-100x SLOWER on this machine (per-iteration sync dominates), so
    direct/serial callers (tests, the tweedie HPO objective) must not let
    sklearn grab every core per fit.
    """
    with threadpool_limits(limits=1):
        return _score_origin_impl(units, cal, origin, horizons, config, shock_factors, price)


def _score_origin_impl(
    units: np.ndarray,
    cal: np.ndarray,
    origin: int,
    horizons: list[int],
    config: ForecastConfig,
    shock_factors: tuple[float, ...] = (),
    price: np.ndarray | None = None,
) -> OriginScore:
    """The fit-and-predict body (see :func:`_score_origin`)."""
    n_series = units.shape[1]
    pf = peak_feature_tensor(units)
    prf = (
        price_feature_tensor(price)
        if price is not None
        else neutral_price_tensor(units.shape[0], n_series)
    )
    rf = rolling_feature_tensor(units)
    cat_lgbm = _lgbm_cat_cols()
    point_cols: list[np.ndarray] = []
    point_models: list[HistGradientBoostingRegressor] = []
    tweedie_cols: list[np.ndarray] = []
    tweedie_models: list[HistGradientBoostingRegressor] = []
    hurdle_raw_cols: list[np.ndarray] = []
    hurdle_lgbm_cols: list[np.ndarray] = []
    lgbm_tw_cols: list[np.ndarray] = []
    lgbm_ps_cols: list[np.ndarray] = []
    pw_cols: dict[float, list[np.ndarray]] = {w: [] for w in PEAK_WEIGHTS}
    hurdle_models: list[tuple[Any, Any]] = []
    lgbm_tw_models: list[Any] = []
    lgbm_ps_models: list[Any] = []
    hurdle_lgbm_models: list[tuple[Any, Any]] = []
    pw_models: dict[float, list[tuple[Any, Any]]] = {w: [] for w in PEAK_WEIGHTS}
    quantile_cols: dict[float, list[np.ndarray]] = {q: [] for q in QUANTILES_MS}
    for h in horizons:
        x_train, y_train = _design_train(units, cal, pf, prf, rf, origin, h)
        x_pred = _design_pred(units, cal, pf, prf, rf, origin, h)
        model = _fit_hgb(config, quantile=None)
        model.fit(x_train, y_train)
        point_models.append(model)
        point_cols.append(np.asarray(model.predict(x_pred), dtype=float))
        tweedie = _fit_tweedie(config)
        tweedie.fit(x_train, y_train)
        tweedie_models.append(tweedie)
        tweedie_cols.append(np.asarray(tweedie.predict(x_pred), dtype=float))
        clf, reg = _fit_hurdle_pair(config)
        positives = y_train > 0
        clf.fit(x_train, positives.astype(int))
        if positives.any():
            reg.fit(x_train[positives], np.log1p(y_train[positives]))
        hurdle_models.append((clf, reg))
        _, raw_point = _hurdle_predict(clf, reg, x_pred, bool(positives.any()))
        hurdle_raw_cols.append(raw_point)
        for q in QUANTILES_MS:
            qm = _fit_hgb(config, quantile=q)
            qm.fit(x_train, y_train)
            quantile_cols[q].append(np.asarray(qm.predict(x_pred), dtype=float))
        # wave 21: LightGBM global candidates + the LGBM hurdle
        lgbm_tw = _fit_lgbm(config, "tweedie")
        _lgbm_fit_safe(lgbm_tw, x_train, y_train, cat_lgbm)
        lgbm_tw_models.append(lgbm_tw)
        lgbm_tw_cols.append(
            _finite_demand_pred(np.asarray(lgbm_tw.predict(x_pred), dtype=float), units[:origin])
        )
        lgbm_ps = _fit_lgbm(config, "poisson")
        _lgbm_fit_safe(lgbm_ps, x_train, y_train, cat_lgbm)
        lgbm_ps_models.append(lgbm_ps)
        lgbm_ps_cols.append(
            _finite_demand_pred(
                np.asarray(lgbm_ps.predict(x_pred), dtype=float), units[:origin], hard_clip=True
            )
        )
        clf_l, reg_l = _fit_hurdle_lgbm_pair(config)
        _lgbm_fit_safe(clf_l, x_train, positives.astype(int), cat_lgbm)
        if positives.any():
            _lgbm_fit_safe(
                reg_l,
                x_train[positives],
                np.log1p(y_train[positives]),
                cat_lgbm,
            )
        hurdle_lgbm_models.append((clf_l, reg_l))
        _, raw_l = _hurdle_predict(clf_l, reg_l, x_pred, bool(positives.any()))
        hurdle_lgbm_cols.append(raw_l)
        # wave 21: peak-weighted hurdle variants (top-decile demand days
        # up-weighted by w in both halves of the pair)
        for w in PEAK_WEIGHTS:
            clf_w, reg_w = _fit_hurdle_pair(config)
            w_train = peak_sample_weights(y_train, n_series, w)
            clf_w.fit(x_train, positives.astype(int), sample_weight=w_train)
            if positives.any():
                reg_w.fit(
                    x_train[positives],
                    np.log1p(y_train[positives]),
                    sample_weight=w_train[positives],
                )
            pw_models[w].append((clf_w, reg_w))
            _, raw_w = _hurdle_predict(clf_w, reg_w, x_pred, bool(positives.any()))
            pw_cols[w].append(raw_w)
    preds: dict[str, np.ndarray] = {
        "direct_hgb": np.column_stack(point_cols),
        "hgb_tweedie": np.column_stack(tweedie_cols),
        "lgbm_tweedie": np.column_stack(lgbm_tw_cols),
        "lgbm_poisson": np.column_stack(lgbm_ps_cols),
        # overwritten by apply_hurdle_correction (raw until then); the
        # peak_weighted_hgb key appears with choose_peak_weight's winner
        "hurdle_hgb": np.column_stack(hurdle_raw_cols),
        "hurdle_lgbm": np.column_stack(hurdle_lgbm_cols),
    }
    hurdle_raw = {"hurdle_hgb": preds["hurdle_hgb"], "hurdle_lgbm": preds["hurdle_lgbm"]}
    pw_raw = {w: np.column_stack(cols) for w, cols in pw_cols.items()}
    quantiles = {q: np.column_stack(v) for q, v in quantile_cols.items()}
    preds["seasonal_naive"] = _seasonal_naive_pred(units, origin, horizons)
    preds["zero"] = np.zeros((n_series, len(horizons)))
    for name, mat in _statistical_preds(units, origin, config.multistep_window_days).items():
        preds[name] = np.column_stack([mat[:, h - 1] for h in horizons])
    shocked: dict[float, dict[str, np.ndarray]] = {}
    for s in shock_factors:
        if s <= 0:
            raise ValueError(f"shock factor must be positive, got {s}")
        if s == 1.0:
            continue  # the base run IS the 1.0 curve
        units_s = units.copy()
        units_s[max(0, origin - 6) : origin + 1] *= s  # the last 7 days before the origin
        pf_s = peak_feature_tensor(units_s)
        rf_s = rolling_feature_tensor(units_s)
        prf_s = (
            price_feature_tensor(price)
            if price is not None
            else neutral_price_tensor(units.shape[0], n_series)
        )
        entry: dict[str, np.ndarray] = {
            "seasonal_naive": _seasonal_naive_pred(units_s, origin, horizons),
            "zero": np.zeros((n_series, len(horizons))),
        }
        for name, mat in _statistical_preds(units_s, origin, config.multistep_window_days).items():
            entry[name] = np.column_stack([mat[:, h - 1] for h in horizons])
        hgb_cols = []
        tweedie_cols_s = []
        hurdle_raw_cols_s = []
        lgbm_tw_cols_s = []
        lgbm_ps_cols_s = []
        hurdle_lgbm_cols_s = []
        pw_cols_s: dict[float, list[np.ndarray]] = {w: [] for w in PEAK_WEIGHTS}
        for j, h in enumerate(horizons):
            x_s = _design_pred(units_s, cal, pf_s, prf_s, rf_s, origin, h)
            hgb_cols.append(np.asarray(point_models[j].predict(x_s), dtype=float))
            tweedie_cols_s.append(np.asarray(tweedie_models[j].predict(x_s), dtype=float))
            clf_s, reg_s = hurdle_models[j]
            _, raw_s = _hurdle_predict(clf_s, reg_s, x_s, len(clf_s.classes_) >= 2)
            hurdle_raw_cols_s.append(raw_s)
            # wave 21 candidates re-predict through their fitted per-h models
            tw_pred_s = np.asarray(lgbm_tw_models[j].predict(x_s), dtype=float)
            lgbm_tw_cols_s.append(_finite_demand_pred(tw_pred_s, units_s[:origin]))
            ps_pred_s = np.asarray(lgbm_ps_models[j].predict(x_s), dtype=float)
            lgbm_ps_cols_s.append(_finite_demand_pred(ps_pred_s, units_s[:origin], hard_clip=True))
            clf_l_s, reg_l_s = hurdle_lgbm_models[j]
            _, raw_l_s = _hurdle_predict(clf_l_s, reg_l_s, x_s, len(clf_l_s.classes_) >= 2)
            hurdle_lgbm_cols_s.append(raw_l_s)
            for w in PEAK_WEIGHTS:
                clf_w_s, reg_w_s = pw_models[w][j]
                _, raw_w_s = _hurdle_predict(clf_w_s, reg_w_s, x_s, len(clf_w_s.classes_) >= 2)
                pw_cols_s[w].append(raw_w_s)
        entry["direct_hgb"] = np.column_stack(hgb_cols)
        entry["hgb_tweedie"] = np.column_stack(tweedie_cols_s)
        entry["hurdle_hgb"] = np.column_stack(hurdle_raw_cols_s)  # raw; the payload
        # applies the committed correction mapping to the routed curve
        entry["lgbm_tweedie"] = np.column_stack(lgbm_tw_cols_s)
        entry["lgbm_poisson"] = np.column_stack(lgbm_ps_cols_s)
        entry["hurdle_lgbm"] = np.column_stack(hurdle_lgbm_cols_s)  # raw, corrected later
        # peak-weighted variants stay keyed by weight until choose_peak_weight
        # promotes the winner to the "peak_weighted_hgb" key
        for w in PEAK_WEIGHTS:
            entry[f"peak_weighted_hgb@{w}"] = np.column_stack(pw_cols_s[w])
        shocked[float(s)] = entry
    return OriginScore(
        origin=origin,
        preds=preds,
        quantiles=quantiles,
        hurdle_raw=hurdle_raw,
        pw_raw=pw_raw,
        shocked=shocked,
    )
