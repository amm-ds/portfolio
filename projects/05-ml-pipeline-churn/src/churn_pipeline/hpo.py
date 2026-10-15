"""Optuna model selection: logistic regression vs histogram gradient boosting.

Fully seeded (TPE sampler + stratified folds), so a study is a deterministic
function of (X, y, seed, trials). The objective scores stratified-CV F1 of the
*full pipeline* — preprocessing stays inside the estimator for every trial —
with per-fold intermediate values reported for median pruning.
"""

import warnings
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
from optuna.trial import Trial
from portfolio_core.logging import get_logger
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from churn_pipeline.config import ChurnConfig, pd, threadpool_limits
from churn_pipeline.evaluate import cost_curve
from churn_pipeline.model import build_pipeline

log = get_logger(__name__)

MODEL_FAMILIES = ("logreg", "histgb", "xgboost", "lightgbm")


@dataclass(frozen=True)
class ModelSelection:
    """Outcome of one HPO study: the production classifier config."""

    family: str
    params: dict[str, Any]
    best_score: float
    objective: str
    n_trials: int
    family_scores: dict[str, float] = field(default_factory=dict)


def suggest_params(trial: Trial) -> tuple[str, dict[str, Any]]:
    """Sample one candidate from the joint search space.

    LogisticRegression: C (log 1e-3..1e2), l1_ratio (0..1; 0 = l2, 1 = l1,
    in-between = elasticnet — sklearn ≥ 1.9 unified API, solver resolved for
    speed: lbfgs for pure l2, saga otherwise).
    HistGradientBoostingClassifier: learning_rate (log 0.05..0.3),
    max_iter (50..150), max_leaf_nodes (15..31), min_samples_leaf (20..60).
    XGBClassifier (sklearn API): n_estimators (50..300), learning_rate
    (log 0.03..0.3), max_depth (3..8), subsample (0.5..1.0).
    LGBMClassifier (sklearn API): n_estimators (50..300), learning_rate
    (log 0.03..0.3), num_leaves (15..63), min_child_samples (20..60).
    Boosting ranges are capped to keep the full selection pass under a
    minute; all arms consume the same ColumnTransformer output inside the
    Pipeline (no native categorical bypass — one preprocessing contract).
    """
    family = trial.suggest_categorical("model", MODEL_FAMILIES)
    if family == "logreg":
        # sklearn >= 1.9 unified API: no `penalty` kwarg; l1_ratio=0 is l2,
        # l1_ratio=1 is l1, in-between is elasticnet (solver resolved later).
        params = {
            "C": trial.suggest_float("C", 1e-3, 1e2, log=True),
            "l1_ratio": trial.suggest_float("l1_ratio", 0.0, 1.0),
        }
    elif family == "histgb":
        params = {
            "learning_rate": trial.suggest_float("learning_rate", 0.05, 0.3, log=True),
            "max_iter": trial.suggest_int("max_iter", 50, 150),
            "max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 15, 31),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 20, 60),
        }
    elif family == "xgboost":
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
        }
    else:  # lightgbm
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 50, 300),
            "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.3, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 63),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 60),
        }
    return family, params


def _resolve_logreg(params: dict[str, Any]) -> dict[str, Any]:
    """Resolve solver from l1_ratio: lbfgs for pure l2, saga otherwise."""
    resolved: dict[str, Any] = {"C": float(params["C"]), "l1_ratio": float(params["l1_ratio"])}
    if resolved["l1_ratio"] == 0.0:
        resolved["solver"] = "lbfgs"
        resolved["max_iter"] = 1000
    else:
        resolved["solver"] = "saga"
        resolved["max_iter"] = 500
    return resolved


def build_estimator(cfg: ChurnConfig, family: str, params: dict[str, Any]) -> Any:
    """Instantiate the full pipeline for a family with resolved params."""
    resolved = _resolve_logreg(params) if family == "logreg" else dict(params)
    return build_pipeline(cfg, family=family, params=resolved)


def _f1_objective(cfg: ChurnConfig, X: pd.DataFrame, y: pd.Series) -> Any:
    """Stratified-CV F1 with per-fold intermediates for median pruning."""

    def fn(trial: Trial) -> float:
        family, params = suggest_params(trial)
        pipe = build_estimator(cfg, family, params)
        folds = StratifiedKFold(n_splits=cfg.cv_folds, shuffle=True, random_state=cfg.seed)
        f1s = []
        for step, (tr, va) in enumerate(folds.split(X, y)):
            pipe.fit(X.iloc[tr], y.iloc[tr])
            pred = pipe.predict(X.iloc[va])
            fold_f1 = float(f1_score(y.iloc[va], pred))
            f1s.append(fold_f1)
            trial.report(fold_f1, step=step)
            if trial.should_prune():
                raise optuna.TrialPruned()
        return float(np.mean(f1s))

    return fn


