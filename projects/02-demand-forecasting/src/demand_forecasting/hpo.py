"""Optuna HPO for the production booster configs (HGB / XGBoost / LightGBM).

The objective is the pooled-CV mean MAE over the *same* date-aligned
expanding-window folds used by the honest backtest (shared via
:func:`demand_forecasting.evaluate.cv_row_folds`), so hyperparameters are
selected under the exact evaluation protocol they will be judged by.

Determinism: seeded TPE sampler + seeded estimator random_state (LightGBM also
gets ``deterministic=True``); the best params land in ``data/hpo_best.json``
(hgb) or ``data/hpo_best_{model}.json`` and are mirrored into
``ForecastConfig`` defaults + ``params.yaml`` (production config). The study
lives in a resumable SQLite storage with per-trial checkpointing.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import optuna
import plotly.graph_objects as go
import polars as pl
from portfolio_core.logging import get_logger
from portfolio_core.plotting import apply_theme, save_html, save_json
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import OneHotEncoder

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.evaluate import cv_row_folds
from demand_forecasting.model import NUMERIC_FEATURES, model_specs, to_xy

logger = get_logger(__name__)

# per-arm search spaces (see DESIGN.md): bounded so ~25-50 pruned trials
# finish in minutes on CPU
SPACES: dict[str, dict[str, tuple[str, tuple[float | int, ...]]]] = {
    "hgb": {
        "learning_rate": ("float", (0.02, 0.3)),
        "max_iter": ("int", (60, 200)),
        "max_leaf_nodes": ("int", (7, 63)),
        "min_samples_leaf": ("int", (10, 100)),
        "l2_regularization": ("float", (1e-8, 10.0)),
        "max_features": ("float", (0.5, 1.0)),
    },
    "xgb": {
        "learning_rate": ("float", (0.01, 0.3)),
        "n_estimators": ("int", (50, 600)),
        "max_depth": ("int", (3, 12)),
        "subsample": ("float", (0.5, 1.0)),
        "colsample_bytree": ("float", (0.5, 1.0)),
        "reg_lambda": ("float", (1e-8, 100.0)),
    },
    "lgbm": {
        "learning_rate": ("float", (0.01, 0.3)),
        "n_estimators": ("int", (50, 600)),
        "num_leaves": ("int", (7, 127)),
        "min_child_samples": ("int", (5, 200)),
        "reg_lambda": ("float", (1e-8, 100.0)),
    },
}
LOG_SCALE: dict[str, set[str]] = {
    "hgb": {"learning_rate", "l2_regularization"},
    "xgb": {"learning_rate", "reg_lambda"},
    "lgbm": {"learning_rate", "reg_lambda"},
}


def suggest_params(trial: optuna.Trial, model: str) -> dict[str, float | int]:
    """Sample one point from the given arm's search space."""
    params: dict[str, float | int] = {}
    for name, (kind, bounds) in SPACES[model].items():
        lo, hi = bounds
        if kind == "int":
            params[name] = trial.suggest_int(name, int(lo), int(hi))
        else:
            params[name] = trial.suggest_float(
                name, float(lo), float(hi), log=name in LOG_SCALE[model]
            )
    return params


def make_estimator(model: str, params: dict[str, Any], seed: int) -> Any:
    """Seeded, deterministic estimator instance for the arm."""
    if model == "hgb":
        return HistGradientBoostingRegressor(random_state=seed, **params)
    if model == "xgb":
        from xgboost import XGBRegressor

        return XGBRegressor(random_state=seed, tree_method="hist", **params)
    if model == "lgbm":
        from lightgbm import LGBMRegressor

        return LGBMRegressor(random_state=seed, deterministic=True, verbosity=-1, **params)
    raise ValueError(f"unknown booster arm: {model}")  # pragma: no cover


def _design_matrix(features: pl.DataFrame, config: ForecastConfig) -> tuple[np.ndarray, np.ndarray]:
    """Numeric+lag+one-hot(series) matrix, identical to the backtest's input."""
    spec = next(s for s in model_specs() if s.name == "hgb")
    x_raw, y, _, _ = to_xy(features, config, spec)
    n_num = len(NUMERIC_FEATURES) + len(config.lags)
    pre = ColumnTransformer(
        [
            ("num", "passthrough", list(range(n_num))),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), [n_num]),
        ]
    )
    x = pre.fit_transform(x_raw)  # series ids are known entities, not target info
    return np.asarray(x, dtype=float), y


def make_objective(
    features: pl.DataFrame, config: ForecastConfig, seed: int, model: str = "hgb"
) -> Callable[[optuna.Trial], float]:
    """Build the CV-mean-MAE objective with per-fold median pruning."""
    x, y = _design_matrix(features, config)
    folds = cv_row_folds(features, config)

    def objective(trial: optuna.Trial) -> float:
        params = suggest_params(trial, model)
        maes = []
        for k, (train_rows, val_rows) in enumerate(folds):
            estimator = make_estimator(model, params, seed)
            estimator.fit(x[train_rows], y[train_rows])
            mae = float(np.mean(np.abs(y[val_rows] - estimator.predict(x[val_rows]))))
            maes.append(mae)
            trial.report(mae, k)
            if trial.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(maes))

    return objective


