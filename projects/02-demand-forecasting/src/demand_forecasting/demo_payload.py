"""Demo payload schema v3 for the demand forecast workbench (showcase demo).

Builds ``reports/demo_payload.json`` — a compact, fully precomputed catalog for
the DIRECT MULTI-HORIZON track (protocol ``direct_multihorizon_v1``, the
primary multi-step headline committed in ``reports_uci/metrics.json`` under
``_multistep``). Schema v2 carried the retained frozen NOWCAST single-origin
curves; v3 replaces the catalog with the multi-step experiment:

- ~100 series from the UCI Online Retail II panel (ALL 15 erratic series are
  represented — the boosted per-horizon HGB only serves those — plus 85 lumpy
  series picked with country diversity), each carrying its ADI/CV² class and
  the committed per-series routing decision (``model_used``);
- per series, the 3 most recent of the 4 scored test origins (the forecast
  window starts the day AFTER the origin — no embargo gap): the as-of-origin
  history (ends the day BEFORE the origin), the 14 contiguous days of
  actuals, and per-model DIRECT curves on the committed h-lattice
  h = 1..14 (the full window — one real direct-h model per day, no display
  interpolation) — ``zero`` (the naive baseline), ``routed`` (the series'
  committed routing method; for erratic series this IS the boosted direct
  HGB), ``floor`` (seasonal-naive, for the decision layer) and, for erratic
  series only, ``champion_hgb`` — with a per-series ``model_used`` field so
  the payload is honest about which model produced each curve;
- bands where the committed protocol emits them: learner rows (erratic) get
  the per-h split-conformal p10/p90 (zero-clipped, sorted, from the
  committed conformal widths); sparse rows (lumpy) honestly carry P(any
  sale) + a small quantile ladder of the training history instead of a
  collapsing band;
- a demand-shock what-if, precomputed OFFLINE and exact: each curve is
  re-scored under {0.5, 1.5, 2.0}x demand in the last 7 days before the
  origin — the statistical methods re-fit on the shocked window, the boosted
  models re-predict through their fitted per-horizon trees on the shocked
  lag trio (units(origin), units(origin-7), units(origin-14) — the only
  demand features the direct models read, by construction). A static payload
  cannot re-run trees client-side, so the shock grid is baked in;
- experiment-wide blocks straight from the committed JSONs: ``class_scoreboard``
  (per ADI/CV² class: n series, the per-series beats-floor count/share
  recomputed from the re-run cells, committed pooled MAE model-vs-floor at
  h=7/h=14 with the paired-bootstrap CIs, the routing effect, and — revision
  3.1 — the wave-20 peak-capable candidates' committed rows per horizon),
  ``horizon_growth`` (pooled MAE and MASE vs the true horizon h), ``bands``
  (per-h coverage/width/verdict + pinball), ``decision`` (the committed
  order-up-to simulation plus the τ→quantile mapping), and ``peak_capture``
  (peak-day MAE + peak timing recall per class with paired-bootstrap CIs);
- revision 3.1 (additive over v3, wave 20): per-series ``models`` entries for
  the peak-capable candidates (``hurdle_hgb`` / ``hgb_tweedie``) on the series
  the committed router selected them for — the candidate curve IS the routed
  curve, surfaced under its own name for the workbench's model chips;
- revision 3.2 (additive over 3.1, full lattice): the committed direct
  h-lattice is h = 1..14, so every per-model curve is a contiguous 14-day
  series (one real direct-h point per window day — no interpolated display
  points anywhere), learner p10/p90 bands and sparse P(sale)+ladder bands cover
  the whole window, and ``horizon_growth`` spans h = 1..14;
- revision 3.3 (additive over 3.2, wave 21): per-series ``models`` alias
  entries cover every ML candidate the committed router may now pick (the
  LightGBM family and the peak-weighted hurdle join the wave-20 pair), and the
  experiment-wide ``win_rates`` block (per-class per-series beats-floor win
  rates with cluster-bootstrap CIs) is carried straight from the committed
  ``_multistep`` block — nothing v3.2 carries moves.
- ``evaluation_metadata`` embeds the committed protocol-v2 block (20 weekly
  rolling origins, select-16/score-4, per-h direct models, the
  leakage-by-construction feature semantics) and ``dataset_metadata`` the
  committed dataset card (cleaning rules, the intermittency class counts).

Drift guards (as v2): the re-run multi-step scoring must reproduce the
committed pooled MAE per candidate over the scored test cells, the committed
conformal widths, the committed class assignments, and the committed origin
plan — any mismatch raises instead of shipping.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from joblib import Parallel, delayed, parallel_config
from portfolio_core.logging import get_logger

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.intermittent import (
    ADI_THRESHOLD,
    CV2_THRESHOLD,
    SPARSE_CLASSES,
    STATISTICAL_METHODS,
    classify_panel,
)
from demand_forecasting.multihorizon import (
    COMPARISON_CANDIDATES,
    LADDER_LEVELS,
    ML_SPARSE,
    OriginScore,
    _calendar_features,
    _policy_residuals,
    _score_origin,
    _test_cells,
    apply_hurdle_correction,
    choose_peak_weight,
    ensemble_weights,
    multistep_origin_indices,
    panel_matrix,
    panel_price_matrix,
    split_origins,
)
from demand_forecasting.probabilistic import TARGET_COVERAGE as _TARGET_COVERAGE

logger = get_logger(__name__)

DEMO_PAYLOAD_NAME = "demo_payload.json"
PAYLOAD_SCHEMA_VERSION = 3
# Additive revisions on top of schema v3:
#   3.1 (wave 20): per-series candidate curves for the peak-capable ML methods
#       the router selected, `peak_capture` per class, and
#       `class_scoreboard[cls].candidates` — nothing v3 carries moves.
#   3.2 (full lattice): the direct h-lattice is now h = 1..14 — every model
#       curve is a contiguous 14-day series (one real direct-h point per
#       window day, no interpolated display points), bands/pinball/widths
#       exist at every h, and `horizon_growth` spans 1..14.
PAYLOAD_REVISION = "3.3"
CATALOG_N = 100
ORIGIN_HISTORY_DAYS = 60
HORIZON_DAYS = 14
SEASON = 7
SIZE_CAP_BYTES = 3 * 1024 * 1024
# Demand-shock what-if stops (1.0x is the committed base curve itself).
SHOCK_FACTORS = (0.5, 1.5, 2.0)
# Service-level grid for the decision layer's τ→quantile mapping.
TAU_GRID = tuple(round(0.50 + 0.01 * k, 2) for k in range(50))
# Class quotas: every erratic series is represented (the boosted HGB only
# serves those — the routing story dies without them); lumpy fills the rest.

NAIVE_MODEL = "zero"
FLOOR_MODEL = "seasonal_naive"
CHAMPION_HGB = "direct_hgb"


def _check_close(name: str, actual: float, committed: float, tol: float = 1e-6) -> None:
    """Guard against drift between the committed metrics JSONs and the frame."""
    if not np.isclose(actual, committed, rtol=tol, atol=tol):
        raise ValueError(f"{name}: recomputed {actual} != committed {committed}")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — run the evaluate stage first")
    data: dict[str, Any] = json.loads(path.read_text())
    return data


# ---------------------------------------------------------------------------
# Catalog selection
# ---------------------------------------------------------------------------


def _select_catalog(
    series_ids: list[str], classes: dict[str, dict[str, Any]], catalog_n: int = CATALOG_N
) -> list[str]:
    """Coverage-first catalog: ALL erratic series, then lumpy with country
    diversity (round-robin across countries by total volume, highest-volume
    series first within each country) — the v2 audit found 64/100 UK series."""
    erratic = [s for s in series_ids if classes[s]["class"] == "erratic"]
    lumpy = [s for s in series_ids if classes[s]["class"] == "lumpy"]
    quota = catalog_n - len(erratic)
    if quota < 0:  # pragma: no cover - UCI has 15 erratic series
        erratic = erratic[:catalog_n]
        quota = 0
    by_country: dict[str, list[str]] = {}
    for sid in lumpy:
        by_country.setdefault(sid.split("|")[0], []).append(sid)
    countries = sorted(by_country, key=lambda c: (-len(by_country[c]), c))
    picked: list[str] = []
    while len(picked) < min(quota, len(lumpy)):
        for c in countries:
            pool = by_country[c]
            if pool and len(picked) < min(quota, len(lumpy)):
                picked.append(pool.pop(0))
    return erratic + picked


# ---------------------------------------------------------------------------
# Origin entries
# ---------------------------------------------------------------------------


def _seasonal_scale(hist_y: np.ndarray) -> float:
    """In-sample seasonal-naive scale: mean |lag-season diff| over the history."""
    if hist_y.size <= SEASON:
        return 0.0
    return float(np.mean(np.abs(hist_y[SEASON:] - hist_y[:-SEASON])))


def _round_curve(v: np.ndarray) -> list[float]:
    """Display-sanitized curve: demand cannot be negative, so clip at zero
    (headline metrics in the committed JSONs remain the raw backtest)."""
    return [round(float(x), 4) for x in np.clip(v, 0.0, None)]


def _sparse_band(hist: np.ndarray) -> dict[str, Any]:
    """The honest sparse band: P(any sale) + a quantile ladder of the
    training history up to the origin — it cannot collapse to zero width."""
    return {
        "p_sale": round(float(np.mean(hist > 0)), 4),
        "ladder": {f"{lvl:.2f}": round(float(np.quantile(hist, lvl)), 4) for lvl in LADDER_LEVELS},
    }


def _origin_entry(
    i: int,
    units: np.ndarray,
    dates: np.ndarray,
    origin: int,
    sc: OriginScore,
    method_of: str,
    sparse_i: bool,
    horizons: list[int],
    widths: dict[int, float],
    origin_history_days: int,
) -> dict[str, Any]:
    """One catalog series at one scored origin: as-of-origin history (ends the
    day BEFORE the origin), 14 contiguous days of actuals (start the day
    AFTER — no gap), and the per-model direct curves at the h-lattice. All
    ``sc`` matrices are already at the h-lattice (one column per horizon), so
    a series' curve is simply its row.
    """
    hist_sl = slice(origin - origin_history_days, origin)  # ends origin-1
    hist_y = units[hist_sl, i]
    train_hist = units[: origin + 1, i]  # the window the methods actually fit on
    hist_dates = [str(d)[:10] for d in dates[hist_sl]]
    actual_sl = slice(origin + 1, origin + 1 + HORIZON_DAYS)
    actual_dates = [str(d)[:10] for d in dates[actual_sl]]
    actual = units[actual_sl, i]
    scale = _seasonal_scale(hist_y)

    def curve_of(method: str) -> np.ndarray:
        """The routed pipeline's point curve for this series."""
        if method == CHAMPION_HGB:
            return sc.preds["direct_hgb"][i, :]
        return sc.preds[method][i, :]

    routed = curve_of(method_of)
    hgb = sc.preds["direct_hgb"][i, :]
    floor = sc.preds[FLOOR_MODEL][i, :]

    models: dict[str, Any] = {
        NAIVE_MODEL: {"y_pred": _round_curve(np.zeros(len(horizons)))},
        "routed": {"y_pred": _round_curve(routed)},
        "floor": {"y_pred": _round_curve(floor)},
    }
    if sparse_i:
        # sparse rows: P(sale) + quantile ladder instead of a collapsing band
        models["routed"]["band"] = _sparse_band(train_hist)
    else:
        # learner rows: the committed per-h split-conformal band (p50 ± width,
        # zero-clipped, sorted, clamped around the displayed point curve)
        p50 = sc.quantiles[0.5][i, :]
        lo = np.clip(np.minimum(p50 - np.array([widths[h] for h in horizons]), routed), 0.0, None)
        hi = np.clip(np.maximum(p50 + np.array([widths[h] for h in horizons]), routed), 0.0, None)
        p10 = [round(float(v), 4) for v in lo]
        p90 = [round(float(v), 4) for v in hi]
        models["routed"]["p10"] = p10
        models["routed"]["p90"] = p90
        models["champion_hgb"] = {
            "y_pred": _round_curve(hgb),
            # the routed curve IS the boosted HGB only when the router kept the
            # series on direct_hgb (wave 20: erratic series may route to the
            # peak-capable ML candidates instead)
            "p10": list(p10),
            "p90": list(p90),
        }
    # what-if shocks (offline, exact): statistical methods re-fit on the
    # shocked window, the boosted models re-predict on the shocked lag trio
    for name, method in (
        (NAIVE_MODEL, "zero"),
        ("routed", method_of),
        ("floor", FLOOR_MODEL),
        *([("champion_hgb", "direct_hgb")] if not sparse_i else []),
    ):
        block: dict[str, list[float]] = {}
        for s, entry in sc.shocked.items():
            block[f"{s:g}"] = _round_curve(entry[method][i, :])
        models[name]["shock"] = block
    if method_of in ML_SPARSE:
        # the router selected a peak-capable ML candidate for this series: the
        # candidate curve IS the routed curve — surface an alias entry under
        # the candidate's name so the workbench can offer it as a model chip
        # without duplicating the curve bytes
        models[method_of] = {"alias": "routed"}

    return {
        "origin_date": str(dates[origin])[:10],
        "history": {"dates": hist_dates, "y": [int(v) for v in hist_y]},
        "actuals": {"dates": actual_dates, "y": [int(v) for v in actual]},
        "horizons": list(horizons),
        "scale": round(scale, 4),
        "models": models,
    }


