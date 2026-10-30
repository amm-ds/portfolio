"""Train-side selection of the alert-operating point (roadmap wave 15).

The wave-14 sweep fixed the threshold budget (2%) and the per-series cooldown
(24 h) a priori — a documented operating assumption, not an optimum. This
stage treats ``(threshold budget, cooldown)`` as a **per-detector-family
operating point** and selects it on train-side validation only, then scores
the test window exactly once per adopted point:

- **Selection surface (no test data).** Each series' train window is split
  80/20, mirroring the synthetic HPO convention: the detector fits on the
  first 80% of train and the last 20% of train becomes the validation slice.
  Candidate budgets flag that fraction of the *fit-slice* scores (threshold
  anchored on past data only, same headline rule); the budgeted alert stream
  (episode dedup + per-series cooldown) is scored with the headline
  event metrics on validation windows, aggregated as the mean over all 12
  series and both feature sets of the family (24 runs per grid point).
- **Conservative adoption.** The grid point maximizing validation range-F1 is
  adopted only when it beats the documented default (2%, 24 h) by
  ``MIN_GAIN``; ties break toward fewer pages, then the default, then the
  simpler point. Otherwise the default stands and the measured verdict is
  "no robust gain".
- **One test pass.** Each family is refit on the full train window and scored
  once on the test window at its adopted operating point through the unmodified
  sweep machinery (:func:`anomaly_detection.nab_sweep.evaluate_sweep_series`).
  No test-origin tuning: selection sees only rows and windows left of the
  70% train split.

Artifacts: ``reports/nab_tune.json`` (protocol, surfaces, selections, the
single test evaluation, and the budgeted-stream comparison against the
committed default-operating-point sweep) and the ``nab_tune_surface`` figure.
"""

import json
from datetime import datetime
from typing import Any

import numpy as np
import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_json

from anomaly_detection.config import AnomalyConfig
from anomaly_detection.model import anomaly_scores, make_model
from anomaly_detection.nab import (
    LEAD_STEPS,
    NAB_SERIES,
    build_series_features,
    fetch_labels,
    fetch_series,
    parse_series_csv,
    windows_to_mask,
)
from anomaly_detection.nab_sweep import (
    COOLDOWN_HOURS,
    DETECTORS,
    FEATURE_SETS,
    _aggregate_runs,
    _stream_metrics,
    cooldown_budget,
    episode_firing_times,
    evaluate_sweep_series,
)

logger = get_logger(__name__)

# Selection grid: threshold budgets are flagged fractions of the fit-slice
# scores; cooldowns are the per-series page cap in hours. Both grids contain
# the documented default so "keep the default" is always a grid point.
INNER_FIT_FRAC = 0.8  # of the train window: fit on 80%, validate on the last 20%
THRESHOLD_BUDGETS: tuple[float, ...] = (0.005, 0.01, 0.02, 0.04, 0.08)
COOLDOWN_HOURS_GRID: tuple[float, ...] = (6.0, 12.0, 24.0, 48.0, 72.0)
DEFAULT_BUDGET = 0.02
DEFAULT_COOLDOWN_HOURS = COOLDOWN_HOURS  # 24.0
# Minimum validation range-F1 gain over the default required to adopt a
# non-default point. The validation evidence is 5 windows across 5 series, so
# one series flipping its single window moves the 24-run mean by ~0.042; a
# 0.05 bar demands at least two series-worth of improvement before the
# operating point moves off the documented default.
MIN_GAIN = 0.05


def inner_train_val(n_train: int) -> tuple[int, int]:
    """Split the train window: fit rows, validation rows (mirrors the HPO slice)."""
    n_inner = int(n_train * INNER_FIT_FRAC)
    n_val = n_train - n_inner
    if n_inner <= 0 or n_val <= 0:
        raise ValueError(f"train window of {n_train} rows cannot be split 80/20")
    return n_inner, n_val


