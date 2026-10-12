"""Holdout evaluation: metrics via portfolio_eval, calibration, permutation
importance, and a business-cost threshold sweep.

Three ``RunResult`` rows are produced: a naive majority baseline (constant
probability = training base rate), the fitted model at the default 0.5
threshold, and the fitted model at the cost-optimal threshold — so the
metrics table quantifies both the value of modeling and of threshold tuning.
"""

from pathlib import Path

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import plotly.graph_objects as go
from numpy.typing import NDArray
from portfolio_core.plotting import apply_theme
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.ml import classification_metrics
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.pipeline import Pipeline

from churn_pipeline.config import ChurnConfig

DEFAULT_THRESHOLD = 0.5


def business_cost(
    y_true: NDArray[np.int64],
    proba: NDArray[np.float64],
    threshold: float,
    fp_cost: float,
    fn_cost: float,
) -> float:
    """Cost = fp_cost·FP + fn_cost·FN at one decision threshold."""
    y_pred = (proba >= threshold).astype(int)
    _tn, fp, fn, _tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return fp_cost * float(fp) + fn_cost * float(fn)


def cost_curve(
    cfg: ChurnConfig, y_true: NDArray[np.int64], proba: NDArray[np.float64]
) -> tuple[NDArray[np.float64], float]:
    """Total business cost across the threshold grid; returns (costs, optimum)."""
    costs = np.array(
        [business_cost(y_true, proba, t, cfg.fp_cost, cfg.fn_cost) for t in cfg.threshold_grid],
        dtype=float,
    )
    return costs, float(cfg.threshold_grid[int(np.argmin(costs))])


def naive_majority_run(
    cfg: ChurnConfig, y_true: NDArray[np.int64], base_rate: float
) -> tuple[RunResult, NDArray[np.float64], float]:
    """Naive baseline: constant probability = training churn base rate.

    On the cost curve this degenerates to two flat regimes (alarm-everyone
    below the base rate, ignore-everyone above); its reported metrics are at
    whichever regime is cheaper. Returns (run, costs, optimal threshold).
    """
    proba = np.full(len(y_true), base_rate, dtype=float)
    costs, optimal = cost_curve(cfg, y_true, proba)
    y_pred = (proba >= optimal).astype(int)
    metrics = [
        MetricResult("roc_auc", 0.5),
        *classification_metrics(list(y_true), [int(p) for p in y_pred]),
        MetricResult(
            "business_cost",
            business_cost(y_true, proba, optimal, cfg.fp_cost, cfg.fn_cost),
            higher_is_better=False,
        ),
    ]
    return RunResult(name="naive_majority", metrics=metrics), costs, optimal


def _holdout_run(
    cfg: ChurnConfig,
    name: str,
    y_true: NDArray[np.int64],
    proba: NDArray[np.float64],
    threshold: float,
) -> RunResult:
    """One RunResult: ROC-AUC + portfolio_eval classification metrics + cost."""
    y_pred = (proba >= threshold).astype(int)
    metrics = [
        MetricResult("roc_auc", float(roc_auc_score(y_true, proba))),
        *classification_metrics(list(y_true), [int(p) for p in y_pred]),
        MetricResult(
            "business_cost",
            business_cost(y_true, proba, threshold, cfg.fp_cost, cfg.fn_cost),
            higher_is_better=False,
        ),
    ]
    return RunResult(name=name, metrics=metrics)


def calibration_figure(
    cfg: ChurnConfig, y_true: NDArray[np.int64], proba: NDArray[np.float64]
) -> go.Figure:
    """Reliability diagram (10 bins): predicted mean vs observed frequency."""
    frac_pos, mean_pred = calibration_curve(y_true, proba, n_bins=cfg.calibration_bins)
    fig = go.Figure()
    fig.add_scatter(
        x=[0, 1],
        y=[0, 1],
        mode="lines",
        name="perfect calibration",
        line={"dash": "dash", "color": "#64748b"},
    )
    fig.add_scatter(
        x=mean_pred, y=frac_pos, mode="lines+markers", name="model", line={"color": "#2dd4bf"}
    )
    fig.update_layout(
        title="Calibration curve (holdout)",
        xaxis_title="Mean predicted probability",
        yaxis_title="Observed churn frequency",
    )
    return apply_theme(fig)


