"""Evaluation: ROC-AUC / PR-AUC per detector at a fixed contamination, plus
report artifacts (metrics.json, report.html, interactive figures).

Scoring uses the continuous anomaly scores against the held-out test window;
the binary decision threshold is the ``1 - contamination`` quantile of the
test scores, so the operating point is fixed a priori rather than tuned.
"""

import json
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import polars as pl
from portfolio_core.logging import get_logger
from portfolio_core.plotting import apply_theme, save_json
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.report import ReportBuilder
from sklearn import metrics as skm

from anomaly_detection.config import SIGNALS, AnomalyConfig
from anomaly_detection.data import load_raw
from anomaly_detection.features import load_features
from anomaly_detection.model import (
    anomaly_scores,
    feature_matrix,
    load_model,
    split_train_test,
)

logger = get_logger(__name__)


def predict_at_contamination(scores: np.ndarray, contamination: float) -> np.ndarray:
    """Binary labels: scores at or above the ``1 - contamination`` quantile."""
    threshold = float(np.quantile(scores, 1.0 - contamination))
    return (scores >= threshold).astype(int)


def evaluate_scores(name: str, y_true: np.ndarray, scores: np.ndarray) -> RunResult:
    """ROC-AUC + PR-AUC of one detector's scores against ground truth."""
    return RunResult(
        name=name,
        metrics=[
            MetricResult("roc_auc", float(skm.roc_auc_score(y_true, scores)), split="test"),
            MetricResult(
                "pr_auc", float(skm.average_precision_score(y_true, scores)), split="test"
            ),
        ],
    )


def random_scores(n: int, seed: int) -> np.ndarray:
    """Seeded uniform-random scores — the reference baseline every detector
    must beat (expected ROC-AUC 0.5, PR-AUC ≈ prevalence)."""
    return np.random.default_rng(seed).random(n)


def add_random_baseline(
    runs: list[RunResult],
    scores_by_model: dict[str, np.ndarray],
    y_test: np.ndarray,
    config: AnomalyConfig,
) -> None:
    """Append the seeded random baseline and insert it first in the run order."""
    scores = random_scores(len(y_test), config.seed)
    run = evaluate_scores("random", y_test, scores)
    scores_by_model["random"] = scores
    runs.insert(0, run)
    roc = run.get("roc_auc")
    pr = run.get("pr_auc")
    assert roc is not None and pr is not None
    logger.info("random baseline roc_auc=%.4f pr_auc=%.4f", roc.value, pr.value)


def score_all(
    config: AnomalyConfig,
) -> tuple[list[RunResult], dict[str, np.ndarray], np.ndarray, np.ndarray]:
    """Score every persisted detector on the test window.

    Returns the per-model runs, the raw test scores per model, the ground
    truth labels, and the test timestamps (all aligned row-wise).
    """
    df = load_features(config)
    _, test = split_train_test(df, config.train_frac)
    x_test = feature_matrix(test, config)
    y_test = test["is_anomaly"].to_numpy().astype(int)
    ts = test["ts"].to_numpy()
    logger.info("scoring %d detectors on %d test rows", len(config.models), x_test.shape[0])

    runs: list[RunResult] = []
    scores_by_model: dict[str, np.ndarray] = {}
    for name in config.models:
        scores = anomaly_scores(load_model(name, config), name, x_test)
        run = evaluate_scores(name, y_test, scores)
        runs.append(run)
        scores_by_model[name] = scores
        roc = run.get("roc_auc")
        pr = run.get("pr_auc")
        assert roc is not None and pr is not None
        logger.info("%s roc_auc=%.4f pr_auc=%.4f", name, roc.value, pr.value)
    return runs, scores_by_model, y_test, ts


def best_model(runs: list[RunResult]) -> str:
    """Detector with the highest PR-AUC (ranking metric for rare anomalies)."""
    if not runs:
        raise ValueError("no runs to rank")

    def pr_auc(run: RunResult) -> float:
        metric = run.get("pr_auc")
        return metric.value if metric is not None else 0.0

    return max(runs, key=pr_auc).name


def roc_figure(
    runs: list[RunResult], scores_by_model: dict[str, np.ndarray], y_test: np.ndarray
) -> go.Figure:
    """ROC curves for all detectors overlaid with the chance diagonal."""
    fig = go.Figure()
    fig.add_scatter(
        x=[0, 1],
        y=[0, 1],
        mode="lines",
        name="chance",
        line={"dash": "dash", "color": "#64748b"},
    )
    for run in runs:
        fpr, tpr, _ = skm.roc_curve(y_test, scores_by_model[run.name])
        metric = run.get("roc_auc")
        assert metric is not None
        fig.add_scatter(x=fpr, y=tpr, mode="lines", name=f"{run.name} (AUC={metric.value:.3f})")
    fig.update_layout(title="ROC curves — test window", xaxis_title="FPR", yaxis_title="TPR")
    return apply_theme(fig)


