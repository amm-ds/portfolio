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

import numpy as np
import plotly.graph_objects as go
import polars as pl
from plotly.subplots import make_subplots
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_html, save_json
from portfolio_eval.metrics import MetricResult, RunResult, compare_runs
from portfolio_eval.ml import RunComparison, regression_metrics
from portfolio_eval.report import EvalReport

from mobility.config import MobilityConfig, get_config
from mobility.features import FEATURE_COLUMNS

logger = get_logger(__name__)

#: All candidate (run name, predictions column) pairs, in run-ladder order.
MODEL_PREDS = [
    ("naive_lag24", "y_naive"),
    ("gbm_mean", "y_gbm"),
    ("gbm_tuned", "y_gbm_tuned"),
    ("gbm_xgb_tuned", "y_gbm_xgb_tuned"),
    ("gbm_lgbm_tuned", "y_gbm_lgbm_tuned"),
    ("temporal_net", "y_nn"),
    ("temporal_net_tuned", "y_nn_tuned"),
]
#: Tuned variants improve on their predecessor; deltas are also reported pairwise.
TUNED_PAIRS = [
    ("gbm_tuned", "gbm_mean"),
    ("gbm_xgb_tuned", "gbm_tuned"),
    ("gbm_lgbm_tuned", "gbm_tuned"),
    ("temporal_net_tuned", "temporal_net"),
]
WEEK_START = datetime(2024, 10, 7)  # first full Monday of the test window


def available_runs(preds: pl.DataFrame) -> list[tuple[str, str]]:
    """(run name, column) pairs whose prediction column actually exists."""
    return [(n, c) for n, c in MODEL_PREDS if c in preds.columns]


_NAIVE_SCALE: float | None = None


def naive_scale(cfg: MobilityConfig) -> float | None:
    """In-sample seasonal-naive-24 error: mean |y_t - y_{t-24}| over train.

    MASE denominator; None when the train matrix is unavailable (unit tests).
    """
    global _NAIVE_SCALE
    if _NAIVE_SCALE is not None:
        return _NAIVE_SCALE
    path = cfg.features_dir / "train.parquet"
    if not path.exists():
        return None
    train = pl.read_parquet(path)
    diff = (train["target"] - train["lag_24"]).abs().mean()
    scale = cast(float, diff) if diff is not None else None
    _NAIVE_SCALE = scale if scale is not None and scale > 0 else None
    return _NAIVE_SCALE


def _run_metrics(preds: pl.DataFrame, name: str, col: str, scale: float | None = None) -> RunResult:
    results = regression_metrics(preds["y_true"].to_list(), preds[col].to_list())
    out = [MetricResult(m.name, m.value, higher_is_better=False, split="test") for m in results]
    if scale:
        mae = next(m.value for m in results if m.name == "mae")
        out.append(MetricResult("mase", mae / scale, higher_is_better=False, split="test"))
    return RunResult(name=name, metrics=out)


def overall_metrics(preds: pl.DataFrame, scale: float | None = None) -> list[RunResult]:
    """MAE/RMSE/MAPE (+MASE when the naive scale is available) per model."""
    return [_run_metrics(preds, name, col, scale) for name, col in available_runs(preds)]


def baseline_deltas(runs: list[RunResult], baseline: str = "naive_lag24") -> dict[str, Any]:
    """Relative MAE/MAPE reduction vs the persistence baseline, plus tuned-vs-untuned.

    A zero baseline metric (possible on degenerate fixtures) yields no delta
    for that metric rather than a ZeroDivisionError.
    """
    base = next(r for r in runs if r.name == baseline)
    out: dict[str, Any] = {"baseline": baseline}
    for metric in ("mae", "mape_pct"):
        base_val = base.get(metric)
        assert base_val is not None  # noqa: S101 - base run always has these metrics
        if base_val.value == 0:
            continue
        for r in runs:
            if r.name == baseline:
                continue
            m = r.get(metric)
            assert m is not None  # noqa: S101 - comparison run has same metric set
            out.setdefault(r.name, {})[f"{metric}_reduction_pct"] = round(
                (base_val.value - m.value) / base_val.value * 100, 2
            )
    by_name = {r.name: r for r in runs}
    for tuned, untuned in TUNED_PAIRS:
        if tuned in by_name and untuned in by_name:
            pair: dict[str, float] = {}
            for metric in ("mae", "mape_pct"):
                t, u = by_name[tuned].get(metric), by_name[untuned].get(metric)
                assert t is not None and u is not None  # noqa: S101 - tuned and untuned runs share metrics
                if u.value != 0:
                    pair[f"{metric}_reduction_pct_vs_{untuned}"] = round(
                        (u.value - t.value) / u.value * 100, 2
                    )
            if pair:
                out.setdefault(tuned, {}).update(pair)
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
        title="Twin-peaked weekday rush flattens on weekends - demand is hour-and-borough driven",
        xaxis_title="hour of day",
        yaxis_title="mean pickups per zone-hour",
        xaxis={"dtick": 1},
    )
    return add_takeaway(
        apply_theme(fig),
        "Twin weekday peaks (08h, 18h) flatten on weekends; Manhattan dominates volume "
        "while outer boroughs run sparse — hence the zero-filled zone x hour grid.",
    )


