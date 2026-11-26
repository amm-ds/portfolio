"""Official NAB scoring math, vendored from numenta/NAB (MIT license).

Ported from ``nab/sweeper.py``, ``nab/optimizer.py``, ``nab/scorer.py``, and
``nab/runner.py`` at upstream commit
``ea702d75cc2258d9d7dd35ca8e5e2539d71f3140``. See ``VENDORED.md`` beside this
file for provenance and ``LICENSE-nab.txt`` for the license text. The port is
pure Python 3 + stdlib: the upstream pandas/multiprocessing plumbing becomes
plain sequences, identifiers are snake_case, and every function names its
upstream source. The scoring math is line-for-line faithful.

NAB scoring in one paragraph: every scored timestamp gets a *sweep score* —
an in-window detection earns up to ``tpWeight`` (sigmoid-scaled by how early
it lands in the window), a detection outside any window costs down to
``-fpWeight`` (sigmoid-scaled by distance past the previous window). A
threshold turns per-point scores into detections; each window's credit is the
best active point inside it and every window starts at ``-fnWeight`` (missed).
Threshold optimization pools all series and keeps the threshold with the
highest total (upstream ``optimizeThreshold``). The published score normalizes
against the null (constant-score) detector and the analytic perfect score,
``100 * (raw - null) / (perfect - null)`` (upstream ``Runner.normalize``).

The sweep only ever compares scores and thresholds at observed values, so the
score is invariant to strictly monotonic transforms of the detector's raw
scores; upstream detectors emit [0, 1] but nothing in the math requires it.
The one constant that must dominate every detector score is the sweep's
initial threshold ``1.1`` (upstream ``calcScoreByThreshold``); callers must
verify ``max(score) < 1.1`` (IsolationForest ``-decision_function`` values
are ~[-0.5, 0.5]).
"""

from collections.abc import Hashable, Sequence
from math import exp, floor
from typing import NamedTuple

# The sweep records its first (all-missed) row at this threshold; it must sit
# above every detector score (upstream hard-codes 1.1 in calcScoreByThreshold).
INITIAL_THRESHOLD = 1.1

# Upstream null detector (nab/detectors/null/null_detector.py) emits a
# constant 0.5 for every record.
NULL_SCORE = 0.5


class AnomalyPoint(NamedTuple):
    """One scored timestamp (upstream ``AnomalyPoint``)."""

    timestamp: Hashable
    anomalyScore: float
    sweepScore: float
    windowName: str | None


class ThresholdScore(NamedTuple):
    """Score and point counts at one threshold (upstream ``ThresholdScore``)."""

    threshold: float
    score: float
    tp: int
    tn: int
    fp: int
    fn: int
    total: int


class SeriesInput(NamedTuple):
    """One series' scored span: per-timestamp detector scores + windows.

    ``timestamps`` must be unique and sorted; every window bound must be an
    element of ``timestamps`` (upstream validates the same in
    ``CorpusLabel.getWindows``).
    """

    name: str
    timestamps: Sequence[Hashable]
    scores: Sequence[float]
    windows: Sequence[tuple[Hashable, Hashable]]


class CorpusTotals(NamedTuple):
    """Corpus-level totals at one threshold (upstream ``scoreCorpus`` Totals row)."""

    score: float
    tp: int
    tn: int
    fp: int
    fn: int
    total: int


def sigmoid(x: float) -> float:
    """Standard sigmoid function (upstream ``sigmoid``)."""
    return 1 / (1 + exp(-x))


def scaled_sigmoid(relative_position_in_window: float) -> float:
    """Scaled sigmoid of the relative position within a window.

    Port of upstream ``scaledSigmoid``. A relative position of -1.0 is the far
    left edge of the anomaly window and maps to ``2*sigmoid(5) - 1`` (the
    maximum true-positive credit); 0.0 is the right edge and maps to 0.0;
    positions past the right edge map to increasingly negative values, capped
    at -1.0 beyond position 3.0.
    """
    if relative_position_in_window > 3.0:
        # FP well behind window
        return -1.0
    return 2 * sigmoid(-5 * relative_position_in_window) - 1.0


