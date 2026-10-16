"""Drift observatory: score one published TLC month against the pinned model.

Contract: ``.github/workflows/drift-observatory.yml`` runs
``python -m mobility.cli drift-check --month YYYY-MM --fail-on-regression``
weekly. The drift question is *not* "does a retrained model fit the new
month?" — it is "does the **persisted** serving artifact still work on data
it has never seen?". So the serving bundle (``reports/models/serving/``,
tuned GBM mean + p90 pair) is loaded via :mod:`mobility.serving`; nothing is
retrained.

Per scored month, bounded to that single file:

1. Fetch ``yellow_tripdata_<month>.parquet`` through the shared
   checksum machinery (:func:`portfolio_core.io.fetch`); a pin from
   ``data/raw/checksums.json`` is enforced when the month is one the pipeline
   already pinned. A 404 (or the CDN's 403 for a missing key) means TLC has
   not published the month yet → :class:`MonthUnavailableError` → CLI exit 2
   (the Action treats 2 as skip-worthy).
2. Light cleaning through the validate stage's ``_raw_slice``/``_clean``
   (schema contracts + month-bounded pickups) plus the cheap gates: null-rate
   ceilings and the row-count floor. Failures halt loudly like the pipeline.
3. Zone-hour demand for the month via the join stage's ``_assemble_demand``
   (same grid reindex + weather/borough join), then the same feature frame
   as training (lags/calendar via :mod:`mobility.features`).
4. Predict with the serving GBM; compare MAE/MAPE against naive lag-24 on
   the same rows, and against the pinned test-window metrics in
   ``reports/metrics.json`` (``gbm_tuned`` + its naive-relative delta).

Regression = (month MAE - pinned MAE)/pinned MAE > tolerance
(``drift.tolerance``, default 0.15; ``--tolerance`` overrides).

Persisted per month under ``reports/drift/``: ``<month>.json`` (machine
report), ``<month>_mae.html/.json`` (themed figure), ``<month>.dq.json``
(DQ gate detail), and a running markdown digest ``DRIFT.md``.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError

import plotly.graph_objects as go
import polars as pl
from portfolio_core.dq import DQCheck, DQReport
from portfolio_core.io import fetch
from portfolio_core.logging import get_logger
from portfolio_core.plotting import add_takeaway, apply_theme, save_html, save_json
from portfolio_eval.ml import regression_metrics

from mobility.config import MobilityConfig, get_config
from mobility.download import _load_pins
from mobility.features import _with_features
from mobility.join import _assemble_demand
from mobility.serving import load_serving_artifact
from mobility.validate import NULL_RATE_CEILINGS, _clean, _null_rates, _raw_slice

logger = get_logger(__name__)

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
PINNED_RUN = "gbm_tuned"


class MonthUnavailableError(RuntimeError):
    """The TLC month file does not exist upstream yet (HTTP 404)."""


@dataclass
class DriftResult:
    """Everything the report/figure/exit-code need for one scored month."""

    month: str
    tolerance: float
    n_rows: int
    month_mae: float
    month_mape_pct: float
    month_naive_mae: float
    month_delta_vs_naive_pct: float | None
    month_p90_coverage: float | None
    pinned_mae: float
    pinned_mape_pct: float
    pinned_delta_vs_naive_pct: float | None
    regression_ratio: float
    regressed: bool
    serving_run: str | None = None
    report_path: Path | None = None
    figure_html: Path | None = None
    figure_json: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def validate_month_format(month: str) -> str:
    """Reject anything that is not YYYY-MM (CLI maps this to exit 2)."""
    if not MONTH_PATTERN.match(month):
        raise ValueError(f"invalid month {month!r}: expected YYYY-MM")
    return month


def fetch_month(month: str, cfg: MobilityConfig) -> Path:
    """Download the single month file; 404 → :class:`MonthUnavailableError`.

    A checksum pin from the pipeline registry is enforced when present (a
    republication fails loudly); drift months are *never* recorded into the
    registry — that file pins the training snapshot only. Without a pin the
    local copy is reused if present (idempotent weekly runs).
    """
    validate_month_format(month)
    url = cfg.tlc_base_url.format(month=month)
    dest = cfg.drift_raw_dir / f"yellow_tripdata_{month}.parquet"
    dest.parent.mkdir(parents=True, exist_ok=True)
    pin = _load_pins(cfg.checksum_registry).get(dest.name)
    if pin is None and dest.exists():
        logger.info("reusing cached %s (no checksum pin for drift month)", dest.name)
        return dest
    try:
        return fetch(url, dest, pin)
    except HTTPError as e:
        # The CDN answers missing keys with 404 or 403 (listing denied);
        # both mean "month not published yet" for this read-only fetch.
        if e.code in (403, 404):
            dest.unlink(missing_ok=True)
            raise MonthUnavailableError(
                f"TLC month {month} is not published yet (HTTP {e.code}: {url}). "
                "TLC files land with ~2 months delay — pick an earlier month."
            ) from e
        raise


def clean_month(month: str, cfg: MobilityConfig) -> Path:
    """Light-validate the fetched month (cheap gates) → cleaned parquet.

    Reuses the validate stage's raw slice and ``Trip``-contract cleaning; the
    gates kept are the null-rate ceilings and the row-count floor (freshness
    is meaningless against a moving current month and the range checks are
    applied by the cleaning filter itself).
    """
    raw_path = cfg.drift_raw_dir / f"yellow_tripdata_{month}.parquet"
    if not raw_path.exists():
        raise FileNotFoundError(f"missing {raw_path} — fetch the month first")

    raw = _raw_slice(raw_path, cfg, "yellow").collect(engine="streaming")
    cleaned = _clean(_raw_slice(raw_path, cfg, "yellow"), month).collect(engine="streaming")
    if cleaned.height == 0:
        raise ValueError(f"month {month}: cleaning removed every row — upstream schema change?")

    report = DQReport(dataset=f"drift_yellow_{month}", n_rows=cleaned.height)
    null_rates = _null_rates(raw)
    for col, ceiling in NULL_RATE_CEILINGS.items():
        report.check_null_rate(col, null_rates[col], ceiling)
    report.add(
        # Same DQCheck shape as validate.py's row_count_floor.
        DQCheck(
            name="row_count_floor",
            column="*",
            passed=cleaned.height >= cfg.min_rows_per_month,
            metric=float(cleaned.height),
            threshold=float(cfg.min_rows_per_month),
            detail=f"cleaned rows {cleaned.height} >= floor {cfg.min_rows_per_month} "
            f"(raw {raw.height})",
        )
    )
    cfg.drift_dir.mkdir(parents=True, exist_ok=True)
    report_path = cfg.drift_dir / f"{month}.dq.json"
    report_path.write_text(report.model_dump_json(indent=2))
    report.raise_if_failed()
    logger.info("drift DQ gates passed for %s (%d rows)", month, cleaned.height)

    out = cfg.drift_clean_dir / f"{month}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    cleaned.write_parquet(out, compression="zstd")
    return out


def month_demand(month: str, cfg: MobilityConfig) -> pl.DataFrame:
    """The month's zone-hour demand: same grid/weather/borough join as the pipeline."""
    for path, stage in [
        (cfg.zones_path, "join"),
        (cfg.weather_path, "join"),
        (cfg.drift_clean_dir / f"{month}.parquet", "drift-check"),
    ]:
        if not path.exists():
            raise FileNotFoundError(f"missing {path} — run `mobility {stage}` first")
    zones = pl.read_parquet(cfg.zones_path)
    weather = pl.read_parquet(cfg.weather_path)
    return _assemble_demand(
        [cfg.drift_clean_dir / f"{month}.parquet"], cfg, zones, weather, [month]
    )


