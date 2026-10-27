"""Direct multi-horizon forecasting track — protocol ``direct_multihorizon_v1``.

The nowcast track (evaluate.py) answers "tomorrow, given today". This module
answers the question replenishment actually asks: **the next 14 days, issued
once per week**, with each horizon modelled directly:

- **Direct per-horizon models** — one model per horizon
  ``h ∈ config.multistep_horizons``. Features for horizon *h* are the calendar
  of the target date (known in advance) plus lags aged ≥ *h* days relative to
  the target: ``lag_h = units(target - h)``, ``lag_{h+7}``, ``lag_{h+14}``.
  Relative to the origin (issue date *t*, target *t+h*) these are
  ``units(t)``, ``units(t-7)``, ``units(t-14)`` — so **no actual within *h*
  days of the target is ever referenced**, by construction (leakage-proof
  tested with tainted panels). The learner is the champion-config HGB
  (``config.hgb_tuned``) with the series identity as a hi/lo pair of native
  categoricals (HGB caps categorical cardinality at 255; the exact pair
  (id // 64, id % 64) keeps both cardinalities small and memory flat — a
  dense one-hot over 1,600 series would not survive parallel origin fits).
- **Weekly rolling origins** — origin = last training date; the forecast
  window is the 14 days *starting the day after the origin* (no embargo gap —
  the 57-day hole of the nowcast layout is gone). Origins are 7 days apart,
  capped at ``config.multistep_n_origins`` by dropping the oldest (the exact
  weekly cadence is preserved; the cap is documented). The LAST
  ``config.multistep_test_origins`` origins are the test set — scored once,
  never read for selection; the earlier origins select (per-series routing
  method, conformal widths).
- **Routing** — series are routed per class on the selection origins only:
  sparse quadrants (ADI ≥ 1.32, see intermittent.py) choose among the
  statistical methods (zero / seasonal_naive / Croston / SBA / TSB + the
  wave-22 ma_28 / ADIDA pair) PLUS the wave-20 peak-capable ML models
  (hgb_tweedie / hurdle_hgb, below) — direct_hgb stays excluded there (the
  wave-19 finding: boosted trees overfit sparse series); smooth/erratic series
  choose among direct_hgb and the two ML candidates. Selection on train
  origins only is property-tested (shuffling the test origins' actuals leaves
  the routing unchanged).
- **Peak features** (wave 20) — the design adds a peak block computed at the
  reference day target-h (so >= h days older than the target, exactly like the)
  lags): rolling mean AND max over 7/14/28-day windows, days-since-last-
  non-zero, the 28d non-zero-day count and the 28d peak ratio. The flat
  intermittent estimators cannot see any of these.
- **Peak-capable candidates** (wave 20) — two ML entries join the sparse
  routing pool, both on the hi/lo series-identity categoricals:
  ``hgb_tweedie`` (HGB with the compound-Poisson tweedie deviance, variance
  power 1.5; lr/depth/leaves tuned on the selection origins by a seeded
  capped Optuna study, hpo.tune_multistep_tweedie) and ``hurdle_hgb`` (per-h
  two-stage HGB: log-loss classifier for P(sale) + HGB on log1p(non-zero
  sizes); point = p_hat x (exp(y_reg) - 1), zero-corrected on the selection origins -
  identity / scalar / isotonic, whichever wins there, tested not assumed).
- **Peak-capture metrics** (wave 20) — per scored window: ``peak_mae`` (MAE
  on the window's top-decile-by-actual days) and ``peak_recall`` (share of
  the window's top-5 actual days ranked in the forecast's own top-5),
  pooled per class with paired cluster-bootstrap CIs vs the routed and zero
  baselines — the headline answer to "peaks aren't captured".
- **Uncertainty** — per horizon: quantile HGBs (p10/p50/p90, pinball loss
  reported) plus a split-conformal ±q80 width calibrated on the selection
  origins, zero-clipped and sorted. Sparse (routed) series get an honest
  sparse band instead: P(any sale) + a quantile ladder of the training
  history, which cannot collapse to a zero-width interval.
- **Decision metric** — an order-up-to policy simulation (service level τ →
  order = quantile_τ of the forecast distribution; holding + stockout cost
  against actuals), champion vs seasonal-naive policy, per demand class, cost
  assumptions documented in the JSON. Wave 22 adds a newsvendor layer: the
  order IS the routed band's q-quantile (band ladder / sparse history ladder;
  the floor reads the same quantile of the seasonal-naive weekday
  distribution) under documented holding/stockout unit costs. Labelled a
  simulation — no savings claims.
- **Paired bootstrap** — every headline comparison (per-class champion-vs-floor
  and champion-vs-naive at h=7/h=14, model-rank gaps, routing before/after)
  carries a 95% cluster bootstrap CI over (series x scored test origins):
  series are resampled with replacement, one shared index draw per
  replication so differences stay paired (the pattern from projects/05 /10).
- **Wave-22 statistical candidates** — ``ma_28`` (rolling 28-day mean, flat),
  and the ADIDA pair ``adida_sba`` / ``adida_tsb`` (7-day temporal aggregation
  aligned to the origin so the 14-day window is exactly 2 buckets, SBA/TSB on
  the bucket series, within-week-profile disaggregation — see
  intermittent.adida_forecast). All three join the sparse routing pool.
- **Wave-22 rolling features** — the design adds a rolling block at the same
  target-h reference day as the peak/price blocks: rolling means over
  7/14/28 days and rolling stds over 14/28 (rmean7/rmean14/rmean28/rstd14/
  rstd28), so the boosters see trend/volatility state, not just levels.
- **Wave-22 hierarchy anchoring** — ``routed_reconciled`` (comparison-only):
  per country block the routed forecast is reconciled to the seasonal-naive
  anchor of the country's aggregated demand (a denser, independent signal),
  discrepancy allocated proportionally to the routed forecasts (fallback:
  training-window means; then no adjustment).
- **Wave-22 metrics** — ``rmae`` (candidate pooled MAE / floor pooled MAE) and
  per-candidate ``rmsse`` (M5 convention) per class and pooled; the decision
  block gains a newsvendor order-quantile cost layer (documented cost
  assumptions, no savings claims). The headline claim quotes rmae.

Outputs are merged into the track's metrics.json (``_multistep`` block — the
per-model nowcast blocks stay untouched), probabilistic.json (``multistep``
key, including per-candidate bands for the peak-capable models),
evaluation_metadata.json (``multi_horizon`` block) and seven figures
(unit-incompatible metrics never share an axis; three of them are the wave-20
peak-capture views).
"""

import json
import math
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import polars as pl
from joblib import Parallel, delayed, parallel_config
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_json
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]  # re-exported

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.evaluate import _json_safe
from demand_forecasting.intermittent import (
    ADI_THRESHOLD,
    CV2_THRESHOLD,
    SPARSE_CLASSES,
    STATISTICAL_METHODS,
    classify_panel,
    statistical_forecast,
)
from demand_forecasting.probabilistic import (
    CALIBRATION_TOL,
    TARGET_COVERAGE,
    calibration_verdict,
)

logger = get_logger(__name__)

PROTOCOL = "direct_multihorizon_v1"
# Target-relative lag ages: lag_h, lag_{h+7}, lag_{h+14} (all ≥ h days old).
LAG_AGES = (0, 7, 14)
# Features need units(origin-14) (lags) and a full 28-day window ending at the
# origin (peak features), so training/prediction designs start at day 28.
MIN_LAG_ORIGIN = 28
ORIGIN_SPACING_DAYS = 7
# Quantile levels for the learner's forecast distribution.
QUANTILES_MS = (0.1, 0.5, 0.9)
# Sparse-band quantile ladder levels (over the training-window demand history).
LADDER_LEVELS = (0.5, 0.8, 0.9, 0.95)

# Peak-oriented features (wave 20), all computed at the reference day
# target-h (= the origin, relative to which every one is ≥ h days old — the
# same leakage-by-construction aging as the lag trio): rolling mean AND max
# over 7/14/28-day windows ending at the reference day, days since the last
# non-zero demand day, the non-zero-day count of the last 28 days, and the
# peak ratio (28d rolling max / 28d rolling mean) the flat intermittent
# estimators structurally cannot see.
PEAK_WINDOWS = (7, 14, 28)
PEAK_FEATURE_NAMES = (
    "roll_mean_7",
    "roll_mean_14",
    "roll_mean_28",
    "roll_max_7",
    "roll_max_14",
    "roll_max_28",
    "days_since_last_nz",
    "nz_count_28",
    "peak_ratio_28",
)
N_PEAK_FEATURES = len(PEAK_FEATURE_NAMES)
# Price features (wave 21), all computed at a reference day r from price[≤r]
# only — the same aging contract as the peak block. Online Retail II is B2B
# wholesale, so a price cut is the promo proxy: ``price_ratio_28d`` compares
# the last known price with its 28-day mean as of target-h, ``price_drop``
# flags a >10% cut, ``days_since_price_change`` counts days since the last
# observed price change. Panels without a price column (synthetic track) get
# a NEUTRAL tensor (asof/ratio 1.0, the rest 0.0) — constant columns the
# boosters never split on, so the synthetic track is bit-stable.
PRICE_FEATURE_NAMES = (
    "price_asof",
    "price_ratio_28d",
    "days_since_price_change",
    "price_drop",
)
N_PRICE_FEATURES = len(PRICE_FEATURE_NAMES)
PRICE_WINDOW_DAYS = 28
PRICE_DROP_RATIO = 0.9
# Rolling-statistics features (wave 22), all computed at a reference day r
# from units[<=r] only — the same aging contract as the peak/price blocks
# (taint-tested). Means over 7/14/28-day windows, stds over 14/28; windows of
# length w are undefined for r < w - 1 and filled with 0.0 (never read:
# designs start at MIN_LAG_ORIGIN = 28).
ROLLING_FEATURE_NAMES = ("rmean7", "rmean14", "rmean28", "rstd14", "rstd28")
N_ROLLING_FEATURES = len(ROLLING_FEATURE_NAMES)
ROLLING_MEAN_WINDOWS = (7, 14, 28)
ROLLING_STD_WINDOWS = (14, 28)
# Newsvendor decision layer (wave 22): the order quantity is the forecast
# band's q-quantile (q in config.service_levels). Cost model is a DOCUMENTED
# ASSUMPTION (not a measured saving): holding 1.0 per ordered-but-unsold unit
# per day, stockout penalty 3.0 per unmet unit per day.
NEWSVENDOR_HOLDING_COST = 1.0
NEWSVENDOR_STOCKOUT_COST = 3.0
# The committed learner band ladder the dense-row quantiles interpolate.
BAND_LADDER_LEVELS = QUANTILES_MS
# Trading-cycle calendar additions (wave 21): wholesale buyers concentrate
# orders at month end, so the TARGET-date calendar carries is_month_end (the
# next calendar day starts a new month) and week_of_month ((dom-1)//7+1).
# Pure functions of the target date — known in advance, leakage-free.
# Tweedie variance power: sklearn's HalfTweedieLoss fixes the compound-Poisson
# regime 1 < p < 2; p = 1.5 is the standard peak-tolerant choice.
TWEEDIE_POWER = 1.5
# Hurdle-family candidates that go through the selection-origin
# zero-correction (identity / scalar / isotonic) — all are two-stage
# p̂ x size models with the same conditional-mean bias structure.
HURDLE_CANDIDATES = ("hurdle_hgb", "hurdle_lgbm", "peak_weighted_hgb")
# Sample-weight grid for peak_weighted_hgb (top-decile demand days up-weighted
# by w in the hurdle fits); the winner is chosen on the selection origins.
PEAK_WEIGHTS = (2.0, 3.0)

CANDIDATES = (
    "routed",
    "direct_hgb",
    "seasonal_naive",
    "zero",
    "croston",
    "sba",
    "tsb",
    "ma_28",
    "adida_sba",
    "adida_tsb",
    "hgb_tweedie",
    "hurdle_hgb",
    "lgbm_tweedie",
    "lgbm_poisson",
    "hurdle_lgbm",
    "peak_weighted_hgb",
    "ensemble_convex",
    "routed_reconciled",
)
# Peak-capable ML candidates the sparse-series router may pick (direct_hgb
# stays reserved for smooth/erratic series — the wave-19 routing finding).
# Wave 21 adds the LightGBM family and the peak-weighted hurdle; the same
# list serves the dense pool (direct_hgb + these candidates).
ML_SPARSE = (
    "hgb_tweedie",
    "hurdle_hgb",
    "lgbm_tweedie",
    "lgbm_poisson",
    "hurdle_lgbm",
    "peak_weighted_hgb",
)
# Candidates compared against the routed pipeline and the zero floor in the
# candidate-comparison / headline rows (the ML pool + the convex ensemble +
# the wave-22 hierarchy-anchored routed post-processing). routed_reconciled
# is comparison-only: it never enters the routing pool.
COMPARISON_CANDIDATES = (*ML_SPARSE, "ensemble_convex", "routed_reconciled")
CHAMPION = "routed"
FLOOR = "seasonal_naive"
NAIVE = "zero"


# ---------------------------------------------------------------------------
# Panel → matrix + calendar
# ---------------------------------------------------------------------------