# ---------------------------------------------------------------------------
# Experiment-wide blocks (from the committed metrics)
# ---------------------------------------------------------------------------


def _class_scoreboard(
    ms: dict[str, Any], cells: dict[str, Any], classes_of: np.ndarray
) -> dict[str, Any]:
    """Per-class scoreboard: committed pooled numbers + per-series
    beats-floor counts recomputed from the (drift-guarded) cells."""
    board: dict[str, Any] = {}
    for cls, entry in ms["headline_per_class"].items():
        cls_mask = classes_of[cells["series"]] == cls
        n = int(entry["n_series"])
        beats: dict[str, Any] = {}
        for h in (7, 14):
            key = f"h{h}"
            if key not in entry:
                continue
            mask = cls_mask & (cells["h"] == h)
            per_series: dict[int, tuple[float, float]] = {}
            for idx in np.flatnonzero(mask):
                i = int(cells["series"][idx])
                a, b = per_series.get(i, (0.0, 0.0))
                per_series[i] = (
                    a + abs(float(cells["pred"]["routed"][idx] - cells["y"][idx])),
                    b + abs(float(cells["pred"]["seasonal_naive"][idx] - cells["y"][idx])),
                )
            count = sum(1 for a, b in per_series.values() if a < b)
            beats[key] = {
                "count": count,
                "n": n,
                "share": round(count / n, 4) if n else None,
            }
        board[cls] = {
            "n_series": n,
            "beats_floor": beats,
            "mae": {
                key: {"model": entry[key]["champion_mae"], "floor": entry[key]["floor_mae"]}
                for key in ("h7", "h14")
                if key in entry
            },
            "gap_bootstrap": {
                key: entry[key]["champion_vs_floor"] for key in ("h7", "h14") if key in entry
            },
            "vs_zero_bootstrap": {
                key: entry[key]["champion_vs_naive_zero"] for key in ("h7", "h14") if key in entry
            },
            "candidates": _candidate_board(entry),
            "routing_effect": ms["routing"]["per_class"].get(cls),
        }
    return board