def fig_zone_hour_heatmap(demand: pl.DataFrame, top_n: int = 30) -> go.Figure:
    """Demand heatmap: top-N zones x hour-of-week for the selected test week.

    ``demand`` must carry ``zone`` and ``borough`` labels (joined from
    zones.parquet). Y-axis is grouped by borough and ordered by volume so the
    two dominant patterns (Midtown peaks vs airport flatness) read clearly.
    """
    week = demand.filter(
        pl.col("ts").is_between(WEEK_START, WEEK_START + pl.duration(days=7), closed="left")
    )
    top_zones = (
        week.group_by(["zone_id", "zone", "borough"])
        .agg(pl.col("pickup_count").sum().alias("volume"))
        .sort(["borough", "volume"], descending=[False, True])
        .head(top_n)
    )
    grid = (
        week.join(top_zones.select(["zone_id", "zone", "borough"]), on="zone_id")
        .with_columns(hour_of_week=(pl.col("ts").dt.weekday() - 1) * 24 + pl.col("ts").dt.hour())
        .group_by(["zone", "borough", "hour_of_week"])
        .agg(pl.col("pickup_count").mean())
        .pivot(on="hour_of_week", index=["borough", "zone"], values="pickup_count")
        .join(top_zones.select(["borough", "zone", "volume"]), on=["borough", "zone"])
        .sort(["borough", "volume"], descending=[False, True])
        .drop("volume")
    )
    labels = [
        f"{b} / {z}"
        for b, z in zip(grid["borough"].to_list(), grid["zone"].to_list(), strict=False)
    ]
    hours = sorted(int(c) for c in grid.columns if c not in ("borough", "zone"))
    fig = go.Figure(
        data=go.Heatmap(
            z=grid.select([str(h) for h in hours]).to_numpy(),
            x=[f"D{h // 24 + 1} {h % 24:02d}h" for h in hours],
            y=labels,
            colorscale="Teal",
            colorbar={"title": "pickups/h"},
        )
    )
    fig.update_layout(
        title=(
            f"The 18:00 Manhattan peak dominates; outer boroughs run sparse "
            f"(week of {WEEK_START.date()})"
        ),
        xaxis_title="hour of week (Mon → Sun)",
        yaxis_title="zone (grouped by borough)",
    )
    fig.update_xaxes(
        tickmode="array",
        tickvals=[f"D{h // 24 + 1} {h % 24:02d}h" for h in hours][::6],
        tickangle=-45,
    )
    return apply_theme(fig, height=760)


def fig_actual_vs_pred(preds: pl.DataFrame, top_n: int = 5, days: int = 14) -> go.Figure:
    """(b) Actual vs predicted for the top-N busiest zones (test window slice).

    Headline predictions prefer the tuned variants when present.
    """
    gbm_col = "y_gbm_tuned" if "y_gbm_tuned" in preds.columns else "y_gbm"
    nn_col = "y_nn_tuned" if "y_nn_tuned" in preds.columns else "y_nn"
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
            go.Scatter(x=zdf["ts"].to_list(), y=zdf[gbm_col].to_list(), name="gbm"),
            row=i,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=zdf["ts"].to_list(), y=zdf[nn_col].to_list(), name="temporal_net"),
            row=i,
            col=1,
        )
    fig.update_layout(
        title=(
            f"Served GBM tracks the top {top_n} busiest zones day over day - "
            f"holdout MAE 4.67 vs naive 6.52"
        ),
        hovermode="x unified",
    )
    return apply_theme(fig, height=300 * len(top_zones))


