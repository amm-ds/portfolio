"""M5 headline experiment — protocol ``m5_direct_v1`` (wave 24).

The UCI Online Retail II panel track (multihorizon.py) stays untouched as the
secondary study; this module is the NEW headline experiment on the committed
Walmart M5 subset, in the regime where ML demonstrably wins: dense daily
store-item demand (16% zero-day share, top-volume assortment) with real
exogenous signal (price, SNAP, events).

Protocol (fixed a priori, machine-readable in evaluation_metadata.json):

- **Weekly rolling origins** near the end of the panel: ``N_ORIGINS = 10``
  origins 7 days apart, each training on >= ``MIN_TRAIN_DAYS`` (3+ years) and
  scoring the next ``HORIZON = 28`` days (the M5 evaluation horizon). The
  first ``N_SELECTION_ORIGINS = 8`` are SELECTION (ensemble weights, conformal
  calibration); the LAST 2 are TEST — scored once, never read for selection.
- **Candidates**: ``seasonal_naive`` (m=7), ``window_avg_28``, ``adida``,
  ``tsb`` (per-series statistical, statsforecast 2.1.1 — C-fast),
  ``auto_ets``, ``auto_ces`` (per-series automatic, statsforecast), ``lgbm``
  (global LightGBM via mlforecast 1.1.0: lags 1/7/14/21/28, rolling means,
  calendar, exog price/SNAP/event codes — no series-identity feature, the
  global model generalises across the 600 series), and ``convex_ensemble`` —
  a convex combination of the best two of {lgbm, auto_ets, auto_ces} by
  SELECTION WAPE, weight fit on the selection origins only over a fixed 0..1
  grid (deterministic, documented).
- **Volume classes** per series: ADI/CV² (Syntetos-Boylan, same thresholds as
  the panel track) computed on the series' REAL history up to the last
  SELECTION origin — pre-introduction days are excluded (an item not yet
  assorted is not intermittent demand). ``dense`` = smooth/erratic,
  ``intermittent`` = intermittent/lumpy.
- **Metrics** per candidate x class x {selection, test}: MAE, WAPE, rmae
  (pooled MAE ratio vs seasonal_naive, floored at 1.0 when the floor is 0),
  WRMSSE and volume-weighted WRMSSE (per (series x origin) unit:
  sqrt(MSE over the 28 scored days / in-sample MSE of the one-step
  seasonal-naive-28 over that series' training window; zero-denominator
  units excluded), peak-day MAE (the window's top-decile-by-actual days),
  plus per-candidate horizon-wise MAE growth, and per-series win-rate vs
  seasonal_naive.
- **Headline gaps** — lgbm vs seasonal_naive and convex_ensemble vs
  seasonal_naive on the TEST origins: pooled-WAPE difference and pooled-WRMSSE
  difference, each with a 95% paired cluster bootstrap over series (one shared
  index draw per replication, ``BOOTSTRAP_REPS = 2000``, fixed seed).
- **Probabilistic** (lgbm + convex_ensemble): a per-series SCALED
  split-conformal band calibrated on SELECTION-origin out-of-sample residuals
  at per-horizon-day granularity —
  ``lo/hi = point ± quantile(|residual_h| / scale_i, 0.8) * scale_i`` with
  ``scale_i`` the series' in-sample seasonal-naive-28 RMSE (the same scale
  family as the WRMSSE denominator). A pooled absolute-width band was tried
  first and mis-serves the panel's volume heterogeneity (top-quintile series
  covered ~61% vs ~90% bottom-quintile at the same nominal 80% level); the
  scaled band brackets every volume quintile at ~80%. This mirrors
  mlforecast's ``PredictionIntervals`` conformal strategy (per-horizon-step
  quantile of calibration-window absolute errors — the 8 selection origins
  are the calibration windows), with the documented per-series scale
  extension; zero-clipped and sorted. Reported: p50/p90 pinball, the
  empirical 80% coverage pooled and by volume class on the test origins.
- **Demo sidecar**: the run retains the per-series forecast curves of the
  FIXED 24-series demo catalog (same deterministic rule as the payload) at
  the 2 test origins — ``reports_m5/catalog_forecasts.parquet`` — so the
  demo payload copies curves from the committed global model instead of
  re-fitting a catalog-subset approximation (an earlier subset refit was
  both weaker and, via a row-order mismatch, mis-aligned — see DESIGN N).
- **Honesty/determinism**: no candidate sees test rows at fit/selection time;
  LightGBM runs ``n_jobs=1`` + fixed seed + ``force_row_wise`` (the repo's
  byte-identity contract); statsforecast runs ``n_jobs=1``; every fit is
  seeded or closed-form, so a re-run reproduces the artifacts byte-for-byte
  (tested on tiny fixtures and the real-subset smoke).
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from portfolio_core.logging import get_logger

from demand_forecasting.intermittent import classify_demand
from demand_forecasting.m5_data import (
    encode_events,
    load_m5_subset,
    m5_dataset_metadata,
    rolling_origins,
    split_exogenous,
)

logger = get_logger(__name__)

PROTOCOL = "m5_direct_v1"
HORIZON = 28
N_ORIGINS = 10
N_SELECTION_ORIGINS = 8  # the LAST N_ORIGINS - this many are scored-once test
MIN_TRAIN_DAYS = 1096  # >= 3 years of training history per origin
ORIGIN_SPACING_DAYS = 7
SEED = 42
BOOTSTRAP_REPS = 2000
# Fixed-a-priori LightGBM config (not tuned — the track compares modelling
# families; tuning belongs to a later phase).
LGBM_KWARGS: dict[str, Any] = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_child_samples": 20,
}
# TSB smoothing constants — repo convention (intermittent.ALPHA), fixed a priori.
TSB_ALPHA_D = 0.1
TSB_ALPHA_P = 0.1
# Ensemble grid: w in [0, 1] step 0.01 over SELECTION WAPE.
ENSEMBLE_GRID = np.round(np.arange(0.0, 1.0 + 1e-9, 0.01), 2)
ENSEMBLE_POOL = ("lgbm", "auto_ets", "auto_ces")
STATISTICAL_CANDIDATES = ("seasonal_naive", "window_avg_28", "adida", "tsb")
CANDIDATES = (*STATISTICAL_CANDIDATES, "auto_ets", "auto_ces", "lgbm", "convex_ensemble")
NAIVE = "seasonal_naive"
DENSE_CLASSES = ("smooth", "erratic")
#: demo catalog quota per (store x class) cell -> 3 stores x 2 classes x 4 = 24.
CATALOG_PER_CELL = 4
#: candidates whose per-series curves the demo sidecar retains (every shipped
#: curve candidate plus auto_ces — a potential ensemble member the demo blend
#: needs verifiable).
SIDECAR_CANDIDATES = ("seasonal_naive", "auto_ets", "auto_ces", "lgbm", "convex_ensemble")
#: the demo sidecar artifact (per-series catalog curves at the test origins).
CATALOG_FORECASTS_NAME = "catalog_forecasts.parquet"
CATALOG_RULE = (
    "deterministic: within each (store, class) cell, series are ordered by "
    "total panel volume descending (ties -> unique_id) and the evenly spaced "
    "ranks [0, 1, len//2, len-1] (first CATALOG_PER_CELL of them) are picked, "
    "so every cell spans high/mid/low volume"
)

METRIC_DEFINITIONS = {
    "mae": "mean |actual - forecast| over the scored (series x day) cells",
    "wape": "sum |actual - forecast| / sum actual over the scored cells "
    "(pooled volume-weighted absolute percentage error)",
    "rmae": "candidate pooled MAE / seasonal_naive pooled MAE over the same "
    "cells (< 1 beats the naive floor); a zero naive MAE floors the ratio at 1.0",
    "wrmsse": "per (series x origin) unit: sqrt(MSE over the 28 scored days / "
    "in-sample MSE of the one-step seasonal-naive-28 over the series' training "
    "window); zero-denominator units excluded; 'wrmsse' = mean over units, "
    "'wrmsse_weighted' = weighted by the training-window volume. NOTE: the "
    "official M5 denominator is the lag-1 random walk; this track uses the "
    "seasonal-naive-28 denominator per the wave-24 plan (a stricter scale for "
    "weekly-seasonal dense demand)",
    "peak_mae": "MAE on the window's top-decile-by-actual days (k = ceil(0.1*28) = 3)",
    "win_rate_vs_naive": "share of series whose pooled test |error| is below the "
    "seasonal_naive pooled test |error|",
    "pinball": "mean pinball loss at the stated quantile over the test cells",
    "coverage_80": "share of test actuals inside the per-series scaled "
    "split-conformal 80% band (pooled and by volume class)",
}


@dataclass
class M5Result:
    """In-memory result: the JSON blocks plus the report-figure payload."""

    metrics: dict[str, Any]
    probabilistic: dict[str, Any]
    metadata: dict[str, Any]
    catalog_frame: pd.DataFrame
    catalog_meta: dict[str, Any]


# ---------------------------------------------------------------------------
# Candidate fits per origin
# ---------------------------------------------------------------------------


def _weekofyear(dates: pd.Series) -> np.ndarray:
    """ISO week as an int32 array — pandas 2 removed .dt.weekofyear, so the
    mlforecast date_features entry is this callable (deterministic)."""
    out: np.ndarray = dates.isocalendar().week.to_numpy().astype("int32")
    return out


def statsforecast_candidates() -> list[Any]:
    """The per-series statistical/automatic candidate models (statsforecast).

    Every model carries an explicit ``alias`` so the forecast frame columns
    are the protocol's snake_case candidate names in every call path.
    """
    from statsforecast.models import ADIDA, TSB, AutoCES, AutoETS, SeasonalNaive, WindowAverage

    return [
        SeasonalNaive(season_length=7, alias="seasonal_naive"),
        WindowAverage(window_size=28, alias="window_avg_28"),
        ADIDA(alias="adida"),
        TSB(alpha_d=TSB_ALPHA_D, alpha_p=TSB_ALPHA_P, alias="tsb"),
        AutoETS(season_length=7, alias="auto_ets"),
        AutoCES(season_length=7, alias="auto_ces"),
    ]


def _sf_fit_predict(
    train: pd.DataFrame, series_ids: list[str], horizon: int
) -> dict[str, np.ndarray]:
    """Batch statsforecast fit_predict re-indexed to (n_series, h)."""
    from statsforecast import StatsForecast

    aliases = ["seasonal_naive", "window_avg_28", "adida", "tsb", "auto_ets", "auto_ces"]
    sf = StatsForecast(models=statsforecast_candidates(), freq="D", n_jobs=1)
    fc: Any = sf.fit_predict(h=horizon, df=train, id_col="unique_id", time_col="ds", target_col="y")
    idx = {sid: i for i, sid in enumerate(series_ids)}
    order = fc["unique_id"].map(idx).to_numpy()
    n_series = len(series_ids)
    if len(fc) != n_series * horizon or not np.array_equal(
        np.sort(order), np.repeat(np.arange(n_series), horizon)
    ):
        raise ValueError("statsforecast did not return exactly the (series x horizon) grid")
    # fc rows are one contiguous h-block per series (statsforecast groups by
    # series); block j belongs to target row order[j * horizon]
    block_target = order.reshape(-1, horizon)[:, 0]
    if set(block_target.tolist()) != set(range(n_series)):
        raise ValueError("statsforecast did not return exactly the (series x horizon) grid")
    out: dict[str, np.ndarray] = {}
    for alias in aliases:
        col: np.ndarray = fc[alias].to_numpy(dtype=float)
        mat = col.reshape(-1, horizon)  # block j -> series_ids[block_target[j]]
        if np.isnan(mat).any():
            raise ValueError(f"candidate {alias} produced NaNs at this origin")
        out[alias] = mat[np.argsort(block_target, kind="stable")]
    return out


def _statistical_forecasts(
    train: pd.DataFrame, series_ids: list[str], horizon: int
) -> dict[str, np.ndarray]:
    """Per-series candidate forecasts at one origin: {name -> (n_series, h)}.

    First the batch statsforecast pass (C-fast). Automatic model selection
    (auto_ets/auto_ces) can fail on degenerate series ("no model able to be
    fitted"); a batch failure then isolates per series: the failing
    (series, candidate) cell falls back to that series' seasonal_naive — a
    documented, deterministic degradation (fixed loop order, no RNG), and the
    seasonal_naive floor itself must always fit.
    """
    try:
        return _sf_fit_predict(train, series_ids, horizon)
    except Exception as exc:
        logger.warning("batch statsforecast failed (%s); per-series fallback", exc)
    from statsforecast import StatsForecast

    aliases = ["seasonal_naive", "window_avg_28", "adida", "tsb", "auto_ets", "auto_ces"]
    n_series = len(series_ids)
    out: dict[str, np.ndarray] = {a: np.zeros((n_series, horizon)) for a in aliases}
    models = statsforecast_candidates()
    for i, sid in enumerate(series_ids):
        s_train = train[train["unique_id"] == sid]
        # the floor is fit first: it is also the fallback for failing cells
        for alias, model in zip(aliases, models, strict=True):
            try:
                sf = StatsForecast(models=[model], freq="D", n_jobs=1)
                fc: Any = sf.fit_predict(
                    h=horizon, df=s_train, id_col="unique_id", time_col="ds", target_col="y"
                )
                row: np.ndarray = fc[alias].to_numpy(dtype=float)
                out[alias][i] = row
            except Exception as exc:
                if alias == NAIVE:
                    raise ValueError(f"seasonal_naive must always fit ({sid}): {exc}") from exc
                logger.warning("candidate %s failed on %s; naive fallback", alias, sid)
                out[alias][i] = out[NAIVE][i]
    return out


def _lgbm_forecast(
    train: pd.DataFrame,
    hist_exog: pd.DataFrame,
    future_exog: pd.DataFrame,
    seed: int,
    n_estimators: int | None = None,
    series_ids: list[str] | None = None,
) -> np.ndarray:
    """Global LightGBM point forecast at one origin: (n_series, h).

    mlforecast recursive strategy: lags 1/7/14/21/28, rolling means at those
    lags, calendar dayofweek/month/ISO-week, exog price/SNAP/event codes
    (history joined on the training frame; future values from the calendar /
    forward-filled price). Determinism: fixed seed, n_jobs=1, force_row_wise
    (the repo's byte-identity contract for LightGBM).

    mlforecast returns rows sorted by ``unique_id`` (alphabetical) — NOT in
    the caller's series order; pass ``series_ids`` to get the result
    re-indexed to it (the demo-payload refit bug was exactly this mismatch).
    """
    from lightgbm import LGBMRegressor
    from mlforecast import MLForecast
    from mlforecast.lag_transforms import RollingMean

    train_m = train.merge(hist_exog, on=["unique_id", "ds"], how="left", validate="1:1")
    if train_m.drop(columns=["unique_id", "ds", "y"]).isna().any().any():
        raise ValueError("exogenous merge produced NaNs in the lgbm training frame")
    kwargs = dict(LGBM_KWARGS)
    if n_estimators is not None:
        kwargs["n_estimators"] = n_estimators
    model = LGBMRegressor(
        random_state=seed,
        verbosity=-1,
        n_jobs=1,
        force_row_wise=True,
        **kwargs,
    )
    fc = MLForecast(
        models=[model],
        freq="D",
        lags=[1, 7, 14, 21, 28],
        lag_transforms={1: [RollingMean(7), RollingMean(28, min_samples=1)], 7: [RollingMean(7)]},
        date_features=["dayofweek", "month", _weekofyear],
    )
    fc.fit(
        train_m,
        id_col="unique_id",
        time_col="ds",
        target_col="y",
        static_features=[],
    )
    pred: Any = fc.predict(HORIZON, X_df=future_exog)
    col_name = pred.columns[-1]
    alpha_ids = sorted(train_m["unique_id"].unique().tolist())
    n_series = len(alpha_ids)
    if len(pred) != n_series * HORIZON:
        raise ValueError("mlforecast did not return the (series x horizon) grid")
    # rows come back one h-block per series, sorted by (unique_id, ds)
    col: np.ndarray = pred.sort_values(["unique_id", "ds"])[col_name].to_numpy(dtype=float)
    mat = col.reshape(n_series, HORIZON)  # alphabetical unique_id order
    if series_ids is not None:
        if set(series_ids) != set(alpha_ids) or len(series_ids) != n_series:
            raise ValueError("series_ids does not match the training frame's series set")
        alpha_pos = {sid: i for i, sid in enumerate(alpha_ids)}
        mat = mat[[alpha_pos[sid] for sid in series_ids]]
    if np.isnan(mat).any():
        raise ValueError("lgbm forecast contains NaNs")
    clipped: np.ndarray = np.clip(mat, 0.0, None)
    return clipped


# ---------------------------------------------------------------------------
# Pure metric pieces (hand-testable)
# ---------------------------------------------------------------------------


def wape(y: np.ndarray, pred: np.ndarray) -> float:
    """Pooled WAPE: sum |err| / sum y (NaN when the scored volume is 0)."""
    den = float(np.sum(y))
    if den <= 0:
        return float("nan")
    return float(np.sum(np.abs(pred - y)) / den)


def rmae(cand_mae: float, naive_mae: float) -> float:
    """Pooled-MAE ratio vs the seasonal_naive floor, floored at 1.0."""
    if naive_mae <= 0:
        return 1.0
    return float(cand_mae / naive_mae)


def naive28_scale(train_y: np.ndarray) -> float:
    """In-sample one-step seasonal-naive-28 MSE over a training series.

    ``mean((y[t] - y[t-28])^2)`` over the contiguous real history; NaN when
    the window has fewer than 29 days (unit excluded from WRMSSE).
    """
    y = np.asarray(train_y, dtype=float)
    if y.size <= HORIZON:
        return float("nan")
    return float(np.mean((y[HORIZON:] - y[:-HORIZON]) ** 2))


def wrmsse_units(
    err_windows: np.ndarray, scales: np.ndarray, volumes: np.ndarray
) -> tuple[float, float]:
    """(pooled, volume-weighted) WRMSSE from per-(series x origin) units.

    ``err_windows`` (n_units, h) scored errors, ``scales``/``volumes`` (n_units,)
    in-sample naive-28 MSEs and training volumes. Zero/NaN-scale units are
    excluded; NaN when every unit is excluded.
    """
    units: list[float] = []
    w_num = 0.0
    w_den = 0.0
    for i in range(err_windows.shape[0]):
        s2 = scales[i]
        if np.isnan(s2) or s2 <= 0:
            continue
        r = float(np.sqrt(np.mean(err_windows[i] ** 2) / s2))
        units.append(r)
        w_num += volumes[i] * r
        w_den += volumes[i]
    if not units:
        return float("nan"), float("nan")
    return float(np.mean(units)), (w_num / w_den if w_den > 0 else float("nan"))


def peak_mae(y: np.ndarray, pred: np.ndarray) -> float:
    """MAE on the top-decile-by-actual scored days (whole scored block)."""
    y = np.asarray(y, dtype=float).reshape(-1)
    pred = np.asarray(pred, dtype=float).reshape(-1)
    k = max(1, int(np.ceil(0.1 * y.size)))
    top = np.argsort(y)[::-1][:k]
    return float(np.mean(np.abs(pred[top] - y[top])))


def pinball_loss(y: np.ndarray, pred: np.ndarray, tau: float) -> float:
    """Mean pinball loss at quantile ``tau``."""
    diff = np.asarray(y, dtype=float) - np.asarray(pred, dtype=float)
    return float(np.mean(np.maximum(tau * diff, (tau - 1.0) * diff)))


def band_scales(scales: np.ndarray) -> np.ndarray:
    """Per-series band scale: the seasonal-naive-28 in-sample RMSE.

    ``scales`` are the per-series naive-28 in-sample MSEs (see
    :func:`naive28_scale`); the band scale is their square root — the same
    scale family as the WRMSSE denominator, so loud and quiet series get
    proportionally wide/narrow conformal bands. Zero/NaN scales (constant or
    too-short training windows) fall back to the origin's median valid RMSE
    (then to 1.0 if no scale is valid at all).
    """
    rmse = np.sqrt(np.where(np.isnan(scales) | (scales <= 0), np.nan, scales))
    fallback = float(np.nanmedian(rmse))
    if not np.isfinite(fallback) or fallback <= 0:
        fallback = 1.0
    out = np.where(np.isnan(rmse), fallback, rmse)
    return np.maximum(out, 1e-9)


def ensemble_weight(pred_a: np.ndarray, pred_b: np.ndarray, y: np.ndarray) -> float:
    """Grid-fit convex weight minimising pooled WAPE of w*A + (1-w)*B.

    The grid is :data:`ENSEMBLE_GRID` (0..1 step 0.01); ties resolve to the
    smallest w (first argmin) — deterministic. Pure, hand-testable.
    """
    best_w, best_err = 0.0, float("inf")
    for w in ENSEMBLE_GRID:
        err = float(np.sum(np.abs(w * pred_a + (1.0 - w) * pred_b - y)))
        if err < best_err - 1e-12:
            best_err, best_w = err, float(w)
    return best_w


def paired_bootstrap_wape(
    abs_err_a: np.ndarray,
    abs_err_b: np.ndarray,
    demand: np.ndarray,
    series_of: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """95% CI on pooled-WAPE(A) - pooled-WAPE(B), cluster bootstrap over series.

    The replicated statistic is the resampled error-ratio difference
    ``(sum |err_A| - sum |err_B|) / sum demand`` — i.e. a WAPE-gap, not an MAE
    gap (units matter: WAPE is volume-normalised). One shared series-index
    draw per replication (the projects/05/10 pattern) keeps the difference
    paired; percentile interval; zero-demand resamples are skipped (NaN).
    """
    uniques = np.unique(series_of)
    sum_a = np.array([abs_err_a[series_of == i].sum() for i in uniques])
    sum_b = np.array([abs_err_b[series_of == i].sum() for i in uniques])
    vol = np.array([demand[series_of == i].sum() for i in uniques])
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, len(uniques), len(uniques))
        denom = vol[idx].sum()
        diffs[b] = (sum_a[idx].sum() - sum_b[idx].sum()) / denom if denom > 0 else np.nan
    lo, hi = np.nanquantile(diffs, [0.025, 0.975])
    denom = float(demand.sum())
    point = float((abs_err_a.sum() - abs_err_b.sum()) / denom) if denom > 0 else float("nan")
    return {
        "diff": point,
        "ci95": [float(lo), float(hi)],
        "spans_zero": bool(lo <= 0.0 <= hi),
        "n_boot": n_boot,
        "seed": seed,
    }


def paired_bootstrap_wrmsse(
    units_a: np.ndarray, units_b: np.ndarray, series_of: np.ndarray, n_boot: int, seed: int
) -> dict[str, Any]:
    """95% CI on pooled-WRMSSE(A) - pooled-WRMSSE(B), cluster bootstrap over series.

    ``units_*`` are per-(series x origin) RMSSE ratios (zero-scale units
    already excluded, pairwise aligned); the replicated statistic is the
    resampled mean difference.
    """
    uniques = np.unique(series_of)
    a_of = np.array([units_a[series_of == i].mean() for i in uniques])
    b_of = np.array([units_b[series_of == i].mean() for i in uniques])
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, len(uniques), len(uniques))
        diffs[b] = a_of[idx].mean() - b_of[idx].mean()
    lo, hi = np.quantile(diffs, [0.025, 0.975])
    return {
        "diff": float(units_a.mean() - units_b.mean()),
        "ci95": [float(lo), float(hi)],
        "spans_zero": bool(lo <= 0.0 <= hi),
        "n_boot": n_boot,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------


def _actual_window(
    y: pd.DataFrame, series_ids: list[str], origin_date: pd.Timestamp, horizon: int
) -> np.ndarray:
    """(n_series, h) actuals for the window after ``origin_date``."""
    lo = origin_date + pd.to_timedelta(1, unit="D")
    hi = origin_date + pd.to_timedelta(horizon, unit="D")
    win = y[(y["ds"] >= lo) & (y["ds"] <= hi)]
    grid = win.pivot(index="unique_id", columns="ds", values="y").reindex(series_ids)
    if grid.shape != (len(series_ids), horizon) or grid.isna().any().any():
        raise ValueError(f"scored window after {origin_date.date()} is not a full grid")
    arr: np.ndarray = grid.to_numpy(dtype=float)
    return arr


def _series_train_history(
    y: pd.DataFrame, series_ids: list[str], upto: pd.Timestamp
) -> dict[str, np.ndarray]:
    """Per-series REAL history (contiguous from first sale) up to ``upto``."""
    keep = set(series_ids)
    hist = y[y["ds"] <= upto]
    return {
        sid: g.sort_values("ds")["y"].to_numpy(dtype=float)
        for sid, g in hist.groupby("unique_id")
        if sid in keep
    }


def run_m5_track(
    data_dir: Path,
    *,
    n_origins: int = N_ORIGINS,
    n_test_origins: int = N_ORIGINS - N_SELECTION_ORIGINS,
    min_train: int = MIN_TRAIN_DAYS,
    seed: int = SEED,
    bootstrap_reps: int = BOOTSTRAP_REPS,
    series_ids: list[str] | None = None,
    n_estimators: int | None = None,
) -> M5Result:
    """Run the full m5_direct_v1 track and return the JSON-ready blocks.

    ``series_ids`` restricts the panel (deterministic pre-sort by the caller)
    for the real-subset smoke test; everything else is the committed protocol.
    """
    t0 = time.time()
    y_all, x_all, s_all = load_m5_subset(Path(data_dir))
    if series_ids is not None:
        keep = set(series_ids)
        y_all = y_all[y_all["unique_id"].isin(keep)]
        x_all = x_all[x_all["unique_id"].isin(keep)]
        s_all = s_all[s_all["unique_id"].isin(keep)]
    series_ids = sorted(y_all["unique_id"].unique().tolist())
    n_series = len(series_ids)
    dates = np.sort(y_all["ds"].unique())
    state_of = s_all.drop_duplicates("unique_id").set_index("unique_id")["state_id"]
    x_enc = encode_events(x_all, x_all["unique_id"].map(state_of))

    origins = rolling_origins(dates, n_origins, HORIZON, min_train, ORIGIN_SPACING_DAYS)
    n_sel = len(origins) - n_test_origins
    selection, test = origins[:n_sel], origins[n_sel:]
    origin_dates = [pd.Timestamp(dates[o]) for o in origins]
    logger.info(
        "m5 track: %d origins (%d selection + %d test), horizon %d, %d series, min_train %d days",
        len(origins),
        len(selection),
        len(test),
        HORIZON,
        n_series,
        min_train,
    )
    logger.info(
        "m5 origins: selection %s | test %s",
        [str(d.date()) for d in origin_dates[: len(selection)]],
        [str(d.date()) for d in origin_dates[len(selection) :]],
    )

    # ---- per-origin forecasts for every candidate ----
    forecasts: dict[str, dict[int, np.ndarray]] = {c: {} for c in CANDIDATES}
    actuals: dict[int, np.ndarray] = {}
    for k, o in enumerate(origins):
        odate = pd.Timestamp(dates[o])
        t_o = time.time()
        train = y_all[y_all["ds"] <= odate]
        actuals[o] = _actual_window(y_all, series_ids, odate, HORIZON)
        preds = _statistical_forecasts(train, series_ids, HORIZON)
        hist_exog, future_exog = split_exogenous(x_enc, series_ids, odate, HORIZON)
        preds["lgbm"] = _lgbm_forecast(
            train, hist_exog, future_exog, seed, n_estimators, series_ids
        )
        for name, mat in preds.items():
            forecasts[name][o] = mat
        logger.info(
            "m5 origin %d/%d (%s): %d series scored in %.1fs",
            k + 1,
            len(origins),
            odate.date(),
            n_series,
            time.time() - t_o,
        )

    # ---- volume classes on the real history up to the LAST SELECTION origin
    hist = _series_train_history(y_all, series_ids, pd.Timestamp(dates[selection[-1]]))
    classes = {sid: classify_demand(hist[sid]) for sid in series_ids}
    dense_mask = np.array([classes[sid]["class"] in DENSE_CLASSES for sid in series_ids])
    logger.info(
        "m5 classes: %d dense, %d intermittent (ADI/CV2 on real history to %s)",
        int(dense_mask.sum()),
        int((~dense_mask).sum()),
        pd.Timestamp(dates[selection[-1]]).date(),
    )

    def _stack(subset: list[int], cand: str) -> tuple[np.ndarray, np.ndarray]:
        return np.concatenate([forecasts[cand][o] for o in subset]), np.concatenate(
            [actuals[o] for o in subset]
        )

    # ---- WRMSSE scales/volumes per (series, origin) (band scales reuse them)
    scales: dict[int, np.ndarray] = {}
    volumes: dict[int, np.ndarray] = {}
    for o in origins:
        h = _series_train_history(y_all, series_ids, pd.Timestamp(dates[o]))
        scales[o] = np.array([naive28_scale(h[sid]) for sid in series_ids])
        volumes[o] = np.array([float(np.sum(h[sid])) for sid in series_ids])

    # ---- conformal band calibration on SELECTION residuals (per horizon day,
    #      per-series scaled — see the module docstring: a pooled absolute
    #      width mis-serves this panel's volume heterogeneity)
    pred_lgbm_sel, act_sel = _stack(selection, "lgbm")
    scale_sel = np.concatenate([band_scales(scales[o]) for o in selection])
    resid_scaled = (pred_lgbm_sel - act_sel) / scale_sel[:, None]  # (n_sel*n_series, H)
    q80 = np.quantile(np.abs(resid_scaled), 0.8, axis=0)  # per horizon day
    q80 = np.maximum(q80, 1e-9)

    # ---- ensemble: best two of the pool by SELECTION WAPE, grid weight ----
    sel_wapes = {c: wape(act_sel, _stack(selection, c)[0]) for c in ENSEMBLE_POOL}
    ranked = sorted(
        ENSEMBLE_POOL,
        key=lambda c: (
            float("inf") if sel_wapes[c] != sel_wapes[c] else sel_wapes[c],
            c,
        ),
    )
    ens_a, ens_b = ranked[0], ranked[1]
    pred_a_sel, pred_b_sel = _stack(selection, ens_a)[0], _stack(selection, ens_b)[0]
    w_ens = ensemble_weight(pred_a_sel, pred_b_sel, act_sel)
    for o in origins:
        forecasts["convex_ensemble"][o] = (
            w_ens * forecasts[ens_a][o] + (1.0 - w_ens) * forecasts[ens_b][o]
        )
    logger.info(
        "m5 ensemble: %s (w=%.2f) + %s (w=%.2f) by selection WAPE %s",
        ens_a,
        w_ens,
        ens_b,
        1.0 - w_ens,
        {c: round(v, 4) for c, v in sel_wapes.items()},
    )

    test_block = _metrics_block(forecasts, actuals, scales, volumes, test, dense_mask, n_series)
    selection_block = _metrics_block(
        forecasts, actuals, scales, volumes, selection, dense_mask, n_series
    )

    # ---- headline gaps with paired cluster bootstrap on the TEST origins ----
    pred_lgbm_t, act_t = _stack(test, "lgbm")
    pred_ens_t, _ = _stack(test, "convex_ensemble")
    pred_naive_t, _ = _stack(test, NAIVE)
    n_o = len(test)
    err_lgbm = np.abs(pred_lgbm_t - act_t).reshape(-1)
    err_ens = np.abs(pred_ens_t - act_t).reshape(-1)
    err_naive = np.abs(pred_naive_t - act_t).reshape(-1)
    act_cells = act_t.reshape(-1)
    ser_cells = np.repeat(np.tile(np.arange(n_series), n_o), HORIZON)  # per scored cell

    def _wrmsse_units_of(cand_pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        err = (cand_pred - act_t).reshape(n_o, n_series, HORIZON)
        sc = np.stack([scales[o] for o in test])  # (n_o, n_series)
        keep = ~(np.isnan(sc) | (sc <= 0))
        units = np.full((n_o, n_series), np.nan)
        units[keep] = np.sqrt((err[keep] ** 2).mean(axis=1) / sc[keep])
        flat_units = units.reshape(-1)[keep.reshape(-1)]
        flat_series = np.tile(np.arange(n_series), n_o)[keep.reshape(-1)]
        return flat_units, flat_series

    units_lgbm, ser_l = _wrmsse_units_of(pred_lgbm_t)
    units_ens, ser_e = _wrmsse_units_of(pred_ens_t)
    units_naive, _ = _wrmsse_units_of(pred_naive_t)

    headline = {
        "lgbm_vs_naive": {
            "wape": paired_bootstrap_wape(
                err_lgbm, err_naive, act_cells, ser_cells, bootstrap_reps, seed + 11
            ),
            "wrmsse": paired_bootstrap_wrmsse(
                units_lgbm, units_naive, ser_l, bootstrap_reps, seed + 12
            ),
        },
        "convex_ensemble_vs_naive": {
            "wape": paired_bootstrap_wape(
                err_ens, err_naive, act_cells, ser_cells, bootstrap_reps, seed + 13
            ),
            "wrmsse": paired_bootstrap_wrmsse(
                units_ens, units_naive, ser_e, bootstrap_reps, seed + 14
            ),
        },
        "baseline": NAIVE,
    }

    # ---- probabilistic block (per-series scaled split-conformal 80% band,
    #      calibration on SELECTION residuals only)
    prob: dict[str, Any] = {
        "method": "per-series scaled split-conformal: lo/hi = point ± "
        "(per-horizon-day 0.8-quantile of |lgbm residual| / series scale over "
        "the SELECTION origins, 8 x n_series calibration points per h) x (the "
        "scored origin's naive-28 in-sample RMSE of that series; zero/NaN scale "
        "-> the origin's median valid RMSE) — level 0.8; zero-clipped and "
        "sorted. p50 = point forecast; p90 = hi band edge.",
        "level": 0.8,
        "per_horizon_width": q80.tolist(),
        "candidates": {},
    }
    for cand in ("lgbm", "convex_ensemble"):
        pred_t, _ = _stack(test, cand)
        los, his, covs = [], [], []
        for o in test:
            width = q80[None, :] * band_scales(scales[o])[:, None]
            lo = np.clip(forecasts[cand][o] - width, 0.0, None)
            hi = forecasts[cand][o] + width
            los.append(lo)
            his.append(hi)
            covs.append((actuals[o] >= lo) & (actuals[o] <= hi))
        hi_t = np.concatenate(his)  # (n_test * n_series, HORIZON)
        covered = np.stack(covs)  # (n_test, n_series, HORIZON)
        prob["candidates"][cand] = {
            "pinball_p50": pinball_loss(act_t, pred_t, 0.5),
            "pinball_p90": pinball_loss(act_t, hi_t, 0.9),
            "coverage_80": float(covered.mean()),
            "coverage_80_by_class": {
                "dense": float(covered[:, dense_mask, :].mean()),
                "intermittent": float(covered[:, ~dense_mask, :].mean()),
            },
            "mean_band_width": float(np.mean([hi - lo for hi, lo in zip(his, los, strict=True)])),
        }

    metrics = {
        "protocol": PROTOCOL,
        "candidates": list(CANDIDATES),
        "origins": {
            "dates": [str(d.date()) for d in origin_dates],
            "indices": [int(o) for o in origins],
            "selection": [str(d.date()) for d in origin_dates[: len(selection)]],
            "test": [str(d.date()) for d in origin_dates[len(selection) :]],
            "horizon_days": HORIZON,
            "min_train_days": min_train,
            "spacing_days": ORIGIN_SPACING_DAYS,
        },
        "classes": {
            "method": "Syntetos-Boylan ADI/CV2 on each series' REAL history (pre-introduction "
            "days excluded) up to the last SELECTION origin",
            "thresholds": {"adi": 1.32, "cv2": 0.49},
            "dense_quadrants": list(DENSE_CLASSES),
            "counts": {
                "dense": int(dense_mask.sum()),
                "intermittent": int((~dense_mask).sum()),
            },
            "per_series": {
                sid: {
                    "adi": classes[sid]["adi"],
                    "cv2": classes[sid]["cv2"],
                    "class": classes[sid]["class"],
                }
                for sid in series_ids
            },
        },
        "ensemble": {
            "pool": list(ENSEMBLE_POOL),
            "selection_wape": sel_wapes,
            "members": [ens_a, ens_b],
            "weight_on_a": w_ens,
            "rule": "best two of the pool by selection WAPE; w grid-fit on selection "
            "origins only (ENSEMBLE_GRID, ties -> smallest w)",
        },
        "selection": selection_block,
        "test": test_block,
        "headline": headline,
    }

    # ---- report payload: sample series (test windows) ----
    sample_ids = _pick_sample_series(series_ids, volumes[origins[-1]], s_all)
    report_series = []
    for sid in sample_ids:
        i = series_ids.index(sid)
        for o in test:
            odate = pd.Timestamp(dates[o])
            days = pd.date_range(odate + pd.to_timedelta(1, unit="D"), periods=HORIZON, freq="D")
            report_series.append(
                {
                    "unique_id": sid,
                    "origin": str(odate.date()),
                    "ds": [str(d.date()) for d in days],
                    "actual": actuals[o][i].tolist(),
                    "seasonal_naive": forecasts[NAIVE][o][i].tolist(),
                    "lgbm": forecasts["lgbm"][o][i].tolist(),
                    "convex_ensemble": forecasts["convex_ensemble"][o][i].tolist(),
                }
            )

    metadata = {
        "protocol": PROTOCOL,
        "dataset": m5_dataset_metadata(Path(data_dir), y_all, s_all),
        "split": {
            "n_origins": len(origins),
            "n_selection": len(selection),
            "n_test": len(test),
            "origin_dates": [str(d.date()) for d in origin_dates],
            "selection_dates": [str(d.date()) for d in origin_dates[: len(selection)]],
            "test_dates": [str(d.date()) for d in origin_dates[len(selection) :]],
            "horizon_days": HORIZON,
            "min_train_days": min_train,
            "spacing_days": ORIGIN_SPACING_DAYS,
            "holdout_designation": f"last {len(test)} origins = test, scored once; "
            "selection (ensemble weight, conformal calibration, class anchoring) "
            "uses the earlier origins only",
        },
        "seeds": {"lgbm_random_state": seed, "bootstrap_seed_base": seed},
        "package_versions": _package_versions(),
        "runtime_seconds": round(time.time() - t0, 3),
        "determinism": "VECLIB_MAXIMUM_THREADS=1 pinned in cli.py before numpy; "
        "LightGBM n_jobs=1 + fixed seed + force_row_wise; statsforecast n_jobs=1; "
        "statsforecast models are closed-form/seed-free",
        "metric_definitions": METRIC_DEFINITIONS,
        "report_sample_series": report_series,
    }

    # ---- demo sidecar: per-series curves for the FIXED demo catalog at the
    #      test origins (the payload copies these — no catalog-subset refit)
    stores = s_all.drop_duplicates("unique_id").set_index("unique_id")["store_id"]
    catalog_ids = _select_catalog(y_all, classes, stores, per_cell=CATALOG_PER_CELL)
    cat_idx = [series_ids.index(sid) for sid in catalog_ids]
    sidecar_rows = []
    for o in test:
        odate = pd.Timestamp(dates[o])
        days = pd.date_range(odate + pd.to_timedelta(1, unit="D"), periods=HORIZON, freq="D")
        block: dict[str, Any] = {
            "unique_id": np.repeat(catalog_ids, HORIZON),
            "origin": str(odate.date()),
            "ds": np.tile(days, len(catalog_ids)),
            "actual": actuals[o][cat_idx].reshape(-1),
        }
        for cand in SIDECAR_CANDIDATES:
            block[cand] = forecasts[cand][o][cat_idx].reshape(-1)
        width = q80[None, :] * band_scales(scales[o])[cat_idx][:, None]
        block["band_lo"] = np.clip(forecasts["lgbm"][o][cat_idx] - width, 0.0, None).reshape(-1)
        block["band_hi"] = (forecasts["lgbm"][o][cat_idx] + width).reshape(-1)
        sidecar_rows.append(pd.DataFrame(block))
    catalog_frame = pd.concat(sidecar_rows, ignore_index=True)
    catalog_meta: dict[str, Any] = {
        "protocol": PROTOCOL,
        "catalog_rule": CATALOG_RULE,
        "per_cell": CATALOG_PER_CELL,
        # the full-panel pooled test WAPEs, pinned by the payload's drift
        # guard against the committed metrics block at 1e-9
        "pooled_test_wape": {c: wape(_stack(test, c)[1], _stack(test, c)[0]) for c in CANDIDATES},
        # the catalog-only pooled test WAPEs, recomputed from the sidecar
        # frame by the payload's guard at 1e-9 (catches a tampered curve
        # column; lgbm/ensemble have no live re-run reference)
        "catalog_test_wape": {
            c: float(
                np.abs(catalog_frame[c].to_numpy() - catalog_frame["actual"].to_numpy()).sum()
                / catalog_frame["actual"].to_numpy().sum()
            )
            for c in SIDECAR_CANDIDATES
        },
    }
    logger.info(
        "m5 demo sidecar: %d catalog series x %d test origins retained",
        len(catalog_ids),
        len(test),
    )

    logger.info(
        "m5 track done in %.1fs: test WAPE lgbm=%.4f naive=%.4f | ensemble=%.4f",
        time.time() - t0,
        test_block["pooled"]["lgbm"]["wape"],
        test_block["pooled"][NAIVE]["wape"],
        test_block["pooled"]["convex_ensemble"]["wape"],
    )
    return M5Result(
        metrics=metrics,
        probabilistic=prob,
        metadata=metadata,
        catalog_frame=catalog_frame,
        catalog_meta=catalog_meta,
    )


def _metrics_block(
    forecasts: dict[str, dict[int, np.ndarray]],
    actuals: dict[int, np.ndarray],
    scales: dict[int, np.ndarray],
    volumes: dict[int, np.ndarray],
    subset: list[int],
    dense_mask: np.ndarray,
    n_series: int,
) -> dict[str, Any]:
    """The pooled/by-class/horizon/win-rate metric block for one origin subset.

    Stacks the per-origin (n_series, h) forecast/actual matrices origin-major
    and computes every metric per candidate; volume classes absent from the
    subset get None (json-safe) instead of NaN.
    """

    def _stack(cand: str) -> tuple[np.ndarray, np.ndarray]:
        return np.concatenate([forecasts[cand][o] for o in subset]), np.concatenate(
            [actuals[o] for o in subset]
        )

    def _rate(err_c: np.ndarray, err_n: np.ndarray, mask: np.ndarray) -> float | None:
        if int(mask.sum()) == 0:
            return None
        return float((err_c[mask] < err_n[mask]).mean())

    n_o = len(subset)
    per_cand: dict[str, Any] = {}
    horizon_mae: dict[str, list[float]] = {}
    for c in CANDIDATES:
        pred, act = _stack(c)
        abs_err = np.abs(pred - act)
        naive_abs = np.abs(_stack(NAIVE)[0] - act)
        mae = float(abs_err.mean())
        naive_mae = float(naive_abs.mean())
        # per-(series x origin) units for WRMSSE (origin-major stacking)
        err_signed = (pred - act).reshape(n_o, n_series, HORIZON)
        sc = np.concatenate([scales[o] for o in subset]).reshape(n_o, n_series)
        vol = np.concatenate([volumes[o] for o in subset]).reshape(n_o, n_series)
        pooled, weighted = wrmsse_units(
            err_signed.reshape(-1, HORIZON), sc.reshape(-1), vol.reshape(-1)
        )
        per_cand[c] = {
            "pooled": {
                "mae": mae,
                "wape": wape(act, pred),
                "rmae": rmae(mae, naive_mae),
                "wrmsse": pooled,
                "wrmsse_weighted": weighted,
                "peak_mae": peak_mae(act, pred),
            }
        }
        for cls_name, mask in (("dense", dense_mask), ("intermittent", ~dense_mask)):
            if int(mask.sum()) == 0:
                per_cand[c][cls_name] = None  # class absent from this subset
                continue
            m = np.tile(mask, n_o)
            cls_mae = float(abs_err[m].mean())
            pooled_c, weighted_c = wrmsse_units(
                (pred - act)[m].reshape(-1, HORIZON),
                np.concatenate([scales[o][mask] for o in subset]),
                np.concatenate([volumes[o][mask] for o in subset]),
            )
            per_cand[c][cls_name] = {
                "mae": cls_mae,
                "wape": wape(act[m], pred[m]),
                "rmae": rmae(cls_mae, float(naive_abs[m].mean())),
                "wrmsse": pooled_c,
                "wrmsse_weighted": weighted_c,
                "peak_mae": peak_mae(act[m], pred[m]),
            }
        # horizon-wise MAE (pooled over series and origins)
        horizon_mae[c] = [
            float(
                np.abs(
                    pred.reshape(n_o, n_series, HORIZON)[:, :, h]
                    - act.reshape(n_o, n_series, HORIZON)[:, :, h]
                ).mean()
            )
            for h in range(HORIZON)
        ]
    # win rate vs naive per class (per-series pooled |err| over the subset)
    pred_naive, act_n = _stack(NAIVE)
    win_rates: dict[str, Any] = {}
    for c in CANDIDATES:
        pred, act = _stack(c)
        err_c = np.abs(pred - act).reshape(n_o, n_series, HORIZON).sum(axis=(0, 2))
        err_n = np.abs(pred_naive - act_n).reshape(n_o, n_series, HORIZON).sum(axis=(0, 2))
        win_rates[c] = {
            "pooled": float((err_c < err_n).mean()),
            "dense": _rate(err_c, err_n, dense_mask),
            "intermittent": _rate(err_c, err_n, ~dense_mask),
        }
    return {
        "pooled": {c: per_cand[c]["pooled"] for c in CANDIDATES},
        "by_class": {
            c: {k: v for k, v in per_cand[c].items() if k != "pooled"} for c in CANDIDATES
        },
        "horizon_mae": horizon_mae,
        "win_rate_vs_naive": win_rates,
    }


def _is_dense(syntetos_boylan_class: str) -> bool:
    return syntetos_boylan_class in DENSE_CLASSES


def _select_catalog(
    y: pd.DataFrame,
    classes: dict[str, dict[str, Any]],
    stores: pd.Series,
    *,
    per_cell: int = CATALOG_PER_CELL,
) -> list[str]:
    """Deterministic demo catalog: balanced across stores x {dense, intermittent}.

    Rule (documented in the payload): within each cell, series are ordered by
    total panel volume descending (ties -> unique_id); the evenly spaced
    ranks [0, 1, len//2, len-1] — first ``per_cell`` of them — are picked, so
    every cell spans high/mid/low volume. Shared by the track (which retains
    the catalog curves in the demo sidecar) and the payload builder.
    """
    volume = y.groupby("unique_id")["y"].sum()
    picked: list[str] = []
    for store in sorted(stores.unique()):
        members_store = [s for s in stores.index if stores.loc[s] == store]
        for cls in ("dense", "intermittent"):
            members = sorted(
                (s for s in members_store if _is_dense(classes[s]["class"]) == (cls == "dense")),
                key=lambda s: (-float(volume.loc[s]), s),
            )
            if not members:
                continue
            # evenly spaced ranks [0, 1, mid, last], clamped to the cell and
            # deduplicated (a 1-member cell contributes only rank 0)
            rank_pool = (0, 1, len(members) // 2, len(members) - 1)
            ranks = sorted({min(r, len(members) - 1) for r in rank_pool})[:per_cell]
            picked.extend(members[r] for r in ranks)
    return picked


def _pick_sample_series(
    series_ids: list[str], volume: np.ndarray, s: pd.DataFrame, k: int = 4
) -> list[str]:
    """Representative sample for the report figure: the top-volume series of
    each store (deterministic — volume order, then id)."""
    stores = s.drop_duplicates("unique_id").set_index("unique_id")["store_id"]
    order = np.argsort(-volume, kind="stable")
    picked: list[str] = []
    seen_stores: set[str] = set()
    for i in order:
        if len(picked) >= k:
            break
        sid = series_ids[int(i)]
        st = str(stores.loc[sid])
        if st not in seen_stores:
            picked.append(sid)
            seen_stores.add(st)
    # top-up with plain volume order if fewer than k stores exist
    for i in order:
        if len(picked) >= k:
            break
        sid = series_ids[int(i)]
        if sid not in picked:
            picked.append(sid)
    return picked[:k]


def _package_versions() -> dict[str, str]:
    from importlib.metadata import version

    out: dict[str, str] = {}
    for pkg in ("statsforecast", "mlforecast", "lightgbm", "datasetsforecast", "polars", "numpy"):
        try:
            out[pkg] = version(pkg)
        except Exception:  # pragma: no cover - package metadata always present
            out[pkg] = "unknown"
    return out


def write_m5_artifacts(result: M5Result, reports_dir: Path) -> None:
    """Persist metrics/probabilistic/evaluation_metadata JSON + the demo sidecar.

    The sidecar parquet carries the per-series catalog curves (actuals, every
    shipped candidate, the lgbm band edges) at the test origins, plus the
    full-panel pooled test WAPEs in its schema metadata for the payload's
    drift guard.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    from demand_forecasting.evaluate import _json_safe

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "metrics.json").write_text(
        json.dumps(_json_safe(result.metrics), indent=2) + "\n"
    )
    (reports_dir / "probabilistic.json").write_text(
        json.dumps(_json_safe(result.probabilistic), indent=2) + "\n"
    )
    (reports_dir / "evaluation_metadata.json").write_text(
        json.dumps(_json_safe(result.metadata), indent=2) + "\n"
    )
    table = pa.Table.from_pandas(result.catalog_frame, preserve_index=False)
    meta = {key.encode(): json.dumps(value).encode() for key, value in result.catalog_meta.items()}
    table = table.replace_schema_metadata({**dict(table.schema.metadata or {}), **meta})
    pq.write_table(table, reports_dir / CATALOG_FORECASTS_NAME)
    logger.info("m5 artifacts -> %s", reports_dir)
