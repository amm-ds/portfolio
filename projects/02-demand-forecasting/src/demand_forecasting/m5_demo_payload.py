"""Demo payload for the ``forecast-workbench`` showcase demo (schema version 4).

Builds ``reports_m5/demo_payload.json`` — a compact, fully precomputed lookup
that lets the showcase UI render per-series forecast curves for the M5
headline track without retraining:

- a deterministic 24-series catalog, balanced across the 3 stores and the
  dense/intermittent volume classes, tagged by shape (steady / weekly-peaked /
  event-driven / slow-mover);
- per catalog series x the 2 scored test origins: the 56-day history tail,
  the 28-day actuals, and curves for ``seasonal_naive`` / ``auto_ets`` /
  ``auto_ces`` / ``lgbm`` / ``lgbm_l2`` / ``xgb`` / ``convex_ensemble`` /
  ``ensemble_l2``, plus the lgbm p10/p90 conformal band and per-series test
  WAPE per candidate;
- the committed headline block (``reports_m5/metrics.json`` +
  ``probabilistic.json``) verbatim under ``groups``.

Curve provenance (honest, documented in the payload): EVERY curve — including
lgbm and the ensemble — is copied from ``reports_m5/catalog_forecasts.parquet``,
the sidecar the evaluate run retains for the fixed catalog (the committed
global 600-series model cannot be re-fit outside the ~22-min track, and the
earlier catalog-subset refit approximation was retired: it was weaker than the
full-panel model and, via an mlforecast alphabetical-row-order mismatch, its
curves landed on the wrong series).

Drift guards, so a stale or tampered artifact fails the build, not the demo:
- the per-series statistical candidates are re-scored over the FULL panel at
  the 2 committed test origins (statsforecast only — C-fast) and their pooled
  test WAPEs are pinned against the committed metrics block at 1e-9;
- the sidecar's schema metadata carries the run's full-panel pooled test
  WAPEs — pinned against the committed metrics block at 1e-9 (mixing artifacts
  from different runs fails here);
- the sidecar's per-series statistical curves and actuals are pinned against a
  live catalog-subset re-run of the same functions at 1e-9.

Everything is deterministic: fixed catalog (from the sidecar), fixed
selection rule, 4-decimal rounding, stable key order — two runs produce
byte-identical JSON.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from portfolio_core.logging import get_logger

from demand_forecasting.m5_data import (
    encode_events,
    load_m5_subset,
)
from demand_forecasting.m5_track import (
    CATALOG_FORECASTS_NAME,
    CATALOG_RULE,
    HORIZON,
    PROTOCOL,
    SIDECAR_CANDIDATES,
    STATISTICAL_CANDIDATES,
    _actual_window,
    _is_dense,
    _statistical_forecasts,
    wape,
)

__all__ = ["build_demo_payload", "write_demo_payload"]

logger = get_logger(__name__)

DEMO_PAYLOAD_NAME = "demo_payload.json"
SCHEMA_VERSION = 4
DEMO_ID = "forecast-workbench"
#: history tail rendered before each scored origin (8 weekly cycles).
HISTORY_DAYS = 56
#: drift-guard tolerance on recomputed pooled test WAPEs (absolute).
DRIFT_TOL = 1e-9
#: sidecar candidates whose curves ship in the payload (all per-series fits
#: are exactly verifiable against a live re-run; lgbm/lgbm_l2/xgb/ensembles
#: come from the committed global run via the sidecar). auto_ces ships
#: explicitly — it entered the set as a wave-25 ensemble member and stays
#: shipped for backward compatibility even though the wave-27/28 blend does
#: not use it; xgb joined in wave 27 (new ensemble member); wave 28 adds the
#: L1/L2 pair lgbm_l2 + ensemble_l2 (new keys inside the open-keyed curves
#: map — schema_version stays 4, the manifest contract is unchanged).
CURVE_CANDIDATES = (
    "seasonal_naive",
    "auto_ets",
    "auto_ces",
    "lgbm",
    "lgbm_l2",
    "xgb",
    "convex_ensemble",
    "ensemble_l2",
)

CURVE_PROVENANCE = (
    "every curve (seasonal_naive, auto_ets, auto_ces, lgbm, lgbm_l2, xgb, "
    "convex_ensemble, ensemble_l2) "
    "is copied from reports_m5/catalog_forecasts.parquet, the sidecar the "
    "committed evaluate run retains for this exact catalog — the lgbm and "
    "lgbm_l2 curves are the committed global 600-series models (no "
    "catalog-subset refit); the "
    "ensemble curves are the committed selection rules applied in-run "
    "(convex_ensemble under selection WAPE, ensemble_l2 under selection "
    "WRMSSE); per-series test WAPEs in each window are computed from these "
    "curves"
)


def _r4(values: np.ndarray | list[float]) -> list[float]:
    """Round to 4 decimals (JSON size) — deterministic."""
    return [round(float(v), 4) for v in values]


def _load_committed(reports_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    metrics = json.loads((reports_dir / "metrics.json").read_text())
    probabilistic = json.loads((reports_dir / "probabilistic.json").read_text())
    metadata = json.loads((reports_dir / "evaluation_metadata.json").read_text())
    if metrics.get("protocol") != PROTOCOL:
        raise ValueError(
            f"committed metrics protocol {metrics.get('protocol')!r} != {PROTOCOL!r} "
            "— the payload must be built from the m5_direct_v1 artifacts"
        )
    return metrics, probabilistic, metadata


def _test_origin_dates(metrics: dict[str, Any]) -> list[pd.Timestamp]:
    tests = metrics["origins"]["test"]
    if len(tests) != 2:
        raise ValueError(f"expected 2 scored test origins, got {tests}")
    return [pd.Timestamp(d) for d in tests]


def _drift_guard_full_panel(
    y_all: pd.DataFrame,
    series_ids: list[str],
    dates: np.ndarray,
    test_origins: list[pd.Timestamp],
    metrics: dict[str, Any],
) -> None:
    """Re-score the per-series candidates over the FULL panel at the test
    origins and pin the pooled test WAPEs against the committed block.

    statsforecast fits are per series and closed-form, so this reproduces the
    committed run's forecasts bitwise; any dataset/code/metrics drift shows up
    as a WAPE difference above 1e-9.
    """
    committed = metrics["test"]["pooled"]
    per_origin: dict[pd.Timestamp, tuple[dict[str, np.ndarray], np.ndarray]] = {}
    for odate in test_origins:
        o_idx = int(np.searchsorted(dates, np.datetime64(odate)))
        train = y_all[y_all["ds"] <= odate]
        preds = _statistical_forecasts(train, series_ids, HORIZON)
        actuals = _actual_window(y_all, series_ids, pd.Timestamp(dates[o_idx]), HORIZON)
        per_origin[odate] = (preds, actuals)
    for cand in STATISTICAL_CANDIDATES:
        pred = np.concatenate([per_origin[o][0][cand] for o in test_origins])
        act = np.concatenate([per_origin[o][1] for o in test_origins])
        recomputed = wape(act, pred)
        expected = committed[cand]["wape"]
        if abs(recomputed - expected) > DRIFT_TOL:
            raise ValueError(
                f"drift guard failed for {cand}: recomputed pooled test WAPE "
                f"{recomputed!r} != committed {expected!r} (tol {DRIFT_TOL}) — "
                "the dataset, m5_track or the committed metrics drifted"
            )
    logger.info(
        "drift guard OK: %d per-series candidates pinned at %g",
        len(STATISTICAL_CANDIDATES),
        DRIFT_TOL,
    )


def _load_sidecar(
    reports_dir: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read the demo sidecar parquet + its schema-metadata block."""
    path = Path(reports_dir) / CATALOG_FORECASTS_NAME
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path} — run `evaluate-m5` first (the payload copies "
            "the catalog curves from the committed run's sidecar)"
        )
    table = pq.read_table(path)
    raw_meta = table.schema.metadata or {}
    meta = {key.decode(): json.loads(value.decode()) for key, value in raw_meta.items()}
    frame = table.to_pandas()
    expected_cols = {
        "unique_id",
        "origin",
        "ds",
        "actual",
        "band_lo",
        "band_hi",
        *SIDECAR_CANDIDATES,
    }
    missing = expected_cols - set(frame.columns)
    if missing:
        raise ValueError(f"sidecar {path} is missing columns {sorted(missing)}")
    return frame, meta


