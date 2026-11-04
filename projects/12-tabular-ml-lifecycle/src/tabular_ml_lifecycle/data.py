"""Data layer: UCI Bike Sharing ingest, synthetic CI twin, DQ gates, time split.

Dataset card (docs/data-registry/bike-sharing.md) rules enforced here:
``hour.csv`` only, sha256-pinned zip, ``casual``/``registered``/``instant``/
``dteday``/``yr`` dropped (casual+registered sum to the target — leakage), and
the split is time-based: the final ``test_weeks`` are scored once, the
``val_weeks`` before them select and early-stop models.
"""

import hashlib
import io
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from portfolio_core.dq import DQCheck, DQReport
from portfolio_core.io import fetch, sha256_of
from portfolio_core.schemas import DatasetContract

# Canonical hourly schema (UCI names kept; instant/dteday/yr/casual/registered dropped).
NUMERIC_COLS = ["temp", "atemp", "hum", "windspeed"]
BINARY_COLS = ["holiday", "workingday"]
ORDINAL_COLS = ["season", "month", "hour", "weekday", "weathersit"]
TARGET_COL = "cnt"
TIMESTAMP_COL = "timestamp"
FRAME_COLS = [TIMESTAMP_COL, *ORDINAL_COLS, *BINARY_COLS, *NUMERIC_COLS, TARGET_COL]

SEASON_LABELS = {1: "spring", 2: "summer", 3: "fall", 4: "winter"}

UCI_COLUMNS = {
    "dteday": TIMESTAMP_COL,
    "season": "season",
    "mnth": "month",
    "hr": "hour",
    "holiday": "holiday",
    "weekday": "weekday",
    "workingday": "workingday",
    "weathersit": "weathersit",
    "temp": "temp",
    "atemp": "atemp",
    "hum": "hum",
    "windspeed": "windspeed",
    "cnt": TARGET_COL,
}


@dataclass(frozen=True)
class SplitWindows:
    """Time-ordered, non-overlapping train/validation/test row windows."""

    train: slice
    val: slice
    test: slice
    n_train: int
    n_val: int
    n_test: int


def split_windows(n_rows: int, val_weeks: int, test_weeks: int) -> SplitWindows:
    """Cut the final ``test_weeks`` (24*7 rows per week) as the scored-once
    test window, the ``val_weeks`` before them as validation; everything earlier
    is training. Windows are contiguous row blocks, strictly time-ordered and
    non-overlapping — whole calendar weeks on a complete grid (synthetic twin),
    approximately 8 weeks of wall-clock on the real series (which has small
    outage gaps; see the DQ gate).
    """
    rows_per_week = 24 * 7
    n_test = test_weeks * rows_per_week
    n_val = val_weeks * rows_per_week
    if n_rows <= n_test + n_val + rows_per_week:
        raise ValueError(
            f"series too short for {val_weeks}+{test_weeks} week windows: {n_rows} rows"
        )
    train_end = n_rows - n_val - n_test
    val_end = n_rows - n_test
    return SplitWindows(
        train=slice(0, train_end),
        val=slice(train_end, val_end),
        test=slice(val_end, n_rows),
        n_train=train_end,
        n_val=n_val,
        n_test=n_test,
    )


