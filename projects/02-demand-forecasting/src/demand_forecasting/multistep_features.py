"""Panel → matrix, target-date calendar and leakage-aged feature tensors.

``panel_matrix`` / ``panel_price_matrix`` pivot the panel to dense arrays;
``_calendar_features`` is the 9-column target-date calendar; the
``*_feature_tensor`` functions compute the wave-20/21/22 peak, price and
rolling blocks at a reference day *r* from data[≤r] only (the aging that makes
the direct designs leakage-proof). ``multistep_origin_indices`` /
``split_origins`` define the weekly rolling origins and the selection/test
split (no embargo gap).
"""

import math
from datetime import timedelta

import numpy as np
import polars as pl

from demand_forecasting.config import ForecastConfig

# Features need units(origin-14) (lags) and a full 28-day window ending at the
# origin (peak features), so training/prediction designs start at day 28.
MIN_LAG_ORIGIN = 28
ORIGIN_SPACING_DAYS = 7


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


# Trading-cycle calendar additions (wave 21): wholesale buyers concentrate
# orders at month end, so the TARGET-date calendar carries is_month_end (the
# next calendar day starts a new month) and week_of_month ((dom-1)//7+1).
# Pure functions of the target date — known in advance, leakage-free.


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
