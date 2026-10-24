"""Demo payload for the demand forecast workbench (showcase demo).

Builds ``reports/demo_payload.json`` — a compact, fully precomputed catalog
that lets the showcase UI render per-series demand forecasts with a band and
the seasonal-naive floor client-side, without retraining or serving model
inference. Schema v2 turns the catalog into a multi-origin backtest bundle on
top of the hardened ``rolling_origin_holdout_v1`` protocol:

- ~100 store-product series from the UCI Online Retail II track (real
  intermittent demand), chosen for demand-class coverage — smooth /
  intermittent / sparse — derived from the committed per-series
  zero-fraction with documented thresholds (``SMOOTH_MAX_ZERO_FRAC`` et al.);
- per series, the v1 keys are unchanged: the last ``HISTORY_DAYS`` committed
  actuals (daily, with dates — the tail includes the forecast window, so the
  UI can overlay the forecast on actuals), the committed test-window backtest
  block (champion point forecast ``y_pred``, p10/p90 quantile band, the
  seasonal-naive floor) and the per-horizon error arrays; emitted curves are
  display-sanitized — clipped at zero (demand cannot be negative), bands
  clamped around the point curve, sparse all-zero-window series carrying
  ``null`` instead of a degenerate band — and the stored window metrics are
  computed from the stored curves, so the payload is exactly self-consistent
  (headline metrics in metrics.json remain the raw backtest values);
- per series, three rolling origins — ``early`` / ``middle`` (two of the
  committed selection folds) and ``test`` (the designated test window, the
  last origin) — each with the as-of-origin history (actuals up to the origin
  date), the 14 horizon days of actuals, and per-model curves for the
  champion, the challenger and the seasonal-naive floor: ``y_pred`` for all
  three, p10/p90 for the champion only. Per origin, per model, the 14-day
  window metrics are precomputed (``mae`` / ``mase`` / ``bias`` / ``wape``)
  so the UI's comparison and error views never recompute;
- ``origins_meta`` records the three origin dates, their fold indices, the
  ``holdout: "test"`` designation on the last origin and the
  ``selection_used_origins`` echo from the committed evaluation metadata;
- ``evaluation_metadata`` embeds the committed protocol block (rolling-origin
  spec, holdout designation, metric definitions including bias/WAPE, and the
  one-sentence target definition) and ``dataset_metadata`` embeds the
  committed dataset card (source URL + sha256, cleaning rules, the
  zero-sales-day caveat, the observed date range);
- the committed scalars: the headline MASE ladder (no run dips below MASE 1
  on the frozen test window — the naive floor itself scores 1.310 there, its
  scale being in-sample error from a quieter period), the champion's MAE edge
  over the strongest naive floor (~15.7%), the band coverage + calibration
  verdict, the champion/challenger/global/naive model names from the
  committed backtest selection, and the feature-schema note (calendar + lag
  features).

Champion = the committed ``_meta.best_model`` (selected on the selection
folds only); challenger = the committed test-window rank-2 non-naive model
(the runner-up to the champion on the frozen test window, by headline MAE).

Everything is deterministic and drift-guarded: the point backtest is
``evaluate.backtest`` on the committed features parquet (the same expanding
windows + embargo that wrote ``reports_uci/metrics.json``), the band reuses
``probabilistic``'s quantile recipe (the one behind
``reports_uci/probabilistic.json``), a recomputed pooled MASE or band
coverage that disagrees with the committed metrics JSONs raises, and the
origin plan must match the committed ``evaluation_metadata.json`` (test
origin = last fold, selection origins = folds 1..n-1).
"""

import json
from datetime import date, timedelta
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
PAYLOAD_SCHEMA_VERSION = 2
CATALOG_N = 100
HISTORY_DAYS = 180
ORIGIN_HISTORY_DAYS = 60
HORIZON_DAYS = 14
SEASON = 7
SIZE_CAP_BYTES = 3 * 1024 * 1024
NAIVE_MODEL = "seasonal_naive"