def figure_hpo_history(study: optuna.Study) -> go.Figure:
    """Optimization history: completed trials + the running best (feasible)."""
    trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    values = [float(t.value) for t in trials if t.value is not None]
    numbers = [t.number for t in trials if t.value is not None]
    fig = go.Figure()
    fig.add_scatter(x=numbers, y=values, name="trial MAE", mode="markers")
    best, bests = float("inf"), []
    for v in values:
        best = min(best, v)
        bests.append(best)
    fig.add_scatter(x=numbers, y=bests, name="best so far", mode="lines")
    fig.update_layout(
        title=(
            f"{len(trials)} seeded trials buy a modest, real gain - best CV "
            f"MAE {best:.3f}, converging on regularised small trees"
        ),
        xaxis_title="trial",
    )
    return apply_theme(fig)


def figure_hpo_importance(study: optuna.Study) -> go.Figure:
    """Hyperparameter importance (variance-based fANOVA fallback to frequency)."""
    try:
        importances = optuna.importance.get_param_importances(study)
    except (RuntimeError, ValueError):
        counts: dict[str, int] = {}
        for t in study.trials:
            for d in t.distributions:
                counts[d] = counts.get(d, 0) + 1
        importances = {k: float(v) for k, v in counts.items()}
    fig = go.Figure()
    names = list(importances)
    fig.add_bar(
        x=[importances[n] for n in names],
        y=names,
        orientation="h",
        name="importance",
        showlegend=False,  # single trace → no "importance" chip over the title
    )
    top2 = sum(sorted(importances.values(), reverse=True)[:2])
    fig.update_layout(
        title=(
            f"Regularisation knobs dominate - top two params carry {top2:.0%} "
            "of the search importance"
        ),
        # Horizontal bars put the parameter names on the y-axis; the theme's
        # 60 px left margin trims them ("min_samples_leaf" → "ples_leaf").
        # automargin sizes the margin to the longest tick label instead.
        yaxis={"automargin": True},
        margin={"l": 60, "r": 30, "t": 60, "b": 50},
    )
    return apply_theme(fig)


def run_hpo(
    settings: DemandSettings,
    config: ForecastConfig,
    model: str = "hgb",
    n_trials: int | None = None,
) -> optuna.Study:
    """Run the seeded HPO study for one booster arm; persist best params + figures.

    The study lives in a SQLite storage under ``data/`` so interrupted runs
    resume where they left off (``cli hpo`` is safe to re-invoke), and a
    per-trial callback checkpoints the best params so any partial run still
    leaves a usable production config.
    """
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    features = pl.read_parquet(settings.data_dir / "features.parquet")
    n = n_trials or config.hpo_n_trials
    sampler = optuna.samplers.TPESampler(seed=settings.seed)
    pruner = optuna.pruners.MedianPruner(n_startup_trials=4, n_warmup_steps=1)
    storage_path = settings.data_dir / "hpo_study.db"
    storage = f"sqlite:///{storage_path}"
    study = optuna.create_study(
        direction="minimize",
        sampler=sampler,
        pruner=pruner,
        study_name=model,
        storage=storage,
        load_if_exists=True,
    )

    def _checkpoint(study_: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        """Best-so-far params to disk after every trial (crash-safe)."""
        if study_.best_trial is None:
            return
        best = dict(study_.best_params)
        out = {
            "best_params": best,
            "best_cv_mae": float(study_.best_value),
            "n_trials": len(study_.trials),
            "seed": settings.seed,
            "model": model,
        }
        path = settings.data_dir / ("hpo_best.json" if model == "hgb" else f"hpo_best_{model}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2))

    logger.info(
        "HPO[%s]: %d new trials (study has %d so far), seed=%d",
        model,
        n,
        len(study.trials),
        settings.seed,
    )
    study.optimize(
        make_objective(features, config, settings.seed, model),
        n_trials=n,
        callbacks=[_checkpoint],
    )

    best = dict(study.best_params)
    out = {
        "best_params": best,
        "best_cv_mae": float(study.best_value),
        "n_trials": len(study.trials),
        "seed": settings.seed,
        "model": model,
    }
    path = settings.data_dir / ("hpo_best.json" if model == "hgb" else f"hpo_best_{model}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    logger.info("HPO[%s] best CV MAE=%.4f params=%s -> %s", model, study.best_value, best, path)

    suffix = "" if model == "hgb" else f"_{model}"
    figs = {
        f"hpo_history{suffix}": figure_hpo_history(study),
        f"hpo_importance{suffix}": figure_hpo_importance(study),
    }
    for name, fig in figs.items():
        save_html(fig, Path(settings.reports_dir) / "figures" / f"{name}.html")
        save_json(fig, Path(settings.reports_dir) / "figures" / f"{name}.json")
    logger.info("HPO[%s] figures -> %s", model, settings.reports_dir / "figures")
    return study
