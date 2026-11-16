"""Regression metrics + paired row/block bootstrap CIs for the frozen test window.

MAPE guards its denominator (hourly counts can be 0; ``max(y, 1)``) — the
guard is part of the metric definition so the number is never NaN-driven.
"""

from dataclasses import dataclass

import numpy as np


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean absolute percentage error, % — denominator floored at 1 rental."""
    denom = np.maximum(np.abs(y_true), 1.0)
    return float(np.mean(np.abs(y_true - y_pred) / denom) * 100.0)


@dataclass(frozen=True)
class BootstrapCI:
    """Percentile CI on the paired per-resample metric delta (champion - floor
    style: positive = champion better when delta = floor_mae - champion_mae)."""

    point: float
    lo: float
    hi: float
    n_boot: int
    significant_95: bool

    def to_dict(self) -> dict[str, float | int | bool]:
        return {
            "point": self.point,
            "lo": self.lo,
            "hi": self.hi,
            "n_boot": self.n_boot,
            "significant_95": self.significant_95,
        }


def paired_bootstrap_deltas(
    y_true: np.ndarray,
    pred_champion: np.ndarray,
    pred_floor: np.ndarray,
    n_boot: int,
    seed: int,
) -> tuple[BootstrapCI, np.ndarray]:
    """Paired per-resample MAE deltas (floor - champion) and their percentile CI.

    Paired resampling keeps the comparison per-row correlated (same hours
    resampled together), so the CI prices row noise, not data volume.
    """
    rng = np.random.default_rng(seed)
    n = len(y_true)
    floor_err = np.abs(y_true - pred_floor)
    champion_err = np.abs(y_true - pred_champion)
    deltas = np.empty(n_boot)
    for b in range(n_boot):
        take = rng.integers(0, n, size=n)
        deltas[b] = float(np.mean(floor_err[take]) - np.mean(champion_err[take]))
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    ci = BootstrapCI(
        point=float(np.mean(floor_err) - np.mean(champion_err)),
        lo=float(lo),
        hi=float(hi),
        n_boot=n_boot,
        significant_95=bool(lo > 0.0),
    )
    return ci, deltas


def paired_block_bootstrap_deltas(
    y_true: np.ndarray,
    pred_champion: np.ndarray,
    pred_floor: np.ndarray,
    n_boot: int,
    seed: int,
    block_size: int,
) -> tuple[BootstrapCI, np.ndarray]:
    """Paired non-overlapping block bootstrap for serially dependent hours.

    Blocks stay intact and use the same positions for both models. The test
    window contains whole weeks, so day (24) and week (168) blocks divide it.
    """
    n = len(y_true)
    if block_size <= 0 or n == 0 or n % block_size != 0:
        raise ValueError("block_size must be positive and divide the ordered sample length")
    rng = np.random.default_rng(seed)
    floor_err = np.abs(y_true - pred_floor)
    champion_err = np.abs(y_true - pred_champion)
    starts = np.arange(0, n, block_size)
    deltas = np.empty(n_boot)
    for b in range(n_boot):
        blocks = rng.choice(starts, size=len(starts), replace=True)
        take = np.concatenate([np.arange(start, start + block_size) for start in blocks])
        deltas[b] = float(np.mean(floor_err[take]) - np.mean(champion_err[take]))
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    ci = BootstrapCI(
        point=float(np.mean(floor_err) - np.mean(champion_err)),
        lo=float(lo),
        hi=float(hi),
        n_boot=n_boot,
        significant_95=bool(lo > 0.0),
    )
    return ci, deltas


def paired_bootstrap_mae_delta(
    y_true: np.ndarray,
    pred_champion: np.ndarray,
    pred_floor: np.ndarray,
    n_boot: int,
    seed: int,
) -> BootstrapCI:
    """95% percentile CI on MAE(floor) - MAE(champion) over paired resamples."""
    ci, _ = paired_bootstrap_deltas(y_true, pred_champion, pred_floor, n_boot, seed)
    return ci