# Demand classes, derived per series from the committed zero-fraction (share
# of modelling-frame days with zero demand) — documented thresholds:
#   smooth:       < 35% zero days — regular, plannable demand
#   intermittent: 35-90%          — frequent zero gaps between demand bursts
#   sparse:       >= 90%          — mostly zero days (count-type demand)
SMOOTH_MAX_ZERO_FRAC = 0.35
INTERMITTENT_MAX_ZERO_FRAC = 0.90
# Per-class catalog quotas (coverage-first selection, top-up by volume);
# ~100 series + 3 origins x 60-day histories keep the indented payload under
# the 3 MB cap (the v1 180-day per-series history is kept for compat).
CLASS_QUOTAS = {"smooth": 20, "intermittent": 35, "sparse": 45}
# The three showcased origins: two selection folds (early/middle) + the test
# window (the last fold, designated holdout).
ORIGIN_LABELS = ("early", "middle", "test")


def _check_close(name: str, actual: float, committed: float, tol: float = 1e-6) -> None:
    """Guard against drift between the committed metrics JSONs and the frame."""
    if not np.isclose(actual, committed, rtol=tol, atol=tol):
        raise ValueError(f"{name}: recomputed {actual} != committed {committed}")


def _committed_runs(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The per-model blocks of a committed metrics.json (no ``_meta`` keys)."""
    return {k: v for k, v in metrics.items() if not k.startswith("_") and isinstance(v, dict)}


def _champion_from_metrics(metrics: dict[str, Any]) -> str:
    """The champion per the committed backtest selection.

    Prefers the protocol-recorded ``_meta.best_model`` (selected on folds
    1..n-1 only, never the test window); falls back to the lowest committed
    MAE for metrics files written before the holdout protocol.
    """
    meta = metrics.get("_meta")
    if isinstance(meta, dict) and isinstance(meta.get("best_model"), str):
        return str(meta["best_model"])
    runs = _committed_runs(metrics)
    return min((k for k in runs if not _is_naive(k)), key=lambda k: float(runs[k]["mae"]))


def _challenger_from_metrics(metrics: dict[str, Any], champion: str) -> str:
    """The committed test-window rank-2 non-naive model (the challenger).

    Ranked by the committed headline (test-window) MAE over the non-naive
    runs, with the champion removed — rank 1 is the strongest rival, rank 2
    is the runner-up showcased next to the champion in the comparison view.
    """
    runs = _committed_runs(metrics)
    ranked = sorted(
        (k for k in runs if not _is_naive(k) and k != champion),
        key=lambda k: float(runs[k]["mae"]),
    )
    if len(ranked) < 2:
        raise ValueError("need >= 2 non-naive runs besides the champion for a challenger")
    return ranked[1]


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


def point_backtest(
    features: pl.DataFrame,
    config: ForecastConfig,
    champion: str,
    challenger: str | None = None,
) -> BacktestResult:
    """The runs the catalog needs: champion (+ challenger) + seasonal-naive floor.

    This is ``evaluate.backtest`` unchanged — same expanding windows, same
    embargo, pooled out-of-fold — so the recomputed MASEs are directly
    comparable to the committed ``reports/metrics.json``. ``challenger`` is
    optional so pre-holdout callers/tests can keep the v1 two-run shape.
    """
    names = {champion, challenger or champion, NAIVE_MODEL}
    specs = [s for s in model_specs() if s.name in names]
    return backtest(features, config, specs=specs)


def quantile_band_backtest(features: pl.DataFrame, config: ForecastConfig) -> dict[str, Any]:
    """Per-fold p10/p90 quantile band backtest (``probabilistic``'s recipe).

    Fits the tuned-config quantile HGBs on each fold's training window and
    keeps every fold's predictions (the catalog band per origin); the pooled
    coverage is recomputed with :func:`probabilistic.coverage` and verified
    against the committed ``probabilistic.json`` by the caller.
    """
    x, y = _design_matrix(features, config)
    folds = cv_row_folds(features, config)
    per_fold: list[float] = []
    by_fold: dict[int, dict[str, Any]] = {}
    for k, (train_rows, val_rows) in enumerate(folds):
        models = _fit_quantile_models(x[train_rows], y[train_rows], config)
        p10 = np.asarray(models[QUANTILES[0]].predict(x[val_rows]), dtype=float)
        p90 = np.asarray(models[QUANTILES[-1]].predict(x[val_rows]), dtype=float)
        per_fold.append(coverage(y[val_rows], p10, p90))
        by_fold[k] = {"rows": val_rows, "p10": p10, "p90": p90}
    if not by_fold:  # pragma: no cover - n_splits >= 2 guarantees a last fold
        raise ValueError("backtest produced no folds")
    last_key = max(by_fold)
    return {
        "coverage_pooled": float(np.mean(per_fold)),
        "per_fold": per_fold,
        "by_fold": by_fold,
        "last": {"rows": by_fold[last_key]["rows"], **by_fold[last_key]},
    }


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


def _origin_fold_frame(
    result: BacktestResult,
    band: dict[str, Any],
    fold_id: int,
    champion: str,
    challenger: str,
) -> pl.DataFrame:
    """One origin's (date, series) rows with champion/challenger/naive + band.

    Same positional-join contract as :func:`_last_fold_frame`, for an
    arbitrary fold and three model curves.
    """
    recs = {
        m: next(f for f in result.folds if f.model == m and f.fold == fold_id)
        for m in (champion, challenger, NAIVE_MODEL)
    }
    b = band["by_fold"][fold_id]
    rec = recs[champion]
    n = rec.dates.size
    if not all(r.dates.size == n for r in recs.values()) or b["p10"].size != n:
        raise ValueError(f"fold {fold_id} prediction arrays disagree in length")
    cols: dict[str, Any] = {
        "date": [str(d)[:10] for d in rec.dates],
        "series_id": [str(s) for s in rec.series],
        "y_true": rec.y_true.astype(float),
        "p10": b["p10"],
        "p90": b["p90"],
    }
    for m, r in recs.items():
        cols[f"pred__{m}"] = r.y_pred.astype(float)
    return pl.DataFrame(cols)


def _origin_plan(result: BacktestResult) -> list[tuple[str, int]]:
    """The showcased (label, fold_id) pairs: two selection folds + the test fold."""
    fold_ids = sorted({f.fold for f in result.folds})
    if len(fold_ids) < 3:
        raise ValueError(
            f"multi-origin payload needs >= 3 folds, got {len(fold_ids)} — "
            "n_splits must be >= 3 (2 selection folds + the test window)"
        )
    return [
        (ORIGIN_LABELS[0], fold_ids[0]),
        (ORIGIN_LABELS[1], fold_ids[1]),
        ("test", fold_ids[-1]),
    ]


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


def _window_metrics(err: np.ndarray, actual: np.ndarray, scale: float) -> dict[str, Any]:
    """The precomputed 14-day window metrics for one model curve.

    ``err = pred - actual`` (the committed bias sign convention); MASE divides
    by the series' seasonal-naive scale over the origin's history (None when
    the scale is 0); WAPE is None when the window has zero total demand.
    """
    abs_actual = float(np.abs(actual).sum())
    return {
        "mae": round(float(np.mean(np.abs(err))), 4),
        "mase": round(float(np.mean(np.abs(err)) / scale), 4) if scale > 0 else None,
        "bias": round(float(np.mean(err)), 4),
        "wape": round(float(np.abs(err).sum() / abs_actual), 4) if abs_actual > 0 else None,
    }


def _emit_band(
    p10: np.ndarray,
    p50: np.ndarray,
    p90: np.ndarray,
    *,
    zero_window: bool,
    sparse: bool,
) -> tuple[list[float] | None, list[float] | None]:
    """Sanitized p10/p90 curves for the catalog (schema v2; ``None`` = no band).

    The committed quantile band is replayed unchanged except for two
    display-level sanity rules, applied per point: clip at zero (the quantile
    HGB emits small negatives on zero-demand days) and clamp the band around
    the displayed point curve (``p10 <= p50 <= p90``) so the UI never shades
    a band that contradicts the line inside it. Both rules are no-ops on
    well-formed points — they only bite on degenerate quantile outputs (the
    audit found 124/4200 inverted origin-band points, all from negative or
    collapsed quantiles). A sparse series whose whole window is zero demand
    honestly carries no band at all (``None``, not a degenerate zero-width
    interval pretending precision the window does not contain); the point
    forecast stays the committed backtest value.
    """
    if sparse and zero_window:
        return None, None
    lo = np.clip(np.minimum(p10, p50), 0.0, None)
    hi = np.clip(np.maximum(p90, p50), 0.0, None)
    return (
        [round(float(v), 4) for v in lo],
        [round(float(v), 4) for v in hi],
    )


def _origin_series_entry(
    features: pl.DataFrame,
    origin_frame: pl.DataFrame,
    series_id: str,
    origin_date: str,
    champion: str,
    challenger: str,
    horizon: int,
    origin_history_days: int,
    demand_class: str,
) -> dict[str, Any]:
    """One catalog series at one origin: as-of-origin history, actuals, curves.

    The history is cut at the origin date (the day before the fold's val
    window — the forecast issuance date), so the early/middle origins carry
    their own context window instead of leaking the test window; the actuals
    are the last ``horizon`` days of the origin's committed fold window.
    """
    sub = origin_frame.filter(pl.col("series_id") == series_id).sort("date")
    if sub.height < horizon:
        raise ValueError(f"{series_id}: origin fold has {sub.height} rows < horizon {horizon}")
    win = sub.tail(horizon)
    cutoff = date.fromisoformat(origin_date)
    hist = (
        features.filter((pl.col("series_id") == series_id) & (pl.col("date") <= cutoff))
        .sort("date")
        .tail(origin_history_days)
    )
    hist_y = hist["y"].to_numpy()
    actual = win["y_true"].to_numpy()
    scale = _seasonal_scale(hist_y)

    def _model_block(col: str, with_band: bool = False) -> dict[str, Any]:
        # metrics are computed from the CLIPPED-AND-ROUNDED stored curve so the
        # payload is exactly self-consistent (a UI recomputation from y_pred
        # reproduces the stored mae/mase/bias/wape bit for bit); demand cannot
        # be negative, so the emitted curve clips the raw backtest at zero
        # (headline metrics in metrics.json remain the raw backtest values)
        pred = np.clip(np.asarray([round(float(v), 4) for v in win[col].to_numpy()]), 0.0, None)
        block: dict[str, Any] = {
            "y_pred": [float(v) for v in pred],
            **_window_metrics(pred - actual, actual, scale),
        }
        if with_band:
            block["p10"], block["p90"] = _emit_band(
                np.asarray(win["p10"].to_numpy(), dtype=float),
                pred,
                np.asarray(win["p90"].to_numpy(), dtype=float),
                zero_window=bool(np.all(actual == 0)),
                sparse=demand_class == "sparse",
            )
        return block

    models: dict[str, Any] = {
        "champion": _model_block(f"pred__{champion}", with_band=True),
        "challenger": _model_block(f"pred__{challenger}"),
        "naive": _model_block(f"pred__{NAIVE_MODEL}"),
    }
    return {
        "origin_date": origin_date,
        "history": {
            "dates": hist["date"].cast(pl.String).to_list(),
            "y": [int(v) for v in hist_y],
        },
        "actuals": {
            "dates": win["date"].to_list(),
            "y": [int(v) for v in actual],
        },
        "scale": round(scale, 4),
        "models": models,
    }


def _catalog_entry(
    series_id: str,
    demand_class: str,
    hist: pl.DataFrame,
    win: pl.DataFrame,
    origins: dict[str, Any],
) -> dict[str, Any]:
    """One catalog series: v1 window block plus the multi-origin bundle."""
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
    # clip at zero like the origin curves (demand cannot be negative); stored
    # errors are computed from the stored curve so the payload stays exactly
    # self-consistent
    y_pred = [round(float(v), 4) for v in np.clip(win["y_pred"].to_numpy(), 0.0, None)]
    naive = [round(float(v), 4) for v in win["naive"]]
    p10, p90 = _emit_band(
        np.asarray(win["p10"].to_numpy(), dtype=float),
        np.asarray(y_pred, dtype=float),
        np.asarray(win["p90"].to_numpy(), dtype=float),
        zero_window=bool(np.all(win_true == 0)),
        sparse=demand_class == "sparse",
    )
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
            "y_pred": y_pred,
            "p10": p10,
            "p90": p90,
            "naive": naive,
        },
        "errors": {
            "scale": round(scale, 4),
            "champion": _errors(np.asarray(y_pred, dtype=float)),
            "naive": _errors(np.asarray(naive, dtype=float)),
        },
        "origins": origins,
    }


def _guard_series(
    catalog: list[dict[str, Any]],
    fold_frame: pl.DataFrame,
    features: pl.DataFrame,
    history_days: int,
    horizon: int,
) -> None:
    """Spot-check two catalog series: window MASE recomputed straight from the
    committed frame must match the stored per-horizon errors, and the test
    origin's stored curves must agree with the v1 forecast block."""
    for entry in (catalog[0], catalog[-1]):
        sid = entry["series_id"]
        hist, win = _window_and_history(features, fold_frame, sid, history_days, horizon)
        scale = _seasonal_scale(hist["y"].to_numpy())
        # the stored curve is the raw backtest clipped at zero — recompute with
        # the same clip so the guard matches what is emitted
        clipped = np.clip(win["y_pred"].to_numpy(), 0.0, None)
        err = float(np.mean(np.abs(win["y_true"].to_numpy() - clipped)))
        recomputed = err / scale if scale > 0 else None
        stored_scale = float(entry["errors"]["scale"])
        stored_maes = entry["errors"]["champion"]["mae"]
        stored = float(np.mean(stored_maes)) / stored_scale if stored_scale > 0 else None
        if recomputed is None or stored is None or not np.isclose(recomputed, stored, atol=1e-3):
            raise ValueError(
                f"catalog {sid}: recomputed window MASE {recomputed} != stored {stored}"
            )
        test_origin = entry["origins"]["test"]
        if test_origin["actuals"]["dates"] != entry["forecast"]["dates"]:
            raise ValueError(f"catalog {sid}: test-origin actuals disagree with the v1 window")
        for key, _v1_curve in (("champion", "y_pred"), ("naive", "naive")):
            stored_mae = float(np.mean(test_origin["models"][key]["mae"]))
            v1_mae = float(np.mean(entry["errors"][key]["mae"]))
            if not np.isclose(stored_mae, v1_mae, atol=1e-3):
                raise ValueError(
                    f"catalog {sid}: test-origin {key} MAE {stored_mae} != v1 window {v1_mae}"
                )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — run the evaluate stage first")
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def build_demo_payload(
    settings: DemandSettings,
    config: ForecastConfig,
    *,
    metrics_dir: Path | None = None,
    catalog_n: int = CATALOG_N,
    history_days: int = HISTORY_DAYS,
    horizon: int = HORIZON_DAYS,
    origin_history_days: int = ORIGIN_HISTORY_DAYS,
) -> dict[str, Any]:
    """Assemble the workbench payload from committed evaluate/train artifacts."""
    metrics_dir = Path(metrics_dir) if metrics_dir else Path(settings.reports_dir)
    metrics = _load_json(metrics_dir / "metrics.json")
    probabilistic = (
        _load_json(metrics_dir / "probabilistic.json")
        if (metrics_dir / "probabilistic.json").exists()
        else None
    )
    eval_meta = _load_json(metrics_dir / "evaluation_metadata.json")
    dataset_meta = _load_json(metrics_dir / "dataset_metadata.json")

    features = pl.read_parquet(settings.data_dir / "features.parquet")
    champion = _champion_from_metrics(metrics)
    challenger = _challenger_from_metrics(metrics, champion)

    result = point_backtest(features, config, champion, challenger)
    band = quantile_band_backtest(features, config)

    # Drift guards: the recomputed backtest must reproduce the committed metrics.
    for model in dict.fromkeys((champion, challenger, NAIVE_MODEL)):
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

    # The origin plan must match the committed evaluation metadata: the last
    # fold is the designated test window, folds 1..n-1 are the selection folds.
    fold_ids = sorted({f.fold for f in result.folds})
    protocol = str(eval_meta.get("protocol", ""))
    if protocol != "rolling_origin_holdout_v1":
        raise ValueError(f"evaluation_metadata protocol {protocol!r} != rolling_origin_holdout_v1")
    if int(eval_meta.get("test_origin", -1)) != fold_ids[-1] + 1:
        raise ValueError("evaluation_metadata test_origin disagrees with the backtest folds")
    if [int(o) for o in eval_meta.get("selection_used_origins", [])] != [
        f + 1 for f in fold_ids[:-1]
    ]:
        raise ValueError("evaluation_metadata selection_used_origins disagrees with the folds")

    plan = _origin_plan(result)
    origin_frames = {
        label: _origin_fold_frame(result, band, fold_id, champion, challenger)
        for label, fold_id in plan
    }
    origins_meta: list[dict[str, Any]] = []
    for label, fold_id in plan:
        frame = origin_frames[label]
        fold_dates = sorted(frame["date"].unique().to_list())
        window = fold_dates[-horizon:]
        origin_date = (date.fromisoformat(fold_dates[0]) - timedelta(days=1)).isoformat()
        meta: dict[str, Any] = {
            "label": label,
            "origin": fold_id + 1,
            "fold_index": fold_id,
            "origin_date": origin_date,
            "horizon_window": [window[0], window[-1]],
        }
        if label == "test":
            meta["holdout"] = "test"
        origins_meta.append(meta)

    stats = _series_stats(features)
    selected = _select_catalog(stats, catalog_n)
    fold_frame = _last_fold_frame(result, band, champion)
    class_by_sid = dict(
        zip(stats["series_id"].to_list(), stats["demand_class"].to_list(), strict=True)
    )
    catalog: list[dict[str, Any]] = []
    for sid in selected:
        hist, win = _window_and_history(features, fold_frame, sid, history_days, horizon)
        origins = {
            label: _origin_series_entry(
                features,
                origin_frames[label],
                sid,
                next(m["origin_date"] for m in origins_meta if m["label"] == label),
                champion,
                challenger,
                horizon,
                origin_history_days,
                class_by_sid[sid],
            )
            for label, _ in plan
        }
        catalog.append(_catalog_entry(sid, class_by_sid[sid], hist, win, origins))
    _guard_series(catalog, fold_frame, features, history_days, horizon)

    runs = _committed_runs(metrics)
    below_one = [k for k, v in runs.items() if float(v["mase"]) < 1.0]
    naive_mase = float(runs[NAIVE_MODEL]["mase"])
    # MASE here divides by the seasonal-naive's in-sample error (a quieter
    # period), so the naive itself scores > 1 on the holiday-quarter test
    # window — 1.0 is not seasonal-naive parity and must not be worded as such.
    if below_one == [champion]:
        claim = (
            f"only {champion} dips below MASE 1.0 on real intermittent demand "
            f"(the naive floor itself scores {naive_mase:.3f} on this window)"
        )
    elif not below_one:
        closest = min(runs, key=lambda k: float(runs[k]["mase"]))
        claim = (
            "no run dips below MASE 1.0 on the frozen test window (the naive "
            f"floor itself scores {naive_mase:.3f} there — the scale is its "
            f"in-sample error from a quieter period); {closest} is closest at "
            f"MASE {float(runs[closest]['mase']):.3f}"
        )
    else:
        claim = (
            f"{champion} dips below MASE 1.0 on real intermittent demand "
            f"({len(below_one)} runs below 1.0)"
        )

    naive_runs = {k: v for k, v in runs.items() if _is_naive(k)}
    strongest_naive = min(naive_runs, key=lambda k: float(naive_runs[k]["mae"]))
    mae_edge_pct = round(
        100.0
        * (float(runs[strongest_naive]["mae"]) - float(runs[champion]["mae"]))
        / float(runs[strongest_naive]["mae"]),
        1,
    )
    split_conformal = (
        probabilistic.get("split_conformal", {}) if isinstance(probabilistic, dict) else {}
    )
    scalars: dict[str, Any] = {
        "headline": {
            "claim": claim,
            "champion": champion,
            "challenger": challenger,
            "champion_mase": float(runs[champion]["mase"]),
            "champion_mae": float(runs[champion]["mae"]),
            "naive_mase": float(runs[NAIVE_MODEL]["mase"]),
            "strongest_naive": strongest_naive,
            "strongest_naive_mae": float(runs[strongest_naive]["mae"]),
            "champion_mae_edge_vs_strongest_naive_pct": mae_edge_pct,
            "only_champion_below_mase_1": below_one == [champion],
            "runs_below_mase_1": below_one,
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
                "calibration_verdict": split_conformal.get("calibration_verdict"),
                "horizon_coverage": split_conformal.get("horizon_coverage"),
                "horizon_avg_width": split_conformal.get("horizon_avg_width"),
                "note": "coverages are empirical out-of-fold; the catalog band is the "
                "committed quantile p10/p90 backtest (h=1 per origin), replayed per "
                "origin on the same fold train windows",
            }
            if probabilistic is not None
            else None
        ),
        "models": {
            "champion": champion,
            "challenger": challenger,
            "global": champion,
            "naive": NAIVE_MODEL,
            "selection_rule": "champion = committed _meta.best_model — lowest pooled MAE over "
            "the selection folds (origins 1..n-1) of the committed expanding-window "
            "backtest (evaluate.py); challenger = the committed test-window rank-2 "
            "non-naive model (runner-up to the champion on the frozen test window, by "
            "headline MAE); the final holdout window is scored once and never read for "
            "selection; 'global' = the same single pooled model serves every series "
            "(one-hot series_id); the naive floor is the weekly seasonal naive",
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
            "origins": {
                m["label"]: {
                    "origin": m["origin"],
                    "fold_index": m["fold_index"],
                    "origin_date": m["origin_date"],
                    "horizon_window": m["horizon_window"],
                    "history_days": len(catalog[0]["origins"][m["label"]]["history"]["y"]),
                }
                for m in origins_meta
            },
        },
    }

    target_definition = str(dataset_meta.get("target_definition", ""))
    evaluation_metadata = {**eval_meta, "target_definition": target_definition}

    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "demo": "forecast-workbench",
        "project": "02-demand-forecasting",
        "track": config.data_source,
        "catalog": catalog,
        "scalars": scalars,
        "origins_meta": {
            "origins": origins_meta,
            "selection_used_origins": [int(o) for o in eval_meta["selection_used_origins"]],
            "horizon_days": horizon,
        },
        "evaluation_metadata": evaluation_metadata,
        "dataset_metadata": dataset_meta,
    }