def _sidecar_guard(
    sidecar: pd.DataFrame,
    sidecar_meta: dict[str, Any],
    metrics: dict[str, Any],
    y_all: pd.DataFrame,
    catalog_ids: list[str],
    test_origins: list[pd.Timestamp],
) -> None:
    """Pin the sidecar against the committed metrics AND a live re-run.

    - schema-metadata pooled test WAPEs vs the committed metrics block (1e-9):
      mixing a sidecar and metrics.json from DIFFERENT runs fails here;
    - per-series statistical curves + actuals vs a live catalog-subset re-run
      of the same m5_track functions (1e-9): dataset / m5_track drift fails
      here. statsforecast fits are per series and closed-form, so the live
      re-run reproduces the committed full-panel forecasts exactly.
    """
    committed = metrics["test"]["pooled"]
    for cand, value in sidecar_meta.get("pooled_test_wape", {}).items():
        if cand not in committed:
            continue
        if abs(float(value) - committed[cand]["wape"]) > DRIFT_TOL:
            raise ValueError(
                f"sidecar drift guard failed for {cand}: sidecar pooled test "
                f"WAPE {value!r} != committed {committed[cand]['wape']!r} "
                f"(tol {DRIFT_TOL}) — the sidecar and metrics.json come from "
                "different runs; re-run `evaluate-m5` and rebuild both"
            )
    # self-consistency: the catalog-only pooled test WAPEs must recompute
    # from the shipped curves (a tampered lgbm/ensemble column fails here —
    # those curves have no live re-run reference)
    actual_np = sidecar["actual"].to_numpy(dtype=float)
    for cand, expected in sidecar_meta.get("catalog_test_wape", {}).items():
        curve = sidecar[cand].to_numpy(dtype=float)
        recomputed = float(np.abs(curve - actual_np).sum() / actual_np.sum())
        if abs(recomputed - float(expected)) > DRIFT_TOL:
            raise ValueError(
                f"sidecar curve guard failed for {cand}: recomputed catalog "
                f"pooled test WAPE {recomputed!r} != recorded {expected!r} — "
                "the sidecar curves were tampered with or corrupted"
            )
    check_candidates = tuple(c for c in ("seasonal_naive", "auto_ets", "auto_ces") if c in sidecar)
    for odate in test_origins:
        train = y_all[(y_all["ds"] <= odate) & (y_all["unique_id"].isin(catalog_ids))]
        live = _statistical_forecasts(train, catalog_ids, HORIZON)
        live_actuals = _actual_window(y_all, catalog_ids, pd.Timestamp(odate), HORIZON)
        block = sidecar[sidecar["origin"] == str(odate.date())]
        if len(block) != len(catalog_ids) * HORIZON:
            raise ValueError(f"sidecar block for {odate.date()} has {len(block)} rows")
        grid = block.pivot(index="unique_id", columns="ds", values="actual").reindex(catalog_ids)
        if grid.isna().any().any():
            raise ValueError(f"sidecar actuals for {odate.date()} are not a full grid")
        if float(np.max(np.abs(grid.to_numpy(dtype=float) - live_actuals))) > DRIFT_TOL:
            raise ValueError(f"sidecar actuals drifted from the dataset at {odate.date()}")
        for cand in check_candidates:
            grid_c = block.pivot(index="unique_id", columns="ds", values=cand).reindex(catalog_ids)
            diff = float(np.max(np.abs(grid_c.to_numpy(dtype=float) - live[cand])))
            if diff > DRIFT_TOL:
                raise ValueError(
                    f"sidecar drift guard failed for {cand} at {odate.date()}: "
                    f"max |curve diff| {diff} > {DRIFT_TOL} — the dataset or "
                    "m5_track drifted from the committed run"
                )
    logger.info(
        "sidecar drift guard OK: pooled WAPEs + %d per-series curves pinned at %g",
        len(check_candidates),
        DRIFT_TOL,
    )


