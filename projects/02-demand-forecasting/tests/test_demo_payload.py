"""Demo payload contract: deterministic multi-origin catalog for the workbench UI."""

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.demo_payload import (
    PAYLOAD_SCHEMA_VERSION,
    SIZE_CAP_BYTES,
    _emit_band,
    build_demo_payload,
    quantile_band_backtest,
    write_demo_payload,
)
from demand_forecasting.features import build_features

# Two series per demand class; zero-fractions land well inside the documented
# thresholds (smooth < 35%, intermittent 35-90%, sparse >= 90%).
CLASSES = ["smooth", "smooth", "intermittent", "intermittent", "sparse", "sparse"]
CATALOG_ARGS = {"catalog_n": 6, "history_days": 60, "horizon": 14, "origin_history_days": 45}
# v1 top-level + per-series keys the v2 payload must keep (clean supersede).
V1_TOP_KEYS = {"schema_version", "demo", "project", "track", "catalog", "scalars"}
V1_ENTRY_KEYS = {"series_id", "label", "demand_class", "history", "forecast", "errors"}
V1_HEADLINE_KEYS = {
    "claim",
    "champion",
    "champion_mase",
    "champion_mae",
    "naive_mase",
    "only_champion_below_mase_1",
    "runs_below_mase_1",
    "mase_by_model",
}


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


def _write_evaluation_metadata(
    reports: Path, result, champion: str = "hgb_tuned", challenger: str = "hgb"
) -> None:
    """The committed evaluation_metadata.json shape, consistent with the backtest."""
    n_folds = result.test_fold_id() + 1
    last = result.last_fold(champion)
    test_dates = np.unique(last.dates)
    meta = {
        "protocol": "rolling_origin_holdout_v1",
        "rolling_origin": {
            "n_origins": n_folds,
            "origin_spacing_days": (test_dates.size // max(n_folds - 1, 1)),
            "horizon_days": 14,
            "embargo_gap_days": 3,
            "min_train_size_dates": 30,
            "test_window": {
                "origin": n_folds,
                "start": str(test_dates.min())[:10],
                "end": str(test_dates.max())[:10],
                "n_days": int(test_dates.size),
            },
        },
        "holdout_designation": "last origin = test; selection used origins 1..n-1 only",
        "selection_used_origins": [i + 1 for i in result.selection_fold_ids()],
        "test_origin": n_folds,
        "selection_rule": "champion (best_model) = lowest pooled MAE over origins 1..n-1",
        "metric_definitions": {
            "mae": "mean |actual - forecast| over the test window (all series pooled)",
            "mase": "MAE scaled by the per-series in-sample seasonal-naive-7 error",
            "bias": "mean(forecast - actual) over the test window",
            "wape": "sum|actual - forecast| / sum|actual| over the test window",
            "fold_maes": "per-fold pooled MAE, folds 1..n (fold n is the test window)",
        },
        "best_model": champion,
        "strongest_naive": "seasonal_naive",
    }
    (reports / "evaluation_metadata.json").write_text(json.dumps(meta))


def _write_dataset_metadata(reports: Path) -> None:
    """The committed dataset_metadata.json shape (small fixture card)."""
    meta = {
        "dataset": "fixture-panel",
        "source": {"url": "https://example.test/panel.zip", "sha256": "0" * 64},
        "cancellation_filtering": "Sales lines only: Quantity > 0 kept.",
        "quantity_handling": "Daily sum of line Quantity per (date, store, product).",
        "daily_aggregation": "Reindexed to the complete daily calendar, zero-filled.",
        "observed_panel": {
            "date_start": "2024-01-01",
            "date_end": "2024-06-08",
            "n_days": 160,
            "n_rows": 1000,
            "n_series": 6,
            "zero_share": 0.5,
        },
        "zero_sales_caveat": "Zero-sales days may be missing rather than true zero demand.",
        "target_definition": "The forecast target is the next 14 days of daily units per series.",
    }
    (reports / "dataset_metadata.json").write_text(json.dumps(meta))


def _run_backtest(features: pl.DataFrame, config: ForecastConfig):
    """Champion + challenger candidate + third wheel + the naive floor."""
    from demand_forecasting.evaluate import backtest
    from demand_forecasting.model import model_specs

    names = {"hgb_tuned", "hgb", "ridge", "seasonal_naive"}
    specs = [s for s in model_specs() if s.name in names]
    return backtest(features, config, specs=specs)


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

    result = _run_backtest(features, config)
    band = quantile_band_backtest(features, config)
    metrics = {
        r.name: {"mae": r.get("mae").value, "mase": r.get("mase").value} for r in result.runs
    }
    metrics["_meta"] = {"best_model": "hgb_tuned"}
    # pin the committed test-window MAE order so the rank-2 challenger is hgb
    # (ridge plays the strongest-rival rank-1 slot, as lgbm_tuned does on UCI)
    metrics["ridge"]["mae"] = float(metrics["hgb"]["mae"]) - 1.0
    (settings.reports_dir / "metrics.json").write_text(json.dumps(metrics))
    probabilistic = {
        "target_coverage": 0.8,
        "quantile_band": {"coverage_pooled": band["coverage_pooled"]},
        "split_conformal": {"coverage_last_fold": 0.85},
    }
    (settings.reports_dir / "probabilistic.json").write_text(json.dumps(probabilistic))
    _write_evaluation_metadata(settings.reports_dir, result)
    _write_dataset_metadata(settings.reports_dir)
    return settings, config, panel


@pytest.fixture
def payload(demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame]) -> dict:
    settings, config, _panel = demo_context
    return build_demo_payload(settings, config, **CATALOG_ARGS)


