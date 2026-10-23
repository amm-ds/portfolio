"""Demo payload for the demand forecast workbench (showcase demo).

Builds ``reports/demo_payload.json`` — a compact, fully precomputed catalog
that lets the showcase UI render per-series demand forecasts with a band and
the seasonal-naive floor client-side, without retraining or serving model
inference:

- ~150 store-product series from the UCI Online Retail II track (real
  intermittent demand), chosen for demand-class coverage — smooth /
  intermittent / sparse — derived from the committed per-series
  zero-fraction with documented thresholds (``SMOOTH_MAX_ZERO_FRAC`` et al.);
- per series: the last ``HISTORY_DAYS`` committed actuals (daily, with
  dates — the tail includes the forecast window, so the UI can overlay the
  forecast on actuals and recompute the stored per-horizon errors), the
  committed last-fold backtest window (``HORIZON_DAYS`` dates)
  with the champion point forecast ``y_pred``, the p10/p90 quantile band, and
  the seasonal-naive floor (the actuals 7 days earlier — the committed
  ``seasonal_naive`` backtest prediction, recomputable from the history);
- per-horizon absolute error and MASE for champion and naive on each series
  (the modelling frame is one-day-ahead per origin, so "horizon" is the day
  offset inside the committed window; MASE divides by the series' in-sample
  seasonal-naive scale over the stored history);
- the committed scalars: the headline MASE ladder (only the tuned HGB clears
  MASE 1 on real intermittent demand), the band coverage numbers, the
  champion/global/naive model names from the committed backtest selection,
  and the feature-schema note (calendar + lag features).

Everything is deterministic and drift-guarded: the point backtest is
``evaluate.backtest`` on the committed features parquet (the same expanding
windows + embargo that wrote ``reports_uci/metrics.json``), the band reuses
``probabilistic``'s quantile recipe (the one behind
``reports_uci/probabilistic.json``), and a recomputed pooled MASE or band
coverage that disagrees with the committed metrics JSONs raises.
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from portfolio_core.logging import get_logger

from demand_forecasting.config import DemandSettings, ForecastConfig
from demand_forecasting.evaluate import BacktestResult, _is_naive, backtest, cv_row_folds
from demand_forecasting.model import NUMERIC_FEATURES, model_specs
from demand_forecasting.probabilistic import (
    QUANTILES,
    _design_matrix,
    _fit_quantile_models,
    coverage,
)

logger = get_logger(__name__)

DEMO_PAYLOAD_NAME = "demo_payload.json"
PAYLOAD_SCHEMA_VERSION = 1
CATALOG_N = 150
HISTORY_DAYS = 180
HORIZON_DAYS = 14
SEASON = 7
SIZE_CAP_BYTES = 2 * 1024 * 1024
NAIVE_MODEL = "seasonal_naive"

# Demand classes, derived per series from the committed zero-fraction (share
# of modelling-frame days with zero demand) — documented thresholds:
#   smooth:       < 35% zero days — regular, plannable demand
#   intermittent: 35-90%          — frequent zero gaps between demand bursts
#   sparse:       >= 90%          — mostly zero days (count-type demand)
SMOOTH_MAX_ZERO_FRAC = 0.35
INTERMITTENT_MAX_ZERO_FRAC = 0.90
# Per-class catalog quotas (coverage-first selection, top-up by volume).
CLASS_QUOTAS = {"smooth": 25, "intermittent": 50, "sparse": 75}


def _check_close(name: str, actual: float, committed: float, tol: float = 1e-6) -> None:
    """Guard against drift between the committed metrics JSONs and the frame."""
    if not np.isclose(actual, committed, rtol=tol, atol=tol):
        raise ValueError(f"{name}: recomputed {actual} != committed {committed}")


def _committed_runs(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The per-model blocks of a committed metrics.json (no ``_meta`` keys)."""
    return {k: v for k, v in metrics.items() if not k.startswith("_") and isinstance(v, dict)}


def _champion_from_metrics(metrics: dict[str, Any]) -> str:
    """The champion per the committed backtest: lowest pooled MAE, naives out."""
    runs = _committed_runs(metrics)
    return min((k for k in runs if not _is_naive(k)), key=lambda k: float(runs[k]["mae"]))


def _series_stats(features: pl.DataFrame) -> pl.DataFrame:
    """Committed per-series demand stats: zero-fraction (class source) + volume."""
    zero_frac = (pl.col("y") == 0).mean()
    return (
        features.group_by("series_id")
        .agg(zero_frac.alias("zero_frac"), pl.col("y").sum().alias("volume"))
        .with_columns(
            pl.when(pl.col("zero_frac") < SMOOTH_MAX_ZERO_FRAC)
            .then(pl.lit("smooth"))
            .when(pl.col("zero_frac") < INTERMITTENT_MAX_ZERO_FRAC)
            .then(pl.lit("intermittent"))
            .otherwise(pl.lit("sparse"))
            .alias("demand_class")
        )
        .sort(["volume", "series_id"], descending=[True, False])
    )


