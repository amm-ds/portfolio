#!/usr/bin/env python3
"""Bake a static snapshot of the registry into the SPA (index resilience).

Reads projects/*/portfolio.yaml, story.yaml, and demo.yaml through the same
portfolio_core loaders the showcase API uses, and writes
apps/showcase-web/src/lib/staticRegistry.ts. The projects index renders from
this snapshot when both the /projects and /demos endpoints are unreachable
(see ProjectsIndex), and lib/demos.ts derives its offline fallback from it.

Deterministic: projects by (order, id), demos by (group, id), stories by
project_id; no timestamps, so a re-run without source changes produces no
diff (CI can gate on freshness). Story prose is deliberately excluded — only
section/figure/metric structure is baked, both to keep the bundle small and
because the copy-guard test forbids certain wording anywhere under src/.

Regenerate after changing any manifest/story/demo file:

    uv run python scripts/gen_static_registry.py

CI/local contract checks use ``--check`` to reject a stale snapshot without
rewriting it (same pattern as scripts/gen_route_manifest.py).
"""

import argparse
import json
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from portfolio_core.demo import load_demo_index, to_registry_entry
from portfolio_core.manifest import load_index
from portfolio_core.story import load_story
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_ROOT = ROOT / "projects"
OUT = ROOT / "apps" / "showcase-web" / "src" / "lib" / "staticRegistry.ts"

HEADER = """// GENERATED — do not edit.
// Static snapshot of the live registry, baked by scripts/gen_static_registry.py
// from projects/*/portfolio.yaml + story.yaml + demo.yaml (same loaders the
// API uses). Re-run that script after changing any of those files; a re-run
// without changes produces byte-identical output.
"""

TS_TYPES = """
export interface StaticProject {
  id: string;
  title: string;
  domain: string;
  topic: string;
  techniques: string[];
  data: string;
  status: "flagship" | "working" | "planned";
  order: number;
}

/** Structural story summary — section/figure/metric ids only, no prose. */
export interface StaticStorySummary {
  project_id: string;
  section_ids: string[];
  figure_names: string[];
  metrics_keys: string[];
  has_roadmap: boolean;
}

export interface StaticDemoRegistryEntry {
  id: string;
  title: string;
  hook: string;
  group: string;
  href: string;
  project: string;
  status: string;
  hero: { label: string; value: string; ci: string | null } | null;
}
"""


def _section_values(sections: list[object], key: str) -> list[str]:
    return sorted({n for s in sections if isinstance(s, dict) for n in s.get(key, [])})


def story_summary(project_dir: Path) -> dict[str, object] | None:
    """Structural summary of one project's story.yaml, or None when absent.

    Prefers the canonical ``load_story``; when the prose fails full validation
    (e.g. a roadmap item over the 300-char cap — the API 500s there too), falls
    back to lenient structural extraction so the snapshot still carries the
    section/figure/metric structure.
    """
    f = project_dir / "story.yaml"
    if not f.exists():
        return None
    pid = project_dir.name
    try:
        story = load_story(project_dir)
    except ValidationError as e:
        print(
            f"gen_static_registry: warning: {pid}/story.yaml fails full "
            f"validation ({e.error_count()} errors) — using structural fallback",
            file=sys.stderr,
        )
        data = yaml.safe_load(f.read_text())
        sections = data.get("sections") or []
        return {
            "project_id": data.get("project_id", pid),
            "section_ids": [s["id"] for s in sections if isinstance(s, dict) and s.get("id")],
            "figure_names": _section_values(sections, "figures"),
            "metrics_keys": _section_values(sections, "metrics_keys"),
            "has_roadmap": bool(data.get("roadmap")),
        }
    if story is None:
        return None
    return {
        "project_id": story.project_id,
        "section_ids": [s.id for s in story.sections],
        "figure_names": sorted({f for s in story.sections for f in s.figures}),
        "metrics_keys": sorted({k for s in story.sections for k in s.metrics_keys}),
        "has_roadmap": bool(story.roadmap),
    }


def story_summaries() -> list[dict[str, object]]:
    summaries = []
    for d in sorted(PROJECTS_ROOT.iterdir()):
        if not d.is_dir():
            continue
        summary = story_summary(d)
        if summary is not None:
            summaries.append(summary)
    return sorted(summaries, key=lambda s: str(s["project_id"]))


def ts_const(name: str, ts_type: str, value: object) -> str:
    payload = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)
    return f"export const {name}: {ts_type}[] = {payload};\n"


def build() -> str:
    """Render the snapshot TypeScript module (without writing it)."""
    if not PROJECTS_ROOT.is_dir():
        sys.exit(f"gen_static_registry: {PROJECTS_ROOT} not found")
    projects = [m.model_dump() for m in load_index(PROJECTS_ROOT)]
    if not projects:
        sys.exit("gen_static_registry: no projects/*/portfolio.yaml found")
    demos = [to_registry_entry(m) for m in load_demo_index(PROJECTS_ROOT)]

    out = HEADER + TS_TYPES
    out += "\n" + ts_const("STATIC_PROJECTS", "StaticProject", projects)
    out += "\n" + ts_const("STATIC_STORIES", "StaticStorySummary", story_summaries())
    out += "\n" + ts_const("STATIC_DEMO_REGISTRY", "StaticDemoRegistryEntry", demos)
    return out


def stale_error() -> str | None:
    """Error message when the committed snapshot differs from a fresh render."""
    try:
        committed = OUT.read_text(encoding="utf-8")
    except OSError as e:
        return f"cannot read {OUT}: {e}"
    if committed != build():
        return f"{OUT} is stale; run scripts/gen_static_registry.py"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed snapshot is stale; do not write",
    )
    args = parser.parse_args()

    if args.check:
        err = stale_error()
        if err is not None:
            print(f"error: {err}", file=sys.stderr)
            return 1
        print(f"static registry is current ({OUT})")
        return 0

    out = build()
    OUT.write_text(out, encoding="utf-8")
    print(
        f"wrote {OUT} ({len(load_index(PROJECTS_ROOT))} projects, "
        f"{len(load_demo_index(PROJECTS_ROOT))} demos, {out.encode('utf-8').__len__()} bytes)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
