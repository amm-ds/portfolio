"""Leakage-proof time-based cross-validation (playbook: random splits mask drift)."""

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TimeFold:
    """One train/validation split with an enforced embargo gap."""

    train_idx: np.ndarray
    val_idx: np.ndarray
    train_end: int
    val_start: int


class TimeSeriesCV:
    """Expanding-window time CV with a purged gap between train and validation.

    Guarantees (property-tested):
    - validation always strictly after training (+ gap),
    - folds are ordered and non-overlapping in validation,
    - no index appears in both train and validation of the same fold.
    """

    def __init__(self, n_splits: int = 5, gap: int = 0, min_train_size: int | None = None) -> None:
        if n_splits < 1:
            raise ValueError("n_splits must be >= 1")
        if gap < 0:
            raise ValueError("gap must be >= 0")
        self.n_splits = n_splits
        self.gap = gap
        self.min_train_size = min_train_size

    def split(self, n_samples: int) -> Iterator[TimeFold]:
        if n_samples < self.n_splits + self.gap + 2:
            raise ValueError(
                f"n_samples={n_samples} too small for n_splits={self.n_splits}, gap={self.gap}"
            )
        val_size = max(1, (n_samples - self.gap) // (self.n_splits + 1))
        train_end = n_samples - self.n_splits * val_size - self.gap
        if self.min_train_size is not None and train_end < self.min_train_size:
            raise ValueError(
                f"min_train_size={self.min_train_size} unreachable with {n_samples} samples"
            )
        idx = np.arange(n_samples)
        for k in range(self.n_splits):
            tr_end = train_end + k * val_size
            v_start = tr_end + self.gap
            v_end = v_start + val_size
            yield TimeFold(
                train_idx=idx[:tr_end].copy(),
                val_idx=idx[v_start:v_end].copy(),
                train_end=tr_end,
                val_start=v_start,
            )
