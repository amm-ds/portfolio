"""Hyperparameter optimisation (Optuna) for the GBM and TemporalNet.

Validation protocol: the last fold of ``portfolio_core.timecv.TimeSeriesCV``
(n_splits=4, **gap=24h**) computed on the **train side only** — the Oct-Dec
test window is never touched. Trials are seeded for determinism.

- GBM study (~30 trials): learning_rate, max_iter, max_leaf_nodes,
  min_samples_leaf, l2_regularization, max_features. Median pruning at a
  100-iteration checkpoint — trials worse than the running median at that
  budget are stopped before paying for the full fit.
- NN study (~10 trials): hidden_size (32-128), lr (log), epochs ≤ 8,
  weight_decay (log) — driven through the same hand-written ``_fit_net`` loop
  as production training.

Best params are persisted to ``reports/models/hpo_{gbm,nn}.json`` (the
runtime source of truth for the train stages) and mirrored into
``params.yaml`` under ``gbm_tuned`` / ``nn_tuned`` as the production config.

Row budget: the HPO window is capped to the most-recent ``hpo.max_fit_rows``
of the train slice per trial (default 1.2M) — temporal slice, never random —
documented in DESIGN.md.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import optuna
import polars as pl
from portfolio_core.logging import get_logger
from portfolio_eval.ml import regression_metrics

from mobility.config import MobilityConfig, get_config
from mobility.model import (
    _fit_net,
    _make_gbm,
    _nn_data,
    _temporal_val_split,
    _xy,
)

logger = get_logger(__name__)


def _hpo_window(cfg: MobilityConfig) -> tuple[pl.DataFrame, np.ndarray, np.ndarray]:
    """Capped train window + embargoed (fit_idx, val_idx) split."""
    train = pl.read_parquet(cfg.features_dir / "train.parquet")
    if cfg.hpo.max_fit_rows is not None and train.height > cfg.hpo.max_fit_rows:
        logger.info(
            "capping HPO window %d -> %d rows (most-recent slice)",
            train.height,
            cfg.hpo.max_fit_rows,
        )
        train = train.tail(cfg.hpo.max_fit_rows)
    fit_idx, val_idx = _temporal_val_split(train.height, gap=24)
    return train, fit_idx, val_idx


def _val_window_bounds(train: pl.DataFrame, val_idx: np.ndarray) -> dict[str, str]:
    ts = train["ts"].to_list()
    return {"fit_until": str(ts[int(val_idx[0]) - 25]), "val_from": str(ts[int(val_idx[0])])}


def tune_gbm(cfg: MobilityConfig) -> dict[str, Any]:
    """Optuna study over GBM hyperparameters; returns the persisted result."""
    train, fit_idx, val_idx = _hpo_window(cfg)
    X, y = _xy(train)
    X_fit, y_fit = X[fit_idx], y[fit_idx]
    X_val, y_val = X[val_idx], y[val_idx]
    logger.info(
        "GBM HPO: %d fit rows, %d val rows (24h embargo), %d trials",
        len(fit_idx),
        len(val_idx),
        cfg.hpo.gbm_trials,
    )
    sampler = optuna.samplers.TPESampler(seed=cfg.seed)
    pruner = optuna.pruners.MedianPruner(n_startup_trials=8, n_warmup_steps=0)
    study = optuna.create_study(
        direction="minimize", sampler=sampler, pruner=pruner, study_name="gbm_mae"
    )

    def objective(trial: optuna.Trial) -> float:
        params = {
            "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.2, log=True),
            "max_iter": trial.suggest_int("max_iter", 100, 300),
            "max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 15, 127),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 200, log=True),
            "l2_regularization": trial.suggest_float("l2_regularization", 1e-3, 100.0, log=True),
            "max_features": trial.suggest_float("max_features", 0.5, 1.0),
        }
        # Median-pruning checkpoint: score a cheap 100-iteration budget first.
        probe = _make_gbm({**params, "max_iter": 100}, seed=cfg.seed)
        probe.fit(X_fit, y_fit)
        probe_mae = regression_metrics(y_val.tolist(), probe.predict(X_val).tolist())[0].value
        trial.report(probe_mae, step=0)
        if trial.should_prune():
            raise optuna.TrialPruned(f"pruned at checkpoint (probe MAE {probe_mae:.4f})")
        model = _make_gbm(params, seed=cfg.seed)
        model.fit(X_fit, y_fit)
        mae = regression_metrics(y_val.tolist(), model.predict(X_val).tolist())[0].value
        logger.info("trial %d: val MAE %.4f %s", trial.number, mae, params)
        return mae

    study.optimize(objective, n_trials=cfg.hpo.gbm_trials)
    result: dict[str, Any] = {
        "kind": "gbm",
        "best_params": {
            k: (round(v, 6) if isinstance(v, float) else v) for k, v in study.best_params.items()
        },
        "best_val_mae": round(float(study.best_value), 6),
        "n_trials": len(study.trials),
        "n_pruned": sum(t.state == optuna.trial.TrialState.PRUNED for t in study.trials),
        "val_window": _val_window_bounds(train, val_idx),
        "sampler": f"TPESampler(seed={cfg.seed})",
        "pruner": "MedianPruned@100it",
    }
    _persist(cfg, "gbm", result)
    logger.info(
        "GBM HPO best val MAE %.4f params %s", result["best_val_mae"], result["best_params"]
    )
    return result


def tune_nn(cfg: MobilityConfig) -> dict[str, Any]:
    """Small Optuna study over TemporalNet hyperparameters (hand-written loop)."""
    data = _nn_data(cfg, max_rows=cfg.hpo.max_fit_rows)
    fit_idx, val_idx = _temporal_val_split(len(data.ys), gap=24)
    logger.info(
        "NN HPO: %d fit rows, %d val rows (24h embargo), %d trials",
        len(fit_idx),
        len(val_idx),
        cfg.hpo.nn_trials,
    )
    sampler = optuna.samplers.TPESampler(seed=cfg.seed)
    study = optuna.create_study(direction="minimize", sampler=sampler, study_name="nn_val_mae")

    def objective(trial: optuna.Trial) -> float:
        params = {
            "hidden_size": trial.suggest_categorical("hidden_size", [32, 64, 96, 128]),
            "lr": trial.suggest_float("lr", 1e-4, 3e-3, log=True),
            "epochs": trial.suggest_int("epochs", 4, 8),
            "weight_decay": trial.suggest_float("weight_decay", 1e-6, 1e-3, log=True),
            "second_hidden_size": 0,  # placeholder, filled below
            "batch_size": cfg.nn.batch_size,
            "grad_clip": cfg.nn.grad_clip,
            "early_stop_patience": cfg.nn.early_stop_patience,
        }
        params["second_hidden_size"] = params["hidden_size"] // 2
        best_val, _ = _fit_net(
            data.Xs,
            data.ys,
            fit_idx,
            val_idx,
            hidden=int(params["hidden_size"]),
            second_hidden=int(params["second_hidden_size"]),
            epochs=int(params["epochs"]),
            batch_size=int(params["batch_size"]),
            lr=float(params["lr"]),
            weight_decay=float(params["weight_decay"]),
            grad_clip=float(params["grad_clip"]),
            patience=int(params["early_stop_patience"]),
            seed=cfg.seed,
            y_sigma=data.y_sigma,
        )
        return best_val

    study.optimize(objective, n_trials=cfg.hpo.nn_trials)
    best = dict(study.best_params)
    best["second_hidden_size"] = best["hidden_size"] // 2
    best["batch_size"] = cfg.nn.batch_size
    best["grad_clip"] = cfg.nn.grad_clip
    best["early_stop_patience"] = cfg.nn.early_stop_patience
    result: dict[str, Any] = {
        "kind": "nn",
        "best_params": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in best.items()},
        "best_val_mae": round(float(study.best_value), 6),
        "n_trials": len(study.trials),
        "n_pruned": 0,
        "sampler": f"TPESampler(seed={cfg.seed})",
    }
    _persist(cfg, "nn", result)
    logger.info("NN HPO best val MAE %.4f params %s", result["best_val_mae"], result["best_params"])
    return result


def _persist(cfg: MobilityConfig, kind: str, result: dict[str, Any]) -> None:
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    (cfg.models_dir / f"hpo_{kind}.json").write_text(json.dumps(result, indent=2) + "\n")
    _mirror_params_yaml(cfg, kind, result)


def _mirror_params_yaml(cfg: MobilityConfig, kind: str, result: dict[str, Any]) -> None:
    """Mirror best params into params.yaml as the production config (gbm_tuned/nn_tuned)."""
    import yaml  # type: ignore[import-untyped]

    path = Path(__file__).resolve().parents[2] / "params.yaml"
    if not path.exists():
        logger.warning("params.yaml not found at %s — skipping mirror", path)
        return
    doc = yaml.safe_load(path.read_text()) or {}
    doc[f"{kind}_tuned"] = {
        "best_params": result["best_params"],
        "best_val_mae": result["best_val_mae"],
        "n_trials": result["n_trials"],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def tune_all(cfg: MobilityConfig | None = None) -> dict[str, dict[str, Any]]:
    """Run both studies (GBM then NN); returns {kind: result}."""
    cfg = cfg or get_config()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    return {"gbm": tune_gbm(cfg), "nn": tune_nn(cfg)}
