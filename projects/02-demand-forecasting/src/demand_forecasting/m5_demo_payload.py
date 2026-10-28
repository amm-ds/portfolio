"""Demo payload for the ``forecast-workbench`` showcase demo (schema version 4).

Builds ``reports_m5/demo_payload.json`` — a compact, fully precomputed lookup
that lets the showcase UI render per-series forecast curves for the M5
headline track without retraining:

- a deterministic 24-series catalog, balanced across the 3 stores and the
  dense/intermittent volume classes, tagged by shape (steady / weekly-peaked /
  event-driven / slow-mover);
- per catalog series x the 2 scored test origins: the 56-day history tail,
  the 28-day actuals, and curves for ``seasonal_naive`` / ``auto_ets`` /
  ``lgbm`` / ``convex_ensemble``, plus the lgbm p10/p90 conformal band and
  per-series test WAPE per candidate;
- the committed headline block (``reports_m5/metrics.json`` +
  ``probabilistic.json``) verbatim under ``groups``.

Curve provenance (honest, documented in the payload): the per-series
statistical candidates re-run the SAME ``m5_track`` functions on the catalog
subset — their fits are per series, so they reproduce the committed
full-panel forecasts exactly. The ``convex_ensemble`` curve applies the
COMMITTED selection rule (members + weight from the committed metrics block)
to the two member curves — both members are per-series, so the ensemble curve
is exact for any catalog series. The ``lgbm`` curve is a documented
catalog-subset refit: the committed global model trains on all 600 series and
cannot be cheaply re-fit outside the full ~22-min track.

Drift guard: the per-series statistical candidates are re-scored over the
FULL panel at the 2 committed test origins (statsforecast only — C-fast) and
their pooled test WAPEs are pinned against the committed metrics block at
1e-9. A tampered dataset, a drifted ``m5_track`` function or a hand-edited
metrics.json fails the build here, not silently in the demo.

Everything is deterministic: fixed selection rule, seeded lgbm refit,
4-decimal rounding, stable key order — two runs produce byte-identical JSON.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from portfolio_core.logging import get_logger

from demand_forecasting.m5_data import (
    encode_events,
    load_m5_subset,
    split_exogenous,
)
from demand_forecasting.m5_track import (
    HORIZON,
    PROTOCOL,
    SEED,
    STATISTICAL_CANDIDATES,
    _actual_window,
    _lgbm_forecast,
    _statistical_forecasts,
    wape,
)

logger = get_logger(__name__)

DEMO_PAYLOAD_NAME = "demo_payload.json"
SCHEMA_VERSION = 4
DEMO_ID = "forecast-workbench"
#: history tail rendered before each scored origin (8 weekly cycles).
HISTORY_DAYS = 56
#: catalog quota per (store x class) cell -> 3 stores x 2 classes x 4 = 24.
CATALOG_PER_CELL = 4
#: drift-guard tolerance on the recomputed pooled test WAPE (absolute).
DRIFT_TOL = 1e-9

CATALOG_RULE = (
    "deterministic: within each (store, class) cell, series are ordered by "
    "total panel volume descending (ties -> unique_id) and the evenly spaced "
    "ranks [0, 1, len//2, len-1] (first CATALOG_PER_CELL of them) are picked, "
    "so every cell spans high/mid/low volume"
)

#: per-series candidates whose curves the demo renders (all per-series fits —
#: exact against the committed run; lgbm is the documented subset refit).
CURVE_CANDIDATES = ("seasonal_naive", "auto_ets", "lgbm", "convex_ensemble")

CURVE_PROVENANCE = (
    "per-series curves (seasonal_naive, auto_ets) re-run the m5_track "
    "functions on the catalog subset and reproduce the committed full-panel "
    "forecasts exactly (per-series fits); convex_ensemble applies the "
    "committed selection rule (auto_ets x weight_on_a + auto_ces x (1-w)) to "
    "the member curves; lgbm is a catalog-subset refit of the fixed config "
    "(the committed global model trains on all 600 series) — per-series "
    "test WAPEs in each window are computed from these curves"
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


def _select_catalog(
    y: pd.DataFrame,
    classes: dict[str, dict[str, Any]],
    stores: pd.Series,
    *,
    per_cell: int = CATALOG_PER_CELL,
) -> list[str]:
    """Deterministic catalog: balanced across stores x {dense, intermittent}.

    Rule (documented in the payload): within each cell, series are ordered by
    total panel volume descending (ties -> unique_id); the evenly spaced
    ranks [0, 1, len//2, len-1] — first ``per_cell`` of them — are picked.
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


def _is_dense(syntetos_boylan_class: str) -> bool:
    return syntetos_boylan_class in ("smooth", "erratic")


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
    stats: dict[str, np.ndarray],
    lgbm: np.ndarray,
    ens_members: tuple[str, str],
    ens_w: float,
    band_width: np.ndarray,
    curve_names: tuple[str, ...],
) -> dict[str, Any]:
    """One (origin x catalog) window: history tail, actuals, curves, band, WAPEs."""
    hist_start = odate - pd.to_timedelta(HISTORY_DAYS - 1, unit="D")
    tail = y_all[(y_all["ds"] >= hist_start) & (y_all["ds"] <= odate)]
    grid = tail.pivot(index="unique_id", columns="ds", values="y").reindex(catalog_ids)
    if grid.shape != (len(catalog_ids), HISTORY_DAYS) or grid.isna().any().any():
        raise ValueError(f"history tail before {odate.date()} is not a full grid")
    history = grid.to_numpy(dtype=float)

    actuals = _actual_window(y_all, catalog_ids, odate, HORIZON)
    days = pd.date_range(odate + pd.to_timedelta(1, unit="D"), periods=HORIZON, freq="D")

    member_a, member_b = stats[ens_members[0]], stats[ens_members[1]]
    curves = dict(stats)  # every per-series candidate the track fit
    curves["lgbm"] = lgbm
    curves["convex_ensemble"] = ens_w * member_a + (1.0 - ens_w) * member_b
    windows: dict[str, Any] = {}
    for i, sid in enumerate(catalog_ids):
        curves_i = {c: _r4(curves[c][i]) for c in curve_names}
        actual_i = actuals[i]
        p50 = curves["lgbm"][i]
        lo = np.clip(p50 - band_width, 0.0, None)
        hi = p50 + band_width
        windows[sid] = {
            "history": _r4(history[i]),
            "actual": _r4(actual_i),
            "curves": curves_i,
            "band": {"p10": _r4(lo), "p90": _r4(hi)},
            "wape": {c: round(wape(actual_i, curves[c][i]), 4) for c in curve_names},
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
    *,
    per_cell: int = CATALOG_PER_CELL,
) -> dict[str, Any]:
    """Assemble the forecast-workbench payload from the committed M5 artifacts."""
    reports_dir = Path(reports_dir)
    metrics, probabilistic, metadata = _load_committed(reports_dir)
    y_all, x_all, s_all = load_m5_subset(Path(data_dir))
    series_ids = sorted(y_all["unique_id"].unique().tolist())
    dates = np.sort(y_all["ds"].unique())
    test_origins = _test_origin_dates(metrics)

    _drift_guard_full_panel(y_all, series_ids, dates, test_origins, metrics)

    classes: dict[str, dict[str, Any]] = metrics["classes"]["per_series"]
    stores = s_all.drop_duplicates("unique_id").set_index("unique_id")["store_id"]
    catalog_ids = _select_catalog(y_all, classes, stores, per_cell=per_cell)
    if len(catalog_ids) < 2:
        raise ValueError(f"catalog too small ({len(catalog_ids)} series) — check the classes block")
    logger.info("m5 demo catalog: %d series (%s)", len(catalog_ids), catalog_ids)

    state_of = s_all.drop_duplicates("unique_id").set_index("unique_id")["state_id"]
    x_enc = encode_events(x_all, x_all["unique_id"].map(state_of))
    # split_exogenous expects the frame pre-filtered to the scored series set
    # (its future-window row-count check is series_ids x horizon).
    x_cat = x_enc[x_enc["unique_id"].isin(catalog_ids)]

    # Committed ensemble rule: members + weight read from the metrics block
    # (the demo applies the same rule the track committed to).
    ens_members = tuple(metrics["ensemble"]["members"])
    if len(ens_members) != 2:
        raise ValueError(f"committed ensemble must have 2 members, got {ens_members}")
    ens_w = float(metrics["ensemble"]["weight_on_a"])
    band_width = np.asarray(probabilistic["per_horizon_width"], dtype=float)
    # ship the demo candidates plus any committed ensemble member not among
    # them (the blend is verifiable from the shipped curves)
    curve_names = tuple(dict.fromkeys((*CURVE_CANDIDATES, *ens_members)))

    origin_blocks: list[dict[str, Any]] = []
    for odate in test_origins:
        train = y_all[(y_all["ds"] <= odate) & (y_all["unique_id"].isin(catalog_ids))]
        stats = _statistical_forecasts(train, catalog_ids, HORIZON)
        hist_exog, future_exog = split_exogenous(x_cat, catalog_ids, odate, HORIZON)
        lgbm = _lgbm_forecast(train, hist_exog, future_exog, SEED)
        origin_blocks.append(
            _window_payload(
                y_all, catalog_ids, odate, stats, lgbm, ens_members, ens_w, band_width, curve_names
            )
        )

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
                "per_horizon_width": _r4(band_width),
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