def write_demo_payload(
    settings: DemandSettings,
    config: ForecastConfig,
    *,
    metrics_dir: Path | None = None,
    catalog_n: int = CATALOG_N,
    history_days: int = HISTORY_DAYS,
    horizon: int = HORIZON_DAYS,
    origin_history_days: int = ORIGIN_HISTORY_DAYS,
) -> Path:
    """Build the payload and persist it to ``reports/demo_payload.json``."""
    payload = build_demo_payload(
        settings,
        config,
        metrics_dir=metrics_dir,
        catalog_n=catalog_n,
        history_days=history_days,
        horizon=horizon,
        origin_history_days=origin_history_days,
    )
    out = Path(settings.reports_dir) / DEMO_PAYLOAD_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2)
    size = len(text.encode())
    if size > SIZE_CAP_BYTES:
        raise ValueError(f"demo payload is {size} bytes — over the {SIZE_CAP_BYTES}-byte cap")
    out.write_text(text + "\n")
    summary = payload["scalars"]["catalog_summary"]
    origins = payload["origins_meta"]["origins"]
    logger.info(
        "demo payload: %d series %s, history %dd x horizon %dd, origins %s -> %s (%d bytes)",
        summary["n_series"],
        summary["by_class"],
        summary["history_days"],
        summary["horizon_days"],
        [(m["label"], m["origin_date"]) for m in origins],
        out,
        size,
    )
    return out
