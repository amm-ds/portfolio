"""Demo payload for the ``forecast-workbench`` showcase demo — FULL-panel
track (wave 32, protocol ``m5_full_v1``).

Builds ``reports_m5_full/demo_payload.json`` mirroring the subset payload's
schema (schema_version 4: ``groups.{headline, test_pooled, test_by_class,
win_rate_vs_naive, classes, ensemble, band, stability}`` plus the per-series
catalog section) so the workbench renders both tracks through the same code
path. Provenance differs from the subset payload and is stated field by field
in ``groups._scope``:

- ``test_pooled`` / ``stability`` / ``classes`` / ``ensemble`` are PANEL-based
  — copied from the committed ``reports_m5_full/metrics.json`` (the official
  hierarchical WRMSSE over all 42,840 nodes + the full-panel bottom metrics);
- ``win_rate_vs_naive`` and ``test_by_class`` are CATALOG-based — the
  committed run did not persist per-series forecasts, so per-series wins vs
  the seasonal-naive floor and per-class WAPEs are computed from
  ``catalog_forecasts.parquet`` (the 48-series wave-32 catalog) and are
  subset statistics, never panel claims;
- ``band`` is CATALOG-based and honest about what it is: the ensemble
  member-envelope (per-day min/max of the committed members), NOT a
  calibrated conformal band — the full track has no probabilistic block;
- the per-series catalog windows copy the persisted catalog curves (the
  same committed-weights blend the catalog run wrote), with the 56-day
  history tails sliced live from the checksum-pinned raw panel.

Guards, so a stale or tampered artifact fails the build, not the demo:
- the catalog's committed ensemble (members/weights) must equal the metrics
  block's ensemble exactly (mixing artifacts from different runs fails here);
- the persisted ensemble curve must recompute from the persisted member
  columns at 1e-9 (a tampered blend column fails here);
- the catalog meta's protocol/version must match the full track.

Everything is deterministic: fixed catalog (from the parquet), 4-decimal
rounding, stable key order — two runs produce byte-identical JSON.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from portfolio_core.logging import get_logger

from demand_forecasting.m5_full import CANDIDATES, PROTOCOL
from demand_forecasting.m5_full_catalog import CATALOG_FORECASTS_NAME, CATALOG_META_NAME
from demand_forecasting.m5_track import HORIZON, wape

__all__ = ["build_demo_payload_full", "write_demo_payload_full"]

logger = get_logger(__name__)

DEMO_PAYLOAD_NAME = "demo_payload.json"
SCHEMA_VERSION = 4
DEMO_ID = "forecast-workbench"
#: history tail rendered before the scored window (8 weekly cycles).
HISTORY_DAYS = 56
#: guard tolerance on the persisted-blend recomputation (absolute).
DRIFT_TOL = 1e-9

SCOPE = {
    "headline": "panel: built from the committed full metrics test block "
    "(official hierarchical WRMSSE); no bootstrap CIs — the full track has none",
    "test_pooled": "panel: full-panel test bottom WAPE + official WRMSSE + bias "
    "per candidate, copied from the committed metrics block",
    "test_by_class": "catalog: per-class WAPE pooled over the catalog series "
    "only (the committed run persisted no per-series forecasts)",
    "win_rate_vs_naive": "catalog: per-series wins vs seasonal_naive over the "
    "catalog series only (subset statistic, not a panel claim)",
    "classes": "panel: ADI/CV² counts over all 30,490 series (train history to "
    "the last selection origin)",
    "ensemble": "panel: the committed full ensemble (members/weights) reused "
    "verbatim by the catalog run — never re-selected",
    "band": "catalog: ensemble member-envelope (per-day min/max of the "
    "committed members) — NOT a calibrated interval; no conformal band exists "
    "on the full track",
    "stability": "panel: population std of the per-origin official WRMSSE "
    "across the 2 selection origins (thin screen — see the report's protocol "
    "limit note)",
}


def _load_committed(reports_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics_path = reports_dir / "metrics.json"
    meta_path = reports_dir / "evaluation_metadata.json"
    if not metrics_path.exists() or not meta_path.exists():
        raise FileNotFoundError(
            f"missing {metrics_path} or {meta_path} — run `evaluate-m5-full` first"
        )
    metrics = json.loads(metrics_path.read_text())
    meta = json.loads(meta_path.read_text())
    if metrics.get("protocol") != PROTOCOL:
        raise ValueError(
            f"committed metrics protocol {metrics.get('protocol')!r} != {PROTOCOL!r} "
            "— the payload must be built from the m5_full_v1 artifacts"
        )
    return metrics, meta


def _load_catalog(reports_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read the wave-32 catalog parquet + meta; drift-guard both against the
    committed metrics block (same run) and against internal tampering."""
    path = reports_dir / CATALOG_FORECASTS_NAME
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path} — run `evaluate-m5-full --catalog-dump {path}` first "
            "(the payload copies the catalog curves from the catalog run)"
        )
    frame = pq.read_table(path).to_pandas()
    expected = {"unique_id", "ds", "actual", *CANDIDATES, "band_lo", "band_hi"}
    missing = expected - set(frame.columns)
    if missing:
        raise ValueError(f"catalog {path} is missing columns {sorted(missing)}")
    meta = json.loads((reports_dir / CATALOG_META_NAME).read_text())
    if meta.get("protocol") != PROTOCOL:
        raise ValueError(f"catalog meta protocol drifted: {meta.get('protocol')!r}")
    return frame, meta


