"""Cross-service transfer: yellow-trained models on green-taxi demand.

Bounded study (config ``green_months`` = 2024-01..03): green pickups are
curated onto the same zone x hour grid with the same lag/calendar/weather
features, and the *yellow-trained* GBMs (default + HPO-tuned) predict green
demand for **March 2024** (features come from green's own January-February
history — the yellow data is never touched at transfer time). Reference floor:
green lag-24 persistence.

Wave-14 addition (the "retrain per service" roadmap item): a GBM fit on green
January-February itself — same default configuration family as ``gbm_mean`` —
predicts the same green March window, so the transfer question gets its honest
control: is the yellow -> green gap a data-regime problem (fixed by per-service
retraining) or a sparsity problem (persistence wins anyway)?

Output: ``reports/green_transfer.json`` + a themed
figure ``green_transfer`` (overall + per-borough MAE).
"""

import json
from typing import Any

import joblib
import plotly.graph_objects as go
import polars as pl
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_html, save_json
from portfolio_eval.ml import regression_metrics

from mobility.config import MobilityConfig, get_config
from mobility.features import FEATURE_COLUMNS, _with_features
from mobility.model import _make_gbm

logger = get_logger(__name__)

GREEN_TEST_MONTH = 3  # March = transfer evaluation window


def green_feature_frame(cfg: MobilityConfig, month: int | None = GREEN_TEST_MONTH) -> pl.DataFrame:
    """Green zone-hour demand → lag/calendar/weather feature matrix.

    ``month`` selects the evaluation window (default: March); ``None`` returns
    every curated month — the green-trained control arm needs Jan-Feb rows.
    """
    if not cfg.green_zone_hour_demand_path.exists():
        raise FileNotFoundError(
            f"missing {cfg.green_zone_hour_demand_path} — run `mobility join` (green slice)"
        )
    feats = (
        _with_features(pl.scan_parquet(cfg.green_zone_hour_demand_path), cfg)
        .drop("pickup_count")
        .collect(engine="streaming")
    )
    return feats.filter(pl.col("ts").dt.month() == month) if month is not None else feats


