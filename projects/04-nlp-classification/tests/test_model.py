"""Model tests: baseline on toy data and the hand-written loop on random data."""

from pathlib import Path

import numpy as np
import torch
from datasets import Dataset  # type: ignore[import-untyped]
from nlp_classification.config import NLPConfig
from nlp_classification.model import (
    TrainingHistory,
    _macro_f1,
    evaluate_epoch,
    load_nn_state_dict,
    lr_at_step,
    make_loaders,
    predict_majority,
    predict_nn,
    predict_random_uniform,
    save_nn_state_dict,
    train_baseline,
    train_nn,
)
from torch import nn


class _TinyClassifier(nn.Module):
    """Minimal sequence classifier honoring the training-loop interface."""

    def __init__(self, vocab: int = 100, dim: int = 16, n_labels: int = 4) -> None:
        super().__init__()
        self.emb = nn.Embedding(vocab, dim)
        self.head = nn.Linear(dim, n_labels)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        labels: torch.Tensor | None = None,
    ) -> "_Output":
        pooled = self.emb(input_ids).mean(dim=1)
        logits = self.head(pooled)
        out = _Output(logits)
        if labels is not None:
            out.loss = nn.functional.cross_entropy(logits, labels)
        return out


class _Output:
    """Duck-typed stand-in for transformers' SequenceClassifierOutput."""

    def __init__(self, logits: torch.Tensor) -> None:
        self.logits = logits
        self.loss: torch.Tensor | None = None


def _cfg() -> NLPConfig:
    return NLPConfig(batch_size=8, epochs=2, train_samples=120, test_samples=100)


def _random_tokenized(n: int, max_length: int, n_labels: int, seed: int) -> Dataset:
    """Random tokenized rows: the training-loop contract, no text needed."""
    rng = np.random.RandomState(seed)
    return Dataset.from_dict(
        {
            "text": [f"row {i}" for i in range(n)],
            "input_ids": rng.randint(0, 100, size=(n, max_length)).tolist(),
            "attention_mask": [[1] * max_length for _ in range(n)],
            "label": rng.randint(0, n_labels, size=n).tolist(),
        }
    )


def test_lr_schedule_warmup_then_decay() -> None:
    # 100 total steps, 10 warmup: step 0 -> 0.1*lr ... step 9 -> lr, then decay
    assert lr_at_step(0, 100, 10, 1.0) == 0.1
    assert lr_at_step(9, 100, 10, 1.0) == 1.0
    assert lr_at_step(54, 100, 10, 1.0) == 0.5  # halfway past warmup
    assert lr_at_step(99, 100, 10, 1.0) == 0.0


def test_macro_f1_sanity() -> None:
    assert _macro_f1([0, 1, 2, 3], [0, 1, 2, 3], 4) == 1.0
    assert _macro_f1([0, 1], [1, 0], 2) == 0.0


def test_handwritten_loop_loss_decreases() -> None:
    """3 epochs x 4 batches of random data through the real loop: loss must drop."""
    cfg = NLPConfig(batch_size=8, epochs=3, warmup_ratio=0.0, seed=1)
    train_ds = _random_tokenized(n=32, max_length=8, n_labels=4, seed=0)
    val_ds = _random_tokenized(n=16, max_length=8, n_labels=4, seed=1)
    model = _TinyClassifier(n_labels=4)

    trained, history = train_nn(cfg, train_ds, val_ds, 4, torch.device("cpu"), model=model)
    # patience=1 may stop after epoch 2 on random data — that is the early-stop path
    assert 2 <= len(history.epochs) <= 3
    losses = [e.train_loss for e in history.epochs]
    assert losses[-1] < losses[0], f"loss did not decrease: {losses}"
    # the restored best model must be scorable
    preds = predict_nn(trained, val_ds, torch.device("cpu"), batch_size=8)
    assert len(preds) == len(val_ds)


def test_evaluate_epoch_reports_loss_and_f1() -> None:
    ds = _random_tokenized(n=16, max_length=8, n_labels=4, seed=2)
    model = _TinyClassifier(n_labels=4)
    cfg = NLPConfig(batch_size=8, train_samples=120, test_samples=100)
    _, val_loader = make_loaders(cfg, ds, ds)
    loss, f1 = evaluate_epoch(model, val_loader, torch.device("cpu"))
    assert loss >= 0.0
    assert 0.0 <= f1 <= 1.0


def test_nn_state_dict_roundtrip(tmp_path: Path) -> None:
    model = _TinyClassifier(n_labels=4)
    path = save_nn_state_dict(model, tmp_path / "tiny.pt")
    loaded = load_nn_state_dict(_TinyClassifier(n_labels=4), path, torch.device("cpu"))
    ds = _random_tokenized(n=8, max_length=8, n_labels=4, seed=3)
    a = predict_nn(model, ds, torch.device("cpu"), 4)
    b = predict_nn(loaded, ds, torch.device("cpu"), 4)
    assert (a == b).all()


def test_history_json_roundtrip(tmp_path: Path) -> None:
    history = TrainingHistory.from_records(
        [
            {
                "epoch": 1,
                "train_loss": 1.0,
                "val_loss": 1.1,
                "val_f1_macro": 0.5,
                "learning_rate": 1e-5,
            },
            {
                "epoch": 2,
                "train_loss": 0.7,
                "val_loss": 0.9,
                "val_f1_macro": 0.6,
                "learning_rate": 0.0,
            },
        ]
    )
    path = history.to_json(tmp_path / "history.json")
    reloaded = TrainingHistory.from_json(path)
    assert reloaded.best_epoch().epoch == 2
    assert reloaded.epochs[0].train_loss == 1.0


def test_baseline_fits_and_predicts(tiny_dataset: Dataset) -> None:
    cfg = _cfg()
    model = train_baseline(cfg, tiny_dataset)
    preds = model.predict(tiny_dataset["text"])
    assert len(preds) == len(tiny_dataset)
    # on the (easy, separable) toy fixture the baseline should beat chance
    acc = float(np.mean(np.asarray(preds) == np.asarray(tiny_dataset["label"])))
    assert acc > 0.5


def test_naive_baselines() -> None:
    """Majority = most frequent training class; random = seeded chance floor."""
    train_labels = [0, 0, 1, 2, 2, 2, 3]  # majority class is 2
    majority = predict_majority(train_labels, n_rows=5)
    assert (majority == 2).all()

    a = predict_random_uniform(200, n_labels=4, seed=7)
    b = predict_random_uniform(200, n_labels=4, seed=7)
    c = predict_random_uniform(200, n_labels=4, seed=8)
    assert (a == b).all() and not (a == c).all()
    assert set(np.unique(a)) <= {0, 1, 2, 3}
    # chance accuracy of uniform random over 4 balanced classes ≈ 0.25
    y = np.random.RandomState(0).randint(0, 4, size=200)
    assert abs(float(np.mean(a == y)) - 0.25) < 0.1
