"""Async load-driver against the running service — experiment 08's discipline.

The harness starts the real service as a subprocess for each backend
(native, onnx), waits for /ready, excludes a warm-up batch from every cell,
and reports the median of repeats per cell. Payloads come from the same
seeded probe grid as the parity gate, so both backends see byte-identical
request streams — the comparison is paired.

Pure, testable pieces (percentile math, cell aggregation, repeat medians)
live at module top; the subprocess/network orchestration below them is kept
thin on purpose.
"""

from __future__ import annotations

import asyncio
import json
import math
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
from portfolio_core.logging import get_logger

from model_serving.artifacts import probe_grid
from model_serving.config import ServingConfig

log = get_logger(__name__)

BACKENDS = ("native", "onnx")


# ---------------------------------------------------------------------------
# Pure math (unit-tested against fixtures)
# ---------------------------------------------------------------------------


def percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile (latency SLO convention), as in experiment 08.

    ``q`` in (0, 1]; rank = ceil(q * n); returns ``None`` for empty input.
    """
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


@dataclass
class RequestRecord:
    """One HTTP request outcome (error is None on success)."""

    cell: str
    latency_s: float | None = None
    status_code: int | None = None
    error: str | None = None


@dataclass
class CellSummary:
    """Aggregates of one cell (one repeat), nearest-rank percentiles."""

    cell: str
    n_requests: int
    n_errors: int
    error_rate: float
    p50_s: float | None
    p95_s: float | None
    p99_s: float | None
    mean_s: float | None
    throughput_rps: float


def summarize_cell(records: list[RequestRecord], cell: str, wall_time_s: float) -> CellSummary:
    """Latency percentiles + throughput + error rate for one cell's records."""
    ok = [r.latency_s for r in records if r.error is None and r.latency_s is not None]
    n_errors = len(records) - len(ok)
    denom = max(len(records), 1)
    return CellSummary(
        cell=cell,
        n_requests=len(records),
        n_errors=n_errors,
        error_rate=n_errors / denom,
        p50_s=percentile(ok, 0.50),
        p95_s=percentile(ok, 0.95),
        p99_s=percentile(ok, 0.99),
        mean_s=(sum(ok) / len(ok)) if ok else None,
        throughput_rps=len(ok) / wall_time_s if wall_time_s > 0 else 0.0,
    )


def median(values: list[float]) -> float:
    """Plain median; the median-of-repeats reduction, tested against fixtures."""
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def median_cell(summaries: list[CellSummary], cell: str) -> dict[str, Any]:
    """Median-of-repeats per metric for one cell (experiment 08's discipline)."""
    rows = [s for s in summaries if s.cell == cell]
    if not rows:
        raise ValueError(f"no summaries for cell {cell}")
    metric_keys = ("p50_s", "p95_s", "p99_s", "mean_s", "throughput_rps", "error_rate")
    out: dict[str, Any] = {
        "cell": cell,
        "n_requests": rows[0].n_requests,
        "repeats": len(rows),
        "repeat": [asdict(s) for s in rows],
    }
    for key in metric_keys:
        vals = [float(getattr(s, key)) for s in rows if getattr(s, key) is not None]
        out[key] = median(vals) if vals else None
        if len(vals) > 1:
            out[f"{key}_min"] = min(vals)
            out[f"{key}_max"] = max(vals)
    return out


def payloads_from_grid(grid: Any, n: int, seed: int) -> list[dict[str, Any]]:
    """Deterministic request payload stream from the seeded probe grid."""
    import random

    rng = random.Random(seed)  # noqa: S311 - seeded bench shuffle RNG, not crypto
    rows: list[dict[str, Any]] = []
    cols = list(grid.columns)
    for i in range(n):
        raw = {c: grid.iloc[i % len(grid)][c] for c in cols}
        rows.append(
            {
                "hour": int(raw["hour"]),
                "temp": float(raw["temp"]),
                "hum": float(raw["hum"]),
                "windspeed": float(raw["windspeed"]),
                "weathersit": int(raw["weathersit"]),
                "hour_sin": float(raw["hour_sin"]),
                "hour_cos": float(raw["hour_cos"]),
                "weekday_sin": float(raw["weekday_sin"]),
                "weekday_cos": float(raw["weekday_cos"]),
                "month_sin": float(raw["month_sin"]),
                "month_cos": float(raw["month_cos"]),
                "holiday": int(raw["holiday"]),
                "workingday": int(raw["workingday"]),
                "cnt_lag_1h": float(raw["cnt_lag_1h"]),
                "cnt_lag_24h": float(raw["cnt_lag_24h"]),
                "cnt_lag_168h": float(raw["cnt_lag_168h"]),
            }
        )
    rng.shuffle(rows)
    return rows


