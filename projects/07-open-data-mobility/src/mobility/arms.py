"""XGBoost / LightGBM challenger arms — deliberately torch-free.

Two OpenMP runtimes (xgboost/lightgbm's libgomp vs torch's) cannot coexist in
one process on macOS — whichever loads second crashes the first at fit time.
So the arms live in their own module and are executed by the CLI in a
subprocess (``mobility train-arms``) that never imports torch:

1. tune each arm with Optuna (seeded TPE, same embargoed 500k-capped window
   and Apr-22+ validation fold as the sklearn GBM study — test untouched),
2. refit the best params on the full train window (mean + quantile-0.9 twin),
3. persist ``hpo_{xgb,lgbm}.json`` + ``gbm_{xgb,lgbm}_tuned.joblib`` pairs and
   merge the arm prediction columns into ``predictions_baseline.parquet``.
"""

import json
from typing import Any

import joblib
import lightgbm
import numpy as np
import optuna
import polars as pl
import xgboost
from portfolio_core.logging import get_logger
from portfolio_core.timecv import TimeSeriesCV
from portfolio_eval.ml import regression_metrics

from mobility.config import MobilityConfig, get_config
from mobility.features import FEATURE_COLUMNS

logger = get_logger(__name__)


def _make_xgb(params: dict[str, Any], *, seed: int, quantile: float | None = None) -> Any:
    kwargs: dict[str, Any] = {
        "n_estimators": int(params["n_estimators"]),
        "learning_rate": float(params["learning_rate"]),
        "max_depth": int(params["max_depth"]),
        "subsample": float(params["subsample"]),
        "colsample_bytree": float(params["colsample_bytree"]),
        "reg_lambda": float(params["reg_lambda"]),
        "tree_method": "hist",
        "random_state": seed,
        "n_jobs": 4,
    }
    if quantile is not None:
        kwargs["objective"] = "reg:quantileerror"
        kwargs["quantile_alpha"] = quantile
    return xgboost.XGBRegressor(**kwargs)


def _make_lgbm(params: dict[str, Any], *, seed: int, quantile: float | None = None) -> Any:
    return lightgbm.LGBMRegressor(
        objective="quantile" if quantile is not None else "regression",
        alpha=quantile if quantile is not None else None,
        n_estimators=int(params["n_estimators"]),
        learning_rate=float(params["learning_rate"]),
        num_leaves=int(params["num_leaves"]),
        min_child_samples=int(params["min_child_samples"]),
        subsample=float(params["subsample"]),
        subsample_freq=1,
        colsample_bytree=float(params["colsample_bytree"]),
        reg_lambda=float(params["reg_lambda"]),
        device="cpu",
        deterministic=True,
        force_row_wise=True,
        random_state=seed,
        verbose=-1,
    )


_FACTORIES = {"xgb": _make_xgb, "lgbm": _make_lgbm}

_SPACES: dict[str, Any] = {
    "xgb": lambda t: {
        "n_estimators": t.suggest_int("n_estimators", 200, 800),
        "learning_rate": t.suggest_float("learning_rate", 0.02, 0.2, log=True),
        "max_depth": t.suggest_int("max_depth", 4, 12),
        "subsample": t.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": t.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_lambda": t.suggest_float("reg_lambda", 1e-3, 100.0, log=True),
    },
    "lgbm": lambda t: {
        "n_estimators": t.suggest_int("n_estimators", 200, 800),
        "learning_rate": t.suggest_float("learning_rate", 0.02, 0.2, log=True),
        "num_leaves": t.suggest_int("num_leaves", 15, 255),
        "min_child_samples": t.suggest_int("min_child_samples", 10, 200, log=True),
        "subsample": t.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": t.suggest_float("colsample_bytree", 0.5, 1.0),
        "reg_lambda": t.suggest_float("reg_lambda", 1e-3, 100.0, log=True),
    },
}


def _hpo_window(
    cfg: MobilityConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, str]]:
    """Capped train window + embargoed split — mirrors tune.py's discipline."""
    train = pl.read_parquet(cfg.features_dir / "train.parquet")
    if cfg.hpo.max_fit_rows is not None and train.height > cfg.hpo.max_fit_rows:
        train = train.tail(cfg.hpo.max_fit_rows)
    fold = list(TimeSeriesCV(n_splits=4, gap=24).split(train.height))[-1]
    X = train.select(FEATURE_COLUMNS).to_numpy().astype(np.float32)
    y = train["target"].to_numpy().astype(np.float32)
    ts = train["ts"].to_list()
    bounds = {
        "fit_until": str(ts[int(fold.val_idx[0]) - 25]),
        "val_from": str(ts[int(fold.val_idx[0])]),
    }
    return X[fold.train_idx], y[fold.train_idx], X[fold.val_idx], y[fold.val_idx], bounds