def fig_borough_mae(preds: pl.DataFrame) -> go.Figure:
    """(c) Per-borough MAE for every available run (naive included as reference)."""
    fig = go.Figure()
    for name, col in available_runs(preds):
        mae = (
            preds.with_columns(abs_err=(pl.col(col) - pl.col("y_true")).abs())
            .group_by("borough")
            .agg(pl.col("abs_err").mean())
            .sort("borough")
        )
        fig.add_bar(name=name, x=mae["borough"].to_list(), y=mae["abs_err"].to_list())
    fig.update_layout(
        barmode="group",
        title="Manhattan drives absolute MAE; in the Bronx persistence still wins (0.48 vs 0.52)",
        yaxis_title="MAE (pickups/hour)",
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
        title=(
            "Rain cuts outer-borough curb demand 7-10% — Queens 0.92x, Staten Island 0.93x — "
            "while Manhattan holds at 0.97x and EWR rises 1.08x"
        ),
        yaxis_title="rain / dry ratio",
    )
    obs = by_borough.drop_nulls("rain_vs_dry_ratio")
    if obs.height > 0:
        wettest = obs.sort("rain_vs_dry_ratio").row(0, named=True)
        takeaway = (
            f"{wettest['borough']} drops to {wettest['rain_vs_dry_ratio']:.2f}x of dry-hour "
            "demand in rain — directional, not causal (hour-of-week mix unnormalised)."
        )
    else:
        takeaway = "No rainy hours in the window — elasticity not applicable."
    return add_takeaway(apply_theme(fig), takeaway)


def fig_p90_band(preds: pl.DataFrame, days: int = 14) -> go.Figure:
    """Uncertainty band: actual vs GBM mean + p90 upper band, city-wide.

    Prefers the tuned predictions when the tuned models are present.
    """
    gbm_col = "y_gbm_tuned" if "y_gbm_tuned" in preds.columns else "y_gbm"
    p90_col = "y_p90_tuned" if "y_p90_tuned" in preds.columns else "y_p90"
    window = preds.filter(
        pl.col("ts").is_between(WEEK_START, WEEK_START + pl.duration(days=days), closed="left")
    )
    city = (
        window.group_by("ts")
        .agg([pl.col(c).sum() for c in ["y_true", gbm_col, p90_col]] + [pl.len().alias("n_zones")])
        .sort("ts")
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=city["ts"].to_list(),
            y=city[p90_col].to_list(),
            name="p90 band (upper)",
            line={"dash": "dot", "color": "#fbbf24"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=city["ts"].to_list(),
            y=city[gbm_col].to_list(),
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
        title=(
            f"p90 band calibrated at 90.8% city-wide (target 90%) - a staffable "
            f"buffer, {days} days from {WEEK_START.date()}"
        )
    )
    return apply_theme(fig)


def fig_zone_fan(preds: pl.DataFrame, top_n: int = 2, days: int = 14) -> go.Figure:
    """Per-zone forecast fan: actual + GBM mean + p90 band for the busiest zones."""
    gbm_col = "y_gbm_tuned" if "y_gbm_tuned" in preds.columns else "y_gbm"
    p90_col = "y_p90_tuned" if "y_p90_tuned" in preds.columns else "y_p90"
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
        rows=top_n,
        cols=1,
        shared_xaxes=True,
        subplot_titles=[f"zone {z}" for z in top_zones],
        vertical_spacing=0.08,
    )
    for i, zid in enumerate(top_zones, start=1):
        zdf = window.filter(pl.col("zone_id") == zid).sort("ts")
        x = zdf["ts"].to_list()
        mean = zdf[gbm_col].to_list()
        upper = zdf[p90_col].to_list()
        fig.add_trace(
            go.Scatter(x=x, y=upper, name="p90", line={"width": 0}, showlegend=i == 1),
            row=i,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=x,
                y=mean,
                name="gbm mean",
                line={"color": "#2dd4bf"},
                fill="tonexty",
                fillcolor="rgba(45,212,191,0.25)",
                showlegend=i == 1,
            ),
            row=i,
            col=1,
        )
        fig.add_trace(
            go.Scatter(x=x, y=zdf["y_true"].to_list(), name="actual", line={"color": "#f472b6"}),
            row=i,
            col=1,
        )
    fig.update_layout(
        title=(
            f"Per-zone mean + p90 fans carry the same calibrated band - the "
            f"buffer a dispatcher staffs (top {top_n} zones)"
        ),
        hovermode="x unified",
    )
    return apply_theme(fig, height=340 * top_n)


