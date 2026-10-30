"""NAB detector-family x feature-set sweep with alert-load operations.

Roadmap wave (story: "run all detector families and residual features on
NAB; add event deduplication and per-series budgets"): the headline NAB
pass evaluates IsolationForest only. This sweep keeps every headline
convention — 70/30 time-ordered split, the train-anchored fixed 2%
threshold (no label tuning), window detection with lead 0, aggregation as
the mean over all 12 series including the 3 non-evaluable ones (mirrors
:func:`anomaly_detection.nab._aggregate`) — and extends the grid:

- **detectors** — ``isolation_forest`` / ``lof`` / ``ocsvm``, untuned
  (config defaults), the same honest-search-free comparison the synthetic
  ladder reports;
- **feature sets** — ``rolling`` (value + rolling mean/std) vs
  ``rolling_residual`` (adds rolling-median residual columns — the current
  headline recipe includes them by default).

On top of every (detector, feature set, series) run it measures the
alert-load layer at the fixed threshold, three streams deep:

- ``raw`` — every above-threshold minute pages (the observed operating cost);
- ``deduped`` — contiguous above-threshold runs collapse to ONE episode
  alert fired at the run's max-score minute (a burst pages once, not 50x);
- ``budgeted`` — a per-series cooldown: after an episode fires, the series
  is silent for 24 h at its own sampling cadence (a paging-rate cap of one
  page per day per series, not a detection rule).

Each stream gets alerts fired, episode count, windows touched, and the
event-aware range precision/recall/F1. Aggregation per NAB family and
overall mirrors the headline artifact so the numbers are directly
comparable.
"""

import json
from typing import Any

import numpy as np
import polars as pl
from portfolio_core.logging import get_logger
from sklearn.metrics import average_precision_score, roc_auc_score

from anomaly_detection.config import AnomalyConfig
from anomaly_detection.model import anomaly_scores, make_model
from anomaly_detection.nab import (
    LEAD_STEPS,
    NAB_SERIES,
    _aggregate,
    build_series_features,
    fetch_labels,
    fetch_series,
    match_events,
    parse_series_csv,
    range_f1,
    windows_to_mask,
)

logger = get_logger(__name__)

DETECTORS: tuple[str, ...] = ("isolation_forest", "lof", "ocsvm")
FEATURE_SETS: tuple[str, ...] = ("rolling", "rolling_residual")
STREAMS: tuple[str, ...] = ("raw", "deduped", "budgeted")

# Per-series alert budget: at most one page per 24 h at the series' own
# sampling cadence (converted to median-step units per series).
COOLDOWN_HOURS = 24.0

_JSON_PAYLOAD_KEYS = ("scores", "y_test", "ts_test", "values", "step_ns")


def episode_firing_times(alert_idx: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, int]:
    """Collapse contiguous alert runs into episode firings.

    ``alert_idx`` = test-row indices (time order) at/above the threshold.
    A run is a maximal stretch of mutually adjacent indices; each run fires
    ONE alert at its max-score minute. Returns (firing row indices, n_runs).
    """
    if alert_idx.size == 0:
        return np.array([], dtype=int), 0
    splits = np.flatnonzero(np.diff(alert_idx) > 1) + 1
    runs = np.split(alert_idx, splits)
    firings = np.array([run[int(np.argmax(scores[run]))] for run in runs], dtype=int)
    return firings, len(runs)


def cooldown_budget(
    firing_idx: np.ndarray, step_ns: float, cooldown_hours: float = COOLDOWN_HOURS
) -> np.ndarray:
    """Per-series paging-rate cap: keep a firing only when the previous kept
    firing is at least ``cooldown_hours`` earlier (in median-step units)."""
    if firing_idx.size == 0:
        return firing_idx
    cooldown_steps = cooldown_hours * 3_600_000_000_000.0 / step_ns
    kept: list[int] = []
    last = -np.inf
    for idx in firing_idx:
        if idx - last >= cooldown_steps:
            kept.append(int(idx))
            last = idx
    return np.asarray(kept, dtype=int)


