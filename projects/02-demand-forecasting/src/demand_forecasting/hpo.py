"""Optuna HPO for the production HGB config (wave 3).

The objective is the pooled-CV mean MAE over the *same* date-aligned
expanding-window folds used by the honest backtest (shared via
:func:`demand_forecasting.evaluate.cv_row_folds`), so hyperparameters are
selected under the exact evaluation protocol they will be judged by.

Determinism: seeded TPE sampler + seeded estimator random_state; the best
params land in ``data/hpo_best.json`` and are mirrored into
``ForecastConfig.hgb_tuned`` defaults + ``params.yaml`` (production config).
"""

import json
from collections.abc import Callable
from pathlib import Path

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

# search space (see DESIGN.md): deliberately bounded so ~50 pruned trials
# finish in minutes on CPU
SPACE: dict[str, tuple[str, tuple[float | int, ...]]] = {
    "learning_rate": ("float", (0.02, 0.3)),
    "max_iter": ("int", (60, 200)),
    "max_leaf_nodes": ("int", (7, 63)),
    "min_samples_leaf": ("int", (10, 100)),
    "l2_regularization": ("float", (1e-8, 10.0)),
    "max_features": ("float", (0.5, 1.0)),
}
LOG_SCALE = {"learning_rate", "l2_regularization"}


def suggest_params(trial: optuna.Trial) -> dict[str, float | int]:
    """Sample one point from the HGB search space."""
    params: dict[str, float | int] = {}
    for name, (kind, bounds) in SPACE.items():
        lo, hi = bounds
        if kind == "int":
            params[name] = trial.suggest_int(name, int(lo), int(hi))
        else:
            params[name] = trial.suggest_float(name, float(lo), float(hi), log=name in LOG_SCALE)
    return params


def _hgb_design_matrix(
    features: pl.DataFrame, config: ForecastConfig
) -> tuple[np.ndarray, np.ndarray]:
    """Numeric+lag+one-hot(series) matrix, identical to the backtest's hgb input."""
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
    features: pl.DataFrame, config: ForecastConfig, seed: int
) -> Callable[[optuna.Trial], float]:
    """Build the CV-mean-MAE objective with per-fold median pruning."""
    x, y = _hgb_design_matrix(features, config)
    folds = cv_row_folds(features, config)

    def objective(trial: optuna.Trial) -> float:
        params = suggest_params(trial)
        maes = []
        for k, (train_rows, val_rows) in enumerate(folds):
            model = HistGradientBoostingRegressor(random_state=seed, **params)
            model.fit(x[train_rows], y[train_rows])
            mae = float(np.mean(np.abs(y[val_rows] - model.predict(x[val_rows]))))
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
    fig.update_layout(title="HPO optimization history (CV mean MAE)", xaxis_title="trial")
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
    fig.add_bar(x=[importances[n] for n in names], y=names, orientation="h", name="importance")
    fig.update_layout(title="HPO hyperparameter importance")
    return apply_theme(fig)


def run_hpo(
    settings: DemandSettings, config: ForecastConfig, n_trials: int | None = None
) -> optuna.Study:
    """Run the seeded HPO study; persist best params + figures.

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
        study_name="hgb",
        storage=storage,
        load_if_exists=True,
    )

    def _checkpoint(study_: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        """Best-so-far params to disk after every trial (crash-safe)."""
        if study_.best_trial is None:
            return
        best = dict(study_.best_params)
        best["random_state"] = settings.seed
        out = {
            "best_params": best,
            "best_cv_mae": float(study_.best_value),
            "n_trials": len(study_.trials),
            "seed": settings.seed,
        }
        path = settings.data_dir / "hpo_best.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2))

    logger.info(
        "HPO: %d new trials (study has %d so far), seed=%d",
        n,
        len(study.trials),
        settings.seed,
    )
    study.optimize(
        make_objective(features, config, settings.seed), n_trials=n, callbacks=[_checkpoint]
    )

    best = dict(study.best_params)
    best["random_state"] = settings.seed
    out = {
        "best_params": best,
        "best_cv_mae": float(study.best_value),
        "n_trials": len(study.trials),
        "seed": settings.seed,
    }
    path = settings.data_dir / "hpo_best.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    logger.info("HPO best CV MAE=%.4f params=%s -> %s", study.best_value, best, path)

    figs = {
        "hpo_history": figure_hpo_history(study),
        "hpo_importance": figure_hpo_importance(study),
    }
    for name, fig in figs.items():
        save_html(fig, Path(settings.reports_dir) / "figures" / f"{name}.html")
        save_json(fig, Path(settings.reports_dir) / "figures" / f"{name}.json")
    logger.info("HPO figures -> %s", settings.reports_dir / "figures")
    return study
