"""Hierarchical forecasting track (wave 23a) — protocol ``hierarchical_rolling_v1``.

Wave 22 closed with a deliberate caveat: the panel track's ``routed_reconciled``
anchoring (proportional allocation toward a seasonal-naive country aggregate)
**lost** on pooled MAE, and the design note said "covariance-projection MinT is
the documented next step". This module is that step, evaluated on the two
canonical Nixtla hierarchical benchmarks (Rangapuram et al. ICML 2021,
Olivares et al. IJF 2023, Kamarthi et al. PROFHIT 2022 — see
``data_hier/PROVENANCE.md``):

- **TourismSmall** — quarterly Australian tourism, 89 nodes / 56 bottom,
  1998Q1-2006Q4, season 4, horizon 4.
- **Labour** — monthly Australian labour force, 57 nodes / 32 bottom,
  1978-2019, season 12, horizon 8.

Protocol (``hierarchical_rolling_v1``): rolling-origin evaluation, origin = the
last training period, forecast window = the next ``horizon`` periods (the
window abuts the origin — no embargo gap, same contract as the panel track).
Origins are evenly spaced one period apart and capped at ``n_origins`` by
dropping the OLDEST (the exact cadence is preserved; the cap is documented in
the JSON ``origins`` block). ``min_train`` periods are required before the
first origin.

Candidates are fixed a priori — there is **no routing and no selection**:
every candidate is evaluated raw and reconciled at every origin, so all
origins are honest evaluation for fixed candidates (unlike the panel track,
nothing is fit on the scored origins):

- ``seasonal_naive`` — hand-rolled, the same definition as the panel track:
  ``f(h) = y[T - m + ((h - 1) mod m)]`` over the training window (h > m wraps
  around the last cycle; h=1 is y[T - m + 1 - 1] = y[T - m], the most recent
  same-season actual).
- ``auto_theta`` / ``auto_ets`` — statsforecast ``AutoTheta`` / ``AutoETS``
  (season_length = m), one model per node, ``n_jobs=1``.
- ``lgbm_global`` — one global ``LGBMRegressor`` over all nodes (mlforecast:
  lags 1..m and 2m, ``RollingMean(m)`` / ``ExpandingMean`` at lag 1, calendar
  date features).

Every candidate is scored **raw**, **+BottomUp** and **+MinT(mint_shrink)**
(hierarchicalforecast). All four base forecasts are reconciled: the
statsforecast insample fits come from ``sf.forecast(df, h, fitted=True)`` +
``sf.forecast_fitted_values()`` (the residual covariance for MinT is built
from those insample residuals — the same construction as the mlforecast
path). ``seasonal_naive`` reconciles through the same machinery with its own
one-step insample residuals (``fitted[t] = y[t - m]``).

Metrics per candidate x reconciliation variant, per hierarchy level (from
``tags``, ordered total -> bottom, short names: the first tag's single node is
``total``, the last tag is ``bottom``): pooled MAE and ``rmae`` (variant MAE /
raw ``seasonal_naive`` MAE at the same level — the floor is 1.0 by
construction). ``coherence`` per reconciled variant: the hand-testable
definition — pooled mean over (origin x parent node x window period) cells of
``|parent_fc - sum children_fc| / max(|parent_actual|, 1)``, where the children
of a node are the bottom nodes with ``S[node, bottom] != 0`` (so the sum is
``S[node] @ bottom_fc``); raw variants are scored too, and a linear base
forecast such as seasonal_naive is exactly coherent (0.0) because the actuals
aggregate linearly. Headline gaps (``lgbm_global+mint_shrink`` vs
``seasonal_naive``, total level and bottom level) carry a 95% paired cluster
bootstrap over the bottom series (2,000 replications, one shared index draw
per replication — the projects/05/10 pattern); total-level quantities are
re-aggregated inside each resample from the sampled bottom series, so the
total stays paired with the bottom draw.

Determinism: fixed seed everywhere (LightGBM ``random_state`` +
``force_row_wise`` + ``n_jobs=1``, statsforecast ``n_jobs=1``), and Apple
Accelerate pinned to one thread via ``VECLIB_MAXIMUM_THREADS=1`` set before
numpy loads (cli.py and this module) — MinT's LAPACK reductions (pinv/SVD)
are not run-to-run reproducible under Accelerate's threading and threadpoolctl
cannot limit Accelerate (``threadpool_info()`` is empty on this host).
``threadpool_limits(limits=1)`` additionally caps every other runtime's pools
around each fit. A run-twice byte-identity check of ``reports_hier/metrics.json``
is part of the wave's gates.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

# Apple Accelerate reads VECLIB_MAXIMUM_THREADS at init time and threadpoolctl
# cannot limit it; MinT's LAPACK reductions (pinv/SVD) are only run-to-run
# reproducible single-threaded. Set before numpy/Accelerate loads (the CLI
# sets this too, earlier — see cli.py); setdefault keeps a user override.
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

# macOS OpenMP landmine (the temporal.py contract): hierarchicalforecast's
# compiled _lib bundles its OWN .dylibs/libomp.dylib — if that image loads
# before the boosters' shared runtime, the first xgboost/lightgbm fit in the
# process segfaults (dual OpenMP runtimes). Import the boosters FIRST so dyld
# shares one runtime.
try:  # pragma: no cover - environment guard, not behaviour
    import lightgbm  # noqa: F401
    import xgboost  # noqa: F401
except ImportError:  # boosters are optional arms; the hierarchical track must still run
    pass

import numpy as np
import pandas as pd  # type: ignore[import-untyped]  # no stubs in the venv
from datasetsforecast.hierarchical import HierarchicalData  # type: ignore[import-untyped]
from hierarchicalforecast.core import HierarchicalReconciliation  # type: ignore[import-untyped]
from hierarchicalforecast.methods import BottomUp, MinTrace  # type: ignore[import-untyped]
from lightgbm import LGBMRegressor
from mlforecast import MLForecast
from mlforecast.lag_transforms import ExpandingMean, RollingMean
from portfolio_core.logging import get_logger
from statsforecast import StatsForecast
from statsforecast.models import AutoETS, AutoTheta
from threadpoolctl import threadpool_limits  # type: ignore[import-untyped]  # re-exported

from demand_forecasting.config import ForecastConfig
from demand_forecasting.evaluate import _json_safe

logger = get_logger(__name__)

PROTOCOL = "hierarchical_rolling_v1"
# Paired cluster bootstrap for the headline gaps (fixed contract).
BOOTSTRAP_REPS = 2000
# Reconciliation-variant suffixes (HierarchicalReconciliation output columns
# are "<candidate>/<method>"; the metrics keys use these compact names).
BOTTOM_UP_SUFFIX = "BottomUp"
MINT_SUFFIX = "MinTrace_method-mint_shrink"


@dataclass(frozen=True)
class GroupSpec:
    """Fixed problem definition of one hierarchical benchmark group."""

    freq: str  # pandas offset alias ('QE' — plain 'Q' is deprecated; 'MS')
    season_length: int
    horizon: int
    min_train: int  # periods before the first origin
    n_origins: int  # cap; oldest origins dropped (exact cadence preserved)


HIERARCHICAL_GROUPS: dict[str, GroupSpec] = {
    "TourismSmall": GroupSpec(freq="QE", season_length=4, horizon=4, min_train=24, n_origins=6),
    "Labour": GroupSpec(freq="MS", season_length=12, horizon=8, min_train=96, n_origins=6),
}
CANDIDATES = ("seasonal_naive", "auto_theta", "auto_ets", "lgbm_global")
NAIVE = "seasonal_naive"
HEADLINE_VARIANT = "lgbm_global+mint_shrink"
# Every scored variant: raw candidates, +BottomUp, +MinT(mint_shrink).
VARIANTS = (
    *CANDIDATES,
    *[f"{c}+bottom_up" for c in CANDIDATES],
    *[f"{c}+mint_shrink" for c in CANDIDATES],
)


def seasonal_naive_forecast(history: np.ndarray, horizon: int, season_length: int) -> np.ndarray:
    """Direct seasonal-naive forecast, the panel-track definition (hand-testable).

    ``f(h) = y[T - m + ((h - 1) mod m)]`` for h = 1..horizon over the training
    window ``history`` (length T ≥ m): h=1 repeats the most recent same-season
    actual y[T - m]; h > m wraps around the last cycle (h=m+1 == h=1).
    """
    history = np.asarray(history, dtype=float)
    t = len(history)
    if t < season_length:
        raise ValueError(f"history shorter than one season: {t} < {season_length}")
    idx = t - season_length + ((np.arange(horizon)) % season_length)
    return history[idx]


def seasonal_naive_fitted(history: np.ndarray, season_length: int) -> np.ndarray:
    """One-step insample seasonal-naive fits ``fitted[t] = y[t - m]``.

    The first m entries are NaN (no same-season predecessor) — MinT's
    residual covariance ignores the NaN rows (hierarchicalforecast drops
    non-finite residuals internally; the tiny-hierarchy tests pin the
    behaviour end to end).
    """
    history = np.asarray(history, dtype=float)
    t = len(history)
    out = np.full(t, np.nan)
    if t > season_length:
        out[season_length:] = history[: t - season_length]
    return out


def level_names(tags: dict[str, np.ndarray]) -> list[str]:
    """Hierarchy levels ordered total -> bottom.

    The first tag holds the single total node, the last tag the bottom level;
    intermediate levels keep their full tag key (collision-free and exact).
    """
    keys = list(tags.keys())
    names = [keys[0], *keys[1:-1], keys[-1]]
    names[0] = "total"
    names[-1] = "bottom"
    return names


def level_members(tags: dict[str, np.ndarray]) -> dict[str, set[str]]:
    """Level name -> set of node ids, ordered total -> bottom."""
    keys = list(tags.keys())
    members: dict[str, set[str]] = {"total": set(str(u) for u in tags[keys[0]])}
    for key in keys[1:-1]:
        members[key] = set(str(u) for u in tags[key])
    members["bottom"] = set(str(u) for u in tags[keys[-1]])
    return members


def build_S_df(S: np.ndarray, uids: list[str], bottom_ids: list[str]) -> pd.DataFrame:
    """The reconciliation matrix as hierarchicalforecast's ``S_df`` frame.

    ``S`` is (n_nodes, n_bottom); row order MUST equal ``uids`` (the
    ``Y_df.unique_id`` unique order — asserted by callers). Hand-tested.
    """
    return pd.DataFrame(S, index=uids, columns=bottom_ids).rename_axis("unique_id").reset_index()


def origin_indices(n_periods: int, spec: GroupSpec) -> list[int]:
    """Rolling-origin indices: one period apart, oldest dropped past the cap.

    Origin ``o`` trains on periods 0..o (so ``o + 1 ≥ min_train``) and scores
    the window o+1..o+horizon (so ``o ≤ n_periods - horizon - 1``).
    """
    first = spec.min_train - 1
    last = n_periods - spec.horizon - 1
    if last < first:
        raise ValueError(
            f"series too short: {n_periods} periods, need >= {first + spec.horizon + 1}"
        )
    eligible = list(range(first, last + 1))
    if len(eligible) > spec.n_origins:
        eligible = eligible[-spec.n_origins :]  # exact cadence preserved
    return eligible


def coherence_error(
    pred: np.ndarray, actual: np.ndarray, S: np.ndarray, parent_rows: np.ndarray
) -> float:
    """Mean over (parent node x window period) cells of the incoherence ratio.

    ``pred`` / ``actual`` are (n_nodes x n_periods) in node order; the bottom
    rows are the last ``S.shape[1]`` rows. For every parent (non-bottom) node:
    ``|fc_parent - S[parent] @ fc_bottom| / max(|actual_parent|, 1)``. Exactly
    0.0 for any variant whose forecasts aggregate linearly (BottomUp, and raw
    linear base forecasts such as seasonal_naive on exactly-aggregating
    actuals). Hand-testable.
    """
    n_bottom = S.shape[1]
    bottom_pred = pred[-n_bottom:]
    num = np.abs(pred[parent_rows] - S[parent_rows] @ bottom_pred)
    den = np.maximum(np.abs(actual[parent_rows]), 1.0)
    return float((num / den).mean())


def _paired_bootstrap_gap(
    bottom_actual: np.ndarray,
    pred_a: np.ndarray,
    pred_b: np.ndarray,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """95% paired cluster bootstrap on MAE(A) - MAE(B), clustered by bottom series.

    ``bottom_actual`` / ``pred_*`` are (n_bottom x n_cells) — one row per bottom
    series, columns the scored (origin x period) cells. One shared index draw
    per replication resamples SERIES with replacement. The bottom-level
    statistic pools the resampled series' |error| cells; the total-level
    statistic re-aggregates the SAMPLED series' actuals and forecasts per cell
    (sampling with replacement weights the aggregate accordingly), so both
    levels stay paired on the same draws. Percentile interval.
    """
    n_series = bottom_actual.shape[0]
    abs_a = np.abs(bottom_actual - pred_a)
    abs_b = np.abs(bottom_actual - pred_b)
    rng = np.random.default_rng(seed)
    diffs_bottom = np.empty(n_boot)
    diffs_total = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n_series, n_series)
        diffs_bottom[i] = abs_a[idx].mean() - abs_b[idx].mean()
        ta = bottom_actual[idx].sum(axis=0)
        diffs_total[i] = (
            np.abs(ta - pred_a[idx].sum(axis=0)).mean()
            - np.abs(ta - pred_b[idx].sum(axis=0)).mean()
        )
    lo_b, hi_b = np.quantile(diffs_bottom, [0.025, 0.975])
    lo_t, hi_t = np.quantile(diffs_total, [0.025, 0.975])
    return {
        "bottom": {
            "diff": float(abs_a.mean() - abs_b.mean()),
            "ci95": [float(lo_b), float(hi_b)],
            "spans_zero": bool(lo_b <= 0.0 <= hi_b),
        },
        "total": {
            "diff": float(
                np.abs(bottom_actual.sum(axis=0) - pred_a.sum(axis=0)).mean()
                - np.abs(bottom_actual.sum(axis=0) - pred_b.sum(axis=0)).mean()
            ),
            "ci95": [float(lo_t), float(hi_t)],
            "spans_zero": bool(lo_t <= 0.0 <= hi_t),
        },
        "n_boot": n_boot,
        "seed": seed,
    }


def _lgbm_model(config: ForecastConfig) -> LGBMRegressor:
    """The fixed global-LightGBM candidate (deterministic fit)."""
    return LGBMRegressor(
        random_state=config.seed,
        n_estimators=300,
        learning_rate=0.05,
        verbosity=-1,
        # repo determinism learnings (multihorizon._fit_lgbm): the row-wise
        # splitter + single job + fixed seed reproduce byte-identically
        # without LightGBM 4.x's degenerate-split assert path
        force_row_wise=True,
        n_jobs=1,
    )


def _date_features(freq: str) -> list[str]:
    return ["month", "year"] if freq == "MS" else ["quarter", "year"]


def _score_origin(
    train: pd.DataFrame,
    window: pd.DataFrame,
    uids: list[str],
    S_df: pd.DataFrame,
    tags: dict[str, np.ndarray],
    S: np.ndarray,
    spec: GroupSpec,
    config: ForecastConfig,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Fit every candidate at one origin; return (scored long frame, coherence).

    The scored frame carries the window actuals plus one column per variant
    (raw / +bottom_up / +mint_shrink per candidate) on
    (unique_id x ds x origin). Coherence is pooled over the variant's
    (parent x period) cells at THIS origin (every origin contributes the same
    number of cells, so the cross-origin mean equals the pooled cell mean).
    """
    m = spec.season_length
    h = spec.horizon
    n_nodes = len(uids)

    # -- seasonal_naive (hand-rolled, all nodes) -----------------------------
    wide = train.pivot(index="ds", columns="unique_id", values="y")[uids]
    hist = wide.to_numpy(dtype=float)
    naive_fc = seasonal_naive_forecast(hist, h, m)  # (h x n_nodes)
    naive_fit = np.column_stack(
        [seasonal_naive_fitted(hist[:, i], m) for i in range(n_nodes)]
    )  # (T_train x n_nodes), first m rows NaN

    base = window[["unique_id", "ds"]].copy()
    # long-form naive forecast in the same (unique_id, ds) order as `base`
    naive_long = (
        pd.DataFrame(
            naive_fc,
            columns=pd.Index(uids, name="unique_id"),
            index=np.sort(window["ds"].unique()),
        )
        .rename_axis("ds")
        .stack()
        .rename("seasonal_naive")
        .reset_index()
    )
    base = base.merge(naive_long, on=["unique_id", "ds"], how="left")

    # insample fits, long (unique_id, ds) -> fitted
    train_ds = wide.index.to_numpy()
    fit_naive = (
        pd.DataFrame(naive_fit, index=train_ds, columns=pd.Index(uids, name="unique_id"))
        .rename_axis("ds")
        .stack()
        .rename("seasonal_naive")
        .reset_index()[["unique_id", "ds", "seasonal_naive"]]
    )

    # -- statsforecast (AutoTheta + AutoETS, all nodes) ----------------------
    sf = StatsForecast(
        models=[AutoTheta(season_length=m), AutoETS(season_length=m)],
        freq=spec.freq,
        n_jobs=1,
    )
    sf_train = train[["unique_id", "ds", "y"]]
    # statsforecast/mlforecast stub their returns as polars frames; this module
    # works in pandas — cast at the boundary (their runtime frames are pandas)
    sf_fc = cast(
        pd.DataFrame,
        sf.fit_predict(h=h, df=sf_train, id_col="unique_id", time_col="ds", target_col="y"),
    )
    sf_fc = sf_fc.rename(columns={"AutoTheta": "auto_theta", "AutoETS": "auto_ets"})
    base = base.merge(sf_fc, on=["unique_id", "ds"], how="left")
    sf_in = StatsForecast(
        models=[AutoTheta(season_length=m), AutoETS(season_length=m)],
        freq=spec.freq,
        n_jobs=1,
    )
    sf_in.forecast(df=sf_train, h=h, fitted=True, id_col="unique_id", time_col="ds", target_col="y")
    fit_stats = cast(pd.DataFrame, sf_in.forecast_fitted_values()).rename(  # type: ignore[no-untyped-call]
        columns={"AutoTheta": "auto_theta", "AutoETS": "auto_ets"}
    )[["unique_id", "ds", "auto_theta", "auto_ets"]]

    # -- mlforecast global LightGBM ------------------------------------------
    mfc = MLForecast(
        models=[_lgbm_model(config)],
        freq=spec.freq,
        lags=[*range(1, m + 1), 2 * m],
        lag_transforms={1: [RollingMean(m), ExpandingMean()]},
        date_features=_date_features(spec.freq),
    )
    mfc.fit(sf_train, id_col="unique_id", time_col="ds", target_col="y", fitted=True)
    lgbm_fc = cast(pd.DataFrame, mfc.predict(h)).rename(columns={"LGBMRegressor": "lgbm_global"})
    base = base.merge(lgbm_fc, on=["unique_id", "ds"], how="left")
    fit_lgbm = cast(pd.DataFrame, mfc.forecast_fitted_values()).rename(
        columns={"LGBMRegressor": "lgbm_global"}
    )[["unique_id", "ds", "lgbm_global"]]

    if base[list(CANDIDATES)].isna().any().any():
        raise ValueError("base forecasts missing cells after the candidate merges")

    # -- reconciliation (one call, all candidates) ---------------------------
    fitted = fit_naive.merge(fit_stats, on=["unique_id", "ds"], how="outer").merge(
        fit_lgbm, on=["unique_id", "ds"], how="outer"
    )
    y_rec = train[["unique_id", "ds", "y"]].merge(fitted, on=["unique_id", "ds"], how="left")
    rec = HierarchicalReconciliation(reconcilers=[BottomUp(), MinTrace(method="mint_shrink")])
    rec_fc = rec.reconcile(Y_hat_df=base, S_df=S_df, tags=tags, Y_df=y_rec)

    variants = {c: rec_fc[c].to_numpy() for c in CANDIDATES}
    for c in CANDIDATES:
        variants[f"{c}+bottom_up"] = rec_fc[f"{c}/{BOTTOM_UP_SUFFIX}"].to_numpy()
        variants[f"{c}+mint_shrink"] = rec_fc[f"{c}/{MINT_SUFFIX}"].to_numpy()

    scored = rec_fc[["unique_id", "ds"]].copy()
    scored = scored.merge(window[["unique_id", "ds", "y"]], on=["unique_id", "ds"], how="left")
    scored = scored.rename(columns={"y": "actual"})
    for name, vals in variants.items():
        scored[name] = vals
    if scored["actual"].isna().any() or scored[NAIVE].isna().any():
        raise ValueError("scored window carries NaN actuals or naive forecasts")

    # -- coherence per variant (parent x window-period cells) ----------------
    n_bottom = S.shape[1]
    parent_rows = np.arange(n_nodes - n_bottom)
    actual_mat = scored.pivot(index="ds", columns="unique_id", values="actual")[uids].to_numpy().T
    coherence = {}
    for name in variants:
        pred_mat = scored.pivot(index="ds", columns="unique_id", values=name)[uids].to_numpy().T
        coherence[name] = coherence_error(pred_mat, actual_mat, S, parent_rows)
    return scored, coherence


