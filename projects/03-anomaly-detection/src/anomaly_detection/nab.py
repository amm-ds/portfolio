"""NAB (Numenta Anomaly Benchmark) — the primary real-data track.

A bounded subset of 12 series spanning three real-world families
(``realAWSCloudwatch``, ``realKnownCause``, ``realTraffic``) is fetched as
individual checksum-pinned CSVs from the NAB repository and evaluated with
event-based metrics that lead with PR-AUC and range-F1:

- A labelled anomaly window counts as **detected** when at least one alert
  timestamp falls inside the window, optionally extended by ``LEAD_STEPS``
  steps before the window start (early-warning credit; default 0 — alerts
  must land inside the window).
- Range precision = detected windows / (detected windows + alerts fired
  outside any window); range recall = detected windows / total windows;
  range-F1 is their harmonic mean.

The seeded synthetic telemetry generator remains the clearly-labelled CI /
fast path (the test-suite runs entirely on it); NAB is the default
``data_source`` for real runs.

Citation: Ahmad, Lavin, Purdy & Agha (2017), "Unsupervised real-time anomaly
detection for streaming data", Neurocomputing 262:134-147.
Benchmark: https://github.com/numenta/NAB
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots
from portfolio_core.io import fetch
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_json
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, roc_auc_score

from anomaly_detection.config import AnomalyConfig
from anomaly_detection.stream import drift_z

logger = get_logger(__name__)

NAB_REPO_RAW = "https://raw.githubusercontent.com/numenta/NAB/master"
NAB_LABELS_URL = f"{NAB_REPO_RAW}/labels/combined_windows.json"
NAB_LABELS_SHA256 = "1e1fbc4601321aad8d0f8b3784c8134299379f68f6c1f7777565f8ffd57ab6b1"
LEAD_STEPS = 0  # documented early-warning tolerance; 0 = alerts must fall inside the window

# 12 series, spread across families: family -> [(name, sha256), ...].
NAB_SERIES: dict[str, list[tuple[str, str]]] = {
    "realAWSCloudwatch": [
        (
            "ec2_cpu_utilization_24ae8d",
            "ab446fbd8b9f37507eb2fdb06315826d8daeef02e241133ce06e0ee571ba53d9",
        ),
        (
            "ec2_cpu_utilization_53ea38",
            "8942e498de7b40f1b4a6d802755592c09b8fb73ce8f658763a09cb9ea1ea94ac",
        ),
        (
            "ec2_disk_write_bytes_1ef3de",
            "ce3d6c6a652ed7c31a6dd3727a36e128fcac6fb2381c63267ad0fbc02eccd9df",
        ),
        (
            "elb_request_count_8c0756",
            "74c26574a01ca9fb89dddb5021e2e13c3a93eb25dc640438a9acb1ceb00f1021",
        ),
    ],
    "realKnownCause": [
        (
            "ambient_temperature_system_failure",
            "230b68ccca20f59d562afd5d24ad52939c9b784386bed0054018358bf9120581",
        ),
        (
            "machine_temperature_system_failure",
            "92bf5b87fc7f9bba8ca0b7ec63ccaac8cb4a1371a258e8c29a10ae9c018d82a4",
        ),
        ("nyc_taxi", "d8fa6f7f0734bf5c8be12c52a94e20a82664c397d9dec4449156bd453d32856d"),
        (
            "ec2_request_latency_system_failure",
            "98378580aa80157e057c61d59d81daddccc6c65a2c0c800e3f01f603b8215c3f",
        ),
    ],
    "realTraffic": [
        ("speed_7578", "15ba994384730cb5a2e6818f17ded1430b40d92eb7a08e5b1a48a445c8c350f6"),
        ("speed_6005", "7976e7596cd1e579696c737576e96a26fe041484472ed7d0a463ce2b094d7aa7"),
        ("TravelTime_387", "38e70e9ead8227fd023bff6e93247d5bc01ee008f781b921a156962419b399bb"),
        ("occupancy_t4013", "5663a8122a300360eb51fbbd0f21706da05af1af55262926d6a226bb6d071704"),
    ],
}

# The timeline matrix is embedded as a single PNG, so it shows six curated
# panels (2x3) instead of all twelve: two per family, spanning the outcomes -
# nyc_taxi misses one labelled event while the other five detect theirs.
TIMELINE_SELECTION: tuple[str, ...] = (
    "realAWSCloudwatch/ec2_cpu_utilization_24ae8d",
    "realAWSCloudwatch/elb_request_count_8c0756",
    "realKnownCause/nyc_taxi",
    "realKnownCause/machine_temperature_system_failure",
    "realTraffic/occupancy_t4013",
    "realTraffic/speed_7578",
)


def nab_dir(config: AnomalyConfig) -> Path:
    return config.data_path / "nab"


def series_csv_url(family: str, name: str) -> str:
    return f"{NAB_REPO_RAW}/data/{family}/{name}.csv"


def parse_series_csv(path: Path) -> pl.DataFrame:
    """Parse one NAB series CSV (``timestamp,value``) into a typed frame."""
    return pl.read_csv(path).with_columns(pl.col("timestamp").str.to_datetime())


def windows_to_mask(times: np.ndarray, windows: list[list[str]]) -> np.ndarray:
    """Boolean pointwise label mask: True inside any labelled window."""
    mask = np.zeros(len(times), dtype=bool)
    for start, end in windows:
        s = np.datetime64(datetime.fromisoformat(start))
        e = np.datetime64(datetime.fromisoformat(end))
        mask |= (times >= s) & (times <= e)
    return mask


def _window_bounds(
    windows: list[list[str]], lead_steps: int, step_ns: float
) -> list[tuple[np.datetime64, np.datetime64]]:
    bounds: list[tuple[np.datetime64, np.datetime64]] = []
    for start, end in windows:
        s = np.datetime64(datetime.fromisoformat(start))
        if lead_steps:
            s_lead = s - np.timedelta64(int(step_ns) * lead_steps, "ns")
            bounds.append((s_lead, np.datetime64(datetime.fromisoformat(end))))
        else:
            bounds.append((s, np.datetime64(datetime.fromisoformat(end))))
    return bounds


def match_events(
    alert_times: np.ndarray,
    windows: list[list[str]],
    lead_steps: int = LEAD_STEPS,
    step_ns: float | None = None,
) -> tuple[list[bool], np.ndarray]:
    """Window-matching core: which windows have an alert, which alerts hit one.

    A window is detected when at least one alert timestamp falls inside it,
    optionally extended ``lead_steps`` steps *before* the start
    (early-warning credit; requires ``step_ns``, the median sampling interval
    in nanoseconds). With ``lead_steps = 0`` the lead is not applied.
    """
    in_window = np.zeros(len(alert_times), dtype=bool)
    detected: list[bool] = []
    for start, end in _window_bounds(windows, lead_steps, step_ns or 0.0):
        hits = (alert_times >= start) & (alert_times <= end)
        in_window |= hits
        detected.append(bool(hits.any()))
    return detected, in_window


def range_f1(detected: list[bool], alerts_fp: int) -> dict[str, float]:
    """Range precision/recall/F1 from window detections + out-of-window alerts."""
    tp = sum(detected)
    fn = len(detected) - tp
    precision = tp / (tp + alerts_fp) if tp + alerts_fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"range_precision": precision, "range_recall": recall, "range_f1": f1}


def build_series_features(df: pl.DataFrame, windows: list[int]) -> pl.DataFrame:
    """Rolling features for one univariate series (same recipe as telemetry)."""
    exprs = (
        [
            pl.col("value").rolling_mean(window_size=w, min_samples=w).alias(f"value_rmean{w}")
            for w in windows
        ]
        + [
            pl.col("value").rolling_std(window_size=w, min_samples=w).alias(f"value_rstd{w}")
            for w in windows
        ]
        + [
            (pl.col("value") - pl.col("value").rolling_median(window_size=w, min_samples=w)).alias(
                f"value_resmed{w}"
            )
            for w in windows
        ]
    )
    return df.select("timestamp", "value", *exprs).drop_nulls()


def evaluate_series(
    df: pl.DataFrame, windows: list[list[str]], config: AnomalyConfig
) -> dict[str, Any]:
    """Fit IsolationForest on the first 70% of one series; event metrics on the rest.

    Returns metric scalars plus the arrays the figures and the alert-budget
    curve need (scores, ref scores, labels, timestamps, values, alerts).
    """
    feat = build_series_features(df, config.windows)
    n_train = int(feat.height * config.train_frac)
    if feat.height - n_train < max(config.windows):
        raise ValueError(f"series too short after feature build: {feat.height} rows")
    cols = [c for c in feat.columns if c != "timestamp"]
    x = feat.select(cols).to_numpy()
    times = feat["timestamp"].to_numpy()
    values = feat["value"].to_numpy()
    y = windows_to_mask(times, windows)

    model = IsolationForest(
        n_estimators=config.n_estimators,
        contamination=config.contamination,
        random_state=config.seed,
        n_jobs=-1,
    )
    model.fit(x[:n_train])
    ref_scores = -model.decision_function(x[:n_train])
    scores = -model.decision_function(x[n_train:])
    y_test, ts_test, vals_test = y[n_train:], times[n_train:], values[n_train:]

    # only windows overlapping the scored (test) portion are evaluable
    t0 = ts_test[0]
    test_windows = [w for w in windows if np.datetime64(datetime.fromisoformat(w[1])) >= t0]
    evaluable = len(test_windows) > 0
    has_positives = bool(y_test.any())

    threshold = float(np.quantile(ref_scores, 1.0 - config.contamination))
    alerts = scores >= threshold
    step_ns = float(np.median(np.diff(times.astype("datetime64[ns]"))))
    detected: list[bool] = []
    in_window = np.zeros(int(alerts.sum()), dtype=bool)
    if evaluable:
        detected, in_window = match_events(ts_test[alerts], test_windows, LEAD_STEPS, step_ns)
    rf1 = range_f1(detected, int((~in_window).sum()))

    # adaptive pass: 10 chunks, drift z vs. the train reference
    chunk_len = int(np.ceil(len(scores) / 10))
    ref_med, ref_iqr = (
        float(np.median(ref_scores)),
        float(np.percentile(ref_scores, 75) - np.percentile(ref_scores, 25)),
    )
    adaptive_flags = np.zeros(len(scores), dtype=bool)
    drift_events = 0
    current = threshold
    for i in range(10):
        sl = slice(i * chunk_len, min((i + 1) * chunk_len, len(scores)))
        adaptive_flags[sl] = scores[sl] >= current
        if drift_z(scores[sl], ref_med, ref_iqr) > 1.0:
            drift_events += 1
            current = float(np.quantile(scores[sl], 1.0 - config.contamination))
        else:
            current = threshold

    metrics: dict[str, Any] = {
        "n_points": int(feat.height),
        "n_test": len(y_test),
        "n_windows": len(test_windows),
        "n_windows_total": len(windows),
        "evaluable": evaluable,
        "point_prevalence": float(y_test.mean()),
        "pr_auc": float(average_precision_score(y_test, scores)) if has_positives else None,
        "roc_auc": float(roc_auc_score(y_test, scores)) if has_positives else None,
        "alerts_fired": int(alerts.sum()),
        "events_detected": int(sum(detected)),
        "events_missed": int(len(detected) - sum(detected)),
        **rf1,
        "adaptive_drift_events": drift_events,
        "adaptive_flags": int(adaptive_flags.sum()),
        # figure/curve payloads
        "scores": scores,
        "ref_scores": ref_scores,
        "y_test": y_test,
        "ts_test": ts_test,
        "values": vals_test,
        "alerts": alerts,
        "windows": test_windows,  # only windows overlapping the scored portion
        "step_ns": step_ns,
    }
    return metrics


def fetch_series(config: AnomalyConfig, family: str, name: str, sha256: str) -> Path:
    """Fetch one checksum-pinned series CSV into ``data/nab/``."""
    directory = nab_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / f"{family}__{name}.csv"
    if not dest.exists():
        fetch(series_csv_url(family, name), dest, expected_sha256=sha256)
    return dest


def fetch_labels(config: AnomalyConfig) -> dict[str, list[list[str]]]:
    """Fetch the combined label windows (checksum-pinned)."""
    directory = nab_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / "combined_windows.json"
    if not dest.exists():
        fetch(NAB_LABELS_URL, dest, expected_sha256=NAB_LABELS_SHA256)
    return dict(json.loads(dest.read_text()))


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ["range_f1", "range_precision", "range_recall"]
    out: dict[str, Any] = {k: float(np.mean([r[k] for r in rows])) for k in keys}
    for k in ("pr_auc", "roc_auc"):
        vals = [r[k] for r in rows if r[k] is not None]
        out[k] = float(np.mean(vals)) if vals else None
    out["series_evaluated"] = sum(1 for r in rows if r["evaluable"])
    out["series_total"] = len(rows)
    out["events_detected"] = int(sum(r["events_detected"] for r in rows))
    out["events_missed"] = int(sum(r["events_missed"] for r in rows))
    out["alerts_fired"] = int(sum(r["alerts_fired"] for r in rows))
    out["adaptive_drift_events"] = int(sum(r["adaptive_drift_events"] for r in rows))
    return out


def alert_budget_curve(
    results: dict[str, dict[str, Any]], config: AnomalyConfig
) -> dict[str, list[dict[str, float]]]:
    """Range-F1 vs. alert budget (train-quantile thresholds), per family + overall."""
    budgets = np.geomspace(0.001, 0.10, 12)
    groups: dict[str, list[str]] = {"overall": list(results)}
    for key in results:
        groups.setdefault(key.split("/")[0], []).append(key)
    out: dict[str, list[dict[str, float]]] = {}
    for label, keys in groups.items():
        rows: list[dict[str, float]] = []
        for budget in budgets:
            f1s = []
            for key in keys:
                r = results[key]
                thr = float(np.quantile(r["ref_scores"], 1.0 - budget))
                alert_times = r["ts_test"][r["scores"] >= thr]
                detected, in_window = match_events(
                    alert_times, r["windows"], LEAD_STEPS, r["step_ns"]
                )
                f1s.append(range_f1(detected, int((~in_window).sum()))["range_f1"])
            rows.append({"budget": float(budget), "range_f1": float(np.mean(f1s))})
        out[label] = rows
    return out


def nab_figures(
    results: dict[str, dict[str, Any]], budget_curve: dict[str, list[dict[str, float]]]
) -> dict[str, go.Figure]:
    """Per-series timeline panel, pooled score distributions, alert-budget curve.

    The timeline figure is the one embedded in the docs, so it shows six
    curated series (2 rows x 3 cols) rather than all twelve - large enough
    for timestamps and alert markers to read at the embedded size.
    """
    keys = [k for k in TIMELINE_SELECTION if k in results] or list(results)[:6]
    titles = [k.split("/", 1)[1] for k in keys]
    fig = make_subplots(rows=2, cols=3, subplot_titles=titles)
    for idx, key in enumerate(keys):
        row, col = idx // 3 + 1, idx % 3 + 1
        r = results[key]
        fig.add_scatter(
            x=r["ts_test"],
            y=r["values"],
            mode="lines",
            showlegend=False,
            line={"width": 1.5},
            row=row,
            col=col,
        )
        for start, end in r["windows"]:
            fig.add_vrect(
                x0=start,
                x1=end,
                fillcolor="#fbbf24",
                opacity=0.25,
                line_width=0,
                row=row,
                col=col,
            )
        fig.add_scatter(
            x=r["ts_test"][r["alerts"]],
            y=r["values"][r["alerts"]],
            mode="markers",
            showlegend=False,
            marker={"color": "#f472b6", "size": 9, "symbol": "x", "line": {"width": 2}},
            row=row,
            col=col,
        )
    n_alerts = sum(int(results[k]["alerts_fired"]) for k in keys)
    fig.update_annotations(font_size=15)
    fig.update_xaxes(tickformat="%b %d", nticks=4)
    fig.update_yaxes(tickfont_size=13)
    fig.update_xaxes(tickfont_size=13)
    fig.update_layout(
        title={
            "text": (
                "Real NAB telemetry hides labelled incidents in noisy baselines — "
                f"most of the {n_alerts:,} alerts miss the event windows"
            ),
            "font": {"size": 19},
        },
    )
    add_takeaway(
        fig,
        "Six representative series (id per panel): amber bands are the labelled "
        "windows, pink crosses are alerts - nyc_taxi misses one window.",
    )
    timelines = apply_theme(fig, height=820)

    scores = np.concatenate([r["scores"] for r in results.values()])
    y = np.concatenate([r["y_test"] for r in results.values()])
    lo, hi = float(scores.min()), float(scores.max())
    bin_size = (hi - lo) / 60 or 1.0
    dist_fig = go.Figure()
    dist_fig.add_histogram(
        x=scores[y == 0], xbins={"start": lo, "end": hi, "size": bin_size}, name="outside windows"
    )
    dist_fig.add_histogram(
        x=scores[y == 1], xbins={"start": lo, "end": hi, "size": bin_size}, name="inside windows"
    )
    dist_fig.update_yaxes(type="log", title="count (log scale)")
    dist_fig.update_xaxes(title="anomaly score")
    dist_fig.update_layout(
        title="Real in-window scores overlap the normal mass - NAB rarity defeats clean separation",
        barmode="overlay",
    )
    dist_fig.update_traces(opacity=0.65)
    add_takeaway(
        dist_fig,
        "Real in-window scores overlap the normal mass far more than synthetic anomalies do.",
    )
    distribution = apply_theme(dist_fig)

    budget_fig = go.Figure()
    for label, curve_rows in budget_curve.items():
        budget_fig.add_scatter(
            x=[r["budget"] for r in curve_rows],
            y=[r["range_f1"] for r in curve_rows],
            mode="lines",
            name=label,
        )
    budget_fig.update_xaxes(type="log", title="alert budget (flagged fraction)")
    budget_fig.update_yaxes(title="range-F1", range=[0, 1.05])
    budget_fig.update_layout(
        title=(
            "Event-level range-F1 peaks at a small alert budget - "
            "more pages mostly add false alarms"
        )
    )
    add_takeaway(
        budget_fig, "Event-level F1 peaks at a small budget; more alerts mostly add false pages."
    )
    return {
        "nab_timelines": timelines,
        "nab_score_distribution": distribution,
        "nab_alert_budget": apply_theme(budget_fig),
    }


_JSON_PAYLOAD_KEYS = ("scores", "ref_scores", "y_test", "ts_test", "values", "alerts", "step_ns")


def run_nab(config: AnomalyConfig) -> dict[str, Any]:
    """NAB stage: fetch, evaluate all series, aggregate, figures, artifact."""
    labels = fetch_labels(config)
    results: dict[str, dict[str, Any]] = {}
    for family, series_list in NAB_SERIES.items():
        for name, sha256 in series_list:
            key = f"{family}/{name}"
            df = parse_series_csv(fetch_series(config, family, name, sha256))
            result = evaluate_series(df, labels[f"{key}.csv"], config)
            results[key] = result
            logger.info(
                "%s: PR-AUC=%.3f range-F1=%.3f (%d/%d events, %d alerts)",
                key,
                result["pr_auc"],
                result["range_f1"],
                result["events_detected"],
                result["n_windows"],
                result["alerts_fired"],
            )

    budget_curve = alert_budget_curve(results, config)
    figures = nab_figures(results, budget_curve)
    for name, fig in figures.items():
        save_json(fig, config.figures_dir / f"{name}.json")

    by_family: dict[str, list[dict[str, Any]]] = {}
    for key, r in results.items():
        by_family.setdefault(key.split("/")[0], []).append(r)
    report: dict[str, Any] = {
        "data_source": "nab",
        "series": {
            k: {kk: vv for kk, vv in r.items() if kk not in _JSON_PAYLOAD_KEYS}
            for k, r in results.items()
        },
        "by_family": {fam: _aggregate(rs) for fam, rs in by_family.items()},
        "overall": _aggregate(list(results.values())),
        "lead_steps": LEAD_STEPS,
        "event_rule": (
            "window detected if >=1 alert inside; range precision over alerts outside windows"
        ),
    }
    out = config.reports_path / "nab_metrics.json"
    out.write_text(json.dumps(report, indent=2))
    logger.info(
        "NAB overall: PR-AUC=%.3f range-F1=%.3f (%d/%d events, %d alerts, %d drift events)",
        report["overall"]["pr_auc"],
        report["overall"]["range_f1"],
        report["overall"]["events_detected"],
        report["overall"]["events_detected"] + report["overall"]["events_missed"],
        report["overall"]["alerts_fired"],
        report["overall"]["adaptive_drift_events"],
    )
    return report