def _assert_band_sane(band: dict, window_actuals: list[int], sparse: bool) -> None:
    """Emitted band hygiene: no negatives, p10 <= y_pred <= p90, and a sparse
    all-zero window honestly carries no band at all (None, not a degenerate
    zero-width interval)."""
    p10, p50, p90 = band["p10"], band["y_pred"], band["p90"]
    if sparse and all(v == 0 for v in window_actuals):
        assert p10 is None and p90 is None
        return
    assert p10 is not None and p90 is not None
    assert len(p10) == 14 == len(p90)
    for lo, mid, hi in zip(p10, p50, p90, strict=True):
        assert lo >= 0.0 and hi >= 0.0
        assert lo <= mid <= hi


def test_emit_band_sanitizes_points() -> None:
    """Clip at zero + clamp around the point curve; sparse zero-window -> no band."""
    p10 = np.array([-0.5, 2.0, 0.0, 1.0])
    p50 = np.array([3.0, 1.0, 0.0, 1.0])
    p90 = np.array([0.0, 5.0, -0.25, 1.0])
    lo, hi = _emit_band(p10, p50, p90, zero_window=False, sparse=False)
    assert lo is not None and hi is not None
    # negatives clipped, degenerate quantile outputs clamped around the point
    assert lo == [0.0, 1.0, 0.0, 1.0]
    assert hi == [3.0, 5.0, 0.0, 1.0]
    assert all(l <= m <= h for l, m, h in zip(lo, p50, hi, strict=True))
    # sparse + all-zero window -> band null instead of a degenerate band
    assert _emit_band(p10, p50, p90, zero_window=True, sparse=True) == (None, None)
    # sparse with real demand in the window keeps its band; so does a
    # non-sparse series on a zero window (the degenerate band covered it all)
    assert _emit_band(p10, p50, p90, zero_window=False, sparse=True)[0] is not None
    assert _emit_band(p10, p50, p90, zero_window=True, sparse=False)[0] is not None


def test_payload_shape(payload: dict) -> None:
    assert payload["schema_version"] == PAYLOAD_SCHEMA_VERSION == 2
    assert payload["demo"] == "forecast-workbench"
    assert payload["project"] == "02-demand-forecasting"
    # v1 -> v2 supersede: every v1 top-level key survives, three blocks are added
    assert set(payload) >= V1_TOP_KEYS
    assert {"origins_meta", "evaluation_metadata", "dataset_metadata"} <= set(payload)
    assert len(payload["catalog"]) == 6
    entry = payload["catalog"][0]
    assert set(entry) >= V1_ENTRY_KEYS
    assert set(entry["origins"]) == {"early", "middle", "test"}
    assert len(entry["history"]["y"]) == 60 == len(entry["history"]["dates"])
    assert set(entry["forecast"]) == {"dates", "y_pred", "p10", "p90", "naive"}
    for k in ("dates", "y_pred", "naive"):
        assert len(entry["forecast"][k]) == 14
    for k in ("p10", "p90"):
        band = entry["forecast"][k]
        assert band is None or len(band) == 14  # sparse all-zero windows: no band
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
    # the emitted band is display-sane: clipped at zero, ordered around the
    # point curve, and absent (not degenerate) on sparse all-zero windows
    _assert_band_sane(
        {"p10": first["p10"], "y_pred": first["y_pred"], "p90": first["p90"]},
        entry["history"]["y"][-14:],
        entry["demand_class"] == "sparse",
    )


