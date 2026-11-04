"""Refinement ablation tests: calibration math, fallback chain, gate, offline stage."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.nab_refinement import (
    BASELINE,
    CANDIDATES,
    IF_CALIBRATED,
    REFINED,
    ContextCalibration,
    decide_adoption,
    evaluate_refinement_series,
    hour_of_week,
    run_nab_refinement,
)

FIXTURE_BASE = datetime(2020, 1, 1)


def _fixture_csv(path: Path, n: int = 220) -> tuple[Path, list[list[str]]]:
    """Hourly NAB-shaped series with an elevated plateau in the test portion."""
    rng = np.random.default_rng(0)
    values = rng.normal(0.0, 1.0, n)
    values[150:170] += 8.0
    times = [FIXTURE_BASE + timedelta(hours=i) for i in range(n)]
    lines = ["timestamp,value"] + [
        f"{t:%Y-%m-%d %H:%M:%S},{v:.4f}" for t, v in zip(times, values, strict=True)
    ]
    path.write_text("\n".join(lines) + "\n")
    windows = [
        [times[152].isoformat(), times[168].isoformat()],
        [times[190].isoformat(), times[195].isoformat()],
    ]
    return path, windows


def _config(tmp_path: Path) -> AnomalyConfig:
    return AnomalyConfig(
        windows=[5, 10],
        n_estimators=50,
        data_dir=str(tmp_path / "d"),
        reports_dir=str(tmp_path / "r"),
    )


def test_hour_of_week_buckets_monday_zero_and_nat() -> None:
    times = np.array(
        ["2020-01-06T00:00:00", "2020-01-06T03:00:00", "2020-01-12T23:00:00"],
        dtype="datetime64[ns]",
    )
    assert hour_of_week(times).tolist() == [0, 3, 167]  # Mon 00:00, Mon 03:00, Sun 23:00
    nat = np.array(["NaT"], dtype="datetime64[ns]")
    assert hour_of_week(nat).tolist() == [-1]


def test_pvalues_are_monotone_decreasing_and_bounded() -> None:
    rng = np.random.default_rng(0)
    ref = rng.normal(0.0, 1.0, 500)
    calib = ContextCalibration({0: ref}, ref, min_context=30)
    scores = np.array([-3.0, -1.0, 0.0, 1.0, 3.0])
    p = calib.pvalues(scores, np.zeros(5, dtype=int))
    assert p is not None
    assert np.all(np.diff(p) < 0)  # distinct scores: strictly decreasing
    assert p.min() > 0.0 and p.max() <= 1.0
    # the conformal +1 correction: extremes land on the exact grid, never 0
    extremes = calib.pvalues(np.array([1e9, -1e9]), np.zeros(2, dtype=int))
    assert extremes is not None
    assert extremes[0] == pytest.approx(1.0 / 501.0)
    assert extremes[1] == pytest.approx(1.0)
    # ties share a p-value (weak monotonicity)
    tied = calib.pvalues(np.array([ref[100], ref[100]]), np.zeros(2, dtype=int))
    assert tied is not None and tied[0] == tied[1]


def test_budget_quantile_respected_exactly() -> None:
    """With test scores exchangeable with the calibration set, the p-value cut
    at the budget quantile flags exactly the budget fraction (± one row,
    deterministic for distinct scores)."""
    rng = np.random.default_rng(1)
    n = 1000
    ref = rng.normal(0.0, 1.0, n)
    calib = ContextCalibration({0: ref}, ref, min_context=30)
    p_ref = calib.pvalues(ref, np.zeros(n, dtype=int))
    assert p_ref is not None
    tau = float(np.quantile(p_ref, 0.02))
    permuted = ref[::-1].copy()  # same values, different order
    p_test = calib.pvalues(permuted, np.zeros(n, dtype=int))
    assert p_test is not None
    flagged = int((p_test <= tau).sum())
    assert flagged == int(np.floor(0.02 * (n - 1))) + 1
    assert flagged / n == pytest.approx(0.02, abs=1.0 / n)


def test_thin_and_unknown_contexts_fall_back_to_global() -> None:
    rng = np.random.default_rng(2)
    global_ref = rng.normal(10.0, 2.0, 400)  # far from the context-0 reference
    thin_ref = rng.normal(0.0, 1.0, 5)  # below min_context
    full_ref = rng.normal(0.0, 1.0, 400)
    calib = ContextCalibration({0: thin_ref, 7: full_ref}, global_ref, min_context=30)
    contexts = np.array([0, 99])  # thin context, unseen context
    p = calib.pvalues(np.array([0.0, 0.0]), contexts)
    expected = (1.0 + float((global_ref >= 0.0).sum())) / (global_ref.size + 1.0)
    assert p is not None
    np.testing.assert_allclose(p, [expected, expected])
    # a full context keeps its own reference (no fallback)
    p_full = calib.pvalues(np.array([0.0]), np.array([7]))
    assert p_full is not None
    assert p_full[0] != pytest.approx(expected)


def test_empty_calibration_returns_none_and_zscores_degenerate_fallback() -> None:
    empty = ContextCalibration({}, np.array([]), min_context=30)
    assert empty.pvalues(np.array([1.0]), np.array([0])) is None
    constant = np.full(50, 3.0)
    degenerate = ContextCalibration({0: constant}, constant, min_context=30)
    scores = np.array([3.0, 6.0])
    np.testing.assert_array_equal(degenerate.zscores(scores, np.zeros(2, dtype=int)), scores)
    global_ref = np.arange(400.0)
    mixed = ContextCalibration({0: constant}, global_ref, min_context=30)
    np.testing.assert_allclose(
        mixed.zscores(scores, np.zeros(2, dtype=int)),
        (scores - global_ref.mean()) / global_ref.std(),
    )


def test_calibrated_run_falls_back_to_raw_cut_without_reference(tmp_path: Path) -> None:
    """If every train minute sits inside a labelled window, no non-anomalous
    calibration exists and the candidate must reproduce the committed raw cut."""
    from anomaly_detection.nab import parse_series_csv

    path, _windows = _fixture_csv(tmp_path / "series.csv")
    times = [FIXTURE_BASE + timedelta(hours=i) for i in range(220)]
    # cover every featured train minute (warm-up drops the first 9 raw rows):
    # no non-anomalous reference remains, so the candidate must take the raw cut
    train_covering = [[times[0].isoformat(), times[160].isoformat()]]
    config = _config(tmp_path)
    df = parse_series_csv(path)
    baseline = evaluate_refinement_series(df, train_covering, config, BASELINE)
    calibrated = evaluate_refinement_series(df, train_covering, config, IF_CALIBRATED)
    assert calibrated["fell_back_to_raw_cut"] is True
    assert calibrated["threshold"] == baseline["threshold"]
    assert (
        calibrated["streams"]["raw"]["alerts_fired"] == baseline["streams"]["raw"]["alerts_fired"]
    )


def test_refinement_runs_are_deterministic(tmp_path: Path) -> None:
    from anomaly_detection.nab import parse_series_csv

    path, windows = _fixture_csv(tmp_path / "series.csv")
    config = _config(tmp_path)
    df = parse_series_csv(path)
    for candidate in CANDIDATES:
        a = evaluate_refinement_series(df, windows, config, candidate)
        b = evaluate_refinement_series(df, windows, config, candidate)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
        # the plateau must be caught by the committed baseline on this fixture,
        # and every candidate's stream ladder must not increase the page load
        streams = a["streams"]
        assert (
            streams["raw"]["alerts_fired"]
            >= streams["deduped"]["alerts_fired"]
            >= streams["budgeted"]["alerts_fired"]
        )
        assert 0.0 <= a["precision_at_budget"] <= 1.0
    assert (
        evaluate_refinement_series(df, windows, config, BASELINE)["streams"]["raw"][
            "events_detected"
        ]
        >= 1
    )


def test_decide_adoption_gate_conditions() -> None:
    baseline = {
        "events_detected": 16,
        "events_missed": 1,
        "precision_at_budget": 0.5,
        "range_f1": 0.15,
    }
    passing = {**baseline, "precision_at_budget": 0.6, "range_f1": 0.20}
    recall_loss = {**baseline, "events_detected": 14, "precision_at_budget": 0.7, "range_f1": 0.40}
    precision_loss = {**baseline, "precision_at_budget": 0.4, "range_f1": 0.30}
    refined = {
        "if_calibrated": precision_loss,
        "fusion_if_lof": recall_loss,
        "fusion_if_lof_norm": passing,
    }
    out = decide_adoption(baseline, refined)
    assert out["adopted"] == "fusion_if_lof_norm"
    # a big F1/precision win does not adopt through a coverage loss
    assert "FAIL" in out["reasons"]["fusion_if_lof"]
    refined["fusion_if_lof_norm"] = precision_loss
    assert decide_adoption(baseline, refined)["adopted"] is None


def test_run_nab_refinement_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full refinement stage on one fixture series with fetch + series list stubbed."""
    import anomaly_detection.nab as nab_module
    import anomaly_detection.nab_tune as nab_tune_module

    config = _config(tmp_path)
    series_path, windows = _fixture_csv(tmp_path / "fixture.csv")
    labels = {"famA/seriesA.csv": windows}

    def fake_fetch(url: str, dest: Path, expected_sha256: str | None = None) -> Path:
        if "combined_windows" in url:
            dest.write_text(json.dumps(labels))
        else:
            dest.write_text(series_path.read_text())
        return dest

    # _iter_series lives in nab_tune and resolves fetch/NAB_SERIES from its imports
    monkeypatch.setattr(nab_module, "fetch", fake_fetch)
    monkeypatch.setattr(nab_tune_module, "NAB_SERIES", {"famA": [("seriesA", "a" * 64)]})

    report = run_nab_refinement(config)
    assert report["data_source"] == "nab"
    assert set(report["candidates"]) == set(CANDIDATES)
    assert set(REFINED) | {BASELINE} == set(CANDIDATES)
    assert len(report["series"]) == len(CANDIDATES)
    baseline = report["candidates"][BASELINE]["overall"]
    assert baseline["streams"]["raw"]["alerts_fired"] > 0
    for candidate in REFINED:
        overall = report["candidates"][candidate]["overall"]
        assert 0.0 <= overall["precision_at_budget"] <= 1.0
        # the gate prices every candidate against the in-artifact baseline
        assert candidate in report["adoption"]["reasons"]
    assert (config.reports_path / "nab_refinement.json").exists()
