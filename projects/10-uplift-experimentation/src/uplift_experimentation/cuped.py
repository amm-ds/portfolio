"""CUPED (Controlled-experiment Using Pre-Experiment Data) variance reduction.

The covariate (``log_history`` = log1p of prior-year spend) is pre-treatment,
so adjusting for it cannot bias the effect estimate; it only removes variance
explained by customer heterogeneity. Standard error of the effect shrinks by
roughly the same factor as the outcome's standard deviation.
"""

import numpy as np


def cuped_theta(y: np.ndarray, x: np.ndarray) -> float:
    """CUPED coefficient theta = cov(Y, X) / var(X), estimated on all rows."""
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    var_x = np.var(x, ddof=1)
    if var_x <= 0:
        raise ValueError("CUPED covariate has zero variance")
    return float(np.cov(y, x, ddof=1)[0, 1] / var_x)


def cuped_adjust(y: np.ndarray, x: np.ndarray, theta: float, x_mean: float) -> np.ndarray:
    """Adjusted outcome Y_adj = Y - theta * (X - mean(X)); mean is preserved."""
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    return y - theta * (x - x_mean)


def variance_reduction(y: np.ndarray, y_adj: np.ndarray) -> float:
    """1 - var(Y_adj) / var(Y): the fraction of outcome variance removed."""
    y = np.asarray(y, dtype=float)
    y_adj = np.asarray(y_adj, dtype=float)
    var_y = np.var(y, ddof=1)
    if var_y <= 0:
        raise ValueError("outcome has zero variance")
    return float(1.0 - np.var(y_adj, ddof=1) / var_y)


def effect_and_se(y: np.ndarray, treatment: np.ndarray) -> tuple[float, float]:
    """Difference in means and its standard error for a (adjusted) outcome."""
    y = np.asarray(y, dtype=float)
    treatment = np.asarray(treatment)
    y1 = y[treatment == 1]
    y0 = y[treatment == 0]
    ate = float(y1.mean() - y0.mean())
    se = float(np.sqrt(np.var(y1, ddof=1) / len(y1) + np.var(y0, ddof=1) / len(y0)))
    return ate, se
