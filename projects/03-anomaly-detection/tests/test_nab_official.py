"""Official NAB score tests: vendored-scorer math, sanity baselines, artifact.

The hand-computed fixtures pin the ported scoring math (sigmoid window
credit, per-window max, FP accumulation, probation filtering); the null and
perfect baselines pin NAB's normalization anchors (0 and 100); the artifact
test re-runs the vendored scorer on the committed scorer inputs and must
reproduce the committed ``nab_official_score.json`` exactly.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest
from anomaly_detection.config import PROJECT_ROOT, AnomalyConfig
from anomaly_detection.nab_official import (
    build_scoring_corpus,
    load_official_windows,
    load_profiles,
    score_profiles,
    verify_against_committed,
)
from anomaly_detection.vendor import nab_scorer

STANDARD = {"tpWeight": 1.0, "fnWeight": 1.0, "fpWeight": 0.11, "tnWeight": 1.0}

SCORE_JSON = PROJECT_ROOT / "reports" / "nab_official_score.json"
SCORES_JSON = PROJECT_ROOT / "reports" / "nab_official_scores.json"


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _ns(iso: str) -> int:
    return int(np.datetime64(iso).astype("datetime64[ns]").astype(np.int64))


def _scaled_sigmoid(pos: float) -> float:
    return -1.0 if pos > 3.0 else 2 * _sigmoid(-5 * pos) - 1.0


def _two_series_corpus() -> list[nab_scorer.SeriesInput]:
    """Tiny deterministic corpus: 2 series, 3 windows, mixed scores."""
    rng_scores_a = [0.9, 0.1, 0.2, 0.8, 0.3, 0.7, 0.95, 0.4, 0.6, 0.05] * 2
    a = nab_scorer.SeriesInput("fam/a", list(range(20)), rng_scores_a, [(5, 8)])
    b_scores = [0.15, 0.55, 0.25, 0.85, 0.35, 0.45, 0.65, 0.75, 0.05, 0.9, 0.8, 0.7, 0.3, 0.2, 0.1]
    b = nab_scorer.SeriesInput("fam/b", list(range(15)), b_scores, [(3, 4), (10, 12)])
    return [a, b]


def _baseline(corpus: list[nab_scorer.SeriesInput], kind: str) -> list[nab_scorer.SeriesInput]:
    out = []
    for s in corpus:
        if kind == "null":
            scores = nab_scorer.null_detector_scores(len(s.timestamps))
        else:
            scores = nab_scorer.perfect_detector_scores(s.timestamps, s.windows)
        out.append(nab_scorer.SeriesInput(s.name, s.timestamps, scores, s.windows))
    return out


def test_null_and_perfect_baselines_normalize_to_0_and_100() -> None:
    """NAB's sanity anchors through the full optimize -> score -> normalize path."""
    corpus = _two_series_corpus()
    null_corpus = _baseline(corpus, "null")
    perfect_corpus = _baseline(corpus, "perfect")
    tp_count = sum(len(s.windows) for s in corpus)
    for profile_name, cost_matrix in load_profiles().items():
        perfect_possible = nab_scorer.perfect_score_possible(tp_count, cost_matrix["tpWeight"])
        null_best = nab_scorer.optimize_threshold(null_corpus, cost_matrix)
        null_totals, _ = nab_scorer.score_corpus(null_best.threshold, null_corpus, cost_matrix)
        perf_best = nab_scorer.optimize_threshold(perfect_corpus, cost_matrix)
        perf_totals, _ = nab_scorer.score_corpus(perf_best.threshold, perfect_corpus, cost_matrix)
        # the perfect detector's raw score must equal NAB's analytic perfect
        assert perf_totals.score == pytest.approx(perfect_possible, abs=1e-12)
        null_norm = nab_scorer.normalized_score(
            null_totals.score, null_totals.score, perfect_possible
        )
        perf_norm = nab_scorer.normalized_score(
            perf_totals.score, null_totals.score, perfect_possible
        )
        assert null_norm == 0.0, profile_name
        assert perf_norm == pytest.approx(100.0, abs=1e-9), profile_name


