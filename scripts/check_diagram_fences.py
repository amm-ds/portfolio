#!/usr/bin/env python3
"""Diagram-fence resolution gate.

Every ```diagram <id>``` fence in a project article (projects/*/story.yaml)
must name a spec registered in the web app's diagram registry
(apps/showcase-web/src/diagrams/index.ts, which spreads the auto registry in
apps/showcase-web/src/diagrams/auto/index.ts). An unregistered id renders the
"Unknown diagram spec." fallback box on the live article, which is how project
15 shipped without its five diagrams.

The web app's vitest suite runs the same check against the real TypeScript
registry (src/__tests__/diagramSpecs.test.ts); this script is the
no-node repo gate.

Exit codes: 0 every fence resolves; 1 at least one fence does not.

Run: uv run python scripts/check_diagram_fences.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = ROOT / "apps" / "showcase-web" / "src" / "diagrams"
REGISTRY_FILES = (DIAGRAMS / "index.ts", DIAGRAMS / "auto" / "index.ts")

FENCE_RE = re.compile(r"^[ \t]*```diagram[ \t]+([A-Za-z0-9_-]+)[ \t]*$", re.MULTILINE)
# Registry entries look like `  "13-serving-pipeline": SERVING_PIPELINE_SPEC,`.
ENTRY_RE = re.compile(r'^[ \t]*"([A-Za-z0-9_-]+)":[ \t]*[A-Z][A-Z0-9_]*,', re.MULTILINE)


def registered_ids(registry_files: tuple[Path, ...] = REGISTRY_FILES) -> set[str]:
    ids: set[str] = set()
    for path in registry_files:
        ids.update(ENTRY_RE.findall(path.read_text(encoding="utf-8")))
    return ids


def fence_refs(projects_dir: Path = ROOT / "projects") -> list[tuple[str, str]]:
    """(story path relative to the repo, diagram id) for every fence, in file order."""
    refs: list[tuple[str, str]] = []
    for story in sorted(projects_dir.glob("*/story.yaml")):
        rel = str(story.relative_to(projects_dir.parent))
        refs.extend((rel, spec_id) for spec_id in FENCE_RE.findall(story.read_text("utf-8")))
    return refs


def unresolved(refs: list[tuple[str, str]], ids: set[str]) -> list[str]:
    return [
        f"{story}: ```diagram {spec_id}``` is not registered"
        for story, spec_id in refs
        if spec_id not in ids
    ]


def main() -> int:
    ids = registered_ids()
    refs = fence_refs()
    failures = unresolved(refs, ids)
    print(
        f"diagram-fences: {len(refs)} fences, {len(ids)} registered specs, "
        f"{len(failures)} unresolved"
    )
    for failure in failures:
        print(f"  error: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
