"""Probabilistic forecasts: quantile HGB + split-conformal band (wave 7).

Two complementary 80% bands on top of the tuned HGB config:

- **quantile band** — three ``HistGradientBoostingRegressor(loss="quantile")``
  models (p10 / p50 / p90) trained per fold on the same date-aligned windows;
- **split-conformal band** — the p50 residuals of all *earlier* folds define a
  symmetric ±q80 correction, applied to the last fold only (classic
  split-conformal: coverage is marginal and exchangeability-based).

Outputs ``reports/probabilistic.json`` (empirical coverages) and
``figures/probabilistic_band`` (two high-volume example series, last fold).
Honest reporting: coverage is empirical out-of-fold, never in-sample.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import polars as pl
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_html, save_json
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import OneHotEncoder

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.evaluate import cv_row_folds
from demand_forecasting.model import NUMERIC_FEATURES, model_specs, to_xy

logger = get_logger(__name__)

QUANTILES = (0.1, 0.5, 0.9)
TARGET_COVERAGE = 0.8
EXAMPLE_N = 2


def _design_matrix(features: pl.DataFrame, config: ForecastConfig) -> tuple[np.ndarray, np.ndarray]:
    """Same numeric+lag+one-hot(series) matrix the hgb backtest uses."""
    spec = next(s for s in model_specs() if s.name == "hgb_tuned")
    x_raw, y, _, _ = to_xy(features, config, spec)
    n_num = len(NUMERIC_FEATURES) + len(config.lags)
    pre = ColumnTransformer(
        [
            ("num", "passthrough", list(range(n_num))),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), [n_num]),
        ]
    )
    return np.asarray(pre.fit_transform(x_raw), dtype=float), y


def _fit_quantile_models(
    x: np.ndarray, y: np.ndarray, config: ForecastConfig
) -> dict[float, HistGradientBoostingRegressor]:
    """p10/p50/p90 HGBs on the tuned production config."""
    fitted: dict[float, HistGradientBoostingRegressor] = {}
    for q in QUANTILES:
        kwargs: dict[str, Any] = config.hgb_tuned.estimator_kwargs()
        kwargs["random_state"] = config.seed
        model = HistGradientBoostingRegressor(loss="quantile", quantile=q, **kwargs)
        model.fit(x, y)
        fitted[q] = model
    return fitted


def coverage(y_true: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    """Empirical coverage of a prediction band."""
    return float(np.mean((y_true >= lo) & (y_true <= hi)))


def run_probabilistic(settings: DemandSettings, config: ForecastConfig) -> dict[str, Any]:
    """Backtest the quantile models and evaluate both bands on the last fold."""
    features = pl.read_parquet(settings.data_dir / "features.parquet")
    x, y = _design_matrix(features, config)
    folds = cv_row_folds(features, config)

    per_fold: list[dict[str, float]] = []
    residuals_early: list[np.ndarray] = []
    for k, (train_rows, val_rows) in enumerate(folds):
        models = _fit_quantile_models(x[train_rows], y[train_rows], config)
        preds = {q: models[q].predict(x[val_rows]) for q in QUANTILES}
        cov = coverage(y[val_rows], preds[0.1], preds[0.9])
        per_fold.append(
            {
                "fold": float(k + 1),
                "quantile_band_coverage": cov,
                "mae_p50": float(np.mean(np.abs(y[val_rows] - preds[0.5]))),
            }
        )
        if k < len(folds) - 1:
            residuals_early.append(np.abs(y[val_rows] - preds[0.5]))
        if k == len(folds) - 1:
            last = {
                "dates": features["date"].to_numpy()[val_rows],
                "series": features["series_id"].to_numpy()[val_rows],
                "y_true": y[val_rows],
                "p10": preds[0.1],
                "p50": preds[0.5],
                "p90": preds[0.9],
            }

    # split-conformal: calibrate on all earlier folds, apply to the last fold
    q80 = float(np.quantile(np.concatenate(residuals_early), TARGET_COVERAGE))
    last["conf_lo"] = last["p50"] - q80
    last["conf_hi"] = last["p50"] + q80
    conformal_cov = coverage(last["y_true"], last["conf_lo"], last["conf_hi"])
    quantile_cov_pooled = float(np.mean([f["quantile_band_coverage"] for f in per_fold]))

    result: dict[str, Any] = {
        "target_coverage": TARGET_COVERAGE,
        "quantile_band": {
            "coverage_pooled": quantile_cov_pooled,
            "per_fold": per_fold,
        },
        "split_conformal": {
            "q80": q80,
            "coverage_last_fold": conformal_cov,
        },
        "mae_p50_pooled": float(np.mean([f["mae_p50"] for f in per_fold])),
    }
    out = settings.reports_dir / "probabilistic.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    logger.info(
        "probabilistic: quantile band coverage %.3f (target %.2f), conformal %.3f (q80=%.3f)",
        quantile_cov_pooled,
        TARGET_COVERAGE,
        conformal_cov,
        q80,
    )

    fig = figure_probabilistic_band(features, last, result)
    save_html(fig, Path(settings.reports_dir) / "figures" / "probabilistic_band.html")
    save_json(fig, Path(settings.reports_dir) / "figures" / "probabilistic_band.json")
    return result


def figure_probabilistic_band(
    features: pl.DataFrame, last: dict[str, np.ndarray], result: dict[str, Any]
) -> go.Figure:
    """Actual vs p50 with the p10-p90 band for two high-volume example series."""
    volume = (
        features.group_by("series_id")
        .agg(pl.col("y").sum().alias("vol"))
        .sort("vol", descending=True)
    )
    examples = volume.head(EXAMPLE_N)["series_id"].to_list()
    fig = go.Figure()
    for sid in examples:
        mask = last["series"] == sid
        x = last["dates"][mask]
        fig.add_scatter(x=x, y=last["y_true"][mask], name=f"{sid} actual", mode="lines")
        fig.add_scatter(
            x=x,
            y=last["p50"][mask],
            name=f"{sid} p50",
            mode="lines",
            line={"dash": "dash"},
        )
        fig.add_scatter(
            x=x,
            y=last["p90"][mask],
            name=f"{sid} p90",
            mode="lines",
            line={"width": 0},
            showlegend=False,
        )
        fig.add_scatter(
            x=x,
            y=last["p10"][mask],
            name=f"{sid} p10",
            mode="lines",
            fill="tonexty",
            line={"width": 0},
            showlegend=False,
        )
    cov = result["quantile_band"]["coverage_pooled"]
    fig.update_layout(title="Probabilistic forecast — p10-p90 band, last CV fold")
    add_takeaway(
        fig,
        f"takeaway: empirical band coverage {cov:.0%} (target {TARGET_COVERAGE:.0%}); "
        "width priced from backtest residuals",
    )
    return apply_theme(fig)
