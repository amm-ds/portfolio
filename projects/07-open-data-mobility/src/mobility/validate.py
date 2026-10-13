"""Per-month DQ gates + cleaned narrow parquet output.

One month at a time (bounded memory, streaming engine): measure raw null
rates, drop rows that violate the ``Trip`` contract ranges or carry nulls in
critical columns, then verify gates — null-rate ceilings, observed ranges,
freshness (newest pickup inside the month), and a row-count floor — via
``portfolio_core.dq.DQReport``. Any failure halts the pipeline loudly
(``DQGateError``) with the full report persisted to ``reports/dq/``.
"""

from pathlib import Path
from typing import cast

import polars as pl
from portfolio_core.dq import DQCheck, DQReport
from portfolio_core.logging import get_logger

from mobility.config import MobilityConfig, get_config
from mobility.schemas import Trip

logger = get_logger(__name__)

#: Columns carried downstream (narrow slice keeps RAM bounded). Green files
#: timestamp with lpep_*; everything else shares the yellow schema.
_TRIP_COLUMNS = {
    "yellow": {
        "tpep_pickup_datetime": "pickup_ts",
        "tpep_dropoff_datetime": "dropoff_ts",
        "PULocationID": "pulocation_id",
        "DOLocationID": "dolocation_id",
        "passenger_count": "passenger_count",
        "trip_distance": "trip_distance_mi",
        "fare_amount": "fare_amount",
    },
    "green": {
        "lpep_pickup_datetime": "pickup_ts",
        "lpep_dropoff_datetime": "dropoff_ts",
        "PULocationID": "pulocation_id",
        "DOLocationID": "dolocation_id",
        "passenger_count": "passenger_count",
        "trip_distance": "trip_distance_mi",
        "fare_amount": "fare_amount",
    },
}

MI_TO_KM = 1.60934

#: Null-rate ceilings on the raw month slice. passenger_count is unused for
#: demand (we count trips, not people) and TLC leaves 5-13% null in 2024 —
#: the ceiling exists to catch a structurally broken file, not the known gap.
NULL_RATE_CEILINGS = {
    "pickup_ts": 0.01,
    "dropoff_ts": 0.01,
    "pulocation_id": 0.01,
    "dolocation_id": 0.01,
    "passenger_count": 0.20,
    "trip_distance_mi": 0.01,
    "fare_amount": 0.01,
}


def _freshness_floor(month: str, slack_days: int) -> str:
    """Newest-pickup gate: last day of month minus ``slack_days``."""
    import calendar
    from datetime import date, timedelta

    year, mm = month.split("-")
    last_day = calendar.monthrange(int(year), int(mm))[1]
    return (date(int(year), int(mm), last_day) - timedelta(days=slack_days)).isoformat()


def _raw_slice(raw_path: Path, cfg: MobilityConfig, color: str) -> pl.LazyFrame:
    mapping = _TRIP_COLUMNS[color]
    lf = pl.scan_parquet(raw_path).rename(mapping).select(list(mapping.values()))
    if cfg.max_rows_per_month is not None:
        lf = lf.head(cfg.max_rows_per_month)
    return lf


def _null_rates(raw: pl.DataFrame) -> dict[str, float]:
    n = max(1, raw.height)
    return {c: float(raw[c].null_count() / n) for c in raw.columns}


def _clean(raw: pl.LazyFrame, month: str) -> pl.LazyFrame:
    """Apply the ``Trip`` contract: range filters + critical-null drops.

    Pickups must fall inside the file's own month (plus a 1-day grace for
    UTC-ish edge records): TLC month files occasionally carry garbage dates
    (e.g. 2002), which would poison per-zone lag alignment downstream.
    """
    year, mm = month.split("-")
    start = pl.datetime(int(year), int(mm), 1)
    end = pl.datetime(int(year), int(mm) + 1, 1) if mm != "12" else pl.datetime(int(year) + 1, 1, 1)
    return (
        raw.filter(pl.col("pickup_ts") >= start, pl.col("pickup_ts") < end + pl.duration(days=1))
        .drop_nulls(["pickup_ts", "dropoff_ts", "pulocation_id", "dolocation_id"])
        .with_columns(
            passenger_count=pl.col("passenger_count").fill_null(0),
            duration_min=(pl.col("dropoff_ts") - pl.col("pickup_ts")).dt.total_minutes(),
        )
        .filter(
            pl.col("passenger_count").is_between(0, 8),
            pl.col("trip_distance_mi").is_between(0.0, 400.0 / MI_TO_KM, closed="both"),
            pl.col("fare_amount") >= 0.0,
            pl.col("duration_min") >= 0.0,
            pl.col("pulocation_id").is_between(1, 265),
            pl.col("dolocation_id").is_between(1, 265),
        )
        .with_columns(trip_distance_km=(pl.col("trip_distance_mi") * MI_TO_KM).round(4))
        .drop("trip_distance_mi")
    )


