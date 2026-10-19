"""Probabilistic forecasts: quantile HGB + zero-aware split-conformal band.

Wave 7 shipped the quantile + global split-conformal pair; wave 17 replaced
the global conformal width with per predicted-zero-bin calibration (the
global q80 degenerates on zero-heavy demand).

Two complementary 80% bands on top of the tuned HGB config:

- **quantile band** — three ``HistGradientBoostingRegressor(loss="quantile")``
  models (p10 / p50 / p90) trained per fold on the same date-aligned windows;
- **zero-aware split-conformal band** — the p50 residuals of all *earlier*
  folds define the ±q80 correction **per predicted-zero bin** (rows the model
  predicts as zero have a different residual law than rows it predicts
  nonzero). A *global* width degenerates on zero-heavy demand — with >80% of
  residuals exactly 0 the global q80 collapses to 0 (UCI wave-7 artefact).
  The band is applied to the last fold only (classic split-conformal:
  coverage is marginal and exchangeability-based).

Outputs ``reports/probabilistic.json`` (empirical coverages) and
``figures/probabilistic_band`` (two high-volume example series, last fold;
an updatemenu toggles the band off — "actual only"). Honest reporting:
coverage is empirical out-of-fold, never in-sample, and the achieved number
is stated in the figure subtitle.
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
from demand_forecasting.evaluate import _display_series, cv_row_folds
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


def _zero_bin_widths(
    p50_cal: np.ndarray, abs_resid_cal: np.ndarray, p50_apply: np.ndarray
) -> tuple[np.ndarray, dict[str, Any]]:
    """Per predicted-zero-bin ±q80 widths (split-conformal calibration).

    Bins are defined by the *prediction* (p50 ≤ 0 vs p50 > 0) — usable at
    forecast time, unlike conditioning on the realised y. Each bin gets its
    own |residual| q80 from the calibration rows; a bin with no calibration
    rows falls back to the pooled q80. Returns one width per ``p50_apply``
    row plus the calibration summary for the metrics JSON.
    """
    zero_cal = p50_cal <= 0
    q80_zero = _bin_q80(abs_resid_cal[zero_cal], abs_resid_cal)
    q80_nonzero = _bin_q80(abs_resid_cal[~zero_cal], abs_resid_cal)
    widths = np.where(p50_apply <= 0, q80_zero, q80_nonzero)
    summary = {
        "bin_definition": "p50 <= 0 (model predicts zero) vs p50 > 0",
        "zero_bin": {"q80": q80_zero, "n_calibration": int(zero_cal.sum())},
        "nonzero_bin": {"q80": q80_nonzero, "n_calibration": int((~zero_cal).sum())},
    }
    return widths, summary


def _bin_q80(bin_resid: np.ndarray, pooled_resid: np.ndarray) -> float:
    """q80 of a bin's |residuals|, falling back to the pooled q80 when empty."""
    if len(bin_resid) == 0:
        return float(np.quantile(pooled_resid, TARGET_COVERAGE))
    return float(np.quantile(bin_resid, TARGET_COVERAGE))


def run_probabilistic(settings: DemandSettings, config: ForecastConfig) -> dict[str, Any]:
    """Backtest the quantile models and evaluate both bands on the last fold."""
    features = pl.read_parquet(settings.data_dir / "features.parquet")
    x, y = _design_matrix(features, config)
    folds = cv_row_folds(features, config)

    per_fold: list[dict[str, float]] = []
    cal_p50: list[np.ndarray] = []  # calibration (all earlier folds) p50 + |resid|
    cal_absres: list[np.ndarray] = []
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
            cal_p50.append(preds[0.5])
            cal_absres.append(np.abs(y[val_rows] - preds[0.5]))
        if k == len(folds) - 1:
            last = {
                "dates": features["date"].to_numpy()[val_rows],
                "series": features["series_id"].to_numpy()[val_rows],
                "y_true": y[val_rows],
                "p10": preds[0.1],
                "p50": preds[0.5],
                "p90": preds[0.9],
            }

    # zero-aware split-conformal: calibrate per predicted-zero bin on all
    # earlier folds, apply per bin on the last fold; demand floors at 0
    widths, bin_summary = _zero_bin_widths(
        np.concatenate(cal_p50), np.concatenate(cal_absres), last["p50"]
    )
    last["conf_lo"] = np.maximum(last["p50"] - widths, 0.0)
    last["conf_hi"] = last["p50"] + widths
    conformal_cov = coverage(last["y_true"], last["conf_lo"], last["conf_hi"])
    zero_mask = last["p50"] <= 0
    quantile_cov_pooled = float(np.mean([f["quantile_band_coverage"] for f in per_fold]))

    def _bin_coverage(mask: np.ndarray) -> float | None:
        """Coverage within one bin; None when the fold has no rows in it."""
        if not mask.any():
            return None
        return coverage(last["y_true"][mask], last["conf_lo"][mask], last["conf_hi"][mask])

    result: dict[str, Any] = {
        "target_coverage": TARGET_COVERAGE,
        "horizon": 1,
        "horizons_note": (
            "The modelling frame is one-day-ahead (h=1 only). Multi-horizon "
            "coverage (h in {1, 7}) needs a horizon-stacked frame — roadmap."
        ),
        "quantile_band": {
            "coverage_pooled": quantile_cov_pooled,
            "per_fold": per_fold,
        },
        "split_conformal": {
            # global q80 kept for reference: on zero-heavy demand it
            # degenerates (UCI: q80 = 0), which is why the band is per-bin.
            "q80": float(np.quantile(np.concatenate(cal_absres), TARGET_COVERAGE)),
            **bin_summary,
            "coverage_last_fold": conformal_cov,
            "coverage_last_fold_zero_bin": _bin_coverage(zero_mask),
            "coverage_last_fold_nonzero_bin": _bin_coverage(~zero_mask),
        },
        "mae_p50_pooled": float(np.mean([f["mae_p50"] for f in per_fold])),
    }
    out = settings.reports_dir / "probabilistic.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    logger.info(
        "probabilistic: quantile band coverage %.3f (target %.2f), zero-aware "
        "conformal %.3f (zero bin %s / nonzero bin %s)",
        quantile_cov_pooled,
        TARGET_COVERAGE,
        conformal_cov,
        _fmt_bin(result["split_conformal"]["coverage_last_fold_zero_bin"]),
        _fmt_bin(result["split_conformal"]["coverage_last_fold_nonzero_bin"]),
    )

    fig = figure_probabilistic_band(features, last, result)
    save_html(fig, Path(settings.reports_dir) / "figures" / "probabilistic_band.html")
    save_json(fig, Path(settings.reports_dir) / "figures" / "probabilistic_band.json")
    # audit-list fan chart: same content served under its canonical name
    save_html(fig, Path(settings.reports_dir) / "figures" / "forecast_fan.html")
    save_json(fig, Path(settings.reports_dir) / "figures" / "forecast_fan.json")
    return result


