"""Metrics schema: per task-by-engine numbers, speedups, and evaluation metadata.

``metrics.json`` is the committed record (consumed by the showcase API, the
figures, the report and the tests); ``evaluation_metadata.json`` carries the
protocol, runtime versions and hardware context so the numbers can be read
the way 08's benchmark record reads them — one shared machine, timing noise
included, everything else pinned.
"""

import json
import math
import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

from data_engineering.config import DEConfig
from data_engineering.data import DataBundle
from data_engineering.engines import engine_versions
from data_engineering.harness import CellResult
from data_engineering.tasks import TASKS

PROTOCOL_NAME = "engine_benchmark_v1"
ENGINE_ORDER = ("pandas", "polars", "duckdb", "sqlite")


@dataclass(frozen=True)
class BenchmarkRecord:
    """The two committed artifacts of one benchmark run."""

    metrics: dict[str, Any]
    metadata: dict[str, Any]


def build_metrics(
    cells: list[CellResult],
    cfg: DEConfig,
    bundle: DataBundle,
    *,
    scalability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble metrics.json content from measured cells."""
    by_task: dict[str, dict[str, CellResult]] = {}
    for cell in cells:
        by_task.setdefault(cell.task, {})[cell.engine] = cell

    tasks_block: dict[str, Any] = {}
    for task in TASKS:
        if task.name not in by_task:
            continue  # task-restricted run (CLI --task): only measured cells report
        engines_block: dict[str, Any] = {}
        for engine in ENGINE_ORDER:
            res = by_task.get(task.name, {}).get(engine)
            if res is None:
                continue  # honest n/a cell (tasks.NA_IMPLS), reported as absent
            engines_block[engine] = {
                "time_median_s": res.time_median_s,
                "time_all_s": res.times,
                "cold_s": res.cold_s,
                "peak_rss_mb": res.peak_rss_mb,
                "tracemalloc_peak_mb": median(res.tracemalloc_peaks_mb)
                if res.tracemalloc_peaks_mb
                else None,
                "result": res.result_rows,
                "detail": res.detail,
            }
        for engine, block in engines_block.items():
            base = by_task[task.name]["pandas"].time_median_s
            block["speedup_vs_pandas"] = (
                round(base / block["time_median_s"], 3) if engine != "pandas" else 1.0
            )
        sqlite_cell = by_task[task.name].get("sqlite")
        if sqlite_cell is not None:
            for engine, block in engines_block.items():
                block["speedup_vs_sqlite"] = (
                    round(sqlite_cell.time_median_s / block["time_median_s"], 3)
                    if engine != "sqlite"
                    else 1.0
                )
        tasks_block[task.name] = {
            "category": task.category,
            "description": task.description,
            "engines": engines_block,
        }

    summary: dict[str, Any] = {"by_engine": {}, "fastest_engine_by_task": {}}
    for engine in ENGINE_ORDER:
        engine_cells = [by_task[t.name][engine] for t in TASKS if engine in by_task.get(t.name, {})]
        if not engine_cells:
            continue
        speedups = [
            by_task[t.name]["pandas"].time_median_s / by_task[t.name][engine].time_median_s
            for t in TASKS
            if engine in by_task.get(t.name, {}) and "pandas" in by_task.get(t.name, {})
        ]
        summary["by_engine"][engine] = {
            "total_time_s": round(sum(c.time_median_s for c in engine_cells), 6),
            "geomean_speedup_vs_pandas": round(
                math.exp(sum(math.log(s) for s in speedups) / len(speedups)), 3
            )
            if speedups
            else None,
        }
    for task in TASKS:
        engines = by_task.get(task.name, {})
        if engines:
            summary["fastest_engine_by_task"][task.name] = min(
                engines, key=lambda e: engines[e].time_median_s
            )

    return {
        "protocol": PROTOCOL_NAME,
        "dataset": {
            "source": bundle.source,
            "n_rows": bundle.n_rows,
            "checksum_sha256": bundle.checksum_sha256,
        },
        "engines": {name: _engine_version(name) for name in ENGINE_ORDER},
        "tasks": tasks_block,
        "summary": summary,
        **({"scalability": scalability} if scalability else {}),
    }


def _engine_version(engine: str) -> dict[str, str]:
    versions = engine_versions()
    if engine == "pandas":
        return {"version": versions["pandas"], "pyarrow": versions["pandas_pyarrow"]}
    return {"version": versions[engine]}


def build_metadata(
    cfg: DEConfig,
    bundle: DataBundle,
    *,
    track: str,
    runtime_s: float,
    cells: list[CellResult],
    scalability: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble evaluation_metadata.json (protocol, versions, hardware)."""
    versions = engine_versions()
    meta: dict[str, Any] = {
        "protocol": PROTOCOL_NAME,
        "protocol_statement": (
            "Warm wall time: median of in-process repeats (see params.yaml repeats), "
            "timed WITHOUT tracemalloc so the tracer never inflates the measured region; "
            "cold reads: one fresh subprocess per IO cell (OS page cache not dropped); "
            "peak RSS: fresh-subprocess ru_maxrss high-water; "
            "tracemalloc peak: one dedicated untimed repeat per cell under tracemalloc "
            "(full-protocol runs only; the diagnostic pass is never part of the wall median); "
            "determinism gate: every repeat, traced pass and probe returns identical canonical "
            "rows (ints/strings/dates exact; floats within 1e-5 relative of the "
            "6-significant-digit canonical form — parallel summation order). "
            "sqlite3 (stdlib) answers each task by loading the prepared file into an "
            "in-memory database via pandas inside the timed cell — the load is the "
            "documented conversion tax — and has no write_parquet (no stdlib parquet "
            "writer), so that cell is n/a."
        ),
        "track": track,
        "seed": cfg.seed,
        "repeats": cfg.repeats,
        "memory_probes": cfg.memory_probes,
        "runtime_s": round(runtime_s, 3),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "engines": versions,
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": __import__("os").cpu_count(),
        },
        "dataset": {
            "source": bundle.source,
            "license": bundle.license,
            "n_rows": bundle.n_rows,
            "checksum_sha256": bundle.checksum_sha256,
            "notes": bundle.notes,
            "prepared_bytes": _prepared_bytes(bundle),
        },
        "timing_note": (
            "Wall-clock on one shared, load-sensitive machine: the ordering and "
            "rough magnitude are stable; exact seconds are context, not a stable "
            "benchmark (same convention as 08)."
        ),
        "determinism": {
            f"{c.task}/{c.engine}": json.dumps(c.result_rows, sort_keys=True, default=str)
            for c in cells
        },
    }
    if scalability is not None:
        meta["scalability"] = scalability
    return meta


def _prepared_bytes(bundle: DataBundle) -> dict[str, int]:
    def _size(path: Path) -> int:
        return path.stat().st_size if path.exists() else -1

    parts = list(bundle.partitioned_dir.glob("day=*/part-0.parquet"))
    return {
        "trips_parquet": _size(bundle.trips_parquet),
        "trips_csv": _size(bundle.trips_csv),
        "zones_csv": _size(bundle.zones_csv),
        "partitioned_parquet_total": sum(p.stat().st_size for p in parts),
        "partitioned_files": len(parts),
    }


def write_record(record: BenchmarkRecord, reports_dir: Path) -> None:
    """Commit both artifacts next to the figures."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "metrics.json").write_text(json.dumps(record.metrics, indent=2) + "\n")
    (reports_dir / "evaluation_metadata.json").write_text(
        json.dumps(record.metadata, indent=2) + "\n"
    )


def load_metrics(reports_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((reports_dir / "metrics.json").read_text())
    return data
