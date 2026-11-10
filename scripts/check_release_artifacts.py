#!/usr/bin/env python3
"""Release-artifact contract gate.

Two checks, both learned from real gaps (external audits, 2026-11):

1. **Artifact completeness** — every shipped project (a ``projects/NN-*``
   directory whose ``portfolio.yaml`` is not marked ``planned``) must expose
   the artifacts the showcase API serves and the release notes promise:
   ``reports/metrics.json``, ``story.yaml``, and ``reports/report.html``.
   Projects 11/12 failed this for days because per-project .gitignore files
   silently excluded the artifacts from git (fixed in v1.1.0) — this gate
   keeps that failure mode impossible.
2. **12→13 feature contract** — project 13 serves project 12's champion
   behind a request schema that mirrors 12's exported feature selection.
   The ``selected`` list must match between the two committed contracts;
   today nothing fails when 12's schema drifts without regenerating 13.

Run: uv run python scripts/check_release_artifacts.py
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROJECTS = REPO / "projects"

REQUIRED = ("reports/metrics.json", "story.yaml", "reports/report.html")


def check_completeness() -> list[str]:
    problems: list[str] = []
    for project in sorted(PROJECTS.iterdir()):
        if not project.is_dir() or not project.name[:2].isdigit():
            continue
        manifest = project / "portfolio.yaml"
        if not manifest.exists() or "planned" in manifest.read_text():
            continue
        for rel in REQUIRED:
            if not (project / rel).exists():
                problems.append(f"{project.name}: missing {rel}")
    return problems


def check_12_13_contract() -> list[str]:
    c12_path = PROJECTS / "12-tabular-ml-lifecycle" / "data" / "feature_selection.json"
    c13_path = PROJECTS / "13-model-serving" / "data" / "models" / "feature_contract.json"
    problems: list[str] = []
    if not c12_path.exists() or not c13_path.exists():
        return [f"missing contract file: {c12_path if not c12_path.exists() else c13_path}"]
    selected_12 = json.loads(c12_path.read_text()).get("selected")
    selected_13 = json.loads(c13_path.read_text()).get("selected")
    if not selected_12 or not selected_13:
        problems.append("one of the contracts carries no 'selected' feature list")
    elif selected_12 != selected_13:
        only_12 = [c for c in selected_12 if c not in selected_13]
        only_13 = [c for c in selected_13 if c not in selected_12]
        problems.append(f"12→13 feature contract drift: only in 12 {only_12 or '—'}")
        problems.append(f"12→13 feature contract drift: only in 13 {only_13 or '—'}")
    return problems


def main() -> int:
    problems = [*check_completeness(), *check_12_13_contract()]
    if problems:
        for p in problems:
            print("ERROR:", p)
        return 1
    print("release-artifacts: OK (all shipped projects complete; 12→13 contract in sync)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
