"""Scalability study: seeded synthetic tracks at 1M / 3M / 10M rows.

The five most discriminating tasks (CSV read, group-by, join, window, filter)
run on every engine across three seeded synthetic sizes, producing the
time-vs-size dataset committed in ``metrics.json`` under ``scalability``.
Datasets are materialized under ``data/scalability/n<N>/`` (gitignored,
regenerable, byte-stable for a given ``(seed, n)``); the lean layout carries
parquet + CSV + zones only, so the bundles set ``with_partitioned=False``.

Protocol (recorded in ``evaluation_metadata.json``): same in-process warm
timing as the main track but with ``scalability_repeats`` (fewer repeats, no
fresh-process probes) — the determinism gate still compares every repeat's
canonical rows, and sqlite still pays its documented per-cell conversion.
"""

import math
import time
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger

from data_engineering.config import DEConfig
from data_engineering.data import DataBundle
from data_engineering.harness import CellResult, run_benchmark
from data_engineering.synthetic import (
    synthetic_checksum,
    trips_frame,
    write_dataset_contract,
    zones_frame,
)

logger = get_logger(__name__)

#: The 4-5 tasks that discriminate engines most, per the brief.
SCALABILITY_TASKS: tuple[str, ...] = ("read_csv", "groupby", "join", "window", "filter")


def scalability_dir(cfg: DEConfig, n: int) -> Path:
    return cfg.data_dir / "scalability" / f"n{n}"


def materialize_scalability_bundle(cfg: DEConfig, n: int) -> DataBundle:
    """Build (or reuse, checksum-verified) the seeded synthetic bundle at ``n`` rows."""
    out_dir = scalability_dir(cfg, n)
    checksum = synthetic_checksum(cfg.seed, n)
    prepared = out_dir / "prepared"
    contract = out_dir / "dataset_contract.json"
    reusable = (
        contract.exists()
        and (prepared / "trips.parquet").exists()
        and (prepared / "trips.csv").exists()
        and (out_dir / "raw" / "taxi_zone_lookup.csv").exists()
    )
    if not reusable:
        logger.info("scalability: generating %s rows (seed %d)", f"{n:,}", cfg.seed)
        trips = trips_frame(cfg.seed, n)
        (out_dir / "raw").mkdir(parents=True, exist_ok=True)
        prepared.mkdir(parents=True, exist_ok=True)
        trips.write_parquet(prepared / "trips.parquet", compression="snappy")
        trips.write_csv(prepared / "trips.csv")
        zones_frame().write_csv(out_dir / "raw" / "taxi_zone_lookup.csv")
        write_dataset_contract(
            out_dir,
            source=f"synthetic://data_engineering.trips_frame(seed={cfg.seed}, n={n})",
            n_rows=len(trips),
            checksum=checksum,
            license_text="Synthetic — generated locally by a seeded generator, no license",
        )
    else:
        # Loud staleness check: the cached layout must still be the seeded one.
        import json

        stored = json.loads(contract.read_text()).get("checksum_sha256", "")
        if stored != checksum:
            raise ValueError(
                f"scalability cache at {out_dir} does not match the seeded generator "
                f"(stored {stored[:12]}…, generator {checksum[:12]}…) — clear the directory."
            )
        logger.info("scalability: reusing cached %s-row layout", f"{n:,}")
    bundle = DataBundle(
        data_dir=out_dir,
        n_rows=n,
        checksum_sha256=checksum,
        source=f"synthetic://trips_frame?seed={cfg.seed}&n={n}",
        license="Synthetic (seeded generator)",
        notes=(
            f"Scalability track: seeded synthetic at {n:,} rows; "
            "lean layout (parquet + CSV + zones, no partitioned dir)."
        ),
        with_partitioned=False,
    )
    bundle.validate()
    return bundle