def test_hand_computed_window_scoring() -> None:
    """Pin the sweep math on a 8-point series with one window at indices 2..4."""
    timestamps = list(range(8))
    scores = [0.9, 0.1, 0.9, 0.1, 0.9, 0.9, 0.1, 0.1]
    sweeper = nab_scorer.Sweeper(probation_percent=0.0, cost_matrix=STANDARD)
    points = sweeper.calc_sweep_score(timestamps, scores, [(2, 4)], "fam/a")

    max_tp = _scaled_sigmoid(-1.0)
    fp_w = STANDARD["fpWeight"]
    expected_sweep = [
        -1.0 * fp_w,  # i=0: before any window -> as-if-far FP credit
        -1.0 * fp_w,  # i=1: before any window
        _scaled_sigmoid(-1.0) / max_tp,  # i=2: window left edge -> full tpWeight
        _scaled_sigmoid(-2 / 3) / max_tp,  # i=3: position -(4-3+1)/3
        _scaled_sigmoid(-1 / 3) / max_tp,  # i=4: right edge -> 0 credit... scaled sigmoid(-1/3)
        _scaled_sigmoid(0.5) * fp_w,  # i=5: 1 step past, width 3 -> pos 1/2
        _scaled_sigmoid(1.0) * fp_w,  # i=6: pos 2/2
        _scaled_sigmoid(1.5) * fp_w,  # i=7: pos 3/2
    ]
    assert [p.sweepScore for p in points] == pytest.approx(expected_sweep, abs=1e-15)
    assert [p.windowName for p in points] == ["fam/a|2" if 2 <= i <= 4 else None for i in range(8)]

    rows = {r.threshold: r for r in sweeper.calc_score_by_threshold(points)}
    # threshold 1.1: nothing active -> the one window is missed, no FPs
    missed = rows[nab_scorer.INITIAL_THRESHOLD]
    assert missed.score == pytest.approx(-STANDARD["fnWeight"])
    assert (missed.tp, missed.fp, missed.fn, missed.tn) == (0, 0, 3, 5)
    # threshold 0.9: active = {0 (fp), 2 (tp), 4 (tp), 5 (fp)}; window credit = max
    at_09 = rows[0.9]
    expected = max(-STANDARD["fnWeight"], expected_sweep[2], expected_sweep[4])
    expected += expected_sweep[0] + expected_sweep[5]
    assert at_09.score == pytest.approx(expected, abs=1e-15)
    assert (at_09.tp, at_09.fp, at_09.fn, at_09.tn) == (2, 2, 1, 3)
    # threshold 0.1: everything active -> window keeps its best point, all FPs sum
    at_01 = rows[0.1]
    expected_all = max(expected_sweep[2], expected_sweep[3], expected_sweep[4])
    expected_all += sum(expected_sweep[i] for i in (0, 1, 5, 6, 7))
    assert at_01.score == pytest.approx(expected_all, abs=1e-15)
    assert (at_01.tp, at_01.fp, at_01.fn, at_01.tn) == (3, 5, 0, 0)


def test_probationary_points_are_excluded_from_scoring() -> None:
    """Upstream probation semantics: rows in the first `probation_percent` of the
    series are labelled 'probationary' and leave both the TP and FN accounting."""
    timestamps = list(range(8))
    scores = [0.9, 0.1, 0.9, 0.1, 0.9, 0.9, 0.1, 0.1]
    sweeper = nab_scorer.Sweeper(probation_percent=0.5, cost_matrix=STANDARD)
    points = sweeper.calc_sweep_score(timestamps, scores, [(2, 4)], "fam/a")
    assert [p.windowName for p in points[:4]] == ["probationary"] * 4
    rows = {r.threshold: r for r in sweeper.calc_score_by_threshold(points)}
    missed = rows[nab_scorer.INITIAL_THRESHOLD]
    # only the post-probation in-window point (i=4) counts as a potential FN
    assert (missed.tp, missed.fp, missed.fn, missed.tn) == (0, 0, 1, 3)
    assert missed.score == pytest.approx(-STANDARD["fnWeight"])