def build_validation_run(
    df: pl.DataFrame,
    windows: list[list[str]],
    config: AnomalyConfig,
    detector: str,
    feature_set: str,
) -> dict[str, Any]:
    """Inner-split validation run for one (series, detector, feature set).

    Fits on the first 80% of the *train window* only; the returned payloads
    cover the last 20% of the train window. Test rows are never touched here —
    the outer test split starts at ``n_train`` and this function stops there.
    """
    feat = build_series_features(df, config.windows, feature_set=feature_set)
    n_train = int(feat.height * config.train_frac)
    if feat.height - n_train < max(config.windows):
        raise ValueError(f"series too short after feature build: {feat.height} rows")
    n_inner, n_val = inner_train_val(n_train)
    cols = [c for c in feat.columns if c != "timestamp"]
    x = feat.select(cols).to_numpy()
    times = feat["timestamp"].to_numpy()

    model = make_model(detector, config)
    if detector == "lof":
        model.fit_predict(x[:n_inner])
    else:
        model.fit(x[:n_inner])
    ref_scores = anomaly_scores(model, detector, x[:n_inner])
    val_scores = anomaly_scores(model, detector, x[n_inner:n_train])

    ts_val = times[n_inner:n_train]
    y_val = windows_to_mask(ts_val, windows)
    # only windows actually overlapping the validation slice are visible to
    # selection: a window starting after the slice ends lives in the test
    # split, and its label must not inform the operating point
    t_first, t_last = ts_val[0], ts_val[-1]
    val_windows = [
        w
        for w in windows
        if np.datetime64(datetime.fromisoformat(w[1])) >= t_first
        and np.datetime64(datetime.fromisoformat(w[0])) <= t_last
    ]
    step_ns = float(np.median(np.diff(times.astype("datetime64[ns]"))))
    return {
        "detector": detector,
        "feature_set": feature_set,
        "n_train": int(n_train),
        "n_inner": int(n_inner),
        "n_val": int(n_val),
        "evaluable": len(val_windows) > 0,
        "n_windows": len(val_windows),
        "point_prevalence": float(y_val.mean()),
        "ref_scores": ref_scores,
        "val_scores": val_scores,
        "ts_val": ts_val,
        "step_ns": step_ns,
        "windows": val_windows,
    }


def budgeted_surface(
    run: dict[str, Any],
    budgets: tuple[float, ...] = THRESHOLD_BUDGETS,
    cooldows: tuple[float, ...] = COOLDOWN_HOURS_GRID,
) -> list[dict[str, Any]]:
    """Validation metrics of the budgeted alert stream over the (budget, cooldown) grid.

    One row per grid point: threshold anchored on the fit-slice scores at
    ``1 - budget``, episodes from the validation scores, then the per-series
    cooldown applied at the series' own sampling cadence.
    """
    out: list[dict[str, Any]] = []
    for budget in budgets:
        threshold = float(np.quantile(run["ref_scores"], 1.0 - budget))
        alert_idx = np.flatnonzero(run["val_scores"] >= threshold)
        firings, _ = episode_firing_times(alert_idx, run["val_scores"])
        for cd in cooldows:
            budgeted = cooldown_budget(firings, run["step_ns"], cooldown_hours=cd)
            metrics = _stream_metrics(
                budgeted,
                int(budgeted.size),
                run["ts_val"],
                run["windows"],
                run["step_ns"],
                run["evaluable"],
            )
            out.append({"budget": float(budget), "cooldown_hours": float(cd), **metrics})
    return out


