"""Measurement harness: warm in-process repeats + isolated fresh-process probes.

Protocol (recorded in ``evaluation_metadata.json``):

- **Warm wall time** — ``repeats`` in-process runs per task-by-engine cell; the
  headline number is the median. Timed repeats run *without* tracemalloc: the
  tracer inflates allocation-heavy cells (a bulk row-bind ingest allocates
  millions of Python objects), so tracing inside the timed region would
  distort exactly the wall times being measured.
- **Python-side allocation peak** — one dedicated untimed repeat per cell runs
  under ``tracemalloc`` (full-protocol runs only; skipped with ``--no-probes``
  and on the scalability track, where it would add minutes for a diagnostic).
- **Isolated probes** — each cell also runs once (or ``memory_probes`` times)
  in a fresh subprocess (``python -m data_engineering.cold``). A new process
  owns its own memory, so its ``ru_maxrss`` high-water mark is the cell's true
  peak RSS — ``resource`` deltas inside one long-lived process would
  under-report every cell after the first high. For IO tasks the probe run is
  also the **cold read** number (fresh interpreter, cold library state; the
  OS page cache is not dropped — not portable — which the limits note).
- **Determinism gate** — every repeat's (and the traced pass's and the
  probe's) canonical result fingerprint must be identical; a mismatch fails
  the cell loudly.
"""

import gc
import json
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from portfolio_core.logging import get_logger

from data_engineering.config import DEConfig
from data_engineering.data import DataBundle, rows_equal
from data_engineering.engines import adapter_names, build_adapter
from data_engineering.tasks import TASKS, Task

logger = get_logger(__name__)


@dataclass
class CellResult:
    """One task x engine measurement."""

    task: str
    engine: str
    category: str
    times: list[float]
    tracemalloc_peaks_mb: list[float]  # dedicated untimed pass (empty = not run)
    cold_s: float | None = None
    peak_rss_mb: float | None = None
    result_rows: list[dict[str, Any]] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def time_median_s(self) -> float:
        return statistics.median(self.times)


def run_cell(
    task: Task,
    engine: str,
    bundle: DataBundle,
    workdir: Path,
    *,
    repeats: int,
    probes: int,
    traced: bool | None = None,
) -> CellResult:
    """Measure one task-by-engine cell (warm repeats + optional fresh-process probes).

    ``traced=None`` ties the dedicated tracemalloc pass to full-protocol runs
    (``probes > 0``): it is a diagnostic, never part of the wall-time median.
    """
    adapter = build_adapter(engine)
    impl = task.impls[engine]
    cell_dir = workdir / task.name
    cell_dir.mkdir(parents=True, exist_ok=True)
    traced = (probes > 0) if traced is None else traced

    times: list[float] = []
    traces: list[float] = []
    rows: list[dict[str, Any]] = []
    detail: dict[str, Any] = {}

    def _run_once() -> tuple[Any, float, float | None]:
        """One repeat: wall time (+ tracemalloc peak when tracing this run)."""
        gc.collect()
        if traced_now[0]:
            tracemalloc.start()
        t0 = time.perf_counter()
        result = impl(adapter, bundle, cell_dir)
        dt = time.perf_counter() - t0
        peak: float | None = None
        if traced_now[0]:
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        return result, dt, peak

    # Timed repeats run untraced; the traced pass below owns tracemalloc.
    traced_now = [False]
    for repeat in range(repeats):
        result, dt, _ = _run_once()
        times.append(dt)
        # Determinism gate: identical canonical rows across repeats. Ints,
        # strings and dates must match exactly; floats compare with
        # rows_equal's 1e-5 band — a parallel engine (DuckDB, Polars)
        # legitimately reorders float summation between runs, and a sum can
        # sit within an ulp of a rounding cliff (one display bin). Structural
        # drift (counts, keys, row order) still fails loudly.
        if not rows:
            rows, detail = result.rows, result.detail
        elif not rows_equal(rows, result.rows):
            raise RuntimeError(
                f"non-deterministic result: {task.name}/{engine} repeat {repeat} "
                f"differs from repeat 0 beyond float tolerance"
            )

    # Dedicated tracemalloc pass: the Python-side allocation peak, untimed.
    if traced:
        traced_now[0] = True
        result, _, peak = _run_once()
        traced_now[0] = False
        if peak is None:  # pragma: no cover - defensive; tracing was just on
            raise RuntimeError(f"tracemalloc pass did not trace: {task.name}/{engine}")
        traces.append(round(peak / 1e6, 3))
        if not rows_equal(rows, result.rows):
            raise RuntimeError(f"traced pass result mismatch: {task.name}/{engine}")

    cold_s: float | None = None
    peak_rss_mb: float | None = None
    if probes > 0:
        probe_times: list[float] = []
        probe_peaks: list[float] = []
        for _ in range(probes):
            probe = _probe_subprocess(bundle, engine, task.name)
            probe_times.append(probe["time_s"])
            probe_peaks.append(probe["peak_rss_mb"])
            if not rows_equal(probe["rows"], rows):
                raise RuntimeError(f"probe/in-process result mismatch: {task.name}/{engine}")
        peak_rss_mb = round(max(probe_peaks), 1)
        if task.cold_measurable:
            cold_s = round(probe_times[0], 6)

    return CellResult(
        task=task.name,
        engine=engine,
        category=task.category,
        times=[round(t, 6) for t in times],
        tracemalloc_peaks_mb=traces,
        cold_s=cold_s,
        peak_rss_mb=peak_rss_mb,
        result_rows=rows,
        detail=detail,
    )