def prep_anomaly_list_for_scoring(
    input_anomaly_list: Sequence[AnomalyPoint],
) -> list[AnomalyPoint]:
    """Sort by anomaly score (desc) and drop probationary rows.

    Port of upstream ``prepAnomalyListForScoring``. The sort is stable, as
    upstream's ``sorted`` is; ties cannot affect any recorded threshold row
    because rows are written only when the score value changes.
    """
    return sorted(
        [x for x in input_anomaly_list if x.windowName != "probationary"],
        key=lambda x: x.anomalyScore,
        reverse=True,
    )


class Sweeper:
    """Per-point sweep scores and threshold sweep (upstream ``Sweeper``)."""

    def __init__(
        self,
        probation_percent: float = 0.15,
        cost_matrix: dict[str, float] | None = None,
    ) -> None:
        self.probation_percent = probation_percent
        self.tp_weight = 0.0
        self.fp_weight = 0.0
        self.fn_weight = 0.0
        if cost_matrix is not None:
            self.set_cost_matrix(cost_matrix)

    def set_cost_matrix(self, cost_matrix: dict[str, float]) -> None:
        """Upstream ``setCostMatrix`` (tnWeight is unused by the sweep)."""
        self.tp_weight = cost_matrix["tpWeight"]
        self.fp_weight = cost_matrix["fpWeight"]
        self.fn_weight = cost_matrix["fnWeight"]

    def _get_probationary_length(self, num_rows: int) -> float:
        """Port of upstream ``_getProbationaryLength`` (capped at 15% of 5000)."""
        return min(
            floor(self.probation_percent * num_rows),
            self.probation_percent * 5000,
        )

    def _prepare_score_by_threshold_parts(
        self, input_anomaly_list: Sequence[AnomalyPoint]
    ) -> dict[str, float]:
        """Port of upstream ``_prepareScoreByThresholdParts``: every window
        starts as a miss (``-fnWeight``); the ``fp`` part starts at 0."""
        score_parts = {"fp": 0.0}
        for row in input_anomaly_list:
            name = row.windowName
            if name is not None and name != "probationary":
                score_parts[name] = -self.fn_weight
        return score_parts

    def calc_sweep_score(
        self,
        timestamps: Sequence[Hashable],
        anomaly_scores: Sequence[float],
        window_limits: Sequence[tuple[Hashable, Hashable]],
        data_set_name: str,
    ) -> list[AnomalyPoint]:
        """Per-point sweep scores for one series (upstream ``calcSweepScore``).

        ``window_limits`` must be sorted by start and non-overlapping, and
        every bound must appear in ``timestamps`` (upstream enforces the same
        via ``list.index``). Window widths follow upstream: single-point
        windows make the false-positive denominator zero, as upstream.
        """
        if len(timestamps) != len(anomaly_scores):
            raise ValueError("timestamps and anomalyScores should not be different lengths!")
        timestamps = list(timestamps)
        window_limits = list(window_limits)  # copy because we mutate this list
        # First-occurrence index per timestamp: upstream calls
        # ``timestamps.index(bound)``; with unique timestamps the two agree.
        index_of: dict[Hashable, int] = {}
        for idx, ts in enumerate(timestamps):
            if ts not in index_of:
                index_of[ts] = idx
        for start, end in window_limits:
            if start not in index_of or end not in index_of:
                raise ValueError(
                    f"window bound not in timestamps for {data_set_name}: {(start, end)}"
                )
        anomaly_list: list[AnomalyPoint] = []

        # One-time config variables
        max_tp = scaled_sigmoid(-1.0)
        probationary_length = self._get_probationary_length(len(timestamps))

        # Iteration variables - these update as we iterate through the data
        cur_window_limits: tuple[Hashable, Hashable] | None = None
        cur_window_name: str | None = None
        cur_window_width = 0.0
        cur_window_right_index = 0
        prev_window_width: float | None = None
        prev_window_right_index: int | None = None

        for i, (cur_time, cur_anomaly) in enumerate(zip(timestamps, anomaly_scores, strict=True)):
            # If not in a window, check if we've just entered one
            if window_limits and cur_time == window_limits[0][0]:
                cur_window_limits = window_limits.pop(0)
                cur_window_name = f"{data_set_name}|{cur_window_limits[0]}"
                cur_window_right_index = index_of[cur_window_limits[1]]
                cur_window_width = float(
                    cur_window_right_index - index_of[cur_window_limits[0]] + 1
                )

            # If in a window, score as if true positive
            if cur_window_limits is not None:
                position_in_window = -(cur_window_right_index - i + 1) / cur_window_width
                unweighted_score = scaled_sigmoid(position_in_window)
                weighted_score = unweighted_score * self.tp_weight / max_tp

            # If outside a window, score as if false positive
            else:
                if prev_window_right_index is None:
                    # No preceding window, so score as if we were just really
                    # far away from the nearest window.
                    unweighted_score = -1.0
                else:
                    numerator = abs(prev_window_right_index - i)
                    denominator = float(prev_window_width - 1) if prev_window_width else 0.0
                    position_past_window = numerator / denominator
                    unweighted_score = scaled_sigmoid(position_past_window)
                weighted_score = unweighted_score * self.fp_weight

            point_window_name = cur_window_name if i >= probationary_length else "probationary"

            anomaly_list.append(
                AnomalyPoint(cur_time, cur_anomaly, weighted_score, point_window_name)
            )

            # If at right-edge of window, exit window. This happens after
            # processing the current point and appending it to the list.
            if cur_window_limits is not None and cur_time == cur_window_limits[1]:
                prev_window_right_index = i
                prev_window_width = cur_window_width
                cur_window_limits = None
                cur_window_name = None
                cur_window_width = 0.0
                cur_window_right_index = 0

        return anomaly_list

    def calc_score_by_threshold(self, anomaly_list: Sequence[AnomalyPoint]) -> list[ThresholdScore]:
        """Score at every candidate threshold (upstream ``calcScoreByThreshold``)."""
        scorable_list = prep_anomaly_list_for_scoring(anomaly_list)
        score_parts = self._prepare_score_by_threshold_parts(scorable_list)
        scores_by_threshold: list[ThresholdScore] = []

        # The current threshold above which an anomaly score is considered an
        # anomaly prediction. Starts above 1.0 so that all points are skipped,
        # which gives the full false-negative score.
        cur_threshold = INITIAL_THRESHOLD

        # Initialize counts: every point in a window is a false negative,
        # every point outside a window is a true negative.
        tn = sum(1 if x.windowName is None else 0 for x in scorable_list)
        fn = sum(1 if x.windowName is not None else 0 for x in scorable_list)
        tp = 0
        fp = 0

        # Iterate through every data point, starting with the highest anomaly
        # scores. Whenever we reach a new anomaly score, save the current
        # score and begin calculating the score for the new, lower threshold.
        for data_point in scorable_list:
            if data_point.anomalyScore != cur_threshold:
                cur_score = sum(score_parts.values())
                total_count = tp + tn + fp + fn
                scores_by_threshold.append(
                    ThresholdScore(cur_threshold, cur_score, tp, tn, fp, fn, total_count)
                )
                cur_threshold = data_point.anomalyScore

            # Adjust counts
            if data_point.windowName is not None:
                tp += 1
                fn -= 1
            else:
                fp += 1
                tn -= 1

            if data_point.windowName is None:
                score_parts["fp"] += data_point.sweepScore
            else:
                score_parts[data_point.windowName] = max(
                    score_parts[data_point.windowName],
                    data_point.sweepScore,
                )

        # Make sure to save the score for the last threshold
        cur_score = sum(score_parts.values())
        total_count = tp + tn + fp + fn
        scores_by_threshold.append(
            ThresholdScore(cur_threshold, cur_score, tp, tn, fp, fn, total_count)
        )
        return scores_by_threshold

    def score_data_set(
        self,
        timestamps: Sequence[Hashable],
        anomaly_scores: Sequence[float],
        window_limits: Sequence[tuple[Hashable, Hashable]],
        data_set_name: str,
        threshold: float,
    ) -> tuple[list[float], ThresholdScore]:
        """Score one series at a fixed threshold (upstream ``scoreDataSet``).

        Returns the per-row sweep scores and the ``ThresholdScore`` whose
        threshold matches ``threshold`` (or, failing an exact match, the next
        higher threshold's row — upstream's fallback).
        """
        anomaly_list = self.calc_sweep_score(
            timestamps, anomaly_scores, window_limits, data_set_name
        )
        scores_by_threshold = self.calc_score_by_threshold(anomaly_list)

        matching_row = None
        prev_row = None
        for threshold_score in scores_by_threshold:
            if threshold_score.threshold == threshold:
                matching_row = threshold_score
                break
            elif threshold_score.threshold < threshold:
                matching_row = prev_row
                break
            prev_row = threshold_score
        if matching_row is None:
            raise ValueError(f"no threshold row at or above {threshold} for {data_set_name}")

        return ([x.sweepScore for x in anomaly_list], matching_row)


