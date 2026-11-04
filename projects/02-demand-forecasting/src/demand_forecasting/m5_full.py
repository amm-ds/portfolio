"""M5 full-panel experiment — protocol ``m5_full_v1`` (m5_full wave).

The headline metric of the M5 competition is the OFFICIAL hierarchical WRMSSE
over all 12 aggregation levels (42,840 series), not the flat per-series
metrics the subset track (``m5_track.py``, protocol ``m5_direct_v1``) reports.
This module is the full-scale study on the pinned 30,490-series panel under
``data_m5/raw/``: same feature pipeline and booster contract as the subset
track, official-style hierarchical scoring, and the wave-30 stability-screened
convex ensemble over a compact pool.

Protocol (machine-readable in evaluation_metadata.json):

- **Weekly rolling origins, end-anchored**: the LAST origin is
  ``n_dates - horizon - 1`` exactly, so the scored-once window is precisely
  the last 28 days of the panel (the M5 competition evaluation window,
  2016-05-23 → 2016-06-19 — the full panel extends through d_1969, unlike the
  subset track's lattice which leaves the final 5 days unscored); earlier
  origins step back 7 days. ``N_ORIGINS = 10`` by default: the first
  ``n_origins - 1`` are SELECTION (ensemble weights), the final origin is
  TEST — scored once, never read for selection. ``MIN_TRAIN_DAYS = 1096``
  (same floor as the subset track).
- **Series universe**: the full 30,490 panel by default; the deterministic
  ladder fallback (``series_cap=10000``: the top-1,000 items by total panel
  units x all 10 stores) is a CLI flag, selected by the wave's feasibility
  gate — see the module docstring of the wave plan.
- **Candidates**: ``seasonal_naive`` (vectorized floor, no statsforecast),
  ``lgbm`` (global LightGBM, committed params.yaml ``m5_lgbm`` values,
  mlforecast recursive strategy — the subset track's wave-25/27 feature
  space), ``lgbm_tweedie`` (same pipeline, objective ``tweedie`` at variance
  power 1.1), ``lgbm_pool_store`` / ``lgbm_pool_storecat`` /
  ``lgbm_pool_dept`` (pooled-global LightGBM: one fit per sorted group,
  same booster config; ``--pooled-strategy direct`` fits one model per
  (group, horizon) — the classic M5 direct-multi-horizon arm — while
  ``recursive`` reuses the subset track's mlforecast per-group fits;
  the feasibility gate decides which the overnight run can afford),
  ``auto_ets`` (statsforecast AutoETS, season 7), and ``convex_ensemble``
  (the headline).
- **Official-style hierarchical WRMSSE** (pure, hand-tested in
  ``tests/test_m5_full.py``): bottom forecasts aggregate bottom-up through
  all 12 levels (total / state / store / cat / dept / state x cat / state x dept
  / store x cat / store x dept / item / state x item / item x store — node sets from
  S_df, never hardcoded counts); per-node RMSSE uses the OFFICIAL M5
  denominator — the mean squared first difference of the node's TRAIN window
  (the subset track's naive-28 denominator is deliberately NOT reused here);
  node weights = revenue (units x sell_price, from the price exog) over the
  28 days preceding the scored window, aggregated bottom-up, normalized
  across all 42,840 nodes — equal total per level, revenue-weighted within a
  level, exactly the official scheme. Zero-denominator nodes are excluded
  with renormalization (counted, logged — the official data has none at
  aggregate levels).
- **Metrics per candidate**: official WRMSSE (hierarchy-wide, per origin +
  per-level breakdown), bottom-level pooled WAPE, bias, zero-day accuracy
  (pooled + intermittent class via ADI/CV² on real history), selection
  fold-stability (population std of the per-origin official WRMSSE over the
  selection origins).
- **Ensemble** (wave-30 screen, headline-metric variant): the pool is ranked
  on the selection origins by mean + 1.0 x population std of the per-origin
  OFFICIAL WRMSSE (computed exactly from the blended bottom forecasts
  re-aggregated through the hierarchy — a forecast-level blend metric, never
  a weighted mean of member metrics); the best three get simplex-grid
  weights (step 0.05) minimising the same screen, applied unchanged to every
  origin including test.
- **Honesty/determinism**: no candidate sees test rows at fit/selection
  time; LightGBM runs ``n_jobs=1`` + fixed seed + ``force_row_wise`` (the
  repo's byte-identity contract) in every arm; ``auto_ets`` MAY run
  multi-process (``--n-jobs-ets``, loky workers) — ETS model selection is
  closed-form and seed-free, so parallelism changes wall time only, never
  values; the seasonal_naive floor is numpy-vectorized; ensemble grids are
  lexicographic deterministic. The subset track (m5_track.py) and its
  artifacts are untouched — everything here reuses its helpers read-only.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from portfolio_core.io import sha256_of
from portfolio_core.logging import get_logger

from demand_forecasting.intermittent import classify_demand
from demand_forecasting.m5_data import encode_events, split_exogenous
from demand_forecasting.m5_track import (
    ENSEMBLE_GRID_STEP,
    ENSEMBLE_STABILITY_LAMBDA,
    HORIZON,
    MIN_TRAIN_DAYS,
    NAIVE,
    SEED,
    _actual_window,
    _attach_panel_features,
    _group_map,
    _lgbm_forecast,
    _lgbm_pool_forecast,
    _lgbm_tweedie_forecast,
    _mlforecast_for,
    _series_train_history,
    bias_metric,
    load_m5_lgbm_params,
    wape,
    zero_day_accuracy,
)

logger = get_logger(__name__)

PROTOCOL = "m5_full_v1"
N_ORIGINS = 10
ORIGIN_SPACING_DAYS = 7
DENSE_CLASSES = ("smooth", "erratic")
STATISTICAL_CANDIDATES = (NAIVE,)
POOL_CANDIDATES = (
    "lgbm",
    "lgbm_tweedie",
    "lgbm_pool_store",
    "lgbm_pool_storecat",
    "lgbm_pool_dept",
    "auto_ets",
)
CANDIDATES = (*STATISTICAL_CANDIDATES, *POOL_CANDIDATES, "convex_ensemble")
ENSEMBLE_POOL = POOL_CANDIDATES
ENSEMBLE_TOP_K = 3
#: official WRMSSE needs >= 29 days of history per bottom series at the first
#: origin (lag-28 features + the first-difference denominator); the panel's
#: latest first-sale date leaves ~31 days at origin 1877, so this is a real
#: but thin floor — asserted loudly on drift.
MIN_SERIES_HISTORY_DAYS = 29

#: The 12 official M5 aggregation levels: (name, static columns of S_df).
#: Node SETS are always derived from S_df at runtime (never the counts below —
#: toy fixtures have their own cardinalities); the counts are the audit
#: expectation for the real 30,490-series panel, checked by the test suite.
M5_LEVELS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("total", ()),
    ("state", ("state_id",)),
    ("store", ("store_id",)),
    ("cat", ("cat_id",)),
    ("dept", ("dept_id",)),
    ("state_cat", ("state_id", "cat_id")),
    ("state_dept", ("state_id", "dept_id")),
    ("store_cat", ("store_id", "cat_id")),
    ("store_dept", ("store_id", "dept_id")),
    ("item", ("item_id",)),
    ("state_item", ("state_id", "item_id")),
    ("item_store", ("item_id", "store_id")),
)
FULL_PANEL_LEVEL_COUNTS = {
    "total": 1,
    "state": 3,
    "store": 10,
    "cat": 3,
    "dept": 7,
    "state_cat": 9,
    "state_dept": 21,
    "store_cat": 30,
    "store_dept": 70,
    "item": 3049,
    "state_item": 9147,
    "item_store": 30490,
}

#: sha256 pins of the full panel (Phase 0, 2026-11-02): the downloaded zip
#: and the datasetsforecast parquet cache under data_m5/raw/.
FULL_CHECKSUMS = {
    "m5/datasets/m5.zip": "cc704ba15d6802f8262e6ec7d4c6041e4ad6366a94365e8c84f721e450eed774",
    ".cache/m5/m5/Y_df.parquet": "bdd4c6fd4c6544188212e805fb5708b1431049a6dae72d11e51842de8310d875",
    ".cache/m5/m5/X_df.parquet": "b2a4400de3dc8e267edaa3936224a0a51b544cef654bd2e535f199b2913ab0af",
    ".cache/m5/m5/S_df.parquet": "856d9780b1ec0f1bab129d7aa8390a86f9c14ad177665074deb3368427c7df97",
}

METRIC_DEFINITIONS = {
    "official_wrmsse": "official M5 hierarchical WRMSSE: bottom forecasts aggregate "
    "bottom-up through all 12 levels (42,840 nodes on the real panel); per-node "
    "RMSSE = sqrt(mean squared error over the 28 scored days / mean squared first "
    "difference of the node's TRAIN window); node weight = revenue (units x "
    "sell_price) over the 28 days preceding the scored window, aggregated "
    "bottom-up and normalized across all nodes (equal total per level — the "
    "official scheme); zero-denominator nodes excluded with renormalization "
    "(counted)",
    "bottom_wape": "pooled WAPE over the 30,490 bottom series' scored cells: "
    "sum |err| / sum actual",
    "bias": "mean(forecast - actual) / mean(actual) over the bottom scored "
    "cells (positive = over-forecast); NaN when the scored volume is 0",
    "stability": "population std (ddof=0) of the per-origin official WRMSSE "
    "across the selection origins",
    "zero_day_accuracy": "share of bottom scored points with actual == 0 whose "
    "forecast is < 0.5 — pooled and for the intermittent ADI/CV² class; NaN "
    "when the block has no zero-actual points",
    "ensemble_screen": "mean + 1.0 x population std of the per-origin official "
    "WRMSSE across the selection origins, computed exactly from the "
    "forecast-level convex blend re-aggregated through the hierarchy",
}


@dataclass
class M5FullResult:
    """In-memory result: the JSON-ready blocks of the full-panel run."""

    metrics: dict[str, Any]
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Loader (sha-pinned, like m5_data.load_m5_subset)
# ---------------------------------------------------------------------------


def verify_m5_full_checksums(raw_dir: Path) -> dict[str, str]:
    """Check the downloaded zip + parquet cache against their pins.

    Missing files and pin mismatches raise ValueError (the track must never
    silently evaluate a drifted dataset), exactly like
    :func:`demand_forecasting.m5_data.verify_m5_checksums` does for the subset.
    """
    out: dict[str, str] = {}
    for rel, expected in FULL_CHECKSUMS.items():
        path = Path(raw_dir) / rel
        if not path.exists():
            raise ValueError(f"missing M5 full-panel file: {path}")
        actual = sha256_of(path)
        if actual != expected:
            raise ValueError(
                f"M5 full-panel checksum changed for {rel}: {actual}. "
                "The pinned panel no longer matches the Phase-0 pin."
            )
        out[rel] = actual
    return out


def load_m5_full(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load (Y, X, S) of the pinned full panel from the datasetsforecast cache.

    ``raw_dir`` is the ``data_m5/raw`` directory holding ``m5/datasets/m5.zip``
    and ``.cache/m5/m5/*.parquet``. Checks the Phase-0 pins, asserts the long
    schema, casts to pandas, and validates the panel shape generically (series
    run contiguously to the panel end; enough history for the lag-28 features
    at any legal origin). Generic — not hardcoded to 30,490/1,969 — so the
    toy fixtures in the tests exercise the same code path; the real-panel
    cardinalities are pinned by the checksums and asserted in the test suite.
    """
    raw_dir = Path(raw_dir)
    verify_m5_full_checksums(raw_dir)
    cache = raw_dir / ".cache" / "m5" / "m5"
    y = pd.read_parquet(cache / "Y_df.parquet")
    x = pd.read_parquet(cache / "X_df.parquet")
    s = pd.read_parquet(cache / "S_df.parquet")
    if tuple(y.columns) != ("unique_id", "ds", "y"):
        raise ValueError(f"full-panel Y schema drifted: {y.columns.tolist()}")
    if tuple(s.columns) != ("unique_id", "item_id", "dept_id", "cat_id", "store_id", "state_id"):
        raise ValueError(f"full-panel S schema drifted: {s.columns.tolist()}")
    expected_x = (
        "unique_id",
        "ds",
        "event_name_1",
        "event_type_1",
        "event_name_2",
        "event_type_2",
        "snap_CA",
        "snap_TX",
        "snap_WI",
        "sell_price",
    )
    if tuple(x.columns) != expected_x:
        raise ValueError(f"full-panel X schema drifted: {x.columns.tolist()}")
    for frame in (y, x):
        frame["ds"] = pd.to_datetime(frame["ds"])
        frame.sort_values(["unique_id", "ds"], inplace=True, ignore_index=True)
    n_series = s["unique_id"].nunique()
    if y["unique_id"].nunique() != n_series or x["unique_id"].nunique() != n_series:
        raise ValueError("Y/X/S disagree on the series set")
    per_series = y.groupby("unique_id")["ds"].agg(["min", "max", "count"])
    if not (per_series["max"] == y["ds"].max()).all():
        raise ValueError("every series must run to the panel end date")
    if bool((per_series["count"] != (per_series["max"] - per_series["min"]).dt.days + 1).any()):
        raise ValueError("series must be contiguous (no mid-series holes)")
    logger.info(
        "m5 full panel: %d series, %d days (%s..%s), %d rows, first-sale span %s..%s",
        n_series,
        y["ds"].nunique(),
        y["ds"].min().date(),
        y["ds"].max().date(),
        len(y),
        per_series["min"].min().date(),
        per_series["min"].max().date(),
    )
    return y, x, s


