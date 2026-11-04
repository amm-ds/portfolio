"""Data layer for the champion re-derivation: pinned UCI ingest + time split.

Vendored from experiment 12 (workspace members are siblings, not deps — the
recipe is re-implemented here so this package stands alone; see DESIGN.md).
Only the pieces the serving study needs are carried over: the sha256-pinned
``hour.csv`` load, the canonical schema, and the time-based split windows.
12's full DQ gate report is a prepare-stage artifact of that pipeline; the
trust boundary here is the pinned-sha256 ingest itself.
"""

import hashlib
import io
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from portfolio_core.io import fetch, sha256_of

# Canonical hourly schema (identical to experiment 12).
NUMERIC_COLS = ["temp", "atemp", "hum", "windspeed"]
BINARY_COLS = ["holiday", "workingday"]
ORDINAL_COLS = ["season", "month", "hour", "weekday", "weathersit"]
TARGET_COL = "cnt"
TIMESTAMP_COL = "timestamp"
FRAME_COLS = [TIMESTAMP_COL, *ORDINAL_COLS, *BINARY_COLS, *NUMERIC_COLS, TARGET_COL]

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
    """Cut the final ``test_weeks`` as the scored-once test window, the
    ``val_weeks`` before them as validation; everything earlier is training."""
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

    Local paths are accepted so tests can point at a fixture zip without the
    network; the sha256 gate applies to both, exactly as in experiment 12.
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
    """Seeded synthetic twin of the canonical schema — the offline test path
    (tests never touch the network). Same generator contract as 12."""
    rng = np.random.default_rng(seed)
    n_rows = n_days * 24
    timestamps = pd.date_range("2024-01-01", periods=n_rows, freq="h")
    hour = timestamps.hour.to_numpy()
    weekday = timestamps.dayofweek.to_numpy()
    month = timestamps.month.to_numpy()
    day_of_year = timestamps.dayofyear.to_numpy()

    day_angle = 2 * np.pi * (day_of_year - 105) / 365.25
    temp = np.clip(0.42 + 0.28 * np.sin(day_angle) + rng.normal(0, 0.05, n_rows), 0.02, 0.98)
    hum = np.clip(0.62 - 0.45 * (temp - 0.4) + rng.normal(0, 0.10, n_rows), 0.05, 0.98)
    windspeed = np.clip(np.abs(rng.normal(0.18, 0.09, n_rows)), 0.0, 0.85)
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
    noise = np.exp(rng.normal(0, 0.16, n_rows))

    level = 620.0 * (1.0 + 0.10 * np.sin(day_angle))
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
            "workingday": 0,
            "temp": np.round(temp, 3),
            "atemp": np.round(np.clip(temp + rng.normal(0, 0.02, n_rows), 0, 1), 3),
            "hum": np.round(hum, 3),
            "windspeed": np.round(windspeed, 3),
            TARGET_COL: np.round(np.maximum(cnt, 0)).astype(int),
        }
    )[FRAME_COLS]
    frame["workingday"] = ((frame["weekday"] < 5) & (frame["holiday"] == 0)).astype(int)
    return frame


def frame_sha256(df: pd.DataFrame) -> str:
    """Checksum of the prepared frame — the dataset-identity line in the report."""
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
    return h.hexdigest()
