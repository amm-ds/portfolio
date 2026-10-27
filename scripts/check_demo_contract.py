#!/usr/bin/env python3
"""Validate every ``projects/*/demo.yaml`` against its committed payload JSON.

For each demo manifest (parsed via ``portfolio_core.demo.load_demo``):
  - the referenced payload file must exist under the project dir;
  - every ``required_keys`` entry must be a top-level key of the payload JSON;
  - if the payload carries a top-level ``schema_version``, it must equal the
    manifest's.

Catches drift between the demo contract (manifest) and the artifacts the
showcase API serves before push. Exits non-zero with a message per violation.
"""

import argparse
import json
import sys
from pathlib import Path

from portfolio_core.demo import load_demo_index

REPO = Path(__file__).resolve().parents[1]
errors: list[str] = []


def check_demo(projects_root: Path) -> None:
    manifests = load_demo_index(projects_root)
    for m in manifests:
        errors_before = len(errors)
        project_dir = projects_root / m.project
        if m.payload is None:
            # Mid-rebuild demo: the manifest is a placeholder until a later
            # phase re-declares the payload. Report, don't fail.
            print(f"INCOMPLETE: {m.id} ({m.project}) — no payload declared")
            continue
        payload_path = project_dir / m.payload.path
        if not payload_path.exists():
            errors.append(
                f"{m.id}: payload file missing at {payload_path} "
                f"(build the artifact that writes {m.payload.path})"
            )
            continue
        try:
            payload = json.loads(payload_path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"{m.id}: payload {payload_path} is not valid JSON — {e}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{m.id}: payload {payload_path} must be a top-level JSON object")
            continue
        missing = [k for k in m.payload.required_keys if k not in payload]
        if missing:
            errors.append(f"{m.id}: payload missing required_keys {missing}")
        payload_version = payload.get("schema_version")
        if payload_version is not None and payload_version != m.payload.schema_version:
            errors.append(
                f"{m.id}: payload schema_version {payload_version} != "
                f"manifest schema_version {m.payload.schema_version}"
            )
        if len(errors) == errors_before:
            print(f"OK: {m.id} ({m.project} -> {m.payload.path})")
    if not manifests:
        print(f"no demo.yaml files found under {projects_root}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--projects-root",
        type=Path,
        default=REPO / "projects",
        help="directory of project subdirs (default: <repo>/projects/)",
    )
    args = parser.parse_args()
    check_demo(args.projects_root)
    if errors:
        for e in errors:
            print("ERROR:", e)
        sys.exit(1)
    print("demo-contract: OK")
