"""Compare entity F1 on the original 7-document set vs the full expanded set.

Reads a completed expanded live-metrics report and the committed references
(to identify the original case ids), pools entity counts per page for each
subset, and writes ``comparison.json`` / ``comparison.md`` with bootstrap
95% intervals over pages (seed 42, 2000 reps, deterministic, $0).

    uv run python scripts/compare_expanded_sample.py reports/expanded-2026-11-19/live-metrics.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_REFERENCE_PATH = ROOT / "evaluations" / "references.json"
BOOTSTRAP_REPS = 2000


def page_counts(case: dict[str, Any]) -> list[tuple[int, int, int]]:
    """(true_positives, predicted, reference) entity counts per reference page."""
    rows = []
    for page in case.get("reference_pages", []):
        e = page["entities"]
        rows.append(
            (
                int(e["entity_true_positive"]),
                int(e["entity_predicted"]),
                int(e["entity_reference"]),
            )
        )
    return rows


def pooled_f1(counts: list[tuple[int, int, int]]) -> float:
    tp = sum(c[0] for c in counts)
    p = sum(c[1] for c in counts)
    r = sum(c[2] for c in counts)
    precision = tp / p if p else 0.0
    recall = tp / r if r else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def bootstrap_ci(pages: list[tuple[int, int, int]], seed: int = 42) -> list[float]:
    rng = np.random.default_rng(seed)
    stats = []
    for _ in range(BOOTSTRAP_REPS):
        idx = rng.integers(0, len(pages), len(pages))
        stats.append(pooled_f1([pages[i] for i in idx]))
    stats.sort()
    return [stats[int(0.025 * len(stats))], stats[int(0.975 * len(stats)) - 1]]


def main() -> int:
    metrics_path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "reports" / "expanded-2026-11-19" / "live-metrics.json"
    )
    metrics = json.loads(metrics_path.read_text())
    original_ids = {c["case_id"] for c in json.loads(ORIGINAL_REFERENCE_PATH.read_text())["cases"]}
    cases = metrics["cases"]
    original_pages = [
        count for c in cases if c["case_id"] in original_ids for count in page_counts(c)
    ]
    expanded_pages = [count for c in cases for count in page_counts(c)]
    n_original_cases = sum(1 for c in cases if c["case_id"] in original_ids)

    result: dict[str, Any] = {
        "dataset_revision": metrics["dataset"]["revision"],
        "model": metrics.get("model") or metrics.get("provider"),
        "original": {
            "n_cases": n_original_cases,
            "n_reference_pages": len(original_pages),
            "entity_f1": pooled_f1(original_pages),
            "entity_f1_ci95": bootstrap_ci(original_pages),
        },
        "expanded": {
            "n_cases": len(cases),
            "n_reference_pages": len(expanded_pages),
            "entity_f1": pooled_f1(expanded_pages),
            "entity_f1_ci95": bootstrap_ci(expanded_pages),
        },
        "cost_estimate_usd": metrics["cost_estimate"]["usd"],
        "cost_note": metrics["cost_estimate"]["note"],
    }
    out_dir = metrics_path.parent
    (out_dir / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")

    o, e = result["original"], result["expanded"]
    lines = [
        "# Expanded sample: entity F1, original vs expanded",
        "",
        f"Dataset revision {result['dataset_revision']} · hosted cloud-equivalent "
        f"spend ${result['cost_estimate_usd']:.6f} ({result['cost_note']}).",
        "",
        "| subset | cases | reference pages | entity F1 | 95% bootstrap CI |",
        "|---|---|---|---|---|",
        f"| original | {o['n_cases']} | {o['n_reference_pages']} | {o['entity_f1']:.4f} "
        f"| [{o['entity_f1_ci95'][0]:.4f}, {o['entity_f1_ci95'][1]:.4f}] |",
        f"| expanded | {e['n_cases']} | {e['n_reference_pages']} | {e['entity_f1']:.4f} "
        f"| [{e['entity_f1_ci95'][0]:.4f}, {e['entity_f1_ci95'][1]:.4f}] |",
        "",
        "Pooled entity F1 from per-page match counts; intervals resample pages "
        "(seed 42, 2000 reps).",
    ]
    (out_dir / "comparison.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
