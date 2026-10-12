"""Data-quality gates for telemetry (platform.md §Contracts).

Gates are data, not prints: each check lands in a :class:`DQReport`, the
report is persisted to HTML, and any failure halts the pipeline loudly via
``raise_if_failed`` (:class:`DQGateError`).
"""

import math

import polars as pl
from portfolio_core.dq import DQReport
from portfolio_core.logging import get_logger
from portfolio_eval.report import EvalReport

from anomaly_detection.config import SIGNALS, AnomalyConfig

logger = get_logger(__name__)

TS_COLUMN = "ts"


def run_dq_gates(df: pl.DataFrame, config: AnomalyConfig) -> DQReport:
    """Evaluate every gate against the raw frame and persist the report.

    Gates:
      * null rate per column <= ``config.max_null_rate``;
      * ``cpu`` and ``mem`` observed within [0, 100];
      * ``latency_ms`` strictly positive (lower bound is a small epsilon so a
        legitimate tiny-but-positive latency still passes).
    """
    report = DQReport(dataset="telemetry", n_rows=df.height)
    for col in (*SIGNALS, TS_COLUMN, "is_anomaly"):
        null_rate = df[col].null_count() / df.height
        report.check_null_rate(col, null_rate, config.max_null_rate)

    stats = df.select(
        [pl.min(c).alias(f"{c}_min") for c in SIGNALS]
        + [pl.max(c).alias(f"{c}_max") for c in SIGNALS]
    ).row(0)
    mins = dict(zip(SIGNALS, stats[: len(SIGNALS)], strict=True))
    maxs = dict(zip(SIGNALS, stats[len(SIGNALS) :], strict=True))
    report.check_range("cpu", float(mins["cpu"]), float(maxs["cpu"]), 0.0, 100.0)
    report.check_range("mem", float(mins["mem"]), float(maxs["mem"]), 0.0, 100.0)
    report.check_range(
        "latency_ms", float(mins["latency_ms"]), float(maxs["latency_ms"]), 1e-9, math.inf
    )
    return report


def persist_report(report: DQReport, config: AnomalyConfig) -> None:
    """Render the DQ report to a standalone HTML artifact."""
    doc = EvalReport(title="DQ Report — telemetry (03-anomaly-detection)")
    doc.add_markdown_table("DQ gates", report.to_markdown())
    doc.write(config.dq_report_path)
    logger.info("wrote %s (passed=%s)", config.dq_report_path, report.passed)


def validate(df: pl.DataFrame, config: AnomalyConfig) -> DQReport:
    """Run gates, persist the report, then fail loudly if any gate failed."""
    report = run_dq_gates(df, config)
    persist_report(report, config)
    report.raise_if_failed()
    logger.info("all %d DQ gates passed", len(report.checks))
    return report