def _shape_tag(
    hist_y: np.ndarray, hist_dates: np.ndarray, event_mask: np.ndarray, demand_class: str
) -> str:
    """Deterministic shape tag from the 56-day history tail.

    Thresholds are fixed a priori against the M5 catalog's observed spread
    (peak-weekday ratios land at 1.1-1.9): slow-mover (intermittent with
    >=25% zero days) -> weekly-peaked (peak weekday mean >= 1.5x the overall
    daily mean) -> event-driven (>=20% of tail demand on event days) -> steady.
    ``event_mask`` marks real event days (see :func:`_event_mask`).
    """
    mean = float(np.mean(hist_y))
    if demand_class == "intermittent" and float(np.mean(hist_y == 0)) >= 0.25:
        return "slow-mover"
    dow = pd.to_datetime(hist_dates).dayofweek.to_numpy()
    daily = np.full(7, np.nan)
    for d in range(7):
        vals = hist_y[dow == d]
        if len(vals):
            daily[d] = np.mean(vals)
    with np.errstate(invalid="ignore"):
        peak_ratio = float(np.nanmax(daily) / max(np.nanmean(daily), 1e-9))
    if mean > 0 and peak_ratio >= 1.5:
        return "weekly-peaked"
    event_share = float(np.sum(hist_y[event_mask])) / max(float(np.sum(hist_y)), 1e-9)
    if event_share >= 0.2:
        return "event-driven"
    return "steady"