def mae_rmae_by_level(
    pooled: pd.DataFrame,
    members: dict[str, set[str]],
    levels: list[str],
    variants: tuple[str, ...] = VARIANTS,
) -> tuple[dict[str, dict[str, dict[str, float]]], dict[str, float]]:
    """Pooled per-level MAE and rmae per variant (hand-testable aggregation).

    ``pooled`` is the scored long frame (``unique_id``, ``actual``, one column
    per variant). rmae = variant MAE / raw ``seasonal_naive`` MAE at the same
    level (the floor is 1.0 by construction). Returns (per_level, naive_mae).
    """
    per_level: dict[str, dict[str, dict[str, float]]] = {}
    naive_mae: dict[str, float] = {}
    for level in levels:
        rows = pooled[pooled["unique_id"].isin(members[level])]
        naive_mae[level] = float((rows["actual"] - rows[NAIVE]).abs().mean())
    for variant in variants:
        per_level[variant] = {}
        for level in levels:
            rows = pooled[pooled["unique_id"].isin(members[level])]
            mae = float((rows["actual"] - rows[variant]).abs().mean())
            per_level[variant][level] = {"mae": mae, "rmae": mae / naive_mae[level]}
    return per_level, naive_mae


def evaluate_group(
    data_dir: Path,
    group: str,
    config: ForecastConfig,
    n_origins: int | None = None,
) -> dict[str, Any]:
    """Evaluate every candidate x reconciliation variant on one benchmark group."""
    spec = HIERARCHICAL_GROUPS[group]
    if n_origins is not None:
        spec = GroupSpec(
            freq=spec.freq,
            season_length=spec.season_length,
            horizon=spec.horizon,
            min_train=spec.min_train,
            n_origins=n_origins,
        )
    Y_df, S, tags = HierarchicalData.load(str(data_dir), group)
    Y_df = Y_df.copy()
    Y_df["ds"] = pd.to_datetime(Y_df["ds"])
    S = np.asarray(S, dtype=float)
    uids = list(Y_df["unique_id"].unique())
    bottom_ids = [str(u) for u in tags[list(tags.keys())[-1]]]
    if S.shape[0] != len(uids):
        raise ValueError("S row count does not match the unique_id order")
    S_df = build_S_df(S, uids, bottom_ids)
    dates = np.sort(Y_df["ds"].unique())
    origins = origin_indices(len(dates), spec)
    origin_dates = [str(pd.Timestamp(dates[o]).date()) for o in origins]
    logger.info(
        "%s: %d nodes (%d bottom), %d periods, %d origins %s..%s",
        group,
        len(uids),
        len(bottom_ids),
        len(dates),
        len(origins),
        origin_dates[0],
        origin_dates[-1],
    )
    levels = level_names(tags)
    members = level_members(tags)

    scored_frames: list[pd.DataFrame] = []
    coherence_sum: dict[str, float] = {name: 0.0 for name in VARIANTS}
    for o in origins:
        cutoff = dates[o]
        train = Y_df[Y_df["ds"] <= cutoff].reset_index(drop=True)
        window = Y_df[Y_df["ds"] > cutoff].reset_index(drop=True)
        window = window[window["ds"] <= dates[o + spec.horizon]]
        with threadpool_limits(limits=1):
            scored, coherence = _score_origin(train, window, uids, S_df, tags, S, spec, config)
        scored["origin"] = str(pd.Timestamp(cutoff).date())
        scored_frames.append(scored)
        for name, val in coherence.items():
            coherence_sum[name] += val
    pooled = pd.concat(scored_frames, ignore_index=True)
    coherence = {name: val / len(origins) for name, val in coherence_sum.items()}

    # -- per-level MAE / rmae -------------------------------------------------
    per_level, naive_mae = mae_rmae_by_level(pooled, members, levels)

    # -- headline bootstrap: lgbm_global+mint_shrink vs seasonal_naive --------
    bottom = pooled[pooled["unique_id"].isin(members["bottom"])]
    cell_index = bottom.sort_values(["unique_id", "ds", "origin"])
    bottom_actual = cell_index.pivot(index="unique_id", columns=["origin", "ds"], values="actual")
    pred_a = cell_index.pivot(index="unique_id", columns=["origin", "ds"], values=HEADLINE_VARIANT)
    pred_b = cell_index.pivot(index="unique_id", columns=["origin", "ds"], values=NAIVE)
    if not (bottom_actual.shape == pred_a.shape == pred_b.shape):
        raise ValueError("bottom-level cell pivot misaligned")
    bootstrap = _paired_bootstrap_gap(
        bottom_actual.to_numpy(dtype=float),
        pred_a.to_numpy(dtype=float),
        pred_b.to_numpy(dtype=float),
        n_boot=BOOTSTRAP_REPS,
        seed=config.seed,
    )
    headline = {
        "claim": (
            f"{HEADLINE_VARIANT} posts rmae {per_level[HEADLINE_VARIANT]['total']['rmae']:.3f} "
            f"vs {NAIVE} at the total level and "
            f"{per_level[HEADLINE_VARIANT]['bottom']['rmae']:.3f} at the bottom level "
            f"(95% paired cluster bootstrap over bottom series, {BOOTSTRAP_REPS} reps, "
            f"seed {config.seed}; total-level MAE gap "
            f"{bootstrap['total']['diff']:.3f}, CI [{bootstrap['total']['ci95'][0]:.3f}, "
            f"{bootstrap['total']['ci95'][1]:.3f}]; bottom-level MAE gap "
            f"{bootstrap['bottom']['diff']:.3f}, CI [{bootstrap['bottom']['ci95'][0]:.3f}, "
            f"{bootstrap['bottom']['ci95'][1]:.3f}])"
        ),
        "total": {
            "rmae": per_level[HEADLINE_VARIANT]["total"]["rmae"],
            "mae": per_level[HEADLINE_VARIANT]["total"]["mae"],
            "naive_mae": naive_mae["total"],
            "bootstrap": bootstrap["total"],
        },
        "bottom": {
            "rmae": per_level[HEADLINE_VARIANT]["bottom"]["rmae"],
            "mae": per_level[HEADLINE_VARIANT]["bottom"]["mae"],
            "naive_mae": naive_mae["bottom"],
            "bootstrap": bootstrap["bottom"],
        },
    }
    return {
        "protocol": PROTOCOL,
        "group": group,
        "freq": spec.freq,
        "season_length": spec.season_length,
        "horizon": spec.horizon,
        "min_train": spec.min_train,
        "origins": {"dates": origin_dates, "n": len(origins)},
        "candidates": list(CANDIDATES),
        "levels": levels,
        "per_level": per_level,
        "coherence": coherence,
        "headline": headline,
        "bootstrap": {
            "method": (
                "paired cluster bootstrap over bottom series (shared index draws per "
                "replication); total-level cells re-aggregated from the sampled bottom "
                "series inside each resample; percentile CI on the pooled-MAE gap"
            ),
            "n_boot": BOOTSTRAP_REPS,
            "seed": config.seed,
        },
    }


