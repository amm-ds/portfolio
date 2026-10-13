"""Holdout evaluation: metrics via portfolio_eval, calibration (raw vs
isotonic), precision-recall and decision-curve analysis, and a business-cost
threshold sweep.

Run ladder (all on the same 1,000-row holdout, same FP=1/FN=5 cost model):
``naive_majority`` → ``logreg_threshold_0.5`` → ``logreg_threshold_<opt>``
(wave-2 pipeline) → ``selected_model`` → ``selected_model_calibrated``.
"""

import itertools
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import plotly.graph_objects as go
from numpy.typing import NDArray
from portfolio_core.plotting import add_takeaway, apply_theme, style_runs
from portfolio_eval.metrics import MetricResult, RunResult
from portfolio_eval.ml import classification_metrics
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_auc_score
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


def expected_calibration_error(
    y_true: NDArray[np.int64], proba: NDArray[np.float64], n_bins: int
) -> float:
    """ECE: bin-weighted |observed frequency - mean predicted probability|."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in itertools.pairwise(edges):
        mask = (proba >= lo) & (proba <= hi if hi == 1.0 else proba < hi)
        if not mask.any():
            continue
        ece += mask.mean() * abs(float(y_true[mask].mean()) - float(proba[mask].mean()))
    return float(ece)


def binned_calibration(
    y_true: NDArray[np.int64], proba: NDArray[np.float64], n_bins: int
) -> list[dict[str, float]]:
    """Binned reliability table (mean predicted vs observed per bin)."""
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows: list[dict[str, float]] = []
    for lo, hi in itertools.pairwise(edges):
        mask = (proba >= lo) & (proba <= hi if hi == 1.0 else proba < hi)
        if not mask.any():
            continue
        rows.append(
            {
                "bin_lo": float(lo),
                "bin_hi": float(hi),
                "n": int(mask.sum()),
                "mean_predicted": float(proba[mask].mean()),
                "observed": float(y_true[mask].mean()),
            }
        )
    return rows


def net_benefit(y_true: NDArray[np.int64], proba: NDArray[np.float64], pt: float) -> float:
    """Decision-curve net benefit at threshold probability pt (Vickers)."""
    n = len(y_true)
    pred = proba >= pt
    tp = float(np.sum(pred & (y_true == 1)))
    fp = float(np.sum(pred & (y_true == 0)))
    return tp / n - (fp / n) * (pt / (1.0 - pt))


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


def _selected_run(
    cfg: ChurnConfig, name: str, y_true: NDArray[np.int64], proba: NDArray[np.float64]
) -> tuple[RunResult, NDArray[np.float64], float]:
    """Selected-model run at its cost-optimal threshold, with ECE attached."""
    costs, optimal = cost_curve(cfg, y_true, proba)
    run = _holdout_run(cfg, name, y_true, proba, optimal)
    run.metrics.append(
        MetricResult(
            "ece",
            expected_calibration_error(y_true, proba, cfg.calibration_bins),
            higher_is_better=False,
        )
    )
    return run, costs, optimal


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def calibration_figure(
    cfg: ChurnConfig,
    y_true: NDArray[np.int64],
    proba_map: dict[str, NDArray[np.float64]],
) -> go.Figure:
    """Reliability diagram comparing raw vs isotonic-calibrated probabilities."""
    fig = go.Figure()
    fig.add_scatter(
        x=[0, 1],
        y=[0, 1],
        mode="lines",
        name="perfect calibration",
        line={"dash": "dash", "color": "#64748b"},
    )
    for name, proba in proba_map.items():
        frac_pos, mean_pred = calibration_curve(y_true, proba, n_bins=cfg.calibration_bins)
        ece = expected_calibration_error(y_true, proba, cfg.calibration_bins)
        fig.add_scatter(
            x=mean_pred,
            y=frac_pos,
            mode="lines+markers",
            name=f"{name} (ece={ece:.3f})",
        )
    fig.update_layout(
        title="Calibration: raw vs isotonic-calibrated (holdout)",
        xaxis_title="Mean predicted probability",
        yaxis_title="Observed churn frequency",
    )
    style_runs(fig, best="isotonic")
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
        title="Permutation importance — selected model (holdout, F1 decrease)",
        xaxis_title="Mean F1 decrease",
        yaxis_title="",
    )
    return apply_theme(fig)


def precision_recall_figure(
    cfg: ChurnConfig,
    y_true: NDArray[np.int64],
    proba_map: dict[str, NDArray[np.float64]],
    base_rate: float,
) -> go.Figure:
    """PR curves per candidate; the naive floor is the base-rate line."""
    fig = go.Figure()
    fig.add_scatter(
        x=[0, 1],
        y=[base_rate, base_rate],
        mode="lines",
        name="naive majority (base rate)",
        line={"dash": "dash", "color": "#64748b"},
    )
    for name, proba in proba_map.items():
        prec, rec, _ = precision_recall_curve(y_true, proba)
        fig.add_scatter(x=rec, y=prec, mode="lines", name=name)
    fig.update_layout(
        title="Precision-recall curves (holdout)",
        xaxis_title="Recall",
        yaxis_title="Precision",
    )
    style_runs(fig, best="selected model")
    return apply_theme(fig)


def decision_curve_figure(
    cfg: ChurnConfig,
    y_true: NDArray[np.int64],
    proba_map: dict[str, NDArray[np.float64]],
    base_rate: float,
) -> go.Figure:
    """Decision-curve analysis: net benefit vs threshold probability.

    References: treat-none (zero) and treat-all
    (base_rate - (1-base_rate)·pt/(1-pt)).
    """
    pt_grid = np.linspace(0.01, 0.9, 100)
    fig = go.Figure()
    fig.add_scatter(
        x=pt_grid,
        y=np.zeros_like(pt_grid),
        mode="lines",
        name="treat none",
        line={"dash": "dash", "color": "#64748b"},
    )
    treat_all = base_rate - (1.0 - base_rate) * pt_grid / (1.0 - pt_grid)
    fig.add_scatter(
        x=pt_grid, y=treat_all.tolist(), mode="lines", name="treat all", line={"dash": "dot"}
    )
    for name, proba in proba_map.items():
        nb = [net_benefit(y_true, proba, float(pt)) for pt in pt_grid]
        fig.add_scatter(x=pt_grid.tolist(), y=nb, mode="lines", name=name)
    fig.update_layout(
        title="Decision-curve analysis: net benefit vs threshold probability",
        xaxis_title="Threshold probability pt",
        yaxis_title="Net benefit (per customer)",
    )
    style_runs(fig, best="selected model")
    return apply_theme(fig)


def cost_figure(
    cfg: ChurnConfig,
    cost_map: dict[str, NDArray[np.float64]],
    opt_map: dict[str, float],
    takeaway: str,
) -> go.Figure:
    """Business cost vs threshold for each candidate; optima marked."""
    fig = go.Figure()
    for name, costs in cost_map.items():
        fig.add_scatter(x=list(cfg.threshold_grid), y=costs.tolist(), mode="lines", name=name)
        opt = opt_map[name]
        fig.add_scatter(
            x=[opt],
            y=[float(costs[int(np.argmin(costs))])],
            mode="markers",
            name=f"{name} optimum",
            marker={"size": 11, "symbol": "star"},
        )
    fig.update_layout(
        title=f"Business cost curve (FP={cfg.fp_cost:g}, FN={cfg.fn_cost:g})",
        xaxis_title="Decision threshold",
        yaxis_title=f"Total cost (FP·{cfg.fp_cost:g} + FN·{cfg.fn_cost:g})",
    )
    style_runs(fig, best="selected model")
    add_takeaway(fig, takeaway)
    return apply_theme(fig)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def evaluate_holdout(
    cfg: ChurnConfig,
    models: dict[str, Pipeline],
    X_test: pd.DataFrame,
    y_test: pd.Series,
    train_base_rate: float,
) -> tuple[list[RunResult], dict[str, go.Figure], dict[str, Any]]:
    """Full holdout evaluation: 5 runs + 6 figures + a numbers summary."""
    y_true = np.asarray(y_test, dtype=int)
    proba = {
        name: np.asarray(m.predict_proba(X_test)[:, 1], dtype=float) for name, m in models.items()
    }

    logreg_proba = proba["logreg"]
    _lg_costs, logreg_opt = cost_curve(cfg, y_true, logreg_proba)
    naive_run, naive_costs, naive_opt = naive_majority_run(cfg, y_true, train_base_rate)
    selected_run, selected_costs, selected_opt = _selected_run(
        cfg, "selected_model", y_true, proba["selected"]
    )
    calib_run, calib_costs, calib_opt = _selected_run(
        cfg, "selected_model_calibrated", y_true, proba["selected_calibrated"]
    )
    runs = [
        naive_run,
        _holdout_run(cfg, "logreg_threshold_0.5", y_true, logreg_proba, DEFAULT_THRESHOLD),
        _holdout_run(cfg, f"logreg_threshold_{logreg_opt:.3f}", y_true, logreg_proba, logreg_opt),
        selected_run,
        calib_run,
    ]

    def _cost(run: RunResult) -> float:
        m = run.get("business_cost")
        return m.value if m else float("nan")

    def _ece(run: RunResult) -> float:
        m = run.get("ece")
        return m.value if m else float("nan")

    summary: dict[str, Any] = {
        "naive_cost": _cost(naive_run),
        "logreg_default_cost": _cost(runs[1]),
        "logreg_tuned_cost": _cost(runs[2]),
        "logreg_opt": logreg_opt,
        "selected_cost": _cost(selected_run),
        "selected_opt": selected_opt,
        "selected_ece": _ece(selected_run),
        "calibrated_cost": _cost(calib_run),
        "calibrated_opt": calib_opt,
        "calibrated_ece": _ece(calib_run),
        "calibration_helps": _cost(calib_run) < _cost(selected_run),
        "base_rate": train_base_rate,
    }
    naive_total = _cost(naive_run)
    savings = naive_total - _cost(selected_run)
    takeaway = (
        f"Selected model at t={selected_opt:.3f} costs {_cost(selected_run):.0f} vs naive "
        f"{naive_total:.0f} (-{100 * savings / naive_total:.1f}%); isotonic variant "
        f"{_cost(calib_run):.0f}."
    )
    figures = {
        "calibration_curve": calibration_figure(
            cfg,
            y_true,
            {
                "selected model (raw)": proba["selected"],
                "selected model isotonic": proba["selected_calibrated"],
            },
        ),
        "permutation_importance": importance_figure(cfg, models["selected"], X_test, y_test),
        "precision_recall_curve": precision_recall_figure(
            cfg,
            y_true,
            {
                "logreg wave-2": logreg_proba,
                "selected model": proba["selected"],
                "selected model isotonic": proba["selected_calibrated"],
            },
            train_base_rate,
        ),
        "decision_curve": decision_curve_figure(
            cfg,
            y_true,
            {
                "selected model": proba["selected"],
                "selected model isotonic": proba["selected_calibrated"],
            },
            train_base_rate,
        ),
        "business_cost_curve": cost_figure(
            cfg,
            {
                "naive majority": naive_costs,
                "selected model": selected_costs,
                "selected model isotonic": calib_costs,
            },
            {
                "naive majority": naive_opt,
                "selected model": selected_opt,
                "selected model isotonic": calib_opt,
            },
            takeaway,
        ),
    }
    return runs, figures, summary


def artifact_paths(cfg: ChurnConfig) -> dict[str, Path]:
    """Canonical locations of persisted model artifacts and the holdout frame."""
    return {
        "logreg": cfg.data_dir / "model.pkl",
        "selected": cfg.data_dir / "selected_model.pkl",
        "selected_calibrated": cfg.data_dir / "selected_model_calibrated.pkl",
        "holdout": cfg.data_dir / "holdout.parquet",
    }