def _catalog_guards(
    frame: pd.DataFrame,
    cat_meta: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    """(1) the catalog's ensemble must BE the committed ensemble; (2) the
    persisted blend column must recompute from the persisted member columns."""
    committed = metrics["ensemble"]
    if list(cat_meta["ensemble"]["members"]) != list(committed["members"]) or [
        float(w) for w in cat_meta["ensemble"]["weights"]
    ] != [float(w) for w in committed["weights"]]:
        raise ValueError(
            "catalog ensemble != committed metrics ensemble — the catalog "
            "parquet and metrics.json come from different runs; re-run the "
            "catalog dump against the committed metrics"
        )
    members = [str(m) for m in committed["members"]]
    weights = [float(w) for w in committed["weights"]]
    blend = np.zeros(len(frame))
    for w, m in zip(weights, members, strict=True):
        blend += w * frame[m].to_numpy(dtype=float)
    drift = float(np.max(np.abs(blend - frame["convex_ensemble"].to_numpy(dtype=float))))
    if drift > DRIFT_TOL:
        raise ValueError(
            f"catalog blend guard failed: ensemble column deviates from the "
            f"committed blend by {drift} > {DRIFT_TOL} — tampered or corrupted"
        )
    logger.info("catalog guards OK: committed ensemble + blend identity pinned at %g", DRIFT_TOL)


def _r4(values: np.ndarray | list[float]) -> list[float]:
    """Round to 4 decimals (JSON size) — deterministic."""
    return [round(float(v), 4) for v in values]


def _per_series_grids(frame: pd.DataFrame, catalog_ids: list[str]) -> dict[str, np.ndarray]:
    """(n_catalog, H) grids per value column, in catalog order."""
    out = {}
    for col in ("actual", *CANDIDATES, "band_lo", "band_hi"):
        grid = frame.pivot(index="unique_id", columns="ds", values=col).reindex(catalog_ids)
        if grid.shape != (len(catalog_ids), HORIZON) or grid.isna().any().any():
            raise ValueError(f"catalog column {col} is not a full grid")
        out[col] = grid.to_numpy(dtype=float)
    return out


def _win_rate_vs_naive(
    grids: dict[str, np.ndarray], class_of: dict[str, str]
) -> dict[str, dict[str, float | None]]:
    """Per-series wins vs the seasonal-naive floor over the catalog (CATALOG
    scope — a subset statistic): a series is a win when the candidate's total
    absolute error over the scored window is below the naive's."""
    actual = grids["actual"]
    naive_err = np.abs(grids["seasonal_naive"] - actual).sum(axis=1)
    dense_mask = np.array([class_of[sid] in ("smooth", "erratic") for sid in class_of])
    # class_of iterates in catalog order (built that way below)
    out: dict[str, dict[str, float | None]] = {}
    for cand in CANDIDATES:
        err = np.abs(grids[cand] - actual).sum(axis=1)
        wins = err < naive_err

        def _rate(wins_arr: np.ndarray, mask: np.ndarray) -> float | None:
            n = int(mask.sum())
            return float(wins_arr[mask].mean()) if n else None

        out[cand] = {
            "pooled": _rate(wins, np.ones(len(wins), dtype=bool)),
            "dense": _rate(wins, dense_mask),
            "intermittent": _rate(wins, ~dense_mask),
        }
    return out


def build_demo_payload_full(
    raw_dir: Path,
    reports_dir: Path,
) -> dict[str, Any]:
    """Assemble the forecast-workbench payload from the committed full-panel
    artifacts + the wave-32 catalog."""
    reports_dir = Path(reports_dir)
    metrics, eval_meta = _load_committed(reports_dir)
    frame, cat_meta = _load_catalog(reports_dir)
    _catalog_guards(frame, cat_meta, metrics)

    catalog_ids = list(dict.fromkeys(frame["unique_id"].tolist()))
    descriptors = {d["unique_id"]: d for d in cat_meta["series"]}
    if set(descriptors) != set(catalog_ids):
        raise ValueError("catalog meta series set does not match the parquet")
    class_of = {sid: descriptors[sid]["class"] for sid in catalog_ids}
    stores = {sid: descriptors[sid]["store"] for sid in catalog_ids}

    grids = _per_series_grids(frame, catalog_ids)
    test_block = metrics["test"]

    # ---- groups blocks (panel-based ones copied; catalog ones computed) ----
    test_pooled = {
        cand: {
            "wape": test_block[cand]["bottom_wape"],
            "wrmsse": test_block[cand]["official_wrmsse"],
            "bias": test_block[cand]["bias"],
            "zero_day_accuracy": test_block[cand]["zero_day_accuracy"],
            "zero_day_accuracy_intermittent": test_block[cand]["zero_day_accuracy_intermittent"],
        }
        for cand in CANDIDATES
    }
    win_rate = _win_rate_vs_naive(grids, class_of)
    actual = grids["actual"]
    by_class: dict[str, dict[str, dict[str, float]]] = {}
    for cand in CANDIDATES:
        per_cls: dict[str, dict[str, float]] = {}
        for cls in ("dense", "intermittent"):
            mask = np.array([class_of[sid] in ("smooth", "erratic") for sid in catalog_ids])
            mask = mask if cls == "dense" else ~mask
            per_cls[cls] = (
                {"wape": wape(actual[mask], grids[cand][mask])} if int(mask.sum()) else {}
            )
        by_class[cand] = per_cls

    scores = {c: test_block[c]["official_wrmsse"] for c in CANDIDATES}
    champion = min(scores, key=lambda c: scores[c])
    naive_wr = scores["seasonal_naive"]
    ens_wr = scores["convex_ensemble"]
    headline = {
        "metric": "official_wrmsse",
        "champion": champion,
        "champion_wrmsse": scores[champion],
        "wrmsse_champion": {"candidate": champion, "wrmsse": scores[champion]},
        "absolute_ensemble_wrmsse": ens_wr,
        "convex_ensemble_vs_naive": {
            "wrmsse": {
                "diff": ens_wr - naive_wr,
                "rel": (ens_wr - naive_wr) / naive_wr if naive_wr > 0 else float("nan"),
                "ci95": None,
                "spans_zero": None,
                "note": "no paired bootstrap on the full track — point estimate only",
            }
        },
    }
    band_width = (grids["band_hi"] - grids["band_lo"]).mean(axis=0)
    band_cover = ((actual >= grids["band_lo"]) & (actual <= grids["band_hi"])).mean(axis=0)
    band = {
        "method": cat_meta["band"],
        "level": None,
        "per_horizon_width": _r4(band_width),
        "per_horizon_coverage": _r4(band_cover),
        "candidates": {"convex_ensemble": {"mean_width": float(band_width.mean())}},
    }
    groups: dict[str, Any] = {
        "headline": headline,
        "test_pooled": test_pooled,
        "test_by_class": by_class,
        "win_rate_vs_naive": win_rate,
        "stability": {cand: metrics["selection"][cand]["stability"] for cand in CANDIDATES},
        "classes": {
            "counts": metrics["classes"]["counts"],
            "thresholds": metrics["classes"]["thresholds"],
        },
        "ensemble": metrics["ensemble"],
        "band": band,
        "_scope": SCOPE,
    }

    # ---- catalog windows: history tails live from the pinned panel ----
    from demand_forecasting.m5_full import load_m5_full

    y_all, _x_all, _s_all = load_m5_full(Path(raw_dir))
    odate = pd.Timestamp(cat_meta["origin"])
    hist_start = odate - pd.to_timedelta(HISTORY_DAYS - 1, unit="D")
    tail = y_all[(y_all["ds"] >= hist_start) & (y_all["ds"] <= odate)]
    history_grid = tail.pivot(index="unique_id", columns="ds", values="y").reindex(catalog_ids)
    if history_grid.shape != (len(catalog_ids), HISTORY_DAYS) or history_grid.isna().any().any():
        raise ValueError(f"history tail before {odate.date()} is not a full grid")
    history = history_grid.to_numpy(dtype=float)
    days = pd.date_range(odate + pd.to_timedelta(1, unit="D"), periods=HORIZON, freq="D")
    block_days = np.sort(frame["ds"].unique())
    if len(block_days) != HORIZON:
        raise ValueError("catalog parquet does not hold exactly one horizon")
    forecast_dates = [str(d.date()) for d in days]

    curve_names = list(CANDIDATES)
    windows: dict[str, Any] = {}
    for i, sid in enumerate(catalog_ids):
        row = frame[frame["unique_id"] == sid].sort_values("ds")
        if len(row) != HORIZON:
            raise ValueError(f"catalog has {len(row)} rows for {sid}")
        curves = {c: grids[c][i] for c in curve_names}
        windows[sid] = {
            "history": _r4(history[i]),
            "actual": _r4(grids["actual"][i]),
            "curves": {c: _r4(v) for c, v in curves.items()},
            "band": {
                "lo": _r4(grids["band_lo"][i]),
                "hi": _r4(grids["band_hi"][i]),
            },
            "wape": {c: round(wape(grids["actual"][i], curves[c]), 4) for c in curve_names},
        }
    catalog = [
        {
            "series_id": sid,
            "store": stores[sid],
            "class": ("dense" if class_of[sid] in ("smooth", "erratic") else "intermittent"),
            "adi": descriptors[sid]["adi"],
            "cv2": descriptors[sid]["cv2"],
            "units_last_28d": descriptors[sid]["units_last_28d"],
            "half": descriptors[sid]["half"],
            "windows": windows[sid],
        }
        for sid in catalog_ids
    ]

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "demo": DEMO_ID,
        "project": "02-demand-forecasting",
        "protocol": PROTOCOL,
        "groups": groups,
        "catalog_rule": cat_meta["catalog_rule"],
        "curve_provenance": (
            "every shipped curve is copied from reports_m5_full/"
            "catalog_forecasts.parquet (the wave-32 catalog run: every candidate "
            "fit at the test origin, the ensemble blended with the COMMITTED "
            "weights — never re-selected; band = ensemble member envelope, not a "
            "calibrated interval); the 56-day history tails are sliced live "
            "from the checksum-pinned raw panel"
        ),
        "history_days": HISTORY_DAYS,
        "origins": [
            {
                "origin": cat_meta["origin"],
                "history_start": str(hist_start.date()),
                "forecast_dates": forecast_dates,
            }
        ],
        "catalog": catalog,
        "evaluation_metadata": {
            "protocol": eval_meta["protocol"],
            "dataset": eval_meta["dataset"],
            "split": eval_meta["split"],
            "seeds": eval_meta["seeds"],
            "determinism": eval_meta["determinism"],
        },
    }
    return payload


def write_demo_payload_full(raw_dir: Path, reports_dir: Path) -> Path:
    """Build the payload and persist it to ``reports_m5_full/demo_payload.json``."""
    reports_dir = Path(reports_dir)
    payload = build_demo_payload_full(raw_dir, reports_dir)
    out = reports_dir / DEMO_PAYLOAD_NAME
    out.write_text(json.dumps(payload, indent=2) + "\n")
    size_kb = out.stat().st_size / 1024
    logger.info(
        "m5 full demo payload: %d catalog series -> %s (%.0f KB)",
        len(payload["catalog"]),
        out,
        size_kb,
    )
    if size_kb > 1024:
        raise ValueError(f"demo payload exceeds the 1 MB cap: {size_kb:.0f} KB")
    return out
