"""Evaluate stage: metrics, figures, and report assembly on synthetic predictions."""

import base64
import importlib.util
import json
import math
import struct
from pathlib import Path

import polars as pl
from mobility.config import MobilityConfig
from mobility.evaluate import (
    build_report,
    overall_metrics,
    p90_coverage,
    paired_mae_intervals,
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


def test_paired_mae_intervals_use_frozen_paired_errors() -> None:
    """Both resampling protocols retain the exact paired MAE delta and its sign."""
    demand = make_zone_hour_demand()
    preds = demand.select(["zone_id", "ts"]).with_columns(
        y_true=pl.lit(10.0),
        y_naive=pl.lit(12.0),
        y_gbm_xgb_tuned=pl.lit(10.5),
        y_gbm_lgbm_tuned=pl.lit(10.75),
    )
    block = paired_mae_intervals(preds, n_resamples=200)
    assert block["n_resamples"] == 200
    assert block["seed"] == 42
    assert block["day_block_length"] == 7
    assert set(block["comparisons"]) == {
        "gbm_xgb_tuned_vs_naive_lag24",
        "gbm_lgbm_tuned_vs_naive_lag24",
    }
    xgb = block["comparisons"]["gbm_xgb_tuned_vs_naive_lag24"]
    lgbm = block["comparisons"]["gbm_lgbm_tuned_vs_naive_lag24"]
    for comparison, expected in ((xgb, -1.5), (lgbm, -1.25)):
        for protocol in ("day_block", "zone_cluster"):
            assert comparison[protocol]["point_mae_delta"] == expected
            assert comparison[protocol]["ci95"] == [expected, expected]
    assert xgb["day_block"]["n_days"] == 10
    assert xgb["day_block"]["block_length_days"] == 7
    assert xgb["zone_cluster"]["n_zones"] == 2
    assert block == paired_mae_intervals(preds, n_resamples=200)


def test_build_report_writes_artifacts(cfg: MobilityConfig, curated: pl.DataFrame) -> None:
    preds = _predictions(cfg)
    cfg.models_dir.mkdir(parents=True, exist_ok=True)
    preds.write_parquet(cfg.models_dir / "predictions.parquet")
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "metrics.json").write_text(
        '{"_meta":{"schema_version":1,"git_sha":"fixture"}}'
    )
    report_path = build_report(cfg)
    assert report_path.exists()
    assert (cfg.reports_dir / "metrics.json").exists()
    figures = list((cfg.reports_dir / "figures").glob("*.html"))
    assert len(figures) >= 5
    metrics = json.loads((cfg.reports_dir / "metrics.json").read_text())
    assert "gbm_mean" in metrics and "mae" in metrics["gbm_mean"]
    assert metrics["_meta"]["n_test_rows"] == preds.height
    assert metrics["_meta"]["schema_version"] == 1
    assert metrics["_meta"]["git_sha"] == "fixture"


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


def test_zone_hour_heatmap_uses_global_top_zones_and_week_orientation() -> None:
    from mobility.evaluate import fig_zone_hour_heatmap

    rows = []
    for day in range(7, 14):
        for hour in range(24):
            for zone_id, zone, borough, pickups in (
                (1, "A", "Bronx", 1),
                (2, "B", "Manhattan", 100 + hour),
                (3, "C", "Queens", 50),
            ):
                rows.append(
                    {
                        "zone_id": zone_id,
                        "zone": zone,
                        "borough": borough,
                        "ts": f"2024-10-{day:02d}T{hour:02d}:00:00",
                        "pickup_count": pickups,
                    }
                )
    demand = pl.DataFrame(rows).with_columns(pl.col("ts").str.to_datetime())
    trace = fig_zone_hour_heatmap(demand, top_n=2).data[0]
    assert list(trace.y) == ["Manhattan / B", "Queens / C"]
    assert trace.x[0] == "D1 00h"
    assert trace.x[-1] == "D7 23h"
    assert len(trace.x) == 168
    assert len(trace.z) == 2
    assert all(len(row) == 168 for row in trace.z)


