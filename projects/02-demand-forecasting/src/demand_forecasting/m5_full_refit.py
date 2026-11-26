"""Pass-4 E9 refit — regenerate the catalog/demo/figure on the COMMITTED blend.

The committed ``m5_full_v1`` run (metrics.json, pooled_strategy ``direct``)
scores the convex ensemble at 0.6211 with weights 0.95/0.00/0.05, but the
wave-32 catalog dump — and everything built from it (demo payload, sample
series figure) — still carried the superseded run's 0.6161 blend (weights
0.60/0.10/0.30, recursive pooled fits). This module is the targeted repair:

- refits ONLY the positive-weight committed ensemble members
  (:data:`REFIT_MEMBERS`) at the scored-once test origin through the exact
  committed code path (:func:`demand_forecasting.m5_full._prepare_panel` +
  ``_direct_prep`` + ``_lgbm_pool_direct_forecast`` per sorted group — the
  same config the committed run used: seed 42, params.yaml ``m5_lgbm``,
  ``n_jobs=1`` + ``force_row_wise`` per fit). Every other catalog candidate
  column carries over from the wave-32 catalog run untouched — zero-weight
  members contribute nothing to the blend, so no other refit is needed;
- REPRODUCTION GATE (hard stop): the refit member official WRMSSEs and the
  committed-weight blend must match the committed ``metrics.json`` test block
  to :data:`REPRO_TOL` before any artifact is touched — on a mismatch the
  driver raises :class:`RefitReproductionError` and writes nothing;
- on pass: updates ``catalog_forecasts.parquet`` (the two member columns, the
  recomputed committed blend, the member-envelope band), ``catalog_meta.json``
  (committed ensemble + an ``e9_refit`` provenance block), writes
  ``headline_interval.json`` (a seeded node bootstrap of the headline blend
  WRMSSE over the 42,840 hierarchy nodes) and logs the reproduction check
  into ``evaluation_metadata.json``.

Wall-time note: the per-(member, group) direct fits are independent and each
is ``n_jobs=1``, so they run in a thread pool with numerics identical to the
committed sequential loop (thread scheduling never enters a fit). Per-candidate
matrices are parquet-cached through the wave-34 ``_cached_forecast`` idiom, so
an interrupted refit resumes without refits.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from portfolio_core.logging import get_logger

from demand_forecasting.m5_data import split_exogenous
from demand_forecasting.m5_full import (
    N_ORIGINS,
    ORIGIN_SPACING_DAYS,
    PROTOCOL,
    _assert_min_history,
    _cached_forecast,
    _direct_prep,
    _lgbm_pool_direct_forecast,
    _package_versions,
    _panel_cache_key,
    _prepare_panel,
    first_diff_scale,
    m5_full_origins,
    official_wrmsse,
    revenue_weights,
    wrmsse_nodes,
)
from demand_forecasting.m5_full_catalog import (
    CATALOG_FORECASTS_NAME,
    CATALOG_META_NAME,
    _self_check,
    load_committed_ensemble,
    select_catalog_ids,
)
from demand_forecasting.m5_track import (
    HORIZON,
    MIN_TRAIN_DAYS,
    SEED,
    _actual_window,
    _attach_panel_features,
)

logger = get_logger(__name__)

#: the committed ensemble's positive-weight members (the only ones the blend
#: needs); the zero-weight member column carries over from the wave-32 catalog.
REFIT_MEMBERS: tuple[str, ...] = ("lgbm_pool_storecat", "lgbm_pool_dept")
#: reproduction gate tolerance on the official WRMSSE (absolute).
REPRO_TOL = 1e-6
#: headline node-bootstrap settings (seeded; offset distinct from the
#: erratic-refinement bootstraps at SEED+3301 / SEED+3401).
HEADLINE_BOOT_REPS = 2000
HEADLINE_BOOT_SEED_OFFSET = 3501
HEADLINE_INTERVAL_NAME = "headline_interval.json"
#: evaluation_metadata.json block logging this refit.
METADATA_BLOCK = "e9_blend_refit"


class RefitReproductionError(RuntimeError):
    """The refit failed the reproduction gate — no artifact was touched."""


def node_bootstrap_ci(
    rmsse: np.ndarray, w: np.ndarray, *, n_boot: int, seed: int
) -> dict[str, Any]:
    """Seeded node bootstrap of the official hierarchical WRMSSE.

    The official WRMSSE is a revenue-weighted mean of per-node RMSSEs, so its
    node-sampling noise is estimated by resampling the (weight, rmsse) node
    pairs with replacement and recomputing the weighted mean per replication
    (weights renormalized per draw) — the single-candidate counterpart of
    :func:`demand_forecasting.m5_full._wrmsse_delta_bootstrap`, same idiom.
    Bounds the node-sampling uncertainty of ONE test window's level; it is
    NOT a paired interval for the vs-floor gap and NOT across-origin noise.
    """
    rmsse = np.asarray(rmsse, dtype=float)
    w = np.asarray(w, dtype=float)
    if rmsse.shape != w.shape or rmsse.ndim != 1 or rmsse.size == 0:
        raise ValueError("node_bootstrap_ci needs aligned 1-D (rmsse, w) vectors")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, rmsse.size, size=(n_boot, rmsse.size))
    draws = (w[idx] * rmsse[idx]).sum(axis=1) / w[idx].sum(axis=1)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {
        "point": float((w * rmsse).sum() / w.sum()),
        "ci95": [float(lo), float(hi)],
        "n_boot": int(n_boot),
        "seed": int(seed),
    }


def _fit_member_parallel(
    prep: pd.DataFrame,
    panel: Any,
    name: str,
    *,
    seed: int,
    n_workers: int,
) -> np.ndarray:
    """One pooled direct member at the origin, group fits fanned out over a
    thread pool.

    Each (sorted-group) fit calls ``_lgbm_pool_direct_forecast`` with a
    single-group dict, which reproduces the committed sequential loop's
    per-group computation exactly (same rows, same per-h fits, same seed);
    assembling the per-group blocks in panel ``series_ids`` order therefore
    reproduces the committed candidate matrix byte-for-byte.
    """
    groups = panel.group_maps[name]
    series_ids = panel.series_ids
    pos = {sid: i for i, sid in enumerate(series_ids)}
    out = np.empty((len(series_ids), HORIZON), dtype=float)

    def _one(gkey: str) -> tuple[list[str], np.ndarray]:
        members = sorted(groups[gkey])
        mat = _lgbm_pool_direct_forecast(
            prep,
            seed,
            series_ids=members,
            groups={gkey: groups[gkey]},
            lgbm_params=panel.lgbm_params,
            name=f"{name}[{gkey}]",
        )
        return members, mat

    keys = sorted(groups)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        for k, (members, mat) in enumerate(pool.map(_one, keys)):
            for j, sid in enumerate(members):
                out[pos[sid]] = mat[j]
            logger.info(
                "e9 refit %s: group %s done (%d/%d, %.0fs elapsed)",
                name,
                keys[k],
                k + 1,
                len(keys),
                time.time() - t0,
            )
    if not np.isfinite(out).all():
        raise ValueError(f"{name} refit contains non-finite values")
    return out


def _update_catalog(
    reports_dir: Path,
    panel: Any,
    o: int,
    preds: dict[str, np.ndarray],
    members: list[str],
    weights: list[float],
    *,
    committed_wape: float,
    repro_block: dict[str, Any],
    runtime_seconds: float,
) -> dict[str, Any]:
    """Rewrite the catalog parquet/meta on the committed blend.

    Only the refit member columns, the recomputed ``convex_ensemble`` blend
    and the member-envelope band change; every other candidate column and the
    (deterministic, forecast-independent) catalog selection carry over. The
    catalog ids are re-derived and asserted equal to the persisted ones
    before anything is written.
    """
    catalog_path = reports_dir / CATALOG_FORECASTS_NAME
    meta_path = reports_dir / CATALOG_META_NAME
    frame = pd.read_parquet(catalog_path)
    meta = json.loads(meta_path.read_text())

    cat_pos, _descriptors = select_catalog_ids(panel, o, catalog_size=int(meta["catalog_size"]))
    catalog_ids = [panel.series_ids[i] for i in cat_pos]
    if list(dict.fromkeys(frame["unique_id"].tolist())) != catalog_ids:
        raise ValueError(
            "re-derived catalog selection does not match the persisted parquet "
            "— the catalog rule is forecast-independent; drift means a stale catalog"
        )
    expected_ids = np.repeat(catalog_ids, HORIZON)
    if not (frame["unique_id"].to_numpy() == expected_ids).all():
        raise ValueError("catalog parquet row order drifted (expected series-major, ds-ascending)")
    cat_idx = np.asarray(cat_pos)
    for name, mat in preds.items():
        frame[name] = np.concatenate([mat[i] for i in cat_idx])
    blend = np.zeros(len(frame))
    for w, member in zip(weights, members, strict=True):
        blend += w * frame[member].to_numpy(dtype=float)
    frame["convex_ensemble"] = blend
    member_stack = np.stack([frame[m].to_numpy(dtype=float) for m in members])
    frame["band_lo"] = member_stack.min(axis=0)
    frame["band_hi"] = member_stack.max(axis=0)

    actuals = _actual_window(panel.y_all, panel.series_ids, pd.Timestamp(panel.dates[o]), HORIZON)
    pre_check = _self_check(
        frame,
        members=members,
        weights=weights,
        actuals=actuals[cat_idx],
        catalog_ids=catalog_ids,
        ensemble_wape_committed=committed_wape,
    )

    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(frame, preserve_index=False)
    schema_meta = {
        "protocol": PROTOCOL,
        "origin": str(pd.Timestamp(panel.dates[o]).date()),
        "weights_source": meta["weights_source"],
        "ensemble": json.dumps({"members": members, "weights": weights}),
        "band": meta["band"],
        "e9_refit": json.dumps(
            {
                "members_refit": sorted(preds),
                "note": "pass-4 E9: refit members at the committed direct config; "
                "all other candidate columns carry over from the wave-32 "
                "recursive catalog run",
                "reproduction": repro_block,
            }
        ),
        "self_check": json.dumps(pre_check),
    }
    table = table.replace_schema_metadata(
        {
            **dict(table.schema.metadata or {}),
            **{k.encode(): v.encode() for k, v in schema_meta.items()},
        }
    )
    pq.write_table(table, catalog_path)

    reread = pq.read_table(catalog_path).to_pandas()
    post_check = _self_check(
        reread,
        members=members,
        weights=weights,
        actuals=actuals[cat_idx],
        catalog_ids=catalog_ids,
        ensemble_wape_committed=committed_wape,
    )

    meta["ensemble"] = {"members": members, "weights": weights}
    meta["self_check"] = post_check
    meta[METADATA_BLOCK] = {
        "date": time.strftime("%Y-%m-%d"),
        "wave": "grade pass 4 E9 (pass-3 finding P3.2)",
        "members_refit": sorted(preds),
        "members_carried_over": [
            c for c in meta["candidates"] if c not in preds and c != "convex_ensemble"
        ],
        "carried_over_note": "non-refit candidate columns (including the zero-weight "
        "lgbm_pool_store member) carry over from the wave-32 catalog run "
        "(recursive pooled fits) — they are demo comparison curves only and "
        "contribute nothing to the committed blend",
        "config": "committed run configuration: pooled_strategy=direct, seed 42, "
        "params.yaml m5_lgbm, n_jobs=1 + force_row_wise per fit; per-group fits "
        "parallelized across threads (identical numerics to the sequential path)",
        "reproduction": repro_block,
        "refit_runtime_seconds": round(runtime_seconds, 3),
        "package_versions": _package_versions(),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    logger.info("e9 catalog updated -> %s / %s", catalog_path, meta_path)
    return post_check


def run_m5_full_refit(
    raw_dir: Path,
    reports_dir: Path,
    *,
    n_workers: int = 8,
    n_boot: int = HEADLINE_BOOT_REPS,
    seed: int = SEED,
    params_path: Path | str = "params.yaml",
    cache_dir: Path | None = None,
    tol: float = REPRO_TOL,
    n_origins: int = N_ORIGINS,
    min_train: int = MIN_TRAIN_DAYS,
    n_estimators: int | None = None,
) -> dict[str, Any]:
    """Refit the active blend members at the test origin and repair the
    catalog-era artifacts on the committed blend. See the module docstring
    for the contract; the reproduction gate runs BEFORE any write."""
    t0 = time.time()
    raw_dir = Path(raw_dir)
    reports_dir = Path(reports_dir)
    metrics_path = reports_dir / "metrics.json"
    committed = json.loads(metrics_path.read_text())
    if committed.get("protocol") != PROTOCOL:
        raise ValueError(
            f"committed metrics protocol {committed.get('protocol')!r} != {PROTOCOL!r}"
        )
    members, weights = load_committed_ensemble(metrics_path)
    active = {m: w for m, w in zip(members, weights, strict=True) if w > 0}
    if set(active) != set(REFIT_MEMBERS):
        raise ValueError(
            f"committed positive-weight members {sorted(active)} != {sorted(REFIT_MEMBERS)} "
            "— the E9 two-member refit only covers the 0.95/0.05 committed blend"
        )

    cache_dir = Path(cache_dir) if cache_dir is not None else raw_dir / ".cache" / "full_forecasts"
    panel_key = _panel_cache_key(raw_dir)
    panel = _prepare_panel(
        raw_dir, series_cap=None, seed=seed, params_path=params_path, n_estimators=n_estimators
    )
    origins = m5_full_origins(panel.n_dates, n_origins, HORIZON, min_train, ORIGIN_SPACING_DAYS)
    o = origins[-1]
    odate = pd.Timestamp(panel.dates[o])
    _assert_min_history(panel.y_all, odate)
    logger.info(
        "e9 refit: test origin %s | members %s | %d workers | cache %s",
        odate.date(),
        REFIT_MEMBERS,
        n_workers,
        cache_dir,
    )

    a_all, y_wide, x_wide = panel.a_all, panel.y_wide, panel.x_wide
    train_nodes = np.asarray(a_all @ y_wide[:, : o + 1])
    actual_nodes = np.asarray(a_all @ y_wide[:, o + 1 : o + 1 + HORIZON])
    scale = first_diff_scale(train_nodes)
    node_w = revenue_weights(y_wide, x_wide, slice(o - HORIZON + 1, o + 1), a_all)

    # the committed per-origin fit path, minus the candidates we do not refit
    train = panel.y_all[panel.y_all["ds"] <= odate]
    hist_exog, _future_exog = split_exogenous(panel.x_enc, panel.series_ids, odate, HORIZON)
    _attach_panel_features(train, hist_exog, _future_exog, panel.s_all)
    t_prep = time.time()
    prep = _direct_prep(train, hist_exog, seed)
    logger.info("e9 refit: direct prep ready in %.0fs (%d rows)", time.time() - t_prep, len(prep))

    preds: dict[str, np.ndarray] = {}
    fit_seconds: dict[str, float] = {}
    for name in REFIT_MEMBERS:
        t_m = time.time()
        # the cache key carries no booster config: keep the committed-config
        # entry names shared with the wave-34 challenger cache, but namespace
        # smoke overrides so a stale override fit is never reused
        cache_name = name if n_estimators is None else f"{name}-ne{n_estimators}"
        mat, hit = _cached_forecast(
            cache_dir,
            panel_key,
            cache_name,
            o,
            panel.series_ids,
            partial(_fit_member_parallel, prep, panel, name, seed=seed, n_workers=n_workers),
        )
        preds[name] = mat
        fit_seconds[name] = time.time() - t_m
        logger.info(
            "e9 refit %s: %s (%.0fs)", name, "cache hit" if hit else "fitted", fit_seconds[name]
        )

    # ---- reproduction gate (STOP condition): nothing is written before this
    blend = np.zeros_like(preds[REFIT_MEMBERS[0]])
    for w, member in zip(weights, members, strict=True):
        if w > 0:
            blend += w * preds[member]
    refit_scores = {
        name: float(official_wrmsse(preds[name], actual_nodes, scale, node_w, a_all)[0])
        for name in REFIT_MEMBERS
    }
    refit_scores["convex_ensemble"] = float(
        official_wrmsse(blend, actual_nodes, scale, node_w, a_all)[0]
    )
    repro: dict[str, Any] = {"tolerance": tol, "members": {}, "passed": True}
    for name in (*REFIT_MEMBERS, "convex_ensemble"):
        committed_score = float(committed["test"][name]["official_wrmsse"])
        delta = abs(refit_scores[name] - committed_score)
        repro["members"][name] = {
            "committed": committed_score,
            "refit": refit_scores[name],
            "abs_delta": delta,
        }
        if delta > tol:
            repro["passed"] = False
    logger.info(
        "e9 reproduction gate: %s",
        {
            k: f"{v['refit']:.6f} vs {v['committed']:.6f} (|d| {v['abs_delta']:.2e})"
            for k, v in repro["members"].items()
        },
    )
    if not repro["passed"]:
        raise RefitReproductionError(
            "E9 refit failed the reproduction gate (tolerance "
            f"{tol}): {json.dumps(repro['members'], indent=2)} — no artifact was touched"
        )

    # ---- headline node bootstrap (committed blend, test origin) ----
    blend_nodes = np.asarray(a_all @ blend)
    rmsse, w_valid = wrmsse_nodes(blend_nodes - actual_nodes, scale, node_w)
    valid = np.isfinite(rmsse) & (w_valid > 0)
    boot_seed = seed + HEADLINE_BOOT_SEED_OFFSET
    interval = node_bootstrap_ci(rmsse[valid], w_valid[valid], n_boot=n_boot, seed=boot_seed)
    interval_block = {
        "protocol": PROTOCOL,
        "candidate": "convex_ensemble",
        "metric": "official_wrmsse",
        "origin": str(odate.date()),
        "origin_index": int(o),
        "point": interval["point"],
        "ci95": interval["ci95"],
        "method": "node bootstrap of the official hierarchical WRMSSE: the "
        "(revenue weight, per-node RMSSE) pairs of the committed blend's valid "
        "hierarchy nodes are resampled with replacement, weights renormalized "
        "per draw, weighted mean recomputed; percentile 2.5/97.5 over the "
        "resamples. Bounds the node-sampling uncertainty of the single test "
        "window's blend level — NOT a paired interval for the vs-floor gap "
        "and NOT across-origin uncertainty",
        "n_valid_nodes": int(valid.sum()),
        "n_boot": interval["n_boot"],
        "seed": interval["seed"],
        "seed_rule": f"m5_track.SEED ({seed}) + {HEADLINE_BOOT_SEED_OFFSET} — distinct from "
        "the erratic-refinement bootstrap offsets (3301/3401)",
        "ensemble": {"members": members, "weights": weights},
        "committed_source": "reports_m5_full/metrics.json test.convex_ensemble.official_wrmsse",
        "reproduction_abs_delta": repro["members"]["convex_ensemble"]["abs_delta"],
    }
    (reports_dir / HEADLINE_INTERVAL_NAME).write_text(json.dumps(interval_block, indent=2) + "\n")
    logger.info(
        "e9 headline interval: %.6f [%.6f, %.6f] (%d nodes, %d draws, seed %d)",
        interval["point"],
        interval["ci95"][0],
        interval["ci95"][1],
        int(valid.sum()),
        n_boot,
        boot_seed,
    )

    # ---- catalog repair + metadata log ----
    runtime = time.time() - t0
    post_check = _update_catalog(
        reports_dir,
        panel,
        o,
        preds,
        members,
        weights,
        committed_wape=float(committed["test"]["convex_ensemble"]["bottom_wape"]),
        repro_block=repro["members"],
        runtime_seconds=runtime,
    )
    meta_path = reports_dir / "evaluation_metadata.json"
    eval_meta = json.loads(meta_path.read_text())
    eval_meta[METADATA_BLOCK] = {
        "date": time.strftime("%Y-%m-%d"),
        "wave": "grade pass 4 E9 (pass-3 finding P3.2)",
        "purpose": "targeted refit of the positive-weight blend members at the test "
        "origin so the catalog, demo payload and sample-series figure serve the "
        "committed 0.6211 blend instead of the superseded 0.6161 one",
        "origin": str(odate.date()),
        "origin_index": int(o),
        "members_refit": list(REFIT_MEMBERS),
        "config": "committed run configuration (pooled_strategy=direct, seed 42, "
        "params.yaml m5_lgbm, n_jobs=1 + force_row_wise per fit); per-group fits "
        "parallelized across threads — identical numerics to the committed "
        "sequential loop",
        "reproduction": {"tolerance": tol, "passed": True, "members": repro["members"]},
        "headline_interval": f"reports_m5_full/{HEADLINE_INTERVAL_NAME}",
        "fit_seconds": {k: round(v, 3) for k, v in fit_seconds.items()},
        "runtime_seconds": round(runtime, 3),
        "n_workers": n_workers,
        "package_versions": _package_versions(),
    }
    meta_path.write_text(json.dumps(eval_meta, indent=2) + "\n")
    logger.info("e9 evaluation metadata logged -> %s", meta_path)

    return {
        "origin": str(odate.date()),
        "members": list(REFIT_MEMBERS),
        "reproduction": repro,
        "headline_interval": interval_block,
        "catalog_self_check": post_check,
        "fit_seconds": fit_seconds,
        "runtime_seconds": runtime,
    }