def figure_probabilistic_band(
    features: pl.DataFrame, last: dict[str, np.ndarray], result: dict[str, Any]
) -> go.Figure:
    """Actual vs p50 with the zero-aware conformal band for two example series.

    The band is the per predicted-zero-bin split-conformal band (see
    :func:`_zero_bin_widths`) — the quantile p10/p90 band stays in
    ``probabilistic.json`` but is not drawn: its global coverage is the number
    the old figure complained about. An updatemenu toggles the band off
    ("actual only"); the achieved last-fold coverage is stated in the subtitle.
    """
    volume = (
        features.group_by("series_id")
        .agg(pl.col("y").sum().alias("vol"))
        .sort("vol", descending=True)
    )
    examples = volume.head(EXAMPLE_N)["series_id"].to_list()
    short = _display_series(examples)  # strip the shared country prefix (long legend names clip)
    fig = go.Figure()
    for sid in examples:
        mask = last["series"] == sid
        x = last["dates"][mask]
        label = short[sid]
        fig.add_scatter(x=x, y=last["y_true"][mask], name=f"{label} actual", mode="lines")
        fig.add_scatter(
            x=x,
            y=last["p50"][mask],
            name=f"{label} p50",
            mode="lines",
            line={"dash": "dash"},
        )
        fig.add_scatter(
            x=x,
            y=last["conf_hi"][mask],
            name=f"{label} band upper",
            mode="lines",
            line={"width": 0},
            showlegend=False,
        )
        fig.add_scatter(
            x=x,
            y=last["conf_lo"][mask],
            name=f"{label} band lower",
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(45, 212, 191, 0.15)",
            line={"width": 0},
            showlegend=False,
        )
    conf = result["split_conformal"]
    fig.update_layout(
        title="Actual vs p50 with the zero-aware conformal band",
        # updatemenu: the band can be removed interactively ("actual only").
        # Buttons sit in the free band between the two-line title and the plot.
        updatemenus=[
            {
                "type": "buttons",
                "direction": "right",
                "showactive": True,
                "x": 0.02,
                "xanchor": "left",
                "y": 1.10,
                "yanchor": "top",
                "buttons": [
                    {
                        "label": "with band",
                        "method": "update",
                        "args": [{"visible": [True] * len(fig.data)}],
                    },
                    {
                        "label": "actual only",
                        "method": "update",
                        "args": [
                            {"visible": ["actual" in (trace.name or "") for trace in fig.data]}
                        ],
                    },
                ],
            }
        ],
    )
    bins = (
        f"; zero-bin {_fmt_bin(conf['coverage_last_fold_zero_bin'])}, "
        f"nonzero-bin {_fmt_bin(conf['coverage_last_fold_nonzero_bin'])}"
        if conf["coverage_last_fold_zero_bin"] is not None
        or conf["coverage_last_fold_nonzero_bin"] is not None
        else ""
    )
    add_takeaway(
        fig,
        f"last fold, two highest-volume series — {TARGET_COVERAGE:.0%} target{bins}",
    )
    # Exceptional top margin: the updatemenu buttons sit above the plot
    # (y=1.10) in the band below the two-line title.
    fig.update_layout(margin={"t": 185})
    return apply_theme(fig)


def _fmt_bin(value: float | None) -> str:
    """Per-bin coverage for the subtitle; 'n/a' when the fold has no such rows."""
    return "n/a" if value is None else f"{value:.1%}"
