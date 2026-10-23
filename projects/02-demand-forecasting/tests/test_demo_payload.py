"""Demo payload contract: deterministic catalog for the forecast workbench UI."""

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.demo_payload import (
    SIZE_CAP_BYTES,
    build_demo_payload,
    point_backtest,
    quantile_band_backtest,
    write_demo_payload,
)
from demand_forecasting.features import build_features

# Two series per demand class; zero-fractions land well inside the documented
# thresholds (smooth < 35%, intermittent 35-90%, sparse >= 90%).
CLASSES = ["smooth", "smooth", "intermittent", "intermittent", "sparse", "sparse"]
CATALOG_ARGS = {"catalog_n": 6, "history_days": 60, "horizon": 14}


def _class_panel(config: ForecastConfig) -> pl.DataFrame:
    """Hand-built 6-series panel spanning all three demand classes."""
    rng = np.random.default_rng(7)
    n_days = config.n_days
    dates = [date(2024, 1, 1) + timedelta(days=d) for d in range(n_days)]
    rows: dict[str, list] = {"date": [], "store": [], "product": [], "units": []}
    for i, cls in enumerate(CLASSES):
        if cls == "smooth":
            units = rng.integers(4, 20, n_days)
        elif cls == "intermittent":
            units = np.where(rng.random(n_days) < 0.5, 0, rng.integers(3, 15, n_days))
        else:
            units = np.where(rng.random(n_days) < 0.95, 0, rng.integers(2, 12, n_days))
        store, product = f"store_{i // 2}", f"product_{i % 2}"
        for d, u in zip(dates, units, strict=True):
            rows["date"].append(d)
            rows["store"].append(store)
            rows["product"].append(product)
            rows["units"].append(int(u))
    return pl.DataFrame(
        rows,
        schema={"date": pl.Date, "store": pl.String, "product": pl.String, "units": pl.Int64},
    )


@pytest.fixture
def demo_context(
    tmp_path: Path, config: ForecastConfig
) -> tuple[DemandSettings, ForecastConfig, pl.DataFrame]:
    """Minimal on-disk context: class-spanning panel, features and the
    committed-metrics shape (values the same backtest produces on this frame)."""
    settings = DemandSettings(
        data_dir=tmp_path / "data", reports_dir=tmp_path / "reports", min_newest_date="2023-01-01"
    )
    panel = _class_panel(config)
    features = build_features(panel, config)
    settings.data_dir.mkdir(parents=True)
    settings.reports_dir.mkdir(parents=True)
    panel.write_parquet(settings.data_dir / "panel.parquet")
    features.write_parquet(settings.data_dir / "features.parquet")

    result = point_backtest(features, config, "hgb_tuned")
    band = quantile_band_backtest(features, config)
    metrics = {
        r.name: {"mae": r.get("mae").value, "mase": r.get("mase").value} for r in result.runs
    }
    (settings.reports_dir / "metrics.json").write_text(json.dumps(metrics))
    probabilistic = {
        "target_coverage": 0.8,
        "quantile_band": {"coverage_pooled": band["coverage_pooled"]},
        "split_conformal": {"coverage_last_fold": 0.85},
    }
    (settings.reports_dir / "probabilistic.json").write_text(json.dumps(probabilistic))
    return settings, config, panel


@pytest.fixture
def payload(demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame]) -> dict:
    settings, config, _panel = demo_context
    return build_demo_payload(settings, config, **CATALOG_ARGS)


def test_payload_shape(payload: dict) -> None:
    assert payload["schema_version"] == 1
    assert payload["demo"] == "forecast-workbench"
    assert payload["project"] == "02-demand-forecasting"
    assert set(payload) == {"schema_version", "demo", "project", "track", "catalog", "scalars"}
    assert len(payload["catalog"]) == 6
    entry = payload["catalog"][0]
    assert set(entry) == {"series_id", "label", "demand_class", "history", "forecast", "errors"}
    assert len(entry["history"]["y"]) == 60 == len(entry["history"]["dates"])
    assert set(entry["forecast"]) == {"dates", "y_pred", "p10", "p90", "naive"}
    assert all(len(entry["forecast"][k]) == 14 for k in entry["forecast"])
    assert set(entry["errors"]) == {"scale", "champion", "naive"}
    for model in ("champion", "naive"):
        assert len(entry["errors"][model]["mae"]) == 14
        assert len(entry["errors"][model]["mase"]) == 14
    # one-day-ahead frame: per-horizon MAE is a single origin's absolute
    # error; the history tail includes the window, so y_true(h=1) is the
    # 14th-from-last history point
    first = entry["forecast"]
    assert entry["errors"]["champion"]["mae"][0] == pytest.approx(
        abs(first["y_pred"][0] - entry["history"]["y"][-14]), abs=0.01
    )


def test_demand_class_coverage(payload: dict) -> None:
    classes = {e["demand_class"] for e in payload["catalog"]}
    assert classes == {"smooth", "intermittent", "sparse"}
    assert payload["scalars"]["catalog_summary"]["by_class"] == {
        "smooth": 2,
        "intermittent": 2,
        "sparse": 2,
    }


