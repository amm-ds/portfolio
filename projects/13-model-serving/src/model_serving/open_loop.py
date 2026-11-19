"""Open-loop (constant-arrival-rate) load arm for the serving harness.

Q4e (next round 2). The committed benchmark is closed-loop (a semaphore caps
concurrency). This arm adds a fixed-schedule arrival process: N requests at a
constant rate r (request i starts at i/r seconds), so latency percentiles are
read under a controlled offered load rather than a client-side concurrency
cap. Reuses the harness's service process, payload stream, request posting,
and cell summarisation; percentiles are nearest-rank from the raw per-request
records, with a paired bootstrap 95% interval on p99.

Output: NEW files under ``reports/open_loop/`` only. Local compute, no
hosted calls, no new dependencies. Existing load reports untouched.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import numpy as np
from portfolio_core.logging import get_logger

from model_serving.artifacts import probe_grid
from model_serving.bench import (
    RequestRecord,
    ServiceProcess,
    _post_one,
    payloads_from_grid,
    percentile,
    summarize_cell,
    warmup,
)
from model_serving.config import ServingConfig

log = get_logger(__name__)

# Constant arrival rates (requests/second) per cell; 300 requests per cell,
# so cell duration is 300/r seconds. Rates above the service's capacity show
# up as queueing latency and (eventually) errors, which is what the arm
# measures.
OPEN_LOOP_RATES_RPS = [50, 100, 200]
BOOTSTRAP_REPS = 2000


async def open_loop_cell(
    client: httpx.AsyncClient,
    cfg: ServingConfig,
    payloads: list[dict[str, Any]],
    rate_rps: int,
    n: int,
) -> tuple[Any, list[RequestRecord]]:
    """One constant-arrival cell: request i starts at i/rate seconds."""
    cell = f"open-r{rate_rps}"
    interval = 1.0 / rate_rps

    async def one(i: int) -> RequestRecord:
        await asyncio.sleep(i * interval)
        latency, error, status = await _post_one(
            client,
            "/predict",
            {"row": payloads[i % len(payloads)]},
            cfg.bench.request_timeout_s,
        )
        return RequestRecord(cell=cell, latency_s=latency, status_code=status, error=error)

    start = time.perf_counter()
    records = list(await asyncio.gather(*(one(i) for i in range(n))))
    wall = time.perf_counter() - start
    return summarize_cell(records, cell, wall), records


def p99_bootstrap(
    latencies: list[float], reps: int = BOOTSTRAP_REPS, seed: int = 42
) -> list[float]:
    """Percentile bootstrap on p99 over the raw ok latencies."""
    arr = np.asarray(latencies)
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(reps):
        idx = rng.integers(0, len(arr), len(arr))
        stats.append(percentile(arr[idx].tolist(), 0.99) or 0.0)
    stats.sort()
    return [stats[int(0.025 * len(stats))], stats[int(0.975 * len(stats)) - 1]]


async def run_open_loop_backend(cfg: ServingConfig, backend: str) -> dict[str, Any]:
    """Constant-arrival cells for one backend on one warmed service process."""
    from model_serving.service.schemas import NUMERIC_FIELDS

    grid = probe_grid(cfg.probe_grid_n, cfg.seed, NUMERIC_FIELDS)
    payloads = payloads_from_grid(grid, cfg.bench.requests_per_concurrency, cfg.seed)

    service = ServiceProcess(cfg, backend)
    cells: list[dict[str, Any]] = []
    try:
        service.start()
        await service.wait_ready(cfg.serve.ready_timeout_s)
        async with httpx.AsyncClient(
            base_url=service.base_url, timeout=cfg.bench.request_timeout_s
        ) as client:
            await warmup(client, cfg, cfg.bench.warmup_requests)
            for rate in OPEN_LOOP_RATES_RPS:
                summary, records = await open_loop_cell(
                    client, cfg, payloads, rate, cfg.bench.requests_per_concurrency
                )
                ok = [r.latency_s for r in records if r.error is None and r.latency_s is not None]
                cells.append(
                    {
                        "rate_rps": rate,
                        "n_requests": summary.n_requests,
                        "n_errors": summary.n_errors,
                        "error_rate": summary.error_rate,
                        "offered_duration_s": round(cfg.bench.requests_per_concurrency / rate, 3),
                        "wall_time_s": round(
                            max(r.latency_s or 0.0 for r in records)
                            + cfg.bench.requests_per_concurrency / rate,
                            3,
                        ),
                        "p50_s": summary.p50_s,
                        "p95_s": summary.p95_s,
                        "p99_s": summary.p99_s,
                        "p99_ci95": p99_bootstrap(ok),
                        "achieved_rps": summary.throughput_rps,
                    }
                )
                log.info(
                    "open-loop[%s]: r=%d p99=%.4fs errors=%d/%d",
                    backend,
                    rate,
                    summary.p99_s or -1,
                    summary.n_errors,
                    summary.n_requests,
                )
    finally:
        service.stop()
    return {"backend": backend, "cells": cells}


def run_open_loop(cfg: ServingConfig) -> dict[str, Any]:
    """Run the constant-arrival arm on both backends; write reports/open_loop/."""
    results = [asyncio.run(run_open_loop_backend(cfg, b)) for b in ("native", "onnx")]
    report: dict[str, Any] = {
        "schema_version": "open-loop-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "method": (
            "constant-arrival-rate arm: request i starts at i/rate seconds; "
            f"{cfg.bench.requests_per_concurrency} requests per cell; "
            "nearest-rank percentiles from raw records; p99 bootstrap 95% "
            f"({BOOTSTRAP_REPS} reps, seed 42). Closed-loop cells unchanged."
        ),
        "rates_rps": OPEN_LOOP_RATES_RPS,
        "backends": results,
    }
    out_dir = cfg.reports_dir / "open_loop"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        "# Open-loop (constant-arrival) arm",
        "",
        f"Generated: {report['generated_at']} · rates {OPEN_LOOP_RATES_RPS} req/s · "
        f"{cfg.bench.requests_per_concurrency} requests per cell · both backends.",
        "",
        "| backend | rate (req/s) | p50 (s) | p95 (s) | p99 (s) | p99 95% CI | errors |",
        "|---|---|---|---|---|---|---|",
    ]
    for backend in results:
        for c in backend["cells"]:
            ci = c["p99_ci95"]
            lines.append(
                f"| {backend['backend']} | {c['rate_rps']} | {c['p50_s']:.4f} "
                f"| {c['p95_s']:.4f} | {c['p99_s']:.4f} "
                f"| [{ci[0]:.4f}, {ci[1]:.4f}] | {c['n_errors']}/{c['n_requests']} |"
            )
    lines += [
        "",
        "Offered load is fixed by the schedule; above the service's capacity, "
        "latency inflates rather than the client backing off (the closed-loop "
        "concurrency cells measure that side). New files only; existing load "
        "reports untouched.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    log.info("wrote %s", out_dir)
    return report