def test_optimize_threshold_maximizes_score_with_stable_tie_break() -> None:
    corpus = _two_series_corpus()
    best = nab_scorer.optimize_threshold(corpus, STANDARD)
    sweeper = nab_scorer.Sweeper(probation_percent=0.0, cost_matrix=STANDARD)
    pooled: list[nab_scorer.AnomalyPoint] = []
    for s in corpus:
        pooled.extend(sweeper.calc_sweep_score(s.timestamps, s.scores, s.windows, s.name))
    rows = sweeper.calc_score_by_threshold(pooled)
    assert best.score == max(r.score for r in rows)
    # stable descending sort: among equal-score rows the highest threshold wins
    tied = [r for r in rows if r.score == best.score]
    assert best.threshold == max(r.threshold for r in tied)


def _fake_series_result(
    key: str, n_train: int, n_test: int, windows: list[list[str]]
) -> tuple[dict, dict]:
    """Minimal evaluate_series-shaped result + committed row for corpus building."""
    start = np.datetime64("2020-01-01T00:00:00")
    ts = start + np.arange(n_train + n_test) * np.timedelta64(1, "h")
    ts_test = ts[n_train:]
    result = {
        "evaluable": True,
        "ts_test": ts_test,
        "scores": np.linspace(-0.2, 0.15, n_test),
        "alerts_fired": 3,
        "events_detected": 1,
        "events_missed": 0,
        "n_test": n_test,
        "n_windows": len(windows),
        "range_precision": 0.5,
        "range_recall": 1.0,
        "range_f1": 2 / 3,
    }
    committed_row = {
        "evaluable": True,
        "n_test": n_test,
        "n_windows": len(windows),
        "alerts_fired": 3,
        "events_detected": 1,
        "events_missed": 0,
        "range_precision": 0.5,
        "range_recall": 1.0,
        "range_f1": 2 / 3,
        "windows": windows,
    }
    return result, committed_row


def test_build_scoring_corpus_clips_window_start_to_scored_span() -> None:
    t0 = "2020-01-01T10:00:00"
    windows = [
        ["2020-01-01 05:00:00", "2020-01-01 12:00:00"],
        ["2020-01-01 15:00:00", "2020-01-01 16:00:00"],
    ]
    result, committed_row = _fake_series_result("fam/a", n_train=10, n_test=20, windows=windows)
    committed = {"series": {"fam/a": committed_row}}
    corpus, clips, excluded = build_scoring_corpus({"fam/a": result}, committed)
    assert excluded == [] and len(corpus) == 1
    first_start, first_end = corpus[0].windows[0]
    assert first_start == _ns(t0)  # clipped from 05:00 to the first scored timestamp
    assert clips and clips[0]["series"] == "fam/a"
    assert first_end == _ns("2020-01-01T12:00:00")
    assert len(corpus[0].windows) == 2


def test_verify_against_committed_raises_on_drift() -> None:
    windows = [["2020-01-01 12:00:00", "2020-01-01 13:00:00"]]
    result, committed_row = _fake_series_result("fam/a", 10, 20, windows)
    committed = {"series": {"fam/a": committed_row}, "overall": {"alerts_fired": 3}}
    ok = verify_against_committed({"fam/a": result}, committed)
    assert ok["alerts_fired_total"] == 3
    drifted = dict(result, alerts_fired=4)
    with pytest.raises(ValueError, match="drifted"):
        verify_against_committed({"fam/a": drifted}, committed)