def load_uci_frame(source: str, sha256: str) -> pd.DataFrame:
    """Fetch the pinned zip, extract ``hour.csv``, map to the canonical schema.

    Local paths and file:// URLs are accepted so tests can point at a fixture
    zip without the network; the sha256 gate applies to both.
    """
    if (
        source.startswith("http://")
        or source.startswith("https://")
        or source.startswith("file://")
    ):
        dest = Path(tempfile.gettempdir()) / "bike-sharing-dataset.zip"
        fetch(source, dest, expected_sha256=sha256)
        zip_path: Path = dest
    else:
        zip_path = Path(source)
        if sha256_of(zip_path) != sha256.lower():
            raise ValueError(
                f"checksum mismatch for {zip_path}: expected {sha256}, got {sha256_of(zip_path)}"
            )
    with zipfile.ZipFile(zip_path) as zf, zf.open("hour.csv") as fh:
        raw = pd.read_csv(io.TextIOWrapper(fh, encoding="utf-8"))
    missing = [c for c in UCI_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"hour.csv is missing required columns: {', '.join(missing)}")
    df = raw.rename(columns=UCI_COLUMNS)[FRAME_COLS].copy()
    df[TIMESTAMP_COL] = pd.to_datetime(df[TIMESTAMP_COL]) + pd.to_timedelta(df["hour"], unit="h")
    return df.sort_values(TIMESTAMP_COL).reset_index(drop=True)


def make_synthetic_frame(seed: int, n_days: int) -> pd.DataFrame:
    """Seeded synthetic twin with the canonical schema (CI path, no network).

    make_regression-flavored: an hour-of-day commuter profile, a weekday/
    weekend amplitude, a weather response with a temperature sweet spot and
    autocorrelated noise, rendered as non-negative integer counts. Same
    schema and loader contract as the UCI track, so every downstream gate
    exercises the identical code path.
    """
    rng = np.random.default_rng(seed)
    n_rows = n_days * 24
    timestamps = pd.date_range("2024-01-01", periods=n_rows, freq="h")
    hour = timestamps.hour.to_numpy()
    weekday = timestamps.dayofweek.to_numpy()
    month = timestamps.month.to_numpy()
    day_of_year = timestamps.dayofyear.to_numpy()

    day_angle = 2 * np.pi * (day_of_year - 105) / 365.25
    temp = 0.42 + 0.28 * np.sin(day_angle) + rng.normal(0, 0.05, n_rows)
    temp = np.clip(temp, 0.02, 0.98)
    hum = np.clip(0.62 - 0.45 * (temp - 0.4) + rng.normal(0, 0.10, n_rows), 0.05, 0.98)
    windspeed = np.clip(np.abs(rng.normal(0.18, 0.09, n_rows)), 0.0, 0.85)
    # Weather situation: worse as humidity rises, jittered into 1..4.
    weathersit = 1 + (hum > 0.55).astype(int) + (hum > 0.75).astype(int)
    weathersit = np.clip(weathersit + (rng.random(n_rows) < 0.08).astype(int), 1, 4)

    morning_peak = np.exp(-0.5 * ((hour - 8) / 2.0) ** 2)
    evening_peak = np.exp(-0.5 * ((hour - 17.5) / 2.5) ** 2)
    midday = np.exp(-0.5 * ((hour - 13) / 5.0) ** 2)
    is_weekend = (weekday >= 5).astype(float)
    hour_shape = (1 - is_weekend) * (
        0.25 + 1.05 * morning_peak + 1.25 * evening_peak + 0.45 * midday
    )
    hour_shape += is_weekend * (0.55 + 0.85 * midday)

    season = np.where(
        np.isin(month, [12, 1, 2]),
        4,
        np.where(np.isin(month, [3, 4, 5]), 1, np.where(np.isin(month, [6, 7, 8]), 2, 3)),
    )
    season_factor = np.select([season == s for s in (1, 2, 3, 4)], [0.85, 0.95, 1.0, 0.75])
    weather_factor = 1.0 - 0.10 * (weathersit - 1) - 0.35 * np.maximum(hum - 0.7, 0)
    weather_factor += 0.55 * np.exp(-0.5 * ((temp - 0.62) / 0.16) ** 2)
    noise = np.exp(rng.normal(0, 0.16, n_rows))  # multiplicative, like count data

    level = 620.0 * (1.0 + 0.10 * np.sin(day_angle))  # mild year-over-year-style drift
    cnt = level * season_factor * hour_shape * np.clip(weather_factor, 0.15, 1.6) * noise
    frame = pd.DataFrame(
        {
            TIMESTAMP_COL: timestamps,
            "season": season.astype(int),
            "month": month.astype(int),
            "hour": hour.astype(int),
            "weekday": weekday.astype(int),
            "weathersit": weathersit.astype(int),
            "holiday": (rng.random(n_days) < 0.02).astype(int).repeat(24),
            "workingday": 0,  # filled below: weekday & ~holiday
            "temp": np.round(temp, 3),
            "atemp": np.round(np.clip(temp + rng.normal(0, 0.02, n_rows), 0, 1), 3),
            "hum": np.round(hum, 3),
            "windspeed": np.round(windspeed, 3),
            TARGET_COL: np.round(np.maximum(cnt, 0)).astype(int),
        }
    )[FRAME_COLS]
    frame["workingday"] = ((frame["weekday"] < 5) & (frame["holiday"] == 0)).astype(int)
    return frame


