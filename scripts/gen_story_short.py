#!/usr/bin/env python3
"""Bake story ``short_version`` values into the SPA (short-copy platform).

Reads projects/*/story.yaml through the same ``portfolio_core.story`` loader
the showcase API uses and writes apps/showcase-web/src/lib/storyShort.ts —
the generated map lib/impact.ts reads so card summaries and og: descriptions
(served via summaryLine) come from the single plain-text source each story
declares (card/README/docs/SEO/social copy).

Deterministic: projects by id, no timestamps — a re-run without source
changes produces no diff. Strict in two ways: a story that fails full
validation aborts the run, and ``--check`` fails while any authored story
still lacks a ``short_version`` (the content phase populates them) — the map
itself carries ``null`` for those so the build keeps working in the meantime.

Regenerate after editing any story.yaml:

    uv run python scripts/gen_story_short.py

CI/local contract checks use ``--check`` to reject a stale or incomplete map
without rewriting it (same pattern as scripts/gen_static_registry.py).
"""

import argparse
import json
import sys
from pathlib import Path

from portfolio_core.story import load_story
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_ROOT = ROOT / "projects"
OUT = ROOT / "apps" / "showcase-web" / "src" / "lib" / "storyShort.ts"

HEADER = """// GENERATED — do not edit.
// Map of project id → story.yaml `short_version`, baked by
// scripts/gen_story_short.py (same loader the showcase API uses). This is the
// single plain-text source for card/README/docs/SEO/social short copy
// (portfolio_core.story.ProjectStory.short_version); lib/impact.ts reads it.
// Re-run that script after changing any story.yaml; a re-run without changes
// produces byte-identical output.
"""


def short_map() -> dict[str, str | None]:
    """project id → short_version (None while not authored yet), sorted."""
    if not PROJECTS_ROOT.is_dir():
        sys.exit(f"gen_story_short: {PROJECTS_ROOT} not found")
    out: dict[str, str | None] = {}
    for d in sorted(PROJECTS_ROOT.iterdir()):
        if not d.is_dir() or not (d / "story.yaml").exists():
            continue
        try:
            story = load_story(d)
        except ValidationError as e:
            sys.exit(f"gen_story_short: {d.name}/story.yaml fails validation: {e}")
        if story is not None:
            out[story.project_id] = story.short_version
    return out


def missing_short_versions(entries: dict[str, str | None]) -> list[str]:
    return sorted(pid for pid, sv in entries.items() if sv is None)


def build() -> str:
    """Render the map module (without writing it)."""
    payload = json.dumps(short_map(), indent=2, ensure_ascii=False, sort_keys=True)
    return HEADER + f"\nexport const STORY_SHORT: Record<string, string | null> = {payload};\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed map is stale or any story lacks short_version; do not write",
    )
    args = parser.parse_args()

    entries = short_map()
    missing = missing_short_versions(entries)

    if args.check:
        try:
            committed = OUT.read_text(encoding="utf-8")
        except OSError as e:
            print(f"error: cannot read {OUT}: {e}", file=sys.stderr)
            return 1
        if committed != build():
            print("error: storyShort.ts is stale; run scripts/gen_story_short.py", file=sys.stderr)
            return 1
        if missing:
            print(
                "error: short_version missing for: " + ", ".join(missing),
                file=sys.stderr,
            )
            return 1
        print(f"story short map is current ({OUT})")
        return 0

    OUT.write_text(build(), encoding="utf-8")
    if missing:
        print(
            "warning: short_version missing for: "
            + ", ".join(missing)
            + " (map carries null; --check fails until the content phase writes them)",
            file=sys.stderr,
        )
    print(f"wrote {OUT} ({len(entries)} stories, {len(missing)} without short_version)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