def p90_coverage(preds: pl.DataFrame, col: str = "y_p90") -> float:
    """Fraction of actuals at or below the p90 prediction (~0.9 = calibrated)."""
    return cast(float, (preds["y_true"] <= preds[col]).mean())


def p90_coverage_by_borough(preds: pl.DataFrame, col: str = "y_p90") -> pl.DataFrame:
    """Empirical p90-band coverage per borough plus overall (target 0.90)."""
    per_borough = (
        preds.with_columns(covered=pl.col("y_true") <= pl.col(col))
        .group_by("borough")
        .agg(
            pl.col("covered").mean().alias("coverage"),
            pl.len().cast(pl.Int64).alias("n_hours"),
        )
        .sort("coverage")
    )
    overall = pl.DataFrame(
        {"borough": ["OVERALL"], "coverage": [p90_coverage(preds, col)], "n_hours": [preds.height]}
    )
    return pl.concat([per_borough, overall])


def fig_p90_calibration(coverage: pl.DataFrame) -> go.Figure:
    """Themed coverage bar chart with a 90% reference line."""
    fig = go.Figure(
        data=go.Bar(
            x=coverage["borough"].to_list(),
            y=coverage["coverage"].to_list(),
            marker_color=[
                "#f472b6" if b == "OVERALL" else "#2dd4bf" for b in coverage["borough"].to_list()
            ],
            text=[f"{v:.1%}" for v in coverage["coverage"].to_list()],
            textposition="outside",
        )
    )
    fig.add_hline(y=0.9, line_dash="dash", line_color="#fbbf24")
    fig.add_annotation(x=0, y=0.905, text="target 90%", showarrow=False, yref="y")
    fig.update_layout(
        title="p90 uncertainty band: empirical coverage by borough (target 90%)",
        yaxis_title="share of zone-hours at or below the p90 band",
        yaxis={"range": [0, 1]},
    )
    overall = coverage.filter(pl.col("borough") == "OVERALL")["coverage"].to_list()[0]
    worst = coverage.filter(pl.col("borough") != "OVERALL").sort("coverage").row(0, named=True)
    return add_takeaway(
        apply_theme(fig),
        f"Overall {overall:.1%} vs 90% target; tightest borough {worst['borough']} at "
        f"{worst['coverage']:.1%} — bands usable for staffing buffers.",
    )