def _candidate_board(entry: dict[str, Any]) -> dict[str, Any]:
    """The peak-capable ML + ensemble candidates per class, from the committed
    headline rows: pooled MAE + the paired-bootstrap gaps vs routed and vs
    zero at each committed horizon."""
    board: dict[str, Any] = {}
    for cand in COMPARISON_CANDIDATES:
        rows: dict[str, Any] = {}
        for key in ("h7", "h14"):
            row = entry.get(key)
            if not row or row.get(f"{cand}_mae") is None:
                continue
            rows[key] = {
                "mae": row[f"{cand}_mae"],
                "vs_routed": row.get(f"{cand}_vs_routed"),
                "vs_zero": row.get(f"{cand}_vs_zero"),
            }
        board[cand] = rows
    return board


def _horizon_growth(ms: dict[str, Any]) -> dict[str, Any]:
    """Committed error-vs-horizon curves: pooled MAE per true horizon for the
    routed pipeline / the floor / zero, the pooled MASE curves, per-class."""
    per_horizon = ms["per_horizon"]

    def _mase(policy: str, h: int) -> float | None:
        v = float(per_horizon[str(h)][policy]["mase"])
        return v if np.isfinite(v) else None

    return {
        "horizons": ms["horizons"],
        "pooled": ms["horizon_growth"]["pooled"],
        "mase": {
            "champion": {str(h): _mase("champion", h) for h in ms["horizons"]},
            "floor": {str(h): _mase("floor", h) for h in ms["horizons"]},
        },
        "per_class": ms["horizon_growth"]["per_class"],
        "note": (
            "pooled over series x scored test origins per TRUE horizon h (direct per-h "
            "models) — the error-growth curve the horizon slider demonstrates"
        ),
    }