def _select_catalog(stats: pl.DataFrame, catalog_n: int = CATALOG_N) -> list[str]:
    """Coverage-first catalog: per-class quota by volume (ties by id), then top-up."""
    picked: list[str] = []
    for cls, quota in CLASS_QUOTAS.items():
        pool = stats.filter(pl.col("demand_class") == cls)["series_id"].to_list()
        picked.extend(pool[: min(quota, catalog_n - len(picked))])
    if len(picked) < catalog_n:
        rest = [s for s in stats["series_id"].to_list() if s not in picked]
        picked.extend(rest[: catalog_n - len(picked)])
    return picked[:catalog_n]


def point_backtest(features: pl.DataFrame, config: ForecastConfig, champion: str) -> BacktestResult:
    """The two runs the catalog needs: champion + seasonal-naive floor.

    This is ``evaluate.backtest`` unchanged — same expanding windows, same
    embargo, pooled out-of-fold — so the recomputed MASEs are directly
    comparable to the committed ``reports/metrics.json``.
    """
    names = {champion, NAIVE_MODEL}
    specs = [s for s in model_specs() if s.name in names]
    return backtest(features, config, specs=specs)


def quantile_band_backtest(features: pl.DataFrame, config: ForecastConfig) -> dict[str, Any]:
    """Per-fold p10/p90 quantile band backtest (``probabilistic``'s recipe).

    Fits the tuned-config quantile HGBs on each fold's training window and
    keeps the last fold's predictions for the catalog band; the pooled
    coverage is recomputed with :func:`probabilistic.coverage` and verified
    against the committed ``probabilistic.json`` by the caller.
    """
    x, y = _design_matrix(features, config)
    folds = cv_row_folds(features, config)
    per_fold: list[float] = []
    last: dict[str, Any] | None = None
    for k, (train_rows, val_rows) in enumerate(folds):
        models = _fit_quantile_models(x[train_rows], y[train_rows], config)
        p10 = np.asarray(models[QUANTILES[0]].predict(x[val_rows]), dtype=float)
        p90 = np.asarray(models[QUANTILES[-1]].predict(x[val_rows]), dtype=float)
        per_fold.append(coverage(y[val_rows], p10, p90))
        if k == len(folds) - 1:
            last = {"rows": val_rows, "p10": p10, "p90": p90}
    if last is None:  # pragma: no cover - n_splits >= 2 guarantees a last fold
        raise ValueError("backtest produced no folds")
    return {"coverage_pooled": float(np.mean(per_fold)), "per_fold": per_fold, "last": last}


def _last_fold_frame(result: BacktestResult, band: dict[str, Any], champion: str) -> pl.DataFrame:
    """Last-fold (date, series) rows with champion, naive and band predictions.

    The :class:`~demand_forecasting.evaluate.FoldRecord` arrays and the band
    predictions share the same val-row order (both come from
    ``cv_row_folds``), so they join positionally.
    """
    rec = result.last_fold(champion)
    rec_n = result.last_fold(NAIVE_MODEL)
    last = band["last"]
    n = rec.dates.size
    if not (rec_n.y_pred.size == last["p10"].size == n):
        raise ValueError("last-fold prediction arrays disagree in length")
    return pl.DataFrame(
        {
            "date": [str(d)[:10] for d in rec.dates],
            "series_id": [str(s) for s in rec.series],
            "y_true": rec.y_true.astype(float),
            "y_pred": rec.y_pred.astype(float),
            "naive": rec_n.y_pred.astype(float),
            "p10": last["p10"],
            "p90": last["p90"],
        }
    )