def _stream_metrics(
    firing_idx: np.ndarray,
    episodes: int,
    ts_test: np.ndarray,
    windows: list[list[str]],
    step_ns: float,
    evaluable: bool,
) -> dict[str, Any]:
    """Event-aware metrics for one alert stream (firings = test-row indices)."""
    detected: list[bool] = []
    n_outside = 0
    if evaluable:
        detected, in_window = match_events(ts_test[firing_idx], windows, LEAD_STEPS, step_ns)
        n_outside = int((~in_window).sum())
    rf1 = range_f1(detected, n_outside)
    return {
        "alerts_fired": int(firing_idx.size),
        "episodes": int(episodes),
        "events_detected": int(sum(detected)),
        "events_missed": int(len(detected) - sum(detected)),
        **rf1,
    }


def evaluate_sweep_series(
    df: pl.DataFrame,
    windows: list[list[str]],
    config: AnomalyConfig,
    detector: str,
    feature_set: str,
) -> dict[str, Any]:
    """One (detector, feature set, series) run: fit, score, three alert streams."""
    from datetime import datetime

    feat = build_series_features(df, config.windows, feature_set=feature_set)
    n_train = int(feat.height * config.train_frac)
    if feat.height - n_train < max(config.windows):
        raise ValueError(f"series too short after feature build: {feat.height} rows")
    cols = [c for c in feat.columns if c != "timestamp"]
    x = feat.select(cols).to_numpy()
    times = feat["timestamp"].to_numpy()
    values = feat["value"].to_numpy()
    y = windows_to_mask(times, windows)

    model = make_model(detector, config)
    if detector == "lof":
        model.fit_predict(x[:n_train])
    else:
        model.fit(x[:n_train])
    ref_scores = anomaly_scores(model, detector, x[:n_train])
    scores = anomaly_scores(model, detector, x[n_train:])
    y_test, ts_test, vals_test = y[n_train:], times[n_train:], values[n_train:]

    # only windows overlapping the scored (test) portion are evaluable
    t0 = ts_test[0]
    test_windows = [w for w in windows if np.datetime64(datetime.fromisoformat(w[1])) >= t0]
    evaluable = len(test_windows) > 0
    has_positives = bool(y_test.any())

    threshold = float(np.quantile(ref_scores, 1.0 - config.contamination))
    alert_idx = np.flatnonzero(scores >= threshold)
    step_ns = float(np.median(np.diff(times.astype("datetime64[ns]"))))

    firings, n_runs = episode_firing_times(alert_idx, scores)
    budgeted = cooldown_budget(firings, step_ns)

    streams = {
        "raw": _stream_metrics(
            alert_idx, int(alert_idx.size), ts_test, test_windows, step_ns, evaluable
        ),
        "deduped": _stream_metrics(firings, n_runs, ts_test, test_windows, step_ns, evaluable),
        "budgeted": _stream_metrics(
            budgeted, int(budgeted.size), ts_test, test_windows, step_ns, evaluable
        ),
    }

    return {
        "detector": detector,
        "feature_set": feature_set,
        "n_points": int(feat.height),
        "n_test": len(y_test),
        "n_windows": len(test_windows),
        "evaluable": evaluable,
        "point_prevalence": float(y_test.mean()),
        "pr_auc": float(average_precision_score(y_test, scores)) if has_positives else None,
        "roc_auc": float(roc_auc_score(y_test, scores)) if has_positives else None,
        "threshold": threshold,
        "streams": streams,
        # payloads the alert-budget curve would need (kept out of the JSON)
        "scores": scores,
        "y_test": y_test,
        "ts_test": ts_test,
        "values": vals_test,
        "step_ns": step_ns,
        "windows": test_windows,
    }


def _base_row(r: dict[str, Any]) -> dict[str, Any]:
    """Project a sweep run onto the fields nab._aggregate reads: event metrics
    from the raw stream (the headline operating point), pointwise AUCs from
    the run level."""
    raw = r["streams"]["raw"]
    return {
        "range_f1": raw["range_f1"],
        "range_precision": raw["range_precision"],
        "range_recall": raw["range_recall"],
        "pr_auc": r["pr_auc"],
        "roc_auc": r["roc_auc"],
        "evaluable": r["evaluable"],
        "events_detected": raw["events_detected"],
        "events_missed": raw["events_missed"],
        "alerts_fired": raw["alerts_fired"],
        "adaptive_drift_events": 0,
    }