def _decision_block(
    ms: dict[str, Any],
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
    method_of: np.ndarray,
    classes_of: np.ndarray,
) -> dict[str, Any]:
    """The committed order-up-to simulation PLUS the τ→quantile mapping the
    decision layer needs: per (class, policy, h), the τ-quantile of the
    policy's selection-origin residuals (the committed simulation's own
    derivation: order = point forecast + q_τ(residuals), clipped at zero)."""
    committed = ms["decision_metric"]
    quantile_map: dict[str, Any] = {}
    for cls in sorted(set(classes_of.tolist())):
        class_mask = classes_of == cls
        per_policy: dict[str, Any] = {}
        for policy in ("champion", "floor"):
            per_h: dict[str, Any] = {}
            for h in horizons:
                res = _policy_residuals(
                    by_origin, selection, horizons, h, class_mask, units, sparse, method_of, policy
                )
                per_h[str(h)] = {
                    f"{tau:.2f}": round(float(np.quantile(res, tau)), 4) for tau in TAU_GRID
                }
            per_policy[policy] = per_h
        quantile_map[cls] = per_policy
    return {
        **committed,
        "tau_grid": [f"{tau:.2f}" for tau in TAU_GRID],
        "quantile_map": quantile_map,
        "mapping_note": (
            "order(origin, h, τ) = max(point forecast + offset, 0) with offset = "
            "quantile_map[class][policy][h][τ]; offsets are τ-quantiles of the policy's "
            "selection-origin residuals per (class, h) — the committed simulation's own "
            "τ→quantile mapping, recomputed on the re-run scores"
        ),
    }


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Drift guards
# ---------------------------------------------------------------------------