def month_features(demand: pl.DataFrame, cfg: MobilityConfig) -> pl.DataFrame:
    """The same feature frame as training (lags/calendar, next-hour target)."""
    from mobility.schemas import DemandRow

    feats = (
        _with_features(demand.lazy(), cfg)
        .drop("pickup_count")  # superseded by target, mirroring build_features
        .collect(engine="streaming")
    )
    for row in feats.head(200).iter_rows(named=True):
        _ = DemandRow(**row)
    return feats


def load_pinned_metrics(cfg: MobilityConfig) -> dict[str, Any]:
    """Pinned test-window metrics: gbm_tuned MAE/MAPE + naive-relative delta."""
    path = cfg.reports_dir / "metrics.json"
    if not path.exists():
        raise FileNotFoundError(f"missing {path} — run `mobility evaluate` first")
    metrics = json.loads(path.read_text())
    for key in (PINNED_RUN, "naive_lag24"):
        if key not in metrics:
            raise KeyError(f"reports/metrics.json has no {key!r} run — cannot pin the baseline")
    delta = metrics.get("deltas", {}).get(PINNED_RUN, {}).get("mae_reduction_pct")
    return {
        "mae": float(metrics[PINNED_RUN]["mae"]),
        "mape_pct": float(metrics[PINNED_RUN]["mape_pct"]),
        "naive_mae": float(metrics["naive_lag24"]["mae"]),
        "delta_vs_naive_pct": float(delta) if delta is not None else None,
    }