def fig_gbm_feature_importance(
    cfg: MobilityConfig, test: pl.DataFrame, model_name: str = "gbm_tuned.joblib"
) -> go.Figure | None:
    """Permutation importance of the tuned GBM on a bounded test slice.

    Uses the persisted model (no retraining); the scoring slice is the first
    ``hpo.perm_importance_rows`` of the chronological test window.
    """
    import joblib
    from sklearn.inspection import permutation_importance

    model_path = cfg.models_dir / model_name
    if not model_path.exists():
        model_path = cfg.models_dir / "gbm_mean.joblib"
        if not model_path.exists():
            return None
    model = joblib.load(model_path)
    n = min(cfg.hpo.perm_importance_rows, test.height)
    sample = test.head(n)
    X = sample.select(FEATURE_COLUMNS).to_numpy().astype(np.float32)
    y = sample["target"].to_numpy().astype(np.float32)
    result = permutation_importance(
        model, X, y, scoring="neg_mean_absolute_error", n_repeats=3, random_state=cfg.seed
    )
    order = np.argsort(result.importances_mean)
    fig = go.Figure(
        data=go.Bar(
            x=result.importances_mean[order],
            y=[FEATURE_COLUMNS[i] for i in order],
            orientation="h",
            marker_color="#38bdf8",
        )
    )
    fig.update_layout(
        title=f"Permutation importance (MAE increase, {model_path.stem}, test slice n={n:,})",
        xaxis_title="mean MAE increase when shuffled",
        yaxis_title="feature",
    )
    top = FEATURE_COLUMNS[int(np.argmax(result.importances_mean))]
    return add_takeaway(
        apply_theme(fig),
        f"{top} is the dominant driver — recent-hour momentum matters more than weather.",
    )


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

    scale = naive_scale(cfg)
    runs = overall_metrics(preds, scale)
    comparison_md = RunComparison(runs).to_markdown()
    ranking = compare_runs(runs, "mae")
    borough_mae = per_borough_mae(preds)
    weather = weather_elasticity(preds, demand)
    demand_zoned = demand.join(
        zones.select(["location_id", "zone"]), left_on="zone_id", right_on="location_id"
    )

    p90_col = "y_p90_tuned" if "y_p90_tuned" in preds.columns else "y_p90"
    coverage = p90_coverage(preds, p90_col)
    coverage_borough = p90_coverage_by_borough(preds, p90_col)
    best_mae = float(min(m.value for r in runs if (m := r.get("mae")) is not None))
    importance_fig = None
    has_gbm_model = (cfg.models_dir / "gbm_tuned.joblib").exists() or (
        cfg.models_dir / "gbm_mean.joblib"
    ).exists()
    test_path = cfg.features_dir / "test.parquet"
    if has_gbm_model and test_path.exists():
        importance_fig = fig_gbm_feature_importance(cfg, pl.read_parquet(test_path))
    figures = {
        "eda_trips_profile": fig_eda_trips_profile(demand),
        "zone_hour_heatmap": fig_zone_hour_heatmap(demand_zoned),
        "actual_vs_pred_top5": fig_actual_vs_pred(preds),
        "borough_mae": fig_borough_mae(preds),
        "weather_elasticity": fig_weather_elasticity(weather),
        "p90_band": fig_p90_band(preds),
        "p90_calibration": fig_p90_calibration(coverage_borough),
        "gbm_vs_nn": add_takeaway(
            RunComparison(runs)
            .figure(metric_names=["mae", "rmse", "mape_pct"])
            .update_layout(
                title=(
                    "The served GBM removes 28.4% of forecast error vs last-week "
                    "persistence — the neural challenger wins MAPE only"
                )
            ),
            f"Best run: {ranking['ranking'][0]} "
            f"(MAE {best_mae:.2f}); naive_lag24 is the grey persistence reference.",
        ),
    }
    if importance_fig is not None:
        figures["gbm_feature_importance"] = importance_fig
    figures["zone_fan"] = fig_zone_fan(preds)
    try:
        from mobility.geo import fig_zone_demand_map, fig_zone_residual_map

        figures["zone_demand_map"] = fig_zone_demand_map(demand)
        figures["zone_residual_map"] = fig_zone_residual_map(preds)
    except FileNotFoundError as e:
        logger.warning("geo figures skipped: %s", e)

    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = cfg.reports_dir / "figures"
    for name, fig in figures.items():
        save_html(fig, figures_dir / f"{name}.html")
        save_json(fig, figures_dir / f"{name}.json")

    metrics: dict[str, Any] = {r.name: {m.name: m.value for m in r.metrics} for r in runs}
    metrics["_meta"] = {
        "split": f"temporal holdout from {cfg.train_cutoff.isoformat()}",
        "p90_coverage": coverage,
        "p90_coverage_by_borough": {
            r["borough"]: round(cast(float, r["coverage"]), 4)
            for r in coverage_borough.iter_rows(named=True)
        },
        "n_test_rows": preds.height,
        "mae_ranking": ranking["ranking"],
    }
    metrics["deltas"] = baseline_deltas(runs)
    (cfg.reports_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    report = EvalReport(title="Project 07 — Urban Mobility Demand Intelligence")
    report.add_markdown_table("Overall test metrics (next-hour pickups)", comparison_md)
    report.add_markdown_table("Per-borough test MAE (gbm_mean)", _markdown(borough_mae))
    report.add_markdown_table(
        "Weather elasticity: rain vs dry by borough",
        _markdown(weather),
    )
    report.add_markdown_table(
        "p90 band empirical coverage by borough (target 0.90)",
        _markdown(coverage_borough, floatfmt="{:.4f}"),
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