def test_origins_shape_and_holdout(payload: dict) -> None:
    """Three origins with the test-window holdout designation and fold indices."""
    meta = payload["origins_meta"]
    assert [m["label"] for m in meta["origins"]] == ["early", "middle", "test"]
    assert meta["origins"][-1]["holdout"] == "test"
    assert "holdout" not in meta["origins"][0]
    assert meta["origins"][-1]["fold_index"] == max(m["fold_index"] for m in meta["origins"])
    assert meta["selection_used_origins"] == [
        m["origin"] for m in meta["origins"] if m["label"] != "test"
    ]
    assert [m["origin_date"] for m in meta["origins"]] == sorted(
        m["origin_date"] for m in meta["origins"]
    )
    entry = payload["catalog"][0]
    for _label, origin in entry["origins"].items():
        assert len(origin["actuals"]["y"]) == 14 == len(origin["actuals"]["dates"])
        assert len(origin["history"]["y"]) == len(origin["history"]["dates"])
        # as-of-origin history: nothing after the origin date, no test-window leak
        assert origin["history"]["dates"][-1] <= origin["origin_date"]
        for model in ("champion", "challenger", "naive"):
            block = origin["models"][model]
            assert len(block["y_pred"]) == 14
            for metric in ("mae", "mase", "bias", "wape"):
                assert metric in block
        band = origin["models"]["champion"]
        # the band is champion-only: challenger and naive are point curves
        assert "p10" not in origin["models"]["challenger"]
        assert "p10" not in origin["models"]["naive"]
        _assert_band_sane(band, origin["actuals"]["y"], entry["demand_class"] == "sparse")
    # the test origin reproduces the v1 forecast window exactly
    test = entry["origins"]["test"]
    assert test["actuals"]["dates"] == entry["forecast"]["dates"]
    assert test["models"]["champion"]["y_pred"] == entry["forecast"]["y_pred"]
    assert test["models"]["naive"]["y_pred"] == entry["forecast"]["naive"]


def test_origins_metric_spread(payload: dict) -> None:
    """The origin story carries signal: per-origin MAE varies across origins."""
    for entry in payload["catalog"]:
        champ_maes = [
            entry["origins"][label]["models"]["champion"]["mae"]
            for label in ("early", "middle", "test")
        ]
        assert all(m is not None for m in champ_maes)
    spread = {
        e["series_id"]: [
            e["origins"][label]["models"]["champion"]["mae"]
            for label in ("early", "middle", "test")
        ]
        for e in payload["catalog"]
    }
    varying = [sid for sid, m in spread.items() if len(set(m)) > 1]
    assert varying, "per-origin champion MAE should vary on at least one series"


def test_origin_metrics_match_hand_computed(
    payload: dict, demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame]
) -> None:
    """Per-origin stored metrics equal a hand recomputation from the stored curves."""
    _settings, _config, panel = demo_context
    units = {
        (f"{r['store']}|{r['product']}", r["date"]): r["units"] for r in panel.iter_rows(named=True)
    }
    for entry in payload["catalog"]:
        sid = entry["series_id"]
        for _label, origin in entry["origins"].items():
            actual = np.asarray(origin["actuals"]["y"], dtype=float)
            # actuals come straight from the committed panel
            for d, y in zip(origin["actuals"]["dates"], origin["actuals"]["y"], strict=True):
                assert units[(sid, date.fromisoformat(d))] == y
            hist_y = np.asarray(origin["history"]["y"], dtype=float)
            scale = float(np.mean(np.abs(hist_y[7:] - hist_y[:-7]))) if hist_y.size > 7 else 0.0
            assert origin["scale"] == pytest.approx(round(scale, 4), abs=1e-4)
            for _model, block in origin["models"].items():
                pred = np.asarray(block["y_pred"], dtype=float)
                err = pred - actual
                expected_mae = round(float(np.mean(np.abs(err))), 4)
                assert block["mae"] == pytest.approx(expected_mae, abs=1e-4)
                assert block["bias"] == pytest.approx(round(float(np.mean(err)), 4), abs=1e-4)
                if scale > 0:
                    assert block["mase"] == pytest.approx(
                        round(float(np.mean(np.abs(err)) / scale), 4), abs=1e-4
                    )
                else:
                    assert block["mase"] is None
                if np.abs(actual).sum() > 0:
                    assert block["wape"] == pytest.approx(
                        round(float(np.abs(err).sum() / np.abs(actual).sum()), 4), abs=1e-4
                    )
                else:
                    assert block["wape"] is None


