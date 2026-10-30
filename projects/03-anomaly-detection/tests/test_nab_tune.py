"""Operating-point selection tests: inner split, surface grid, conservative argmax.

All offline: the stage runs against the same tiny fixture series the NAB
tests use, with fetch + series list stubbed. The protocol invariants pinned
here: selection never sees test rows, longer cooldowns never page more, and a
grid point only moves the operating point when it beats the documented
default by the adoption margin.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from anomaly_detection.config import AnomalyConfig
from anomaly_detection.nab import parse_series_csv
from anomaly_detection.nab_sweep import DETECTORS, FEATURE_SETS, STREAMS
from anomaly_detection.nab_tune import (
    COOLDOWN_HOURS_GRID,
    DEFAULT_BUDGET,
    DEFAULT_COOLDOWN_HOURS,
    INNER_FIT_FRAC,
    MIN_GAIN,
    THRESHOLD_BUDGETS,
    aggregate_surface,
    budgeted_surface,
    build_validation_run,
    inner_train_val,
    run_nab_tune,
    select_operating_point,
)

BASE = datetime(2020, 1, 1)


def _fixture_series(path: Path, n: int = 220) -> tuple[Path, list[list[str]]]:
    """Tiny NAB-shaped series: hourly points, elevated plateau near the end."""
    rng = np.random.default_rng(0)
    values = rng.normal(0.0, 1.0, n)
    values[150:170] += 8.0  # anomaly plateau crossing the inner validation slice
    lines = ["timestamp,value"]
    times = [BASE + timedelta(hours=i) for i in range(n)]
    for t, v in zip(times, values, strict=True):
        lines.append(f"{t:%Y-%m-%d %H:%M:%S},{v:.4f}")
    path.write_text("\n".join(lines) + "\n")
    windows = [
        [times[152].isoformat(), times[168].isoformat()],  # overlaps the val slice
        [times[190].isoformat(), times[195].isoformat()],  # inside the test split
    ]
    return path, windows


def _config(tmp_path: Path) -> AnomalyConfig:
    return AnomalyConfig(
        windows=[5, 10],
        n_estimators=50,
        data_dir=str(tmp_path / "d"),
        reports_dir=str(tmp_path / "r"),
    )


def test_inner_train_val_split_bounds() -> None:
    n_inner, n_val = inner_train_val(147)
    assert n_inner == int(147 * INNER_FIT_FRAC) == 117
    assert n_inner + n_val == 147
    assert n_val > 0
    with pytest.raises(ValueError, match="cannot be split"):
        inner_train_val(1)


def test_build_validation_run_excludes_test_rows(tmp_path: Path) -> None:
    """The selection run must stop at the train split: no test row, and only
    windows overlapping the inner validation slice are visible."""
    config = _config(tmp_path)
    path, windows = _fixture_series(tmp_path / "series.csv")
    df = parse_series_csv(path)
    run = build_validation_run(df, windows, config, "isolation_forest", "rolling")

    feat_height = df.height - (max(config.windows) - 1)  # drop-null warm-up
    n_train = int(feat_height * config.train_frac)
    times = df["timestamp"].to_list()
    warm = df.height - feat_height
    assert run["n_train"] == n_train
    assert run["n_inner"] + run["n_val"] == n_train
    assert len(run["ref_scores"]) == run["n_inner"]
    assert len(run["val_scores"]) == run["n_val"]
    # the whole validation slice sits left of the outer test split
    assert run["ts_val"][0] >= times[warm + run["n_inner"]]
    assert run["ts_val"][-1] < times[warm + n_train]
    # only the plateau window overlaps the validation slice; the test window does not
    assert run["evaluable"] and run["n_windows"] == 1
    assert run["windows"][0][0] == windows[0][0]


def test_budgeted_surface_grid_shape_and_monotonicity(tmp_path: Path) -> None:
    """Grid size is exact and a longer cooldown never pages more (rate cap)."""
    config = _config(tmp_path)
    path, windows = _fixture_series(tmp_path / "series.csv")
    run = build_validation_run(parse_series_csv(path), windows, config, "lof", "rolling")
    surface = budgeted_surface(run)
    assert len(surface) == len(THRESHOLD_BUDGETS) * len(COOLDOWN_HOURS_GRID)
    for row in surface:
        assert 0.0 <= row["range_f1"] <= 1.0
        assert row["alerts_fired"] >= 0 and row["episodes"] >= 0
    for budget in THRESHOLD_BUDGETS:
        alerts = [
            r["alerts_fired"]
            for r in sorted(
                (r for r in surface if r["budget"] == budget),
                key=lambda r: r["cooldown_hours"],
            )
        ]
        assert alerts == sorted(alerts, reverse=True)  # rate cap is monotone


def _row(budget: float, cooldown: float, f1: float, alerts: int) -> dict:
    return {
        "budget": budget,
        "cooldown_hours": cooldown,
        "range_f1": f1,
        "range_recall": 0.0,
        "alerts_fired": alerts,
    }


def test_select_operating_point_adopts_clear_winner() -> None:
    surface = [
        _row(DEFAULT_BUDGET, DEFAULT_COOLDOWN_HOURS, 0.10, 40),
        _row(0.01, 12.0, 0.30, 5),  # clear winner, two grid neighbours present
        _row(0.01, DEFAULT_COOLDOWN_HOURS, 0.28, 7),
        _row(DEFAULT_BUDGET, 12.0, 0.08, 50),
    ]
    sel = select_operating_point(surface)
    assert sel["adopted"] is True
    assert (sel["budget"], sel["cooldown_hours"]) == (0.01, 12.0)
    assert sel["val_gain_over_default"] == pytest.approx(0.20)
    assert sel["plateau_count"] == 2
    assert sel["neighbor_mean_range_f1"] == pytest.approx((0.28 + 0.08) / 2)


def test_select_operating_point_keeps_default_without_robust_gain() -> None:
    """Below the adoption margin the default stands — the measured
    "no robust gain" path must be a first-class outcome, not an error."""
    surface = [
        _row(DEFAULT_BUDGET, DEFAULT_COOLDOWN_HOURS, 0.10, 40),
        _row(0.01, 12.0, 0.10 + MIN_GAIN - 0.001, 5),  # tantalisingly short
    ]
    sel = select_operating_point(surface)
    assert sel["adopted"] is False
    assert (sel["budget"], sel["cooldown_hours"]) == (DEFAULT_BUDGET, DEFAULT_COOLDOWN_HOURS)
    assert sel["val_range_f1"] == pytest.approx(0.10)


def test_select_operating_point_tie_breaks_are_deterministic() -> None:
    # equal F1: fewer pages wins
    tied_load = [
        _row(DEFAULT_BUDGET, DEFAULT_COOLDOWN_HOURS, 0.10, 40),
        _row(0.01, 12.0, 0.30, 9),
        _row(0.04, 48.0, 0.30, 3),
    ]
    sel = select_operating_point(tied_load)
    assert sel["adopted"] is True
    assert (sel["budget"], sel["cooldown_hours"]) == (0.04, 48.0)
    # equal F1 and equal pages: the default is sticky
    tied_default = [
        _row(DEFAULT_BUDGET, DEFAULT_COOLDOWN_HOURS, 0.30, 5),
        _row(0.01, 12.0, 0.30, 5),
    ]
    sel_default = select_operating_point(tied_default)
    assert sel_default["adopted"] is False  # gain 0 < margin, default kept
    assert (sel_default["budget"], sel_default["cooldown_hours"]) == (
        DEFAULT_BUDGET,
        DEFAULT_COOLDOWN_HOURS,
    )
    # byte-identical repeat: the protocol is a pure function of the surface
    assert select_operating_point(tied_load) == sel


def test_select_operating_point_requires_default_in_grid() -> None:
    surface = [_row(0.01, 12.0, 0.5, 3)]
    with pytest.raises(ValueError, match="not in the selection grid"):
        select_operating_point(surface)


def test_aggregate_surface_averages_runs() -> None:
    run_a = [_row(0.02, 24.0, 0.2, 4), _row(0.04, 24.0, 0.4, 8)]
    run_b = [_row(0.02, 24.0, 0.4, 6), _row(0.04, 24.0, 0.0, 2)]
    agg = aggregate_surface([run_a, run_b])
    assert agg[0]["range_f1"] == pytest.approx(0.3)
    assert agg[0]["alerts_fired"] == 10
    assert agg[1]["range_f1"] == pytest.approx(0.2)
    with pytest.raises(ValueError, match="no validation runs"):
        aggregate_surface([])


def test_compare_vs_default_reads_committed_sweep(tmp_path: Path) -> None:
    """The default-operating-point baseline is read from the committed sweep
    artifact; deltas must be computed cell-by-cell."""
    from anomaly_detection.nab_tune import _compare_vs_default

    reports = tmp_path / "r"
    reports.mkdir()
    sweep = {
        "grid": {
            "isolation_forest+rolling": {
                "overall": {
                    "streams": {
                        "budgeted": {"alerts_fired": 10, "range_f1": 0.2, "range_recall": 0.5}
                    }
                }
            }
        }
    }
    (reports / "nab_sweep.json").write_text(json.dumps(sweep))
    cells = {
        "isolation_forest+rolling": {
            "overall": {
                "streams": {"budgeted": {"alerts_fired": 8, "range_f1": 0.25, "range_recall": 0.6}}
            }
        }
    }
    families = {"isolation_forest": {"budget": 0.01, "cooldown_hours": 12.0, "adopted": True}}
    config = AnomalyConfig(data_dir=str(tmp_path / "d"), reports_dir=str(reports))
    out = _compare_vs_default(config, cells, families)
    assert out["available"] is True and out["sourced_from"] == "nab_sweep.json"
    row = out["cells"]["isolation_forest+rolling"]
    assert row["delta_alerts_fired"] == -2
    assert row["delta_range_f1"] == pytest.approx(0.05)
    assert row["delta_range_recall"] == pytest.approx(0.1)
    assert row["operating_point"]["adopted"] is True


def test_run_nab_tune_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full tuning stage on one fixture series with fetch + series list stubbed."""
    import anomaly_detection.nab as nab_module
    import anomaly_detection.nab_sweep as sweep_module
    import anomaly_detection.nab_tune as tune_module

    config = _config(tmp_path)
    series_path, windows = _fixture_series(tmp_path / "fixture.csv")
    labels = {"famA/seriesA.csv": windows}  # NAB label keys carry the .csv suffix

    def fake_fetch(url: str, dest: Path, expected_sha256: str | None = None) -> Path:
        if "combined_windows" in url:
            dest.write_text(json.dumps(labels))
        else:
            dest.write_text(series_path.read_text())
        return dest

    monkeypatch.setattr(nab_module, "fetch", fake_fetch)
    monkeypatch.setattr(tune_module, "NAB_SERIES", {"famA": [("seriesA", "a" * 64)]})
    assert sweep_module.NAB_SERIES is not tune_module.NAB_SERIES  # stub is in place

    report = run_nab_tune(config)
    proto = report["protocol"]
    assert proto["test_evaluations_per_family"] == 1
    assert proto["min_gain_to_adopt"] == MIN_GAIN
    assert proto["default_operating_point"] == {
        "budget": DEFAULT_BUDGET,
        "cooldown_hours": DEFAULT_COOLDOWN_HOURS,
    }
    # the fixture has exactly one window overlapping the inner validation slice
    assert report["validation_evidence"]["windows_total"] == 1
    assert report["validation_evidence"]["series_evaluable"] == 1
    for surface in report["selection"]["surfaces"].values():
        assert len(surface) == len(THRESHOLD_BUDGETS) * len(COOLDOWN_HOURS_GRID)
    for sel in report["selection"]["families"].values():
        assert isinstance(sel["adopted"], bool)
        assert sel["grid_size"] == len(THRESHOLD_BUDGETS) * len(COOLDOWN_HOURS_GRID)
    # one test evaluation per sweep cell, same shape as the sweep artifact
    assert set(report["evaluation"]["cells"]) == {
        f"{d}+{f}" for d in DETECTORS for f in FEATURE_SETS
    }
    for cell in report["evaluation"]["cells"].values():
        assert set(cell["overall"]["streams"]) == set(STREAMS)
        assert (
            cell["overall"]["streams"]["raw"]["alerts_fired"]
            >= cell["overall"]["streams"]["budgeted"]["alerts_fired"]
        )
        assert 0.0 <= cell["overall"]["range_f1"] <= 1.0
    # no committed sweep artifact in the tmp reports dir: comparison says so
    assert report["vs_default_sweep_budgeted"]["available"] is False
    artifact = config.reports_path / "nab_tune.json"
    assert artifact.exists()
    on_disk = json.loads(artifact.read_text())
    assert on_disk["stage"] == "nab_tune"
    assert (config.figures_dir / "nab_tune_surface.json").exists()
