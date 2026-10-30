#!/usr/bin/env python3
"""Verify the single-source short copy across public surfaces.

The story's ``short_version`` is the single plain-text source for short copy
(scripts/gen_story_short.py bakes it into apps/showcase-web/src/lib/storyShort.ts).
This checker fails while any consumer surface drifts from it:

- README.md — Projects table, per-project "Highlights" cell
- README.md — "Selected results" table, per-project row
- docs/projects/index.md — per-project "Impact in one line" cell
- docs/projects/<id>.md — the opening blockquote

Containment is checked on whitespace-normalized text, so re-wrapping the
markdown does not false-positive; any real wording drift does. Nothing is
ever written — ``--check`` is the explicit CI mode (exit 1 on any mismatch),
mirroring scripts/gen_static_registry.py:

    uv run python scripts/check_short_copy.py --check
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from portfolio_core.story import load_story
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_ROOT = ROOT / "projects"
README = ROOT / "README.md"
DOCS_PROJECTS_INDEX = ROOT / "docs" / "projects" / "index.md"
DOCS_PROJECTS_DIR = ROOT / "docs" / "projects"

_WS = re.compile(r"\s+")


def norm(text: str) -> str:
    """Collapse whitespace so markdown wrapping/reflow cannot hide drift."""
    return _WS.sub(" ", text).strip()


@dataclass
class Surface:
    """One place a project's short_version must appear verbatim."""

    label: str
    haystack: str

    def contains(self, short_version: str) -> bool:
        return norm(short_version) in norm(self.haystack)


def short_versions() -> dict[str, str]:
    """project id → short_version, sorted (same loader as gen_story_short)."""
    if not PROJECTS_ROOT.is_dir():
        sys.exit(f"check_short_copy: {PROJECTS_ROOT} not found")
    out: dict[str, str] = {}
    for d in sorted(PROJECTS_ROOT.iterdir()):
        if not d.is_dir() or not (d / "story.yaml").exists():
            continue
        try:
            story = load_story(d)
        except ValidationError as e:
            sys.exit(f"check_short_copy: {d.name}/story.yaml fails validation: {e}")
        if story is not None:
            if story.short_version is None:
                sys.exit(f"check_short_copy: {story.project_id} has no short_version")
            out[story.project_id] = story.short_version
    return out


def readme_highlights_row(readme: str, project_id: str) -> Surface | None:
    """The Projects-table row that links to this project (Highlights cell)."""
    for line in readme.splitlines():
        if f"](projects/{project_id}/)" in line:
            return Surface(f"README.md projects row ({project_id})", line)
    return None


def readme_results_row(readme: str, project_id: str) -> Surface | None:
    """The Selected-results row keyed by the project number ("| 01 ...")."""
    num = project_id.split("-", 1)[0]
    in_results = False
    for line in readme.splitlines():
        if line.startswith("## "):
            in_results = line.strip() == "## Selected results"
            continue
        if in_results and re.match(rf"\|\s*{num}\s+", line):
            return Surface(f"README.md selected-results row ({project_id})", line)
    return None


def docs_index_row(index: str, project_id: str) -> Surface | None:
    num = project_id.split("-", 1)[0]
    for line in index.splitlines():
        if re.match(rf"\|\s*{num}\s*\|", line) and f"({project_id}.md)" in line:
            return Surface(f"docs/projects/index.md row ({project_id})", line)
    return None


def docs_opening_blockquote(page: str, project_id: str) -> Surface | None:
    """The page's opening blockquote: the first run of '>'-prefixed lines."""
    quote: list[str] = []
    for line in page.splitlines():
        if line.startswith(">"):
            quote.append(line.removeprefix(">").lstrip())
        elif quote:
            break
    if quote:
        return Surface(f"docs/projects/{project_id}.md opening", "\n".join(quote))
    return None


def collect(sv: dict[str, str]) -> list[tuple[str, Surface | None]]:
    readme = README.read_text(encoding="utf-8")
    index = DOCS_PROJECTS_INDEX.read_text(encoding="utf-8")
    surfaces: list[tuple[str, Surface | None]] = []
    for pid in sv:
        page_path = DOCS_PROJECTS_DIR / f"{pid}.md"
        page = page_path.read_text(encoding="utf-8") if page_path.exists() else None
        surfaces.append((pid, readme_highlights_row(readme, pid)))
        surfaces.append((pid, readme_results_row(readme, pid)))
        surfaces.append((pid, docs_index_row(index, pid)))
        surfaces.append(
            (pid, docs_opening_blockquote(page, pid) if page is not None else None),
        )
    return surfaces


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="CI mode: exit 1 on any mismatch (this script never writes)",
    )
    parser.parse_args()

    sv = short_versions()
    violations: list[str] = []
    checked = 0
    for pid, surface in collect(sv):
        if surface is None:
            violations.append(f"{pid}: surface missing (row/blockquote not found)")
            continue
        checked += 1
        if not surface.contains(sv[pid]):
            violations.append(f"{pid}: {surface.label} does not contain the short_version")

    if violations:
        for v in violations:
            print(f"error: {v}", file=sys.stderr)
        print(
            f"short-copy check FAILED: {len(violations)} violation(s) across "
            f"{len(sv)} stories ({checked} surfaces checked)",
            file=sys.stderr,
        )
        return 1
    print(f"short copy is single-sourced ({checked} surfaces across {len(sv)} stories)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
