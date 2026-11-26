"""LightGBM training for the served model — vendored from experiment 12's v2 recipe.

Determinism contract (12's): every fit is seeded; LightGBM runs single-threaded
with ``deterministic=True`` (histogram order otherwise varies the model); the
Optuna sampler is seeded. The same seed must reproduce the same metrics — the
train stage's reproduction gate holds this package to 12's committed v2 MAE.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import optuna
import pandas as pd
from lightgbm import LGBMRegressor, early_stopping, log_evaluation

from model_serving.config import ServingConfig

optuna.logging.set_verbosity(optuna.logging.WARNING)

_LGBM_FIXED: dict[str, Any] = {
    "objective": "regression",
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
    "verbosity": -1,
}

_INT_PARAMS = {"num_leaves", "max_depth", "min_child_samples"}


@dataclass
class HPOOutcome:
    """What the HPO study found, serialized into the train-run record."""

    best_params: dict[str, float]
    n_trials: int
    best_val_mae: float
    time_budget_s: int
    trial_cap: int


def lgbm_estimator(cfg: ServingConfig, seed: int, **params: float) -> LGBMRegressor:
    """LightGBM with the fixed determinism knobs plus HPO-chosen params."""
    converted: dict[str, Any] = {
        k: (int(v) if k in _INT_PARAMS else float(v)) for k, v in params.items()
    }
    return LGBMRegressor(
        n_estimators=cfg.lgbm.n_estimators,
        random_state=seed,
        **_LGBM_FIXED,
        **converted,
    )


def _fit_lgbm(
    cfg: ServingConfig,
    model: LGBMRegressor,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> LGBMRegressor:
    """Fit with early stopping on the validation window (LightGBM 4.7 API)."""
    model.fit(
        X_train,
        y_train,
        eval_X=X_val,
        eval_y=y_val,
        eval_metric="mae",
        callbacks=[early_stopping(cfg.lgbm.early_stopping, verbose=False), log_evaluation(0)],
    )
    return model


def _lgbm_search_space(trial: optuna.Trial) -> dict[str, float]:
    return {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 15, 255),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
        "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
    }


def run_hpo(
    cfg: ServingConfig,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
) -> HPOOutcome:
    """Seeded Optuna study: LightGBM hyperparameters, MAE on validation, both a
    trial cap and a wall-clock budget (whichever binds first)."""

    def objective(trial: optuna.Trial) -> float:
        model = lgbm_estimator(cfg, cfg.seed, **_lgbm_search_space(trial))
        _fit_lgbm(cfg, model, X_train, y_train, X_val, y_val)
        return float(np.mean(np.abs(y_val - model.predict(X_val))))

    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=cfg.seed),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=8),
    )
    study.optimize(
        objective,
        n_trials=cfg.lgbm.hpo_trials,
        timeout=cfg.lgbm.hpo_time_budget_s,
        show_progress_bar=False,
    )
    best = study.best_params
    return HPOOutcome(
        best_params={k: float(v) for k, v in best.items()},
        n_trials=len(study.trials),
        best_val_mae=float(study.best_value),
        time_budget_s=cfg.lgbm.hpo_time_budget_s,
        trial_cap=cfg.lgbm.hpo_trials,
    )


def train_lgbm_final(
    cfg: ServingConfig,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    params: dict[str, float],
) -> LGBMRegressor:
    """Refit the winning config on train with early stopping on validation."""
    model = lgbm_estimator(cfg, cfg.seed, **params)
    return _fit_lgbm(cfg, model, X_train, y_train, X_val, y_val)