def run_dq_gates(df: pd.DataFrame, dataset: str = "bike_sharing_hourly") -> DQReport:
    """Data-quality gates every source (UCI or synthetic) passes before modeling."""
    report = DQReport(dataset=dataset, n_rows=len(df))
    for col in FRAME_COLS:
        if col != TIMESTAMP_COL:
            report.check_null_rate(col, float(df[col].isna().mean()), 0.0)
    ranges: dict[str, tuple[float, float]] = {
        "season": (1, 4),
        "month": (1, 12),
        "hour": (0, 23),
        "weekday": (0, 6),
        "weathersit": (1, 4),
        "holiday": (0, 1),
        "workingday": (0, 1),
        "temp": (0.0, 1.0),
        "atemp": (0.0, 1.0),
        "hum": (0.0, 1.0),
        "windspeed": (0.0, 1.0),
    }
    for col, (lo, hi) in ranges.items():
        series = df[col].dropna()
        report.check_range(
            col, float(cast(float, series.min())), float(cast(float, series.max())), lo, hi
        )
    report.check_range(
        TARGET_COL, float(df[TARGET_COL].min()), float(df[TARGET_COL].max()), 0.0, 1e7
    )
    ts = pd.to_datetime(df[TIMESTAMP_COL])
    report.add(_gap_check(ts))
    report.add(_duplicate_check(ts))
    report.raise_if_failed()
    return report


def _gap_check(ts: pd.Series) -> DQCheck:
    """Hourly-grid completeness within a budget: the UCI series has 165 missing
    hours (the January 2011 outage pattern, ~1% of rows), so lags and the
    seasonal-naive floor are positional over the observed sequence — the gate
    bounds the missing fraction instead of demanding a perfect grid.
    """
    diffs = ts.diff().dropna().dt.total_seconds()
    gaps = int((diffs != 3600).sum())
    budget = max(24, int(0.02 * len(ts)))
    return DQCheck(
        name="hourly_grid",
        column=TIMESTAMP_COL,
        passed=gaps <= budget,
        metric=float(gaps),
        threshold=float(budget),
        detail=(
            f"{gaps} non-1h steps vs budget {budget} ({len(ts)} rows); "
            "lags are positional over the observed sequence"
        ),
    )


def _duplicate_check(ts: pd.Series) -> DQCheck:
    dups = int(ts.duplicated().sum())
    return DQCheck(
        name="unique_timestamps",
        column=TIMESTAMP_COL,
        passed=dups == 0,
        metric=float(dups),
        threshold=0.0,
        detail=f"{dups} duplicate timestamps (expect 0)",
    )


def dataset_contract_for(
    df: pd.DataFrame, name: str, source: str, license_: str
) -> DatasetContract:
    """Checksum the prepared frame into the platform DatasetContract."""
    return DatasetContract(
        name=name,
        source=source,
        license=license_,
        snapshot_date=date.today(),
        checksum_sha256=_frame_sha256(df),
        n_rows=len(df),
    )


def _frame_sha256(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
    return h.hexdigest()