def _window_and_history(
    features: pl.DataFrame,
    fold_frame: pl.DataFrame,
    series_id: str,
    history_days: int,
    horizon: int,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """The catalog series' forecast window (last ``horizon`` fold dates) and
    the last ``history_days`` committed actuals.

    The window is the series' tail, so the history's last ``horizon`` points
    ARE the window actuals — the overlap is verified against the backtest
    fold's ``y_true`` so a panel/fold mismatch raises instead of shipping.
    """
    sub = fold_frame.filter(pl.col("series_id") == series_id).sort("date")
    if sub.height < horizon:
        raise ValueError(f"{series_id}: last fold has {sub.height} rows < horizon {horizon}")
    win = sub.tail(horizon)
    hist = features.filter(pl.col("series_id") == series_id).sort("date").tail(history_days)
    if hist.height >= horizon:
        overlap = hist["y"].to_numpy()[-horizon:]
        if not np.array_equal(overlap, win["y_true"].to_numpy()):
            raise ValueError(f"{series_id}: history tail disagrees with the backtest window")
    return hist, win


def _seasonal_scale(hist_y: np.ndarray) -> float:
    """In-sample seasonal-naive scale: mean |lag-season diff| over the history."""
    if hist_y.size <= SEASON:
        return 0.0
    return float(np.mean(np.abs(hist_y[SEASON:] - hist_y[:-SEASON])))


def _catalog_entry(
    series_id: str,
    demand_class: str,
    hist: pl.DataFrame,
    win: pl.DataFrame,
) -> dict[str, Any]:
    """One catalog series: actuals, committed window forecasts, per-horizon errors."""
    hist_y = hist["y"].to_numpy()
    win_true = win["y_true"].to_numpy()
    scale = _seasonal_scale(hist_y)

    def _errors(pred: np.ndarray) -> dict[str, Any]:
        mae = np.abs(win_true - pred)
        return {
            "mae": [round(float(v), 4) for v in mae],
            "mase": [round(float(v / scale), 4) if scale > 0 else None for v in mae],
        }

    store, _, product = series_id.partition("|")
    return {
        "series_id": series_id,
        "label": f"{store} · {product}",
        "demand_class": demand_class,
        "history": {
            "dates": hist["date"].cast(pl.String).to_list(),
            "y": [int(v) for v in hist_y],
        },
        "forecast": {
            "dates": win["date"].to_list(),
            "y_pred": [round(float(v), 4) for v in win["y_pred"]],
            "p10": [round(float(v), 4) for v in win["p10"]],
            "p90": [round(float(v), 4) for v in win["p90"]],
            "naive": [round(float(v), 4) for v in win["naive"]],
        },
        "errors": {
            "scale": round(scale, 4),
            "champion": _errors(win["y_pred"].to_numpy()),
            "naive": _errors(win["naive"].to_numpy()),
        },
    }


def _guard_series(
    catalog: list[dict[str, Any]],
    fold_frame: pl.DataFrame,
    features: pl.DataFrame,
    history_days: int,
    horizon: int,
) -> None:
    """Spot-check two catalog series: window MASE recomputed straight from the
    committed frame must match the stored per-horizon errors."""
    for entry in (catalog[0], catalog[-1]):
        sid = entry["series_id"]
        hist, win = _window_and_history(features, fold_frame, sid, history_days, horizon)
        scale = _seasonal_scale(hist["y"].to_numpy())
        err = float(np.mean(np.abs(win["y_true"].to_numpy() - win["y_pred"].to_numpy())))
        recomputed = err / scale if scale > 0 else None
        stored_scale = float(entry["errors"]["scale"])
        stored_maes = entry["errors"]["champion"]["mae"]
        stored = float(np.mean(stored_maes)) / stored_scale if stored_scale > 0 else None
        if recomputed is None or stored is None or not np.isclose(recomputed, stored, atol=1e-3):
            raise ValueError(
                f"catalog {sid}: recomputed window MASE {recomputed} != stored {stored}"
            )


def build_demo_payload(
    settings: DemandSettings,
    config: ForecastConfig,
    *,
    metrics_dir: Path | None = None,
    catalog_n: int = CATALOG_N,
    history_days: int = HISTORY_DAYS,
    horizon: int = HORIZON_DAYS,
) -> dict[str, Any]:
    """Assemble the workbench payload from committed evaluate/train artifacts."""
    metrics_dir = Path(metrics_dir) if metrics_dir else Path(settings.reports_dir)
    metrics_path = metrics_dir / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"{metrics_path} missing — run the evaluate stage first")
    metrics: dict[str, Any] = json.loads(metrics_path.read_text())
    prob_path = metrics_dir / "probabilistic.json"
    probabilistic: dict[str, Any] | None = (
        json.loads(prob_path.read_text()) if prob_path.exists() else None
    )

    features = pl.read_parquet(settings.data_dir / "features.parquet")
    champion = _champion_from_metrics(metrics)

    result = point_backtest(features, config, champion)
    band = quantile_band_backtest(features, config)

    # Drift guards: the recomputed backtest must reproduce the committed metrics.
    for model in dict.fromkeys((champion, NAIVE_MODEL)):
        run = next(r for r in result.runs if r.name == model)
        mase = run.get("mase")
        if mase is None:
            raise ValueError(f"backtest run {model} has no MASE")
        _check_close(f"metrics.{model}.mase", mase.value, float(metrics[model]["mase"]))
    if probabilistic is not None:
        _check_close(
            "probabilistic.quantile_band.coverage_pooled",
            band["coverage_pooled"],
            float(probabilistic["quantile_band"]["coverage_pooled"]),
        )

    stats = _series_stats(features)
    selected = _select_catalog(stats, catalog_n)
    fold_frame = _last_fold_frame(result, band, champion)
    class_by_sid = dict(
        zip(stats["series_id"].to_list(), stats["demand_class"].to_list(), strict=True)
    )
    catalog = [
        _catalog_entry(
            sid,
            class_by_sid[sid],
            *_window_and_history(features, fold_frame, sid, history_days, horizon),
        )
        for sid in selected
    ]
    _guard_series(catalog, fold_frame, features, history_days, horizon)

    runs = _committed_runs(metrics)
    below_one = [k for k, v in runs.items() if float(v["mase"]) < 1.0]
    only_champion = below_one == [champion]
    claim = (
        f"only {champion} clears MASE 1.0 — seasonal-naive parity — on real intermittent demand"
        if only_champion
        else f"{champion} clears MASE 1.0 on real intermittent demand "
        f"({len(below_one)} runs below 1.0)"
    )

    scalars: dict[str, Any] = {
        "headline": {
            "claim": claim,
            "champion": champion,
            "champion_mase": float(runs[champion]["mase"]),
            "champion_mae": float(runs[champion]["mae"]),
            "naive_mase": float(runs[NAIVE_MODEL]["mase"]),
            "only_champion_below_mase_1": only_champion,
            "mase_by_model": {k: float(v["mase"]) for k, v in runs.items()},
        },
        "band": (
            {
                "target_coverage": float(probabilistic["target_coverage"]),
                "quantile_coverage_pooled": float(
                    probabilistic["quantile_band"]["coverage_pooled"]
                ),
                "split_conformal_coverage_last_fold": float(
                    probabilistic["split_conformal"]["coverage_last_fold"]
                ),
                "note": "coverages are empirical out-of-fold; the catalog band is the "
                "committed quantile p10/p90 backtest (h=1 per origin)",
            }
            if probabilistic is not None
            else None
        ),
        "models": {
            "champion": champion,
            "global": champion,
            "naive": NAIVE_MODEL,
            "selection_rule": "champion = lowest pooled out-of-fold MAE on the committed "
            "expanding-window backtest (evaluate.py); 'global' = the same single pooled "
            "model serves every series (one-hot series_id); the naive floor is the weekly "
            "seasonal naive",
        },
        "feature_schema": {
            "calendar": NUMERIC_FEATURES,
            "lags": [f"lag_{lag}" for lag in config.lags],
            "series": "one-hot series_id (global model, handle_unknown='ignore')",
            "note": "calendar + lag features only — every feature is computable before "
            "day t (leakage-safe shifts)",
        },
        "catalog_summary": {
            "n_series": len(catalog),
            "by_class": {
                cls: sum(1 for e in catalog if e["demand_class"] == cls) for cls in CLASS_QUOTAS
            },
            "history_days": len(catalog[0]["history"]["y"]),
            "horizon_days": len(catalog[0]["forecast"]["y_pred"]),
            "forecast_window": [
                catalog[0]["forecast"]["dates"][0],
                catalog[0]["forecast"]["dates"][-1],
            ],
            "class_thresholds": {
                "zero_frac_smooth_max": SMOOTH_MAX_ZERO_FRAC,
                "zero_frac_intermittent_max": INTERMITTENT_MAX_ZERO_FRAC,
            },
        },
    }

    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "demo": "forecast-workbench",
        "project": "02-demand-forecasting",
        "track": config.data_source,
        "catalog": catalog,
        "scalars": scalars,
    }


def write_demo_payload(
    settings: DemandSettings,
    config: ForecastConfig,
    *,
    metrics_dir: Path | None = None,
    catalog_n: int = CATALOG_N,
    history_days: int = HISTORY_DAYS,
    horizon: int = HORIZON_DAYS,
) -> Path:
    """Build the payload and persist it to ``reports/demo_payload.json``."""
    payload = build_demo_payload(
        settings,
        config,
        metrics_dir=metrics_dir,
        catalog_n=catalog_n,
        history_days=history_days,
        horizon=horizon,
    )
    out = Path(settings.reports_dir) / DEMO_PAYLOAD_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    size = len(text.encode())
    if size > SIZE_CAP_BYTES:
        raise ValueError(f"demo payload is {size} bytes — over the {SIZE_CAP_BYTES}-byte cap")
    out.write_text(text + "\n")
    summary = payload["scalars"]["catalog_summary"]
    logger.info(
        "demo payload: %d series %s, history %dd x horizon %dd -> %s (%d bytes)",
        summary["n_series"],
        summary["by_class"],
        summary["history_days"],
        summary["horizon_days"],
        out,
        size,
    )
    return out