def validate_month(month: str, cfg: MobilityConfig, color: str = "yellow") -> DQReport:
    """Validate one month of one service color; persist cleaned parquet."""
    raw_dir = cfg.tlc_raw_dir if color == "yellow" else cfg.raw_dir / color
    raw_path = raw_dir / f"{color}_tripdata_{month}.parquet"
    if not raw_path.exists():
        raise FileNotFoundError(f"missing raw file {raw_path} — run `mobility download`")

    lf = _raw_slice(raw_path, cfg, color)
    raw = lf.collect(engine="streaming")
    n_raw = raw.height
    null_rates = _null_rates(raw)

    cleaned_lf = _clean(lf, month)
    cleaned = cleaned_lf.collect(engine="streaming")
    n_clean = cleaned.height
    row_floor = cfg.min_rows_per_month if color == "yellow" else cfg.green_min_rows_per_month

    report = DQReport(dataset=f"tlc_{color}_{month}", n_rows=n_clean)
    for col, ceiling in NULL_RATE_CEILINGS.items():
        report.check_null_rate(col, null_rates[col], ceiling)
    report.check_range(
        "fare_amount",
        cast(float, cleaned["fare_amount"].min()),
        cast(float, cleaned["fare_amount"].max()),
        0.0,
        float("inf"),
    )
    report.check_range(
        "trip_distance_km",
        cast(float, cleaned["trip_distance_km"].min()),
        cast(float, cleaned["trip_distance_km"].max()),
        0.0,
        400.0,
    )
    report.check_range(
        "passenger_count",
        cast(float, cleaned["passenger_count"].min()),
        cast(float, cleaned["passenger_count"].max()),
        0.0,
        8.0,
    )
    newest = str(cast(object, cleaned["pickup_ts"].max()))
    report.check_freshness(newest, _freshness_floor(month, cfg.freshness_slack_days))
    report.add(
        DQCheck(
            name="row_count_floor",
            column="*",
            passed=n_clean >= row_floor,
            metric=float(n_clean),
            threshold=float(row_floor),
            detail=f"cleaned rows {n_clean} >= floor {row_floor} "
            f"(raw {n_raw}, kept {n_clean / max(1, n_raw):.3%})",
        )
    )

    # Contract spot-check: one validated row must satisfy the Trip schema.
    _ = Trip(**cleaned.row(0, named=True))

    out_dir = cfg.validated_dir if color == "yellow" else cfg.validated_dir / color
    out_dir.mkdir(parents=True, exist_ok=True)
    cleaned.write_parquet(out_dir / f"{month}.parquet", compression="zstd")
    (cfg.reports_dir / "dq").mkdir(parents=True, exist_ok=True)
    (cfg.reports_dir / "dq" / f"{color}_{month}.json").write_text(report.model_dump_json(indent=2))
    logger.info(
        "%s %s: %d rows cleaned (%.1f%% of raw)",
        color,
        month,
        n_clean,
        100 * n_clean / max(1, n_raw),
    )
    return report


def validate_all(cfg: MobilityConfig | None = None) -> list[DQReport]:
    """Gate every configured month (yellow + green); raise on first failure."""
    cfg = cfg or get_config()
    reports: list[DQReport] = []
    for month in cfg.months:
        report = validate_month(month, cfg, color="yellow")
        report.raise_if_failed()
        reports.append(report)
    for month in cfg.green_months:
        report = validate_month(month, cfg, color="green")
        report.raise_if_failed()
        reports.append(report)
    logger.info("all %d files passed DQ gates", len(reports))
    persist_dq_summary(cfg, reports)
    return reports


def persist_dq_summary(cfg: MobilityConfig, reports: list[DQReport]) -> None:
    """Human-readable DQ digest: markdown + standalone HTML report."""
    from portfolio_eval.report import EvalReport

    cfg.reports_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Data-quality validation (TLC yellow, 2024)",
        "",
        f"{len(reports)} monthly files passed all gates. Detail per month:",
        "",
    ]
    for r in reports:
        failed = r.n_failed
        lines.append(
            f"- **{r.dataset}** — {r.n_rows:,} rows, "
            f"{len(r.checks)} checks, {'all passed' if failed == 0 else f'{failed} FAILED'}"
        )
        if failed:
            lines.extend(
                f"  - ❌ {c.name} ({c.column}): {c.detail}" for c in r.checks if not c.passed
            )
    md = "\n".join(lines) + "\n\n"
    md += "\n\n".join(f"## {r.dataset}\n\n{r.to_markdown()}" for r in reports)
    (cfg.reports_dir / "dq_validated.md").write_text(md)

    report = EvalReport(title="Data-quality validation (TLC yellow, 2024)")
    for r in reports:
        report.add_markdown_table(r.dataset, r.to_markdown())
    report.write(cfg.reports_dir / "dq_validated.html")


def load_dq_reports(cfg: MobilityConfig | None = None) -> list[DQReport]:
    """Read back the per-month DQ reports persisted during validation."""
    from portfolio_core.dq import DQReport

    cfg = cfg or get_config()
    out: list[DQReport] = []
    for path in sorted((cfg.reports_dir / "dq").glob("*.json")):
        out.append(DQReport.model_validate_json(path.read_text()))
    if not out:
        raise FileNotFoundError(
            f"no DQ reports in {cfg.reports_dir / 'dq'} — run `mobility validate`"
        )
    return out