def pr_figure(
    runs: list[RunResult], scores_by_model: dict[str, np.ndarray], y_test: np.ndarray
) -> go.Figure:
    """Precision-recall curves for all detectors with the prevalence baseline."""
    fig = go.Figure()
    baseline = float(np.mean(y_test))
    fig.add_scatter(
        x=[0, 1],
        y=[baseline, baseline],
        mode="lines",
        name=f"prevalence ({baseline:.3f})",
        line={"dash": "dash", "color": "#64748b"},
    )
    for run in runs:
        precision, recall, _ = skm.precision_recall_curve(y_test, scores_by_model[run.name])
        metric = run.get("pr_auc")
        assert metric is not None
        fig.add_scatter(
            x=recall, y=precision, mode="lines", name=f"{run.name} (AP={metric.value:.3f})"
        )
    fig.update_layout(
        title="PR curves — test window", xaxis_title="recall", yaxis_title="precision"
    )
    return apply_theme(fig)


def telemetry_figure(config: AnomalyConfig, scores: np.ndarray) -> go.Figure:
    """Test-window telemetry with the best model's flags marked.

    Ground-truth anomalies sit on a strip below the signal traces so the
    detector's flags can be eyeballed against them.
    """
    df = load_features(config)
    _, test = split_train_test(df, config.train_frac)
    ts = test["ts"].to_numpy()
    flags = predict_at_contamination(scores, config.contamination)
    y_true = test["is_anomaly"].to_numpy().astype(int)

    fig = go.Figure()
    for sig in SIGNALS:
        fig.add_scatter(x=ts, y=test[sig].to_numpy(), mode="lines", name=sig)
    flagged = flags == 1
    fig.add_scatter(
        x=ts[flagged],
        y=test["cpu"].to_numpy()[flagged],
        mode="markers",
        name="flagged (best model)",
        marker={"color": "#f472b6", "size": 7, "symbol": "x"},
    )
    truth = y_true == 1
    fig.add_scatter(
        x=ts[truth],
        y=np.full(int(truth.sum()), -8.0),
        mode="markers",
        name="ground truth anomaly",
        marker={"color": "#fbbf24", "size": 6},
    )
    fig.update_layout(
        title="Test window — telemetry with best-model anomaly flags",
        xaxis_title="time",
        yaxis_title="value",
    )
    return apply_theme(fig, height=620)


def eda_signals_overview(raw: pl.DataFrame, max_rows: int = 2_880) -> go.Figure:
    """Raw telemetry over an initial window with injected anomalies marked.

    Two days (2 880 minutes) of the prepared stream: the daily CPU/memory
    seasonality is visible, and latency spikes align with the injected
    anomalies (pink markers).
    """
    window = raw.head(max_rows)
    ts = window["ts"].to_numpy()
    fig = go.Figure()
    for sig in SIGNALS:
        fig.add_scatter(x=ts, y=window[sig].to_numpy(), mode="lines", name=sig)
    anom = window["is_anomaly"].to_numpy()
    fig.add_scatter(
        x=ts[anom],
        y=window["cpu"].to_numpy()[anom],
        mode="markers",
        name="injected anomaly",
        marker={"color": "#f472b6", "size": 7, "symbol": "x"},
    )
    fig.update_layout(
        title=f"Raw telemetry — first {window.height:,} minutes (synthetic, seeded)",
        xaxis_title="time",
        yaxis_title="value",
    )
    return apply_theme(fig, height=620)


def run_evaluation(config: AnomalyConfig) -> tuple[dict[str, dict[str, float]], Path]:
    """Full evaluate stage: runs, figures, HTML report, metrics.json, figure JSON."""
    runs, scores_by_model, y_test, _ = score_all(config)
    add_random_baseline(runs, scores_by_model, y_test, config)
    champion = best_model(runs)
    logger.info("best model by PR-AUC: %s", champion)

    figures = {
        "eda_signals_overview": eda_signals_overview(load_raw(config)),
        "roc_curves": roc_figure(runs, scores_by_model, y_test),
        "pr_curves": pr_figure(runs, scores_by_model, y_test),
        "telemetry_flags": telemetry_figure(config, scores_by_model[champion]),
    }
    builder = ReportBuilder(
        title="Evaluation — 03-anomaly-detection", figures_dir=config.figures_dir
    )
    for run in runs:
        builder.add_run(run)
    builder.build(config.eval_dir, figures=figures)
    for name, fig in figures.items():
        save_json(fig, config.figures_dir / f"{name}.json")
    logger.info("wrote %s/{metrics.json,report.html}", config.eval_dir)

    metrics = json.loads((config.eval_dir / "metrics.json").read_text())
    return metrics, config.eval_dir / "report.html"
