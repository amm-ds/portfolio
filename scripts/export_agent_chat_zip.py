#!/usr/bin/env python3
"""Export apps/agent-chat as a versioned, timestamped zip for external collaboration.

Local-only by design: ``artifacts/`` is gitignored at the repo root, so the
zips never enter git. Each export carries a STATUS manifest (git SHA, dirty
flag, per-file hashes) both inside the zip and beside it; the next export
diffs itself against the previous one so development between handoffs is
visible at a glance (files added/removed/changed + the commit range).

Usage:
    uv run python scripts/export_agent_chat_zip.py          # export + diff vs previous
    uv run python scripts/export_agent_chat_zip.py --no-diff
    uv run python scripts/export_agent_chat_zip.py --list   # show exports + statuses
"""

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "apps" / "agent-chat"
OUT_DIR = REPO / "artifacts" / "agent-chat-zips"

# Reproducible or machine-local payloads: the collaborator rebuilds them
# (dvc repro / npm ci), and session state is never shared.
EXCLUDE_DIRS = {
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    "agent_chat_memory",
    # test-runner state (external evaluation P1-4): never part of a handoff
    "test-results",
    "playwright-report",
    "coverage",
    ".nyc_output",
    "htmlcov",
}
EXCLUDE_FILES = {".DS_Store", "agent_chat.db", ".env"}
EXCLUDE_SUFFIXES = {".pyc"}
# reproducible data (corpus + vector index): rebuilt by the app's own pipeline
EXCLUDE_PREFIXES = ("data/raw/", "data/index/")


class ExportError(RuntimeError):
    """Fatal export problem (e.g. not inside a git worktree)."""


@dataclass
class ExportMeta:
    version: int
    zip_name: str
    created_at: str
    git_sha: str
    dirty: bool
    dirty_files: list[str]
    file_count: int
    total_bytes: int


