"""Hyperparameter optimisation (Optuna) for the three detector families.

Each family gets a seeded TPE study (~30 trials, median pruning on a cheap
first phase) maximising PR-AUC on a validation window carved from the *end of
the train window* — the test window stays untouched until final evaluation.
The tuned detectors are then refit on the full train window and persisted
next to per-study artifacts (best params, importances, trial history) that the
evaluate stage turns into figures.

LOF tuning uses a novelty-mode estimator (``decision_function`` works out of
the box for validation scoring); the final tuned LOF is refit with
``novelty=False`` on the full train window so test scoring reuses the wave-2
``fit_predict``/local-reachability replication unchanged.
"""

import json
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
import optuna
from portfolio_core.logging import get_logger
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM

from anomaly_detection.config import AnomalyConfig

logger = get_logger(__name__)

optuna.logging.set_verbosity(optuna.logging.WARNING)


def suggest_isolation_forest(trial: optuna.Trial) -> dict[str, Any]:
    """Search space: tree count, row/feature subsampling."""
    return {
        "n_estimators": trial.suggest_int("n_estimators", 100, 600),
        "max_samples": trial.suggest_float("max_samples", 0.1, 1.0),
        "max_features": trial.suggest_float("max_features", 0.3, 1.0),
        "fit_rows": trial.suggest_float("fit_rows", 0.3, 1.0),
    }


def suggest_lof(trial: optuna.Trial) -> dict[str, Any]:
    """Search space: neighborhood size."""
    return {"n_neighbors": trial.suggest_int("n_neighbors", 5, 200)}


def suggest_ocsvm(trial: optuna.Trial) -> dict[str, Any]:
    """Search space: nu (log) and RBF gamma (log, absolute value)."""
    return {
        "nu": trial.suggest_float("nu", 0.005, 0.2, log=True),
        "gamma": trial.suggest_float("gamma", 1e-4, 5e-1, log=True),
    }


SEARCH_SPACES: dict[str, Any] = {
    "isolation_forest": suggest_isolation_forest,
    "lof": suggest_lof,
    "ocsvm": suggest_ocsvm,
}


def _row_subset(x: np.ndarray, frac: float, seed: int) -> np.ndarray:
    """Deterministic row subsample (fraction of rows, at least 100 rows)."""
    n = max(100, int(x.shape[0] * frac))
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(x.shape[0], size=n, replace=False))
    return x[idx]


def _val_scores(model: Any, x_val: np.ndarray) -> np.ndarray:
    """Higher = more anomalous, mirroring the evaluate-stage convention."""
    return -np.asarray(model.decision_function(x_val), dtype=float)


def make_objective(
    name: str,
    x_fit: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    config: AnomalyConfig,
) -> Any:
    """Objective factory: PR-AUC on the validation window with 2-phase pruning.

    Phase 0 fits on a cheap subset and reports an intermediate value so the
    median pruner can discard unpromising trials before the full fit.
    """

    def objective(trial: optuna.Trial) -> float:
        params = SEARCH_SPACES[name](trial)
        if name == "isolation_forest":
            fit_rows = params.pop("fit_rows")

            def build(rows: np.ndarray) -> IsolationForest:
                return IsolationForest(
                    n_estimators=params["n_estimators"],
                    max_samples=params["max_samples"],
                    max_features=params["max_features"],
                    contamination=config.contamination,
                    random_state=config.seed,
                    n_jobs=-1,
                ).fit(rows)

            cheap = build(_row_subset(x_fit, fit_rows * 0.5, config.seed + trial.number))
            trial.report(float(average_precision_score(y_val, _val_scores(cheap, x_val))), 0)
            if trial.should_prune():
                raise optuna.TrialPruned()
            full = build(_row_subset(x_fit, fit_rows, config.seed + trial.number))
            return float(average_precision_score(y_val, _val_scores(full, x_val)))

        if name == "lof":

            def build(rows: np.ndarray) -> LocalOutlierFactor:
                return LocalOutlierFactor(n_neighbors=params["n_neighbors"], novelty=True).fit(rows)

            cheap = build(_row_subset(x_fit, 0.5, config.seed + trial.number))
            trial.report(float(average_precision_score(y_val, _val_scores(cheap, x_val))), 0)
            if trial.should_prune():
                raise optuna.TrialPruned()
            full = build(x_fit)
            return float(average_precision_score(y_val, _val_scores(full, x_val)))

        if name == "ocsvm":

            def build(rows: np.ndarray) -> OneClassSVM:
                return OneClassSVM(kernel="rbf", nu=params["nu"], gamma=params["gamma"]).fit(rows)

            cheap = build(_row_subset(x_fit, 0.5, config.seed + trial.number))
            trial.report(float(average_precision_score(y_val, _val_scores(cheap, x_val))), 0)
            if trial.should_prune():
                raise optuna.TrialPruned()
            full = build(x_fit)
            return float(average_precision_score(y_val, _val_scores(full, x_val)))

        raise ValueError(f"unknown family {name!r}")

    return objective