def evaluate_transfer(cfg: MobilityConfig | None = None) -> dict[str, Any]:
    """Score yellow-trained GBMs and a green-retrained GBM on green March demand.

    The yellow-trained runs answer "does the yellow artifact transfer?"; the
    ``gbm_green_retrained`` arm (same default GBM family, fit on green
    January-February) is the per-service-retraining control the roadmap calls
    for — it separates "wrong service distribution" from "sparse demand is
    just hard".
    """
    cfg = cfg or get_config()
    test = green_feature_frame(cfg)
    X = test.select(FEATURE_COLUMNS).to_numpy().astype("float32")
    y_true = test["target"].to_list()

    models: dict[str, tuple[str, str]] = {  # run name -> (mean model file, pred col)
        "gbm_mean": ("gbm_mean.joblib", "y_gbm"),
        "gbm_tuned": ("gbm_tuned.joblib", "y_gbm_tuned"),
    }
    preds = test.select(
        ["zone_id", "borough", "ts", pl.col("target").alias("y_true"), pl.col("lag_24")]
    )
    metrics: dict[str, Any] = {}
    for run, (file, col) in models.items():
        path = cfg.models_dir / file
        if not path.exists():
            logger.warning("skipping %s — %s not found", run, path)
            continue
        model = joblib.load(path)
        preds = preds.with_columns(pl.Series(col, model.predict(X)))
        m = regression_metrics(y_true, preds[col].to_list())
        metrics[run] = {r.name: r.value for r in m}

    # Per-service retraining control: fit the default GBM family on green's
    # own Jan-Feb history (the same rows the transfer features come from),
    # then score it on the same green March window.
    train_green = green_feature_frame(cfg, month=None).filter(
        pl.col("ts").dt.month() < GREEN_TEST_MONTH
    )
    X_train = train_green.select(FEATURE_COLUMNS).to_numpy().astype("float32")
    y_train = train_green["target"].to_numpy().astype("float32")
    green_model = _make_gbm(cfg.gbm.model_dump(), seed=cfg.seed)
    green_model.fit(X_train, y_train)
    preds = preds.with_columns(pl.Series("y_gbm_green", green_model.predict(X)))
    metrics["gbm_green_retrained"] = {
        r.name: r.value for r in regression_metrics(y_true, preds["y_gbm_green"].to_list())
    }
    logger.info(
        "green-retrained GBM: %d train rows (green Jan-Feb), MAE %.4f on green March",
        train_green.height,
        metrics["gbm_green_retrained"]["mae"],
    )

    preds = preds.with_columns(y_naive=pl.col("lag_24"))
    metrics["naive_lag24"] = {
        r.name: r.value for r in regression_metrics(y_true, preds["y_naive"].to_list())
    }

    by_borough: dict[str, dict[str, float]] = {}
    for run, (_, col) in {
        **models,
        "gbm_green_retrained": ("", "y_gbm_green"),
        "naive_lag24": ("", "y_naive"),
    }.items():
        if col not in preds.columns:
            continue
        mae = (
            preds.with_columns(e=(pl.col(col) - pl.col("y_true")).abs())
            .group_by("borough")
            .agg(pl.col("e").mean())
        )
        by_borough[run] = {r["borough"]: round(r["e"], 4) for r in mae.iter_rows(named=True)}

    out: dict[str, Any] = {
        "window": f"2024-03 green taxi (n={preds.height:,} zone-hours)",
        "features_from": "green Jan-Feb history (yellow untouched at transfer time)",
        "green_retrain": (
            f"gbm_green_retrained fit on green Jan-Feb 2024 "
            f"(n={train_green.height:,} zone-hours, default GBM family)"
        ),
        "overall": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in metrics.items()},
        "mae_by_borough": by_borough,
    }
    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "green_transfer.json").write_text(json.dumps(out, indent=2) + "\n")
    fig = fig_green_transfer(out)
    save_html(fig, cfg.reports_dir / "figures" / "green_transfer.html")
    save_json(fig, cfg.reports_dir / "figures" / "green_transfer.json")
    logger.info("green transfer: %s", json.dumps(out["overall"]))
    return out


def fig_green_transfer(result: dict[str, Any]) -> go.Figure:
    """Grouped bars: overall MAE per run, with the mixed-verdict takeaway.

    Reference order is fixed (naive, then the two yellow-trained runs) so the
    transfer comparison reads left-to-right; the green-retrained control arm
    appends last when present.
    """
    runs = [r for r in ("naive_lag24", "gbm_mean", "gbm_tuned") if r in result["overall"]]
    runs += [r for r in ("gbm_green_retrained",) if r in result["overall"]]
    maes = [result["overall"][r]["mae"] for r in runs]
    colors = ["#64748b", "#38bdf8", "#2dd4bf", "#fbbf24"]
    fig = go.Figure(
        data=go.Bar(
            x=runs,
            y=maes,
            marker_color=colors[: len(runs)],
            text=[f"{v:.2f}" for v in maes],
            textposition="outside",
        )
    )
    base = result["overall"].get("naive_lag24", {})
    tuned = result["overall"].get("gbm_tuned", {})
    if base and tuned:
        mae_delta = (base["mae"] - tuned["mae"]) / base["mae"] * 100
        rmse_delta = (base["rmse"] - tuned["rmse"]) / base["rmse"] * 100
        takeaway = (
            f"Mixed transfer: MAE {tuned['mae']:.2f} vs naive {base['mae']:.2f} "
            f"({mae_delta:+.0f}%), but wins on RMSE ({rmse_delta:+.0f}%) and MAPE"
        )
        retrained = result["overall"].get("gbm_green_retrained")
        if retrained:
            retrained_delta = (base["mae"] - retrained["mae"]) / base["mae"] * 100
            takeaway += (
                f"; green-trained control: MAE {retrained['mae']:.2f} "
                f"({retrained_delta:+.0f}% vs naive)"
            )
    else:
        takeaway = "Transfer metrics unavailable."
    fig.update_layout(
        title="Transfer: yellow-trained GBM on green demand",
        yaxis_title="MAE (pickups/hour)",
    )
    return add_takeaway(apply_theme(fig), takeaway)