def _window_payload(
    y_all: pd.DataFrame,
    catalog_ids: list[str],
    odate: pd.Timestamp,
    sidecar_block: pd.DataFrame,
    curve_names: tuple[str, ...],
) -> dict[str, Any]:
    """One (origin x catalog) window: history tail (live) + curves/band (sidecar)."""
    hist_start = odate - pd.to_timedelta(HISTORY_DAYS - 1, unit="D")
    tail = y_all[(y_all["ds"] >= hist_start) & (y_all["ds"] <= odate)]
    grid = tail.pivot(index="unique_id", columns="ds", values="y").reindex(catalog_ids)
    if grid.shape != (len(catalog_ids), HISTORY_DAYS) or grid.isna().any().any():
        raise ValueError(f"history tail before {odate.date()} is not a full grid")
    history = grid.to_numpy(dtype=float)

    days = pd.date_range(odate + pd.to_timedelta(1, unit="D"), periods=HORIZON, freq="D")
    block_days = np.sort(sidecar_block["ds"].unique())
    if len(block_days) != HORIZON or not (block_days == days.to_numpy()).all():
        raise ValueError(f"sidecar dates for {odate.date()} do not match the forecast window")

    windows: dict[str, Any] = {}
    for i, sid in enumerate(catalog_ids):
        row = sidecar_block[sidecar_block["unique_id"] == sid].sort_values("ds")
        if len(row) != HORIZON:
            raise ValueError(f"sidecar has {len(row)} rows for {sid} at {odate.date()}")
        actual_i = row["actual"].to_numpy(dtype=float)
        curves_i = {c: row[c].to_numpy(dtype=float) for c in curve_names}
        windows[sid] = {
            "history": _r4(history[i]),
            "actual": _r4(actual_i),
            "curves": {c: _r4(v) for c, v in curves_i.items()},
            "band": {
                "p10": _r4(row["band_lo"].to_numpy(dtype=float)),
                "p90": _r4(row["band_hi"].to_numpy(dtype=float)),
            },
            "wape": {c: round(wape(actual_i, curves_i[c]), 4) for c in curve_names},
        }
    return {
        "origin": str(odate.date()),
        "history_start": str(hist_start.date()),
        "history_dates": [
            str(d.date()) for d in pd.date_range(hist_start, periods=HISTORY_DAYS, freq="D")
        ],
        "forecast_dates": [str(d.date()) for d in days],
        "windows": windows,
    }


