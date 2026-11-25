"""Read-only M5 calibration and deterministic item-level splits."""

import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import numpy as np
import polars as pl
import yaml  # type: ignore[import-untyped]

from dynamic_pricing.ledger import (
    append_ledger,
    canonical_sha256,
    file_sha256,
    write_json,
)


@dataclass(frozen=True)
class SeriesCalibration:
    series_id: str
    item_id: str
    base: float
    dow: tuple[float, ...]
    k: float
    p_ref: float


def load_params(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("params.yaml must contain a mapping")
    return cast(dict[str, Any], raw)


def verify_sources(params: dict[str, Any], repo_root: Path) -> None:
    """Refuse to read a source whose pinned digest has drifted."""
    sources = params["calibration"]["source_files"]
    for name in ("Y", "X", "S"):
        source = sources[name]
        path = repo_root / source["path"]
        observed = file_sha256(path)
        if observed != source["sha256"]:
            message = (
                f"SHA-256 mismatch for {source['path']}: "
                f"expected {source['sha256']}, got {observed}"
            )
            raise ValueError(message)


def load_m5(
    params: dict[str, Any], repo_root: Path
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Load only the pre-registered calendar window from verified parquet files."""
    verify_sources(params, repo_root)
    calibration = params["calibration"]
    start = date.fromisoformat(calibration["window_start"])
    end = date.fromisoformat(calibration["window_end"])
    sources = calibration["source_files"]
    y = (
        pl.read_parquet(repo_root / sources["Y"]["path"])
        .select("unique_id", "ds", "y")
        .with_columns(pl.col("unique_id").cast(pl.String), pl.col("ds").cast(pl.Date))
        .filter(pl.col("ds").is_between(start, end, closed="both"))
    )
    x = (
        pl.read_parquet(repo_root / sources["X"]["path"])
        .select("unique_id", "ds", "sell_price")
        .with_columns(pl.col("unique_id").cast(pl.String), pl.col("ds").cast(pl.Date))
        .filter(pl.col("ds").is_between(start, end, closed="both"))
    )
    s = pl.read_parquet(repo_root / sources["S"]["path"]).select(
        pl.col("unique_id").cast(pl.String), pl.col("item_id").cast(pl.String)
    )
    return y, x, s


def _series_calibration(
    series_id: str,
    item_id: str,
    y: pl.DataFrame,
    x: pl.DataFrame,
    end: date,
    recent_days: int,
    k_floor: float,
    k_cap: float,
) -> SeriesCalibration:
    recent_start = end - timedelta(days=recent_days - 1)
    recent_y = y.filter(pl.col("ds") >= recent_start)
    base = float(np.asarray(recent_y["y"], dtype=np.float64).mean())
    if base <= 0:
        raise ValueError(f"{series_id} has non-positive recent demand")

    dates = y["ds"].to_list()
    units = np.asarray(y["y"], dtype=np.float64)
    weekday_means = np.array(
        [float(units[[day.weekday() == weekday for day in dates]].mean()) for weekday in range(7)]
    )
    dow_values = weekday_means * (7.0 / float(weekday_means.sum()))
    expected = base * np.array([dow_values[day.weekday()] for day in dates])
    residuals = units - expected
    excess_variance = max(float(np.var(residuals, ddof=1)) - float(expected.mean()), 0.0)
    raw_k = (
        k_cap if excess_variance <= 1e-12 else float(np.mean(np.square(expected))) / excess_variance
    )

    recent_prices = [float(value) for value in x.filter(pl.col("ds") >= recent_start)["sell_price"]]
    price_counts = Counter(recent_prices)
    max_count = max(price_counts.values())
    p_ref = min(price for price, count in price_counts.items() if count == max_count)
    return SeriesCalibration(
        series_id=series_id,
        item_id=item_id,
        base=round(base, 8),
        dow=tuple(round(float(value), 8) for value in dow_values),
        k=round(float(np.clip(raw_k, k_floor, k_cap)), 8),
        p_ref=round(p_ref, 6),
    )


def _summaries(rows: list[SeriesCalibration]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for field in ("base", "k", "p_ref"):
        values = np.array([getattr(row, field) for row in rows], dtype=np.float64)
        percentiles = np.percentile(values, [0, 25, 50, 75, 100])
        result[field] = {
            label: round(float(value), 6)
            for label, value in zip(
                ("min", "p25", "median", "p75", "max"), percentiles, strict=True
            )
        }
    return result


def run_calibration(project_root: Path, repo_root: Path, params_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    params = load_params(params_path)
    y, x, s = load_m5(params, repo_root)
    calibration = params["calibration"]
    end = date.fromisoformat(calibration["window_end"])
    item_by_series = dict(s.iter_rows())
    y_groups = {
        str(frame["unique_id"][0]): frame
        for frame in y.partition_by("unique_id", maintain_order=True)
    }
    x_groups = {
        str(frame["unique_id"][0]): frame
        for frame in x.partition_by("unique_id", maintain_order=True)
    }
    if set(y_groups) != set(x_groups) or set(y_groups) != set(item_by_series):
        raise ValueError("Y, X, and S must contain identical series ids")

    rows = [
        _series_calibration(
            series_id,
            item_by_series[series_id],
            y_groups[series_id],
            x_groups[series_id],
            end,
            int(calibration["recent_days"]),
            float(calibration["k_floor"]),
            float(calibration["k_cap"]),
        )
        for series_id in sorted(y_groups)
    ]
    write_json(project_root / "data" / "calibration.json", [asdict(row) for row in rows])

    rng = np.random.default_rng(int(params["seed"]))
    shuffled_items = np.array(sorted(set(item_by_series.values())), dtype=object)
    rng.shuffle(shuffled_items)
    train_n = int(calibration["split_items"]["train"])
    val_n = int(calibration["split_items"]["val"])
    test_n = int(calibration["split_items"]["test"])
    item_ids = {
        "train": sorted(str(item) for item in shuffled_items[:train_n]),
        "val": sorted(str(item) for item in shuffled_items[train_n : train_n + val_n]),
        "test": sorted(
            str(item) for item in shuffled_items[train_n + val_n : train_n + val_n + test_n]
        ),
    }
    assigned = set().union(*(set(items) for items in item_ids.values()))
    series_ids = {
        split: sorted(series for series, item in item_by_series.items() if item in items)
        for split, items in item_ids.items()
    }
    split_payload: dict[str, Any] = {
        "seed": int(params["seed"]),
        "calibration_window": {
            "start": calibration["window_start"],
            "end": calibration["window_end"],
        },
        "item_ids": item_ids,
        "series_ids": series_ids,
        "unassigned_item_ids": sorted(set(item_by_series.values()) - assigned),
        "sealed_evaluation": {},
    }
    split_payload["content_sha256"] = canonical_sha256(split_payload)
    splits_path = project_root / "data" / "splits.json"
    write_json(splits_path, split_payload)

    summary: dict[str, Any] = {
        "n_series": len(rows),
        "n_source_items": len(set(item_by_series.values())),
        "series_by_split": {split: len(ids) for split, ids in series_ids.items()},
        "distributions": _summaries(rows),
    }
    append_ledger(
        project_root,
        step="E2-2",
        change="Calibrated M5 demand, weekday profiles, NB dispersion, and reference prices",
        split="calibration",
        config_sha256=canonical_sha256(params),
        set_sha256=file_sha256(splits_path),
        n=len(rows),
        headline=summary,
        wall_clock_s=time.perf_counter() - started,
        report_path="projects/15-dynamic-pricing-rl/data/calibration.json",
        decision="calibration complete; no policy evaluated",
    )
    return summary