def git(*args: str) -> str:
    proc = subprocess.run(  # noqa: S603 - fixed git binary + static args
        ["/usr/bin/env", "git", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    if proc.returncode != 0:
        raise ExportError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def provenance() -> dict[str, set[str]]:
    """Classify every app-relative path as tracked / ignored / untracked.

    The payload can carry files git does not track (focused reports the
    collaborator wants) — the manifest records their origin per file so a
    ``dirty: false`` export can no longer smuggle in bytes that are not
    provably from the named commit (external evaluation P1-4)."""
    tracked = {
        Path(p).relative_to("apps/agent-chat").as_posix()
        for p in git("ls-files", "--", "apps/agent-chat").splitlines()
        if p.strip()
    }
    ignored: set[str] = set()
    untracked: set[str] = set()
    for line in git(
        "status", "--porcelain", "--ignored=matching", "--", "apps/agent-chat"
    ).splitlines():
        if line.startswith("!! "):
            ignored.add(Path(line[3:].strip()).relative_to("apps/agent-chat").as_posix())
        elif line.startswith("?? "):
            untracked.add(Path(line[3:].strip()).relative_to("apps/agent-chat").as_posix())
    return {"tracked": tracked, "ignored": ignored, "untracked": untracked}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class FileEntry(TypedDict):
    bytes: int
    sha256: str
    origin: str  # "tracked" | "ignored" | "untracked" (see provenance())


def _classify(rel: str, origins: dict[str, set[str]]) -> str:
    for origin in ("tracked", "ignored", "untracked"):
        bucket = origins[origin]
        if rel in bucket:
            return origin
        # git collapses fully-ignored directories to the dir path — treat any
        # path under a listed dir as that origin
        if any(rel.startswith(parent + "/") for parent in bucket):
            return origin
    return "untracked"


def collect_files(origins: dict[str, set[str]]) -> dict[str, FileEntry]:
    files: dict[str, FileEntry] = {}
    for path in sorted(APP.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(APP).as_posix()
        parts = set(path.relative_to(APP).parts[:-1])
        if parts & EXCLUDE_DIRS:
            continue
        if path.name in EXCLUDE_FILES or path.suffix in EXCLUDE_SUFFIXES:
            continue
        if any(rel.startswith(p) for p in EXCLUDE_PREFIXES):
            continue
        files[rel] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "origin": _classify(rel, origins),
        }
    return files


def previous_export() -> "tuple[Path, dict[str, Any]] | None":
    if not OUT_DIR.exists():
        return None
    metas = sorted(OUT_DIR.glob("*.status.json"))
    if not metas:
        return None
    latest = metas[-1]
    return latest, json.loads(latest.read_text())


def diff_against(prev: dict[str, Any], files: dict[str, FileEntry]) -> list[str]:
    prev_files = prev.get("files", {})
    if not isinstance(prev_files, dict):
        prev_files = {}
    added = sorted(set(files) - set(prev_files))
    removed = sorted(set(prev_files) - set(files))
    changed = sorted(
        p for p in set(files) & set(prev_files) if files[p]["sha256"] != prev_files[p]["sha256"]
    )
    lines = []
    if added:
        lines.append(
            f"added ({len(added)}): " + ", ".join(added[:10]) + (" …" if len(added) > 10 else "")
        )
    if removed:
        lines.append(
            f"removed ({len(removed)}): "
            + ", ".join(removed[:10])
            + (" …" if len(removed) > 10 else "")
        )
    if changed:
        lines.append(
            f"changed ({len(changed)}): "
            + ", ".join(changed[:10])
            + (" …" if len(changed) > 10 else "")
        )
    if not lines:
        lines.append("no file changes since the previous export")
    prev_sha = prev.get("git_sha")
    cur_sha = git("rev-parse", "HEAD")
    if prev_sha and prev_sha != cur_sha:
        log = git("log", "--oneline", f"{prev_sha[:7]}..{cur_sha}")
        if log:
            lines.append(f"commits since previous export ({prev_sha[:7]}..{cur_sha[:7]}):")
            lines.extend(f"  {line}" for line in log.splitlines())
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-diff", action="store_true", help="skip the diff against the previous export"
    )
    parser.add_argument("--list", action="store_true", help="list existing exports and exit")
    args = parser.parse_args()

    if args.list:
        prev = previous_export()
        if not prev:
            print("no exports yet")
            return 0
        for meta_path in sorted(OUT_DIR.glob("*.status.json")):
            d = json.loads(meta_path.read_text())
            print(
                f"v{d['version']} {d['created_at']} {d['git_sha'][:7]}"
                f"{'-dirty' if d['dirty'] else ''} {d['file_count']} files {d['total_bytes']} B"
            )
        return 0

    try:
        origins = provenance()
        files = collect_files(origins)
        sha = git("rev-parse", "HEAD")
        porcelain = git("status", "--porcelain")
    except ExportError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    dirty_files = [line.strip() for line in porcelain.splitlines() if line.strip()]
    origin_counts = {
        origin: sum(1 for f in files.values() if f["origin"] == origin)
        for origin in ("tracked", "ignored", "untracked")
    }
    prev = previous_export()
    prev_meta: dict[str, Any] | None = prev[1] if prev else None
    version = (int(prev_meta["version"]) + 1) if prev_meta else 1
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    zip_name = f"agent-chat-v{version}-{stamp}-{sha[:7]}{'-dirty' if dirty_files else ''}.zip"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUT_DIR / zip_name
    total_bytes = sum(int(f["bytes"]) for f in files.values())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            zf.write(APP / rel, arcname=f"agent-chat/{rel}")
        meta = {
            "version": version,
            "zip": zip_name,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "git_sha": sha,
            "dirty": bool(dirty_files),
            "dirty_files": dirty_files,
            "payload_origins": origin_counts,
            "excludes": sorted(EXCLUDE_DIRS | EXCLUDE_FILES) + list(EXCLUDE_PREFIXES),
            "file_count": len(files),
            "total_bytes": total_bytes,
            "files": files,
        }
        zf.writestr("STATUS.json", json.dumps(meta, indent=2))

    (OUT_DIR / f"{zip_path.stem}.status.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"export -> {zip_path.relative_to(REPO)}")
    summary = (
        f"  v{version} | {sha[:7]}{'-dirty' if dirty_files else ''} | "
        f"{len(files)} files | {total_bytes / 1024:.0f} KiB | "
        f"origins: {origin_counts['tracked']} tracked / "
        f"{origin_counts['ignored']} ignored / {origin_counts['untracked']} untracked"
    )
    print(summary)
    if dirty_files:
        print(
            f"  WARNING: {len(dirty_files)} uncommitted change(s) at export time; "
            "the SHA is not a faithful label"
        )

    if not args.no_diff and prev_meta is not None and int(prev_meta.get("version", 0)) < version:
        print("  diff vs previous export:")
        for line in diff_against(prev_meta, files):
            print(f"    {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