def optimize_threshold(
    series: Sequence[SeriesInput],
    cost_matrix: dict[str, float],
    probation_percent: float = 0.0,
) -> ThresholdScore:
    """Best (threshold, score) over the pooled corpus (upstream ``optimizeThreshold``).

    Pools every series' sweep points, sweeps all candidate thresholds, and
    returns the highest-scoring row. Upstream breaks ties by taking the first
    row of a stable descending sort, i.e. the highest threshold among equals;
    the same order is kept here.
    """
    sweeper = Sweeper(probation_percent=probation_percent, cost_matrix=cost_matrix)
    all_anomaly_rows: list[AnomalyPoint] = []
    for s in series:
        all_anomaly_rows.extend(sweeper.calc_sweep_score(s.timestamps, s.scores, s.windows, s.name))
    scores_by_threshold = sweeper.calc_score_by_threshold(all_anomaly_rows)
    return sorted(scores_by_threshold, key=lambda x: x.score, reverse=True)[0]


def score_corpus(
    threshold: float,
    series: Sequence[SeriesInput],
    cost_matrix: dict[str, float],
    probation_percent: float = 0.0,
) -> tuple[CorpusTotals, dict[str, ThresholdScore]]:
    """Corpus totals at one threshold (upstream ``scoreCorpus`` Totals row).

    Returns the summed totals plus the per-series ``ThresholdScore`` rows.
    """
    sweeper = Sweeper(probation_percent=probation_percent, cost_matrix=cost_matrix)
    per_series: dict[str, ThresholdScore] = {}
    score = 0.0
    tp = tn = fp = fn = total = 0
    for s in series:
        _, row = sweeper.score_data_set(s.timestamps, s.scores, s.windows, s.name, threshold)
        per_series[s.name] = row
        score += row.score
        tp += row.tp
        tn += row.tn
        fp += row.fp
        fn += row.fn
        total += row.total
    return CorpusTotals(score, tp, tn, fp, fn, total), per_series


