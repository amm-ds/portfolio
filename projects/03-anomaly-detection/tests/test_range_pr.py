"""Range-based PR sweep, PA%K, and the no-skill band (external evaluation P1)."""

import numpy as np
import pytest
from anomaly_detection.range_pr import band, interp_precision, pa_k, range_pr_area, range_pr_points


def _series(n: int = 400, n_windows: int = 2, seed: int = 0):
    """Synthetic test segment: uniform times + two labelled windows."""
    times = np.arange("2024-01-01", n, dtype="datetime64[h]")
    windows = [
        [str(times[100]), str(times[110])],
        [str(times[300]), str(times[310])],
    ]
    return times, windows


def test_perfect_scorer_sweeps_to_full_recall_with_precision_one():
    times, windows = _series()
    scores = np.zeros(400)
    scores[105] = 1.0  # inside window 1
    scores[305] = 1.0  # inside window 2
    recalls, precisions = range_pr_points(scores, times, windows, step_ns=3_600_000_000_000)
    assert recalls[-1] == pytest.approx(1.0)
    # the curve keeps the best precision at each recall: alerting exactly the
    # two spikes covers both windows with zero false positives, so the
    # envelope reaches (1, 1) — the all-alerts point (precision 2/380) is the
    # same recall with worse precision and is dropped by the envelope
    assert precisions[-1] == pytest.approx(1.0)
    # the high-threshold end starts from silence: recall 0, precision 1
    assert recalls[0] == pytest.approx(0.0)
    assert precisions[0] == pytest.approx(1.0)
    area = range_pr_area(scores, times, windows, step_ns=3_600_000_000_000)
    assert area == pytest.approx(1.0)


def test_no_skill_scores_sit_near_the_bottom():
    times, windows = _series(seed=3)
    rng = np.random.default_rng(7)
    scores = rng.random(400)
    area = range_pr_area(scores, times, windows, step_ns=3_600_000_000_000)
    # with 2 windows / 400 points the no-skill area is small; the exact value
    # is distribution-dependent, so bound it well below the perfect 1.0
    assert 0.0 <= area < 0.6


def test_pa_k_caps_alerts_and_reports_budget():
    times, windows = _series()
    scores = np.zeros(400)
    scores[105] = 1.0
    scores[305] = 1.0
    row = pa_k(scores, times, windows, step_ns=3_600_000_000_000, k_pct=1.0)
    assert row["alerts"] == 4  # 1% of 400, at least one
    assert row["range_recall"] == pytest.approx(1.0)
    assert row["range_precision"] == pytest.approx(0.5)
    tiny = pa_k(scores, times, windows, step_ns=3_600_000_000_000, k_pct=0.1)
    assert tiny["alerts"] == 1
    assert tiny["range_recall"] == pytest.approx(0.5)


def test_band_reports_mean_and_percentiles():
    def measure(seed: int) -> dict[str, float]:
        return {"range_pr_auc": float(seed) / 10, "pa_k_precision": 0.1, "pa_k_recall": 0.2}

    stats = band(range(10), measure)
    assert stats["range_pr_auc"]["mean"] == pytest.approx(0.45)
    # numpy interpolates percentiles linearly between the drawn values
    assert stats["range_pr_auc"]["p2.5"] == pytest.approx(0.0225)
    assert stats["range_pr_auc"]["p97.5"] == pytest.approx(0.8775)
    assert stats["pa_k_precision"]["mean"] == pytest.approx(0.1)


def test_interp_precision_plateaus_past_last_recall():
    grid = np.linspace(0, 1, 11)
    out = interp_precision(np.array([0.0, 0.5]), np.array([1.0, 0.4]), grid)
    assert out[0] == pytest.approx(1.0)
    assert out[5] == pytest.approx(0.4)
    assert out[-1] == pytest.approx(0.4)  # plateau, no extrapolation wobble


def test_empty_scores_return_degenerate_curve():
    recalls, precisions = range_pr_points(
        np.array([]), np.array([], dtype="datetime64[h]"), [], step_ns=1.0
    )
    assert list(recalls) == [0.0]
    assert list(precisions) == [1.0]