def panel_matrix(panel: pl.DataFrame) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Pivot the panel to (dates, series_ids, units) dense numpy arrays."""
    p = panel.with_columns((pl.col("store") + "|" + pl.col("product")).alias("series_id")).sort(
        ["date", "series_id"]
    )
    wide = p.pivot(index="date", on="series_id", values="units").sort("date")
    series_ids = [str(c) for c in wide.columns if c != "date"]
    units = wide.drop("date").to_numpy().astype(float)
    dates = wide["date"].to_numpy()
    return dates, series_ids, units


def panel_price_matrix(
    panel: pl.DataFrame, dates: np.ndarray, series_ids: list[str]
) -> np.ndarray | None:
    """Pivot the panel's ``price`` column to a (dates x series) matrix aligned
    with :func:`panel_matrix`. Returns None when the panel carries no price
    column (the synthetic track) — callers then use the neutral tensor.
    """
    if "price" not in panel.columns:
        return None
    p = panel.with_columns((pl.col("store") + "|" + pl.col("product")).alias("series_id")).sort(
        ["date", "series_id"]
    )
    wide = p.pivot(index="date", on="series_id", values="price").sort("date")
    cols = [str(c) for c in wide.columns if c != "date"]
    mat = wide.drop("date").to_numpy().astype(float)
    if not np.array_equal(wide["date"].to_numpy(), dates) or set(cols) != set(series_ids):
        raise ValueError("price pivot does not align with the units pivot")
    order = [cols.index(s) for s in series_ids]
    return mat[:, order]


def _calendar_features(dates: np.ndarray) -> np.ndarray:
    """The multi-step calendar block (9 columns), as a pure function of date.

    Columns: dow (1=Mon..7=Sun), is_weekend, month, iso week, doy sin/cos, day
    ordinal (trend counter), is_month_end (the next calendar day starts a new
    month — the wave-21 trading-cycle hypothesis: wholesale buyers concentrate
    orders at month end) and week_of_month ((dom-1)//7 + 1). Deterministic and
    known in advance — leakage-free.
    """
    py_dates = dates.astype("datetime64[D]").astype(object)
    epoch = np.datetime64("0001-01-01")
    ordinals = (dates.astype("datetime64[D]") - epoch).astype(np.int64) + 1
    dow = np.array([d.weekday() + 1 for d in py_dates], dtype=float)  # 1=Mon
    is_weekend = (dow >= 6).astype(float)
    months = np.array([d.month for d in py_dates], dtype=float)
    weeks = np.array([int(d.isocalendar().week) for d in py_dates], dtype=float)
    doy = np.array([d.timetuple().tm_yday for d in py_dates], dtype=float)
    ang = doy * math.tau / 365.25
    next_months = np.array([(d + timedelta(days=1)).month for d in py_dates], dtype=float)
    is_month_end = (next_months != months).astype(float)
    week_of_month = np.array([(d.day - 1) // 7 + 1 for d in py_dates], dtype=float)
    return np.column_stack(
        [
            dow,
            is_weekend,
            months,
            weeks,
            np.sin(ang),
            np.cos(ang),
            ordinals.astype(float),
            is_month_end,
            week_of_month,
        ]
    )


# ---------------------------------------------------------------------------
# Peak features (all computed at a reference day r from units[≤r] only)
# ---------------------------------------------------------------------------


def peak_feature_tensor(units: np.ndarray) -> np.ndarray:
    """(n_dates x n_series x N_PEAK_FEATURES) tensor of peak features.

    Every feature for reference day *r* reads ``units[≤r]`` only, so a design
    whose reference day is ``target - h`` references no actual within *h* days
    of the target — the same aging that makes the lag trio leakage-proof.
    Columns follow :data:`PEAK_FEATURE_NAMES`; windows of length *w* are
    undefined for ``r < w - 1`` and filled with 0.0 (never read: designs start
    at :data:`MIN_LAG_ORIGIN` = 28). ``days_since_last_nz`` is the distance
    back from *r* to the most recent non-zero day (``r + 1`` if none yet).
    ``peak_ratio_28`` is 0.0 when the 28d rolling mean is 0 (all-zero window).
    """
    n_dates, n_series = units.shape
    pf = np.zeros((n_dates, n_series, N_PEAK_FEATURES))
    csum = np.vstack([np.zeros((1, n_series)), np.cumsum(units, axis=0)])
    nonzero = (units > 0).astype(float)
    cpos = np.vstack([np.zeros((1, n_series)), np.cumsum(nonzero, axis=0)])
    for col, w in enumerate(PEAK_WINDOWS):
        if w > n_dates:
            continue  # window never fully fits; features stay 0.0 (undefined)
        idx = np.arange(w - 1, n_dates)  # reference days with a full window
        pf[idx, :, col] = (csum[idx + 1] - csum[idx + 1 - w]) / w
        pf[idx, :, col + 3] = np.lib.stride_tricks.sliding_window_view(units, w, axis=0).max(axis=2)
    last_nz = np.full(n_series, -1)
    dsl = np.zeros((n_dates, n_series))
    for r in range(n_dates):
        last_nz = np.where(units[r] > 0, r, last_nz)
        dsl[r] = np.where(last_nz >= 0, (r - last_nz).astype(float), float(r + 1))
    pf[:, :, 6] = dsl
    pf[27:, :, 7] = cpos[28:] - cpos[:-28]  # non-zero-day count, last 28 days
    mean28 = pf[:, :, 2]
    pf[:, :, 8] = np.where(mean28 > 0, pf[:, :, 5] / np.where(mean28 > 0, mean28, 1.0), 0.0)
    return pf


# ---------------------------------------------------------------------------
# Price features (wave 21) — all computed at a reference day r from price[≤r]
# ---------------------------------------------------------------------------


def neutral_price_tensor(n_dates: int, n_series: int) -> np.ndarray:
    """The no-price-panel neutral tensor: asof/ratio 1.0, the rest 0.0.

    Every column is constant, so the boosters never split on it — the
    synthetic track (no price column) stays bit-stable.
    """
    out = np.zeros((n_dates, n_series, N_PRICE_FEATURES))
    out[:, :, 0] = 1.0
    out[:, :, 1] = 1.0
    return out


def price_feature_tensor(price: np.ndarray) -> np.ndarray:
    """(n_dates x n_series x N_PRICE_FEATURES) tensor of price features.

    Every feature for reference day *r* reads ``price[≤r]`` only, so a design
    whose reference day is ``target - h`` references no price within *h* days
    of the target — the same aging as the peak block (taint-tested: post-target-h
    price moves must not move the features). Columns follow
    :data:`PRICE_FEATURE_NAMES`:

    - ``price_asof[r]`` — the last valid (finite, > 0) price at day ≤ r;
      1.0 when the series has no observed price yet (neutral).
    - ``price_ratio_28d[r]`` — ``price_asof[r] / mean(price_asof over the
      28 days ending at r)``; 1.0 before the first full window (day 27 —
      never read: designs start at :data:`MIN_LAG_ORIGIN` = 28). A price cut
      shows up here as a ratio < 1.
    - ``days_since_price_change[r]`` — days since the most recent day whose
      valid price differed from the previously observed price (0 on the
      change day); ``r + 1`` when no price was ever observed.
    - ``price_drop[r]`` — 1.0 when ``price_ratio_28d < 0.9`` (the wholesale
      promo proxy), else 0.0.
    """
    n_dates, n_series = price.shape
    out = np.zeros((n_dates, n_series, N_PRICE_FEATURES))
    valid = np.isfinite(price) & (price > 0)
    # forward pass: last-valid-price (asof) and days-since-price-change
    asof = np.ones((n_dates, n_series))
    prev = np.full(n_series, np.nan)
    last = np.ones(n_series)
    last_change = np.full(n_series, -1)
    seen = np.zeros(n_series, dtype=bool)
    for r in range(n_dates):
        m = valid[r]
        changed = m & (price[r] != prev)
        last = np.where(m, price[r], last)
        seen |= m
        prev = np.where(m, price[r], prev)
        last_change = np.where(changed, r, last_change)
        asof[r] = np.where(seen, last, 1.0)
        out[r, :, 2] = np.where(last_change >= 0, (r - last_change).astype(float), float(r + 1))
    out[:, :, 0] = asof
    # 28d window mean of asof (window [r-27, r]); ratio 1.0 before day 27
    csum = np.vstack([np.zeros((1, n_series)), np.cumsum(asof, axis=0)])
    idx = np.arange(PRICE_WINDOW_DAYS - 1, n_dates)
    if idx.size:
        mean_w = (csum[idx + 1] - csum[idx + 1 - PRICE_WINDOW_DAYS]) / PRICE_WINDOW_DAYS
        ratio = np.ones((n_dates, n_series))
        ratio[idx] = asof[idx] / mean_w
        out[:, :, 1] = ratio
        out[:, :, 3] = (ratio < PRICE_DROP_RATIO).astype(float)
    else:
        out[:, :, 1] = 1.0
    return out


# ---------------------------------------------------------------------------
# Rolling features (wave 22) — all computed at a reference day r from units[≤r]
# ---------------------------------------------------------------------------


def rolling_feature_tensor(units: np.ndarray) -> np.ndarray:
    """(n_dates x n_series x N_ROLLING_FEATURES) tensor of rolling statistics.

    Every feature for reference day *r* reads ``units[<=r]`` only, so a design
    whose reference day is ``target - h`` references no actual within *h* days
    of the target — the same aging that makes the lag trio/peak/price blocks
    leakage-proof (taint-tested). Columns follow
    :data:`ROLLING_FEATURE_NAMES`: rolling means over 7/14/28-day windows
    (columns 0-2) and rolling standard deviations (population, ddof=0) over
    14/28-day windows (columns 3-4), each window ENDING at the reference day.
    Windows of length *w* are undefined for ``r < w - 1`` and filled with 0.0
    (never read: designs start at :data:`MIN_LAG_ORIGIN` = 28).
    """
    n_dates, n_series = units.shape
    out = np.zeros((n_dates, n_series, N_ROLLING_FEATURES))
    csum = np.vstack([np.zeros((1, n_series)), np.cumsum(units, axis=0)])
    csum2 = np.vstack([np.zeros((1, n_series)), np.cumsum(units**2, axis=0)])
    col = 0
    for w in ROLLING_MEAN_WINDOWS + ROLLING_STD_WINDOWS:
        if w > n_dates:
            continue  # window never fully fits; features stay 0.0 (undefined)
        idx = np.arange(w - 1, n_dates)  # reference days with a full window
        s1 = csum[idx + 1] - csum[idx + 1 - w]
        mean = s1 / w
        if col < len(ROLLING_MEAN_WINDOWS):
            out[idx, :, col] = mean
        else:
            var = np.maximum(csum2[idx + 1] - csum2[idx + 1 - w] - w * mean**2, 0.0) / w
            out[idx, :, col] = np.sqrt(var)
        col += 1
    return out


# ---------------------------------------------------------------------------
# Weekly rolling origins (no embargo gap)
# ---------------------------------------------------------------------------


def multistep_origin_indices(n_dates: int, config: ForecastConfig) -> list[int]:
    """Weekly rolling origin indices with the cap applied (documented).

    Origin *o* trains on days 0..o (so ``o + 1 ≥ min_train_size``) and scores
    the window o+1 .. o+window_days (so ``o ≤ n_dates - window_days - 1``).
    The design for horizon h needs training rows down to candidate origin
    :data:`MIN_LAG_ORIGIN`, so ``o ≥ MIN_LAG_ORIGIN + h`` for the largest
    horizon (wave 20: peak features raised MIN_LAG_ORIGIN to 28). The
    forecast window starts the day AFTER the origin — no embargo gap. When
    the eligible range exceeds ``multistep_n_origins``, the oldest origins
    are dropped (exact weekly cadence preserved; the cap exists for runtime;
    UCI's 43 eligible weekly origins are capped to the most recent 20).
    """
    first = max(
        config.min_train_size - 1,
        MIN_LAG_ORIGIN + max(config.multistep_horizons),
    )
    last = n_dates - config.multistep_window_days - 1
    if last < first:
        raise ValueError(
            f"panel too short for the multi-step track: {n_dates} dates, "
            f"need >= {first + config.multistep_window_days + 1}"
        )
    eligible = list(range(first, last + 1, ORIGIN_SPACING_DAYS))
    cap = config.multistep_n_origins
    if len(eligible) > cap:
        # keep the exact weekly cadence: drop the OLDEST origins (runtime cap,
        # documented in the block's cap_note)
        eligible = eligible[-cap:]
    return eligible


def split_origins(origin_indices: list[int], config: ForecastConfig) -> tuple[list[int], list[int]]:
    """(selection origins, test origins) — the LAST ``multistep_test_origins``
    origins are scored once and never read for selection."""
    n_test = min(config.multistep_test_origins, max(1, len(origin_indices) // 3))
    return origin_indices[:-n_test], origin_indices[-n_test:]


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


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------


def pinball_loss(y: np.ndarray, q: np.ndarray, tau: float) -> float:
    """Mean pinball (quantile) loss — lower is better."""
    diff = y - q
    return float(np.mean(np.maximum(tau * diff, (tau - 1.0) * diff)))


def order_up_to_cost(
    order: np.ndarray, y: np.ndarray, holding_cost: float, stockout_cost: float
) -> float:
    """Holding + stockout cost of one order-up-to decision (per scored cell).

    ``holding_cost · max(order - actual, 0) + stockout_cost · max(actual -
    order, 0)`` — the order-up-to simulation's cost cell, kept pure so the
    math is hand-testable.
    """
    order = np.asarray(order, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(
        holding_cost * np.maximum(order - y, 0.0).sum()
        + stockout_cost * np.maximum(y - order, 0.0).sum()
    )


def _ladder_quantile(q: float, p10: np.ndarray, p50: np.ndarray, p90: np.ndarray) -> np.ndarray:
    """q-quantile of the committed p10/p50/p90 band ladder (wave 22 newsvendor).

    Linear interpolation between the ladder rungs, linear extrapolation above
    p90 / below p10 (same segment slope), zero-clipped. Pure math, hand-testable:
    with p10=1, p50=3, p90=5 the q=0.8 rung is 3 + 0.3 x (5-3)/0.4 = 4.5.
    """
    lo_slope = (p50 - p10) / (0.5 - 0.1)
    hi_slope = (p90 - p50) / (0.9 - 0.5)
    out = np.where(q <= 0.5, p50 + (q - 0.5) * lo_slope, p50 + (q - 0.5) * hi_slope)
    return np.maximum(out, 0.0)


def _paired_bootstrap_cost(
    cost_a: np.ndarray,
    cost_b: np.ndarray,
    demand: np.ndarray,
    series_codes: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """95% CI on cost-per-unit-demand(A) - cost-per-unit-demand(B).

    Same resampling contract as :func:`_paired_bootstrap_mae` (one shared
    series-index draw per replication, percentile interval); the replicated
    statistic is the resampled-cluster cost ratio difference, so the point
    estimate is (sum A / sum demand) - (sum B / sum demand) over all cells.
    """
    uniques = np.unique(series_codes)
    sum_a = np.array([cost_a[series_codes == i].sum() for i in uniques])
    sum_b = np.array([cost_b[series_codes == i].sum() for i in uniques])
    sum_d = np.array([demand[series_codes == i].sum() for i in uniques])
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, len(uniques), len(uniques))
        denom = sum_d[idx].sum()
        diffs[b] = (sum_a[idx].sum() - sum_b[idx].sum()) / denom if denom > 0 else np.nan
    lo, hi = np.nanquantile(diffs, [0.025, 0.975])
    denom = demand.sum()
    point = (cost_a.sum() - cost_b.sum()) / denom if denom > 0 else float("nan")
    return {
        "diff": float(point),
        "ci95": [float(lo), float(hi)],
        "spans_zero": bool(lo <= 0.0 <= hi),
        "n_boot": n_boot,
        "seed": seed,
    }


def rmsse_pooled(
    err: np.ndarray,
    scale2: np.ndarray,
    volume: np.ndarray,
    series_codes: np.ndarray,
) -> tuple[float, float]:
    """(pooled RMSSE, volume-weighted RMSSE) — M5-style.

    Per series i: ``sqrt(mean(err²) / scale2_i)`` with scale2_i the in-sample
    MSE of the one-step seasonal-naive-7 on the cell's training window
    (scale2 = 0 → the series is excluded, not infinite). The weighted variant
    weights those per-series RMSSEs by the series' training-window volume.
    """
    pooled: list[float] = []
    w_num = 0.0
    w_den = 0.0
    for i in np.unique(series_codes):
        mask = series_codes == i
        s2 = float(scale2[mask][0])
        if s2 > 0:
            r = math.sqrt(float(np.mean(err[mask] ** 2)) / s2)
            pooled.append(r)
            vol = float(volume[mask][0])
            w_num += vol * r
            w_den += vol
    if not pooled:
        return float("nan"), float("nan")
    return float(np.mean(pooled)), (w_num / w_den if w_den > 0 else float("nan"))


def _rmae_cells(cells: dict[str, Any], mask: np.ndarray, pred_key: str) -> float:
    """Relative MAE: candidate pooled MAE / seasonal_naive floor pooled MAE
    over the same masked cells (< 1 = beats the floor). NaN when the floor's
    pooled MAE is 0 (no relative scale exists)."""
    err_c = float(np.abs(cells["pred"][pred_key][mask] - cells["y"][mask]).mean())
    err_f = float(np.abs(cells["pred"][FLOOR][mask] - cells["y"][mask]).mean())
    return err_c / err_f if err_f > 0 else float("nan")


def _rmsse_cells(cells: dict[str, Any], mask: np.ndarray, pred_key: str) -> tuple[float, float]:
    """(pooled, volume-weighted) RMSSE for one candidate over the masked
    cells, M5 convention: the unit is a (series x scored origin) evaluation —
    numerator = MSE of the candidate over that unit's scored horizon days,
    denominator = the in-sample MSE of the one-step seasonal-naive-7 over the
    unit's training window (cells["scale2"], 0-scale units excluded)."""
    err = cells["pred"][pred_key][mask] - cells["y"][mask]
    origins = np.unique(cells["origin"][mask])
    rank = {int(o): k for k, o in enumerate(origins)}
    codes = cells["series"][mask] * len(origins) + np.array(
        [rank[int(o)] for o in cells["origin"][mask]]
    )
    return rmsse_pooled(err, cells["scale2"][mask], cells["volume"][mask], codes)


def _paired_bootstrap_mae(
    err_a: np.ndarray,
    err_b: np.ndarray,
    series_codes: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """95% CI on pooled-MAE(A) - pooled-MAE(B), cluster bootstrap over series.

    One shared index draw per replication resamples SERIES with replacement
    (all cells of a sampled series enter together), so the difference stays
    paired on identical resamples (the projects/05 /10 pattern). Percentile
    interval; ``spans_zero`` marks comparisons the data does not establish.
    """
    abs_a = np.abs(err_a)
    abs_b = np.abs(err_b)
    uniques = np.unique(series_codes)
    sum_a = np.array([abs_a[series_codes == i].sum() for i in uniques])
    sum_b = np.array([abs_b[series_codes == i].sum() for i in uniques])
    cnt = np.array([int((series_codes == i).sum()) for i in uniques], dtype=float)
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, len(uniques), len(uniques))
        denom = cnt[idx].sum()
        diffs[b] = (sum_a[idx].sum() - sum_b[idx].sum()) / denom
    lo, hi = np.quantile(diffs, [0.025, 0.975])
    return {
        "diff": float(abs_a.sum() / cnt.sum() - abs_b.sum() / cnt.sum()),
        "ci95": [float(lo), float(hi)],
        "spans_zero": bool(lo <= 0.0 <= hi),
        "n_boot": n_boot,
        "seed": seed,
    }


def _paired_bootstrap_values(
    val_a: np.ndarray,
    val_b: np.ndarray,
    series_of: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """95% CI on mean(A) - mean(B) over per-window values, clustered by series.

    Same resampling contract as :func:`_paired_bootstrap_mae` (one shared
    series-index draw per replication), but the unit is a scored *window*
    (series x test origin) carrying one value each (peak_mae or peak_recall).
    """
    uniques = np.unique(series_of)
    sum_a = np.array([val_a[series_of == i].sum() for i in uniques])
    sum_b = np.array([val_b[series_of == i].sum() for i in uniques])
    cnt = np.array([int((series_of == i).sum()) for i in uniques], dtype=float)
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, len(uniques), len(uniques))
        denom = cnt[idx].sum()
        diffs[b] = (sum_a[idx].sum() - sum_b[idx].sum()) / denom
    lo, hi = np.quantile(diffs, [0.025, 0.975])
    return {
        "diff": float(val_a.mean() - val_b.mean()),
        "ci95": [float(lo), float(hi)],
        "spans_zero": bool(lo <= 0.0 <= hi),
        "n_boot": n_boot,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Peak-capture metrics (the user's headline concern)
# ---------------------------------------------------------------------------

PEAK_CANDIDATES = (
    "routed",
    "zero",
    "hgb_tweedie",
    "hurdle_hgb",
    "lgbm_tweedie",
    "lgbm_poisson",
    "hurdle_lgbm",
    "peak_weighted_hgb",
    "ensemble_convex",
    "routed_reconciled",
)
# Candidates in the per-series beats-floor win-rate report.
WIN_RATE_CANDIDATES = ("routed", "zero", *COMPARISON_CANDIDATES)


def _window_peak_arrays(y3: np.ndarray, pred3: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """(peak_mae, peak_recall) per (origin, series) window.

    ``y3``/``pred3`` are (n_origins x n_horizons x n_series). ``peak_mae`` is
    the |error| on the window's top-k-by-actual demand days (the top decile:
    ``k = max(1, ceil(0.1 · n_horizons))``); ``peak_recall`` is the share of
    the window's top-5 actual days that the forecast's own top-5 ranked days
    include. Both are per-window scalars — pooled per class downstream.
    """
    n_o, _n_h, n_s = y3.shape
    top_k = np.argsort(y3, axis=1)[:, ::-1][:, :k, :]  # (n_o, k, n_s)
    arange_o = np.arange(n_o)[:, None, None]
    arange_s = np.arange(n_s)[None, None, :]
    peak_mae = np.abs(pred3[arange_o, top_k, arange_s] - y3[arange_o, top_k, arange_s]).mean(axis=1)
    top5 = np.argsort(y3, axis=1)[:, ::-1][:, :5, :]  # (n_o, 5, n_s)
    pred5 = np.argsort(pred3, axis=1)[:, ::-1][:, :5, :]
    recall = np.zeros((n_o, n_s))
    for r in range(n_o):
        for i in range(n_s):
            recall[r, i] = len(set(top5[r, :, i].tolist()) & set(pred5[r, :, i].tolist())) / 5.0
    return peak_mae, recall


def _peak_capture(
    cells: dict[str, Any],
    test: list[int],
    horizons: list[int],
    n_series: int,
    config: ForecastConfig,
) -> dict[str, Any]:
    """Peak-capture report per demand class: peak_mae + peak_recall per
    candidate (routed / zero / hgb_tweedie / hurdle_hgb), each with a paired
    cluster bootstrap CI against the routed and the zero baseline.

    Windows are (series x scored test origin); the peak days are picked within
    each window over the scored h-lattice days, so every compared number is
    an out-of-sample, selection-untouched quantity.
    """
    n_o, n_h = len(test), len(horizons)
    y3 = cells["y"].reshape(n_o, n_h, n_series)
    cls3 = cells["class"].reshape(n_o, n_h, n_series)
    ser3 = cells["series"].reshape(n_o, n_h, n_series)
    classes = [str(c) for c in np.unique(cls3)]
    k = max(1, math.ceil(0.1 * n_h))
    seed = config.seed + 4020  # distinct bootstrap stream
    series_of = ser3[:, 0, :].reshape(-1)  # window -> series

    per_cand: dict[str, dict[str, np.ndarray]] = {}
    for cand in PEAK_CANDIDATES:
        pred3 = cells["pred"][cand].reshape(n_o, n_h, n_series)
        peak_mae, recall = _window_peak_arrays(y3, pred3, k)
        per_cand[cand] = {"peak_mae": peak_mae.reshape(-1), "peak_recall": recall.reshape(-1)}
    per_class: dict[str, Any] = {}
    for cls in classes:
        mask = cls3[:, 0, :].reshape(-1) == cls
        entry: dict[str, Any] = {"n_windows": int(mask.sum())}
        for cand in PEAK_CANDIDATES:
            pm = per_cand[cand]["peak_mae"]
            pr = per_cand[cand]["peak_recall"]
            item: dict[str, Any] = {
                "peak_mae": float(pm[mask].mean()),
                "peak_recall": float(pr[mask].mean()),
            }
            for base in ("routed", "zero"):
                if cand == base:
                    continue
                item[f"peak_mae_vs_{base}"] = _paired_bootstrap_values(
                    pm[mask],
                    per_cand[base]["peak_mae"][mask],
                    series_of[mask],
                    config.bootstrap_reps,
                    seed,
                )
                item[f"peak_recall_vs_{base}"] = _paired_bootstrap_values(
                    pr[mask],
                    per_cand[base]["peak_recall"][mask],
                    series_of[mask],
                    config.bootstrap_reps,
                    seed,
                )
            entry[cand] = item
        per_class[cls] = entry
    return {
        "definition": (
            "per scored window (series x test origin) over the scored h-lattice days: "
            "peak_mae = MAE on the window's top-decile-by-actual demand days "
            f"(k = max(1, ceil(0.1 x {n_h})) = {k}); peak_recall = share of the window's "
            "top-5 actual days whose day ranks in the forecast's own top-5"
        ),
        "candidates": list(PEAK_CANDIDATES),
        "top_k_days": k,
        "top_recall_days": 5,
        "bootstrap": {
            "method": "paired cluster bootstrap over series (windows of a sampled series "
            "enter together), percentile 95% CI",
            "n_boot": config.bootstrap_reps,
            "seed": seed,
        },
        "per_class": per_class,
    }


# ---------------------------------------------------------------------------
# Per-series beats-floor win rates (wave 21: "improve error for EVERY series")
# ---------------------------------------------------------------------------


def _win_rates(
    cells: dict[str, Any], horizons: list[int], config: ForecastConfig
) -> dict[str, Any]:
    """Per-series beats-floor win rate by class and horizon, with a paired
    cluster bootstrap CI on the win rate.

    A series "beats the floor" at horizon h when its summed |error| over the
    scored test origins at that h is strictly below the seasonal-naive
    floor's. The win rate is the share of series (per class) winning that
    per-series comparison; the 95% CI resamples SERIES with replacement (one
    shared index draw per replication across candidates, so the intervals
    stay paired), exactly the cluster-bootstrap contract of the MAE CIs.
    """
    seed = config.seed + 8801  # distinct bootstrap stream
    classes = [str(c) for c in np.unique(cells["class"])]
    n_series_all = int(cells["series"].max()) + 1
    per_class: dict[str, Any] = {}
    for cls in classes:
        cls_mask = cells["class"] == cls
        series_u = np.unique(cells["series"][cls_mask])
        per_h: dict[str, Any] = {}
        for h in horizons:
            mask = cls_mask & (cells["h"] == h)
            ser = cells["series"][mask]
            y = cells["y"][mask]
            floor_s = np.bincount(
                ser, weights=np.abs(cells["pred"][FLOOR][mask] - y), minlength=n_series_all
            )
            win_mat = np.zeros((len(WIN_RATE_CANDIDATES), n_series_all))
            for k, cand in enumerate(WIN_RATE_CANDIDATES):
                cand_s = np.bincount(
                    ser, weights=np.abs(cells["pred"][cand][mask] - y), minlength=n_series_all
                )
                win_mat[k] = cand_s < floor_s
            w_cls = win_mat[:, series_u]  # (n_cand, n_series_in_class)
            rng = np.random.default_rng(seed)
            idx = rng.integers(0, w_cls.shape[1], (config.bootstrap_reps, w_cls.shape[1]))
            rates = w_cls[:, idx].mean(axis=2)  # (n_cand, n_boot)
            h_entry: dict[str, Any] = {}
            for k, cand in enumerate(WIN_RATE_CANDIDATES):
                lo, hi = np.quantile(rates[k], [0.025, 0.975])
                h_entry[cand] = {
                    "win_rate": float(w_cls[k].mean()),
                    "beats_floor_count": int(w_cls[k].sum()),
                    "ci95": [float(lo), float(hi)],
                }
            per_h[str(h)] = h_entry
        per_class[cls] = {"n_series": len(series_u), "per_horizon": per_h}
    return {
        "definition": (
            "per series and horizon: beats-floor = the series' summed |error| over the "
            "scored test origins at that h is strictly below the seasonal_naive floor's; "
            "win_rate = the share of series in the class beating the floor; 95% CI = "
            "percentile interval of a cluster bootstrap over series (one shared index "
            "draw per replication across candidates)"
        ),
        "floor": FLOOR,
        "candidates": list(WIN_RATE_CANDIDATES),
        "bootstrap": {
            "method": "cluster bootstrap over series (one shared index draw per "
            "replication across candidates), percentile 95% CI",
            "n_boot": config.bootstrap_reps,
            "seed": seed,
        },
        "per_class": per_class,
    }


def _scales(units: np.ndarray, origin: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-series (MASE scale, squared seasonal-naive scale, train volume)."""
    diffs = units[7 : origin + 1] - units[: origin + 1 - 7]
    return (
        np.mean(np.abs(diffs), axis=0),
        np.mean(diffs**2, axis=0),
        units[: origin + 1].sum(axis=0),
    )


# ---------------------------------------------------------------------------
# Long table over test origins
# ---------------------------------------------------------------------------


def _test_cells(
    by_origin: dict[int, OriginScore],
    test: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    series_ids: list[str],
    ens_weights: np.ndarray | None = None,
    ens_ml_idx: np.ndarray | None = None,
) -> dict[str, Any]:
    """Flatten (series x test origin x horizon) into column arrays."""
    n_cells = units.shape[1] * len(test) * len(horizons)
    # country block per series (store = country in the UCI panel) for the
    # wave-22 hierarchy anchoring: total -> country -> (country, product)
    country_of = np.array([sid.split("|")[0] for sid in series_ids], dtype=object)
    cells: dict[str, Any] = {
        "series": np.empty(n_cells, dtype=int),
        "origin": np.empty(n_cells, dtype=int),
        "h": np.empty(n_cells, dtype=int),
        "y": np.empty(n_cells),
        "sparse": np.empty(n_cells, dtype=bool),
        "scale": np.empty(n_cells),
        "scale2": np.empty(n_cells),
        "volume": np.empty(n_cells),
        "pred": {name: np.empty(n_cells) for name in CANDIDATES},
        "p50": np.empty(n_cells),
        "p10": np.empty(n_cells),
        "p90": np.empty(n_cells),
    }
    r = 0
    for o in test:
        sc = by_origin[o]
        sc_mase, sc_scale2, sc_vol = _scales(units, o)
        for j, h in enumerate(horizons):
            n = units.shape[1]
            sl = slice(r, r + n)
            cells["series"][sl] = np.arange(n)
            cells["origin"][sl] = o
            cells["h"][sl] = h
            cells["y"][sl] = units[o + h]
            cells["sparse"][sl] = sparse
            cells["scale"][sl] = sc_mase
            cells["scale2"][sl] = sc_scale2
            cells["volume"][sl] = sc_vol
            cells["p50"][sl] = sc.quantiles[0.5][:, j]
            cells["p10"][sl] = sc.quantiles[0.1][:, j]
            cells["p90"][sl] = sc.quantiles[0.9][:, j]
            for name in (
                "direct_hgb",
                "seasonal_naive",
                "zero",
                "croston",
                "sba",
                "tsb",
                "ma_28",
                "adida_sba",
                "adida_tsb",
                "hgb_tweedie",
                "hurdle_hgb",
                "lgbm_tweedie",
                "lgbm_poisson",
                "hurdle_lgbm",
                "peak_weighted_hgb",
            ):
                cells["pred"][name][sl] = sc.preds[name][:, j]
            routed = _routed_pred(sc, j, sparse, method_of)
            cells["pred"]["routed"][sl] = routed
            cells["pred"]["routed_reconciled"][sl] = _reconciled_pred(
                units, sc, j, sparse, method_of, country_of, horizons
            )
            if ens_weights is not None and ens_ml_idx is not None:
                cells["pred"]["ensemble_convex"][sl] = _ensemble_pred(
                    sc, routed, ens_weights, ens_ml_idx, j
                )
            r += n
    return cells


def _reconciled_pred(
    units: np.ndarray,
    sc: OriginScore,
    j: int,
    sparse: np.ndarray,
    method_of: np.ndarray,
    country_of: np.ndarray,
    horizons: list[int],
) -> np.ndarray:
    """Hierarchy-anchored post-processing of the routed forecast (wave 22).

    For horizon index ``j`` (true horizon h), each country block is anchored
    to the seasonal-naive forecast of the country's AGGREGATED demand on the
    target day — a genuinely independent, denser signal than any member
    series. The discrepancy (anchor - sum of member routed forecasts) is
    allocated to member series proportionally to their routed forecast;
    members with zero forecast get nothing. If every member forecast in the
    block is zero, the discrepancy is allocated proportionally to the member
    training-window means (up to the origin); if those are all zero too, the
    block is left unadjusted. Pure numpy, deterministic.
    """
    origin = sc.origin
    h = horizons[j]
    ref = origin + h - 7 * math.ceil(h / 7)  # seasonal-naive reference day
    routed = _routed_pred(sc, j, sparse, method_of)
    countries = np.unique(country_of)
    anchor = np.zeros(countries.shape[0])
    for c_i, c in enumerate(countries):
        members = country_of == c
        anchor[c_i] = units[ref][members].sum()
    train_mean = units[: origin + 1].mean(axis=0)
    out = routed.copy()
    for c_i, c in enumerate(countries):
        members = np.flatnonzero(country_of == c)
        block_sum = float(routed[members].sum())
        discrepancy = anchor[c_i] - block_sum
        if discrepancy == 0.0:
            continue
        if block_sum > 0:
            weights = routed[members] / block_sum
        else:
            mean_sum = float(train_mean[members].sum())
            if mean_sum <= 0:
                continue  # nothing to allocate to: no adjustment
            weights = train_mean[members] / mean_sum
        out[members] = routed[members] + discrepancy * weights
    return out


# ---------------------------------------------------------------------------
# Result container + main entry
# ---------------------------------------------------------------------------


@dataclass
class MultiStepResult:
    """Everything the multi-step track produced, plus the report figures."""

    block: dict[str, Any] = field(default_factory=dict)  # metrics.json "_multistep"
    probabilistic_block: dict[str, Any] = field(default_factory=dict)  # probabilistic.json
    metadata_block: dict[str, Any] = field(default_factory=dict)  # evaluation_metadata.json
    figures: dict[str, go.Figure] = field(default_factory=dict)


def run_multistep(
    settings: DemandSettings, config: ForecastConfig, panel: pl.DataFrame
) -> MultiStepResult:
    """Run the full direct multi-horizon track; returns JSON blocks + figures."""
    del settings  # artifact merging is the caller's job (evaluate.py)
    dates, series_ids, units = panel_matrix(panel)
    price = panel_price_matrix(panel, dates, series_ids)
    cal = _calendar_features(dates)
    horizons = list(config.multistep_horizons)
    n_series = len(series_ids)
    classes = classify_panel(units, series_ids)
    sparse = np.array([classes[s]["class"] in SPARSE_CLASSES for s in series_ids])

    origins = multistep_origin_indices(len(dates), config)
    selection, test = split_origins(origins, config)
    logger.info(
        "multistep: %d origins (%d selection + %d test), horizons %s, %d series, "
        "%d sparse (%.1f%%), price features %s",
        len(origins),
        len(selection),
        len(test),
        horizons,
        n_series,
        int(sparse.sum()),
        100.0 * sparse.mean(),
        "on" if price is not None else "off (neutral)",
    )
    # inner_max_num_threads=1: the workers run full-core already — letting
    # each estimator ALSO spawn its own thread pool (sklearn OpenMP, LightGBM)
    # oversubscribes the machine and every fit slows down several-fold
    with parallel_config("loky", inner_max_num_threads=1):
        scores = Parallel(n_jobs=-2)(
            delayed(_score_origin)(units, cal, o, horizons, config, (), price) for o in origins
        )
    by_origin = {s.origin: s for s in scores}

    # ---- peak-weight choice + hurdle zero-correction: SELECTION origins only --
    pw_choice = choose_peak_weight(by_origin, selection, horizons, units)
    correction = apply_hurdle_correction(by_origin, selection, horizons, units)

    # ---- routing: per-series best candidate on SELECTION origins only ----
    method_of = _route(by_origin, selection, horizons, units, sparse, n_series)

    # ---- convex ensemble: per-series weight on SELECTION origins only (no refits)
    ens = ensemble_weights(by_origin, selection, horizons, units, sparse, method_of, n_series)
    ens_ml_idx = np.array([ML_SPARSE.index(str(m)) for m in ens["ml_choice"]])

    # ---- long table over the TEST origins (scored once) ----
    cells = _test_cells(
        by_origin,
        test,
        horizons,
        units,
        sparse,
        method_of,
        series_ids,
        ens["weights"],
        ens_ml_idx,
    )
    class_of_series = np.array([classes[s]["class"] for s in series_ids])
    cells["class"] = class_of_series[cells["series"]]

    per_horizon = _per_horizon_metrics(cells, horizons)
    bands = _bands(by_origin, selection, test, horizons, units, sparse, cells)
    bootstrap = _bootstrap_suite(cells, horizons, config)
    growth = _growth_curves(cells, horizons)
    peak = _peak_capture(cells, test, horizons, n_series, config)
    win_rates = _win_rates(cells, horizons, config)
    class_of_series = np.array([classes[s]["class"] for s in series_ids])
    decision = _order_up_to(
        by_origin,
        selection,
        horizons,
        units,
        sparse,
        method_of,
        cells,
        class_of_series,
        config,
        dates,
    )
    block = _assemble_block(
        dates,
        origins,
        selection,
        test,
        horizons,
        classes,
        sparse,
        method_of,
        per_horizon,
        bands,
        bootstrap,
        growth,
        decision,
        cells,
        series_ids,
        config,
        correction,
        peak,
        win_rates,
        pw_choice,
        ens,
    )
    figures = _figures(block, horizons, bands["json"], cells, test, n_series)
    result = MultiStepResult(
        block=block,
        probabilistic_block=bands["json"],
        metadata_block=_metadata_block(block, config),
        figures=figures,
    )
    logger.info(
        "multistep: pooled MAE h1=%.3f -> h14=%.3f (champion), coverage pooled=%.3f (%s)",
        per_horizon[horizons[0]]["champion"]["mae"],
        per_horizon[horizons[-1]]["champion"]["mae"],
        bands["json"]["pooled_coverage"],
        bands["json"]["pooled_verdict"],
    )
    return result


# ---------------------------------------------------------------------------
# Hurdle zero-correction (chosen on the SELECTION origins only)
# ---------------------------------------------------------------------------


def choose_peak_weight(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
) -> dict[str, Any]:
    """Pick the peak_weighted_hgb sample-weight multiplier on SELECTION cells.

    Both weight variants (see :data:`PEAK_WEIGHTS`) are fit at every origin;
    the one with the lowest pooled |error| over the selection origins' cells
    wins and its raw predictions become the ``peak_weighted_hgb`` candidate
    (which then goes through the same zero-correction as the other hurdle
    models). Reads no test-origin actual (property-tested).
    """
    scores: dict[str, float] = {}
    for w in PEAK_WEIGHTS:
        total = 0.0
        count = 0
        for o in selection:
            y = np.column_stack([units[o + h] for h in horizons])
            total += float(np.abs(by_origin[o].pw_raw[w] - y).sum())
            count += int(y.size)
        scores[str(w)] = total / count if count else float("nan")
    chosen = float(min(scores, key=lambda k: scores[k]))
    for sc in by_origin.values():
        sc.hurdle_raw["peak_weighted_hgb"] = sc.pw_raw[chosen]
        sc.preds["peak_weighted_hgb"] = sc.pw_raw[chosen].copy()
        # promote the same variant in the what-if shock entries (keyed by
        # weight until now; apply_hurdle_correction maps the promoted key)
        for entry in sc.shocked.values():
            key = f"peak_weighted_hgb@{chosen}"
            if key in entry:
                entry["peak_weighted_hgb"] = entry.pop(key)
                for w in PEAK_WEIGHTS:
                    entry.pop(f"peak_weighted_hgb@{w}", None)
    return {
        "weights": list(PEAK_WEIGHTS),
        "chosen": chosen,
        "selection_mae": scores,
        "definition": "pooled MAE of each raw weight variant over the selection origins' "
        "cells; the winner is applied to all origins (then zero-corrected)",
    }


def apply_hurdle_correction(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    candidates: tuple[str, ...] = HURDLE_CANDIDATES,
) -> dict[str, Any]:
    """Pick and apply the hurdle zero-correction — tested, not assumed.

    The raw hurdle point forecast (p̂ x size) is biased toward non-zero
    answers (it is a conditional mean of the positive part). For every
    hurdle-family candidate (see :data:`HURDLE_CANDIDATES`) three mappings are
    compared on the SELECTION origins' cells only: identity, a scalar
    ``Σactual / Σpred`` shrink, and an isotonic regression of actual on
    predicted. The mapping with the lowest summed |error| on the selection
    cells wins and is applied to EVERY origin's stored predictions (in place),
    so routing and scoring see the same corrected candidate. Reads no
    test-origin actual (property-tested). Returns, per candidate, the choice
    and the selection-origin MAE of every variant (the "does the correction
    help?" evidence, committed in metrics.json).
    """
    out: dict[str, Any] = {}
    for cand in candidates:
        raw_sel: list[np.ndarray] = []
        y_sel: list[np.ndarray] = []
        for o in selection:
            sc = by_origin[o]
            if cand not in sc.hurdle_raw:  # pragma: no cover - defensive
                raise ValueError(f"origin {o} has no raw {cand} predictions")
            # both flattened series-major so cell i of raw pairs with cell i of y
            raw_sel.append(np.transpose(sc.hurdle_raw[cand]).reshape(-1))
            y_sel.append(np.column_stack([units[o + h] for h in horizons]).reshape(-1))
        raw = np.concatenate(raw_sel)
        y = np.concatenate(y_sel)
        denom = float(raw.sum())
        scalar = float(y.sum()) / denom if denom > 0 else 1.0
        iso = IsotonicRegression(out_of_bounds="clip").fit(raw, y)
        variants: dict[str, np.ndarray] = {
            "identity": raw,
            "scalar": raw * scalar,
            "isotonic": np.asarray(iso.predict(raw), dtype=float),
        }
        maes = {name: float(np.abs(v - y).mean()) for name, v in variants.items()}
        chosen = min(maes, key=lambda name: maes[name])

        def _map(
            flat: np.ndarray,
            _chosen: str = chosen,
            _scalar: float = scalar,
            _iso: IsotonicRegression = iso,
        ) -> np.ndarray:
            if _chosen == "identity":
                return flat
            if _chosen == "scalar":
                return flat * _scalar
            return np.asarray(_iso.predict(flat), dtype=float)

        for sc in by_origin.values():
            if cand not in sc.hurdle_raw:  # pragma: no cover - defensive
                continue
            sc.preds[cand] = _map(sc.hurdle_raw[cand].reshape(-1)).reshape(
                sc.hurdle_raw[cand].shape
            )
            # the demo payload's what-if curves go through the same mapping
            for entry in sc.shocked.values():
                if cand in entry:
                    raw_s = entry[cand]
                    entry[cand] = _map(raw_s.reshape(-1)).reshape(raw_s.shape)
        out[cand] = {
            "chosen": chosen,
            "selection_mae": maes,
            "scalar_factor": scalar,
        }
    out["note"] = (
        "identity/scalar/isotonic compared on the selection origins only; the "
        "winner per hurdle candidate is applied to all origins; a series of "
        "all-zero training windows has no correction candidate (raw p̂=0)"
    )
    return out


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _route(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    n_series: int,
) -> np.ndarray:
    """Per-series method: best candidate on SELECTION origins only.

    Pool per series (the wave-20 extension of the wave-19 statistical-only
    router): sparse (ADI ≥ 1.32) series choose among the statistical methods
    AND the peak-capable ML candidates (hgb_tweedie / hurdle_hgb) — direct_hgb
    stays excluded there (the wave-19 finding: boosted trees overfit sparse
    series); smooth/erratic series choose among direct_hgb (the previous
    routed winner) and the two ML candidates. Property (tested): the choice
    reads no test-origin actual — shuffling the test window leaves every
    choice unchanged.
    """
    pool = (*STATISTICAL_METHODS, *ML_SPARSE, "direct_hgb")
    cand_err = {name: np.zeros(n_series) for name in pool}
    for o in selection:
        sc = by_origin[o]
        actual = np.column_stack([units[o + h] for h in horizons])
        for name in pool:
            cand_err[name] += np.abs(actual - sc.preds[name]).sum(axis=1)
    # eligibility: statistical methods are sparse-only, direct_hgb is dense-only
    for name in STATISTICAL_METHODS:
        cand_err[name][~sparse] = np.inf
    cand_err["direct_hgb"][sparse] = np.inf
    stack = np.stack([cand_err[name] for name in pool], axis=1)
    method_of = np.array(pool, dtype=object)[np.argmin(stack, axis=1)]
    return method_of.copy()


# ---------------------------------------------------------------------------
# Convex ensemble (wave 21): per-series weight between the routed pick and the
# best ML candidate, chosen on the SELECTION origins only (no refits)
# ---------------------------------------------------------------------------


def ensemble_weights(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    n_series: int,
) -> dict[str, Any]:
    """Per-series convex blend of the routed pick and the best ML candidate.

    The best ML candidate is per series (lowest summed |error| over the
    selection origins among :data:`ML_SPARSE` — every series is eligible for
    the whole ML pool; class eligibility was the router's job). The weight
    w in {0, 0.1, ..., 1} (prediction = ``w · routed + (1 - w) · best_ml``)
    minimises each series' summed |error| over the selection cells — a pure
    post-processing of stored predictions, no refits. Reads no test-origin
    actual (property-tested alongside the router).
    """
    n_h = len(horizons)
    ml_err = {c: np.zeros(n_series) for c in ML_SPARSE}
    routed_err = np.zeros(n_series)
    R = np.zeros((n_series, n_h))
    M_stack = np.zeros((n_series, n_h, len(ML_SPARSE)))  # summed ML candidate preds
    Y = np.zeros((n_series, n_h))
    for o in selection:
        sc = by_origin[o]
        y = np.column_stack([units[o + h] for h in horizons])
        routed = np.column_stack([_routed_pred(sc, j, sparse, method_of) for j in range(n_h)])
        routed_err += np.abs(y - routed).sum(axis=1)
        for k, c in enumerate(ML_SPARSE):
            ml_err[c] += np.abs(y - sc.preds[c]).sum(axis=1)
            M_stack[:, :, k] += sc.preds[c]
        R += routed
        Y += y
    # best-ML pick from the COMPLETE selection errors, then blend per series
    ml_idx = np.argmin(np.stack([ml_err[c] for c in ML_SPARSE], axis=1), axis=1)
    ml_choice = np.array(ML_SPARSE, dtype=object)[ml_idx]
    M = np.take_along_axis(M_stack, ml_idx[:, None, None], axis=2)[:, :, 0]
    grid = np.round(np.linspace(0.0, 1.0, 11), 1)
    # errs[i, g] = summed |error| of series i under weight grid[g]
    errs = np.stack([np.abs(w * R + (1.0 - w) * M - Y).sum(axis=1) for w in grid], axis=1)
    w_pos = np.argmin(errs, axis=1)
    weights = grid[w_pos]
    n_cells = n_series * n_h * len(selection)
    from collections import Counter

    return {
        "weights": weights,
        "ml_choice": ml_choice,
        "grid": [float(w) for w in grid],
        "selection_mae": {
            "routed": float(routed_err.sum() / n_cells),
            "best_ml": float(
                np.stack([ml_err[c] for c in ML_SPARSE], axis=1).min(axis=1).sum() / n_cells
            ),
            "ensemble": float(errs[np.arange(n_series), w_pos].sum() / n_cells),
        },
        "weight_counts": {str(w): int(c) for w, c in sorted(Counter(weights).items())},
        "ml_choice_counts": {
            str(m): int(c) for m, c in sorted(Counter(str(m) for m in ml_choice).items())
        },
        "definition": "per series: pred = w * routed + (1 - w) * best_ml with best_ml = the "
        "ML_SPARSE candidate of lowest summed |error| on the selection origins; w in "
        "{0, 0.1, ..., 1} minimises the same selection loss — no refits, test origins "
        "never read",
    }


def _ensemble_pred(
    sc: OriginScore, routed_col: np.ndarray, weights: np.ndarray, ml_idx: np.ndarray, j: int
) -> np.ndarray:
    """The convex-ensemble point forecast for one (origin, horizon j) column:
    blend of the routed pipeline's per-series pick with that series' best ML
    candidate — ``w x routed + (1 - w) x best_ml`` (see :func:`ensemble_weights`)."""
    ml_stack = np.stack([sc.preds[c][:, j] for c in ML_SPARSE], axis=1)  # (n_s, n_c)
    best_ml = np.take_along_axis(ml_stack, ml_idx[:, None], axis=1)[:, 0]
    return np.asarray(weights * routed_col + (1.0 - weights) * best_ml, dtype=float)


# ---------------------------------------------------------------------------
# Per-horizon metric suite
# ---------------------------------------------------------------------------


def _metric_dict(cells: dict[str, Any], mask: np.ndarray, pred_key: str) -> dict[str, float]:
    """Pooled MAE/RMSE/MASE/bias/WAPE for one candidate over the masked cells."""
    y = cells["y"][mask]
    err = cells["pred"][pred_key][mask] - y
    abs_err = np.abs(err)
    scale_mask = cells["scale"][mask] > 0
    mase = (
        float(abs_err[scale_mask].sum() / cells["scale"][mask][scale_mask].sum())
        if scale_mask.any()
        else float("nan")
    )
    abs_y = float(np.abs(y).sum())
    return {
        "n": int(mask.sum()),
        "mae": float(abs_err.mean()),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mase": mase,
        "bias": float(err.mean()),
        "wape": float(abs_err.sum() / abs_y) if abs_y > 0 else float("nan"),
    }


def _per_horizon_metrics(cells: dict[str, Any], horizons: list[int]) -> dict[int, dict[str, Any]]:
    """Pooled MAE/RMSE/MASE/bias/WAPE/RMSSE per TRUE horizon (test origins).

    Errors now genuinely grow with h — the growth curve is the point.
    MASE divides the pooled |err| by the pooled per-series seasonal scale
    (zero-scale rows excluded); RMSSE is M5-style per series, reported pooled
    and volume-weighted. Champion and floor metrics are both carried.
    """
    out: dict[int, dict[str, Any]] = {}
    for h in horizons:
        mask = cells["h"] == h
        entry: dict[str, Any] = {
            "champion": _metric_dict(cells, mask, CHAMPION),
            "floor": _metric_dict(cells, mask, FLOOR),
        }
        err = cells["pred"][CHAMPION][mask] - cells["y"][mask]
        rmsse, wrmsse = rmsse_pooled(
            err, cells["scale2"][mask], cells["volume"][mask], cells["series"][mask]
        )
        entry["champion"]["rmsse"] = rmsse
        entry["champion"]["wrmsse"] = wrmsse
        out[h] = entry
    return out


# ---------------------------------------------------------------------------
# Bands: split-conformal per h (learner) + sparse P(sale)/ladder bands
# ---------------------------------------------------------------------------


def _bands(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    test: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    cells: dict[str, Any],
) -> dict[str, Any]:
    """Per-horizon bands on the test origins.

    Learner rows (smooth/erratic): ±q80 split-conformal width per h,
    calibrated on the selection origins' p50 residuals, zero-clipped and
    sorted. Sparse rows (routed): band [0, q90 of the training history] plus
    P(any sale) and a quantile ladder — it cannot collapse to zero width.
    Returns the per-h coverage/width table (metrics) plus the probabilistic.json
    block (keyed "json").
    """
    # conformal widths per h from selection-origin p50 residuals (learner rows)
    widths: dict[int, float] = {}
    for h in horizons:
        res: list[np.ndarray] = []
        for o in selection:
            sc = by_origin[o]
            j = horizons.index(h)
            res.append(units[o + h][~sparse] - sc.quantiles[0.5][~sparse, j])
        widths[h] = float(np.quantile(np.abs(np.concatenate(res)), TARGET_COVERAGE))

    units.shape[1]
    per_h: dict[int, dict[str, Any]] = {}
    sparse_band: dict[str, Any] = {}
    for h in horizons:
        mask = cells["h"] == h
        y = cells["y"][mask]
        lo = np.empty(mask.sum())
        hi = np.empty(mask.sum())
        # learner rows: p50 ± width, zero-clipped (sorting is then automatic)
        p50 = cells["p50"][mask]
        w = widths[h]
        lo[:] = np.clip(p50 - w, 0.0, None)
        hi[:] = p50 + w
        # sparse rows: [0, q90 of the training history up to the origin]
        sparse_rows = np.flatnonzero(cells["sparse"][mask])
        for r in sparse_rows:
            i = int(cells["series"][mask][r])
            o = int(cells["origin"][mask][r])
            hist = units[: o + 1, i]
            lo[r] = 0.0
            hi[r] = float(np.quantile(hist, TARGET_COVERAGE))
        covered = (y >= lo) & (y <= hi)
        per_h[h] = {
            "coverage": float(covered.mean()),
            "avg_width": float((hi - lo).mean()),
            "calibration_verdict": calibration_verdict(float(covered.mean()), TARGET_COVERAGE),
            "learner_coverage": float(covered[~cells["sparse"][mask]].mean())
            if (~cells["sparse"][mask]).any()
            else float("nan"),
            "sparse_coverage": float(covered[cells["sparse"][mask]].mean())
            if cells["sparse"][mask].any()
            else float("nan"),
        }

    # pinball loss of the learner quantiles per h (on learner rows)
    pinball: dict[int, dict[str, float]] = {}
    for h in horizons:
        mask = (cells["h"] == h) & (~cells["sparse"])
        pinball[h] = {
            f"pinball_p{int(q * 100)}": pinball_loss(
                cells["y"][mask], cells[f"p{int(q * 100)}"][mask], q
            )
            for q in QUANTILES_MS
        }

    # sparse band summary from the LAST test origin (dataset-level flavour)
    last_o = max(test)
    sparse_band = {
        "definition": (
            "P(any sale) = share of non-zero demand days in the training history "
            "up to the origin; quantile ladder over the same history"
        ),
        "ladder_levels": list(LADDER_LEVELS),
        "series": {
            str(i): {
                "p_sale": float(np.mean(units[: last_o + 1, i] > 0)),
                "ladder": [
                    float(np.quantile(units[: last_o + 1, i], lvl)) for lvl in LADDER_LEVELS
                ],
            }
            for i in np.flatnonzero(sparse)
        },
    }

    # bands for the peak-capable candidates: conformal width per h from the
    # selection-origin residuals around the candidate's own point forecast
    # (zero-clipped and sorted — clipping floors at 0, so sorting is
    # automatic); sparse rows honestly keep the P(sale)+ladder band as today.
    candidate_bands: dict[str, Any] = {}
    for cand in ML_SPARSE:
        cand_widths: dict[int, float] = {}
        for h in horizons:
            j = horizons.index(h)
            res_c = np.concatenate(
                [units[o + h] - by_origin[o].preds[cand][:, j] for o in selection]
            )
            cand_widths[h] = float(np.quantile(np.abs(res_c), TARGET_COVERAGE))
        cand_per_h: dict[int, dict[str, Any]] = {}
        for h in horizons:
            mask = cells["h"] == h
            y = cells["y"][mask]
            lo_c = np.clip(cells["pred"][cand][mask] - cand_widths[h], 0.0, None)
            hi_c = cells["pred"][cand][mask] + cand_widths[h]
            sparse_rows = np.flatnonzero(cells["sparse"][mask])
            for r in sparse_rows:
                i = int(cells["series"][mask][r])
                o = int(cells["origin"][mask][r])
                lo_c[r] = 0.0
                hi_c[r] = float(np.quantile(units[: o + 1, i], TARGET_COVERAGE))
            covered_c = (y >= lo_c) & (y <= hi_c)
            cand_per_h[h] = {
                "coverage": float(covered_c.mean()),
                "avg_width": float((hi_c - lo_c).mean()),
                "calibration_verdict": calibration_verdict(
                    float(covered_c.mean()), TARGET_COVERAGE
                ),
            }
        candidate_bands[cand] = {
            "band_type": "point ± q80 split-conformal width per horizon, calibrated on the "
            "selection origins, zero-clipped and sorted; sparse rows carry the P(sale)+"
            "quantile-ladder history band instead",
            "conformal_widths_by_h": {str(h): cand_widths[h] for h in horizons},
            "per_horizon": {str(h): cand_per_h[h] for h in horizons},
            "pooled_coverage": float(np.mean([cand_per_h[h]["coverage"] for h in horizons])),
            "pooled_verdict": calibration_verdict(
                float(np.mean([cand_per_h[h]["coverage"] for h in horizons])), TARGET_COVERAGE
            ),
        }

    pooled_cov = float(np.mean([per_h[h]["coverage"] for h in horizons]))
    block = {
        "protocol": PROTOCOL,
        "target_coverage": TARGET_COVERAGE,
        "calibration_tolerance": CALIBRATION_TOL,
        "band_types": {
            "learner": "p50 ± q80 split-conformal width per horizon, calibrated on the "
            "selection origins, zero-clipped and sorted",
            "sparse": "P(any sale) + quantile ladder of the training history (no collapsing band)",
            "candidate": "peak-capable candidates (hgb_tweedie / hurdle_hgb): point ± q80 "
            "split-conformal width per horizon around the candidate's own point forecast, "
            "zero-clipped and sorted; sparse rows keep the P(sale)+ladder band",
        },
        "conformal_widths_by_h": {str(h): widths[h] for h in horizons},
        "per_horizon": {str(h): {**per_h[h], **pinball[h]} for h in horizons},
        "candidate_bands": candidate_bands,
        "pooled_coverage": pooled_cov,
        "pooled_verdict": calibration_verdict(pooled_cov, TARGET_COVERAGE),
        "sparse_band": sparse_band,
        "verdict_rule": "|coverage - target| <= 0.05 -> calibrated; above target -> "
        "conservative; below -> optimistic (per horizon and pooled)",
    }
    return {"per_h": per_h, "widths": widths, "json": block}


# ---------------------------------------------------------------------------
# Paired bootstrap suite
# ---------------------------------------------------------------------------


def _bootstrap_suite(
    cells: dict[str, Any], horizons: list[int], config: ForecastConfig
) -> dict[str, Any]:
    """95% cluster-bootstrap CIs on every headline comparison.

    Unit = (series x scored test origins): series are resampled with
    replacement, one shared draw per replication so differences stay paired.
    """
    seed = config.seed + 2002  # distinct stream from every other consumer
    classes = [str(c) for c in np.unique(cells["class"])]

    def _pair(mask: np.ndarray, a: str, b: str) -> dict[str, Any]:
        return _paired_bootstrap_mae(
            cells["pred"][a][mask] - cells["y"][mask],
            cells["pred"][b][mask] - cells["y"][mask],
            cells["series"][mask],
            config.bootstrap_reps,
            seed,
        )

    per_class: dict[str, Any] = {}
    for cls in classes:
        cls_mask = cells["class"] == cls
        entry: dict[str, Any] = {}
        for h in (7, 14):
            if h not in horizons:
                continue
            mask = cls_mask & (cells["h"] == h)
            if not mask.any():
                continue
            h_entry: dict[str, Any] = {
                "champion_mae": float(
                    np.abs(cells["pred"][CHAMPION][mask] - cells["y"][mask]).mean()
                ),
                "floor_mae": float(np.abs(cells["pred"][FLOOR][mask] - cells["y"][mask]).mean()),
                "champion_vs_floor": _pair(mask, CHAMPION, FLOOR),
                "champion_vs_naive_zero": _pair(mask, CHAMPION, NAIVE),
            }
            # peak-capable candidates vs the routed pipeline and the zero floor
            for cand in COMPARISON_CANDIDATES:
                h_entry[f"{cand}_mae"] = float(
                    np.abs(cells["pred"][cand][mask] - cells["y"][mask]).mean()
                )
                h_entry[f"{cand}_vs_routed"] = _pair(mask, cand, CHAMPION)
                h_entry[f"{cand}_vs_zero"] = _pair(mask, cand, NAIVE)
            entry[f"h{h}"] = h_entry
        # routing before/after: all-HGB (unrouted) vs routed champion, all h
        entry["routing"] = _pair(cls_mask, "direct_hgb", CHAMPION)
        entry["n_series"] = len(np.unique(cells["series"][cls_mask]))
        per_class[cls] = entry

    # model ranks pooled over test origins and all horizons (with rank gaps)
    overall_mae = {
        name: float(np.abs(cells["pred"][name] - cells["y"]).mean()) for name in CANDIDATES
    }
    ranked = sorted(CANDIDATES, key=lambda n: overall_mae[n])
    rank_gaps: list[dict[str, Any]] = []
    for rank, name in enumerate(ranked[:5], start=1):
        gap: dict[str, Any] = {"rank": rank, "model": name, "mae": overall_mae[name]}
        if rank < len(ranked):
            nxt = ranked[rank]
            gap["gap_to_next"] = {
                "model": nxt,
                **_paired_bootstrap_mae(
                    cells["pred"][name] - cells["y"],
                    cells["pred"][nxt] - cells["y"],
                    cells["series"],
                    config.bootstrap_reps,
                    seed,
                ),
            }
        rank_gaps.append(gap)

    return {
        "method": "paired cluster bootstrap (series resampled with replacement, one shared "
        "draw per replication), percentile 95% CI over series x scored test origins",
        "unit": "series cluster x scored test origins",
        "n_boot": config.bootstrap_reps,
        "seed": seed,
        "per_class": per_class,
        "rank_gaps": rank_gaps,
    }


# ---------------------------------------------------------------------------
# Horizon growth curves
# ---------------------------------------------------------------------------


def _growth_curves(cells: dict[str, Any], horizons: list[int]) -> dict[str, Any]:
    """Pooled MAE by TRUE horizon for the champion, the floor and zero."""
    curves: dict[str, Any] = {"pooled": {}, "per_class": {}}
    for name in (CHAMPION, FLOOR, NAIVE):
        curves["pooled"][name] = {
            str(h): float(
                np.abs(cells["pred"][name][cells["h"] == h] - cells["y"][cells["h"] == h]).mean()
            )
            for h in horizons
        }
    for cls in np.unique(cells["class"]):
        cls_mask = cells["class"] == cls
        curves["per_class"][str(cls)] = {
            name: {
                str(h): float(
                    np.abs(
                        cells["pred"][name][cls_mask & (cells["h"] == h)]
                        - cells["y"][cls_mask & (cells["h"] == h)]
                    ).mean()
                )
                for h in horizons
            }
            for name in (CHAMPION, FLOOR)
        }
    return curves


# ---------------------------------------------------------------------------
# Candidate comparison (pooled over horizons, per class)
# ---------------------------------------------------------------------------


def _candidate_comparison(cells: dict[str, Any], config: ForecastConfig) -> dict[str, Any]:
    """Pooled-over-h MAE of the peak-capable candidates vs the routed/zero
    baselines, per class, with paired cluster-bootstrap CIs on every gap."""
    seed = config.seed + 6402  # distinct bootstrap stream
    classes = [str(c) for c in np.unique(cells["class"])]
    per_class: dict[str, Any] = {}
    for cls in classes:
        mask = cells["class"] == cls
        entry: dict[str, Any] = {
            "routed_mae": float(np.abs(cells["pred"][CHAMPION][mask] - cells["y"][mask]).mean()),
            "zero_mae": float(np.abs(cells["pred"][NAIVE][mask] - cells["y"][mask]).mean()),
        }
        for cand in COMPARISON_CANDIDATES:
            item: dict[str, Any] = {
                "mae": float(np.abs(cells["pred"][cand][mask] - cells["y"][mask]).mean())
            }
            for base_name, base in (("routed", CHAMPION), ("zero", NAIVE)):
                item[f"vs_{base_name}"] = _paired_bootstrap_mae(
                    cells["pred"][cand][mask] - cells["y"][mask],
                    cells["pred"][base][mask] - cells["y"][mask],
                    cells["series"][mask],
                    config.bootstrap_reps,
                    seed,
                )
            entry[cand] = item
        per_class[cls] = entry
    return {
        "method": "pooled MAE over series x scored test origins x all horizons; gaps carry "
        "a 95% paired cluster bootstrap CI over series (negative diff = candidate better)",
        "candidates": list(COMPARISON_CANDIDATES),
        "n_boot": config.bootstrap_reps,
        "seed": seed,
        "per_class": per_class,
    }


# ---------------------------------------------------------------------------
# Wave-22 relative-error blocks: rmae + per-candidate rmsse (per class/pooled)
# ---------------------------------------------------------------------------


def _rmae_block(cells: dict[str, Any]) -> dict[str, Any]:
    """Relative MAE (candidate pooled MAE / seasonal_naive floor pooled MAE)
    for every candidate, pooled and per demand class. The floor itself sits at
    1.0 by construction; this is the headline ratio the claim quotes."""
    full = np.ones(cells["y"].shape[0], dtype=bool)
    classes = [str(c) for c in np.unique(cells["class"])]
    return {
        "definition": "rmae = candidate pooled MAE / seasonal_naive floor pooled MAE over "
        "the same scored cells; < 1 = beats the floor (the floor's rmae is 1.0 "
        "by construction)",
        "pooled": {name: _rmae_cells(cells, full, name) for name in CANDIDATES},
        "per_class": {
            cls: {name: _rmae_cells(cells, cells["class"] == cls, name) for name in CANDIDATES}
            for cls in classes
        },
    }


def _rmsse_block(cells: dict[str, Any]) -> dict[str, Any]:
    """Per-candidate RMSSE (M5 convention, see :func:`_rmsse_cells`), pooled
    and per demand class, with the volume-weighted variant alongside."""

    def _entry(mask: np.ndarray, name: str) -> dict[str, float]:
        r, wr = _rmsse_cells(cells, mask, name)
        return {"rmsse": r, "wrmsse": wr}

    full = np.ones(cells["y"].shape[0], dtype=bool)
    classes = [str(c) for c in np.unique(cells["class"])]
    return {
        "definition": "M5-style RMSSE per (series x scored origin) unit: numerator = MSE of "
        "the candidate over the unit's scored horizon days, denominator = in-sample MSE of "
        "the one-step seasonal-naive-7 over the unit's training window; averaged over units "
        "(zero-scale units excluded); wrmsse weights by training-window volume",
        "pooled": {name: _entry(full, name) for name in CANDIDATES},
        "per_class": {
            cls: {name: _entry(cells["class"] == cls, name) for name in CANDIDATES}
            for cls in classes
        },
    }


# ---------------------------------------------------------------------------
# Decision metric: order-up-to policy simulation
# ---------------------------------------------------------------------------


def _routed_pred(sc: OriginScore, j: int, sparse: np.ndarray, method_of: np.ndarray) -> np.ndarray:
    del sparse  # eligibility is encoded in method_of by _route
    out = sc.preds["direct_hgb"][:, j].copy()
    for name in (*STATISTICAL_METHODS, *ML_SPARSE):
        mask = method_of == name
        out[mask] = sc.preds[name][mask, j]
    return out


def _policy_residuals(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    h: int,
    class_mask: np.ndarray,
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    policy: str,
) -> np.ndarray:
    """Selection-origin residuals (actual - forecast) for one policy, one class.

    The class mask is per SERIES; residuals are pooled over selection origins.
    """
    j = horizons.index(h)
    res: list[np.ndarray] = []
    for o in selection:
        sc = by_origin[o]
        if policy == "champion":
            pred = _routed_pred(sc, j, sparse, method_of)
        else:
            pred = sc.preds["seasonal_naive"][:, j]
        res.append((units[o + h] - pred)[class_mask])
    return np.concatenate(res)


def _newsvendor(
    dates: np.ndarray,
    cells: dict[str, Any],
    units: np.ndarray,
    sparse: np.ndarray,
    config: ForecastConfig,
) -> dict[str, Any]:
    """Newsvendor order-quantile cost layer (wave 22, additive in the decision
    block; documented cost assumptions — NOT a measured saving).

    For each service level q in ``config.service_levels`` and each scored
    cell (series x test origin x horizon day):

    - **routed policy order** — the routed band's q-quantile. Dense rows:
      linear interpolation of the committed p10/p50/p90 learner band ladder
      (extrapolation above p90 with the p50→p90 slope, zero-clipped — see
      :func:`_ladder_quantile`). Sparse rows: the q-quantile of the training
      history up to the origin (the existing sparse ladder machinery; the
      P(sale) summary stays in the bands block).
    - **floor policy order** — the q-quantile of the seasonal-naive empirical
      distribution: the training-window demand observed on the target day's
      weekday (0 when the weekday never occurred in the window).
    - **cost per cell** — holding 1.0 per ordered-but-unsold unit + stockout
      3.0 per unmet unit (per day, assumption).

    Reported per demand class as expected daily cost per unit-demand (total
    cost / total demand) for the routed vs the floor policy, with a paired
    cluster bootstrap CI on the difference (series resampled with
    replacement, one shared draw per replication).
    """
    dows = np.array([d.weekday() for d in dates.astype("datetime64[D]").astype(object)])
    out: dict[str, Any] = {
        "simulation": True,
        "label": "newsvendor order-quantile cost — documented cost assumptions, no savings claims",
        "cost_assumptions": {
            "holding_cost_per_unit_ordered_unsold_per_day": NEWSVENDOR_HOLDING_COST,
            "stockout_cost_per_unit_short_per_day": NEWSVENDOR_STOCKOUT_COST,
            "cost_basis": "per scored cell (series x test origin x horizon day); "
            "assumption, not measured",
        },
        "order_definition": {
            "routed_dense": "q-quantile of the committed p10/p50/p90 learner band ladder "
            "(linear interpolation; linear extrapolation above p90), zero-clipped",
            "routed_sparse": "q-quantile of the training history up to the origin (the "
            "existing sparse ladder machinery)",
            "floor": "q-quantile of the seasonal-naive empirical distribution: the "
            "training-window demand on the target day's weekday",
        },
        "service_levels": [float(q) for q in config.service_levels],
        "per_class": {},
    }
    for cls in [str(c) for c in np.unique(cells["class"])]:
        mask = cells["class"] == cls
        idx = np.flatnonzero(mask)
        ser = cells["series"][idx]
        org = cells["origin"][idx]
        h_of = cells["h"][idx]
        y = cells["y"][idx]
        per_q: dict[str, Any] = {}
        for q in config.service_levels:
            # routed orders: dense rows interpolate the band ladder; sparse
            # rows read the history ladder (one quantile per series x origin)
            order_r = np.empty(idx.size)
            dense_rows = ~sparse[ser]
            order_r[dense_rows] = _ladder_quantile(
                q,
                cells["p10"][idx[dense_rows]],
                cells["p50"][idx[dense_rows]],
                cells["p90"][idx[dense_rows]],
            )
            for k in np.flatnonzero(~dense_rows):
                order_r[k] = float(np.quantile(units[: int(org[k]) + 1, int(ser[k])], q))
            # floor orders: weekday-filtered training history quantile
            order_f = np.empty(idx.size)
            for r in range(idx.size):
                o = int(org[r])
                hist = units[: o + 1, int(ser[r])]
                same_dow = hist[dows[: o + 1] == dows[o + int(h_of[r])]]
                order_f[r] = float(np.quantile(same_dow, q)) if same_dow.size else 0.0
            cost_r = NEWSVENDOR_HOLDING_COST * np.maximum(order_r - y, 0.0) + (
                NEWSVENDOR_STOCKOUT_COST * np.maximum(y - order_r, 0.0)
            )
            cost_f = NEWSVENDOR_HOLDING_COST * np.maximum(order_f - y, 0.0) + (
                NEWSVENDOR_STOCKOUT_COST * np.maximum(y - order_f, 0.0)
            )
            denom = float(y.sum())
            per_q[f"q_{q:.2f}"] = {
                "routed_cost_per_unit_demand": float(cost_r.sum() / denom)
                if denom > 0
                else float("nan"),
                "floor_cost_per_unit_demand": float(cost_f.sum() / denom)
                if denom > 0
                else float("nan"),
                "routed_minus_floor": _paired_bootstrap_cost(
                    cost_r, cost_f, y, ser, config.bootstrap_reps, config.seed + 9602
                ),
            }
        out["per_class"][cls] = per_q
    return out


def _order_up_to(
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    cells: dict[str, Any],
    class_of_series: np.ndarray,
    config: ForecastConfig,
    dates: np.ndarray,
) -> dict[str, Any]:
    """Order-up-to policy evaluation (simulation — no savings claims).

    Per series, service level τ: the order for (origin, h) is the τ-quantile
    of the policy's forecast distribution, approximated as
    ``point + q_τ(residuals)`` with residuals calibrated per (class, h) on the
    SELECTION origins. Cost per cell: ``holding · max(order - actual, 0) +
    stockout · max(actual - order, 0)``, summed over the scored test cells.
    Champion (routed) policy vs seasonal-naive policy, per demand class.
    """
    classes = [str(c) for c in np.unique(cells["class"])]
    out: dict[str, Any] = {
        "simulation": True,
        "label": "order-up-to policy simulation — cost assumptions documented, no savings claims",
        "cost_assumptions": {
            "holding_cost_per_unit": config.holding_cost,
            "stockout_cost_per_unit_short": config.stockout_cost,
            "cost_basis": "per scored cell (series x test origin x horizon)",
        },
        "service_levels": list(config.service_levels),
        "per_class": {},
    }
    for cls in classes:
        class_mask = class_of_series == cls  # per-series mask
        per_tau: dict[str, Any] = {}
        for tau in config.service_levels:
            totals: dict[str, float] = {}
            for policy in ("champion", "floor"):
                cost = 0.0
                demand = 0.0
                pred_key = CHAMPION if policy == "champion" else FLOOR
                for h in horizons:
                    cell_mask = (cells["h"] == h) & (cells["class"] == cls)
                    pred = cells["pred"][pred_key][cell_mask]
                    res = _policy_residuals(
                        by_origin,
                        selection,
                        horizons,
                        h,
                        class_mask,
                        units,
                        sparse,
                        method_of,
                        policy,
                    )
                    q_tau = float(np.quantile(res, tau))
                    order = np.maximum(pred + q_tau, 0.0)
                    y = cells["y"][cell_mask]
                    cost += order_up_to_cost(order, y, config.holding_cost, config.stockout_cost)
                    demand += float(y.sum())
                totals[policy] = cost
                totals[f"{policy}_per_unit_demand"] = cost / demand if demand > 0 else float("nan")
            per_tau[f"tau_{tau:.2f}"] = {
                **totals,
                "delta_champion_minus_floor": totals["champion"] - totals["floor"],
            }
        out["per_class"][cls] = per_tau
    # wave 22: the newsvendor order-quantile layer, additive over the
    # order-up-to simulation above (different order rule, documented costs)
    out["newsvendor"] = _newsvendor(dates, cells, units, sparse, config)
    return out


# ---------------------------------------------------------------------------
# Block assembly
# ---------------------------------------------------------------------------


def _assemble_block(
    dates: np.ndarray,
    origins: list[int],
    selection: list[int],
    test: list[int],
    horizons: list[int],
    classes: dict[str, dict[str, Any]],
    sparse: np.ndarray,
    method_of: np.ndarray,
    per_horizon: dict[int, dict[str, Any]],
    bands: dict[str, Any],
    bootstrap: dict[str, Any],
    growth: dict[str, Any],
    decision: dict[str, Any],
    cells: dict[str, Any],
    series_ids: list[str],
    config: ForecastConfig,
    correction: dict[str, Any],
    peak: dict[str, Any],
    win_rates: dict[str, Any],
    pw_choice: dict[str, Any],
    ens: dict[str, Any],
) -> dict[str, Any]:
    """The ``_multistep`` block of metrics.json (multi-step headline)."""
    del bands  # band numbers live in probabilistic.json (merged separately)
    counts = {
        cls: int(sum(1 for s in series_ids if classes[s]["class"] == cls))
        for cls in ("smooth", "erratic", "intermittent", "lumpy")
    }
    headline: dict[str, Any] = {}
    for cls, entry in bootstrap["per_class"].items():
        headline[cls] = {key: value for key, value in entry.items() if key.startswith("h")}
        headline[cls]["n_series"] = entry["n_series"]
    routing_choices = {sid: str(method_of[i]) for i, sid in enumerate(series_ids)}
    overall = {name: float(np.abs(cells["pred"][name] - cells["y"]).mean()) for name in CANDIDATES}
    rmae = _rmae_block(cells)
    champ_mae = overall[CHAMPION]
    headline_claim = (
        f"champion '{CHAMPION}' pooled test MAE {champ_mae:.2f} vs floor '{FLOOR}' "
        f"{overall[FLOOR]:.2f} — rmae {rmae['pooled'][CHAMPION]:.3f} "
        "(relative MAE vs the seasonal-naive floor; < 1 beats the floor)"
    )
    return {
        "protocol": PROTOCOL,
        "track_note": (
            "PRIMARY multi-step headline. The per-model blocks above are the retained "
            "frozen nowcast (one-day-ahead) track, rolling_origin_holdout_v1 — valid but "
            "never mixed into the multi-step leaderboard. Each multi-step row is a TRUE "
            "horizon-h forecast issued at the origin (no actual within h days of the "
            "target is referenced)."
        ),
        "horizons": horizons,
        "window_days": config.multistep_window_days,
        "candidates": list(CANDIDATES),
        "champion": CHAMPION,
        "champion_definition": "per-series routing: sparse (ADI>=1.32) series -> best candidate "
        "among the statistical methods (zero/seasonal_naive/Croston/SBA/TSB + the wave-22 "
        "ma_28/ADIDA pair) + the six peak-capable ML candidates on the selection origins; "
        "smooth/erratic -> best among direct_hgb + the same ML pool",
        "floor": FLOOR,
        "naive": NAIVE,
        "peak_capable_candidates": {
            "hgb_tweedie": "HGBRegressor with the compound-Poisson tweedie deviance "
            "(variance power 1.5); lr/depth/leaves tuned on the selection origins via a "
            "seeded capped Optuna study (hpo.tune_multistep_tweedie)",
            "hurdle_hgb": "per-h two-stage HGB: log-loss classifier for P(sale) + HGB on "
            "log1p(non-zero sizes); point = p_hat x (exp(y_reg) - 1), zero-corrected on the "
            "selection origins (identity / scalar / isotonic — whichever wins there)",
            "lgbm_tweedie": "global LightGBM with the tweedie objective (variance power "
            "1.5), series identity as hi/lo categoricals; lr/leaves/min_child_samples tuned "
            "on the selection origins via a seeded capped Optuna study (hpo.tune_multistep_lgbm)",
            "lgbm_poisson": "global LightGBM with the poisson count objective — same "
            "features, same tuning contract as lgbm_tweedie",
            "hurdle_lgbm": "the two-stage hurdle on LightGBM halves (classifier x "
            "log1p-size regressor), same raw point math and the same selection-origin "
            "zero-correction as hurdle_hgb",
            "peak_weighted_hgb": "the HGB hurdle pair fit with sample weights 2-3 on each "
            "series' top-decile demand days; the weight is chosen on the selection origins, "
            "then the same zero-correction applies",
            "ensemble_convex": "per-series convex blend w x routed + (1 - w) x best_ml "
            "(w in {0, 0.1, ..., 1}, best_ml = the per-series best ML candidate, both "
            "chosen on the selection origins; no refits)",
        },
        "post_processing_candidates": {
            "routed_reconciled": "hierarchy anchoring of the routed forecast (comparison-"
            "only, never in the routing pool): per country block the anchor is the "
            "seasonal-naive forecast of the country's aggregated demand on the target day; "
            "the discrepancy is allocated to member series proportionally to their routed "
            "forecast (fallback: training-window means; then no adjustment)"
        },
        "origins": {
            "n_origins": len(origins),
            "dates": [str(dates[o])[:10] for o in origins],
            "selection_dates": [str(dates[o])[:10] for o in selection],
            "test_dates": [str(dates[o])[:10] for o in test],
            "spacing_days": ORIGIN_SPACING_DAYS,
            "min_train_dates": config.min_train_size,
            "gap_days": 0,
            "cap_note": (
                f"weekly origins, capped at {config.multistep_n_origins} by dropping the "
                "oldest (exact weekly cadence kept) for runtime; the window starts the day "
                "AFTER the origin (no embargo gap)"
            ),
        },
        "demand_classes": {
            "method": "Syntetos-Boylan quadrants on ADI and CV^2 over the full panel",
            "thresholds": {"adi": ADI_THRESHOLD, "cv2": CV2_THRESHOLD},
            "counts": counts,
            "n_series": len(series_ids),
            "sparse_share": float(sparse.mean()),
            "series": {sid: classes[sid]["class"] for sid in series_ids},
        },
        "routing": {
            "rule": "per-series routing on the selection origins ONLY: sparse (ADI >= 1.32) "
            "series choose among zero/seasonal_naive/Croston/SBA/TSB/ma_28/adida_sba/"
            "adida_tsb plus the six peak-capable ML candidates; smooth/erratic series "
            "choose among direct_hgb plus the same ML pool",
            "method_choices": routing_choices,
            "pool_sparse": list((*STATISTICAL_METHODS, *ML_SPARSE)),
            "pool_dense": list(("direct_hgb", *ML_SPARSE)),
            "hurdle_correction": correction,
            "peak_weight_choice": pw_choice,
            "ensemble": {
                k: v
                for k, v in ens.items()
                if k not in ("ml_choice", "weights")  # numpy arrays, not JSON-safe
            },
            "per_class": {cls: entry["routing"] for cls, entry in bootstrap["per_class"].items()},
        },
        "headline_per_class": headline,
        "candidate_comparison": _candidate_comparison(cells, config),
        "peak_capture": peak,
        "win_rates": win_rates,
        "per_horizon": {str(h): per_horizon[h] for h in horizons},
        "horizon_growth": growth,
        "overall_mae_test": overall,
        "headline_claim": headline_claim,
        "rmae": rmae,
        "rmsse": _rmsse_block(cells),
        "bootstrap": {
            "method": bootstrap["method"],
            "unit": bootstrap["unit"],
            "n_boot": bootstrap["n_boot"],
            "seed": bootstrap["seed"],
            "rank_gaps": bootstrap["rank_gaps"],
        },
        "decision_metric": decision,
    }


def _metadata_block(block: dict[str, Any], config: ForecastConfig) -> dict[str, Any]:
    """The ``multi_horizon`` block of evaluation_metadata.json (protocol v2)."""
    origins = block["origins"]
    return {
        "protocol": PROTOCOL,
        "track": "multi_step (primary); the top-level rolling_origin_holdout_v1 keys "
        "describe the retained frozen nowcast track",
        "horizons": block["horizons"],
        "window_days": block["window_days"],
        "origins": origins,
        "holdout_designation": (
            f"last {config.multistep_test_origins} origins = test (scored once); the "
            "earlier origins select (routing + conformal calibration) only"
        ),
        "selection_rule": "per-series routing method = lowest summed |error| over the "
        "selection origins: sparse series among zero/seasonal_naive/Croston/SBA/TSB/"
        "ma_28/adida_sba/adida_tsb plus the six ML candidates (direct_hgb ineligible — "
        "the wave-19 sparse finding); smooth/erratic series among direct_hgb plus the "
        "same ML pool; the convex-ensemble weight and the peak-weighted hurdle's sample "
        "weight are chosen on the same selection origins; never reads test actuals "
        "(property-tested by shuffling the test origins' actuals)",
        "feature_semantics": "direct per-horizon models: calendar of the target date (incl. "
        "is_month_end / week_of_month, the wholesale trading-cycle hypothesis) + peak block "
        "at target-h (rolling mean/max over 7/14/28d windows ending at target-h, "
        "days-since-last-nonzero, 28d non-zero-day count, 28d peak ratio) + price block at "
        "target-h (price_asof, price_ratio_28d, days_since_price_change, price_drop — the "
        "B2B promo proxy; neutral constants when the panel has no price column) + rolling "
        "block at target-h (wave 22: rmean7/rmean14/rmean28, rstd14/rstd28 — rolling "
        "means/stds of demand over windows ending at target-h) + lags "
        "lag_h, lag_{h+7}, lag_{h+14} (every demand/price feature >= h days old relative "
        "to the target — no actual within h days of the target is referenced, taint-tested "
        "for units AND price); training rows use targets <= the origin only",
        "uncertainty": "per-horizon split-conformal (learner rows and the peak-capable "
        "candidates' own point forecasts) and P(sale)+quantile ladder (sparse rows), both "
        "calibrated on selection origins",
        "metric_definitions": {
            "mae": "mean |actual - forecast| over series x scored test origins at horizon h",
            "mase": "pooled |err| / pooled per-series in-sample seasonal-naive-7 scale "
            "(zero-scale rows excluded); 1.0 is the scale's in-sample error level, "
            "NOT the naive's own holdout error — the naive's MASE can differ from "
            "1.0 on a scored window",
            "rmae": "candidate pooled MAE / seasonal_naive floor pooled MAE over the same "
            "scored cells; < 1 = beats the floor (the floor sits at 1.0 by construction)",
            "rmsse": "M5-style per (series x scored origin) unit: sqrt(MSE(candidate) / "
            "in-sample MSE of the one-step seasonal-naive-7 on the unit's training window), "
            "averaged over units (zero-scale excluded)",
            "wrmsse": "volume-weighted RMSSE (weights = training-window demand)",
            "bias": "mean(forecast - actual) at horizon h",
            "wape": "sum|err| / sum|actual| at horizon h",
            "pinball_pXX": "mean pinball loss of the learner quantile at level XX",
            "coverage": "share of actuals inside the per-h band on the scored origins",
            "calibration_verdict": "|coverage - target| <= 0.05 -> calibrated; above -> "
            "conservative; below -> optimistic",
            "peak_mae": "per scored window (series x test origin), MAE on the window's "
            "top-decile-by-actual days of the scored h-lattice; pooled per class as the "
            "mean over windows",
            "peak_recall": "per scored window, the share of the window's top-5 actual days "
            "whose day ranks in the forecast's own top-5; pooled per class as the mean "
            "over windows",
            "win_rate": "per class and horizon: the share of series whose summed |error| "
            "over the scored test origins at that h is strictly below the seasonal_naive "
            "floor's; 95% CI = cluster bootstrap over series (one shared index draw per "
            "replication across candidates)",
            "newsvendor_cost": "decision layer (documented assumption, not a measured "
            "saving): order = the routed band's q-quantile (dense rows interpolate the "
            "committed p10/p50/p90 ladder; sparse rows read the training-history ladder; "
            "the floor reads the same quantile of the seasonal-naive empirical "
            "distribution = training demand on the target's weekday); cost = 1.0 x "
            "ordered-but-unsold + 3.0 x unmet per unit per day; reported per class as "
            "expected daily cost per unit-demand with a paired cluster-bootstrap CI",
        },
        "candidates": list(CANDIDATES),
    }


# ---------------------------------------------------------------------------
# Figures (unit-incompatible metrics never share an axis)
# ---------------------------------------------------------------------------


def _peak_day_pairs(
    cells: dict[str, Any],
    test: list[int],
    horizons: list[int],
    n_series: int,
    candidate: str,
    max_points: int = 1500,
) -> tuple[np.ndarray, np.ndarray]:
    """(peak-day actual, forecast) pairs for one candidate on its windows'
    top-decile days — the scatter data behind multistep_peak_day_scatter."""
    n_o, n_h = len(test), len(horizons)
    y3 = cells["y"].reshape(n_o, n_h, n_series)
    pred3 = cells["pred"][candidate].reshape(n_o, n_h, n_series)
    k = max(1, math.ceil(0.1 * n_h))
    top_k = np.argsort(y3, axis=1)[:, ::-1][:, :k, :]
    arange_o = np.arange(n_o)[:, None, None]
    arange_s = np.arange(n_series)[None, None, :]
    actual = y3[arange_o, top_k, arange_s].reshape(-1)
    pred = pred3[arange_o, top_k, arange_s].reshape(-1)
    if actual.size > max_points:  # deterministic subsample for the JSON size
        step = int(np.ceil(actual.size / max_points))
        actual, pred = actual[::step], pred[::step]
    return actual, pred


def _figures(
    block: dict[str, Any],
    horizons: list[int],
    prob_block: dict[str, Any],
    cells: dict[str, Any],
    test: list[int],
    n_series: int,
) -> dict[str, go.Figure]:
    """The four multi-step figures (unit-incompatible metrics on separate axes)."""
    growth = block["horizon_growth"]["pooled"]
    per_class = block["headline_per_class"]
    hs = [str(h) for h in horizons]

    # (1) error vs horizon: MAE (units) and MASE (unitless) on SEPARATE panels.
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("MAE by true horizon (units)", "MASE by true horizon"),
    )
    for name in (CHAMPION, FLOOR, NAIVE):
        fig.add_scatter(
            x=hs, y=list(growth[name].values()), name=name, mode="lines+markers", row=1, col=1
        )
    for name, key in ((CHAMPION, "champion"), (FLOOR, "floor")):
        fig.add_scatter(
            x=hs,
            y=[block["per_horizon"][str(h)][key]["mase"] for h in horizons],
            name=f"{name} (MASE)",
            mode="lines+markers",
            row=1,
            col=2,
        )
    fig.update_layout(title="Multi-step error vs horizon — champion vs floor vs zero")
    add_takeaway(
        fig,
        "direct per-horizon models on the scored origins — error grows with the true "
        "horizon h now (the old nowcast h-index was chronological rank, not horizon)",
    )
    error_fig = apply_theme(fig)

    # (2) per-class scoreboard: MAE bars (units) + gap-with-CI panel (units).
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "champion vs floor MAE (units)",
            "champion - floor MAE gap with 95% CI (units)",
        ),
    )
    first = {"champion": True, "floor": True}
    for cls in sorted(per_class):
        for h in (7, 14):
            key = f"h{h}"
            if key not in per_class[cls]:
                continue
            e = per_class[cls][key]
            x_pos = f"{cls}<br>h={h}"
            for name, color in (("champion", "#2dd4bf"), ("floor", "#64748b")):
                fig.add_bar(
                    x=[x_pos],
                    y=[e[f"{name}_mae"]],
                    name=name,
                    marker_color=color,
                    legendgroup=name,
                    showlegend=first[name],
                    row=1,
                    col=1,
                )
                first[name] = False
            gap = e["champion_vs_floor"]
            fig.add_scatter(
                x=[x_pos],
                y=[gap["diff"]],
                name="gap",
                mode="markers",
                marker={"color": "#fbbf24", "size": 10},
                error_y={
                    "type": "data",
                    "array": [gap["ci95"][1] - gap["diff"]],
                    "arrayminus": [gap["diff"] - gap["ci95"][0]],
                },
                showlegend=False,
                row=1,
                col=2,
            )
    fig.add_shape(
        type="line",
        xref="x2 domain",
        x0=0,
        x1=1,
        yref="y2",
        y0=0.0,
        y1=0.0,
        line={"dash": "dot", "color": "#fbbf24"},
    )
    fig.update_layout(
        title="Multi-step class scoreboard at h=7/h=14",
        barmode="group",
    )
    add_takeaway(
        fig,
        "right panel: 95% paired cluster bootstrap over series x scored origins — "
        "a gap CI above zero means the champion beats the floor for that class",
    )
    scoreboard_fig = apply_theme(fig)

    # (3) routing: all-HGB minus routed MAE per class (units; positive = helps).
    fig = go.Figure()
    for cls in sorted(block["routing"]["per_class"]):
        r = block["routing"]["per_class"][cls]
        fig.add_bar(
            x=[cls],
            y=[r["diff"]],
            name="unrouted - routed MAE",
            marker_color="#2dd4bf",
            error_y={
                "type": "data",
                "array": [r["ci95"][1] - r["diff"]],
                "arrayminus": [r["diff"] - r["ci95"][0]],
            },
        )
    fig.add_shape(
        type="line",
        xref="paper",
        x0=0,
        x1=1,
        yref="y",
        y0=0.0,
        y1=0.0,
        line={"dash": "dot", "color": "#fbbf24"},
    )
    fig.update_layout(
        title="Routing effect per class — all-HGB MAE minus routed MAE (positive = routing helps)",
        yaxis_title="MAE difference (units)",
    )
    add_takeaway(
        fig,
        "whiskers = 95% paired bootstrap CI over series x scored origins; sparse "
        "classes should sit above zero — boosted trees overfit intermittent series",
    )
    routing_fig = apply_theme(fig)

    # (4) band calibration: coverage per h and width per h on SEPARATE panels.
    per_h = prob_block["per_horizon"]
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            f"empirical coverage per horizon (target {TARGET_COVERAGE:.0%})",
            "average band width per horizon (units)",
        ),
    )
    fig.add_scatter(
        x=hs,
        y=[per_h[str(h)]["coverage"] for h in horizons],
        name="coverage",
        mode="lines+markers",
        row=1,
        col=1,
    )
    fig.add_shape(
        type="line",
        xref="x domain",
        x0=hs[0],
        x1=hs[-1],
        yref="y",
        y0=TARGET_COVERAGE,
        y1=TARGET_COVERAGE,
        line={"dash": "dot", "color": "#fbbf24"},
        row=1,
        col=1,
    )
    fig.add_scatter(
        x=hs,
        y=[per_h[str(h)]["avg_width"] for h in horizons],
        name="avg width",
        mode="lines+markers",
        row=1,
        col=2,
    )
    fig.update_layout(title="Multi-step band calibration per horizon")
    add_takeaway(
        fig,
        f"verdict rule: |coverage - {TARGET_COVERAGE:.0%}| ≤ {CALIBRATION_TOL:.2f} calibrated, "
        "above conservative, below optimistic; sparse rows carry P(sale)+ladder bands",
    )
    band_fig = apply_theme(fig)

    peak_fig = _figure_peak_capture(block)
    candidate_fig = _figure_candidate_comparison(block)
    scatter_fig = _figure_peak_day_scatter(cells, test, horizons, n_series)
    win_fig = _figure_win_rates(block)

    return {
        "multistep_error_vs_horizon": error_fig,
        "multistep_class_scoreboard": scoreboard_fig,
        "multistep_routing": routing_fig,
        "multistep_band_calibration": band_fig,
        "multistep_peak_capture": peak_fig,
        "multistep_candidate_comparison": candidate_fig,
        "multistep_peak_day_scatter": scatter_fig,
        "multistep_win_rates": win_fig,
    }


def _figure_win_rates(block: dict[str, Any]) -> go.Figure:
    """Per-series beats-floor win rates (wave 21 — the "EVERY time series"
    metric): share of series in each class beating the seasonal-naive floor
    per candidate at h=7 and h=14, with the cluster-bootstrap CI whiskers."""
    wr = block["win_rates"]["per_class"]
    classes_sorted = sorted(wr)
    fig = make_subplots(
        rows=len(classes_sorted),
        cols=2,
        subplot_titles=("win rate vs floor at h=7 (share of series)", "at h=14"),
        row_titles=classes_sorted,
    )
    for row, cls in enumerate(classes_sorted, start=1):
        for col, h in enumerate((7, 14), start=1):
            key = str(h)
            if key not in wr[cls]["per_horizon"]:
                continue
            entry = wr[cls]["per_horizon"][key]
            for cand in block["win_rates"]["candidates"]:
                item = entry[cand]
                color = "#2dd4bf" if cand == "routed" else "#64748b"
                fig.add_bar(
                    x=[f"{cls}<br>{cand}"],
                    y=[item["win_rate"]],
                    name=cand,
                    marker_color=color,
                    legendgroup=cand,
                    showlegend=row == 1 and col == 1,
                    row=row,
                    col=col,
                )
                fig.add_scatter(
                    x=[f"{cls}<br>{cand}"],
                    y=[item["win_rate"]],
                    name="95% CI",
                    mode="markers",
                    marker={"color": "#fbbf24", "size": 4},
                    error_y={
                        "type": "data",
                        "array": [item["ci95"][1] - item["win_rate"]],
                        "arrayminus": [item["win_rate"] - item["ci95"][0]],
                    },
                    showlegend=False,
                    row=row,
                    col=col,
                )
    fig.update_layout(
        title="Per-series beats-floor win rate per class (95% cluster-bootstrap CI)",
        barmode="group",
    )
    add_takeaway(
        fig,
        "the 'improve EVERY series' metric: pooled MAE can fall while most series lose — "
        "this panel counts, per class, how many series actually beat the seasonal-naive "
        "floor per candidate and horizon",
    )
    return apply_theme(fig)


def _figure_peak_capture(block: dict[str, Any]) -> go.Figure:
    """Peak capture per class: peak_recall and peak_mae differences vs the
    zero forecast with paired-bootstrap CIs (positive recall diff / negative
    MAE diff = better than zero)."""
    peak = block["peak_capture"]["per_class"]
    classes_sorted = sorted(peak)
    fig = make_subplots(
        rows=len(classes_sorted),
        cols=2,
        subplot_titles=(
            "peak_recall minus zero (share of top-5 peak days ranked top-5)",
            "peak_mae minus zero (units, on top-decile demand days)",
        ),
        row_titles=classes_sorted,
    )
    for row, cls in enumerate(classes_sorted, start=1):
        for col, metric in enumerate(("peak_recall", "peak_mae"), start=1):
            for cand in PEAK_CANDIDATES:
                item = peak[cls][cand]
                comp = item.get(f"{metric}_vs_zero")
                if comp is None:
                    continue
                color = "#2dd4bf" if cand == "routed" else "#64748b"
                fig.add_bar(
                    x=[f"{cls}<br>{cand}"],
                    y=[comp["diff"]],
                    name=cand,
                    marker_color=color,
                    legendgroup=cand,
                    showlegend=row == 1 and col == 1,
                    row=row,
                    col=col,
                )
                fig.add_scatter(
                    x=[f"{cls}<br>{cand}"],
                    y=[comp["diff"]],
                    name="95% CI",
                    mode="markers",
                    marker={"color": "#fbbf24", "size": 4},
                    error_y={
                        "type": "data",
                        "array": [comp["ci95"][1] - comp["diff"]],
                        "arrayminus": [comp["diff"] - comp["ci95"][0]],
                    },
                    showlegend=False,
                    row=row,
                    col=col,
                )
    fig.add_shape(
        type="line",
        xref="paper",
        x0=0,
        x1=1,
        yref="y",
        y0=0.0,
        y1=0.0,
        line={"dash": "dot", "color": "#fbbf24"},
    )
    fig.update_layout(
        title="Peak capture per class — difference vs the zero forecast (95% paired bootstrap CI)",
        barmode="group",
    )
    add_takeaway(
        fig,
        "the user's headline question: do the peak-capable candidates rank the window's "
        "peak days better than the flat zero baseline? recall diff > 0 and MAE diff < 0 "
        "is a win; routed is the committed per-series router",
    )
    return apply_theme(fig)


def _figure_candidate_comparison(block: dict[str, Any]) -> go.Figure:
    """Pooled-over-h MAE per class for every ML/ensemble candidate with the
    gap CI vs the routed pipeline."""
    comp_block = block["candidate_comparison"]["per_class"]
    comp_cands = tuple(block["candidate_comparison"]["candidates"])
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("pooled MAE, all horizons (units)", "candidate minus routed MAE (95% CI)"),
    )
    for cls in sorted(comp_block):
        entry = comp_block[cls]
        x_pos = f"{cls}"
        for name, color in (("routed", "#2dd4bf"), ("zero", "#94a3b8")):
            key = "routed_mae" if name == "routed" else "zero_mae"
            fig.add_bar(
                x=[x_pos],
                y=[entry[key]],
                name=name,
                marker_color=color,
                legendgroup=name,
                showlegend=False,
                row=1,
                col=1,
            )
        for cand in comp_cands:
            fig.add_bar(
                x=[x_pos],
                y=[entry[cand]["mae"]],
                name=cand,
                marker_color="#64748b",
                legendgroup=cand,
                showlegend=False,
                row=1,
                col=1,
            )
            gap = entry[cand]["vs_routed"]
            fig.add_scatter(
                x=[f"{cls}<br>{cand}"],
                y=[gap["diff"]],
                name="gap",
                mode="markers",
                marker={"color": "#fbbf24", "size": 10},
                error_y={
                    "type": "data",
                    "array": [gap["ci95"][1] - gap["diff"]],
                    "arrayminus": [gap["diff"] - gap["ci95"][0]],
                },
                showlegend=False,
                row=1,
                col=2,
            )
    fig.add_shape(
        type="line",
        xref="x2 domain",
        x0=0,
        x1=1,
        yref="y2",
        y0=0.0,
        y1=0.0,
        line={"dash": "dot", "color": "#fbbf24"},
    )
    fig.update_layout(
        title="ML + ensemble candidates vs the routed pipeline — pooled multi-step MAE",
        barmode="group",
    )
    add_takeaway(
        fig,
        "right panel: candidate MAE minus routed MAE with 95% paired bootstrap CIs — "
        "negative means the candidate beats the committed router on pooled MAE",
    )
    return apply_theme(fig)


def _figure_peak_day_scatter(
    cells: dict[str, Any], test: list[int], horizons: list[int], n_series: int
) -> go.Figure:
    """Forecast vs actual on each scored window's top-decile day (lumpy class
    — 98.6% of the panel), one panel per candidate (linear axes: the zero
    candidate's y=0 row is the point of the figure)."""
    lumpy_mask = cells["class"] == "lumpy"
    has_lumpy = bool(lumpy_mask.any())
    n_cand = len(PEAK_CANDIDATES)
    n_cols = 3
    n_rows = math.ceil(n_cand / n_cols)
    fig = make_subplots(
        rows=n_rows,
        cols=n_cols,
        subplot_titles=tuple(f"{c} (lumpy peak days)" for c in PEAK_CANDIDATES),
    )
    if has_lumpy:
        for pos, cand in enumerate(PEAK_CANDIDATES, start=1):
            row, col = (pos - 1) // n_cols + 1, (pos - 1) % n_cols + 1
            actual, pred = _peak_day_pairs(cells, test, horizons, n_series, cand)
            fig.add_scatter(
                x=actual,
                y=pred,
                name=cand,
                mode="markers",
                marker={"size": 4, "opacity": 0.5},
                showlegend=False,
                row=row,
                col=col,
            )
            hi = float(max(actual.max(), pred.max())) if actual.size else 1.0
            xref = "x domain" if pos == 1 else f"x{pos} domain"
            yref = "y" if pos == 1 else f"y{pos}"
            fig.add_shape(
                type="line",
                xref=xref,
                x0=0,
                x1=1,
                yref=yref,
                y0=0.0,
                y1=hi,
                line={"dash": "dot", "color": "#fbbf24"},
                row=row,
                col=col,
            )
    fig.update_xaxes(title="peak-day actual (units)")
    fig.update_yaxes(title="forecast (units)")
    fig.update_layout(title="Peak-day scatter — each scored window's top-decile demand day (lumpy)")
    add_takeaway(
        fig,
        "points on the dotted parity line nail the peak; a flat candidate (zero) hugs the "
        "bottom — this is the structural miss the peak-capable candidates were built for",
    )
    return apply_theme(fig)


# ---------------------------------------------------------------------------
# Artifact merging (called from evaluate.py / probabilistic.py / cli.py)
# ---------------------------------------------------------------------------


def merge_metrics_json(settings: DemandSettings, result: MultiStepResult) -> None:
    """Add the ``_multistep`` block to the track's metrics.json.

    The per-model nowcast blocks (and ``_meta``) are untouched; keys starting
    with ``_`` are ignored by the demo payload's run parser, so the payload
    keeps working unchanged.
    """
    path = Path(settings.reports_dir) / "metrics.json"
    metrics: dict[str, Any] = json.loads(path.read_text())
    metrics["_multistep"] = result.block
    path.write_text(json.dumps(_json_safe(metrics), indent=2))
    logger.info("multistep metrics merged -> %s", path)


def merge_evaluation_metadata(settings: DemandSettings, result: MultiStepResult) -> None:
    """Add the ``multi_horizon`` protocol block to evaluation_metadata.json."""
    path = Path(settings.reports_dir) / "evaluation_metadata.json"
    meta: dict[str, Any] = json.loads(path.read_text())
    meta["multi_horizon"] = result.metadata_block
    path.write_text(json.dumps(_json_safe(meta), indent=2))
    logger.info("multistep evaluation metadata merged -> %s", path)


def probabilistic_multistep_block(result: MultiStepResult) -> dict[str, Any]:
    """The ``multistep`` key for probabilistic.json (merged by run_probabilistic)."""
    return result.probabilistic_block


def save_multistep_figures(settings: DemandSettings, result: MultiStepResult) -> None:
    """Persist the multi-step figure JSONs next to the other figures."""
    out_dir = Path(settings.reports_dir) / "figures"
    for name, fig in result.figures.items():
        save_json(fig, out_dir / f"{name}.json")
