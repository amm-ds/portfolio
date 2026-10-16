"""Drift-check tests: synthetic month, mocked/persisted model — no network.

Builds a tiny February-2024 world (2 zones, hourly trips with a deterministic
count pattern) in the tmp workspace, persists a real (tiny) serving bundle,
and exercises the three contract paths: within tolerance (exit 0), regression
(exit 1 only with --fail-on-regression), and unpublished month (exit 2).
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError

import joblib
import polars as pl
import pytest
from mobility import cli as cli_mod
from mobility.config import MobilityConfig
from mobility.drift import (
    MonthUnavailableError,
    fetch_month,
    regression_ratio,
    run_drift_check,
    validate_month_format,
)
from mobility.features import FEATURE_COLUMNS
from sklearn.ensemble import HistGradientBoostingRegressor
from typer.testing import CliRunner

runner = CliRunner()

DRIFT_MONTH = "2024-02"
DRIFT_ZONES = pl.DataFrame(
    {
        "location_id": [1, 2],
        "borough": ["Manhattan", "Queens"],
        "zone": ["Midtown Center", "JFK Airport"],
    }
)
PINNED = {
    "gbm_tuned": {"mae": 1.0, "mape_pct": 50.0},
    "naive_lag24": {"mae": 2.0, "mape_pct": 90.0},
    "deltas": {"baseline": "naive_lag24", "gbm_tuned": {"mae_reduction_pct": 50.0}},
}


def _feb_trips() -> pl.DataFrame:
    """One trip file for DRIFT_MONTH: count = (hour % 4) + zone + weekday."""
    rows = []
    ts = datetime(2024, 2, 1)
    while ts < datetime(2024, 3, 1):
        for zone in (1, 2):
            count = (ts.hour % 4) + zone + ts.weekday() + 1
            for _ in range(count):
                rows.append(
                    {
                        "tpep_pickup_datetime": ts,
                        "tpep_dropoff_datetime": ts + timedelta(minutes=15),
                        "PULocationID": zone,
                        "DOLocationID": zone,
                        "passenger_count": 1,
                        "trip_distance": 3.1,
                        "fare_amount": 20.0,
                    }
                )
        ts += timedelta(hours=1)
    return pl.DataFrame(rows)


@pytest.fixture()
def drift_ready(cfg: MobilityConfig) -> dict:
    """Tmp workspace with a synthetic month, serving bundle, pinned metrics."""
    cfg.drift_raw_dir.mkdir(parents=True, exist_ok=True)
    _feb_trips().write_parquet(cfg.drift_raw_dir / f"yellow_tripdata_{DRIFT_MONTH}.parquet")
    DRIFT_ZONES.select(["location_id", "borough", "zone"]).write_parquet(cfg.zones_path)
    days = pl.date_range(date(2024, 2, 1), date(2024, 2, 29), "1d", eager=True)
    pl.DataFrame(
        {
            "date": days,
            "prcp_mm": [0.0] * len(days),
            "snow_mm": [0.0] * len(days),
            "tmax_c": [10.0] * len(days),
            "tmin_c": [0.0] * len(days),
        }
    ).write_parquet(cfg.weather_path)
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "metrics.json").write_text(json.dumps(PINNED))

    # Train tiny GBMs on the *actual* feature frame the check will build, so
    # the good model genuinely fits the synthetic month.
    from mobility.drift import clean_month, month_demand, month_features

    clean_month(DRIFT_MONTH, cfg)
    demand = month_demand(DRIFT_MONTH, cfg)
    feats = month_features(demand, cfg)
    assert feats.height > 0
    X = feats.select(FEATURE_COLUMNS).to_numpy()
    y = feats["target"].to_numpy()
    gbm = HistGradientBoostingRegressor(max_iter=100, random_state=0).fit(X, y)
    p90 = HistGradientBoostingRegressor(max_iter=50, random_state=0).fit(X, y)

    serving = cfg.models_dir / "serving"
    serving.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "gbm": gbm,
            "p90": p90,
            "feature_names": list(FEATURE_COLUMNS),
            "target_transform": None,
        },
        serving / "model.joblib",
    )
    (serving / "meta.json").write_text(json.dumps({"train_runs": ["gbm_tuned"]}))
    (serving / "zones.json").write_text("[]")
    return {"cfg": cfg, "feats": feats, "serving": serving}


def _write_offset_model(serving: Path, feats: pl.DataFrame, offset: float) -> None:
    """Same tiny model shifted by `offset` → controlled MAE regression."""
    X = feats.select(FEATURE_COLUMNS).to_numpy()
    y = feats["target"].to_numpy() + offset
    bundle = joblib.load(serving / "model.joblib")
    bundle["gbm"] = HistGradientBoostingRegressor(max_iter=100, random_state=0).fit(X, y)
    joblib.dump(bundle, serving / "model.joblib")


def _patch_cfg(monkeypatch: pytest.MonkeyPatch, cfg: MobilityConfig) -> None:
    monkeypatch.setattr(cli_mod, "_cfg", lambda: cfg)


# ---------------------------------------------------------------------------
# Unit math
# ---------------------------------------------------------------------------


def test_regression_ratio_math() -> None:
    assert regression_ratio(1.15, 1.0) == pytest.approx(0.15)
    assert regression_ratio(0.85, 1.0) == pytest.approx(-0.15)
    assert regression_ratio(2.0, 4.0) == pytest.approx(-0.5)
    with pytest.raises(ValueError):
        regression_ratio(1.0, 0.0)


def test_validate_month_format() -> None:
    assert validate_month_format("2025-03") == "2025-03"
    for bad in ("2024-13", "2024-1", "03-2024", "2024-00", "not-a-month"):
        with pytest.raises(ValueError):
            validate_month_format(bad)


# ---------------------------------------------------------------------------
# Within tolerance → exit 0 + report artifacts
# ---------------------------------------------------------------------------


def test_within_tolerance_exit_0(drift_ready: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = drift_ready["cfg"]
    _patch_cfg(monkeypatch, cfg)
    result = run_drift_check(DRIFT_MONTH, cfg)
    assert result.regressed is False
    assert result.month_mae < 0.5  # tiny model fits the synthetic pattern
    # Naive lag-24 error = |weekday(t+1) - weekday(t-24)|: 2 within a week,
    # 6 across the Sunday->Monday boundary -> mean ≈ 2.55 pickups/hour.
    assert result.month_naive_mae == pytest.approx(2.55, abs=0.1)
    assert result.month_delta_vs_naive_pct is not None
    assert result.month_delta_vs_naive_pct > 50  # model clearly beats naive
    assert result.regression_ratio < 0

    report = json.loads((cfg.drift_dir / f"{DRIFT_MONTH}.json").read_text())
    assert report["regressed"] is False
    assert report["pinned_test_window"]["gbm_tuned"]["mae"] == 1.0
    assert report["month_metrics"]["gbm_tuned"]["p90_coverage"] is not None
    assert (cfg.drift_dir / f"{DRIFT_MONTH}_mae.html").exists()
    assert (cfg.drift_dir / f"{DRIFT_MONTH}_mae.json").exists()
    assert (cfg.drift_dir / f"{DRIFT_MONTH}.dq.json").exists()
    drift_md = (cfg.drift_dir / "DRIFT.md").read_text()
    assert DRIFT_MONTH in drift_md
    assert "within tolerance" in drift_md

    res = runner.invoke(cli_mod.app, ["drift-check", "--month", DRIFT_MONTH])
    assert res.exit_code == 0, res.output
    assert "within tolerance" in res.output
    # DRIFT.md appends one section per run.
    assert (cfg.drift_dir / "DRIFT.md").read_text().count(f"## {DRIFT_MONTH}") == 2


# ---------------------------------------------------------------------------
# Regression → exit 1 only with --fail-on-regression; report still written
# ---------------------------------------------------------------------------


def test_regression_exit_codes(drift_ready: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = drift_ready["cfg"]
    _patch_cfg(monkeypatch, cfg)
    _write_offset_model(drift_ready["serving"], drift_ready["feats"], offset=30.0)

    result = run_drift_check(DRIFT_MONTH, cfg)
    assert result.regressed is True
    assert result.regression_ratio == pytest.approx((result.month_mae - 1.0) / 1.0)
    assert result.month_mae > 0.15 * 1.0 + 1.0  # clearly beyond default tolerance

    res = runner.invoke(
        cli_mod.app, ["drift-check", "--month", DRIFT_MONTH, "--fail-on-regression"]
    )
    assert res.exit_code == 1, res.output
    assert "REGRESSION" in res.output

    # Without the flag: report is still written, exit 0 (manual-run contract).
    res = runner.invoke(cli_mod.app, ["drift-check", "--month", DRIFT_MONTH])
    assert res.exit_code == 0, res.output
    report = json.loads((cfg.drift_dir / f"{DRIFT_MONTH}.json").read_text())
    assert report["regressed"] is True


def test_tolerance_flag_overrides_params(
    drift_ready: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = drift_ready["cfg"]
    _patch_cfg(monkeypatch, cfg)
    _write_offset_model(drift_ready["serving"], drift_ready["feats"], offset=30.0)
    result = run_drift_check(DRIFT_MONTH, cfg)
    assert result.regressed is True  # beyond the default 0.15 tolerance

    # --tolerance overrides params in both directions (scoring is deterministic).
    res = runner.invoke(
        cli_mod.app,
        [
            "drift-check",
            "--month",
            DRIFT_MONTH,
            "--fail-on-regression",
            "--tolerance",
            f"{result.regression_ratio + 1.0:.4f}",
        ],
    )
    assert res.exit_code == 0, res.output

    res = runner.invoke(
        cli_mod.app,
        [
            "drift-check",
            "--month",
            DRIFT_MONTH,
            "--fail-on-regression",
            "--tolerance",
            f"{result.regression_ratio - 1.0:.4f}",
        ],
    )
    assert res.exit_code == 1, res.output


# ---------------------------------------------------------------------------
# Unpublished month → exit 2 (skip-worthy), bad month → exit 2
# ---------------------------------------------------------------------------


def test_unavailable_month_exit_2(drift_ready: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = drift_ready["cfg"]
    _patch_cfg(monkeypatch, cfg)

    def _raise_404(url: str, dest: Path, pin: str | None = None) -> Path:
        raise HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    def _raise_403(url: str, dest: Path, pin: str | None = None) -> Path:
        raise HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)

    # The CDN answers missing keys with 404 or 403 — both are skip-worthy.
    for raiser in (_raise_404, _raise_403):
        monkeypatch.setattr("mobility.drift.fetch", raiser)
        with pytest.raises(MonthUnavailableError):
            fetch_month("2099-01", cfg)

    res = runner.invoke(cli_mod.app, ["drift-check", "--month", "2099-01"])
    assert res.exit_code == 2, res.output
    assert "not published yet" in res.output
    # Skip-worthy: no report artifacts for the missing month.
    assert not (cfg.drift_dir / "2099-01.json").exists()


def test_bad_month_exit_2(drift_ready: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_cfg(monkeypatch, drift_ready["cfg"])
    res = runner.invoke(cli_mod.app, ["drift-check", "--month", "2024-13"])
    assert res.exit_code == 2, res.output