def test_naive_matches_hand_computed(
    payload: dict, demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame]
) -> None:
    """The stored naive floor must equal the actuals 7 days before each window date."""
    _settings, _config, panel = demo_context
    units = {
        (f"{r['store']}|{r['product']}", r["date"]): r["units"] for r in panel.iter_rows(named=True)
    }
    for entry in payload["catalog"]:
        for d, naive in zip(entry["forecast"]["dates"], entry["forecast"]["naive"], strict=True):
            prior = date.fromisoformat(d) - timedelta(days=7)
            assert naive == pytest.approx(float(units[(entry["series_id"], prior)]))


def test_stored_mase_matches_committed(
    payload: dict, demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame]
) -> None:
    settings, _config, _panel = demo_context
    metrics = json.loads((settings.reports_dir / "metrics.json").read_text())
    headline = payload["scalars"]["headline"]
    assert headline["champion"] == "hgb_tuned"
    assert headline["champion_mase"] == pytest.approx(metrics["hgb_tuned"]["mase"], abs=1e-9)
    assert headline["naive_mase"] == pytest.approx(metrics["seasonal_naive"]["mase"], abs=1e-9)
    assert headline["mase_by_model"] == {
        k: v["mase"] for k, v in metrics.items() if isinstance(v, dict)
    }


def test_drift_guard_raises_on_tampered_metrics(
    demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame],
) -> None:
    settings, config, _panel = demo_context
    metrics = json.loads((settings.reports_dir / "metrics.json").read_text())
    metrics["hgb_tuned"]["mase"] += 0.5
    (settings.reports_dir / "metrics.json").write_text(json.dumps(metrics))
    with pytest.raises(ValueError, match="hgb_tuned"):
        build_demo_payload(settings, config, **CATALOG_ARGS)


def test_drift_guard_raises_on_tampered_coverage(
    demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame],
) -> None:
    settings, config, _panel = demo_context
    probabilistic = json.loads((settings.reports_dir / "probabilistic.json").read_text())
    probabilistic["quantile_band"]["coverage_pooled"] += 0.2
    (settings.reports_dir / "probabilistic.json").write_text(json.dumps(probabilistic))
    with pytest.raises(ValueError, match="coverage_pooled"):
        build_demo_payload(settings, config, **CATALOG_ARGS)


def test_scalars_models_and_feature_schema(payload: dict) -> None:
    models = payload["scalars"]["models"]
    assert models["champion"] == "hgb_tuned" == models["global"]
    assert models["naive"] == "seasonal_naive"
    schema = payload["scalars"]["feature_schema"]
    assert schema["lags"] == ["lag_1", "lag_7"]
    assert {"dow", "is_weekend", "doy_sin", "doy_cos"} <= set(schema["calendar"])
    band = payload["scalars"]["band"]
    assert band["target_coverage"] == 0.8
    assert 0.0 <= band["quantile_coverage_pooled"] <= 1.0


def test_payload_size_cap(tmp_path: Path) -> None:
    """A 150-series payload at production shape must fit the 2 MB cap."""
    from demand_forecasting.data import build_panel

    config = ForecastConfig(
        n_days=220, n_stores=15, n_products=10, lags=[1, 7], n_splits=2, gap=3, min_train_size=40
    )
    settings = DemandSettings(data_dir=tmp_path / "data", reports_dir=tmp_path / "reports")
    panel = build_panel(DemandSettings(), config)
    features = build_features(panel, config)
    settings.data_dir.mkdir(parents=True)
    settings.reports_dir.mkdir(parents=True)
    features.write_parquet(settings.data_dir / "features.parquet")

    result = point_backtest(features, config, "hgb_tuned")
    band = quantile_band_backtest(features, config)
    metrics = {
        r.name: {"mae": r.get("mae").value, "mase": r.get("mase").value} for r in result.runs
    }
    (settings.reports_dir / "metrics.json").write_text(json.dumps(metrics))
    (settings.reports_dir / "probabilistic.json").write_text(
        json.dumps(
            {
                "target_coverage": 0.8,
                "quantile_band": {"coverage_pooled": band["coverage_pooled"]},
                "split_conformal": {"coverage_last_fold": 0.9},
            }
        )
    )

    payload = build_demo_payload(settings, config)  # defaults: 150 x 180 x 14
    assert payload["scalars"]["catalog_summary"]["n_series"] == 150
    size = len((json.dumps(payload, indent=2) + "\n").encode())
    assert size <= SIZE_CAP_BYTES


def test_write_demo_payload_roundtrip(
    demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame],
) -> None:
    settings, config, _panel = demo_context
    out = write_demo_payload(settings, config, **CATALOG_ARGS)
    assert out.name == "demo_payload.json"
    on_disk = json.loads(out.read_text())
    assert on_disk == build_demo_payload(settings, config, **CATALOG_ARGS)
