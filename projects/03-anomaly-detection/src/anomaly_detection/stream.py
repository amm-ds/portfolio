"""Adaptive-threshold streaming detection (wave-7 headline).

Simulates deploying the champion detector on the test window as a stream of
chunks (24 h = 1 440 minutes each). A fixed-threshold run anchors the
baseline; the adaptive run monitors per-chunk score-distribution drift with a
robust statistic — the chunk median's z-shift against the train-window
reference, normalized by the reference IQR:

    drift_z(chunk) = |median(scores_chunk) - median(scores_train)| / IQR(scores_train)

When |drift_z| > ``drift_z_max`` a drift event is recorded and the threshold
for subsequent chunks is re-anchored to the drifting distribution's
``1 - contamination`` quantile, so the alert budget (flagged fraction) holds
in absolute terms while drift persists; when drift clears, the threshold
reverts to the train-window fixed quantile.
"""

import json
from typing import Any

import joblib
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_json

from anomaly_detection.config import AnomalyConfig
from anomaly_detection.evaluate import predict_at_contamination
from anomaly_detection.features import load_features
from anomaly_detection.model import anomaly_scores, feature_matrix, split_train_test

logger = get_logger(__name__)

CHUNK_ROWS = 1_440  # 24 h of one-minute telemetry
DRIFT_Z_MAX = 1.0


def drift_z(chunk_scores: np.ndarray, ref_median: float, ref_iqr: float) -> float:
    """Robust drift statistic: median shift in units of reference IQR."""
    if ref_iqr <= 0:
        return 0.0
    return float(abs(np.median(chunk_scores) - ref_median) / ref_iqr)


def _rates(flags: np.ndarray, y_true: np.ndarray) -> dict[str, float]:
    tp = int((flags & (y_true == 1)).sum())
    fp = int((flags & (y_true == 0)).sum())
    fn = int(((~flags) & (y_true == 1)).sum())
    return {
        "flags": int(flags.sum()),
        "tp": tp,
        "fp": fp,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
    }


def simulate_stream(
    model: Any,
    model_name: str,
    config: AnomalyConfig,
    chunk_rows: int = CHUNK_ROWS,
    drift_z_max: float = DRIFT_Z_MAX,
) -> dict[str, Any]:
    """Run fixed vs. adaptive threshold over the chunked test window."""
    df = load_features(config)
    train, test = split_train_test(df, config.train_frac)
    x_train, x_test = feature_matrix(train, config), feature_matrix(test, config)
    y_test = test["is_anomaly"].to_numpy().astype(int)

    ref_scores = anomaly_scores(model, model_name, x_train)
    ref_median, ref_iqr = (
        float(np.median(ref_scores)),
        float(np.percentile(ref_scores, 75) - np.percentile(ref_scores, 25)),
    )
    fixed_threshold = float(np.quantile(ref_scores, 1.0 - config.contamination))
    test_scores = anomaly_scores(model, model_name, x_test)

    n_chunks = int(np.ceil(len(y_test) / chunk_rows))
    fixed_flags = predict_at_contamination(test_scores, config.contamination).astype(bool)
    adaptive_flags = np.zeros(len(y_test), dtype=bool)
    drift_events: list[int] = []

    threshold = fixed_threshold
    chunk_drift_z: list[float] = []
    for i in range(n_chunks):
        sl = slice(i * chunk_rows, min((i + 1) * chunk_rows, len(y_test)))
        chunk = test_scores[sl]
        adaptive_flags[sl] = chunk >= threshold
        z = drift_z(chunk, ref_median, ref_iqr)
        chunk_drift_z.append(z)
        if z > drift_z_max:
            drift_events.append(i)
            threshold = float(np.quantile(chunk, 1.0 - config.contamination))
        else:
            threshold = fixed_threshold

    result: dict[str, Any] = {
        "model": model_name,
        "chunk_rows": chunk_rows,
        "n_chunks": n_chunks,
        "drift_z_max": drift_z_max,
        "drift_statistic": "abs(chunk_median - train_median) / train_IQR",
        "chunk_drift_z": chunk_drift_z,
        "ref_median": ref_median,
        "ref_iqr": ref_iqr,
        "fixed_threshold": fixed_threshold,
        "drift_events": drift_events,
        "fixed": _rates(fixed_flags, y_test),
        "adaptive": _rates(adaptive_flags, y_test),
        "prevalence": float(y_test.mean()),
    }
    logger.info(
        "stream: %d chunks, %d drift events; fixed flags=%d adaptive flags=%d",
        n_chunks,
        len(drift_events),
        result["fixed"]["flags"],
        result["adaptive"]["flags"],
    )
    result["figure"] = str(
        save_json(
            adaptive_stream_figure(result),
            config.figures_dir / "adaptive_stream.json",
        )
    )
    return result


