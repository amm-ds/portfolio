"""HPO tests: deterministic seeded study, tuned-config plumbing, callbacks.

No network: the studies run over a millisecond-scale dummy objective and the
training-loop callback test uses a tiny injected module.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import optuna
import pytest
import torch
from datasets import Dataset  # type: ignore[import-untyped]
from nlp_classification.config import HPOBest, NLPConfig
from nlp_classification.evaluate import select_tuned_run
from nlp_classification.hpo import make_study, suggest_config, tuned_config
from nlp_classification.model import train_nn
from torch import nn


def test_seeded_study_is_deterministic() -> None:
    """Two studies from make_study with the same seed pick the same params."""

    def objective(trial: optuna.Trial) -> float:
        x = trial.suggest_float("learning_rate", 1e-5, 5e-5, log=True)
        return -((x - 3e-5) ** 2)

    cfg = NLPConfig(seed=7)
    study_a = make_study(cfg)
    study_b = make_study(cfg)
    study_a.optimize(objective, n_trials=4)
    study_b.optimize(objective, n_trials=4)
    assert study_a.best_params == study_b.best_params
    assert study_a.best_value == study_b.best_value


def test_suggest_config_respects_search_space() -> None:
    cfg = NLPConfig()
    study = make_study(cfg)

    def objective(trial: optuna.Trial) -> float:
        trial_cfg = suggest_config(trial, cfg)
        assert cfg.hpo.lr_min <= trial_cfg.learning_rate <= cfg.hpo.lr_max
        assert 0.0 <= trial_cfg.warmup_ratio <= cfg.hpo.warmup_max
        assert 0.0 <= trial_cfg.weight_decay <= cfg.hpo.weight_decay_max
        assert cfg.hpo.epochs_min <= trial_cfg.epochs <= cfg.hpo.epochs_max
        assert trial_cfg.batch_size == cfg.batch_size  # fixed by the budget
        return 0.0

    study.optimize(objective, n_trials=3)


def test_tuned_config_requires_hpo_best() -> None:
    cfg = NLPConfig()
    with pytest.raises(ValueError, match="hpo stage"):
        tuned_config(cfg)
    best = HPOBest(
        learning_rate=3e-5,
        warmup_ratio=0.05,
        weight_decay=0.02,
        epochs=3,
        best_val_f1_macro=0.9,
    )
    tuned = tuned_config(cfg.model_copy(update={"hpo_best": best}))
    assert tuned.learning_rate == 3e-5
    assert tuned.epochs == 3
    assert tuned.model_name == cfg.model_name  # everything else untouched


def test_train_nn_reports_epochs_to_callback() -> None:
    """The on_epoch hook (used for Optuna pruning) fires once per epoch."""

    class _Tiny(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.emb = nn.Embedding(50, 8)
            self.head = nn.Linear(8, 4)

        def forward(
            self,
            input_ids: torch.Tensor,
            attention_mask: torch.Tensor | None = None,
            labels: torch.Tensor | None = None,
        ) -> Any:
            logits = self.head(self.emb(input_ids).mean(dim=1))
            out = SimpleNamespace(logits=logits, loss=None)
            if labels is not None:
                out.loss = nn.functional.cross_entropy(logits, labels)
            return out

    rng = np.random.RandomState(0)
    ds = Dataset.from_dict(
        {
            "text": ["x"] * 24,
            "input_ids": rng.randint(0, 50, size=(24, 8)).tolist(),
            "attention_mask": [[1] * 8 for _ in range(24)],
            "label": rng.randint(0, 4, size=24).tolist(),
        }
    )
    seen: list[tuple[int, float]] = []
    cfg = NLPConfig(batch_size=8, epochs=2, warmup_ratio=0.0, seed=1)
    train_nn(
        cfg,
        ds,
        ds,
        4,
        torch.device("cpu"),
        model=_Tiny(),
        on_epoch=lambda e, f1: seen.append((e, f1)),
    )
    assert [e for e, _ in seen] == [1, 2]
    assert all(0.0 <= f1 <= 1.0 for _, f1 in seen)


def test_select_tuned_run_picks_winner_and_persists(tmp_path: Path) -> None:
    y_true = [0, 1, 2, 3]
    y_pred_hpo = [0, 1, 2, 3]  # perfect
    y_pred_wave2 = [0, 1, 2, 2]  # one error
    run, record = select_tuned_run(y_true, y_pred_hpo, y_pred_wave2, tmp_path / "sel.json")
    assert run.name == "distilbert_tuned"
    assert record["winner"] == "hpo_retrained"
    assert record["candidates"]["hpo_retrained"]["f1_macro"] == 1.0
    persisted = json.loads((tmp_path / "sel.json").read_text())
    assert persisted["winner"] == "hpo_retrained"

    # flip quality: the wave-2 artifact must win when it scores higher
    _, record2 = select_tuned_run(y_true, y_pred_wave2, y_pred_hpo, tmp_path / "sel.json")
    assert record2["winner"] == "wave2_artifact"