def _drift_guard(
    ms: dict[str, Any],
    prob_ms: dict[str, Any],
    cells: dict[str, Any],
    by_origin: dict[int, OriginScore],
    selection: list[int],
    horizons: list[int],
    units: np.ndarray,
    sparse: np.ndarray,
) -> dict[int, float]:
    """Assert the re-run reproduces every committed scalar the payload carries
    (pooled MAE per candidate over the scored cells, the routed per-h MAE,
    and the conformal widths); return the recomputed widths for band emission."""
    for name, committed in ms["overall_mae_test"].items():
        mae = float(np.abs(cells["pred"][name] - cells["y"]).mean())
        _check_close(f"_multistep.overall_mae_test.{name}", mae, float(committed))
    for h in horizons:
        mask = cells["h"] == h
        mae = float(np.abs(cells["pred"]["routed"][mask] - cells["y"][mask]).mean())
        _check_close(
            f"_multistep.per_horizon.{h}.champion.mae",
            mae,
            ms["per_horizon"][str(h)]["champion"]["mae"],
        )
    # conformal widths, recomputed from the selection origins' p50 residuals
    widths: dict[int, float] = {}
    for h in horizons:
        j = horizons.index(h)
        res = np.concatenate(
            [units[o + h][~sparse] - by_origin[o].quantiles[0.5][~sparse, j] for o in selection]
        )
        widths[h] = float(np.quantile(np.abs(res), _TARGET_COVERAGE))
        _check_close(
            f"probabilistic.multistep.conformal_widths_by_h.{h}",
            widths[h],
            float(prob_ms["conformal_widths_by_h"][str(h)]),
        )
    return widths