def regression_ratio(month_mae: float, pinned_mae: float) -> float:
    """Relative MAE regression vs the pinned test window (negative = improvement)."""
    if pinned_mae <= 0:
        raise ValueError("pinned MAE must be positive to define a regression ratio")
    return (month_mae - pinned_mae) / pinned_mae


def _delta_vs_naive(naive_mae: float, model_mae: float) -> float | None:
    """MAE reduction vs naive lag-24 in %; None when the naive MAE is 0."""
    if naive_mae == 0:
        return None
    return round((naive_mae - model_mae) / naive_mae * 100, 2)


def score_month(month: str, cfg: MobilityConfig) -> dict[str, Any]:
    """Predict the month's feature frame with the persisted serving bundle."""
    demand = month_demand(month, cfg)
    feats = month_features(demand, cfg)
    if feats.height == 0:
        raise ValueError(
            f"month {month}: no scorable zone-hours (need > {max(cfg.lags)}h of history)"
        )

    artifact = load_serving_artifact(cfg)
    bundle = artifact["bundle"]
    feature_names = list(bundle["feature_names"])
    gbm = bundle["gbm"]
    X = feats.select(feature_names).to_numpy()
    y_true = feats["target"].to_numpy()
    y_pred = cast(Any, gbm).predict(X)
    y_naive = feats["lag_24"].to_numpy()

    gbm_metrics = {m.name: m.value for m in regression_metrics(y_true.tolist(), y_pred.tolist())}
    naive_metrics = {m.name: m.value for m in regression_metrics(y_true.tolist(), y_naive.tolist())}

    p90_coverage: float | None = None
    p90 = bundle.get("p90")
    if p90 is not None:
        y_p90 = cast(Any, p90).predict(X)
        p90_coverage = float((y_true <= y_p90).mean())

    logger.info(
        "scored %s: %d zone-hours, MAE %.4f (naive %.4f, pinned comparison next)",
        month,
        feats.height,
        gbm_metrics["mae"],
        naive_metrics["mae"],
    )
    return {
        "n_rows": feats.height,
        "gbm_mae": float(gbm_metrics["mae"]),
        "gbm_mape_pct": float(gbm_metrics["mape_pct"]),
        "naive_mae": float(naive_metrics["mae"]),
        "naive_mape_pct": float(naive_metrics["mape_pct"]),
        "p90_coverage": p90_coverage,
        "serving_run": artifact["meta"].get("train_runs", [None])[0],
        "ts_min": str(feats["ts"].min()),
        "ts_max": str(feats["ts"].max()),
    }


def fig_drift_bars(result: DriftResult) -> go.Figure:
    """Monthly GBM MAE vs the pinned test-window baseline + naive reference."""
    labels = [
        f"pinned {PINNED_RUN}\n(Q4 test window)",
        f"{result.month}\n{PINNED_RUN} (serving)",
        f"{result.month}\nnaive_lag24",
    ]
    colors = ["#94a3b8", "#f472b6" if result.regressed else "#2dd4bf", "#94a3b8"]
    fig = go.Figure(
        data=go.Bar(
            x=labels,
            y=[result.pinned_mae, result.month_mae, result.month_naive_mae],
            marker_color=colors,
            text=[
                f"{v:.3f}" for v in (result.pinned_mae, result.month_mae, result.month_naive_mae)
            ],
            textposition="outside",
        )
    )
    ceiling = result.pinned_mae * (1 + result.tolerance)
    fig.add_hline(
        y=ceiling,
        line_dash="dash",
        line_color="#fbbf24",
        annotation_text=f"regression ceiling (+{result.tolerance:.0%})",
    )
    fig.update_layout(
        title=f"Drift check {result.month}: serving-model MAE vs pinned baseline",
        yaxis_title="MAE (pickups/hour)",
        yaxis={"range": [0, max(ceiling, result.month_mae, result.month_naive_mae) * 1.2]},
    )
    status = "REGRESSION" if result.regressed else "within tolerance"
    ratio_pct = f"{result.regression_ratio:+.1%}"
    return add_takeaway(
        apply_theme(fig),
        f"{result.month}: {ratio_pct} vs pinned MAE → {status} "
        f"(tolerance ±{result.tolerance:.0%}).",
    )