def importance_figure(
    cfg: ChurnConfig, model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series
) -> go.Figure:
    """Permutation importance (holdout F1, 5 repeats) as a sorted bar chart.

    ``permutation_importance`` permutes the *raw input columns*, so labels are
    the pipeline's input feature names, not the transformed space.
    """
    result = permutation_importance(
        model, X_test, y_test, scoring="f1", n_repeats=5, random_state=cfg.seed
    )
    names = [str(c) for c in model.feature_names_in_]
    order = np.argsort(result.importances_mean)
    fig = go.Figure()
    fig.add_bar(
        x=result.importances_mean[order],
        y=[names[i] for i in order],
        orientation="h",
        error_x={"type": "data", "array": result.importances_std[order]},
        marker={"color": "#38bdf8"},
    )
    fig.update_layout(
        title="Permutation importance (holdout, F1 decrease)",
        xaxis_title="Mean F1 decrease",
        yaxis_title="",
    )
    return apply_theme(fig)


def cost_figure(
    cfg: ChurnConfig,
    costs: NDArray[np.float64],
    optimal: float,
    naive_costs: NDArray[np.float64] | None = None,
    naive_optimal: float | None = None,
) -> go.Figure:
    """Business cost vs decision threshold; optima of model and naive marked."""
    fig = go.Figure()
    fig.add_scatter(
        x=list(cfg.threshold_grid),
        y=costs.tolist(),
        mode="lines",
        name="logistic model",
        line={"color": "#f472b6"},
    )
    opt_cost = float(costs[int(np.argmin(costs))])
    fig.add_scatter(
        x=[optimal],
        y=[opt_cost],
        mode="markers",
        name=f"model optimum t={optimal:.3f}",
        marker={"size": 12, "symbol": "star", "color": "#fbbf24"},
    )
    if naive_costs is not None:
        fig.add_scatter(
            x=list(cfg.threshold_grid),
            y=naive_costs.tolist(),
            mode="lines",
            name="naive majority",
            line={"dash": "dot", "color": "#64748b"},
        )
        n_opt = float(naive_costs[int(np.argmin(naive_costs))])
        fig.add_scatter(
            x=[naive_optimal],
            y=[n_opt],
            mode="markers",
            name=f"naive optimum t={naive_optimal:.3f}",
            marker={"size": 12, "symbol": "x", "color": "#94a3b8"},
        )
    fig.update_layout(
        title=f"Business cost curve (FP={cfg.fp_cost:g}, FN={cfg.fn_cost:g})",
        xaxis_title="Decision threshold",
        yaxis_title=f"Total cost (FP·{cfg.fp_cost:g} + FN·{cfg.fn_cost:g})",
    )
    return apply_theme(fig)


def evaluate_holdout(
    cfg: ChurnConfig,
    model: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    train_base_rate: float,
) -> tuple[list[RunResult], dict[str, go.Figure], float]:
    """Full holdout evaluation: naive + 2 model runs (0.5 vs tuned) + 3 figures."""
    y_true = np.asarray(y_test, dtype=int)
    proba = np.asarray(model.predict_proba(X_test)[:, 1], dtype=float)

    costs, optimal = cost_curve(cfg, y_true, proba)
    naive_run, naive_costs, naive_opt = naive_majority_run(cfg, y_true, train_base_rate)
    runs = [
        naive_run,
        _holdout_run(cfg, "logreg_threshold_0.5", y_true, proba, DEFAULT_THRESHOLD),
        _holdout_run(cfg, f"logreg_threshold_{optimal:.3f}", y_true, proba, optimal),
    ]
    figures = {
        "calibration_curve": calibration_figure(cfg, y_true, proba),
        "permutation_importance": importance_figure(cfg, model, X_test, y_test),
        "business_cost_curve": cost_figure(cfg, costs, optimal, naive_costs, naive_opt),
    }
    return runs, figures, optimal


def artifact_paths(cfg: ChurnConfig) -> tuple[Path, Path]:
    """Canonical locations of the persisted model and holdout frame."""
    return cfg.data_dir / "model.pkl", cfg.data_dir / "holdout.parquet"