def _probe_subprocess(bundle: DataBundle, engine: str, task: str) -> dict[str, Any]:
    """One fresh-process run; returns its wall time, peak RSS and result hash."""
    with tempfile.TemporaryDirectory(prefix="de11-probe-") as tmp:
        bundle_json = Path(tmp) / "bundle.json"
        bundle_json.write_text(json.dumps(bundle.to_dict()))
        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "data_engineering.cold", str(bundle_json), engine, task],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    if proc.returncode != 0:
        raise RuntimeError(
            f"cold probe failed for {task}/{engine} (exit {proc.returncode}): {proc.stderr.strip()}"
        )
    probe: dict[str, Any] = json.loads(proc.stdout.strip().splitlines()[-1])
    return probe


def run_benchmark(
    bundle: DataBundle,
    cfg: DEConfig,
    *,
    engines: list[str] | None = None,
    task_names: list[str] | None = None,
    repeats: int | None = None,
    probes: int | None = None,
    workdir: Path | None = None,
) -> list[CellResult]:
    """Run every requested task x engine cell and return the measurements."""
    bundle.validate()
    engines = engines or adapter_names()
    selected = task_names or [t.name for t in TASKS]
    task_list = [t for t in TASKS if t.name in selected]
    repeats = cfg.repeats if repeats is None else repeats
    probes = cfg.memory_probes if probes is None else probes

    scratch = workdir or Path(tempfile.mkdtemp(prefix="de11-run-"))
    scratch.mkdir(parents=True, exist_ok=True)
    cells: list[CellResult] = []
    for task in task_list:
        for engine in engines:
            if engine not in task.impls:
                logger.info("cell skipped (n/a): %s x %s", task.name, engine)
                continue  # honest n/a pair (see tasks.NA_IMPLS), not a failure
            logger.info(
                "cell start: %s x %s (%d repeats, %d probes)",
                task.name,
                engine,
                repeats,
                probes,
            )
            cell = run_cell(
                task,
                engine,
                bundle,
                scratch,
                repeats=repeats,
                probes=probes,
            )
            cells.append(cell)
            logger.info(
                "cell done: %s x %s — median %.3fs%s",
                task.name,
                engine,
                cell.time_median_s,
                f", cold {cell.cold_s:.3f}s" if cell.cold_s is not None else "",
            )
    return cells
