"""Probabilistic forecasts: quantile HGB + zero-aware split-conformal band.

Wave 7 shipped the quantile + global split-conformal pair; wave 17 replaced
the global conformal width with per predicted-zero-bin calibration (the
global q80 degenerates on zero-heavy demand); wave 23 adds the non-degenerate
sparse interval: rows the model predicts as zero get the per-series training
history q80 as an upper bound ([0, q80]) instead of the zero-bin's ±0 width,
so the band carries honest width at the zero atom (the nowcast UCI track's
zero-aware band collapses to width 0.00 there — the committed negative result
the sparse history band replaces for reporting).

Two complementary 80% bands on top of the tuned HGB config:

- **quantile band** — three ``HistGradientBoostingRegressor(loss="quantile")``
  models (p10 / p50 / p90) trained per fold on the same date-aligned windows;
- **zero-aware split-conformal band** — the p50 residuals of all *earlier*
  folds define the ±q80 correction **per predicted-zero bin** (rows the model
  predicts as zero have a different residual law than rows it predicts
  nonzero). A *global* width degenerates on zero-heavy demand — with >80% of
  residuals exactly 0 the global q80 collapses to 0 (UCI wave-7 artefact).
  The band is applied to the last fold only (classic split-conformal:
  coverage is marginal and exchangeability-based);
- **sparse history band** (wave 23) — same bin split, but predicted-zero rows
  take [0, q80 of that series' calibration-fold actuals] (pooled q80 fallback
  for a series absent from the calibration folds): zero width is impossible
  wherever the history saw any demand, and coverage at predicted-zero rows
  remains honest because the upper bound still has to contain the actuals.

Outputs ``reports/probabilistic.json`` (empirical coverages, per-horizon
coverage AND average width on the test window, calibration verdict) and
``figures/probabilistic_band`` (two high-volume example series, test window;
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
from demand_forecasting.evaluate import EVAL_HORIZON_DAYS, _display_series, cv_row_folds
from demand_forecasting.model import NUMERIC_FEATURES, model_specs, to_xy

logger = get_logger(__name__)

QUANTILES = (0.1, 0.5, 0.9)
TARGET_COVERAGE = 0.8
EXAMPLE_N = 2
# |coverage - target| within this tolerance at the evaluation horizon set
# counts as calibrated; above the target is conservative, below is optimistic.
CALIBRATION_TOL = 0.05


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


def calibration_verdict(empirical: float, target: float = TARGET_COVERAGE) -> str:
    """Classify band calibration: calibrated / conservative / optimistic.

    ``conservative`` = the band covers MORE than targeted (wider than needed),
    ``optimistic`` = it covers less. Tolerance per CALIBRATION_TOL.
    """
    if abs(empirical - target) <= CALIBRATION_TOL:
        return "calibrated"
    return "conservative" if empirical > target else "optimistic"


def horizon_band_stats(
    last: dict[str, np.ndarray], n_horizons: int = EVAL_HORIZON_DAYS
) -> dict[str, Any]:
    """Per-horizon empirical coverage and average band width on the test window.

    Horizons are day-offsets within the final ``n_horizons`` days of the test
    window (per-series chronological rank — the same convention as
    ``evaluate._horizon_metrics`` and the demo payload's forecast window).
    Reported alongside the pooled horizon-set numbers so a band that covers
    on average can still be seen missing at specific horizons.
    """
    dates = last["dates"]
    block_start = dates.max() - np.timedelta64(n_horizons - 1, "D")
    block = np.flatnonzero(dates >= block_start)
    covered = (last["y_true"] >= last["conf_lo"]) & (last["y_true"] <= last["conf_hi"])
    width = last["conf_hi"] - last["conf_lo"]
    position: dict[str, int] = {}
    cov = [float("nan")] * n_horizons
    avg_width = [float("nan")] * n_horizons
    cov_sum = np.zeros(n_horizons)
    width_sum = np.zeros(n_horizons)
    cnt = np.zeros(n_horizons)
    for i in block:
        sid = str(last["series"][i])
        h = position.get(sid, 0)
        if h >= n_horizons:
            continue
        position[sid] = h + 1
        cov_sum[h] += float(covered[i])
        width_sum[h] += float(width[i])
        cnt[h] += 1
    for h in range(n_horizons):
        if cnt[h]:
            cov[h] = float(cov_sum[h] / cnt[h])
            avg_width[h] = float(width_sum[h] / cnt[h])
    return {
        "horizon_coverage": cov,
        "horizon_avg_width": avg_width,
        "coverage_horizon_set": float(np.mean(covered[block])) if block.size else float("nan"),
        "avg_width_horizon_set": float(np.mean(width[block])) if block.size else float("nan"),
    }


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


def sparse_history_band(
    last: dict[str, np.ndarray],
    cal_series: np.ndarray,
    cal_y: np.ndarray,
    widths: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Non-degenerate band for predicted-zero rows (wave 23).

    Rows the p50 predicts as zero take ``[0, q80 of the same series'
    calibration-fold actuals]`` (all calibration folds precede the scored
    fold, so the history is leakage-safe); a series with no calibration rows
    falls back to the pooled calibration q80. Rows predicted nonzero keep the
    zero-aware ±width band. Returns (lo, hi, summary dict).
    """
    series_last = last["series"].astype(str)
    zero_rows = last["p50"] <= 0
    lo = np.maximum(last["p50"] - widths, 0.0)
    hi = last["p50"] + widths
    cal_s = cal_series.astype(str)
    pooled_q80 = float(np.quantile(cal_y, TARGET_COVERAGE)) if cal_y.size else 0.0
    hist_q80: dict[str, float] = {}
    for sid in np.unique(series_last[zero_rows]):
        hist = cal_y[cal_s == sid]
        hist_q80[str(sid)] = float(np.quantile(hist, TARGET_COVERAGE)) if hist.size else pooled_q80
    for r in np.flatnonzero(zero_rows):
        lo[r] = 0.0
        hi[r] = hist_q80[series_last[r]]
    summary = {
        "definition": "p50 <= 0 rows: [0, q80 of the series' calibration-fold actuals] "
        "(pooled q80 fallback); p50 > 0 rows: the zero-aware ±q80 width",
        "zero_rows": int(zero_rows.sum()),
        "nonzero_rows": int((~zero_rows).sum()),
        "fallback_series": int(
            sum(1 for sid in np.unique(series_last[zero_rows]) if not np.any(cal_s == sid))
        ),
    }
    return lo, hi, summary


def run_probabilistic(
    settings: DemandSettings, config: ForecastConfig, multistep: Any | None = None
) -> dict[str, Any]:
    """Backtest the quantile models and evaluate both bands on the last fold.

    ``multistep`` optionally carries the multi-step track result
    (:class:`~demand_forecasting.multihorizon.MultiStepResult`); its
    per-horizon band block is merged into probabilistic.json under the
    ``multistep`` key (the nowcast keys are untouched).
    """
    features = pl.read_parquet(settings.data_dir / "features.parquet")
    x, y = _design_matrix(features, config)
    folds = cv_row_folds(features, config)

    per_fold: list[dict[str, float]] = []
    cal_p50: list[np.ndarray] = []  # calibration (all earlier folds) p50 + |resid|
    cal_absres: list[np.ndarray] = []
    cal_y: list[np.ndarray] = []  # calibration actuals (sparse-history band input)
    cal_series: list[np.ndarray] = []
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
            cal_y.append(y[val_rows])
            cal_series.append(features["series_id"].to_numpy()[val_rows])
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

    # wave 23: the non-degenerate sparse band — predicted-zero rows take
    # [0, q80 of the series' calibration-fold actuals] instead of ±0 width.
    sparse_lo, sparse_hi, sparse_summary = sparse_history_band(
        last, np.concatenate(cal_series), np.concatenate(cal_y), widths
    )
    last["sparse_lo"] = sparse_lo
    last["sparse_hi"] = sparse_hi
    sparse_cov = coverage(last["y_true"], sparse_lo, sparse_hi)
    sparse_horizon = horizon_band_stats({**last, "conf_lo": sparse_lo, "conf_hi": sparse_hi})
    sparse_verdict = calibration_verdict(sparse_horizon["coverage_horizon_set"])
    sparse_zero_cov = (
        coverage(last["y_true"][zero_mask], sparse_lo[zero_mask], sparse_hi[zero_mask])
        if zero_mask.any()
        else None
    )

    # test-window band evaluation: per-horizon (h=1..14) coverage AND average
    # width over the final 14 days, plus a calibration verdict for the champion.
    horizon = horizon_band_stats(last)
    verdict = calibration_verdict(horizon["coverage_horizon_set"])

    def _bin_coverage(mask: np.ndarray) -> float | None:
        """Coverage within one bin; None when the fold has no rows in it."""
        if not mask.any():
            return None
        return coverage(last["y_true"][mask], last["conf_lo"][mask], last["conf_hi"][mask])

    result: dict[str, Any] = {
        "target_coverage": TARGET_COVERAGE,
        "horizon": 1,
        "horizons_note": (
            "The modelling frame is one-day-ahead per origin (each row's forecast uses "
            "only information available the day before). Per-horizon statistics group "
            "the test window's final 14 days by day-offset (h=1..14) — descriptive "
            "coverage/width by horizon position, not separately calibrated bands. "
            "Origin-stacked multi-horizon bands are delivered by the multi-step track "
            "('multistep' key below, protocol direct_multihorizon_v1)."
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
            # frozen-holdout evaluation of the band applied to the test window
            **horizon,
            "calibration_verdict": verdict,
            "calibration_verdict_rule": "coverage pooled over horizons 1..14 of the test "
            "window: |coverage - target| <= 0.05 -> calibrated; above target -> "
            "conservative; below -> optimistic",
            # wave 23: the zero-bin width collapses to 0 on zero-heavy panels
            # (see sparse_history_band below) — kept as the documented negative
            # result, no longer the reported band.
        },
        "sparse_history_band": {
            **sparse_summary,
            "coverage_last_fold": sparse_cov,
            "coverage_last_fold_zero_rows": sparse_zero_cov,
            "avg_width_last_fold": float(np.mean(sparse_hi - sparse_lo)),
            **sparse_horizon,
            "calibration_verdict": sparse_verdict,
            "vs_zero_aware": {
                "zero_aware_coverage": conformal_cov,
                "zero_aware_avg_width_horizon_set": horizon["avg_width_horizon_set"],
                "coverage_delta": sparse_cov - conformal_cov,
                "width_delta_horizon_set": sparse_horizon["avg_width_horizon_set"]
                - horizon["avg_width_horizon_set"],
            },
        },
        "mae_p50_pooled": float(np.mean([f["mae_p50"] for f in per_fold])),
    }
    if multistep is not None:
        result["multistep"] = multistep.probabilistic_block
    out = settings.reports_dir / "probabilistic.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    logger.info(
        "probabilistic: quantile band coverage %.3f (target %.2f), zero-aware "
        "conformal %.3f (zero bin %s / nonzero bin %s); test window h=1..14: "
        "coverage %.3f, avg width %.2f -> %s",
        quantile_cov_pooled,
        TARGET_COVERAGE,
        conformal_cov,
        _fmt_bin(result["split_conformal"]["coverage_last_fold_zero_bin"]),
        _fmt_bin(result["split_conformal"]["coverage_last_fold_nonzero_bin"]),
        horizon["coverage_horizon_set"],
        horizon["avg_width_horizon_set"],
        verdict,
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
    """Actual vs p50 with the reported band for two example series.

    Wave 23 draws the non-degenerate sparse history band
    (:func:`sparse_history_band`) — predicted-zero rows get [0, history q80]
    instead of the zero-aware band's ±0 width; older artifacts without that
    block fall back to the zero-aware band. The quantile p10/p90 band stays
    in ``probabilistic.json`` but is not drawn: its global coverage is the
    number the old figure complained about. An updatemenu toggles the band
    off ("actual only"); the achieved last-fold coverage is stated in the
    subtitle.
    """
    volume = (
        features.group_by("series_id")
        .agg(pl.col("y").sum().alias("vol"))
        .sort("vol", descending=True)
    )
    examples = volume.head(EXAMPLE_N)["series_id"].to_list()
    short = _display_series(examples)  # strip the shared country prefix (long legend names clip)
    fig = go.Figure()
    # wave 23: draw the non-degenerate sparse history band when present
    # (falls back to the zero-aware band for older artifacts).
    band_lo = last.get("sparse_lo", last["conf_lo"])
    band_hi = last.get("sparse_hi", last["conf_hi"])
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
            y=band_hi[mask],
            name=f"{label} band upper",
            mode="lines",
            line={"width": 0},
            showlegend=False,
        )
        fig.add_scatter(
            x=x,
            y=band_lo[mask],
            name=f"{label} band lower",
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(45, 212, 191, 0.15)",
            line={"width": 0},
            showlegend=False,
        )
    conf = (
        result["sparse_history_band"]
        if "sparse_history_band" in result
        else result["split_conformal"]
    )
    band_name = (
        "the sparse history band" if "sparse_history_band" in result else "the zero-aware band"
    )
    fig.update_layout(
        title=f"Actual vs p50 with {band_name}",
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
    if "sparse_history_band" in result:
        bins = f"; predicted-zero rows {_fmt_bin(conf['coverage_last_fold_zero_rows'])}"
    else:
        bins = (
            f"; zero-bin {_fmt_bin(conf['coverage_last_fold_zero_bin'])}, "
            f"nonzero-bin {_fmt_bin(conf['coverage_last_fold_nonzero_bin'])}"
            if conf["coverage_last_fold_zero_bin"] is not None
            or conf["coverage_last_fold_nonzero_bin"] is not None
            else ""
        )
    add_takeaway(
        fig,
        f"test window, two highest-volume series — {TARGET_COVERAGE:.0%} target{bins}; "
        f"h=1..14: coverage {conf['coverage_horizon_set']:.2f}, "
        f"avg width {conf['avg_width_horizon_set']:.1f} units "
        f"({conf['calibration_verdict']})",
    )
    # Exceptional top margin: the updatemenu buttons sit above the plot
    # (y=1.10) in the band below the two-line title.
    fig.update_layout(margin={"t": 185})
    return apply_theme(fig)


def _fmt_bin(value: float | None) -> str:
    """Per-bin coverage for the subtitle; 'n/a' when the fold has no such rows."""
    return "n/a" if value is None else f"{value:.1%}"