def perfect_score_possible(tp_count: int, tp_weight: float) -> float:
    """Analytic perfect score (upstream ``Runner.normalize``): each window's
    best possible credit is ``tpWeight``, so perfect is ``tpCount * tpWeight``."""
    return tp_count * tp_weight


def normalized_score(raw_score: float, null_raw_score: float, perfect_raw_score: float) -> float:
    """NAB's published normalization (upstream ``Runner.normalize``):

    ``100 * (raw - null) / (perfect - null)`` — the null detector scores 0 and
    the analytic perfect detector scores 100 by construction.
    """
    return 100 * (raw_score - null_raw_score) / (perfect_raw_score - null_raw_score)


def null_detector_scores(n_points: int) -> list[float]:
    """Constant-score baseline (upstream ``NullDetector``: 0.5 for every record)."""
    return [NULL_SCORE] * n_points


def perfect_detector_scores(
    timestamps: Sequence[Hashable], windows: Sequence[tuple[Hashable, Hashable]]
) -> list[float]:
    """Perfect-detector scores per NAB's definition of the perfect baseline:
    fire the maximum score (1.0) exactly at each window's first timestamp and
    0.0 elsewhere, so every window earns its full ``tpWeight`` and no false
    positives fire. Upstream computes the same value analytically
    (``perfect_score_possible``); running these scores through the sweep must
    reproduce it, which the sanity gate checks.
    """
    starts = {start for start, _ in windows}
    return [1.0 if ts in starts else 0.0 for ts in timestamps]
