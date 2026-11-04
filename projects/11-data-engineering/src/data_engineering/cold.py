"""Fresh-process single-task runner (cold reads + true peak RSS probes).

Invoked by the harness as ``python -m data_engineering.cold <bundle.json>
<engine> <task>``: one task implementation runs once in this clean interpreter,
and the run's wall time, process peak RSS (``ru_maxrss`` high-water) and
canonical-result fingerprint are printed as one JSON line for the parent to
collect. A fresh process owns its memory, so the high-water mark is
attributable to this cell alone.
"""

import json
import resource
import sys
import tempfile
import time
from pathlib import Path

from data_engineering.data import DataBundle
from data_engineering.engines import build_adapter
from data_engineering.tasks import TASKS_BY_NAME


def _peak_rss_mb() -> float:
    """Process peak RSS in MB (ru_maxrss: bytes on macOS, KiB on Linux)."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            "usage: python -m data_engineering.cold <bundle.json> <engine> <task>",
            file=sys.stderr,
        )
        return 2
    bundle = DataBundle.from_dict(json.loads(Path(argv[1]).read_text()))
    adapter = build_adapter(argv[2])
    task = TASKS_BY_NAME[argv[3]]

    with tempfile.TemporaryDirectory(prefix="de11-cold-work-") as work:
        t0 = time.perf_counter()
        result = task.impls[argv[2]](adapter, bundle, Path(work))
        elapsed = time.perf_counter() - t0

    print(
        json.dumps(
            {
                "time_s": round(elapsed, 6),
                "peak_rss_mb": round(_peak_rss_mb(), 1),
                "rows": result.rows,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