def evaluate_hierarchical(
    data_dir: Path,
    reports_dir: Path,
    groups: list[str],
    config: ForecastConfig,
) -> dict[str, Any]:
    """Run the hierarchical track for ``groups``; write the reports_hier JSONs."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    blocks = {g: evaluate_group(data_dir, g, config) for g in groups}
    metrics = {"groups": blocks}
    (reports_dir / "metrics.json").write_text(json.dumps(_json_safe(metrics), indent=2))
    metadata = {
        "hierarchical": {
            "protocol": PROTOCOL,
            "seed": config.seed,
            "groups": {
                g: {
                    "freq": HIERARCHICAL_GROUPS[g].freq,
                    "season_length": HIERARCHICAL_GROUPS[g].season_length,
                    "horizon": HIERARCHICAL_GROUPS[g].horizon,
                    "min_train": HIERARCHICAL_GROUPS[g].min_train,
                    "n_origins": blocks[g]["origins"]["n"],
                    "origin_dates": blocks[g]["origins"]["dates"],
                    "candidates": list(CANDIDATES),
                    "levels": blocks[g]["levels"],
                }
                for g in groups
            },
        }
    }
    (reports_dir / "evaluation_metadata.json").write_text(
        json.dumps(_json_safe(metadata), indent=2)
    )
    logger.info("hierarchical metrics -> %s", reports_dir / "metrics.json")
    return metrics