def test_evaluation_and_dataset_metadata(payload: dict) -> None:
    ev = payload["evaluation_metadata"]
    assert ev["protocol"] == "rolling_origin_holdout_v1"
    assert ev["rolling_origin"]["n_origins"] >= 3
    assert ev["rolling_origin"]["horizon_days"] == 14
    assert "last origin = test" in ev["holdout_designation"]
    assert {"bias", "wape", "mae", "mase", "fold_maes"} <= set(ev["metric_definitions"])
    # the one-sentence target definition is embedded
    assert ev["target_definition"].startswith("The forecast target is")
    ds = payload["dataset_metadata"]
    assert ds["source"]["url"].startswith("https://")
    assert len(ds["source"]["sha256"]) == 64
    assert "zero" in ds["zero_sales_caveat"].lower()
    assert ds["observed_panel"]["date_start"] < ds["observed_panel"]["date_end"]


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
        # same floor inside the multi-origin bundle (test origin)
        for d, naive in zip(
            entry["origins"]["test"]["actuals"]["dates"],
            entry["origins"]["test"]["models"]["naive"]["y_pred"],
            strict=True,
        ):
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
        k: v["mase"] for k, v in metrics.items() if not k.startswith("_") and isinstance(v, dict)
    }
    assert headline["challenger"] == "hgb"
    assert headline["strongest_naive"] == "seasonal_naive"
    # v1 headline keys survive the supersede
    assert set(headline) >= V1_HEADLINE_KEYS


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


def test_drift_guard_raises_on_tampered_protocol(
    demo_context: tuple[DemandSettings, ForecastConfig, pl.DataFrame],
) -> None:
    settings, config, _panel = demo_context
    eval_meta = json.loads((settings.reports_dir / "evaluation_metadata.json").read_text())
    eval_meta["test_origin"] = 1
    (settings.reports_dir / "evaluation_metadata.json").write_text(json.dumps(eval_meta))
    with pytest.raises(ValueError, match="test_origin"):
        build_demo_payload(settings, config, **CATALOG_ARGS)


def test_scalars_models_and_feature_schema(payload: dict) -> None:
    models = payload["scalars"]["models"]
    assert models["champion"] == "hgb_tuned" == models["global"]
    assert models["challenger"] == "hgb"
    assert models["naive"] == "seasonal_naive"
    schema = payload["scalars"]["feature_schema"]
    assert schema["lags"] == ["lag_1", "lag_7"]
    assert {"dow", "is_weekend", "doy_sin", "doy_cos"} <= set(schema["calendar"])
    band = payload["scalars"]["band"]
    assert band["target_coverage"] == 0.8
    assert 0.0 <= band["quantile_coverage_pooled"] <= 1.0


def test_payload_size_cap(tmp_path: Path) -> None:
    """A full-quota payload at production shape must fit the 3 MB cap."""
    from demand_forecasting.data import build_panel

    config = ForecastConfig(
        n_days=220, n_stores=15, n_products=10, lags=[1, 7], n_splits=3, gap=3, min_train_size=40
    )
    settings = DemandSettings(data_dir=tmp_path / "data", reports_dir=tmp_path / "reports")
    panel = build_panel(DemandSettings(), config)
    features = build_features(panel, config)
    settings.data_dir.mkdir(parents=True)
    settings.reports_dir.mkdir(parents=True)
    features.write_parquet(settings.data_dir / "features.parquet")

    result = _run_backtest(features, config)
    band = quantile_band_backtest(features, config)
    metrics = {
        r.name: {"mae": r.get("mae").value, "mase": r.get("mase").value} for r in result.runs
    }
    metrics["_meta"] = {"best_model": "hgb_tuned"}
    # pin the committed test-window MAE order so the rank-2 challenger is hgb
    # (ridge plays the strongest-rival rank-1 slot, as lgbm_tuned does on UCI)
    metrics["ridge"]["mae"] = float(metrics["hgb"]["mae"]) - 1.0
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
    _write_evaluation_metadata(settings.reports_dir, result)
    _write_dataset_metadata(settings.reports_dir)

    payload = build_demo_payload(settings, config)  # defaults: 100 x 180 x 14, 3 origins
    assert payload["scalars"]["catalog_summary"]["n_series"] == 100
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