def _drift_markdown(result: DriftResult) -> str:
    month_delta = (
        f"{result.month_delta_vs_naive_pct:+.1f}%"
        if result.month_delta_vs_naive_pct is not None
        else "n/a (naive MAE = 0)"
    )
    pinned_delta = (
        f"{result.pinned_delta_vs_naive_pct:+.1f}%"
        if result.pinned_delta_vs_naive_pct is not None
        else "n/a"
    )
    lines = [
        f"## {result.month} — {'❌ REGRESSION' if result.regressed else '✅ within tolerance'}",
        "",
        f"- serving model: `{result.serving_run or 'unknown'}` (persisted artifact, no retraining)",
        f"- scored rows: {result.n_rows:,} zone-hours",
        f"- MAE: **{result.month_mae:.4f}** vs pinned {result.pinned_mae:.4f} "
        f"({result.regression_ratio:+.2%}, tolerance ±{result.tolerance:.0%})",
        f"- MAPE: {result.month_mape_pct:.2f}% vs pinned {result.pinned_mape_pct:.2f}%",
        f"- ΔMAE vs naive lag-24: {month_delta} (pinned window: {pinned_delta})",
    ]
    if result.month_p90_coverage is not None:
        lines.append(f"- p90 band coverage: {result.month_p90_coverage:.1%} (target 90%)")
    lines.append("")
    return "\n".join(lines)


def write_report(result: DriftResult, cfg: MobilityConfig) -> DriftResult:
    """Persist <month>.json + themed figure (.html/.json) + append DRIFT.md."""
    cfg.drift_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "month": result.month,
        "generated_at": datetime.now(UTC).isoformat(),
        "tolerance": result.tolerance,
        "regressed": result.regressed,
        "regression_ratio": result.regression_ratio,
        "serving_run": result.serving_run,
        "n_scored_rows": result.n_rows,
        "month_metrics": {
            PINNED_RUN: {
                "mae": result.month_mae,
                "mape_pct": result.month_mape_pct,
                "mae_reduction_vs_naive_pct": result.month_delta_vs_naive_pct,
                "p90_coverage": result.month_p90_coverage,
            },
            "naive_lag24": {"mae": result.month_naive_mae},
        },
        "pinned_test_window": {
            "source": "reports/metrics.json",
            PINNED_RUN: {
                "mae": result.pinned_mae,
                "mape_pct": result.pinned_mape_pct,
                "mae_reduction_vs_naive_pct": result.pinned_delta_vs_naive_pct,
            },
        },
        **result.extra,
    }
    report_path = cfg.drift_dir / f"{result.month}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    fig = fig_drift_bars(result)
    figure_html = save_html(fig, cfg.drift_dir / f"{result.month}_mae.html")
    figure_json = save_json(fig, cfg.drift_dir / f"{result.month}_mae.json")

    drift_md = cfg.drift_dir / "DRIFT.md"
    if not drift_md.exists():
        drift_md.write_text(
            "# Drift observatory — 07-open-data-mobility\n\n"
            "Each published TLC month scored against the pinned serving model "
            "(persisted artifact, no retraining) by the scheduled "
            "`drift-observatory` workflow. Regression = month MAE > pinned "
            "test-window MAE x (1 + tolerance). Response runbook: "
            "`docs/runbooks/drift-response.md`.\n\n"
        )
    with drift_md.open("a") as f:
        f.write(_drift_markdown(result))

    result.report_path = report_path
    result.figure_html = figure_html
    result.figure_json = figure_json
    logger.info("drift report -> %s", report_path)
    return result


def run_drift_check(
    month: str,
    cfg: MobilityConfig | None = None,
    tolerance: float | None = None,
) -> DriftResult:
    """Score one month end to end; raises MonthUnavailableError on a 404."""
    cfg = cfg or get_config()
    validate_month_format(month)
    tol = cfg.drift.tolerance if tolerance is None else tolerance

    fetch_month(month, cfg)
    clean_month(month, cfg)
    score = score_month(month, cfg)
    pinned = load_pinned_metrics(cfg)

    ratio = regression_ratio(score["gbm_mae"], pinned["mae"])
    result = DriftResult(
        month=month,
        tolerance=tol,
        n_rows=int(score["n_rows"]),
        month_mae=score["gbm_mae"],
        month_mape_pct=score["gbm_mape_pct"],
        month_naive_mae=score["naive_mae"],
        month_delta_vs_naive_pct=_delta_vs_naive(score["naive_mae"], score["gbm_mae"]),
        month_p90_coverage=score["p90_coverage"],
        pinned_mae=pinned["mae"],
        pinned_mape_pct=pinned["mape_pct"],
        pinned_delta_vs_naive_pct=pinned["delta_vs_naive_pct"],
        regression_ratio=ratio,
        regressed=ratio > tol,
        serving_run=score["serving_run"],
        extra={
            "scored_window": {"ts_min": score["ts_min"], "ts_max": score["ts_max"]},
            "naive_lag24": {"mae": score["naive_mae"], "mape_pct": score["naive_mape_pct"]},
        },
    )
    return write_report(result, cfg)