def build_demo_payload(
    settings: DemandSettings,
    config: ForecastConfig,
    *,
    metrics_dir: Path | None = None,
    catalog_n: int = CATALOG_N,
    origin_history_days: int = ORIGIN_HISTORY_DAYS,
) -> dict[str, Any]:
    """Assemble the v3 workbench payload from the committed multi-step track.

    Re-runs the direct multi-horizon scoring (same deterministic code path
    that wrote the committed metrics) to recover the per-origin per-series
    curves the metrics JSONs do not persist, then drift-guards the re-run
    against every committed scalar the payload carries.
    """
    metrics_dir = Path(metrics_dir) if metrics_dir else Path(settings.reports_dir)
    metrics = _load_json(metrics_dir / "metrics.json")
    probabilistic = _load_json(metrics_dir / "probabilistic.json")
    eval_meta = _load_json(metrics_dir / "evaluation_metadata.json")
    dataset_meta = _load_json(metrics_dir / "dataset_metadata.json")

    ms = metrics.get("_multistep")
    if not isinstance(ms, dict):
        raise ValueError("metrics.json has no _multistep block — run the multi-step track first")
    if ms["protocol"] != "direct_multihorizon_v1":
        raise ValueError(f"committed protocol {ms['protocol']!r} != direct_multihorizon_v1")
    prob_ms = probabilistic.get("multistep")
    if not isinstance(prob_ms, dict):
        raise ValueError("probabilistic.json has no multistep block")
    mh_meta = eval_meta.get("multi_horizon")
    if not isinstance(mh_meta, dict):
        raise ValueError("evaluation_metadata.json has no multi_horizon block")

    panel = pl.read_parquet(settings.data_dir / "panel.parquet")
    dates, series_ids, units = panel_matrix(panel)
    price = panel_price_matrix(panel, dates, series_ids)
    cal = _calendar_features(dates)
    horizons = list(config.multistep_horizons)
    classes = classify_panel(units, series_ids)
    classes_of = np.array([classes[s]["class"] for s in series_ids])
    sparse = np.array([classes[s]["class"] in SPARSE_CLASSES for s in series_ids])

    origins = multistep_origin_indices(len(dates), config)
    selection, test = split_origins(origins, config)
    # the origin plan must match the committed block exactly
    if [str(dates[o])[:10] for o in origins] != ms["origins"]["dates"]:
        raise ValueError("recomputed origin plan disagrees with committed _multistep.origins")
    # the class assignments must match the committed table exactly
    committed_classes = ms["demand_classes"]["series"]
    if {s: classes[s]["class"] for s in series_ids} != {
        s: str(c) for s, c in committed_classes.items()
    }:
        raise ValueError("recomputed ADI/CV² classes disagree with committed demand_classes")

    # routing per series, from the COMMITTED routing table (chosen on the
    # selection origins only — property-tested upstream); the wave-20 table
    # covers every series (sparse: statistical + ML candidates; dense:
    # direct_hgb + ML candidates)
    choices = ms["routing"]["method_choices"]
    method_of = np.empty(len(series_ids), dtype=object)
    for i, sid in enumerate(series_ids):
        m = choices.get(sid)
        if sparse[i]:
            if m not in (*STATISTICAL_METHODS, *ML_SPARSE):
                raise ValueError(f"committed routing table missing method for sparse series {sid}")
        elif m not in ("direct_hgb", *ML_SPARSE):
            raise ValueError(f"committed routing table missing method for dense series {sid}")
        method_of[i] = m

    # re-run every origin (scored origins also get the shock grid);
    # inner_max_num_threads=1 — workers are full-core already (see multihorizon)
    with parallel_config("loky", inner_max_num_threads=1):
        scores = Parallel(n_jobs=-2)(
            delayed(_score_origin)(
                units, cal, o, horizons, config, SHOCK_FACTORS if o in test else (), price
            )
            for o in origins
        )
    by_origin = {s.origin: s for s in scores}

    # the peak-weight choice and the hurdle zero-correction are part of the
    # committed candidates: re-derive them on the selection origins
    # (deterministic) so the re-run cells match
    choose_peak_weight(by_origin, selection, horizons, units)
    apply_hurdle_correction(by_origin, selection, horizons, units)

    # ---- drift guards: the re-run must reproduce the committed scalars ----
    ens = ensemble_weights(
        by_origin, selection, horizons, units, sparse, method_of, len(series_ids)
    )
    ens_ml_idx = np.array([ML_SPARSE.index(str(m)) for m in ens["ml_choice"]])
    cells = _test_cells(
        by_origin, test, horizons, units, sparse, method_of, ens["weights"], ens_ml_idx
    )
    widths = _drift_guard(ms, prob_ms, cells, by_origin, selection, horizons, units, sparse)

    # ---- catalog ----
    scored = test[-3:]  # 3 of the last-4 scored origins (the most recent)
    selected = _select_catalog(series_ids, classes, catalog_n)
    sid_idx = {s: i for i, s in enumerate(series_ids)}
    catalog: list[dict[str, Any]] = []
    for sid in selected:
        i = sid_idx[sid]
        method = str(method_of[i])
        entry: dict[str, Any] = {
            "series_id": sid,
            "label": f"{sid.split('|')[0]} · {sid.split('|')[1]}",
            "country": sid.split("|")[0],
            "product": sid.split("|")[1],
            "demand_class": classes[sid]["class"],
            "adi": round(classes[sid]["adi"], 4),
            "cv2": round(classes[sid]["cv2"], 4) if np.isfinite(classes[sid]["cv2"]) else None,
            "model_used": method,
            "origins": [
                _origin_entry(
                    i,
                    units,
                    dates,
                    o,
                    by_origin[o],
                    method,
                    bool(sparse[i]),
                    horizons,
                    widths,
                    origin_history_days,
                )
                for o in scored
            ],
        }
        catalog.append(entry)

    # ---- experiment-wide blocks ----
    scoreboard = _class_scoreboard(ms, cells, classes_of)
    growth = _horizon_growth(ms)
    decision = _decision_block(
        ms, by_origin, selection, horizons, units, sparse, method_of, classes_of
    )
    routing_win = ms["routing"]["per_class"].get("lumpy", {})
    win_diff = routing_win.get("diff")
    win_ci = routing_win.get("ci95")
    claim = (
        "the routed pipeline leads the multi-step leaderboard; routing lumpy series away "
        "from the boosted model wins "
        f"+{win_diff:.1f} MAE [{win_ci[0]:.1f}, {win_ci[1]:.1f}] over all-HGB "
        "(95% paired bootstrap over series x scored origins)"
        if win_diff is not None and win_ci is not None
        else "the routed pipeline leads the multi-step leaderboard"
    )

    by_class = {
        cls: sum(1 for e in catalog if e["demand_class"] == cls) for cls in ("erratic", "lumpy")
    }
    countries: dict[str, int] = {}
    for e in catalog:
        countries[e["country"]] = countries.get(e["country"], 0) + 1
    model_used_counts: dict[str, int] = {}
    for e in catalog:
        model_used_counts[e["model_used"]] = model_used_counts.get(e["model_used"], 0) + 1

    target_definition = str(dataset_meta.get("target_definition", ""))
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "payload_revision": PAYLOAD_REVISION,
        "demo": "forecast-workbench",
        "project": "02-demand-forecasting",
        "track": config.data_source,
        "protocol": ms["protocol"],
        "catalog": catalog,
        "class_scoreboard": scoreboard,
        "horizon_growth": growth,
        "peak_capture": ms["peak_capture"],
        "win_rates": ms["win_rates"],
        "bands": {
            "target_coverage": prob_ms["target_coverage"],
            "band_types": prob_ms["band_types"],
            "conformal_widths_by_h": prob_ms["conformal_widths_by_h"],
            "per_horizon": prob_ms["per_horizon"],
            "pooled_coverage": prob_ms["pooled_coverage"],
            "pooled_verdict": prob_ms["pooled_verdict"],
            "sparse_ladder_levels": list(LADDER_LEVELS),
            "note": (
                "per-h coverage/width are the committed pooled values over the scored test "
                "origins; per-series panels show the conformal p10/p90 (learner rows) or the "
                "P(sale)+ladder (sparse rows) instead"
            ),
        },
        "decision": decision,
        "headline": {
            "claim": claim,
            "pooled_mae_by_model": ms["overall_mae_test"],
            "routing_win_lumpy": routing_win,
            "n_series_experiment": ms["demand_classes"]["n_series"],
            "class_counts": ms["demand_classes"]["counts"],
            "sparse_share": ms["demand_classes"]["sparse_share"],
        },
        "catalog_summary": {
            "n_series": len(catalog),
            "by_class": by_class,
            "countries": dict(sorted(countries.items(), key=lambda kv: (-kv[1], kv[0]))),
            "model_used_counts": dict(sorted(model_used_counts.items())),
            "origins": [
                {
                    "origin_date": str(dates[o])[:10],
                    "horizon_window": [str(dates[o + 1])[:10], str(dates[o + HORIZON_DAYS])[:10]],
                }
                for o in scored
            ],
            "history_days": origin_history_days,
            "horizon_days": HORIZON_DAYS,
            "horizons": horizons,
            "shock_factors": list(SHOCK_FACTORS),
            "shock_note": (
                "demand shock xs scales the last 7 days before the origin (the demand signal "
                "every candidate reads): statistical curves are re-fit on the shocked window, "
                "boosted curves re-predict through the fitted per-horizon trees on the shocked "
                "lag trio — precomputed offline, exact; bands stay on the unshocked base run"
            ),
            "routing_rule": ms["routing"]["rule"],
            "candidates": ms["candidates"],
            "peak_capable_candidates": ms["peak_capable_candidates"],
            "class_thresholds": {"adi": ADI_THRESHOLD, "cv2": CV2_THRESHOLD},
            "experiment_origins": ms["origins"],
        },
        "evaluation_metadata": {
            **mh_meta,
            "target_definition": target_definition,
            "nowcast_track_note": ms["track_note"],
        },
        "dataset_metadata": dataset_meta,
    }


def write_demo_payload(
    settings: DemandSettings,
    config: ForecastConfig,
    *,
    metrics_dir: Path | None = None,
    catalog_n: int = CATALOG_N,
    origin_history_days: int = ORIGIN_HISTORY_DAYS,
) -> Path:
    """Build the v3 payload and persist it to ``reports/demo_payload.json``."""
    payload = build_demo_payload(
        settings,
        config,
        metrics_dir=metrics_dir,
        catalog_n=catalog_n,
        origin_history_days=origin_history_days,
    )
    out = Path(settings.reports_dir) / DEMO_PAYLOAD_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    size = len(text.encode())
    if size > SIZE_CAP_BYTES:
        raise ValueError(f"demo payload is {size} bytes — over the {SIZE_CAP_BYTES}-byte cap")
    out.write_text(text + "\n")
    summary = payload["catalog_summary"]
    logger.info(
        "demo payload v3: %d series %s, origins %s -> %s (%d bytes)",
        summary["n_series"],
        summary["by_class"],
        [o["origin_date"] for o in summary["origins"]],
        out,
        size,
    )
    return out
