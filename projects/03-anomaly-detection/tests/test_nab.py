"""NAB track tests: window matching, loader, series evaluation — all offline."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.nab import (
    NAB_SERIES,
    evaluate_series,
    match_events,
    parse_series_csv,
    range_f1,
    run_nab,
    windows_to_mask,
)

BASE = datetime(2020, 1, 1)
W1 = [(BASE + timedelta(hours=10)).isoformat(), (BASE + timedelta(hours=12)).isoformat()]
W2 = [(BASE + timedelta(hours=20)).isoformat(), (BASE + timedelta(hours=21)).isoformat()]
WINDOWS = [list(W1), list(W2)]


def test_windows_to_mask_marks_window_points() -> None:
    times = np.array([BASE + timedelta(hours=h) for h in range(24)]).astype("datetime64[ns]")
    mask = windows_to_mask(times, WINDOWS)
    assert mask.sum() == 5  # inclusive bounds: 10,11,12 and 20,21
    assert mask[10] and mask[11] and mask[12]
    assert mask[20] and mask[21]
    assert not mask[0] and not mask[15]


def test_match_events_inside_outside_and_lead() -> None:
    base = np.datetime64(BASE)
    hours = np.timedelta64(3_600_000_000_000, "ns")  # 1 h in ns
    # alerts at h=11 (inside W1), h=15 (outside), h=21 (inside W2)
    alerts = base + hours * np.array([11, 15, 21])
    detected, in_window = match_events(alerts, WINDOWS)
    assert detected == [True, True]
    assert in_window.tolist() == [True, False, True]

    # lead credit: an alert 1h before W1 start detects W1 with lead_steps=1
    early = base + hours * np.array([9])
    detected_lead, _ = match_events(early, WINDOWS, lead_steps=1, step_ns=float(hours))
    assert detected_lead == [True, False]
    # ... but not without the lead
    detected_no, _ = match_events(early, WINDOWS, lead_steps=0)
    assert detected_no == [False, False]


def test_range_f1_arithmetic() -> None:
    assert range_f1([True, True], 0)["range_f1"] == pytest.approx(1.0)
    assert range_f1([False, False], 5)["range_recall"] == 0.0
    half = range_f1([True, False], 1)
    assert half["range_precision"] == pytest.approx(0.5)
    assert half["range_recall"] == pytest.approx(0.5)
    assert half["range_f1"] == pytest.approx(0.5)


def test_parse_series_csv_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "series.csv"
    path.write_text("timestamp,value\n2020-01-01 00:00:00,1.5\n2020-01-01 01:00:00,2.5\n")
    df = parse_series_csv(path)
    assert df.schema["timestamp"] == pl.Datetime(time_unit="us")
    assert df["value"].to_list() == [1.5, 2.5]


def _fixture_series(path: Path, n: int = 220) -> tuple[Path, list[list[str]]]:
    """Tiny NAB-shaped series: hourly points, elevated plateau near the end."""
    rng = np.random.default_rng(0)
    values = rng.normal(0.0, 1.0, n)
    values[150:170] += 8.0  # anomaly plateau in the test portion
    lines = ["timestamp,value"]
    times = [BASE + timedelta(hours=i) for i in range(n)]
    for t, v in zip(times, values, strict=True):
        lines.append(f"{t:%Y-%m-%d %H:%M:%S},{v:.4f}")
    path.write_text("\n".join(lines) + "\n")
    windows = [
        [times[152].isoformat(), times[168].isoformat()],
        [times[190].isoformat(), times[195].isoformat()],  # un-detected decoy window
    ]
    return path, windows


def test_evaluate_series_event_metrics(tmp_path: Path) -> None:
    config = AnomalyConfig(
        windows=[5, 10],
        n_estimators=50,
        data_dir=str(tmp_path / "d"),
        reports_dir=str(tmp_path / "r"),
    )
    path, windows = _fixture_series(tmp_path / "series.csv")
    result = evaluate_series(parse_series_csv(path), windows, config)
    assert 0.0 <= result["range_f1"] <= 1.0
    assert result["events_detected"] >= 1  # the plateau window must be caught
    assert result["alerts_fired"] > 0
    assert result["n_windows"] == 2
    assert 0.0 <= result["pr_auc"] <= 1.0


def test_run_nab_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full NAB stage against fixture files, with fetch + series list stubbed."""
    import anomaly_detection.nab as nab_module

    config = AnomalyConfig(
        windows=[5, 10],
        n_estimators=50,
        data_dir=str(tmp_path / "d"),
        reports_dir=str(tmp_path / "r"),
    )
    series_path, windows = _fixture_series(tmp_path / "fixture.csv")
    labels = {"famA/seriesA.csv": windows}  # NAB label keys carry the .csv suffix

    def fake_fetch(url: str, dest: Path, expected_sha256: str | None = None) -> Path:
        if "combined_windows" in url:
            dest.write_text(json.dumps(labels))
        else:
            dest.write_text(series_path.read_text())
        return dest

    monkeypatch.setattr(nab_module, "fetch", fake_fetch)
    monkeypatch.setattr(nab_module, "NAB_SERIES", {"famA": [("seriesA", "a" * 64)]})
    assert NAB_SERIES is not nab_module.NAB_SERIES  # stub is in place

    report = run_nab(config)
    assert report["data_source"] == "nab"
    assert set(report["series"]) == {"famA/seriesA"}
    assert set(report["by_family"]) == {"famA"}
    assert "overall" in report
    assert 0.0 <= report["overall"]["range_f1"] <= 1.0
    for name in ("nab_timelines", "nab_score_distribution", "nab_alert_budget"):
        assert (config.figures_dir / f"{name}.json").exists()
    assert (config.reports_path / "nab_metrics.json").exists()
