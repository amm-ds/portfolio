#!/usr/bin/env python3
"""Stamp a uniform provenance ``_meta`` block into every committed metrics.json.

External evaluation P2-1: no metrics artifact exposed a machine-checkable
identity (git SHA, lockfile hash, data/params hashes, seed, timestamp). This
generator makes the identity a first-class, versioned contract:

- ``schema_version`` — bump on shape changes
- ``git_sha`` — HEAD at stamp time; the artifact's lineage label
- ``uv_lock_sha256`` — the workspace lockfile the run resolved against
- ``params_sha256`` — the project's params.yaml (null when absent, justified)
- ``data_contract_sha256`` — the pinned dataset contract when one exists
- ``seed`` — top-level ``seed`` from params.yaml (the value the pipeline used)
- ``created_at`` — last git commit date of the metrics file itself, so a
  re-stamp at the same commit is byte-identical (CI can gate on freshness
  exactly like scripts/gen_static_registry.py)

Deterministic: every input is committed state at a given commit. Run after
changing any metrics artifact:

    uv run python scripts/stamp_metrics_meta.py

CI/local contract checks use ``--check`` (exit 1 on any stale block, no writes).
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
UV_LOCK = ROOT / "uv.lock"
SCHEMA_VERSION = 1

_SHA256_RE = __import__("re").compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git(*args: str) -> str:
    proc = subprocess.run(  # noqa: S603 - fixed git binary + static args
        ["/usr/bin/env", "git", *args],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if proc.returncode != 0:
        sys.exit(f"stamp_metrics_meta: git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def metrics_files() -> list[Path]:
    return sorted(p for p in PROJECTS.glob("*/reports*/metrics.json") if p.is_file())


def load_params(path: Path) -> dict[str, Any]:
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except OSError:
        return {}


def block_for(metrics_path: Path, head: str, lock_hash: str) -> dict[str, Any]:
    if metrics_path.parent.name == "reports":
        project_dir = metrics_path.parents[1]
    else:
        project_dir = metrics_path.parents[2]
    params_path = project_dir / "params.yaml"
    params = load_params(params_path)
    seed = params.get("seed")
    created = git("log", "-1", "--format=%cI", "--", str(metrics_path.relative_to(ROOT)))
    return {
        "schema_version": SCHEMA_VERSION,
        "git_sha": head,
        "uv_lock_sha256": lock_hash,
        "params_sha256": sha256_file(params_path),
        "data_contract_sha256": sha256_file(project_dir / "data" / "raw" / "dataset_contract.json"),
        "seed": int(seed) if isinstance(seed, int) else None,
        "created_at": created or None,
    }


def render(metrics_path: Path, head: str, lock_hash: str) -> str:
    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    data["_meta"] = block_for(metrics_path, head, lock_hash)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def validate_block(path: Path, block: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(block, dict):
        return [f"{path}: _meta is not an object"]
    required = {
        "schema_version": int,
        "git_sha": str,
        "uv_lock_sha256": (str, type(None)),
        "params_sha256": (str, type(None)),
        "data_contract_sha256": (str, type(None)),
        "seed": (int, type(None)),
        "created_at": (str, type(None)),
    }
    for key, types in required.items():
        if key not in block:
            problems.append(f"{path}: _meta missing {key!r}")
        elif not isinstance(block[key], types):
            problems.append(f"{path}: _meta.{key} has the wrong type")
    if isinstance(block.get("git_sha"), str) and len(block["git_sha"]) != 40:
        problems.append(f"{path}: _meta.git_sha is not a full SHA")
    for key in ("uv_lock_sha256", "params_sha256", "data_contract_sha256"):
        value = block.get(key)
        if isinstance(value, str) and not _SHA256_RE.match(value):
            problems.append(f"{path}: _meta.{key} is not a sha256 hex digest")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when any committed block differs from a fresh stamp; do not write",
    )
    args = parser.parse_args()

    head = git("rev-parse", "HEAD")
    lock_hash = sha256_file(UV_LOCK)
    files = metrics_files()
    if not files:
        sys.exit("stamp_metrics_meta: no projects/*/reports*/metrics.json found")

    stale: list[str] = []
    problems: list[str] = []
    for path in files:
        fresh = render(path, head, lock_hash or "")
        committed = path.read_text(encoding="utf-8")
        if committed != fresh:
            stale.append(str(path.relative_to(ROOT)))
            if not args.check:
                path.write_text(fresh, encoding="utf-8")
        # validate the stamped content (what ships), not the pre-write read
        block = json.loads(fresh).get("_meta")
        problems.extend(validate_block(path.relative_to(ROOT), block))

    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    if args.check:
        for rel in stale:
            print(
                f"error: {rel} has a stale _meta; run scripts/stamp_metrics_meta.py",
                file=sys.stderr,
            )
        if stale or problems:
            print(
                f"metrics-meta check FAILED: {len(stale)} stale, {len(problems)} invalid "
                f"across {len(files)} artifacts",
                file=sys.stderr,
            )
            return 1
        print(f"metrics-meta: OK ({len(files)} artifacts carry a valid _meta)")
        return 0
    print(f"stamped _meta into {len(files)} artifacts ({len(stale)} changed)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