def build_demo_payload(
    data_dir: Path,
    reports_dir: Path,
) -> dict[str, Any]:
    """Assemble the forecast-workbench payload from the committed M5 artifacts."""
    reports_dir = Path(reports_dir)
    metrics, probabilistic, metadata = _load_committed(reports_dir)
    y_all, x_all, s_all = load_m5_subset(Path(data_dir))
    series_ids = sorted(y_all["unique_id"].unique().tolist())
    dates = np.sort(y_all["ds"].unique())
    test_origins = _test_origin_dates(metrics)

    _drift_guard_full_panel(y_all, series_ids, dates, test_origins, metrics)

    sidecar, sidecar_meta = _load_sidecar(reports_dir)
    catalog_ids = list(dict.fromkeys(sidecar["unique_id"].tolist()))
    if len(catalog_ids) < 2:
        raise ValueError(f"catalog too small ({len(catalog_ids)} series) — check the sidecar")
    logger.info("m5 demo catalog: %d series (%s)", len(catalog_ids), catalog_ids)
    _sidecar_guard(sidecar, sidecar_meta, metrics, y_all, catalog_ids, test_origins)

    classes: dict[str, dict[str, Any]] = metrics["classes"]["per_series"]
    stores = s_all.drop_duplicates("unique_id").set_index("unique_id")["store_id"]
    state_of = s_all.drop_duplicates("unique_id").set_index("unique_id")["state_id"]
    x_enc = encode_events(x_all, x_all["unique_id"].map(state_of))

    # Committed ensemble rule: members + weights read from the metrics block
    # (the shipped ensemble curve is verified against this rule in the tests).
    ens_members = tuple(metrics["ensemble"]["members"])
    if len(ens_members) < 2:
        raise ValueError(f"committed ensemble must have >= 2 members, got {ens_members}")
    ens_weights = [float(w) for w in metrics["ensemble"]["weights"]]
    if len(ens_weights) != len(ens_members):
        raise ValueError("committed ensemble weights/members length mismatch")
    for member in ens_members:
        if member not in sidecar.columns:
            raise ValueError(f"committed ensemble member {member!r} missing from the sidecar")
    # ship the demo candidates plus any committed ensemble member not among
    # them (the blend is verifiable from the shipped curves)
    curve_names = tuple(dict.fromkeys((*CURVE_CANDIDATES, *ens_members)))

    origin_blocks: list[dict[str, Any]] = []
    for odate in test_origins:
        block = sidecar[sidecar["origin"] == str(odate.date())]
        origin_blocks.append(_window_payload(y_all, catalog_ids, odate, block, curve_names))

    # shape tags: deterministic, from the 56-day history tail + event codes.
    # The no-event marker is whatever encode_events assigned to the dominant
    # (no-event) category — its string sorts first or last depending on how
    # the parquet represented nulls, so resolve it from the mode, not a
    # hardcoded code.
    no_event_code = {
        col: int(x_enc[col].mode().iloc[0]) for col in ("event_name_1_code", "event_name_2_code")
    }
    catalog = []
    for sid in catalog_ids:
        per_origin = {}
        for block in origin_blocks:
            win = block["windows"][sid]
            shape = _shape_tag(
                np.asarray(win["history"], dtype=float),
                np.asarray(block["history_dates"], dtype=object),
                _event_mask(x_enc, sid, block["history_start"], no_event_code),
                "dense" if _is_dense(classes[sid]["class"]) else "intermittent",
            )
            per_origin[block["origin"]] = {**win, "shape": shape}
        catalog.append(
            {
                "series_id": sid,
                "store": str(stores.loc[sid]),
                "class": "dense" if _is_dense(classes[sid]["class"]) else "intermittent",
                "adi": round(float(classes[sid]["adi"]), 4),
                "cv2": round(float(classes[sid]["cv2"]), 4),
                "origins": per_origin,
            }
        )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "demo": DEMO_ID,
        "project": "02-demand-forecasting",
        "protocol": PROTOCOL,
        "groups": {
            "headline": metrics["headline"],
            "test_pooled": metrics["test"]["pooled"],
            "test_by_class": {
                cand: metrics["test"]["by_class"][cand]
                for cand in ("seasonal_naive", "auto_ets", "lgbm", "convex_ensemble")
            },
            "win_rate_vs_naive": metrics["test"]["win_rate_vs_naive"],
            "classes": {
                "counts": metrics["classes"]["counts"],
                "thresholds": metrics["classes"]["thresholds"],
            },
            "ensemble": metrics["ensemble"],
            "band": {
                "method": probabilistic["method"],
                "level": probabilistic["level"],
                "per_horizon_width": probabilistic["per_horizon_width"],
                "candidates": probabilistic["candidates"],
            },
        },
        "catalog_rule": CATALOG_RULE,
        "curve_provenance": CURVE_PROVENANCE,
        "history_days": HISTORY_DAYS,
        "origins": [
            {
                "origin": block["origin"],
                "history_start": block["history_start"],
                "forecast_dates": block["forecast_dates"],
            }
            for block in origin_blocks
        ],
        "catalog": catalog,
        "evaluation_metadata": {
            "protocol": metadata["protocol"],
            "dataset": {
                "subset_rule": metadata["dataset"]["subset_rule"],
                "observed_panel": metadata["dataset"]["observed_panel"],
                "citation": metadata["dataset"]["citation"],
            },
            "split": metadata["split"],
            "seeds": metadata["seeds"],
            "determinism": metadata["determinism"],
        },
    }
    return payload