# ---------------------------------------------------------------------------
# Subprocess service + RSS probe
# ---------------------------------------------------------------------------


class ServiceProcess:
    """The real service as a subprocess; readiness gated on /ready."""

    def __init__(self, cfg: ServingConfig, backend: str) -> None:
        self.cfg = cfg
        self.backend = backend
        self.process: subprocess.Popen[bytes] | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.cfg.serve.host}:{self.cfg.serve.port}"

    def start(self) -> None:
        cmd = [
            sys.executable,
            "-m",
            "model_serving.cli",
            "serve",
            "--backend",
            self.backend,
            "--host",
            self.cfg.serve.host,
            "--port",
            str(self.cfg.serve.port),
        ]
        log.info("bench: starting %s backend on %s", self.backend, self.base_url)
        self.process = subprocess.Popen(  # noqa: S603 - own CLI, fixed argv
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    async def wait_ready(self, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        async with httpx.AsyncClient(base_url=self.base_url, timeout=2.0) as client:
            while time.monotonic() < deadline:
                if self.process is not None and self.process.poll() is not None:
                    raise RuntimeError(f"service exited early (rc={self.process.returncode})")
                try:
                    r = await client.get("/ready")
                    if r.status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.25)
        raise TimeoutError(f"service not ready within {timeout_s}s")

    def rss_mb(self) -> float:
        """Fresh-process resident set size via ps (KB on macOS and Linux)."""
        if self.process is None or self.process.pid is None:
            raise RuntimeError("service not running")
        out = subprocess.run(  # noqa: S603 - fixed `ps` probe, no user input
            ["ps", "-o", "rss=", "-p", str(self.process.pid)],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
        return float(out.stdout.strip().split()[0]) / 1024.0

    def stop(self) -> None:
        if self.process is None:
            return
        proc = self.process
        self.process = None
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# Load cells
# ---------------------------------------------------------------------------


async def _post_one(
    client: httpx.AsyncClient, path: str, payload: dict[str, Any], timeout_s: float
) -> tuple[float | None, str | None, int | None]:
    start = time.perf_counter()
    try:
        r = await client.post(path, json=payload, timeout=timeout_s)
        latency = time.perf_counter() - start
        if r.status_code != 200:
            return None, f"http {r.status_code}", r.status_code
        return latency, None, r.status_code
    except httpx.HTTPError as exc:
        return None, type(exc).__name__, None


async def concurrency_cell(
    client: httpx.AsyncClient,
    cfg: ServingConfig,
    payloads: list[dict[str, Any]],
    concurrency: int,
    repeat: int,
) -> tuple[CellSummary, list[RequestRecord]]:
    """One (concurrency, repeat) cell: N requests under a semaphore."""
    cell = f"c{concurrency}"
    semaphore = asyncio.Semaphore(concurrency)
    n = cfg.bench.requests_per_concurrency

    async def guarded(i: int) -> RequestRecord:
        async with semaphore:
            latency, error, status = await _post_one(
                client,
                "/predict",
                {"row": payloads[i % len(payloads)]},
                cfg.bench.request_timeout_s,
            )
            return RequestRecord(cell=cell, latency_s=latency, status_code=status, error=error)

    start = time.perf_counter()
    records = list(await asyncio.gather(*(guarded(i) for i in range(n))))
    wall = time.perf_counter() - start
    return summarize_cell(records, cell, wall), records


async def batch_cell(
    client: httpx.AsyncClient,
    cfg: ServingConfig,
    payloads: list[dict[str, Any]],
    size: int,
    repeat: int,
) -> tuple[CellSummary, list[RequestRecord]]:
    """One (batch size) cell: K batched requests, throughput counted in rows/s."""
    cell = f"b{size}"
    k = cfg.bench.batch_requests_per_size

    async def one(i: int) -> RequestRecord:
        rows = [payloads[(i * size + j) % len(payloads)] for j in range(size)]
        latency, error, status = await _post_one(
            client, "/predict/batch", {"rows": rows}, cfg.bench.request_timeout_s
        )
        return RequestRecord(cell=cell, latency_s=latency, status_code=status, error=error)

    start = time.perf_counter()
    records = list(await asyncio.gather(*(one(i) for i in range(k))))
    wall = time.perf_counter() - start
    summary = summarize_cell(records, cell, wall)
    summary.throughput_rps = len(records) * size / wall if wall > 0 else 0.0
    return summary, records


async def warmup(client: httpx.AsyncClient, cfg: ServingConfig, n: int) -> None:
    """Warm-up requests, excluded from every measurement (08's discipline)."""
    payload = {"row": probe_row_zero()}
    await asyncio.gather(
        *(_post_one(client, "/predict", payload, cfg.bench.request_timeout_s) for _ in range(n))
    )


def probe_row_zero() -> dict[str, Any]:
    """A fixed in-contract warm-up row (all zeros is a legal feature vector)."""
    from model_serving.service.schemas import NUMERIC_FIELDS

    row: dict[str, Any] = {"hour": 0}
    for name in NUMERIC_FIELDS:
        if name == "weathersit":
            row[name] = 1
        elif name in ("holiday", "workingday"):
            row[name] = 0
        else:
            row[name] = 0.0
    return row


# ---------------------------------------------------------------------------
# Stage orchestration
# ---------------------------------------------------------------------------


async def run_backend(cfg: ServingConfig, backend: str) -> dict[str, Any]:
    """Full protocol for one backend: fresh-process RSS, sweep, batch curve."""
    from model_serving.service.schemas import NUMERIC_FIELDS

    grid = probe_grid(cfg.probe_grid_n, cfg.seed, NUMERIC_FIELDS)
    payloads = payloads_from_grid(grid, cfg.bench.requests_per_concurrency, cfg.seed)

    rss_readings: list[float] = []
    summaries: list[CellSummary] = []
    records: list[RequestRecord] = []

    service = ServiceProcess(cfg, backend)
    try:
        for _ in range(cfg.bench.rss_probes):
            service.start()
            await service.wait_ready(cfg.serve.ready_timeout_s)
            async with httpx.AsyncClient(
                base_url=service.base_url, timeout=cfg.bench.request_timeout_s
            ) as client:
                await warmup(client, cfg, cfg.bench.warmup_requests)
            rss_readings.append(service.rss_mb())
            service.stop()
        log.info(
            "bench[%s]: fresh-process RSS median %.0f MB (%d probes)",
            backend,
            median(rss_readings),
            len(rss_readings),
        )

        service.start()
        await service.wait_ready(cfg.serve.ready_timeout_s)
        async with httpx.AsyncClient(
            base_url=service.base_url, timeout=cfg.bench.request_timeout_s
        ) as client:
            await warmup(client, cfg, cfg.bench.warmup_requests)
            for concurrency in cfg.bench.concurrency_levels:
                for repeat in range(cfg.bench.repeats):
                    summary, cell_records = await concurrency_cell(
                        client, cfg, payloads, concurrency, repeat
                    )
                    summaries.append(summary)
                    records.extend(cell_records)
                log.info(
                    "bench[%s]: c=%d p50=%.4fs p95=%.4fs rps=%.1f errors=%d/%d",
                    backend,
                    concurrency,
                    summary.p50_s or -1,
                    summary.p95_s or -1,
                    summary.throughput_rps,
                    summary.n_errors,
                    summary.n_requests,
                )
            for size in cfg.bench.batch_sizes:
                for repeat in range(cfg.bench.repeats):
                    summary, cell_records = await batch_cell(client, cfg, payloads, size, repeat)
                    summaries.append(summary)
                    records.extend(cell_records)
                log.info(
                    "bench[%s]: batch=%d p50=%.4fs rows/s=%.1f errors=%d/%d",
                    backend,
                    size,
                    summary.p50_s or -1,
                    summary.throughput_rps,
                    summary.n_errors,
                    summary.n_requests,
                )
    finally:
        service.stop()

    concurrency_cells = [median_cell(summaries, f"c{c}") for c in cfg.bench.concurrency_levels]
    batch_cells = [median_cell(summaries, f"b{b}") for b in cfg.bench.batch_sizes]
    return {
        "backend": backend,
        "rss_mb": {
            "probes": rss_readings,
            "median": median(rss_readings),
            "min": min(rss_readings),
            "max": max(rss_readings),
        },
        "concurrency": {c["cell"]: c for c in concurrency_cells},
        "batch": {c["cell"]: c for c in batch_cells},
        "summaries": [asdict(s) for s in summaries],
        "n_records": len(records),
    }


def benchmark_core(cfg: ServingConfig) -> Path:
    """Run the paired benchmark over both backends; persist the raw record."""
    started = time.perf_counter()
    results = {backend: asyncio.run(run_backend(cfg, backend)) for backend in BACKENDS}
    run = {
        "seed": cfg.seed,
        "host": cfg.serve.host,
        "port": cfg.serve.port,
        "concurrency_levels": cfg.bench.concurrency_levels,
        "requests_per_concurrency": cfg.bench.requests_per_concurrency,
        "warmup_requests": cfg.bench.warmup_requests,
        "repeats": cfg.bench.repeats,
        "batch_sizes": cfg.bench.batch_sizes,
        "batch_requests_per_size": cfg.bench.batch_requests_per_size,
        "backends": results,
        "bench_runtime_s": round(time.perf_counter() - started, 3),
    }
    out = cfg.data_dir / "bench_run.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run, indent=2) + "\n")
    log.info("bench: %.1fs -> %s", run["bench_runtime_s"], out)
    return out
