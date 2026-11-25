"""Small, deterministic interval helpers shared by portfolio experiments."""

import math
from collections.abc import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]
Statistic = Callable[[FloatArray, FloatArray], float]


def wilson_interval(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Return the Wilson score interval for ``k`` successes in ``n`` trials."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("k must satisfy 0 <= k <= n")
    if z <= 0:
        raise ValueError("z must be positive")

    proportion = k / n
    denominator = 1.0 + z * z / n
    centre = proportion + z * z / (2.0 * n)
    half_width = z * math.sqrt(proportion * (1.0 - proportion) / n + z * z / (4.0 * n * n))
    return (
        max(0.0, (centre - half_width) / denominator),
        min(1.0, (centre + half_width) / denominator),
    )


def _paired_inputs(a: ArrayLike, b: ArrayLike) -> tuple[FloatArray, FloatArray]:
    left = np.asarray(a, dtype=np.float64)
    right = np.asarray(b, dtype=np.float64)
    if left.ndim != 1 or right.ndim != 1:
        raise ValueError("a and b must be one-dimensional")
    if left.shape != right.shape:
        raise ValueError("a and b must have the same length")
    if left.size == 0:
        raise ValueError("a and b must not be empty")
    return left, right


def _validate_resamples(n_resamples: int) -> None:
    if n_resamples <= 0:
        raise ValueError("n_resamples must be positive")


def _interval(point: float, draws: FloatArray) -> tuple[float, float, float]:
    lo, hi = np.quantile(draws, [0.025, 0.975])
    return point, float(lo), float(hi)


def paired_bootstrap(
    a: ArrayLike,
    b: ArrayLike,
    stat: Statistic,
    n_resamples: int = 2000,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Bootstrap ``stat(a, b)`` by resampling aligned rows with replacement."""
    left, right = _paired_inputs(a, b)
    _validate_resamples(n_resamples)
    point = float(stat(left, right))
    rng = np.random.default_rng(seed)
    draws = np.empty(n_resamples, dtype=np.float64)
    for index in range(n_resamples):
        rows = rng.integers(0, left.size, size=left.size)
        draws[index] = stat(left[rows], right[rows])
    return _interval(point, draws)


def cluster_bootstrap(
    a: ArrayLike,
    b: ArrayLike,
    clusters: ArrayLike,
    stat: Statistic,
    n_resamples: int = 2000,
    seed: int = 42,
    strata: ArrayLike | None = None,
) -> tuple[float, float, float]:
    """Bootstrap a paired statistic over intact clusters, optionally by stratum.

    Within each stratum, clusters are sampled with replacement until the
    original number of clusters is reached. All rows from a sampled cluster
    enter the draw together, including repeated copies of that cluster.
    """
    left, right = _paired_inputs(a, b)
    _validate_resamples(n_resamples)
    cluster_ids = np.asarray(clusters)
    if cluster_ids.ndim != 1 or cluster_ids.size != left.size:
        raise ValueError("clusters must be one-dimensional and aligned with a and b")
    stratum_ids = np.zeros(left.size, dtype=np.int64) if strata is None else np.asarray(strata)
    if stratum_ids.ndim != 1 or stratum_ids.size != left.size:
        raise ValueError("strata must be one-dimensional and aligned with a and b")

    groups: list[list[NDArray[np.int64]]] = []
    for stratum in np.unique(stratum_ids):
        stratum_rows = np.flatnonzero(stratum_ids == stratum)
        stratum_clusters = cluster_ids[stratum_rows]
        groups.append(
            [stratum_rows[stratum_clusters == cluster] for cluster in np.unique(stratum_clusters)]
        )
    for cluster in np.unique(cluster_ids):
        if np.unique(stratum_ids[cluster_ids == cluster]).size != 1:
            raise ValueError("each cluster must belong to exactly one stratum")

    point = float(stat(left, right))
    rng = np.random.default_rng(seed)
    draws = np.empty(n_resamples, dtype=np.float64)
    for draw_index in range(n_resamples):
        selected_groups: list[NDArray[np.int64]] = []
        for stratum_groups in groups:
            choices = rng.integers(0, len(stratum_groups), size=len(stratum_groups))
            selected_groups.extend(stratum_groups[choice] for choice in choices)
        rows = np.concatenate(selected_groups)
        draws[draw_index] = stat(left[rows], right[rows])
    return _interval(point, draws)
