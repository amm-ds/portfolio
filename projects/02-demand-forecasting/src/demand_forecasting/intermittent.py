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
- **ma_28** (wave 22): the rolling 28-day mean of the training window, held
  flat across the window — the missing moving-average baseline the audit
  flagged (deterministic, pure).
- **ADIDA** (wave 22, ``adida_sba`` / ``adida_tsb``): aggregation-disaggregation
  intermittent-demand approach. The daily series is aggregated into
  non-overlapping 7-day buckets aligned to the END of the training window (so
  the forecast window o+1..o+14 is exactly 2 buckets); SBA (resp. TSB) is fit
  on the bucket-total series and forecasts the next bucket totals; each bucket
  total is disaggregated into daily values via the series' empirical
  within-week profile (the mean share of each position in the 7-day cycle over
  the training window — index-mod-7 of the daily panel IS the weekday offset,
  the panels are contiguous daily). Edge cases: an all-zero training profile
  gives an all-zero forecast; a positive bucket forecast under an all-zero
  profile spreads uniformly (bucket_total / 7 per day).

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

import math
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
#: Wave 22 adds the moving-average baseline (ma_28) and the ADIDA pair
#: (adida_sba / adida_tsb — temporal aggregation of the SBA/TSB estimators).
STATISTICAL_METHODS = (
    "zero",
    "seasonal_naive",
    "croston",
    "sba",
    "tsb",
    "ma_28",
    "adida_sba",
    "adida_tsb",
)


def ma_28_forecast(y: np.ndarray, horizon: int) -> np.ndarray:
    """Rolling 28-day mean of the training window, held flat across the window.

    Windows shorter than 28 days average over what exists. Pure and
    deterministic — the audit-flagged missing moving-average baseline.
    """
    y = np.asarray(y, dtype=float)
    if y.size == 0:
        return np.zeros(horizon)
    w = min(28, y.size)
    return np.full(horizon, float(y[-w:].mean()))


#: ADIDA bucket length (days). The window o+1..o+14 is exactly 2 buckets when
#: the aggregation is aligned to the end of the training window.
ADIDA_BUCKET_DAYS = 7


def _adida_disaggregate(
    bucket_fc: np.ndarray, profile: np.ndarray, horizon: int, bucket: int
) -> np.ndarray:
    """Disaggregate per-bucket totals into daily values via the within-week
    profile (position ``k`` of each bucket gets ``profile[k]`` — see
    :func:`adida_forecast` for the alignment). Pure math, hand-testable: a
    positive bucket total under an all-zero profile spreads uniformly
    (``total / bucket`` per day).
    """
    out = np.zeros(horizon)
    if not np.any(profile > 0):
        profile = np.full(bucket, 1.0 / bucket)
    for b, total in enumerate(bucket_fc):
        day_lo = b * bucket
        if day_lo >= horizon:
            break
        take = min(bucket, horizon - day_lo)
        out[day_lo : day_lo + take] = total * profile[:take]
    return out


def adida_forecast(
    method: str,
    y: np.ndarray,
    horizon: int,
    alpha: float = ALPHA,
    bucket: int = ADIDA_BUCKET_DAYS,
) -> np.ndarray:
    """ADIDA-style temporal aggregation around a flat intermittent estimator.

    ``method`` is the base estimator fit on the bucket series (``"sba"`` or
    ``"tsb"`` — both live in this module; Croston is deliberately not exposed
    since SBA dominates it here). Steps, all pure numpy:

    1. Aggregate the daily training series into non-overlapping ``bucket``-day
       buckets aligned to the END of the training window, so the forecast
       window (which abuts the origin) starts exactly on a bucket boundary.
    2. Fit the base estimator on the bucket-total series, forecast the next
       ``ceil(horizon / bucket)`` bucket totals (flat per bucket).
    3. Disaggregate via :func:`_adida_disaggregate` with the series' empirical
       within-week profile: position ``k`` of the 7-day cycle gets the share
       of training demand observed at days ``t ≡ (len + k) (mod 7)``
       (index-mod-7 is the weekday offset of a contiguous daily panel).

    Edge cases: an all-zero training profile → all-zero forecast; a positive
    bucket total under an all-zero profile → spread uniformly (bucket_total /
    bucket per day — unreachable through this entry point since a zero
    profile implies zero bucket totals, so the branch lives in the pure
    disaggregation helper where it is unit-tested); a training window shorter
    than one bucket → all-zero forecast.
    """
    y = np.asarray(y, dtype=float)
    if method not in ("sba", "tsb"):
        raise ValueError(f"ADIDA base method must be 'sba' or 'tsb', got {method!r}")
    n = int(y.size)
    n_bk = math.ceil(horizon / bucket)
    n_full = n // bucket
    if n_full == 0 or n_bk == 0 or not np.any(y > 0):
        return np.zeros(horizon)
    bucket_totals = y[n - n_full * bucket :].reshape(n_full, bucket).sum(axis=1)
    base = statistical_forecast(method, bucket_totals, n_bk, alpha=alpha)
    total = float(y.sum())
    pos = np.arange(n) % bucket
    profile = np.array([float(y[pos == (n + k) % bucket].sum()) / total for k in range(bucket)])
    return _adida_disaggregate(base, profile, horizon, bucket)


def statistical_forecast(
    method: str, y: np.ndarray, horizon: int, alpha: float = ALPHA
) -> np.ndarray:
    """Dispatch one statistical method to an ``horizon``-step forecast vector.

    ``seasonal_naive`` is NOT flat — it is handled by the multi-step engine
    (its direct h-step value depends on the horizon position), so this
    dispatcher covers the statistical methods used by sparse-series routing.
    ``ma_28`` is flat; the ADIDA pair varies within the window (the
    within-week profile disaggregation is day-specific).
    """
    if method == "zero":
        return np.zeros(horizon)
    if method == "croston":
        return croston_forecast(y, horizon, alpha)
    if method == "sba":
        return sba_forecast(y, horizon, alpha)
    if method == "tsb":
        return tsb_forecast(y, horizon, alpha)
    if method == "ma_28":
        return ma_28_forecast(y, horizon)
    if method == "adida_sba":
        return adida_forecast("sba", y, horizon, alpha)
    if method == "adida_tsb":
        return adida_forecast("tsb", y, horizon, alpha)
    raise ValueError(f"not a flat statistical method: {method!r}")