def _decode(arr: object) -> list:
    """Decode a plotly 6 binary array ({"bdata": ..., "dtype": ...}) or return as-is."""
    if isinstance(arr, dict) and "bdata" in arr:
        raw = base64.b64decode(arr["bdata"])
        fmt = {"f8": "d", "f4": "f", "i8": "q", "i4": "i", "u8": "Q", "u4": "I"}[
            arr.get("dtype", "f8")
        ]
        return list(struct.unpack(f"<{len(raw) // struct.calcsize(fmt)}{fmt}", raw))
    return list(arr)  # type: ignore[arg-type]


def test_committed_figure_titles_state_their_own_data() -> None:
    """Committed figure payloads (patched without a full re-run) must agree
    with the numbers in their own traces."""
    figures = Path(__file__).parents[1] / "reports" / "figures"

    heat = json.loads((figures / "hour_borough_heatmap.json").read_text())
    title = heat["layout"]["title"]["text"]
    trace = heat["data"][0]
    z = {b: _decode(row) for b, row in zip(trace["y"], trace["z"], strict=True)}
    manhattan = z["Manhattan"]
    peak = trace["x"][manhattan.index(max(manhattan))]
    assert f"Manhattan peaks at {max(manhattan):.1f} pickups/zone-hour at {peak}" in title
    assert f"the Bronx tops out at {max(z['Bronx']):.2f}" in title

    mae = json.loads((figures / "borough_mae.json").read_text())
    title = mae["layout"]["title"]["text"]
    bronx = {}
    for t in mae["data"]:
        xs = _decode(t["x"])
        bronx[t["name"]] = _decode(t["y"])[list(xs).index("Bronx")]
    assert bronx["naive_lag24"] < bronx["gbm_mean"]
    assert (
        "Persistence beats the GBM in the Bronx "
        f"({bronx['naive_lag24']:.2f} vs {bronx['gbm_mean']:.2f} MAE)" in title
    )

    conf = json.loads((figures / "conformal_coverage.json").read_text())
    title = conf["layout"]["title"]["text"]
    traces = {(t["name"], t.get("yaxis", "y")): t for t in conf["data"]}
    raw, conf_band = traces[("raw quantile band", "y")], traces[("stratum-conformal band", "y")]
    before = dict(zip(_decode(raw["x"]), _decode(raw["y"]), strict=True))
    after = dict(zip(_decode(conf_band["x"]), _decode(conf_band["y"]), strict=True))
    width_before = _decode(traces[("raw quantile band", "y2")]["y"])[0]
    width_after = _decode(traces[("stratum-conformal band", "y2")]["y"])[0]
    assert f"coverage {before['overall']:.1%} → {after['overall']:.1%}" in title
    assert f"{width_after - width_before:+.2f} pickups of band height" in title
    calib = json.loads((figures / "p90_calibration.json").read_text())
    calib_x = _decode(calib["data"][0]["x"])
    overall = _decode(calib["data"][0]["y"])[list(calib_x).index("OVERALL")]
    assert f"the {overall:.1%} headline is the full window" in title

    wx = json.loads((figures / "weather_elasticity.json").read_text())
    title = wx["layout"]["title"]["text"]
    trace = wx["data"][0]
    ratio = dict(zip(_decode(trace["x"]), _decode(trace["y"]), strict=True))
    below = {b: (1.0 - r) * 100.0 for b, r in ratio.items() if r < 1.0}
    assert {"Manhattan", "Queens", "Staten Island"} <= set(below)
    lo, hi = math.floor(min(below.values())), math.ceil(max(below.values()))
    assert f"average {lo}\u2013{hi}% fewer pickups in Manhattan, Queens and Staten Island" in title

    ladder = json.loads((figures / "gbm_vs_nn.json").read_text())
    title = ladder["layout"]["title"]["text"]
    traces = {t["name"]: t for t in ladder["data"]}
    mae_y = dict(zip(_decode(traces["mae"]["x"]), _decode(traces["mae"]["y"]), strict=True))
    mase_y = dict(zip(_decode(traces["mase"]["x"]), _decode(traces["mase"]["y"]), strict=True))
    leader = min(mae_y, key=lambda k: mae_y[k])
    assert "gbm" in leader and "tuned" in leader
    assert all(v < 1.0 for k, v in mase_y.items() if "naive" not in k)
    assert "The tuned GBM leads the run ladder" in title
    assert "every learned model beats persistence (MASE < 1)" in title
