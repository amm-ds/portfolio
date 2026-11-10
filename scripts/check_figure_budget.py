#!/usr/bin/env python3
"""Committed figure-weight budget (external audit F-02).

Interactive figures are the showcase payload; a per-customer trace or an
unsimplified geometry can silently commit multi-megabyte JSONs that dominate
mobile page weight. Warn above WARN_BYTES, fail above FAIL_BYTES per figure.

Run: uv run python scripts/check_figure_budget.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

WARN_BYTES = 500 * 1024
FAIL_BYTES = 1500 * 1024


def main() -> int:
    oversized: list[tuple[int, Path]] = []
    warnings = 0
    for fig in sorted(REPO.glob("projects/*/reports*/figures/*.json")):
        size = fig.stat().st_size
        rel = fig.relative_to(REPO)
        if size > FAIL_BYTES:
            oversized.append((size, rel))
        elif size > WARN_BYTES:
            warnings += 1
            print(f"WARN {size / 1024:7.0f} KiB {rel}")
    for size, rel in oversized:
        print(f"FAIL {size / 1024:7.0f} KiB {rel} (budget {FAIL_BYTES // 1024} KiB)")
    if oversized:
        print(f"figure-budget: {len(oversized)} figure(s) over {FAIL_BYTES // 1024} KiB")
        return 1
    print(f"figure-budget: OK ({warnings} over the {WARN_BYTES // 1024} KiB warn line)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
