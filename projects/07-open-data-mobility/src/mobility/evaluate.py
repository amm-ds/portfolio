"""Evaluation: metrics, figures, business insights, report assembly.

Pure read stage: consumes ``reports/models/predictions.parquet`` (written by
the train stages) plus the curated zone-hour table for the demand figures.
Everything lands in ``reports/``: metrics.json, report.html, figures/*.html
(+ *.json for the showcase app). The ``dashboard`` command re-runs
:func:`build_report` alone so DVC has a dedicated report-assembly stage.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import apply_theme, save_html, save_json
from portfolio_eval.metrics import MetricResult, RunResult, compare_runs
from portfolio_eval.ml import RunComparison, regression_metrics
from portfolio_eval.report import EvalReport

from mobility.config import MobilityConfig, get_config

logger = get_logger(__name__)

MODEL_PREDS = [("naive_lag24", "y_naive"), ("gbm_mean", "y_gbm"), ("temporal_net", "y_nn")]
WEEK_START = datetime(2024, 10, 7)  # first full Monday of the test window


def _run_metrics(preds: pl.DataFrame, name: str, col: str) -> RunResult:
    results = regression_metrics(preds["y_true"].to_list(), preds[col].to_list())
    return RunResult(
        name=name,
        metrics=[
            MetricResult(m.name, m.value, higher_is_better=False, split="test") for m in results
        ],
    )


def overall_metrics(preds: pl.DataFrame) -> list[RunResult]:
    """MAE/RMSE/MAPE per model on the temporal test window."""
    return [_run_metrics(preds, name, col) for name, col in MODEL_PREDS]


def baseline_deltas(
    runs: list[RunResult], baseline: str = "naive_lag24"
) -> dict[str, dict[str, float]]:
    """Relative MAE/MAPE reduction of each run vs the persistence baseline.

    A zero baseline metric (possible on degenerate fixtures) yields no delta
    for that metric rather than a ZeroDivisionError.
    """
    base = next(r for r in runs if r.name == baseline)
    out: dict[str, dict[str, float]] = {}
    for metric in ("mae", "mape_pct"):
        base_val = base.get(metric)
        assert base_val is not None
        if base_val.value == 0:
            continue
        for r in runs:
            if r.name == baseline:
                continue
            m = r.get(metric)
            assert m is not None
            out.setdefault(r.name, {})[f"{metric}_reduction_pct"] = round(
                (base_val.value - m.value) / base_val.value * 100, 2
            )
    return out


def per_borough_mae(preds: pl.DataFrame, col: str = "y_gbm") -> pl.DataFrame:
    """Zone-hour absolute error grouped by borough (honest groupby, no model)."""
    return (
        preds.with_columns(abs_err=(pl.col(col) - pl.col("y_true")).abs())
        .group_by("borough")
        .agg(pl.col("abs_err").mean().alias("mae"), pl.len().alias("n_rows"))
        .sort("mae", descending=True)
    )


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------


def fig_eda_trips_profile(demand: pl.DataFrame) -> go.Figure:
    """EDA: mean pickups by hour-of-day, one series per borough (curated grain)."""
    by_hour = (
        demand.with_columns(hour=pl.col("ts").dt.hour())
        .group_by(["borough", "hour"])
        .agg(pl.col("pickup_count").mean().alias("mean_pickups"))
        .sort(["borough", "hour"])
    )
    fig = go.Figure()
    for borough in by_hour["borough"].unique().sort().to_list():
        b = by_hour.filter(pl.col("borough") == borough)
        fig.add_scatter(
            x=b["hour"].to_list(),
            y=b["mean_pickups"].to_list(),
            name=borough,
            mode="lines+markers",
        )
    fig.update_layout(
        title="Demand profile by hour of day and borough (2024, mean pickups/zone-hour)",
        xaxis_title="hour of day",
        yaxis_title="mean pickups per zone-hour",
        xaxis={"dtick": 1},
    )
    return apply_theme(fig)


def fig_zone_hour_heatmap(demand: pl.DataFrame, top_n: int = 30) -> go.Figure:
    """(a) Demand heatmap: top-N zones x hour-of-week for the selected week.

    ``demand`` must carry a ``zone`` label column (joined from zones.parquet).
    """
    week = demand.filter(
        pl.col("ts").is_between(WEEK_START, WEEK_START + pl.duration(days=7), closed="left")
    )
    top_zones = (
        week.group_by(["zone_id", "zone"])
        .agg(pl.col("pickup_count").sum())
        .sort("pickup_count", descending=True)
        .head(top_n)
    )
    grid = (
        week.join(top_zones.select(["zone_id", "zone"]), on="zone_id")
        .with_columns(hour_of_week=(pl.col("ts").dt.weekday() - 1) * 24 + pl.col("ts").dt.hour())
        .group_by(["zone", "hour_of_week"])
        .agg(pl.col("pickup_count").mean())
        .pivot(on="hour_of_week", index="zone", values="pickup_count")
        .sort("zone")
    )
    zones = grid["zone"].to_list()
    hours = sorted(int(c) for c in grid.columns if c != "zone")
    fig = go.Figure(
        data=go.Heatmap(
            z=grid.select([str(h) for h in hours]).to_numpy(),
            x=[f"D{h // 24 + 1} {h % 24:02d}h" for h in hours],
            y=zones,
            colorscale="Teal",
            colorbar={"title": "pickups/h"},
        )
    )
    fig.update_layout(
        title=f"Zone x hour-of-week demand — week of {WEEK_START.date()} (top {top_n} zones)",
        xaxis_title="hour of week (Mon → Sun)",
        yaxis_title="zone",
    )
    return apply_theme(fig, height=760)


def fig_actual_vs_pred(preds: pl.DataFrame, top_n: int = 5, days: int = 14) -> go.Figure:
    """(b) Actual vs predicted for the top-N busiest zones (test window slice)."""
    top_zones = (
        preds.group_by(["zone_id", "borough"])
        .agg(pl.col("y_true").sum())
        .sort("y_true", descending=True)
        .head(top_n)["zone_id"]
        .to_list()
    )
    window = preds.filter(
        pl.col("ts").is_between(WEEK_START, WEEK_START + pl.duration(days=days), closed="left"),
        pl.col("zone_id").is_in(top_zones),
    )
    fig = make_subplots(
        rows=len(top_zones),
        cols=1,
        shared_xaxes=True,
        subplot_titles=[f"zone {z}" for z in top_zones],
        vertical_spacing=0.05,
    )
    for i, zid in enumerate(top_zones, start=1):
        zdf = window.filter(pl.col("zone_id") == zid).sort("ts")
        fig.add_trace(
            go.Scatter(x=zdf["ts"].to_list(), y=zdf["y_true"].to_list(), name="actual"),
            row=i,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=zdf["ts"].to_list(), y=zdf["y_gbm"].to_list(), name="gbm"),
            row=i,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=zdf["ts"].to_list(), y=zdf["y_nn"].to_list(), name="temporal_net"),
            row=i,
            col=1,
        )
    fig.update_layout(
        title=(
            f"Actual vs predicted demand — top {top_n} zones, {days} days from {WEEK_START.date()}"
        ),
        hovermode="x unified",
    )
    return apply_theme(fig, height=300 * len(top_zones))


def fig_borough_mae(preds: pl.DataFrame) -> go.Figure:
    """(c) Per-borough MAE for each model."""
    fig = go.Figure()
    for name, col in MODEL_PREDS:
        mae = (
            preds.with_columns(abs_err=(pl.col(col) - pl.col("y_true")).abs())
            .group_by("borough")
            .agg(pl.col("abs_err").mean())
            .sort("borough")
        )
        fig.add_bar(name=name, x=mae["borough"].to_list(), y=mae["abs_err"].to_list())
    fig.update_layout(
        barmode="group", title="Per-borough test MAE by model", yaxis_title="MAE (pickups/hour)"
    )
    return apply_theme(fig)


def weather_elasticity(preds: pl.DataFrame, demand: pl.DataFrame) -> pl.DataFrame:
    """(d) Honest rain-vs-dry demand ratio per borough on the test window.

    Joins predictions back to the curated weather columns, then a plain
    groupby: dry (PRCP = 0) vs rain (PRCP ≥ 1 mm) hourly demand, with sample
    counts. Caveat (reported alongside): hour-of-week mix is not normalised.
    """
    weather = demand.select(["zone_id", "ts", "prcp_mm", "tmax_c"])
    joined = preds.join(weather, on=["zone_id", "ts"], how="left").with_columns(
        condition=pl.when(pl.col("prcp_mm") >= 1.0).then(pl.lit("rain")).otherwise(pl.lit("dry"))
    )
    by_borough = (
        joined.group_by(["borough", "condition"])
        .agg(pl.col("y_true").mean().alias("mean_pickups"), pl.len().alias("n_hours"))
        .pivot(on="condition", index="borough", values=["mean_pickups", "n_hours"])
    )
    for col in ("mean_pickups_rain", "n_hours_rain"):
        if col not in by_borough.columns:
            by_borough = by_borough.with_columns(**{col: pl.lit(None, dtype=pl.Float64)})
    return by_borough.with_columns(
        rain_vs_dry_ratio=(pl.col("mean_pickups_rain") / pl.col("mean_pickups_dry"))
    ).sort("rain_vs_dry_ratio")


def fig_weather_elasticity(by_borough: pl.DataFrame) -> go.Figure:
    fig = go.Figure(
        data=go.Bar(
            x=by_borough["borough"].to_list(),
            y=by_borough["rain_vs_dry_ratio"].to_list(),
            marker_color="#38bdf8",
            text=[
                f"{v:.3f}" if v is not None else "-"
                for v in by_borough["rain_vs_dry_ratio"].to_list()
            ],
            textposition="outside",
        )
    )
    fig.add_hline(y=1.0, line_dash="dash", line_color="#f472b6")
    fig.update_layout(
        title="Weather elasticity: mean hourly pickups, rain (≥1 mm) vs dry, by borough",
        yaxis_title="rain / dry ratio",
    )
    return apply_theme(fig)


def fig_p90_band(preds: pl.DataFrame, days: int = 14) -> go.Figure:
    """Uncertainty band: actual vs GBM mean + p90 upper band, city-wide."""
    window = preds.filter(
        pl.col("ts").is_between(WEEK_START, WEEK_START + pl.duration(days=days), closed="left")
    )
    city = (
        window.group_by("ts")
        .agg([pl.col(c).sum() for c in ["y_true", "y_gbm", "y_p90"]] + [pl.len().alias("n_zones")])
        .sort("ts")
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=city["ts"].to_list(),
            y=city["y_p90"].to_list(),
            name="p90 band (upper)",
            line={"dash": "dot", "color": "#fbbf24"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=city["ts"].to_list(),
            y=city["y_gbm"].to_list(),
            name="gbm mean",
            line={"color": "#2dd4bf"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=city["ts"].to_list(),
            y=city["y_true"].to_list(),
            name="actual",
            line={"color": "#f472b6"},
        )
    )
    fig.update_layout(
        title=f"City-wide demand with p90 uncertainty band — {days} days from {WEEK_START.date()}"
    )
    return apply_theme(fig)


def p90_coverage(preds: pl.DataFrame) -> float:
    """Fraction of actuals at or below the p90 prediction (~0.9 = calibrated)."""
    return cast(float, (preds["y_true"] <= preds["y_p90"]).mean())


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------


def _markdown(df: pl.DataFrame, floatfmt: str = "{:.4f}") -> str:
    cols = df.columns
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.iter_rows(named=True):
        cells = []
        for c in cols:
            v = row[c]
            if v is None:
                cells.append("-")
            elif isinstance(v, float):
                cells.append(floatfmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_report(cfg: MobilityConfig | None = None) -> Path:
    """Assemble metrics.json + report.html + figures from persisted artifacts."""
    cfg = cfg or get_config()
    preds_path = cfg.models_dir / "predictions.parquet"
    if not preds_path.exists():
        raise FileNotFoundError(f"missing {preds_path} — run the train stages first")
    preds = pl.read_parquet(preds_path)
    demand = pl.read_parquet(cfg.zone_hour_demand_path)
    zones = pl.read_parquet(cfg.zones_path)

    runs = overall_metrics(preds)
    comparison_md = RunComparison(runs).to_markdown()
    ranking = compare_runs(runs, "mae")
    borough_mae = per_borough_mae(preds)
    weather = weather_elasticity(preds, demand)
    coverage = p90_coverage(preds)
    demand_zoned = demand.join(
        zones.select(["location_id", "zone"]), left_on="zone_id", right_on="location_id"
    )

    figures = {
        "eda_trips_profile": fig_eda_trips_profile(demand),
        "zone_hour_heatmap": fig_zone_hour_heatmap(demand_zoned),
        "actual_vs_pred_top5": fig_actual_vs_pred(preds),
        "borough_mae": fig_borough_mae(preds),
        "weather_elasticity": fig_weather_elasticity(weather),
        "p90_band": fig_p90_band(preds),
        "gbm_vs_nn": RunComparison(runs).figure(metric_names=["mae", "rmse", "mape_pct"]),
    }

    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = cfg.reports_dir / "figures"
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")

    metrics: dict[str, Any] = {r.name: {m.name: m.value for m in r.metrics} for r in runs}
    metrics["_meta"] = {
        "split": f"temporal holdout from {cfg.train_cutoff.isoformat()}",
        "p90_coverage": coverage,
        "n_test_rows": preds.height,
        "mae_ranking": ranking["ranking"],
    }
    metrics["deltas"] = {
        "baseline": "naive_lag24",
        **baseline_deltas(runs),
    }
    (cfg.reports_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    report = EvalReport(title="Project 07 — Urban Mobility Demand Intelligence")
    report.add_markdown_table("Overall test metrics (next-hour pickups)", comparison_md)
    report.add_markdown_table("Per-borough test MAE (gbm_mean)", _markdown(borough_mae))
    report.add_markdown_table(
        "Weather elasticity: rain vs dry by borough",
        _markdown(weather),
    )
    weather_obs = weather.drop_nulls("rain_vs_dry_ratio")  # boroughs without rain hours
    if weather_obs.height > 0:
        driest = weather_obs.sort("rain_vs_dry_ratio").row(0, named=True)
        wettest = weather_obs.sort("rain_vs_dry_ratio", descending=True).row(0, named=True)
        rain_insight = (
            f"<li><b>Rain suppresses curb demand:</b> the wettest-borough ratio is "
            f"{wettest['borough']} at {wettest['rain_vs_dry_ratio']:.3f}x dry-hour demand, "
            f"the most resilient is {driest['borough']} at "
            f"{driest['rain_vs_dry_ratio']:.3f}x.</li>"
        )
    else:
        rain_insight = (
            "<li>No rainy hours in the evaluation window — elasticity not applicable.</li>"
        )
    report.add_html(
        "Business insights",
        "<ul>"
        + rain_insight
        + (
            f"<li><b>p90 uncertainty band calibration:</b> {coverage:.1%} of "
            "realised zone-hours fall at or below the quantile-GBM upper band "
            "(target 90%) — usable for fleet/staffing buffers.</li>"
        )
        + (
            f"<li><b>Best model by MAE:</b> {ranking['ranking'][0]} "
            f"({metrics[ranking['ranking'][0]]['mae']:.3f} pickups/hour MAE city-wide).</li>"
        )
        + (
            "<li>Caveat: rain/dry ratios are raw groupbys — hour-of-week mix "
            "is not normalised; treat them as directional elasticity, not "
            "causal estimates.</li>"
        )
        + "</ul>",
    )
    for name in figures:
        report.add_html(
            name.replace("_", " ").title(),
            f'<p><a href="figures/{name}.html">interactive figure</a> '
            f"(<code>figures/{name}.html</code>)</p>",
        )
    return report.write(cfg.reports_dir / "report.html")


def evaluate(cfg: MobilityConfig | None = None) -> Path:
    """Evaluate entry point (alias kept for the CLI/dvc stage name)."""
    path = build_report(cfg)
    logger.info("report -> %s", path)
    return path