def tune_family(
    name: str,
    x_fit: np.ndarray,
    y_fit: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    config: AnomalyConfig,
    n_trials: int | None = None,
) -> optuna.Study:
    """Run one seeded TPE study for a detector family and return it."""
    study = optuna.create_study(
        direction="maximize",
        study_name=f"{name}_hpo",
        sampler=optuna.samplers.TPESampler(seed=config.seed),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=8),
    )
    study.optimize(
        make_objective(name, x_fit, x_val, y_val, config),
        n_trials=n_trials or config.hpo_trials,
        show_progress_bar=False,
    )
    return study


def fit_tuned(
    name: str, best_params: dict[str, Any], x_train: np.ndarray, config: AnomalyConfig
) -> Any:
    """Refit the best configuration on the full train window.

    LOF returns to ``novelty=False`` (``fit_predict`` per spec) so the
    evaluate stage scores it with the wave-2 local-reachability replication.
    """
    if name == "isolation_forest":
        rows = _row_subset(x_train, float(best_params.get("fit_rows", 1.0)), config.seed)
        model = IsolationForest(
            n_estimators=int(best_params["n_estimators"]),
            max_samples=float(best_params["max_samples"]),
            max_features=float(best_params["max_features"]),
            contamination=config.contamination,
            random_state=config.seed,
            n_jobs=-1,
        )
        model.fit(rows)
        return model
    if name == "lof":
        model = LocalOutlierFactor(
            n_neighbors=int(best_params["n_neighbors"]),
            contamination=config.contamination,
            novelty=False,
        )
        model.fit_predict(x_train)
        return model
    if name == "ocsvm":
        return OneClassSVM(
            kernel="rbf",
            nu=float(best_params["nu"]),
            gamma=float(best_params["gamma"]),
        ).fit(x_train)
    raise ValueError(f"unknown family {name!r}")


def persist_study(study: optuna.Study, name: str, out_dir: Path) -> Path:
    """Write best params, importances, and trial history as JSON."""
    importances = optuna.importance.get_param_importances(study)
    payload = {
        "family": name,
        "n_trials": len(study.trials),
        "best_params": {
            k: (float(v) if isinstance(v, float) else v) for k, v in study.best_params.items()
        },
        "best_value": float(study.best_value),
        "importances": {k: float(v) for k, v in importances.items()},
        "trials": [
            {
                "number": t.number,
                "value": float(t.value) if t.value is not None else None,
                "params": {k: float(v) if isinstance(v, float) else v for k, v in t.params.items()},
                "pruned": t.state == optuna.trial.TrialState.PRUNED,
            }
            for t in study.trials
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}_hpo.json"
    path.write_text(json.dumps(payload, indent=2))
    logger.info(
        "%s HPO: best val PR-AUC=%.4f params=%s (%d trials)",
        name,
        study.best_value,
        study.best_params,
        len(study.trials),
    )
    return path


def tune_all(config: AnomalyConfig, x_train: np.ndarray, y_train: np.ndarray) -> dict[str, Any]:
    """Tune every configured family and persist tuned models + study artifacts.

    The tail of the train window (last 20%) serves as validation; detectors
    never see the test window during search.
    """
    n_val = max(100, int(x_train.shape[0] * 0.2))
    x_fit, y_fit = x_train[:-n_val], y_train[:-n_val]
    x_val, y_val = x_train[-n_val:], y_train[-n_val:]
    logger.info(
        "HPO: %d fit rows, %d validation rows (train window only)",
        x_fit.shape[0],
        x_val.shape[0],
    )

    config.tuned_models_dir.mkdir(parents=True, exist_ok=True)
    tuned: dict[str, Any] = {}
    for name in config.models:
        study = tune_family(name, x_fit, y_fit, x_val, y_val, config)
        persist_study(study, name, config.tuned_models_dir)
        model = fit_tuned(name, study.best_params, x_train, config)
        path = config.tuned_models_dir / f"{name}_tuned.joblib"
        joblib.dump(model, path)
        logger.info("wrote %s", path)
        tuned[name] = model
    return tuned
