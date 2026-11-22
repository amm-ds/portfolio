"""Run infrastructure: per-question checkpoints, manifest, guards, host capture.

Phase0-infra (2026-11-22). Paid-run safety for project 01:

- ``reports/runs/<run_id>/rows.jsonl`` — one flushed line per finished
  question, so a budget abort never loses completed work.
- ``manifest.json`` — config hash, commit, dirty flag, split name, set sha256,
  index id, judge model, judge prompt hash, cumulative spend. Resume skips
  question hashes already present only when the manifest matches; a manifest
  mismatch refuses to resume.
- Sealed guard: a question file's sha256 is verified against its manifest
  before any run reads it.
- Request-host capture: an httpx log handler records the host of every model
  request into each checkpoint row.
- File-write guard: runs write only under ``data/`` and ``reports/``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from portfolio_core.llm_budget import get_ledger, reset_ledger
from portfolio_core.logging import get_logger

logger = get_logger(__name__)

RUNS_ROOT = Path("reports") / "runs"
SEALED_SET = "golden_sealed_v2.json"
_WRITE_ROOTS = ("data/", "reports/")
HTTP_REQUEST_RE = re.compile(r"HTTP Request: \w+ (\S+)")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def question_hash(question: str) -> str:
    return hashlib.sha256(question.encode("utf-8")).hexdigest()[:16]


def verify_set_sha(set_path: Path) -> str:
    """Sealed guard: refuse to run when the set file differs from its manifest.

    A manifest ``data/<name>.sha256.json`` must exist and list this file's
    sha256; a mismatch (or a missing manifest for a golden set) raises.
    """
    manifest_path = set_path.with_suffix(".sha256.json")
    if not manifest_path.exists():
        if set_path.name.startswith("golden_"):
            raise SystemExit(f"sealed guard: no sha manifest for {set_path.name}")
        return sha256_file(set_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = payload.get("sha256") or payload.get(set_path.name, {}).get("sha256")
    actual = sha256_file(set_path)
    if expected and expected != actual:
        raise SystemExit(
            f"sealed guard: sha mismatch for {set_path.name} "
            f"(manifest {expected[:12]}…, file {actual[:12]}…)"
        )
    return actual


def guard_run_write(path: Path) -> None:
    """Police writes inside the repo: only data/ or reports/ paths are allowed.

    Paths outside the repo (tests' tmp dirs) are not policed.
    """
    try:
        rel = path.resolve().relative_to(Path.cwd().resolve().parent.parent)
    except ValueError:
        return
    if "reports" not in rel.parts and "data" not in rel.parts:
        raise PermissionError(f"run write-guard: refusing to write outside data//reports/: {rel}")


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - fixed well-known VCS binary
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:  # broad: outside a checkout the commit is unknown
        return "unknown"


def git_dirty() -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],  # noqa: S607 - fixed well-known VCS binary
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        return bool(out.strip())
    except Exception:  # broad: dirty unknown outside a checkout
        return True


@dataclass
class RunManifest:
    run_id: str
    config_hash: str
    commit: str
    dirty: bool
    split: str
    set_sha256: str
    index_id: str
    judge_model: str
    judge_prompt_hash: str
    created_at: str = ""
    cumulative_spend_usd: float = 0.0

    def identity(self) -> str:
        """The fields that must match for a resume to be allowed."""
        payload = {k: v for k, v in asdict(self).items() if k != "cumulative_spend_usd"}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


class HostGrabber(logging.Handler):
    """Captures the destination host of every httpx request made during a row."""

    def __init__(self) -> None:
        super().__init__()
        self.hosts: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        match = HTTP_REQUEST_RE.search(message)
        if match:
            from urllib.parse import urlparse

            host = urlparse(match.group(1)).hostname
            if host and host not in self.hosts:
                self.hosts.append(host)


@dataclass
class Checkpoint:
    """Per-question checkpoint under reports/runs/<run_id>/."""

    run_dir: Path
    manifest: RunManifest
    rows_path: Path = field(init=False)
    _rows: dict[str, dict[str, Any]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.rows_path = self.run_dir / "rows.jsonl"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "manifest.json").write_text(
            json.dumps(asdict(self.manifest), indent=2) + "\n", encoding="utf-8"
        )

    @classmethod
    def open(cls, run_dir: Path, manifest: RunManifest, resume: bool = True) -> Checkpoint:
        """Open or create a checkpoint; refuse to resume on identity mismatch."""
        if run_dir.exists() and (run_dir / "manifest.json").exists() and resume:
            old = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            old_identity = RunManifest(**old).identity()
            if old_identity != manifest.identity():
                raise SystemExit(
                    f"checkpoint refusal: manifest identity differs in {run_dir} "
                    "(config/commit/set changed; refusing to resume)"
                )
            manifest.cumulative_spend_usd = old.get("cumulative_spend_usd", 0.0)
            checkpoint = cls(run_dir, manifest)
            if checkpoint.rows_path.exists():
                for line in checkpoint.rows_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        row = json.loads(line)
                        checkpoint._rows[row["qhash"]] = row
            return checkpoint
        return cls(run_dir, manifest)

    @property
    def completed(self) -> set[str]:
        return set(self._rows)

    def write_row(
        self,
        qhash: str,
        question: str,
        trace: dict[str, Any],
        hosts: list[str],
        spend_usd: float,
    ) -> None:
        guard_run_write(self.rows_path)
        row = {
            "qhash": qhash,
            "question": question,
            "trace": trace,
            "hosts": sorted(hosts),
            "spend_usd": round(spend_usd, 6),
            "ts": time.time(),
        }
        with self.rows_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
        self._rows[qhash] = row

    def merged_traces(self, new_traces: list[Any]) -> list[dict[str, Any]]:
        """Checkpoint rows (resume) followed by the current run's traces."""
        rows = [r["trace"] for r in self._rows.values()]
        rows.extend(new_traces)
        return rows

    def update_spend(self, total_spend_usd: float) -> None:
        self.manifest.cumulative_spend_usd = round(total_spend_usd, 6)
        (self.run_dir / "manifest.json").write_text(
            json.dumps(asdict(self.manifest), indent=2) + "\n", encoding="utf-8"
        )


def seed_spend_from_manifest(checkpoint: Checkpoint) -> None:
    """Seed the process ledger with prior cumulative spend (resume)."""
    prior = checkpoint.manifest.cumulative_spend_usd
    if prior > 0:
        reset_ledger()
        get_ledger(seed_usd=prior)
        logger.info("ledger seeded with prior spend $%s from checkpoint", prior)


def make_run_id(split: str, set_sha256: str) -> str:
    return f"{split}-{set_sha256[:12]}"


def config_hash(config: Any) -> str:
    payload = config.model_dump_json() if hasattr(config, "model_dump_json") else json.dumps(config)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
