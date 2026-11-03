"""Wave-32 catalog dump for the full-panel track (protocol ``m5_full_v1``).

The committed overnight run scored the full 30,490-series panel under the
official hierarchical WRMSSE but did not persist per-series forecasts; the
forecast-workbench demo needs a curated catalog of series with per-candidate
curves at the scored-once test origin. That is all this module does — it is
NOT a re-evaluation:

- fits EVERY candidate at ONLY the final (test) origin through the shared
  :func:`demand_forecasting.m5_full._prepare_panel` /
  :func:`demand_forecasting.m5_full._origin_forecasts` path — the same panel
  context, configuration (recursive pooled, seed 42, params.yaml ``m5_lgbm``)
  and candidate set the committed run used; the pooled group models are
  panel-wide fits regardless of the catalog size;
- blends ``convex_ensemble`` with the COMMITTED members/weights read from
  ``reports_m5_full/metrics.json`` — the catalog run never re-selects weights;
- selects the catalog deterministically (rule below);
- writes ``catalog_forecasts.parquet`` (long format: one row per catalog
  series x forecast day; the actuals, every candidate's curve, the committed
  blend and a member-envelope band) plus ``catalog_meta.json`` (per-series
  descriptors: store, category, class, units/intermittency ranks, half);
- self-checks the persisted frame (blend identity, actuals, catalog-mean WAPE)
  before finishing and logs the result.

Catalog selection rule (deterministic given the pinned panel; recorded in the
meta): the catalog has two halves. The TOP half is filled by total units over
the LAST 28 DAYS OF THE PANEL (the scored window — demo curation only: every
candidate is scored on every series, so the pick does not touch any model
choice) and the BOTTOM half by the HARDEST INTERMITTENCY on the real training
history up to the test origin (Syntetos-Boylan ADI descending, ties -> CV2
descending, ties -> unique_id). Within each half the picks round-robin across
the sorted (store_id, cat_id) cells (the ranked order inside each cell is
preserved), so the catalog stays balanced across stores and categories; any
series may serve — the catalog is disjoint from nothing, and a series already
taken by the top half is skipped in the bottom half.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from portfolio_core.logging import get_logger

from demand_forecasting.intermittent import classify_demand
from demand_forecasting.m5_full import (
    CANDIDATES,
    ORIGIN_SPACING_DAYS,
    PROTOCOL,
    _assert_min_history,
    _FullPanel,
    _origin_forecasts,
    _package_versions,
    _prepare_panel,
    m5_full_origins,
)
from demand_forecasting.m5_track import (
    HORIZON,
    MIN_TRAIN_DAYS,
    SEED,
    _actual_window,
    _series_train_history,
)

logger = get_logger(__name__)

#: the catalog artifacts (next to each other under reports_m5_full/).
CATALOG_FORECASTS_NAME = "catalog_forecasts.parquet"
CATALOG_META_NAME = "catalog_meta.json"
#: the committed configuration the catalog run must mirror (the overnight
#: run's flags) — the CLI falls back to these when the mode is requested
#: without explicit overrides.
COMMITTED_SERIES_CAP = 30_490
CATALOG_RULE = (
    "deterministic two halves over the scored-panel series: top half by total "
    "units over the last 28 days of the panel (the scored window), bottom half "
    "by hardest intermittency on the training history to the test origin "
    "(ADI desc, ties -> CV2 desc, ties -> unique_id); within each half the "
    "picks round-robin across the sorted (store_id, cat_id) cells preserving "
    "the rank order inside each cell, so the catalog is balanced across "
    "stores and categories; a series taken by the top half is skipped in the "
    "bottom half; any series may serve (disjoint from nothing)"
)
#: tolerance of the persisted-frame self-checks (blend identity / actuals).
SELF_CHECK_TOL = 1e-9


@dataclass
class M5FullCatalogResult:
    """In-memory result: the persisted catalog frame + its meta block."""

    frame: pd.DataFrame
    meta: dict[str, Any]


def load_committed_ensemble(metrics_path: Path) -> tuple[list[str], list[float]]:
    """Read the COMMITTED ensemble members/weights — the catalog blend reuses
    them verbatim and never re-selects. Loud failures on drift."""
    path = Path(metrics_path)
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path} — the catalog run blends with the committed "
            "ensemble weights; run `evaluate-m5-full` first"
        )
    metrics = json.loads(path.read_text())
    if metrics.get("protocol") != PROTOCOL:
        raise ValueError(
            f"committed metrics protocol {metrics.get('protocol')!r} != {PROTOCOL!r} "
            "— the catalog run must blend with the m5_full_v1 ensemble"
        )
    block = metrics.get("ensemble") or {}
    members = [str(m) for m in block.get("members") or []]
    weights = [float(w) for w in block.get("weights") or []]
    if not members or len(members) != len(weights):
        raise ValueError(f"committed ensemble block is malformed: {block}")
    unknown = [m for m in members if m not in CANDIDATES]
    if unknown:
        raise ValueError(f"committed ensemble members not in the candidate set: {unknown}")
    if abs(sum(weights) - 1.0) > 1e-6:
        raise ValueError(f"committed ensemble weights do not sum to 1: {weights}")
    return members, weights


def _round_robin_take(
    ranked: list[int], quota: int, cells_of: dict[int, str], taken: set[int]
) -> list[int]:
    """Deterministic balanced pick: round-robin across the sorted cells over
    the pre-ranked panel positions, preserving the rank order inside each
    cell; positions already in ``taken`` (the other half's picks) are skipped.
    Stops when the quota is met or every cell is exhausted."""
    by_cell: dict[str, list[int]] = {}
    for i in ranked:
        if i in taken:
            continue
        by_cell.setdefault(cells_of[i], []).append(i)
    order_cells = sorted(by_cell)
    out: list[int] = []
    while len(out) < quota:
        progressed = False
        for cell in order_cells:
            if by_cell[cell] and len(out) < quota:
                out.append(by_cell[cell].pop(0))
                progressed = True
        if not progressed:
            break
    return out


def select_catalog_ids(
    panel: _FullPanel,
    o: int,
    *,
    catalog_size: int,
) -> tuple[list[int], dict[int, dict[str, Any]]]:
    """The deterministic catalog: panel positions + per-series descriptors.

    Top half by last-28-day units, bottom half by hardest train-history
    intermittency, round-robin balanced across (store, cat) cells — see the
    module docstring for the exact rule.
    """
    if catalog_size < 2:
        raise ValueError(f"catalog_size must be >= 2, got {catalog_size}")
    series_ids = panel.series_ids
    s_meta = panel.s_meta
    y_wide = panel.y_wide

    units28 = y_wide[:, -HORIZON:].sum(axis=1)
    # stable sort on -units keeps the (sorted) unique_id order as the tiebreak
    volume_rank = np.argsort(-units28, kind="stable").tolist()

    hist = _series_train_history(panel.y_all, series_ids, pd.Timestamp(panel.dates[o]))
    stats = {i: classify_demand(hist[series_ids[i]]) for i in range(len(series_ids))}
    # hardest first: ADI desc, ties -> CV2 desc, ties -> unique_id asc
    # (lexsort's LAST key is primary; inf CV2 sorts last under negation-safe
    # handling because -inf < any finite value)
    adi = np.array([stats[i]["adi"] for i in range(len(series_ids))])
    cv2 = np.array([stats[i]["cv2"] for i in range(len(series_ids))])
    adi = np.where(np.isfinite(adi), adi, np.inf)
    cv2 = np.where(np.isfinite(cv2), cv2, np.inf)
    inter_rank = np.lexsort((np.arange(len(series_ids)), -cv2, -adi)).tolist()

    cells_of = {
        i: f"{s_meta['store_id'].loc[series_ids[i]]}_{s_meta['cat_id'].loc[series_ids[i]]}"
        for i in range(len(series_ids))
    }
    top_quota = catalog_size - catalog_size // 2
    bottom_quota = catalog_size // 2
    taken: set[int] = set()
    top_pick = _round_robin_take(volume_rank, top_quota, cells_of, taken)
    taken.update(top_pick)
    bottom_pick = _round_robin_take(inter_rank, bottom_quota, cells_of, taken)

    units_rank_pos = {i: r for r, i in enumerate(volume_rank)}
    inter_rank_pos = {i: r for r, i in enumerate(inter_rank)}
    chosen: list[int] = []
    half_of: dict[int, str] = {}
    for i in top_pick:
        chosen.append(i)
        half_of[i] = "top_units"
    for i in bottom_pick:
        chosen.append(i)
        half_of[i] = "bottom_intermittency"
    descriptors = {
        i: {
            "store": str(s_meta["store_id"].loc[series_ids[i]]),
            "cat_id": str(s_meta["cat_id"].loc[series_ids[i]]),
            "dept_id": str(s_meta["dept_id"].loc[series_ids[i]]),
            "class": stats[i]["class"],
            "adi": round(float(stats[i]["adi"]), 4),
            "cv2": (round(float(stats[i]["cv2"]), 4) if np.isfinite(stats[i]["cv2"]) else "inf"),
            "units_last_28d": round(float(units28[i]), 4),
            "units_rank": units_rank_pos[i],
            "intermittency_rank": inter_rank_pos[i],
            "half": half_of[i],
        }
        for i in chosen
    }
    logger.info(
        "m5_full catalog: %d series (top-units %d + hardest-intermittency %d) "
        "balanced across %d (store, cat) cells",
        len(chosen),
        len(top_pick),
        len(bottom_pick),
        len({cells_of[i] for i in chosen}),
    )
    return chosen, descriptors


def _self_check(
    frame: pd.DataFrame,
    *,
    members: list[str],
    weights: list[float],
    actuals: np.ndarray,
    catalog_ids: list[str],
    ensemble_wape_committed: float | None,
) -> dict[str, Any]:
    """Verify the persisted catalog frame BEFORE the meta is written: the
    ensemble column must be the committed convex blend of the member columns
    (recomputed from the FILE, not memory), the actuals must reproduce the
    panel's scored window, and the ensemble's catalog-mean WAPE is logged
    next to the committed panel-wide bottom WAPE (a subset, not comparable —
    recorded side by side, never subtracted)."""
    blend = np.zeros(len(frame))
    for w, member in zip(weights, members, strict=True):
        blend += w * frame[member].to_numpy(dtype=float)
    persisted = frame["convex_ensemble"].to_numpy(dtype=float)
    blend_drift = float(np.max(np.abs(blend - persisted)))
    if blend_drift > SELF_CHECK_TOL:
        raise ValueError(
            f"catalog self-check failed: persisted ensemble column deviates from "
            f"the committed blend by {blend_drift} > {SELF_CHECK_TOL}"
        )
    grid = frame.pivot(index="unique_id", columns="ds", values="actual").reindex(catalog_ids)
    if grid.shape != (len(catalog_ids), HORIZON) or grid.isna().any().any():
        raise ValueError("catalog self-check failed: persisted actuals are not a full grid")
    actual_drift = float(np.max(np.abs(grid.to_numpy(dtype=float) - actuals)))
    if actual_drift > SELF_CHECK_TOL:
        raise ValueError(
            f"catalog self-check failed: persisted actuals deviate from the panel "
            f"by {actual_drift} > {SELF_CHECK_TOL}"
        )
    actual = frame["actual"].to_numpy(dtype=float)
    ens_wape = float(np.abs(persisted - actual).sum() / actual.sum())
    logger.info(
        "catalog self-check OK: ensemble = committed blend (%d members, drift %.2e); "
        "actuals reproduce the scored window (drift %.2e); ensemble catalog WAPE %.4f "
        "(panel-wide committed test bottom WAPE %.4f — a %d-series subset, not comparable)",
        len(members),
        blend_drift,
        actual_drift,
        ens_wape,
        ensemble_wape_committed if ensemble_wape_committed is not None else float("nan"),
        len(catalog_ids),
    )
    return {
        "ensemble_blend_max_abs_drift": blend_drift,
        "actuals_max_abs_drift": actual_drift,
        "ensemble_catalog_wape": ens_wape,
        "panel_committed_test_bottom_wape": ensemble_wape_committed,
        "note": "the catalog WAPE is a subset statistic — never compared to the "
        "panel-wide committed number",
    }


def run_m5_full_catalog(
    raw_dir: Path,
    catalog_path: Path,
    *,
    metrics_path: Path,
    catalog_size: int = 48,
    series_cap: int | None = COMMITTED_SERIES_CAP,
    pooled_strategy: Literal["direct", "recursive"] = "recursive",
    n_estimators: int | None = None,
    n_jobs_ets: int = 1,
    min_train: int = MIN_TRAIN_DAYS,
    seed: int = SEED,
    params_path: Path | str = "params.yaml",
) -> M5FullCatalogResult:
    """Run the wave-32 catalog dump: every candidate at the test origin only,
    committed-weights ensemble blend, deterministic catalog selection, parquet
    + meta on disk. The pooled arms fit on the full (capped) panel at the
    origin — the catalog subsetting happens AFTER the fits."""
    t0 = time.time()
    members, weights = load_committed_ensemble(metrics_path)
    panel = _prepare_panel(
        raw_dir,
        series_cap=series_cap,
        seed=seed,
        params_path=params_path,
        n_estimators=n_estimators,
    )
    origins = m5_full_origins(panel.n_dates, 1, HORIZON, min_train, ORIGIN_SPACING_DAYS)
    o = origins[-1]  # the scored-once test origin, exactly as in the committed run
    odate = pd.Timestamp(panel.dates[o])
    _assert_min_history(panel.y_all, odate)
    logger.info(
        "m5_full catalog run: test origin %s only | %d series (cap %s) | pooled=%s "
        "| committed ensemble %s x %s (reused, NOT re-selected)",
        odate.date(),
        panel.n_series,
        series_cap,
        pooled_strategy,
        members,
        [round(w, 4) for w in weights],
    )

    preds, times = _origin_forecasts(
        panel,
        o,
        seed=seed,
        pooled_strategy=pooled_strategy,
        n_estimators=n_estimators,
        n_jobs_ets=n_jobs_ets,
    )
    blend = np.zeros_like(preds[members[0]])
    for w, member in zip(weights, members, strict=True):
        blend += w * preds[member]
    preds["convex_ensemble"] = blend
    actuals = _actual_window(panel.y_all, panel.series_ids, odate, HORIZON)

    cat_pos, descriptors = select_catalog_ids(panel, o, catalog_size=catalog_size)
    catalog_ids = [panel.series_ids[i] for i in cat_pos]
    days = pd.date_range(odate + pd.to_timedelta(1, unit="D"), periods=HORIZON, freq="D")
    cat_idx = np.asarray(cat_pos)
    block: dict[str, Any] = {
        "unique_id": np.repeat(catalog_ids, HORIZON),
        "ds": np.tile(days.to_numpy(), len(catalog_ids)),
        "actual": actuals[cat_idx].reshape(-1),
    }
    for cand in CANDIDATES:
        block[cand] = preds[cand][cat_idx].reshape(-1)
    # member envelope — a cheap honesty band, NOT a calibrated interval
    member_stack = np.stack([preds[m][cat_idx] for m in members])
    block["band_lo"] = member_stack.min(axis=0).reshape(-1)
    block["band_hi"] = member_stack.max(axis=0).reshape(-1)
    frame = pd.DataFrame(block)

    metrics = json.loads(Path(metrics_path).read_text())
    committed_wape = metrics["test"]["convex_ensemble"]["bottom_wape"]

    # in-memory check before touching disk, then write, then re-verify the file
    pre_check = _self_check(
        frame,
        members=members,
        weights=weights,
        actuals=actuals[cat_idx],
        catalog_ids=catalog_ids,
        ensemble_wape_committed=committed_wape,
    )
    catalog_path = Path(catalog_path)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(frame, preserve_index=False)
    schema_meta = {
        "protocol": PROTOCOL,
        "origin": str(odate.date()),
        "catalog_rule": CATALOG_RULE,
        "weights_source": str(metrics_path),
        "ensemble": json.dumps({"members": members, "weights": weights}),
        "band": "band_lo/band_hi = per-day min/max of the committed ensemble "
        "member forecasts (an envelope, NOT a calibrated prediction interval)",
        "self_check": json.dumps(pre_check),
    }
    schema_meta_encoded = {k.encode(): v.encode() for k, v in schema_meta.items()}
    table = table.replace_schema_metadata(
        {**dict(table.schema.metadata or {}), **schema_meta_encoded}
    )
    pq.write_table(table, catalog_path)
    logger.info("m5_full catalog forecasts -> %s (%d rows)", catalog_path, len(frame))

    # post-write verification against the re-read file (catches a bad write)
    reread = pq.read_table(catalog_path).to_pandas()
    post_check = _self_check(
        reread,
        members=members,
        weights=weights,
        actuals=actuals[cat_idx],
        catalog_ids=catalog_ids,
        ensemble_wape_committed=committed_wape,
    )

    meta: dict[str, Any] = {
        "protocol": PROTOCOL,
        "origin": str(odate.date()),
        "forecast_window": [str(days[0].date()), str(days[-1].date())],
        "horizon_days": HORIZON,
        "catalog_size": len(catalog_ids),
        "catalog_rule": CATALOG_RULE,
        "series_universe": {
            "n_series": panel.n_series,
            "ladder_cap": series_cap,
            "pooled_strategy": pooled_strategy,
        },
        "weights_source": str(metrics_path),
        "weights_rule": "committed members/weights read from the committed run's "
        "metrics.json and reused verbatim — the catalog run does NOT re-select",
        "ensemble": {"members": members, "weights": weights},
        "band": schema_meta["band"],
        "candidates": list(CANDIDATES),
        "runtime_seconds": round(time.time() - t0, 3),
        "runtime_seconds_per_candidate": {k: round(v, 3) for k, v in times.items()},
        "package_versions": _package_versions(),
        "self_check": post_check,
        "series": [{"unique_id": panel.series_ids[i], **descriptors[i]} for i in cat_pos],
    }
    meta_path = catalog_path.parent / CATALOG_META_NAME
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    logger.info("m5_full catalog meta -> %s", meta_path)
    return M5FullCatalogResult(frame=frame, meta=meta)
