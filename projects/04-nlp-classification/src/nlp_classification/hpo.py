"""Optuna HPO over the hand-written fine-tuning loop.

Search space: learning rate (log), warmup ratio, weight decay, epochs — batch
size stays fixed at 32 per the bounded budget. Objective: validation macro-F1
on the stratified carve-out. Median pruning fires between epochs so unpromising
trials stop early. The sampler is seeded, so the whole study is deterministic.

Outputs: ``reports/hpo_study.json`` (best params + per-trial summary),
``reports/hpo_best.json`` (machine-readable best params for train-tuned), the
two HPO figures, and a best-params block written back into ``params.yaml``.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import optuna
import plotly.graph_objects as go
import torch
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
from optuna.trial import TrialState
from portfolio_core.logging import get_logger
from portfolio_core.plotting import apply_theme, save_html, save_json

from nlp_classification.config import HPOBest, NLPConfig
from nlp_classification.model import train_nn
from nlp_classification.shims import Dataset, yaml_safe_dump, yaml_safe_load

logger = get_logger(__name__)


def suggest_config(trial: optuna.Trial, cfg: NLPConfig) -> NLPConfig:
    """Sample one trial configuration from the declared search space."""
    hpo = cfg.hpo
    return cfg.model_copy(
        update={
            "learning_rate": trial.suggest_float("learning_rate", hpo.lr_min, hpo.lr_max, log=True),
            "warmup_ratio": trial.suggest_float("warmup_ratio", 0.0, hpo.warmup_max),
            "weight_decay": trial.suggest_float("weight_decay", 0.0, hpo.weight_decay_max),
            "epochs": trial.suggest_int("epochs", hpo.epochs_min, hpo.epochs_max),
        }
    )


def make_study(
    cfg: NLPConfig, seed: int | None = None, startup_trials: int | None = None
) -> optuna.Study:
    """Deterministic study: seeded TPE sampler + median pruner between epochs.

    ``seed``/``startup_trials`` overrides exist so the small multi-seed
    variance study can run independent studies per seed.
    """
    return optuna.create_study(
        direction="maximize",
        sampler=TPESampler(seed=cfg.seed if seed is None else seed),
        pruner=MedianPruner(
            n_startup_trials=cfg.hpo.startup_trials if startup_trials is None else startup_trials,
            n_warmup_steps=cfg.hpo.pruner_warmup_epochs,
        ),
    )


def run_hpo(
    cfg: NLPConfig,
    train_tok: Dataset,
    val_tok: Dataset,
    n_labels: int,
    device: torch.device,
) -> tuple[HPOBest, optuna.Study]:
    """Run the study; returns the winning params and the finished study.

    Each trial trains through the real hand-written loop and reports validation
    macro-F1 per epoch so the pruner can stop losers early.
    """
    study = make_study(cfg)

    def objective(trial: optuna.Trial) -> float:
        trial_cfg = suggest_config(trial, cfg)

        def on_epoch(epoch: int, val_f1: float) -> None:
            trial.report(val_f1, epoch - 1)
            if trial.should_prune():
                raise optuna.TrialPruned(f"pruned after epoch {epoch} (val_f1={val_f1:.4f})")

        _, history = train_nn(trial_cfg, train_tok, val_tok, n_labels, device, on_epoch=on_epoch)
        return history.best_epoch().val_f1_macro

    study = make_study(cfg)
    logger.info(
        "starting HPO: %d trials, space lr=[%.0e, %.0e] warmup=[0, %.2f] "
        "wd=[0, %.2f] epochs=[%d, %d]",
        cfg.hpo.n_trials,
        cfg.hpo.lr_min,
        cfg.hpo.lr_max,
        cfg.hpo.warmup_max,
        cfg.hpo.weight_decay_max,
        cfg.hpo.epochs_min,
        cfg.hpo.epochs_max,
    )
    study.optimize(objective, n_trials=cfg.hpo.n_trials)

    best = HPOBest(
        learning_rate=float(study.best_params["learning_rate"]),
        warmup_ratio=float(study.best_params["warmup_ratio"]),
        weight_decay=float(study.best_params["weight_decay"]),
        epochs=int(study.best_params["epochs"]),
        best_val_f1_macro=float(study.best_value),
    )
    n_pruned = sum(1 for t in study.trials if t.state == TrialState.PRUNED)
    logger.info(
        "HPO done: best val_f1=%.4f (lr=%.2e warmup=%.3f wd=%.3f epochs=%d), %d/%d trials pruned",
        best.best_val_f1_macro,
        best.learning_rate,
        best.warmup_ratio,
        best.weight_decay,
        best.epochs,
        n_pruned,
        len(study.trials),
    )
    return best, study


def run_multi_seed_hpo(
    cfg: NLPConfig,
    train_tok: Dataset,
    val_tok: Dataset,
    n_labels: int,
    device: torch.device,
) -> dict[str, Any]:
    """Seed-variance study: one small independent study per fixed seed.

    Each seed re-runs the same search space (with the tighter ``epochs_max``
    budget) so the spread of best validation macro-F1 across seeds can be
    compared against the HPO gain itself — the honest finding may be that
    variance exceeds the gain at this sample size.
    """
    ms = cfg.hpo_seeds
    seed_cfg = cfg.model_copy(
        update={
            "hpo": cfg.hpo.model_copy(update={"epochs_max": ms.epochs_max, "n_trials": ms.n_trials})
        }
    )
    best_per_seed: dict[str, float] = {}
    for seed in ms.seeds:
        study = make_study(seed_cfg, seed=seed, startup_trials=ms.startup_trials)

        def objective(trial: optuna.Trial) -> float:
            trial_cfg = suggest_config(trial, seed_cfg)
            _, history = train_nn(trial_cfg, train_tok, val_tok, n_labels, device)
            return history.best_epoch().val_f1_macro

        study.optimize(objective, n_trials=ms.n_trials)
        best_per_seed[str(seed)] = float(study.best_value)
        logger.info("seed-variance: seed=%d best val_f1=%.4f", seed, study.best_value)

    values = np.asarray(list(best_per_seed.values()), dtype=float)
    report = {
        "seeds": best_per_seed,
        "mean": float(values.mean()),
        "std": float(values.std(ddof=0)),
        "n_trials_per_seed": ms.n_trials,
        "epochs_max": ms.epochs_max,
    }
    logger.info(
        "seed-variance: mean=%.4f std=%.4f over %d seeds",
        report["mean"],
        report["std"],
        len(values),
    )
    return report


def persist_seed_report(cfg: NLPConfig, report: dict[str, Any]) -> Path:
    path = Path(cfg.reports_dir) / "hpo_seeds.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    return path


def tuned_config(cfg: NLPConfig) -> NLPConfig:
    """Config with the HPO best params applied (used by the train-tuned stage)."""
    if cfg.hpo_best is None:
        raise ValueError("hpo_best is not set — run the hpo stage first")
    return cfg.model_copy(
        update={
            "learning_rate": cfg.hpo_best.learning_rate,
            "warmup_ratio": cfg.hpo_best.warmup_ratio,
            "weight_decay": cfg.hpo_best.weight_decay,
            "epochs": cfg.hpo_best.epochs,
        }
    )


def persist_hpo(
    cfg: NLPConfig, best: HPOBest, study: optuna.Study, params_path: str | Path
) -> None:
    """Write study summary, HPO figures, and best params (reports/ + params.yaml)."""
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "hpo_best.json").write_text(best.model_dump_json(indent=2))
    trials = [
        {
            "number": t.number,
            "state": str(t.state).split(".")[-1],
            "value": t.value,
            "params": {k: float(v) if isinstance(v, float) else v for k, v in t.params.items()},
        }
        for t in study.trials
    ]
    cfg.study_path.write_text(
        json.dumps(
            {"best": best.model_dump(), "n_trials": len(study.trials), "trials": trials},
            indent=2,
        )
    )
    for name, fig in (
        ("hpo_history", hpo_history_figure(study)),
        ("hpo_importance", hpo_importance_figure(study)),
    ):
        save_html(fig, Path(cfg.reports_dir) / "figures" / f"{name}.html")
        save_json(fig, Path(cfg.reports_dir) / "figures" / f"{name}.json")

    params_file = Path(params_path)
    if params_file.exists():
        data: dict[str, Any] = yaml_safe_load(params_file.read_text()) or {}
        data["hpo_best"] = best.model_dump()
        params_file.write_text(yaml_safe_dump(data, sort_keys=False))


def hpo_history_figure(study: optuna.Study) -> go.Figure:
    """Optimization history: per-trial best value, completed vs pruned."""
    trials = study.trials
    fig = go.Figure()
    fig.add_scatter(
        x=[t.number for t in trials if t.value is not None],
        y=[t.value for t in trials if t.value is not None],
        mode="markers",
        name="trial value",
    )
    best_so_far: list[float] = []
    running = -1.0
    for t in trials:
        if t.value is not None:
            running = max(running, t.value)
        best_so_far.append(running)
    fig.add_scatter(
        x=[t.number for t in trials],
        y=best_so_far,
        mode="lines+markers",
        name="best so far",
    )
    fig.update_layout(
        title="Optuna HPO — validation macro-F1 per trial (median pruning)",
        xaxis_title="trial",
        yaxis_title="val macro-F1",
    )
    return apply_theme(fig)


def hpo_importance_figure(study: optuna.Study) -> go.Figure:
    """Parameter importance (fanova over completed trials) as a bar panel."""
    completed = [t for t in study.trials if t.value is not None and t.state.name == "COMPLETE"]
    if len(completed) < 2:
        fig = go.Figure()
        fig.update_layout(title="HPO parameter importance (needs ≥2 completed trials)")
        return apply_theme(fig)
    importances = optuna.importance.get_param_importances(study)
    names = list(importances)
    fig = go.Figure(data=go.Bar(x=names, y=[importances[n] for n in names]))
    fig.update_layout(
        title="HPO parameter importance (fANOVA)",
        yaxis_title="importance",
        yaxis_range=[0, 1],
    )
    return apply_theme(fig)
