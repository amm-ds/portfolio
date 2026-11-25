"""Append-only, repo-relative experiment ledger."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast


def canonical_sha256(value: Any) -> str:
    """Hash a JSON-compatible configuration without formatting ambiguity."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def file_sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def append_ledger(
    project_root: Path,
    *,
    step: str,
    change: str,
    split: str,
    config_sha256: str,
    set_sha256: str,
    n: int,
    headline: dict[str, Any],
    wall_clock_s: float,
    report_path: str,
    decision: str,
    request_hosts: list[str] | None = None,
) -> None:
    """Append one run without mutating any earlier ledger row."""
    path = project_root / "reports" / "experiment_log.json"
    rows = cast(list[dict[str, Any]], json.loads(path.read_text())) if path.exists() else []
    rows.append(
        {
            "ts": datetime.now(UTC).isoformat(),
            "step": step,
            "change": change,
            "split": split,
            "config_sha256": config_sha256,
            "set_sha256": set_sha256,
            "n": n,
            "headline": headline,
            "wall_clock_s": wall_clock_s,
            "request_hosts": request_hosts or [],
            "report_path": report_path,
            "decision": decision,
        }
    )
    write_json(path, rows)