def adaptive_stream_figure(result: dict[str, Any]) -> go.Figure:
    """Fixed/adaptive detection outcomes plus the per-chunk drift statistic."""
    outcomes = ("alerts", "true positives", "false positives")
    keys = ("flags", "tp", "fp")
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("detection outcomes (test minutes)", "drift statistic per chunk"),
    )
    for name, color in (("fixed", "#64748b"), ("adaptive", "#38bdf8")):
        rates = result[name]
        fig.add_bar(
            x=list(outcomes),
            y=[rates[key] for key in keys],
            name=name,
            marker_color=color,
            text=[rates[key] for key in keys],
            textposition="outside",
            row=1,
            col=1,
        )
    drift = result["chunk_drift_z"]
    drift_max = max(drift) if drift else 0.1
    thresh = float(result["drift_z_max"])
    fig.add_scatter(
        x=list(range(1, len(drift) + 1)),
        y=drift,
        name="drift z",
        mode="lines+markers",
        marker_color="#f472b6",
        showlegend=False,
        row=1,
        col=2,
    )
    if thresh <= drift_max * 2.5:
        fig.add_hline(
            y=thresh,
            line={"dash": "dot", "color": "#fbbf24"},
            row=1,
            col=2,
        )
        y2_upper = max(drift_max, thresh) * 1.15
        thresh_note = "dotted = drift trigger threshold"
    else:
        y2_upper = drift_max * 1.35
        thresh_note = f"trigger threshold {thresh:.2f} sits off-scale above the data"
    fig.update_xaxes(title="outcome", row=1, col=1)
    fig.update_xaxes(title="chunk", row=1, col=2, dtick=1)
    fig.update_yaxes(title="minutes", row=1, col=1)
    fig.update_yaxes(title="|median shift| / train IQR", range=[0.0, y2_upper], row=1, col=2)
    fig.update_layout(title="Fixed vs adaptive stream outcomes and drift", barmode="group")
    fixed, adaptive = result["fixed"], result["adaptive"]
    add_takeaway(
        fig,
        f"{len(result['drift_events'])} of {result['n_chunks']} chunks trigger drift; "
        f"fixed precision/recall {fixed['precision']:.3f}/{fixed['recall']:.3f}; "
        f"adaptive {adaptive['precision']:.3f}/{adaptive['recall']:.3f}; "
        f"{thresh_note}",
    )
    return apply_theme(fig)


def load_champion(config: AnomalyConfig) -> tuple[Any, str]:
    """The champion detector: tuned IsolationForest when available, else untuned."""
    preferred = [
        (config.tuned_models_dir, "isolation_forest_tuned"),
        (config.models_dir, "isolation_forest"),
        (config.models_dir, config.models[0]),
    ]
    for directory, name in preferred:
        path = directory / f"{name}.joblib"
        if path.exists():
            return joblib.load(path), name
    raise FileNotFoundError("no detector artifacts found; run train/tune first")


def run_detection(
    config: AnomalyConfig,
    adaptive: bool = True,
    chunk_rows: int = CHUNK_ROWS,
    drift_z_max: float = DRIFT_Z_MAX,
) -> dict[str, Any]:
    """Full detect stage: champion scores the stream, fixed vs. adaptive."""
    model, name = load_champion(config)
    result = simulate_stream(model, name, config, chunk_rows, drift_z_max)
    result["adaptive_enabled"] = adaptive
    if not adaptive:
        # fixed-mode run: report the baseline only
        result.pop("adaptive")
        result.pop("drift_events")
    out = config.reports_path / "detect.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    logger.info("wrote %s", out)
    return result