def _cost_objective(cfg: ChurnConfig, X: pd.DataFrame, y: pd.Series) -> Any:
    """CV business cost (FP=fp_cost, FN=fn_cost), threshold tuned per trial.

    Per fold we fit on the train part and score out-of-fold probabilities on
    the validation part; the trial's cost is the business cost of the pooled
    out-of-fold probabilities at their cost-optimal threshold — the same
    threshold-tuning view used at evaluation, so the objective optimizes
    exactly what deployment measures. Pruning intermediates report the
    running mean of per-fold costs (each at its own fold-optimal threshold).
    """

    def fn(trial: Trial) -> float:
        family, params = suggest_params(trial)
        if family == "xgboost":
            # XGBClassifier ignores sklearn class_weight; balance via the
            # native scale_pos_weight (fixed per dataset, like class_weight).
            n_pos = float(np.sum(y == 1))
            n_neg = float(len(y) - n_pos)
            params = {**params, "scale_pos_weight": n_neg / max(n_pos, 1.0)}
        pipe = build_estimator(cfg, family, params)
        folds = StratifiedKFold(n_splits=cfg.cv_folds, shuffle=True, random_state=cfg.seed)
        y_arr = np.asarray(y, dtype=int)
        oof = np.zeros(len(y_arr), dtype=float)
        fold_costs: list[float] = []
        for step, (tr, va) in enumerate(folds.split(X, y)):
            pipe.fit(X.iloc[tr], y.iloc[tr])
            proba = np.asarray(pipe.predict_proba(X.iloc[va])[:, 1], dtype=float)
            oof[va] = proba
            fold_costs.append(float(cost_curve(cfg, y_arr[va], proba)[0].min()))
            trial.report(-float(np.mean(fold_costs)), step=step)
            if trial.should_prune():
                raise optuna.TrialPruned()
        total_costs, _ = cost_curve(cfg, y_arr, oof)
        return -float(total_costs.min())

    return fn


def run_study(
    cfg: ChurnConfig,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_trials: int | None = None,
) -> ModelSelection:
    """Seeded TPE study over the joint space with median pruning.

    Fits run single-threaded: OpenMP oversubscription makes HistGB ~200x
    slower than sequential on this machine (measured), and 75 sequential fits
    still take only a few seconds.
    """
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    objective = _cost_objective if cfg.hpo_objective == "cost" else _f1_objective
    study = optuna.create_study(
        direction="maximize",
        sampler=TPESampler(seed=cfg.seed),
        pruner=MedianPruner(n_startup_trials=6, n_min_trials=3),
    )
    with threadpool_limits(limits=1), warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        study.optimize(
            objective(cfg, X_train, y_train),
            n_trials=n_trials or cfg.hpo_trials,
            show_progress_bar=False,
        )
    best = study.best_trial
    best_value = cast(float, best.value)
    family = str(best.params["model"])
    params = {k: v for k, v in best.params.items() if k != "model"}
    # Only COMPLETED trials carry full-pipeline OOF costs; pruned trials hold
    # partial-fold intermediates (Optuna 5 sets value on pruned trials too).
    family_scores: dict[str, float] = {}
    for fam in MODEL_FAMILIES:
        vals = [
            t.value
            for t in study.trials
            if t.state == optuna.trial.TrialState.COMPLETE
            and t.params.get("model") == fam
            and t.value is not None
        ]
        if vals:
            family_scores[fam] = float(-np.mean(vals))
    log.info(
        "hpo: selected %s %s (%s=%.4f over %d trials)",
        family,
        {k: round(v, 4) for k, v in params.items()},
        cfg.hpo_objective,
        best_value,
        len(study.trials),
    )
    return ModelSelection(
        family=family,
        params=params,
        best_score=best_value,
        objective=cfg.hpo_objective,
        n_trials=len(study.trials),
        family_scores=family_scores,
    )


def cv_f1_of_selected(
    cfg: ChurnConfig, selection: ModelSelection, X: pd.DataFrame, y: pd.Series
) -> float:
    """Out-of-fold F1 of the selected pipeline (used by tests, not the CLI)."""
    pipe = build_estimator(cfg, selection.family, selection.params)
    pred = cross_val_predict(
        pipe,
        X,
        y,
        cv=StratifiedKFold(n_splits=cfg.cv_folds, shuffle=True, random_state=cfg.seed),
    )
    return float(f1_score(y, pred))