def tune_arm(cfg: MobilityConfig, arm: str, n_trials: int) -> dict[str, Any]:
    """Challenger study on the same embargoed window as the sklearn GBM."""
    X_fit, y_fit, X_val, y_val, bounds = _hpo_window(cfg)
    make = _FACTORIES[arm]
    logger.info(
        "%s HPO: %d fit rows, %d val rows, %d trials", arm, len(y_fit), len(y_val), n_trials
    )
    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=cfg.seed),
        study_name=f"{arm}_mae",
    )

    def objective(trial: optuna.Trial) -> float:
        params = _SPACES[arm](trial)
        model = make(params, seed=cfg.seed)
        model.fit(X_fit, y_fit)
        mae = regression_metrics(y_val.tolist(), model.predict(X_val).tolist())[0].value
        logger.info("%s trial %d: val MAE %.4f", arm, trial.number, mae)
        return mae

    study.optimize(objective, n_trials=n_trials)
    result: dict[str, Any] = {
        "kind": arm,
        "best_params": {
            k: (round(v, 6) if isinstance(v, float) else v) for k, v in study.best_params.items()
        },
        "best_val_mae": round(float(study.best_value), 6),
        "n_trials": len(study.trials),
        "n_pruned": 0,
        "val_window": bounds,
        "sampler": f"TPESampler(seed={cfg.seed})",
        "challenger_to": "gbm_tuned",
    }
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    (cfg.models_dir / f"hpo_{arm}.json").write_text(json.dumps(result, indent=2) + "\n")
    logger.info("%s HPO best val MAE %.4f %s", arm, result["best_val_mae"], result["best_params"])
    return result


def fit_arm_pair(cfg: MobilityConfig, arm: str, params: dict[str, Any]) -> None:
    """Refit best params on the full train window; persist pair + p90 twin."""
    train = pl.read_parquet(cfg.features_dir / "train.parquet")
    if train.height > cfg.max_train_rows:
        train = train.tail(cfg.max_train_rows)
    test = pl.read_parquet(cfg.features_dir / "test.parquet")
    X_train = train.select(FEATURE_COLUMNS).to_numpy().astype(np.float32)
    y_train = train["target"].to_numpy().astype(np.float32)
    X_test = test.select(FEATURE_COLUMNS).to_numpy().astype(np.float32)

    make = _FACTORIES[arm]
    model = make(params, seed=cfg.seed)
    model.fit(X_train, y_train)
    p90_model = make(params, seed=cfg.seed, quantile=0.9)
    p90_model.fit(X_train, y_train)
    joblib.dump(model, cfg.models_dir / f"gbm_{arm}_tuned.joblib")
    joblib.dump(p90_model, cfg.models_dir / f"gbm_p90_{arm}_tuned.joblib")

    # merge prediction columns into the baseline predictions frame
    base_path = cfg.models_dir / "predictions_baseline.parquet"
    base = pl.read_parquet(base_path)
    extra = pl.DataFrame(
        {
            "zone_id": test["zone_id"],
            "ts": test["ts"],
            f"y_gbm_{arm}_tuned": model.predict(X_test),
            f"y_p90_{arm}_tuned": p90_model.predict(X_test),
        }
    )
    base = base.join(extra, on=["zone_id", "ts"], how="left")
    base.write_parquet(base_path, compression="zstd")
    logger.info("%s pair refit on full train window; %s columns merged", arm, arm)


def fit_arms(cfg: MobilityConfig | None = None) -> dict[str, dict[str, Any]]:
    """Tune + fit both arms; entry point for the CLI subprocess."""
    cfg = cfg or get_config()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    results: dict[str, dict[str, Any]] = {}
    for arm in ("xgb", "lgbm"):
        results[arm] = tune_arm(cfg, arm, n_trials=cfg.hpo.arm_trials)
        fit_arm_pair(cfg, arm, results[arm]["best_params"])
    return results
