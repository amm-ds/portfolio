"""R5: error budget card from committed metrics only (no model calls).

One table: cost per query, latency median and p95, and the unsupported rate
with its interval, side by side, for the sealed held-out run.

Sources (all committed, read-only):
- ``reports/metrics.json`` → ``rag_agent.est_cost_usd_per_query`` and
  ``detail.heldout.ops`` (p50/p95 latency).
- ``reports/question_traces_heldout.json`` → per-question verdicts; the
  unsupported rate is ``unsupported-claim`` outcomes over all sealed
  questions, with a Wilson 95% interval.

Output: NEW files under ``reports/error_budget/`` only. No copy changes.

    uv run python scripts/error_budget.py
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def main() -> int:
    metrics = json.loads((ROOT / "reports" / "metrics.json").read_text())
    traces = json.loads((ROOT / "reports" / "question_traces_heldout.json").read_text())

    cost = float(metrics["rag_agent"]["est_cost_usd_per_query"])
    ops = metrics["detail"]["heldout"]["ops"]
    n_total = len(traces)
    n_unsupported = sum(1 for row in traces if row["verdict"] == "unsupported-claim")
    interval = wilson(n_unsupported, n_total)

    report: dict[str, Any] = {
        "schema_version": "error-budget-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "set": "sealed held-out (committed run)",
        "cost_usd_per_query": cost,
        "latency_p50_s": ops["p50_latency_s"],
        "latency_p95_s": ops["p95_latency_s"],
        "unsupported_rate": n_unsupported / n_total,
        "unsupported_n": n_unsupported,
        "unsupported_total_n": n_total,
        "unsupported_wilson95": list(interval),
        "sources": {
            "cost": "reports/metrics.json -> rag_agent.est_cost_usd_per_query",
            "latency": "reports/metrics.json -> detail.heldout.ops.p50/p95_latency_s",
            "unsupported": "reports/question_traces_heldout.json -> verdict == 'unsupported-claim'",
        },
        "note": (
            "Cost is the committed cloud-equivalent estimate at the reference "
            "rate card, not billed spend. Latency covers the full answer pass "
            "(retrieval + generation + verify)."
        ),
    }
    out_dir = ROOT / "reports" / "error_budget"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")

    lines = [
        "# R5 error budget — sealed held-out run",
        "",
        f"Generated: {report['generated_at']} · sources: committed metrics/traces only.",
        "",
        "| measure | value | interval / note |",
        "|---|---|---|",
        f"| cost per query | ${cost:.6f} | cloud-equivalent estimate, committed rate card |",
        f"| latency p50 | {ops['p50_latency_s']:.2f} s | full answer pass |",
        f"| latency p95 | {ops['p95_latency_s']:.2f} s | full answer pass |",
        f"| unsupported-claim rate | {n_unsupported}/{n_total} = {n_unsupported / n_total:.4f} "
        f"| Wilson 95% [{interval[0]:.4f}, {interval[1]:.4f}] |",
        "",
        "New files only; no committed record touched and no copy changed.",
    ]
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