def run_scalability(
    cfg: DEConfig,
    *,
    engines: list[str] | None = None,
    task_names: list[str] | None = None,
    sizes: list[int] | None = None,
    repeats: int | None = None,
) -> tuple[list[tuple[int, list[CellResult]]], float]:
    """Measure every task x engine cell at every requested size.

    Returns ``[(n, cells), ...]`` plus the wall-clock seconds of the whole
    study. Probes are off by design (the main track owns RSS/cold numbers).
    """
    sizes = sizes or list(cfg.scalability_rows)
    repeats = cfg.scalability_repeats if repeats is None else repeats
    tasks = task_names or list(SCALABILITY_TASKS)
    t0 = time.perf_counter()
    runs: list[tuple[int, list[CellResult]]] = []
    for n in sizes:
        bundle = materialize_scalability_bundle(cfg, n)
        logger.info("scalability: %s rows — %d tasks", f"{n:,}", len(tasks))
        cells = run_benchmark(
            bundle,
            cfg,
            engines=engines,
            task_names=tasks,
            repeats=repeats,
            probes=0,
        )
        runs.append((n, cells))
    return runs, time.perf_counter() - t0


def loglog_slope(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope of log10(y) over log10(x) — the growth exponent."""
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("need >= 2 paired points for a slope")
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        raise ValueError("degenerate x values for a slope")
    return num / den


def build_scalability_metrics(runs: list[tuple[int, list[CellResult]]]) -> dict[str, Any]:
    """Assemble the metrics.json ``scalability`` block from measured runs."""
    sizes = [n for n, _ in runs]
    tasks_block: dict[str, Any] = {}
    for task_name in SCALABILITY_TASKS:
        engines_block: dict[str, Any] = {}
        for engine in _engines_in(runs, task_name):
            by_size: dict[str, Any] = {}
            medians: list[float] = []
            for n, cells in runs:
                cell = next((c for c in cells if c.task == task_name and c.engine == engine), None)
                if cell is None:
                    continue  # honest n/a cell (sqlite write task is not in this set)
                key = str(n)
                by_size[key] = {
                    "time_median_s": cell.time_median_s,
                    "time_all_s": cell.times,
                }
                medians.append(cell.time_median_s)
            if not by_size:
                continue
            log_x = [round(_log10(n), 6) for n in sizes]
            log_y = [round(_log10(t), 6) for t in medians]
            engines_block[engine] = {
                "by_size": by_size,
                "loglog_slope": round(loglog_slope(log_x, log_y), 3),
            }
        if engines_block:
            tasks_block[task_name] = {
                "engines": engines_block,
                "fastest_engine_by_size": _fastest_by_size(runs, task_name, engines_block),
            }
    return {"sizes": sizes, "tasks": tasks_block}


def _fastest_by_size(
    runs: list[tuple[int, list[CellResult]]], task_name: str, engines_block: dict[str, Any]
) -> dict[str, str]:
    """Engine with the smallest median per size, among the measured ones."""
    out: dict[str, str] = {}
    for n, cells in runs:
        measured = [
            (engines_block[c.engine]["by_size"][str(n)]["time_median_s"], c.engine)
            for c in cells
            if c.task == task_name and c.engine in engines_block
        ]
        if measured:
            out[str(n)] = min(measured)[1]
    return out


def _engines_in(runs: list[tuple[int, list[CellResult]]], task_name: str) -> list[str]:
    seen: list[str] = []
    for _, cells in runs:
        for cell in cells:
            if cell.task == task_name and cell.engine not in seen:
                seen.append(cell.engine)
    return seen


def _log10(value: float) -> float:
    return math.log10(value)


def scalability_protocol_statement(cfg: DEConfig) -> str:
    return (
        "Scalability study: seeded synthetic tracks at "
        f"{', '.join(f'{n:,}' for n in cfg.scalability_rows)} rows over the "
        f"{len(SCALABILITY_TASKS)} most discriminating tasks ({', '.join(SCALABILITY_TASKS)}); "
        f"median of {cfg.scalability_repeats} warm in-process repeats, no fresh-process "
        "probes; determinism gate between repeats; sqlite converts the files into its "
        "in-memory database inside each timed cell (the documented conversion tax)."
    )
