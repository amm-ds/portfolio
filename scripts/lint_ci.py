#!/usr/bin/env python3
"""Validate CI workflow files and Makefile consistency (catches the class of bug
that broke ci.yml in wave 13 — unquoted colons in step names — before push)."""

import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
errors: list[str] = []


def check_workflows() -> None:
    for f in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        try:
            yaml.safe_load(f.read_text())
        except yaml.YAMLError as e:
            errors.append(f"{f.name}: invalid YAML — {e}")
    if not errors:
        print("workflows: all parse OK")


def check_makefile() -> None:
    mk = (REPO / "Makefile").read_text()
    phony = set()
    for m in re.finditer(r"^\.PHONY:\s*(.+)$", mk, re.M):
        phony.update(m.group(1).split())
    for m in re.finditer(r"^([a-z][a-z0-9-]*):", mk, re.M):
        target = m.group(1)
        if target not in phony:
            errors.append(f"Makefile: target '{target}' missing from .PHONY")
    print(f"makefile: {len(phony)} phony targets checked")


if __name__ == "__main__":
    check_workflows()
    check_makefile()
    if errors:
        for e in errors:
            print("ERROR:", e)
        sys.exit(1)
    print("lint-ci: OK")