def _event_mask(
    x_enc: pd.DataFrame, sid: str, history_start: str, no_event_code: dict[str, int]
) -> np.ndarray:
    """Real-event-day mask over the 56-day tail: a day is an event day when
    either event column carries a code different from its no-event mode."""
    start = pd.Timestamp(history_start)
    end = start + pd.to_timedelta(HISTORY_DAYS, unit="D")
    tail = x_enc[(x_enc["unique_id"] == sid) & (x_enc["ds"] >= start) & (x_enc["ds"] < end)]
    if len(tail) != HISTORY_DAYS:
        raise ValueError(f"exog tail for {sid} has {len(tail)} rows, expected {HISTORY_DAYS}")
    c1 = tail["event_name_1_code"].to_numpy(dtype=float)
    c2 = tail["event_name_2_code"].to_numpy(dtype=float)
    mask: np.ndarray = (c1 != no_event_code["event_name_1_code"]) | (
        c2 != no_event_code["event_name_2_code"]
    )
    return mask


def write_demo_payload(data_dir: Path, reports_dir: Path) -> Path:
    """Build the payload and persist it to ``reports_m5/demo_payload.json``."""
    reports_dir = Path(reports_dir)
    payload = build_demo_payload(data_dir, reports_dir)
    out = reports_dir / DEMO_PAYLOAD_NAME
    out.write_text(json.dumps(payload, indent=2) + "\n")
    size_kb = out.stat().st_size / 1024
    logger.info(
        "m5 demo payload: %d catalog series, %d origins -> %s (%.0f KB)",
        len(payload["catalog"]),
        len(payload["origins"]),
        out,
        size_kb,
    )
    if size_kb > 1024:
        raise ValueError(f"demo payload exceeds the 1 MB cap: {size_kb:.0f} KB")
    return out