def _aggregate_runs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mirror nab._aggregate plus a per-stream alert-load table."""
    base = _aggregate([_base_row(r) for r in rows])
    streams: dict[str, Any] = {}
    for stream in STREAMS:
        srs = [r["streams"][stream] for r in rows]
        streams[stream] = {
            "alerts_fired": int(sum(s["alerts_fired"] for s in srs)),
            "episodes": int(sum(s["episodes"] for s in srs)),
            "events_detected": int(sum(s["events_detected"] for s in srs)),
            "events_missed": int(sum(s["events_missed"] for s in srs)),
            "range_precision": float(np.mean([s["range_precision"] for s in srs])),
            "range_recall": float(np.mean([s["range_recall"] for s in srs])),
            "range_f1": float(np.mean([s["range_f1"] for s in srs])),
        }
    base["streams"] = streams
    return base


def run_nab_sweep(config: AnomalyConfig) -> dict[str, Any]:
    """The sweep stage: 12 series x 3 detectors x 2 feature sets, plus the
    dedup/cooldown alert-load layer on every run. Writes reports/nab_sweep.json."""
    labels = fetch_labels(config)
    results: dict[str, dict[str, Any]] = {}
    for family, series_list in NAB_SERIES.items():
        for name, sha256 in series_list:
            key = f"{family}/{name}"
            df = parse_series_csv(fetch_series(config, family, name, sha256))
            for detector in DETECTORS:
                for feature_set in FEATURE_SETS:
                    cfg_key = f"{detector}+{feature_set}"
                    result = evaluate_sweep_series(
                        df, labels[f"{key}.csv"], config, detector, feature_set
                    )
                    results[f"{key}|{cfg_key}"] = result
                    s = result["streams"]
                    logger.info(
                        "%s %s: raw %d / deduped %d / budgeted %d alerts (range-F1 %.3f/%.3f/%.3f)",
                        key,
                        cfg_key,
                        s["raw"]["alerts_fired"],
                        s["deduped"]["alerts_fired"],
                        s["budgeted"]["alerts_fired"],
                        s["raw"]["range_f1"],
                        s["deduped"]["range_f1"],
                        s["budgeted"]["range_f1"],
                    )

    grid: dict[str, Any] = {}
    for detector in DETECTORS:
        for feature_set in FEATURE_SETS:
            cfg_key = f"{detector}+{feature_set}"
            rows = [r for k, r in results.items() if k.endswith(f"|{cfg_key}")]
            by_family: dict[str, list[dict[str, Any]]] = {}
            for k, r in results.items():
                if k.endswith(f"|{cfg_key}"):
                    by_family.setdefault(k.split("|")[0].split("/")[0], []).append(r)
            grid[cfg_key] = {
                "overall": _aggregate_runs(rows),
                "by_family": {fam: _aggregate_runs(rs) for fam, rs in by_family.items()},
            }

    report: dict[str, Any] = {
        "data_source": "nab",
        "grid_axes": {"detectors": list(DETECTORS), "feature_sets": list(FEATURE_SETS)},
        "threshold_rule": "train-anchored fixed contamination quantile (no label tuning)",
        "lead_steps": LEAD_STEPS,
        "cooldown_hours": COOLDOWN_HOURS,
        "stream_definitions": {
            "raw": "every above-threshold test minute alerts",
            "deduped": "contiguous above-threshold runs fire one episode alert at the "
            "run's max-score minute",
            "budgeted": "deduped episodes plus a per-series cooldown: at most one page "
            "per 24 h at the series' sampling cadence",
        },
        "grid": grid,
        "series": {
            k: {kk: vv for kk, vv in r.items() if kk not in _JSON_PAYLOAD_KEYS}
            for k, r in results.items()
        },
    }
    out = config.reports_path / "nab_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    for cfg_key, entry in grid.items():
        st = entry["overall"]["streams"]
        logger.info(
            "sweep %s: PR-AUC=%.3f raw %d alerts / budgeted %d (recall %.3f/%.3f)",
            cfg_key,
            entry["overall"]["pr_auc"],
            st["raw"]["alerts_fired"],
            st["budgeted"]["alerts_fired"],
            st["raw"]["range_recall"],
            st["budgeted"]["range_recall"],
        )
    return report