@pytest.mark.skipif(not SCORES_JSON.exists(), reason="committed scorer inputs not present")
def test_committed_official_score_matches_vendored_scorer() -> None:
    """Re-run the vendored scorer on the committed scorer inputs: must match."""
    committed = json.loads(SCORE_JSON.read_text())
    payload = json.loads(SCORES_JSON.read_text())
    labels = load_official_windows()

    corpus: list[nab_scorer.SeriesInput] = []
    for key in committed["scored_series"]:
        s = payload["series"][key]
        ts_ns = [_ns(t) for t in s["timestamps"]]
        windows = [(_ns(a), _ns(b)) for a, b in s["windows"]]
        # re-derive the test-span-clipped windows from the vendored labels
        t0 = ts_ns[0]
        ts_set = set(ts_ns)
        derived = []
        for start_s, end_s in labels[f"{key}.csv"]:
            start = _ns(start_s.replace(" ", "T"))
            end = _ns(end_s.replace(" ", "T"))
            if end < t0:
                continue
            derived.append((max(start, t0), end))
        assert windows == derived, f"{key}: committed windows differ from vendored labels"
        assert all(a in ts_set and b in ts_set for a, b in windows)
        corpus.append(nab_scorer.SeriesInput(key, ts_ns, [float(v) for v in s["scores"]], windows))

    rescored = score_profiles(corpus)
    for profile_name, committed_profile in committed["profiles"].items():
        fresh = rescored["profiles"][profile_name]
        assert fresh["threshold"] == committed_profile["threshold"]
        assert fresh["score"] == pytest.approx(committed_profile["score"], abs=1e-9)
        assert fresh["raw_score"] == pytest.approx(committed_profile["raw_score"], abs=1e-9)
        assert fresh["counts"] == committed_profile["counts"]
        assert rescored["sanity"]["null"][profile_name] == 0.0
        assert rescored["sanity"]["perfect"][profile_name] == pytest.approx(100.0, abs=1e-9)


def test_run_nab_official_offline_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end on a stubbed one-series NAB: artifact written, gates hold."""
    import anomaly_detection.nab as nab_module
    import anomaly_detection.nab_official as official_module

    config = AnomalyConfig(
        windows=[5, 10],
        n_estimators=50,
        data_dir=str(tmp_path / "d"),
        reports_dir=str(tmp_path / "r"),
    )
    config.reports_path.mkdir(parents=True)

    base = np.datetime64("2020-01-01T00:00:00")
    n = 220
    ts = base + np.arange(n) * np.timedelta64(1, "h")
    rng = np.random.default_rng(0)
    values = rng.normal(0.0, 1.0, n)
    values[150:170] += 8.0
    lines = ["timestamp,value"] + [f"{t},{v:.4f}" for t, v in zip(ts, values, strict=True)]
    series_csv = tmp_path / "series.csv"
    series_csv.write_text("\n".join(lines) + "\n")
    windows = [[str(ts[152]), str(ts[168])]]

    def fake_fetch(url: str, dest: Path, expected_sha256: str | None = None) -> Path:
        if "combined_windows" in url:
            dest.write_text(json.dumps({"famA/seriesA.csv": windows}))
        else:
            dest.write_text(series_csv.read_text())
        return dest

    monkeypatch.setattr(nab_module, "fetch", fake_fetch)
    monkeypatch.setattr(nab_module, "NAB_SERIES", {"famA": [("seriesA", "a" * 64)]})
    monkeypatch.setattr(official_module, "NAB_SERIES", {"famA": [("seriesA", "a" * 64)]})

    # the committed artifact the runner verifies against, built from the same
    # deterministic recompute (one series, so totals match by construction)
    from anomaly_detection.nab import evaluate_series, parse_series_csv

    probe = evaluate_series(parse_series_csv(series_csv), windows, config)
    committed = {
        "series": {
            "famA/seriesA": {
                "evaluable": True,
                "n_test": probe["n_test"],
                "n_windows": probe["n_windows"],
                "alerts_fired": probe["alerts_fired"],
                "events_detected": probe["events_detected"],
                "events_missed": probe["events_missed"],
                "range_precision": probe["range_precision"],
                "range_recall": probe["range_recall"],
                "range_f1": probe["range_f1"],
                "windows": windows,
            }
        },
        "overall": {"alerts_fired": probe["alerts_fired"]},
    }
    (config.reports_path / "nab_metrics.json").write_text(json.dumps(committed))

    report = official_module.run_nab_official(config)
    assert (config.reports_path / "nab_official_score.json").exists()
    assert (config.reports_path / "nab_official_scores.json").exists()
    assert report["scored_series"] == ["famA/seriesA"]
    for name in ("standard", "reward_low_FP_rate", "reward_low_FN_rate"):
        assert report["sanity"]["null"][name] == 0.0
        assert report["sanity"]["perfect"][name] == pytest.approx(100.0, abs=1e-9)
        assert -100.0 <= report["profiles"][name]["score"] <= 100.0
