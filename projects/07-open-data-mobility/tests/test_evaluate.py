"""Evaluate stage: metrics, figures, and report assembly on synthetic predictions."""

import importlib.util
import json
from pathlib import Path

import polars as pl
from mobility.config import MobilityConfig
from mobility.evaluate import (
    build_report,
    overall_metrics,
    p90_coverage,
    per_borough_mae,
    weather_elasticity,
)

_spec = importlib.util.spec_from_file_location(
    "mobility_test_helpers", Path(__file__).parent / "conftest.py"
)
assert _spec is not None and _spec.loader is not None
_helpers_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helpers_mod)
make_zone_hour_demand = _helpers_mod.make_zone_hour_demand


def _predictions(cfg: MobilityConfig) -> pl.DataFrame:
    demand = make_zone_hour_demand()
    return demand.select(
        [
            "zone_id",
            "borough",
            "ts",
            pl.col("pickup_count").alias("y_true"),
            pl.col("pickup_count").alias("lag_24"),
        ]
    ).with_columns(
        y_gbm=pl.col("y_true") * 0.9 + 0.2,
        y_p90=pl.col("y_true") * 1.5 + 1.0,
        y_nn=pl.col("y_true") * 0.8 + 0.3,
        y_naive=pl.col("lag_24"),
    )


def test_overall_metrics_ranking(cfg: MobilityConfig) -> None:
    runs = overall_metrics(_predictions(cfg))
    assert [r.name for r in runs] == ["naive_lag24", "gbm_mean", "temporal_net"]
    mae = {r.name: r.get("mae") for r in runs}
    assert mae["gbm_mean"] is not None
    assert mae["gbm_mean"] is not None and mae["gbm_mean"].value < 1.0  # near-perfect preds
    mape = {r.name: r.get("mape_pct") for r in runs}
    assert all(m is not None and m.value >= 0 for m in mape.values())


def test_per_borough_mae_and_coverage(cfg: MobilityConfig) -> None:
    preds = _predictions(cfg)
    mae = per_borough_mae(preds)
    assert set(mae["borough"].to_list()) == {"Manhattan", "Queens"}
    # predictions sit above the truth with headroom → coverage ≈ 1
    assert p90_coverage(preds) > 0.99


def test_weather_elasticity_groupby(cfg: MobilityConfig) -> None:
    """Queens rain hours (day 2, PRCP 5 mm) carry half the demand → ratio < 1."""
    demand = make_zone_hour_demand().with_columns(
        prcp_mm=pl.when((pl.col("zone_id") == 2) & (pl.col("ts").dt.day() == 2))
        .then(5.0)
        .otherwise(0.0),
        pickup_count=pl.when((pl.col("zone_id") == 2) & (pl.col("ts").dt.day() == 2))
        .then(1)
        .otherwise(pl.col("pickup_count")),
    )
    preds = demand.select(["zone_id", "borough", "ts", pl.col("pickup_count").alias("y_true")])
    out = weather_elasticity(preds, demand)
    assert set(out.columns) >= {
        "borough",
        "mean_pickups_dry",
        "mean_pickups_rain",
        "rain_vs_dry_ratio",
    }
    queens = out.filter(pl.col("borough") == "Queens").row(0, named=True)
    assert queens["rain_vs_dry_ratio"] < 1.0


def test_baseline_deltas_vs_naive(cfg: MobilityConfig) -> None:
    """Deltas record relative MAE/MAPE reduction vs naive_lag24.

    Explicit small frame: constant demand, imperfect persistence (y_naive=12 vs
    truth 10 → MAE 2), decent model (y_gbm → MAE 0.5), worse model (y_nn → MAE 1).
    """
    from mobility.evaluate import baseline_deltas

    demand = make_zone_hour_demand()
    preds = demand.select(
        [
            "zone_id",
            "borough",
            "ts",
            pl.lit(10.0).alias("y_true"),
            pl.lit(10.0).alias("lag_24"),
        ]
    ).with_columns(
        y_gbm=pl.lit(10.5),
        y_p90=pl.lit(15.0),
        y_nn=pl.lit(11.0),
        y_naive=pl.lit(12.0),
    )
    deltas = baseline_deltas(overall_metrics(preds))
    assert deltas["baseline"] == "naive_lag24"
    assert set(deltas) == {"baseline", "gbm_mean", "temporal_net"}
    assert deltas["gbm_mean"]["mae_reduction_pct"] == 75.0
    assert deltas["temporal_net"]["mae_reduction_pct"] == 50.0
    # zero-baseline guard: a perfect naive produces no deltas, no ZeroDivisionError
    perfect = preds.with_columns(y_naive=pl.col("y_true"))
    assert baseline_deltas(overall_metrics(perfect)) == {"baseline": "naive_lag24"}


def test_build_report_writes_artifacts(cfg: MobilityConfig, curated: pl.DataFrame) -> None:
    preds = _predictions(cfg)
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    preds.write_parquet(cfg.models_dir / "predictions.parquet")
    report_path = build_report(cfg)
    assert report_path.exists()
    assert (cfg.reports_dir / "metrics.json").exists()
    figures = list((cfg.reports_dir / "figures").glob("*.html"))
    assert len(figures) >= 5
    metrics = json.loads((cfg.reports_dir / "metrics.json").read_text())
    assert "gbm_mean" in metrics and "mae" in metrics["gbm_mean"]
    assert metrics["_meta"]["n_test_rows"] == preds.height


def test_hour_borough_heatmap_matches_groupby() -> None:
    """Heatmap payload is exactly the hour x borough mean-pickups aggregate."""
    from mobility.evaluate import fig_hour_borough_heatmap

    demand = make_zone_hour_demand()
    fig = fig_hour_borough_heatmap(demand)
    trace = fig.data[0]
    assert trace.type == "heatmap"
    assert len(trace.x) == 24
    assert list(trace.y) == ["Manhattan", "Queens"]
    expected = (
        demand.with_columns(hour=pl.col("ts").dt.hour())
        .group_by(["borough", "hour"])
        .agg(pl.col("pickup_count").mean().alias("mean_pickups"))
    )
    for borough, row in zip(trace.y, trace.z, strict=True):
        want = expected.filter(pl.col("borough") == borough).sort("hour")["mean_pickups"].to_list()
        assert list(row) == want
