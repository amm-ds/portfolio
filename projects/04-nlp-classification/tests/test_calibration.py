"""Calibration tests: ECE properties, temperature recovery, probability shape."""

import numpy as np
import pytest
import torch
from datasets import Dataset  # type: ignore[import-untyped]
from nlp_classification.calibration import (
    expected_calibration_error,
    fit_temperature,
)
from nlp_classification.model import predict_proba_nn
from torch import nn


class _FixedLogits(nn.Module):
    """Stub model returning preset logits (ignores its inputs)."""

    def __init__(self, logits: torch.Tensor) -> None:
        super().__init__()
        self._logits = logits

    def forward(self, input_ids, attention_mask=None, labels=None):
        from types import SimpleNamespace

        batch = input_ids.shape[0]
        reps = int(np.ceil(batch / len(self._logits)))
        out = self._logits.repeat(reps, 1)[:batch]
        return SimpleNamespace(logits=out)


def _toy_tokenized(n: int, vocab: int = 20, max_length: int = 6) -> Dataset:
    rng = np.random.RandomState(0)
    return Dataset.from_dict(
        {
            "text": ["x"] * n,
            "input_ids": rng.randint(0, vocab, size=(n, max_length)).tolist(),
            "attention_mask": [[1] * max_length for _ in range(n)],
            "label": rng.randint(0, 4, size=n).tolist(),
        }
    )


def test_ece_perfect_and_overconfident() -> None:
    labels = np.array([0, 1, 2, 3])
    perfect = np.eye(4)[labels]  # conf 1.0, always right
    assert expected_calibration_error(perfect, labels) == 0.0

    overconfident_wrong = np.eye(4)[np.array([1, 0, 3, 2])]  # conf 1.0, always wrong
    assert expected_calibration_error(overconfident_wrong, labels) == pytest.approx(1.0)


def test_ece_miscalibrated_is_positive() -> None:
    labels = np.array([0, 0, 1, 1])
    # always predicts class 0 with a middling confidence -> acc/conf gap
    probs = np.array([[0.6, 0.4], [0.6, 0.4], [0.6, 0.4], [0.6, 0.4]])
    ece = expected_calibration_error(probs, labels, n_bins=5)
    assert ece > 0.0


def test_temperature_recovers_known_scale() -> None:
    """Logits generated at a true temperature must be recovered by the fit."""
    rng = np.random.RandomState(1)
    base_logits = torch.tensor(rng.normal(0, 2, size=(256, 4)), dtype=torch.float32)
    true_t = 2.5
    true_probs = torch.softmax(base_logits / true_t, dim=-1)
    labels = torch.multinomial(true_probs, 1).squeeze(1)
    model = _FixedLogits(base_logits)
    ds = _toy_tokenized(256)
    ds = ds.map(lambda _, i: {"label": int(labels[i])}, with_indices=True)

    fitted = fit_temperature(model, ds, torch.device("cpu"), batch_size=256, max_iter=80)
    assert fitted == pytest.approx(true_t, rel=0.3)  # finite-sample tolerance


def test_predict_proba_rows_sum_to_one() -> None:
    ds = _toy_tokenized(10)
    model = _FixedLogits(torch.tensor([[2.0, 0.0, 0.0, 0.0]]))
    probs = predict_proba_nn(model, ds, torch.device("cpu"), batch_size=4)
    assert probs.shape == (10, 4)
    assert np.allclose(probs.sum(axis=1), 1.0)


def test_ece_rejects_empty() -> None:
    with pytest.raises(ValueError):
        expected_calibration_error(np.zeros((0, 4)), np.zeros((0,), dtype=int))
