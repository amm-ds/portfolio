"""Intermittent-demand statistical methods and ADI/CV² classification.

The UCI panel is ~89% zero-demand days, so the classical intermittent-demand
toolkit (Croston family) is a first-class citizen of the multi-step track, not
an afterthought:

- **Croston** (1972): separate simple exponential smoothing of the non-zero
  demand *sizes* and the inter-demand *intervals*; forecast = size/interval.
- **SBA** (Syntetos-Boylan approximation): Croston scaled by ``1 - alpha/2`` —
  the standard bias correction.
- **TSB** (Teunter-Syntetos-Babai): smooth the demand *probability* every
  period and the demand *size* on demand periods only; forecast = p·z. Unlike
  Croston/SBA it reacts when a series goes quiet (the probability decays).

All three are flat ``h``-step forecasts (the standard convention for
intermittent methods): one value per series, constant across the window.
Each is pure (stateless, no RNG) so results are deterministic and the
recursions are unit-tested against hand-computed cases.

**Classification** follows the Syntetos-Boylan quadrants on ADI (average
inter-demand interval) and CV² (squared coefficient of variation), computed
over the full panel history per series:

- ADI < 1.32 and CV² < 0.49 → ``smooth``
- ADI < 1.32 and CV² ≥ 0.49 → ``erratic``
- ADI ≥ 1.32 and CV² < 0.49 → ``intermittent``
- ADI ≥ 1.32 and CV² ≥ 0.49 → ``lumpy``

The routing rule (multi-step track): series in the ``intermittent``/``lumpy``
quadrants (ADI ≥ 1.32) are routed to the best *statistical* method, chosen on
the selection origins only; ``smooth``/``erratic`` series go to the direct
per-horizon boosted model.
"""

from typing import Any

import numpy as np

# Syntetos-Boylan cutoffs (classical intermittent-demand literature).
ADI_THRESHOLD = 1.32
CV2_THRESHOLD = 0.49

CLASSES = ("smooth", "erratic", "intermittent", "lumpy")
# Classes routed to statistical methods on the multi-step track.
SPARSE_CLASSES = ("intermittent", "lumpy")

# Default SES smoothing constant for the Croston family. Fixed (not estimated)
# so forecasts are deterministic and hand-testable; documented in DESIGN.md.
ALPHA = 0.1


def classify_demand(y: np.ndarray) -> dict[str, Any]:
    """ADI, CV² and the Syntetos-Boylan quadrant for one demand series.

    ADI = n_periods / n_nonzero (mean gap between demand periods; a fully
    zero series gets ADI = n_periods — maximally intermittent). CV² uses the
    population variance over the mean²; a zero-mean series gets CV² = inf.
    """
    y = np.asarray(y, dtype=float)
    n = int(y.size)
    n_nonzero = int(np.count_nonzero(y))
    adi = float(n / n_nonzero) if n_nonzero else float(n)
    mean = float(y.mean()) if n else 0.0
    cv2 = float(np.var(y) / mean**2) if mean > 0 else float("inf")
    if adi < ADI_THRESHOLD and cv2 < CV2_THRESHOLD:
        cls = "smooth"
    elif adi < ADI_THRESHOLD:
        cls = "erratic"
    elif cv2 < CV2_THRESHOLD:
        cls = "intermittent"
    else:
        cls = "lumpy"
    return {"adi": adi, "cv2": cv2, "class": cls}


def classify_panel(units: np.ndarray, series_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Per-series ADI/CV² classes for a (n_dates x n_series) units matrix."""
    return {sid: classify_demand(units[:, i]) for i, sid in enumerate(series_ids)}


def _ses(values: np.ndarray, alpha: float) -> float:
    """Simple exponential smoothing: level seeded at the first value."""
    level = float(values[0])
    for v in values[1:]:
        level = alpha * float(v) + (1.0 - alpha) * level
    return level


def _croston_parts(y: np.ndarray, alpha: float) -> tuple[float, float] | None:
    """Smoothed demand size ``z`` and inter-demand interval ``p``.

    Returns None when the series has no demand in the training window
    (forecast is identically zero — no smoothing constant can fix that).
    """
    idx = np.flatnonzero(y)
    if idx.size == 0:
        return None
    sizes = y[idx]
    intervals = np.diff(idx).astype(float)
    intervals = np.concatenate(([float(idx[0] + 1)], intervals))
    z = _ses(sizes, alpha)
    p = _ses(intervals, alpha)
    return z, p


def croston_forecast(y: np.ndarray, horizon: int, alpha: float = ALPHA) -> np.ndarray:
    """Flat Croston h-step forecast: SES(size) / SES(interval)."""
    parts = _croston_parts(y, alpha)
    if parts is None:
        return np.zeros(horizon)
    z, p = parts
    value = z / p if p > 0 else 0.0
    return np.full(horizon, value)


def sba_forecast(y: np.ndarray, horizon: int, alpha: float = ALPHA) -> np.ndarray:
    """Syntetos-Boylan approximation: Croston x (1 - alpha/2)."""
    return croston_forecast(y, horizon, alpha) * (1.0 - alpha / 2.0)


def tsb_forecast(
    y: np.ndarray, horizon: int, alpha_d: float = ALPHA, alpha_p: float = ALPHA
) -> np.ndarray:
    """Teunter-Syntetos-Babai: smooth demand probability and demand size.

    The probability level updates every period (so it decays when a series
    goes quiet); the size level updates on demand periods only. Both levels
    are seeded from the first period (probability indicator) and the first
    non-zero demand (size) respectively.
    """
    y = np.asarray(y, dtype=float)
    if y.size == 0 or not np.any(y):
        return np.zeros(horizon)
    p = 1.0 if y[0] > 0 else 0.0
    nonzero = y[y > 0]
    z = float(nonzero[0])
    for t in range(1, y.size):
        p = alpha_p * (1.0 if y[t] > 0 else 0.0) + (1.0 - alpha_p) * p
        if y[t] > 0:
            z = alpha_d * float(y[t]) + (1.0 - alpha_d) * z
    return np.full(horizon, p * z)


#: Statistical candidates eligible for sparse-series routing (multi-step track).
STATISTICAL_METHODS = ("zero", "seasonal_naive", "croston", "sba", "tsb")


def statistical_forecast(method: str, y: np.ndarray, horizon: int) -> np.ndarray:
    """Dispatch one statistical method to a flat ``horizon``-step forecast.

    ``seasonal_naive`` is NOT flat — it is handled by the multi-step engine
    (its direct h-step value depends on the horizon position), so this
    dispatcher covers only the flat methods used by sparse-series routing.
    """
    if method == "zero":
        return np.zeros(horizon)
    if method == "croston":
        return croston_forecast(y, horizon)
    if method == "sba":
        return sba_forecast(y, horizon)
    if method == "tsb":
        return tsb_forecast(y, horizon)
    raise ValueError(f"not a flat statistical method: {method!r}")