def aggregate_surface(run_surfaces: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Mean-over-runs surface (same grid order in every per-run list)."""
    if not run_surfaces:
        raise ValueError("no validation runs to aggregate")
    out: list[dict[str, Any]] = []
    for i, combo in enumerate(run_surfaces[0]):
        out.append(
            {
                "budget": float(combo["budget"]),
                "cooldown_hours": float(combo["cooldown_hours"]),
                "range_f1": float(np.mean([r[i]["range_f1"] for r in run_surfaces])),
                "range_recall": float(np.mean([r[i]["range_recall"] for r in run_surfaces])),
                "alerts_fired": int(sum(r[i]["alerts_fired"] for r in run_surfaces)),
            }
        )
    return out


def _surface_row(surface: list[dict[str, Any]], budget: float, cooldown: float) -> dict[str, Any]:
    for row in surface:
        if row["budget"] == budget and row["cooldown_hours"] == cooldown:
            return row
    raise ValueError(f"operating point ({budget}, {cooldown}) not in the selection grid")


def select_operating_point(
    surface: list[dict[str, Any]],
    default: tuple[float, float] = (DEFAULT_BUDGET, DEFAULT_COOLDOWN_HOURS),
    min_gain: float = MIN_GAIN,
) -> dict[str, Any]:
    """Deterministic conservative argmax over one family's validation surface.

    Ranking: higher validation range-F1, then fewer budgeted alerts, then the
    documented default point, then the lower budget, then the shorter cooldown.
    The argmax is adopted only when it beats the default by ``min_gain``;
    otherwise the default stands (``adopted=False`` = the measured
    "no robust gain" path). ``plateau_count`` and ``neighbor_mean_range_f1``
    expose how fragile the peak is on a 5-window validation set.
    """
    default_row = _surface_row(surface, *default)
    best = min(
        surface,
        key=lambda r: (
            -r["range_f1"],
            r["alerts_fired"],
            0 if (r["budget"], r["cooldown_hours"]) == default else 1,
            r["budget"],
            r["cooldown_hours"],
        ),
    )
    gain = float(best["range_f1"] - default_row["range_f1"])
    adopted = gain >= min_gain
    plateau = [r for r in surface if r["range_f1"] >= best["range_f1"] - min_gain]
    budgets = sorted({r["budget"] for r in surface})
    cooldows = sorted({r["cooldown_hours"] for r in surface})
    neighbors = [
        r
        for r in surface
        if r is not best
        and (
            abs(budgets.index(r["budget"]) - budgets.index(best["budget"]))
            + abs(cooldows.index(r["cooldown_hours"]) - cooldows.index(best["cooldown_hours"]))
            == 1
        )
    ]
    selected = best if adopted else default_row
    return {
        "budget": float(selected["budget"]),
        "cooldown_hours": float(selected["cooldown_hours"]),
        "adopted": bool(adopted),
        "val_range_f1": float(selected["range_f1"]),
        "val_range_f1_best": float(best["range_f1"]),
        "val_range_f1_default": float(default_row["range_f1"]),
        "val_gain_over_default": gain,
        "plateau_count": len(plateau),
        "neighbor_mean_range_f1": float(np.mean([r["range_f1"] for r in neighbors]))
        if neighbors
        else None,
        "grid_size": len(surface),
    }


def tune_figure(selection: dict[str, Any]) -> go.Figure:
    """Validation surface per detector family: range-F1 vs cooldown, one line
    per threshold budget; ring = documented default, star = adopted point."""
    fig = make_subplots(rows=1, cols=len(DETECTORS), subplot_titles=list(DETECTORS))
    for col, detector in enumerate(DETECTORS, start=1):
        surface = selection["surfaces"][detector]
        chosen = selection["families"][detector]
        for budget in THRESHOLD_BUDGETS:
            rows = sorted(
                (r for r in surface if r["budget"] == budget),
                key=lambda r: r["cooldown_hours"],
            )
            fig.add_scatter(
                x=[r["cooldown_hours"] for r in rows],
                y=[r["range_f1"] for r in rows],
                mode="lines+markers",
                name=f"threshold budget {budget:.3f}",
                legendgroup=f"{budget}",
                showlegend=col == 1,
                row=1,
                col=col,
            )
        default_row = _surface_row(surface, DEFAULT_BUDGET, DEFAULT_COOLDOWN_HOURS)
        fig.add_scatter(
            x=[default_row["cooldown_hours"]],
            y=[default_row["range_f1"]],
            mode="markers",
            name="default (kept if star absent)",
            marker={"symbol": "circle-open", "size": 13, "color": "#64748b"},
            showlegend=col == 1,
            row=1,
            col=col,
        )
        if chosen["adopted"]:
            fig.add_scatter(
                x=[chosen["cooldown_hours"]],
                y=[chosen["val_range_f1"]],
                mode="markers",
                name="adopted operating point",
                marker={"symbol": "star", "size": 15, "color": "#dc2626"},
                showlegend=col == 1,
                row=1,
                col=col,
            )
    fig.update_xaxes(type="log", title="per-series cooldown (hours, log)")
    fig.update_yaxes(title="validation range-F1 (budgeted stream)", range=[0, 1.05])
    fig.update_layout(title="Train-side operating-point selection surfaces (NAB)")
    add_takeaway(
        fig,
        "inner 80/20 split of each train window — mean over 12 series x 2 feature "
        "sets; only points >=0.05 F1 above the ring move the operating point",
    )
    return apply_theme(fig, height=460)


def _iter_series(config: AnomalyConfig) -> Any:
    """Yield (key, frame, label windows) for every pinned NAB series."""
    labels = fetch_labels(config)
    for family, series_list in NAB_SERIES.items():
        for name, sha256 in series_list:
            key = f"{family}/{name}"
            df = parse_series_csv(fetch_series(config, family, name, sha256))
            yield key, df, labels[f"{key}.csv"]


def _compare_vs_default(
    config: AnomalyConfig,
    cells: dict[str, Any],
    families: dict[str, Any],
) -> dict[str, Any]:
    """Budgeted-stream deltas between the tuned evaluation and the committed
    default-operating-point sweep (reports/nab_sweep.json, same conventions)."""
    sweep_path = config.reports_path / "nab_sweep.json"
    if not sweep_path.exists():
        return {"available": False, "reason": f"{sweep_path} not present"}
    sweep = json.loads(sweep_path.read_text())

    def budgeted(entry: dict[str, Any]) -> dict[str, Any]:
        return dict(entry["overall"]["streams"]["budgeted"])

    out: dict[str, Any] = {"available": True, "sourced_from": str(sweep_path.name), "cells": {}}
    for cell_key, entry in sweep["grid"].items():
        detector = cell_key.split("+")[0]
        sel = families[detector]
        default_b, tuned_b = budgeted(entry), budgeted(cells[cell_key])
        out["cells"][cell_key] = {
            "operating_point": {
                "budget": sel["budget"],
                "cooldown_hours": sel["cooldown_hours"],
                "adopted": sel["adopted"],
            },
            "default_budgeted": default_b,
            "tuned_budgeted": tuned_b,
            "delta_alerts_fired": int(tuned_b["alerts_fired"] - default_b["alerts_fired"]),
            "delta_range_f1": float(tuned_b["range_f1"] - default_b["range_f1"]),
            "delta_range_recall": float(tuned_b["range_recall"] - default_b["range_recall"]),
        }
    return out


def run_nab_tune(config: AnomalyConfig) -> dict[str, Any]:
    """The tuning stage: select per-family operating points on train-side
    validation, evaluate each once on the test window, write the artifact."""
    # --- phase A: selection surface (train window only) ---------------------
    run_surfaces: dict[str, list[list[dict[str, Any]]]] = {d: [] for d in DETECTORS}
    val_windows_per_series: dict[str, int] = {}
    for key, df, windows in _iter_series(config):
        for detector in DETECTORS:
            for feature_set in FEATURE_SETS:
                run = build_validation_run(df, windows, config, detector, feature_set)
                # window layout is detector/feature-set-independent; count once
                if detector == DETECTORS[0] and feature_set == FEATURE_SETS[0]:
                    val_windows_per_series[key] = run["n_windows"] if run["evaluable"] else 0
                run_surfaces[detector].append(budgeted_surface(run))
        logger.info(
            "%s: %d validation window(s) in the inner train split",
            key,
            val_windows_per_series[key],
        )

    surfaces = {d: aggregate_surface(rs) for d, rs in run_surfaces.items()}
    families = {d: select_operating_point(surfaces[d]) for d in DETECTORS}
    for detector in DETECTORS:
        sel = families[detector]
        logger.info(
            "select %s: budget=%.3f cooldown=%.0fh adopted=%s (val F1 %.3f vs default %.3f)",
            detector,
            sel["budget"],
            sel["cooldown_hours"],
            sel["adopted"],
            sel["val_range_f1"],
            sel["val_range_f1_default"],
        )

    # --- phase B: one test evaluation per adopted operating point -----------
    cells: dict[str, Any] = {}
    family_runs: dict[str, list[dict[str, Any]]] = {d: [] for d in DETECTORS}
    for detector in DETECTORS:
        sel = families[detector]
        for feature_set in FEATURE_SETS:
            rows: list[dict[str, Any]] = []
            by_family: dict[str, list[dict[str, Any]]] = {}
            for key, df, windows in _iter_series(config):
                result = evaluate_sweep_series(
                    df,
                    windows,
                    config,
                    detector,
                    feature_set,
                    threshold_budget=sel["budget"],
                    cooldown_hours=sel["cooldown_hours"],
                )
                rows.append(result)
                by_family.setdefault(key.split("/")[0], []).append(result)
            family_runs[detector].extend(rows)
            cells[f"{detector}+{feature_set}"] = {
                "operating_point": {
                    "budget": sel["budget"],
                    "cooldown_hours": sel["cooldown_hours"],
                    "adopted": sel["adopted"],
                },
                "overall": _aggregate_runs(rows),
                "by_family": {fam: _aggregate_runs(rs) for fam, rs in by_family.items()},
            }

    evaluation = {
        "cells": cells,
        "families": {
            detector: {
                "operating_point": {
                    "budget": families[detector]["budget"],
                    "cooldown_hours": families[detector]["cooldown_hours"],
                    "adopted": families[detector]["adopted"],
                },
                "overall": _aggregate_runs(family_runs[detector]),
            }
            for detector in DETECTORS
        },
    }
    vs_default = _compare_vs_default(config, cells, families)

    report: dict[str, Any] = {
        "data_source": "nab",
        "stage": "nab_tune",
        "protocol": {
            "selection_split": (
                "inner 80/20 split of each series' train window: fit on the first "
                "80%, validate on the last 20% (mirrors the synthetic HPO slice); "
                "the outer test split is never touched during selection"
            ),
            "inner_fit_frac": INNER_FIT_FRAC,
            "threshold_budgets": list(THRESHOLD_BUDGETS),
            "cooldown_hours_grid": list(COOLDOWN_HOURS_GRID),
            "default_operating_point": {
                "budget": DEFAULT_BUDGET,
                "cooldown_hours": DEFAULT_COOLDOWN_HOURS,
            },
            "min_gain_to_adopt": MIN_GAIN,
            "objective": "range-F1 of the budgeted alert stream (dedup + per-series cooldown)",
            "aggregation": (
                "mean over all 12 series including non-evaluable ones (0), "
                "averaged over the family's two feature sets (24 runs per point)"
            ),
            "tie_break": (
                "higher validation range-F1; then fewer budgeted alerts; then the "
                "default point; then lower budget; then shorter cooldown"
            ),
            "test_evaluations_per_family": 1,
            "lead_steps": LEAD_STEPS,
            "stream_definitions": {
                "raw": "every above-threshold test minute alerts",
                "deduped": "contiguous above-threshold runs fire one episode alert at the "
                "run's max-score minute",
                "budgeted": "deduped episodes plus the family's selected per-series cooldown",
            },
        },
        "validation_evidence": {
            "series_evaluable": sum(1 for v in val_windows_per_series.values() if v > 0),
            "series_total": len(val_windows_per_series),
            "windows_total": int(sum(val_windows_per_series.values())),
            "windows_per_series": val_windows_per_series,
        },
        "selection": {"surfaces": surfaces, "families": families},
        "evaluation": evaluation,
        "vs_default_sweep_budgeted": vs_default,
    }
    out = config.reports_path / "nab_tune.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    save_json(tune_figure(report["selection"]), config.figures_dir / "nab_tune_surface.json")
    logger.info("wrote %s and the nab_tune_surface figure", out)
    return report