def apply_series_cap(
    y: pd.DataFrame, x: pd.DataFrame, s: pd.DataFrame, cap: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """The deterministic ladder fallback: keep the top-``cap // 10`` items by
    total panel units (ties → item_id) across all 10 stores.

    Deterministic and volume-anchored — every kept item contributes all its
    store series, so the hierarchy structure stays complete (no orphan
    store/category nodes). The actual kept count is logged and recorded (a
    partially-listed item would land below the nominal cap).
    """
    per_store = cap // 10
    units = y.groupby("unique_id")["y"].sum()
    items = s.drop_duplicates("unique_id")[["unique_id", "item_id"]].set_index("unique_id")
    item_units = units.groupby(items["item_id"]).sum()
    keep_items = set(
        item_units.sort_index().sort_values(ascending=False, kind="stable").index[:per_store]
    )
    keep_ids = sorted(sid for sid in units.index if items.loc[sid, "item_id"] in keep_items)
    keep = set(keep_ids)
    logger.info(
        "m5 full ladder: keeping %d items -> %d series (cap %d)",
        len(keep_items),
        len(keep_ids),
        cap,
    )
    return (
        y[y["unique_id"].isin(keep)].copy(),
        x[x["unique_id"].isin(keep)].copy(),
        s[s["unique_id"].isin(keep)].copy(),
    )


# ---------------------------------------------------------------------------
# Hierarchy: aggregation, denominators, revenue weights (pure, hand-testable)
# ---------------------------------------------------------------------------


def build_aggregation(s_meta: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Bottom-up aggregation operators for all 12 levels.

    ``s_meta`` is the S frame (one row per bottom series). For each level:
    ``node_ids`` (sorted "_"-joined static values; ``["total"]`` for the
    root) and ``matrix`` — a CSR (n_nodes, n_bottom) 0/1 matrix whose row j
    sums the bottom series of node j. Node sets derive from the data, never
    from hardcoded counts. Pure and deterministic; hand-verified on a tiny
    3-item x 2-store fixture in the tests.
    """
    from scipy import sparse  # type: ignore[import-untyped]

    s_sorted = s_meta.drop_duplicates("unique_id").sort_values("unique_id", ignore_index=True)
    bottom_ids = s_sorted["unique_id"].tolist()
    out: dict[str, dict[str, Any]] = {}
    for name, cols in M5_LEVELS:
        if not cols:
            node_ids = ["total"]
            rows = np.zeros(len(bottom_ids), dtype=np.int32)
            cols_idx = np.arange(len(bottom_ids), dtype=np.int32)
        else:
            keys = s_sorted[list(cols)].astype(str).agg("_".join, axis=1).to_numpy()
            node_ids = sorted(set(keys.tolist()))
            node_pos = {k: i for i, k in enumerate(node_ids)}
            rows = np.array([node_pos[k] for k in keys], dtype=np.int32)
            cols_idx = np.arange(len(bottom_ids), dtype=np.int32)
        mat = sparse.csr_matrix(
            (np.ones(len(bottom_ids), dtype=np.float32), (rows, cols_idx)),
            shape=(len(node_ids), len(bottom_ids)),
        )
        out[name] = {"node_ids": node_ids, "matrix": mat}
    return out


def aggregation_stack(
    agg: dict[str, dict[str, Any]],
) -> tuple[np.ndarray, list[str], list[str], dict[str, slice]]:
    """The 42,840-node (on the real panel) block-stacked aggregation.

    Returns ``(a_all, node_ids, levels, level_slices)``: CSR (n_nodes_all,
    n_bottom) with one block per level in :data:`M5_LEVELS` order, the flat
    node id list, and the slice of each level's block. Bottom-up aggregation
    of ANY bottom-aligned matrix (actuals, forecasts, revenue) is ``a_all @ x``.
    """
    from scipy import sparse

    mats = [agg[name]["matrix"] for name, _ in M5_LEVELS]
    node_ids: list[str] = []
    slices: dict[str, slice] = {}
    start = 0
    for (name, _), block in zip(M5_LEVELS, mats, strict=True):
        n = block.shape[0]
        slices[name] = slice(start, start + n)
        node_ids.extend(agg[name]["node_ids"])
        start += n
    return sparse.vstack(mats, format="csr"), node_ids, [n for n, _ in M5_LEVELS], slices


def wide_panel(
    y: pd.DataFrame, series_ids: list[str], dates: np.ndarray, value_col: str = "y"
) -> np.ndarray:
    """(n_series, n_dates) float32 calendar grid of ``value_col``; 0 before a
    series' first sale.

    The panel is contiguous only FROM each series' first sale (the loader
    enforces no mid-series holes), so the reindexed grid's remaining NaNs are
    exactly the pre-introduction days — filled with 0, the official M5
    convention (the raw CSVs are full-length): every aggregation node spans
    the full calendar, and the first-difference denominators match the
    official full-length series.
    """
    grid = y.pivot(index="unique_id", columns="ds", values=value_col).reindex(
        index=series_ids, columns=pd.DatetimeIndex(dates)
    )
    if grid.isna().any().any():
        grid = grid.fillna(0.0)
    arr: np.ndarray = grid.to_numpy(dtype=np.float32)
    return arr


def first_diff_scale(train_nodes: np.ndarray) -> np.ndarray:
    """Official M5 denominator: mean squared first difference of the TRAIN
    window, per node (NaN for windows shorter than 2 days)."""
    if train_nodes.shape[1] < 2:
        return np.full(train_nodes.shape[0], np.nan)
    d = np.diff(train_nodes, axis=1)
    return np.mean(d * d, axis=1)


def revenue_weights(
    y_wide: np.ndarray, price_wide: np.ndarray, window: slice, a_all: Any
) -> np.ndarray:
    """Official-scheme node weights: revenue over the 28-day window preceding
    the scored block (train-side — leakage-free), aggregated bottom-up,
    normalized across ALL nodes (so each level carries equal total weight).
    """
    rev_bottom = (y_wide[:, window] * price_wide[:, window]).sum(axis=1)
    rev_nodes = np.asarray(a_all @ rev_bottom).ravel()
    total = float(rev_nodes.sum())
    if total <= 0:
        raise ValueError("revenue weights: the window's total revenue is 0")
    return rev_nodes / total


def wrmsse_nodes(
    err_nodes: np.ndarray, scale: np.ndarray, weights: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Per-node RMSSE and its weight, zero/NaN-denominator nodes excluded.

    Returns ``(rmsse, w)`` where invalid nodes get NaN/0 — the official score
    sums ``w * rmsse`` over valid nodes only (weights renormalized over the
    valid set by :func:`official_wrmsse`).
    """
    num = np.mean(err_nodes * err_nodes, axis=1)
    valid = np.isfinite(scale) & (scale > 0)
    rmsse = np.full(err_nodes.shape[0], np.nan)
    rmsse[valid] = np.sqrt(num[valid] / scale[valid])
    w = np.where(valid, weights, 0.0)
    return rmsse, w


def official_wrmsse(
    pred_bottom: np.ndarray,
    actual_nodes: np.ndarray,
    scale: np.ndarray,
    weights: np.ndarray,
    a_all: Any,
) -> tuple[float, int]:
    """The official-style hierarchical WRMSSE of one (n_bottom, h) forecast.

    ``actual_nodes``/``scale`` are precomputed per origin (hierarchy-wide);
    the forecast aggregates bottom-up here. Returns (score, n_excluded_nodes).
    """
    pred_nodes = np.asarray(a_all @ pred_bottom)
    rmsse, w = wrmsse_nodes(pred_nodes - actual_nodes, scale, weights)
    total_w = float(w.sum())
    if total_w <= 0:
        return float("nan"), int((~(np.isfinite(scale) & (scale > 0))).sum())
    return float(np.sum(w * np.where(np.isnan(rmsse), 0.0, rmsse)) / total_w), int(
        (~(np.isfinite(scale) & (scale > 0))).sum()
    )


def per_level_wrmsse(
    pred_bottom: np.ndarray,
    actual_nodes: np.ndarray,
    scale: np.ndarray,
    weights: np.ndarray,
    a_all: Any,
    level_slices: dict[str, slice],
) -> dict[str, float]:
    """Official WRMSSE restricted to each level (weights renormalized within
    the level) — the per-level breakdown of the report."""
    pred_nodes = np.asarray(a_all @ pred_bottom)
    rmsse, w = wrmsse_nodes(pred_nodes - actual_nodes, scale, weights)
    out: dict[str, float] = {}
    for name, sl in level_slices.items():
        wl = w[sl]
        tot = float(wl.sum())
        if tot <= 0:
            out[name] = float("nan")
            continue
        out[name] = float(np.sum(wl * np.where(np.isnan(rmsse[sl]), 0.0, rmsse[sl])) / tot)
    return out


# ---------------------------------------------------------------------------
# Origin plan
# ---------------------------------------------------------------------------


def m5_full_origins(
    n_dates: int, n_origins: int, horizon: int, min_train: int, spacing_days: int
) -> list[int]:
    """End-anchored weekly origin plan: the LAST origin is ``n_dates - horizon
    - 1`` exactly (the scored-once window is precisely the last ``horizon``
    days of the panel, whatever they are), earlier origins step back at
    ``spacing_days``. Origin o trains on days 0..o (needs ``o + 1 >=
    min_train``). Pure; unit-tested."""
    last = n_dates - horizon - 1
    first = last - spacing_days * (n_origins - 1)
    if last < min_train - 1:
        raise ValueError(
            f"panel too short: {n_dates} dates (min_train={min_train}, horizon={horizon})"
        )
    if first < min_train - 1:
        raise ValueError(
            f"not enough history for {n_origins} origins spaced {spacing_days}d "
            f"with min_train={min_train}: first origin would be day {first}"
        )
    return list(range(first, last + 1, spacing_days))


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


def _seasonal_naive_forecast(train_wide: np.ndarray, horizon: int) -> np.ndarray:
    """Vectorized seasonal-naive floor: repeat the train window's last 7 days.

    ``train_wide`` is the (n_series, n_train_days) calendar grid (pre-
    introduction zeros included, the official convention). Pure numpy,
    no statsforecast — the batch dependency stays out of the floor.
    """
    if train_wide.shape[1] < 7:
        raise ValueError("seasonal_naive needs at least 7 days of history")
    last_week = train_wide[:, -7:]
    reps = int(np.ceil(horizon / 7))
    return np.tile(last_week, (1, reps))[:, :horizon].astype(float)


def _auto_ets_forecast(
    train: pd.DataFrame, series_ids: list[str], horizon: int, n_jobs: int
) -> np.ndarray:
    """auto_ets via statsforecast (AutoETS season 7), re-indexed to the caller's
    series order. Parallel workers are allowed in principle (ETS selection is
    closed-form and seed-free — determinism note in the module docstring);
    Phase-0 finding on this host: loky spawn under ``uv run`` HANGS the batch
    (verified twice), so the committed/overnight runs use ``n_jobs=1`` — the
    per-series fallback after a batch failure stays the documented degradation
    (fixed loop order, no RNG)."""
    from statsforecast import StatsForecast
    from statsforecast.models import AutoETS

    n_series = len(series_ids)
    idx = {sid: i for i, sid in enumerate(series_ids)}
    try:
        sf = StatsForecast(
            models=[AutoETS(season_length=7, alias="auto_ets")], freq="D", n_jobs=n_jobs
        )
        fc: Any = sf.fit_predict(
            h=horizon, df=train, id_col="unique_id", time_col="ds", target_col="y"
        )
        # fc is LONG: one row per (series, horizon step) — statsforecast's
        # _make_future_df repeats each uid h times, series-major. The model
        # column reshapes to (n_series, h) in that same order.
        mat_any = fc["auto_ets"].to_numpy(dtype=float).reshape(-1, horizon)
        # Wave-32 fix: the pre-fix code argsorted the per-ROW positions (one
        # per fc row, values 0..n_series*h-1) into the (n_series, h) matrix —
        # the first out-of-bounds index is exactly n_series ("index 30490 is
        # out of bounds for axis 0 with size 30490" at the full panel), the
        # batch failed at EVERY origin and the per-series fallback silently
        # did the work (177 min/origin overnight). Collapse the row positions
        # to one per series (each series block is exactly h rows) BEFORE the
        # argsort.
        order = fc["unique_id"].map(idx).to_numpy().reshape(-1, horizon)[:, 0]
        mat: np.ndarray = mat_any[np.argsort(order, kind="stable")]
        if mat.shape != (n_series, horizon):
            raise ValueError(f"auto_ets batch shape drifted: {mat.shape} != {(n_series, horizon)}")
        if np.isnan(mat).any():
            raise ValueError("auto_ets produced NaNs at this origin")
        return mat
    except Exception as exc:
        logger.warning("batch auto_ets failed (%s); per-series fallback", exc)
    out = np.zeros((n_series, horizon))
    for i, sid in enumerate(series_ids):
        s_train = train[train["unique_id"] == sid]
        try:
            sf = StatsForecast(
                models=[AutoETS(season_length=7, alias="auto_ets")], freq="D", n_jobs=1
            )
            fc = sf.fit_predict(
                h=horizon, df=s_train, id_col="unique_id", time_col="ds", target_col="y"
            )
            out[i] = fc["auto_ets"].to_numpy(dtype=float)
        except Exception as exc:
            logger.warning("auto_ets failed on %s (%s); seasonal_naive fallback", sid, exc)
            out[i] = np.resize(s_train["y"].to_numpy(dtype=float)[-7:], horizon)
    return out


def _direct_prep(train: pd.DataFrame, hist_exog: pd.DataFrame, seed: int) -> Any:
    """The shared mlforecast-preprocessed frame for the direct pooled arms.

    One preprocess pass per origin serves all (group, horizon) fits of the
    three pooled arms — the feature space is the subset track's exact
    ``_mlforecast_for`` config (lags 1/7/14/21/28, rolling means/stds,
    expanding mean, calendar, exog + panel statics attached upstream).
    """
    from lightgbm import LGBMRegressor

    train_m = train.merge(hist_exog, on=["unique_id", "ds"], how="left", validate="1:1")
    if train_m.drop(columns=["unique_id", "ds", "y"]).isna().any().any():
        raise ValueError("exogenous merge produced NaNs in the direct-prep frame")
    prep = _mlforecast_for(
        LGBMRegressor(
            random_state=seed, verbosity=-1, n_jobs=1, force_row_wise=True, n_estimators=10
        )
    ).preprocess(train_m, id_col="unique_id", time_col="ds", target_col="y", static_features=[])
    return prep.sort_values(["unique_id", "ds"], ignore_index=True)


def _lgbm_pool_direct_forecast(
    prep: pd.DataFrame,
    seed: int,
    *,
    series_ids: list[str],
    groups: dict[str, list[str]],
    lgbm_params: dict[str, Any],
    name: str,
    horizon: int = HORIZON,
    n_estimators: int | None = None,
) -> np.ndarray:
    """Direct per-horizon pooled LightGBM: ONE fit per (sorted group, h).

    The classic M5 direct-multi-horizon arm: every horizon h = 1..28 gets its
    own fit on the group's rows (features at day t -> y_{t+h}), sharing the
    origin's single preprocessed frame; the prediction rows are each series'
    last train row (features known at the origin). Determinism: groups iterate
    in sorted-key order, h in fixed 1..28 order, every fit n_jobs=1 + fixed
    seed + force_row_wise. A series whose last-row features are NaN (shorter
    than the deepest lag window — only possible for < ~85 days of history)
    degrades to that series' seasonal_naive row, documented and counted.
    """
    from lightgbm import LGBMRegressor

    params = dict(lgbm_params)
    if n_estimators is not None:
        params["n_estimators"] = n_estimators
    feature_cols = [c for c in prep.columns if c not in ("unique_id", "ds", "y")]
    uids = prep["unique_id"].to_numpy()
    # prep is sorted by (unique_id, ds): per-series contiguous blocks
    change = np.empty(len(uids), dtype=bool)
    change[0] = True
    change[1:] = uids[1:] != uids[:-1]
    starts = np.flatnonzero(change)
    lengths = np.diff(np.append(starts, len(uids)))
    block_start = dict(zip(uids[starts].tolist(), starts.tolist(), strict=True))
    block_len = dict(zip(uids[starts].tolist(), lengths.tolist(), strict=True))

    out = np.empty((len(series_ids), horizon), dtype=float)
    pos = {sid: i for i, sid in enumerate(series_ids)}
    n_fallback = 0
    for gkey in sorted(groups):
        members = sorted(groups[gkey])
        row_idx = np.concatenate(
            [np.arange(block_start[m], block_start[m] + block_len[m]) for m in members]
        )
        sub = prep.iloc[row_idx]
        sub_uid = sub["unique_id"].to_numpy()
        y_all = sub["y"].to_numpy(dtype=float)
        x_all = sub[feature_cols].to_numpy(dtype=float)
        # per-series boundaries inside the group frame (member-sorted order)
        g_change = np.empty(len(sub_uid), dtype=bool)
        g_change[0] = True
        g_change[1:] = sub_uid[1:] != sub_uid[:-1]
        g_starts = np.flatnonzero(g_change)
        g_lengths = np.diff(np.append(g_starts, len(sub_uid)))
        last_rows = g_starts + g_lengths - 1
        # rows whose features are fully observed (lag warmup) — same mask for
        # every h; per-h target availability is applied on top
        feat_ok = np.isfinite(x_all).all(axis=1)
        pred_x = x_all[last_rows]
        pred_ok = np.isfinite(pred_x).all(axis=1)
        g_pred = np.empty((len(members), horizon), dtype=float)
        for h in range(1, horizon + 1):
            # target: y shifted -h within each series block (row t -> y[t+h])
            y_h = np.full(len(y_all), np.nan)
            for st, ln in zip(g_starts, g_lengths, strict=True):
                y_h[st : st + ln - h] = y_all[st + h : st + ln]
            fit_mask = feat_ok & np.isfinite(y_h)
            model = LGBMRegressor(
                random_state=seed, verbosity=-1, n_jobs=1, force_row_wise=True, **params
            )
            model.fit(x_all[fit_mask], y_h[fit_mask])
            g_pred[:, h - 1] = model.predict(pred_x)
        # NaN-feature prediction rows -> seasonal_naive degradation (counted)
        if not pred_ok.all():
            n_fallback += int((~pred_ok).sum())
            last7 = np.stack([y_all[lr - 6 : lr + 1] for lr in last_rows])
            naive_rows = np.tile(last7, (1, 4))[:, :horizon]
            g_pred[~pred_ok] = naive_rows[~pred_ok]
        for j, sid in enumerate(members):
            out[pos[sid]] = g_pred[j]
    if not np.isfinite(out).all():
        raise ValueError(f"{name} forecast contains non-finite values")
    if n_fallback:
        logger.warning(
            "%s: %d series fell back to seasonal_naive (short history)", name, n_fallback
        )
    clipped: np.ndarray = np.clip(out, 0.0, None)
    return clipped


# ---------------------------------------------------------------------------
# Ensemble (wave-30 stability screen on the official WRMSSE)
# ---------------------------------------------------------------------------


def _screen(vals: np.ndarray) -> float:
    """mean + 1.0 x population std over per-origin official WRMSSEs
    (NaN propagates -> ranks last)."""
    vals = np.asarray(vals, dtype=float)
    return float(np.mean(vals) + ENSEMBLE_STABILITY_LAMBDA * np.std(vals))


def _blend_wrmsse_per_origin(
    member_preds: list[np.ndarray], weights_w: np.ndarray, origin_ctx: dict[int, dict[str, Any]]
) -> np.ndarray:
    """Per-origin official WRMSSE of a convex forecast-level blend — the exact
    blend metric (bottom forecasts combine, THEN re-aggregate through the
    hierarchy), one entry per origin in ``origin_ctx`` order."""
    out = np.empty(len(origin_ctx))
    for k, o in enumerate(origin_ctx):
        combo = np.zeros_like(member_preds[0][k])
        for wi, p in zip(weights_w, member_preds, strict=True):
            combo += wi * p[k]
        out[k] = origin_ctx[o]["wrmsse_fn"](combo)
    return out


def screened_ensemble(
    forecasts: dict[str, dict[int, np.ndarray]],
    selection: list[int],
    origin_ctx: dict[int, dict[str, Any]],
    *,
    pool: tuple[str, ...] = ENSEMBLE_POOL,
    top_k: int = ENSEMBLE_TOP_K,
) -> tuple[list[str], np.ndarray, dict[str, dict[str, float]]]:
    """Wave-30 screen on the official WRMSSE: rank the pool on the selection
    origins by mean + 1.0 x std of the per-origin official WRMSSE; the top
    ``top_k`` get simplex-grid weights (step 0.05, lexicographic walk, ties ->
    first grid point) minimising the same screen of the BLEND's per-origin
    WRMSSE, computed exactly from the forecast-level convex combination.
    Returns (members, weights, per-member screen stats); writes the blend into
    ``forecasts["convex_ensemble"]`` for EVERY origin (test included — the
    same convex combo, never re-fit on test). Deterministic; hand-testable.
    """
    per_origin = {
        c: np.array([origin_ctx[o]["wrmsse_fn"](forecasts[c][o]) for o in selection]) for c in pool
    }
    screen = {
        c: {"mean": float(np.mean(v)), "std": float(np.std(v)), "score": _screen(v)}
        for c, v in per_origin.items()
    }
    ranked = sorted(
        pool,
        key=lambda c: (
            float("inf") if screen[c]["score"] != screen[c]["score"] else screen[c]["score"],
            c,
        ),
    )
    members = ranked[:top_k]
    member_preds = [np.stack([forecasts[m][o] for o in selection]) for m in members]
    grid = np.round(np.arange(0.0, 1.0 + 1e-9, ENSEMBLE_GRID_STEP), 2)
    best_w: np.ndarray | None = None
    best = float("inf")
    k = len(members)

    def _walk(depth: int, prefix: list[float]) -> None:
        nonlocal best_w, best
        if depth == k - 1:
            w = np.array([*prefix, 1.0 - sum(prefix)])
            if w[-1] < -1e-9:
                return
            w = np.clip(w, 0.0, 1.0)
            sel_ctx = {o: origin_ctx[o] for o in selection}
            s = _screen(_blend_wrmsse_per_origin(member_preds, w, sel_ctx))
            if s != s:
                s = float("inf")  # NaN screen ranks last
            if s < best - 1e-12:
                best, best_w = s, w
            return
        for gval in grid:
            if sum(prefix) + gval > 1.0 + 1e-9:
                break
            _walk(depth + 1, [*prefix, float(gval)])

    _walk(0, [])
    if best_w is None:  # pragma: no cover - the all-zero prefix always fits
        raise ValueError("no point on the ensemble simplex grid")
    for o in forecasts[members[0]]:
        combo = np.zeros_like(forecasts[members[0]][o])
        for wi, member in zip(best_w, members, strict=True):
            combo += wi * forecasts[member][o]
        forecasts["convex_ensemble"][o] = combo
    logger.info(
        "m5_full ensemble: members %s screen %s weights %s",
        members,
        {c: round(v["score"], 4) for c, v in screen.items()},
        {m: round(float(wi), 2) for m, wi in zip(members, best_w, strict=True)},
    )
    return members, best_w, screen


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------


def _package_versions() -> dict[str, str]:
    from importlib.metadata import version

    out: dict[str, str] = {}
    for pkg in ("statsforecast", "mlforecast", "lightgbm", "datasetsforecast", "numpy"):
        try:
            out[pkg] = version(pkg)
        except Exception:  # pragma: no cover - package metadata always present
            out[pkg] = "unknown"
    return out


# ---------------------------------------------------------------------------
# Shared panel context + per-origin candidate fits (full track AND catalog run)
# ---------------------------------------------------------------------------


@dataclass
class _FullPanel:
    """The static context of one m5_full evaluation: the loaded (and
    optionally ladder-capped) frames plus the hierarchy operators, wide grids,
    encoded exog, pooled-group maps and booster params every origin fit
    needs. Built once by :func:`_prepare_panel` and shared by the full track
    and the wave-32 catalog run so both fit candidates on the IDENTICAL panel
    context."""

    y_all: pd.DataFrame
    x_all: pd.DataFrame
    s_all: pd.DataFrame
    series_ids: list[str]
    n_series: int
    dates: np.ndarray
    n_dates: int
    agg: dict[str, dict[str, Any]]
    a_all: Any
    node_ids: list[str]
    level_names: list[str]
    level_slices: dict[str, slice]
    y_wide: np.ndarray
    x_wide: np.ndarray
    x_enc: pd.DataFrame
    s_meta: pd.DataFrame
    group_maps: dict[str, dict[str, list[str]]]
    lgbm_params: dict[str, Any]


def _prepare_panel(
    raw_dir: Path,
    *,
    series_cap: int | None,
    seed: int,
    params_path: Path | str,
    n_estimators: int | None,
) -> _FullPanel:
    """Load the pinned panel (checksum-gated, ladder cap applied) and build
    every static frame the origin fits share. Same inputs -> same context for
    the committed full track and the catalog run."""
    y_all, x_all, s_all = load_m5_full(Path(raw_dir))
    if series_cap is not None:
        y_all, x_all, s_all = apply_series_cap(y_all, x_all, s_all, series_cap)
    series_ids = sorted(y_all["unique_id"].unique().tolist())
    n_series = len(series_ids)
    dates = np.sort(y_all["ds"].unique())
    n_dates = len(dates)

    s_sorted = s_all.drop_duplicates("unique_id").sort_values("unique_id", ignore_index=True)
    if s_sorted["unique_id"].tolist() != series_ids:
        raise ValueError("S frame series set does not match Y")
    agg = build_aggregation(s_sorted)
    a_all, node_ids, level_names, level_slices = aggregation_stack(agg)
    y_wide = wide_panel(y_all, series_ids, dates)
    x_wide = wide_panel(
        x_all[["unique_id", "ds", "sell_price"]], series_ids, dates, value_col="sell_price"
    ).astype(np.float32)
    state_of = s_all.drop_duplicates("unique_id").set_index("unique_id")["state_id"]
    x_enc = encode_events(x_all, x_all["unique_id"].map(state_of))
    s_meta = s_all.drop_duplicates("unique_id").set_index("unique_id")
    lgbm_params = load_m5_lgbm_params(params_path)
    if n_estimators is not None:  # smoke-test override wins over params.yaml
        lgbm_params["n_estimators"] = n_estimators
    group_maps = {
        "lgbm_pool_store": _group_map(series_ids, s_meta, ("store_id",)),
        "lgbm_pool_storecat": _group_map(series_ids, s_meta, ("store_id", "cat_id")),
        "lgbm_pool_dept": _group_map(series_ids, s_meta, ("dept_id",)),
    }
    return _FullPanel(
        y_all=y_all,
        x_all=x_all,
        s_all=s_all,
        series_ids=series_ids,
        n_series=n_series,
        dates=dates,
        n_dates=n_dates,
        agg=agg,
        a_all=a_all,
        node_ids=node_ids,
        level_names=level_names,
        level_slices=level_slices,
        y_wide=y_wide,
        x_wide=x_wide,
        x_enc=x_enc,
        s_meta=s_meta,
        group_maps=group_maps,
        lgbm_params=lgbm_params,
    )


def _assert_min_history(y_all: pd.DataFrame, first_origin: pd.Timestamp) -> None:
    """The official-WRMSSE floor needs >= MIN_SERIES_HISTORY_DAYS of bottom
    history at the first origin — asserted loudly on drift."""
    first_origin_min_hist = first_origin - y_all.groupby("unique_id")["ds"].min().max()
    if int(first_origin_min_hist.days) < MIN_SERIES_HISTORY_DAYS:
        raise ValueError(
            f"shortest series history at the first origin is "
            f"{first_origin_min_hist.days}d < {MIN_SERIES_HISTORY_DAYS}d"
        )


def _origin_forecasts(
    panel: _FullPanel,
    o: int,
    *,
    seed: int,
    pooled_strategy: Literal["direct", "recursive"],
    n_estimators: int | None,
    n_jobs_ets: int,
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    """Fit EVERY candidate at origin ``o`` and return the ((n_series, h)
    matrices keyed by candidate — seasonal_naive included) plus the
    per-candidate wall-clock seconds. The pooled arms are panel-wide fits:
    they see the full series universe at this origin regardless of any later
    subsetting (the catalog run relies on this). Shared by the full track and
    the wave-32 catalog run so both produce the identical candidate set; the
    ensemble itself is blended by the callers (selection screen vs committed
    weights). Progress is logged per candidate."""
    odate = pd.Timestamp(panel.dates[o])
    train = panel.y_all[panel.y_all["ds"] <= odate]
    train_wide_o = panel.y_wide[:, : o + 1]
    hist_exog, future_exog = split_exogenous(panel.x_enc, panel.series_ids, odate, HORIZON)
    _attach_panel_features(train, hist_exog, future_exog, panel.s_all)

    preds: dict[str, np.ndarray] = {NAIVE: _seasonal_naive_forecast(train_wide_o, HORIZON)}
    times: dict[str, float] = {}
    t = time.time()
    preds["auto_ets"] = _auto_ets_forecast(train, panel.series_ids, HORIZON, n_jobs_ets)
    times["auto_ets"] = time.time() - t
    t = time.time()
    preds["lgbm"] = _lgbm_forecast(
        train,
        hist_exog,
        future_exog,
        seed,
        series_ids=panel.series_ids,
        lgbm_params=panel.lgbm_params,
    )
    times["lgbm"] = time.time() - t
    t = time.time()
    preds["lgbm_tweedie"] = _lgbm_tweedie_forecast(
        train,
        hist_exog,
        future_exog,
        seed,
        series_ids=panel.series_ids,
        lgbm_params=panel.lgbm_params,
        n_estimators=n_estimators,
    )
    times["lgbm_tweedie"] = time.time() - t
    if pooled_strategy == "direct":
        t = time.time()
        prep = _direct_prep(train, hist_exog, seed)
        t_prep = time.time() - t
        for name in ("lgbm_pool_store", "lgbm_pool_storecat", "lgbm_pool_dept"):
            t = time.time()
            preds[name] = _lgbm_pool_direct_forecast(
                prep,
                seed,
                series_ids=panel.series_ids,
                groups=panel.group_maps[name],
                lgbm_params=panel.lgbm_params,
                name=name,
                n_estimators=n_estimators,
            )
            times[name] = time.time() - t + t_prep
    else:
        for name in ("lgbm_pool_store", "lgbm_pool_storecat", "lgbm_pool_dept"):
            t = time.time()
            preds[name] = _lgbm_pool_forecast(
                train,
                hist_exog,
                future_exog,
                seed,
                series_ids=panel.series_ids,
                groups=panel.group_maps[name],
                lgbm_params=panel.lgbm_params,
                name=name,
            )
            times[name] = time.time() - t
    for name, dt in times.items():
        logger.info("m5_full candidate %s @ %s: %.1fs", name, odate.date(), dt)
    return preds, times


def run_m5_full(
    raw_dir: Path,
    *,
    n_origins: int = N_ORIGINS,
    series_cap: int | None = None,
    pooled_strategy: Literal["direct", "recursive"] = "direct",
    n_estimators: int | None = None,
    n_jobs_ets: int = 1,
    min_train: int = MIN_TRAIN_DAYS,
    seed: int = SEED,
    params_path: Path | str = "params.yaml",
) -> M5FullResult:
    """Run the m5_full_v1 track on the pinned full panel and return the
    JSON-ready blocks. ``series_cap`` activates the deterministic ladder
    fallback; ``pooled_strategy`` selects direct-per-horizon vs the subset
    track's recursive pooled fits (the feasibility gate decides which the
    overnight run can afford); ``n_estimators`` is the smoke-test override
    (wins over params.yaml for every lgbm arm, like the subset track).
    """
    t0 = time.time()
    panel = _prepare_panel(
        raw_dir,
        series_cap=series_cap,
        seed=seed,
        params_path=params_path,
        n_estimators=n_estimators,
    )
    y_all, s_all = panel.y_all, panel.s_all
    series_ids, dates, n_dates = panel.series_ids, panel.dates, panel.n_dates
    n_series = panel.n_series
    a_all, y_wide, x_wide = panel.a_all, panel.y_wide, panel.x_wide
    agg, node_ids = panel.agg, panel.node_ids
    level_names, level_slices = panel.level_names, panel.level_slices

    origins = m5_full_origins(n_dates, n_origins, HORIZON, min_train, ORIGIN_SPACING_DAYS)
    selection, test = origins[:-1], origins[-1:]
    origin_dates = [pd.Timestamp(dates[o]) for o in origins]
    _assert_min_history(y_all, origin_dates[0])
    logger.info(
        "m5_full track: %d series, %d origins (%d selection + 1 test), horizon %d, "
        "pooled=%s, min_train %d",
        n_series,
        len(origins),
        len(selection),
        HORIZON,
        pooled_strategy,
        min_train,
    )
    logger.info(
        "m5_full origins: selection %s | test %s",
        [str(d.date()) for d in origin_dates[:-1]],
        [str(d.date()) for d in origin_dates[-1:]],
    )

    # ---- per-origin hierarchy context (shared across candidates) ----
    origin_ctx: dict[int, dict[str, Any]] = {}
    for o in origins:
        train_nodes = np.asarray(a_all @ y_wide[:, : o + 1])
        actual_nodes = np.asarray(a_all @ y_wide[:, o + 1 : o + 1 + HORIZON])
        scale = first_diff_scale(train_nodes)
        w = revenue_weights(y_wide, x_wide, slice(o - HORIZON + 1, o + 1), a_all)
        ctx: dict[str, Any] = {
            "actual_nodes": actual_nodes,
            "scale": scale,
            "weights": w,
        }
        ctx["wrmsse_fn"] = lambda pred, ctx=ctx: official_wrmsse(
            pred, ctx["actual_nodes"], ctx["scale"], ctx["weights"], a_all
        )[0]
        origin_ctx[o] = ctx

    # ---- per-origin forecasts ----
    forecasts: dict[str, dict[int, np.ndarray]] = {c: {} for c in CANDIDATES}
    actuals: dict[int, np.ndarray] = {}
    runtime: dict[str, dict[int, float]] = {c: {} for c in CANDIDATES}
    for k, o in enumerate(origins):
        odate = pd.Timestamp(dates[o])
        t_o = time.time()
        actuals[o] = _actual_window(y_all, series_ids, odate, HORIZON)
        preds, times = _origin_forecasts(
            panel,
            o,
            seed=seed,
            pooled_strategy=pooled_strategy,
            n_estimators=n_estimators,
            n_jobs_ets=n_jobs_ets,
        )
        for name, mat in preds.items():
            forecasts[name][o] = mat
        for name, dt in times.items():
            runtime[name][o] = dt
        logger.info(
            "m5_full origin %d/%d (%s): %d series in %.1fs",
            k + 1,
            len(origins),
            odate.date(),
            n_series,
            time.time() - t_o,
        )

    # ---- volume classes on real history up to the LAST SELECTION origin
    hist = _series_train_history(y_all, series_ids, pd.Timestamp(dates[selection[-1]]))
    classes = {sid: classify_demand(hist[sid]) for sid in series_ids}
    dense_mask = np.array([classes[sid]["class"] in DENSE_CLASSES for sid in series_ids])
    inter_mask = ~dense_mask
    logger.info(
        "m5_full classes: %d dense, %d intermittent (ADI/CV2 on real history to %s)",
        int(dense_mask.sum()),
        int(inter_mask.sum()),
        pd.Timestamp(dates[selection[-1]]).date(),
    )

    # ---- ensemble on the selection origins (wave-30 screen, official metric)
    ens_members, ens_weights, ens_screen = screened_ensemble(forecasts, selection, origin_ctx)

    # ---- metric blocks ----
    def _candidate_block(cand: str, o: int) -> dict[str, Any]:
        pred = forecasts[cand][o]
        act = actuals[o]
        score, excluded = official_wrmsse(
            pred,
            origin_ctx[o]["actual_nodes"],
            origin_ctx[o]["scale"],
            origin_ctx[o]["weights"],
            a_all,
        )
        levels = per_level_wrmsse(
            pred,
            origin_ctx[o]["actual_nodes"],
            origin_ctx[o]["scale"],
            origin_ctx[o]["weights"],
            a_all,
            level_slices,
        )
        return {
            "official_wrmsse": score,
            "excluded_zero_scale_nodes": excluded,
            "per_level_wrmsse": levels,
            "bottom_wape": wape(act, pred),
            "bias": bias_metric(act, pred),
            "zero_day_accuracy": zero_day_accuracy(act, pred),
            "zero_day_accuracy_intermittent": (
                zero_day_accuracy(act[inter_mask], pred[inter_mask])
                if int(inter_mask.sum())
                else None
            ),
        }

    def _subset_block(subset: list[int]) -> dict[str, Any]:
        per_origin_scores = {
            c: np.array([origin_ctx[o]["wrmsse_fn"](forecasts[c][o]) for o in subset])
            for c in CANDIDATES
        }
        out: dict[str, Any] = {}
        for c in CANDIDATES:
            scores = per_origin_scores[c]
            block_blocks = [_candidate_block(c, o) for o in subset]
            out[c] = {
                "official_wrmsse_mean": float(np.mean(scores)),
                "official_wrmsse_per_origin": [float(v) for v in scores],
                "stability": float(np.std(scores)),
                "bottom_wape_mean": float(np.mean([b["bottom_wape"] for b in block_blocks])),
                "bias_mean": float(np.mean([b["bias"] for b in block_blocks])),
                "zero_day_accuracy_mean": float(
                    np.nanmean([b["zero_day_accuracy"] for b in block_blocks])
                ),
                "zero_day_accuracy_intermittent_mean": float(
                    np.nanmean(
                        [
                            b["zero_day_accuracy_intermittent"]
                            for b in block_blocks
                            if b["zero_day_accuracy_intermittent"] is not None
                        ]
                    )
                ),
            }
        return out

    def _test_block() -> dict[str, Any]:
        o = test[-1]
        return {c: _candidate_block(c, o) for c in CANDIDATES}

    metrics: dict[str, Any] = {
        "protocol": PROTOCOL,
        "candidates": list(CANDIDATES),
        "pooled_strategy": pooled_strategy,
        "series_universe": {
            "n_series": n_series,
            "ladder_cap": series_cap,
            "ladder_rule": (
                f"top-{series_cap // 10} items by total panel units "
                "(ties -> item_id) x all 10 stores"
                if series_cap is not None
                else None
            ),
        },
        "origins": {
            "dates": [str(d.date()) for d in origin_dates],
            "indices": [int(o) for o in origins],
            "selection": [str(d.date()) for d in origin_dates[:-1]],
            "test": [str(d.date()) for d in origin_dates[-1:]],
            "horizon_days": HORIZON,
            "min_train_days": min_train,
            "spacing_days": ORIGIN_SPACING_DAYS,
        },
        "hierarchy": {
            "levels": level_names,
            "n_nodes_total": len(node_ids),
            "level_node_counts": {name: len(agg[name]["node_ids"]) for name in level_names},
            "wrmsse": METRIC_DEFINITIONS["official_wrmsse"],
        },
        "classes": {
            "method": "Syntetos-Boylan ADI/CV2 on each series' REAL history up to the "
            "last SELECTION origin",
            "thresholds": {"adi": 1.32, "cv2": 0.49},
            "dense_quadrants": list(DENSE_CLASSES),
            "counts": {
                "dense": int(dense_mask.sum()),
                "intermittent": int(inter_mask.sum()),
            },
        },
        "ensemble": {
            "pool": list(ENSEMBLE_POOL),
            "selection_screen": ens_screen,
            "members": ens_members,
            "weights": [float(w) for w in ens_weights],
            "rule": "wave-30 screen on the official WRMSSE: best three of the pool by "
            "mean + 1.0 x population std of the per-origin official WRMSSE over the "
            "selection origins; simplex-grid weights (step 0.05, ties -> first grid "
            "point) minimising the same screen of the blend's per-origin WRMSSE, "
            "computed exactly from the forecast-level convex combination "
            "re-aggregated through the hierarchy",
        },
        "selection": _subset_block(selection),
        "test": _test_block(),
        "metric_definitions": METRIC_DEFINITIONS,
    }

    metadata = {
        "protocol": PROTOCOL,
        "dataset": {
            "dataset": "M5 Forecasting Competition (Walmart) — accuracy track FULL panel",
            "provenance_ref": str(Path(raw_dir) / "PROVENANCE.md"),
            "checksums_sha256": dict(FULL_CHECKSUMS),
            "observed_panel": {
                "date_start": str(y_all["ds"].min().date()),
                "date_end": str(y_all["ds"].max().date()),
                "n_days": int(n_dates),
                "n_rows": len(y_all),
                "n_series": n_series,
                "zero_share": float((y_all["y"] == 0).mean()),
                "stores": sorted(s_all["store_id"].unique().tolist()),
            },
            "citation": "Makridakis et al., M5 competition companion, International "
            "Journal of Forecasting (2022); research use with attribution per "
            "competition terms",
        },
        "split": {
            "n_origins": len(origins),
            "n_selection": len(selection),
            "n_test": 1,
            "origin_dates": [str(d.date()) for d in origin_dates],
            "selection_dates": [str(d.date()) for d in origin_dates[:-1]],
            "test_dates": [str(d.date()) for d in origin_dates[-1:]],
            "horizon_days": HORIZON,
            "min_train_days": min_train,
            "spacing_days": ORIGIN_SPACING_DAYS,
            "holdout_designation": "the final origin (last 28 days of the panel) is "
            "test, scored once; all earlier origins select (ensemble weights)",
        },
        "seeds": {"lgbm_random_state": seed},
        "package_versions": _package_versions(),
        "runtime_seconds": round(time.time() - t0, 3),
        "runtime_seconds_per_candidate_origin": {
            c: {str(k): round(v, 3) for k, v in runtime[c].items()} for c in CANDIDATES
        },
        "determinism": "VECLIB_MAXIMUM_THREADS=1 pinned in cli.py before numpy; every "
        "LightGBM fit n_jobs=1 + fixed seed + force_row_wise (direct pooled arms "
        "iterate sorted group keys and h=1..28 in fixed order); auto_ets may run "
        "n_jobs>1 (ETS selection is closed-form/seed-free — parallelism changes "
        "wall time only); seasonal_naive is numpy-vectorized; ensemble grid is "
        "lexicographic deterministic",
        "lgbm_params": {k: panel.lgbm_params[k] for k in panel.lgbm_params},
        "pooled_strategy": pooled_strategy,
        "n_jobs_ets": n_jobs_ets,
    }
    logger.info(
        "m5_full track done in %.1fs: test official WRMSSE lgbm=%.4f naive=%.4f ensemble=%.4f",
        time.time() - t0,
        metrics["test"]["lgbm"]["official_wrmsse"],
        metrics["test"][NAIVE]["official_wrmsse"],
        metrics["test"]["convex_ensemble"]["official_wrmsse"],
    )
    return M5FullResult(metrics=metrics, metadata=metadata)


def write_m5_full_artifacts(result: M5FullResult, reports_dir: Path) -> None:
    """Persist metrics.json + evaluation_metadata.json under reports_dir."""
    from demand_forecasting.evaluate import _json_safe

    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "metrics.json").write_text(
        json.dumps(_json_safe(result.metrics), indent=2) + "\n"
    )
    (reports_dir / "evaluation_metadata.json").write_text(
        json.dumps(_json_safe(result.metadata), indent=2) + "\n"
    )
