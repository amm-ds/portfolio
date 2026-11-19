"""Cold-start re-timing with per-cell spread (Q4g, next round 2).

Re-runs the harness's fresh-process cold probe (`python -m
data_engineering.cold`, reused from :mod:`data_engineering.harness`) REPEATED
times per cold-measurable task-by-engine cell on the real bundle, and reports
per-cell spread (min / median / max) next to the committed warm median and
the committed single cold probe (both read-only).

Output: NEW files under ``reports/cold_start/`` only. No hosted calls, no new
dependencies; the existing subprocess machinery only.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import numpy as np
from portfolio_core.logging import get_logger

from data_engineering.config import DEConfig
from data_engineering.fetch import load_real_bundle
from data_engineering.harness import _probe_subprocess

log = get_logger(__name__)

COLD_REPEATS = 5


def run_cold_start(cfg: DEConfig) -> dict[str, Any]:
    """Re-time cold starts per committed cold-measurable cell; write the report."""
    committed = json.loads((cfg.reports_dir / "metrics.json").read_text())
    bundle = load_real_bundle(cfg)
    bundle.validate()

    cells: list[dict[str, Any]] = []
    for task_name, task_block in committed["tasks"].items():
        for engine, engine_block in task_block["engines"].items():
            if engine_block.get("cold_s") is None:
                continue
            repeats: list[float] = []
            peaks: list[float] = []
            for _ in range(COLD_REPEATS):
                probe = _probe_subprocess(bundle, engine, task_name)
                repeats.append(float(probe["time_s"]))
                peaks.append(float(probe["peak_rss_mb"]))
            warm = engine_block.get("time_all_s") or []
            warm_median = float(np.median(warm)) if warm else None
            entry: dict[str, Any] = {
                "task": task_name,
                "engine": engine,
                "cold_repeats_s": repeats,
                "cold_min_s": min(repeats),
                "cold_median_s": float(np.median(repeats)),
                "cold_max_s": max(repeats),
                "cold_spread_s": max(repeats) - min(repeats),
                "peak_rss_mb_max": max(peaks),
                "committed_cold_s_single_probe": engine_block.get("cold_s"),
                "committed_warm_median_s": warm_median,
                "cold_over_warm_ratio": (
                    round(float(np.median(repeats)) / warm_median, 3) if warm_median else None
                ),
            }
            cells.append(entry)
            log.info(
                "%s/%s: cold median %.3fs (spread %.3f) vs warm median %.3fs",
                task_name,
                engine,
                entry["cold_median_s"],
                entry["cold_spread_s"],
                warm_median or float("nan"),
            )

    report: dict[str, Any] = {
        "schema_version": "cold-start-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "data_source": "real-trip bundle via load_real_bundle (same as the committed benchmark)",
        "method": (
            f"{COLD_REPEATS} fresh-process cold probes per cell "
            "(python -m data_engineering.cold); warm numbers are the committed "
            "time_all_s medians, read-only"
        ),
        "n_cells": len(cells),
        "cells": cells,
    }
    out_dir = cfg.reports_dir / "cold_start"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        "# Cold-start timings with per-cell spread",
        "",
        f"Generated: {report['generated_at']} · {len(cells)} cold-measurable "
        f"cells x {COLD_REPEATS} fresh-process probes - real-trip bundle.",
        "",
        "| task | engine | cold med (s) | spread | warm med (s, committed) | cold/warm |",
        "|---|---|---|---|---|---|",
    ]
    for c in cells:
        warm = f"{c['committed_warm_median_s']:.3f}" if c["committed_warm_median_s"] else "n/a"
        ratio = f"{c['cold_over_warm_ratio']:.2f}" if c["cold_over_warm_ratio"] else "n/a"
        lines.append(
            f"| {c['task']} | {c['engine']} | {c['cold_median_s']:.3f} "
            f"| {c['cold_spread_s']:.3f} | {warm} | {ratio} |"
        )
    lines += [
        "",
        "Spread is the max-min across the five cold probes of one cell on one "
        "shared machine — read it as run-to-run noise, not a distribution. "
        "New files only; committed timing reports untouched.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    log.info("wrote %s", out_dir)
    return report
