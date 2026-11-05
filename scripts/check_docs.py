#!/usr/bin/env python3
"""Documentation gate (docs-as-code): relative markdown links must resolve to
an existing file or heading anchor; fenced code blocks must carry a language
tag; /glossary#slug anchors referenced from apps/showcase-web/src must exist
in the glossary data.

Surfaces: README.md, projects/*/README.md, docs/**/*.md.

Run: uv run python scripts/check_docs.py
"""

import json
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parents[1]

DOC_FILES = [
    REPO / "README.md",
    *sorted((REPO / "projects").glob("*/README.md")),
    *sorted((REPO / "docs").rglob("*.md")),
]

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SKIP_SCHEME_RE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)
GLOSSARY_ANCHOR_RE = re.compile(r"/glossary#(?!<)([a-z0-9][a-z0-9-]*)")
# "/glossary#slug" (the literal word) is a placeholder in prose and comments,
# never a real anchor — the regex above already skips "#<slug>".
PLACEHOLDER_SLUGS = {"slug"}


def github_slug(heading: str) -> str:
    """GitHub-style heading anchor: lowercase, punctuation stripped, spaces -> hyphens."""
    text = unicodedata.normalize("NFKD", heading)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", "-", text, flags=re.UNICODE).strip("-")


def heading_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    for line in path.read_text().splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        base = github_slug(m.group(2))
        if not base:
            continue
        n = seen.get(base, 0)
        seen[base] = n + 1
        anchors.add(base if n == 0 else f"{base}-{n}")
    return anchors


def fenced_spans(text: str) -> list[tuple[int, int]]:
    """(start_line, end_line) 1-based spans of fenced code blocks."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for i, line in enumerate(text.splitlines(), 1):
        if start is None:
            if line.lstrip().startswith("```"):
                start = i
        elif line.rstrip().startswith("```"):
            spans.append((start, i))
            start = None
    if start is not None:
        spans.append((start, 10**9))  # unclosed fence: everything after is code
    return spans


def check_links() -> list[str]:
    problems: list[str] = []
    anchor_cache: dict[Path, set[str]] = {}
    for f in DOC_FILES:
        rel = f.relative_to(REPO)
        lines = f.read_text().splitlines()
        code = fenced_spans("\n".join(lines))
        for lineno, line in enumerate(lines, 1):
            if any(a <= lineno <= b for a, b in code):
                continue  # link syntax inside fenced code is not a link
            for m in LINK_RE.finditer(line):
                url = unquote(m.group(1)).strip()
                if SKIP_SCHEME_RE.match(url):
                    continue
                path_part, _, frag = url.partition("#")
                if not path_part:
                    target = f
                else:
                    target = (f.parent / path_part).resolve()
                    if not str(target).startswith(str(REPO)):
                        problems.append(f"{rel}:{lineno}: link escapes the repo: {url}")
                        continue
                    if target.is_dir():
                        continue
                    if not target.exists():
                        problems.append(f"{rel}:{lineno}: broken link -> {url}")
                        continue
                if frag and target.suffix == ".md":
                    if target not in anchor_cache:
                        anchor_cache[target] = heading_anchors(target)
                    if frag not in anchor_cache[target]:
                        problems.append(f"{rel}:{lineno}: missing anchor #{frag} in {url}")
    return problems


def check_code_fences() -> list[str]:
    problems: list[str] = []
    for f in DOC_FILES:
        rel = f.relative_to(REPO)
        in_fence = False
        for lineno, line in enumerate(f.read_text().splitlines(), 1):
            if not in_fence and line.lstrip().startswith("```"):
                in_fence = True
                if not line.lstrip()[3:].strip():
                    problems.append(f"{rel}:{lineno}: fenced block missing a language tag")
            elif in_fence and line.rstrip().startswith("```"):
                in_fence = False
    return problems


def check_glossary_anchors() -> list[str]:
    glossary_path = REPO / "apps" / "showcase-web" / "src" / "lib" / "glossary.json"
    slugs = {e["slug"] for e in json.loads(glossary_path.read_text())}
    src = REPO / "apps" / "showcase-web" / "src"
    problems: list[str] = []
    for f in sorted(src.rglob("*")):
        if f.suffix not in {".ts", ".tsx"}:
            continue
        rel = f.relative_to(REPO)
        lines = f.read_text().splitlines()
        code = fenced_spans("\n".join(lines))
        for lineno, line in enumerate(lines, 1):
            if any(a <= lineno <= b for a, b in code):
                continue
            for m in GLOSSARY_ANCHOR_RE.finditer(line):
                if m.group(1) in PLACEHOLDER_SLUGS:
                    continue
                if m.group(1) not in slugs:
                    glossary_rel = glossary_path.relative_to(REPO)
                    problems.append(f"{rel}:{lineno}: /glossary#{m.group(1)} not in {glossary_rel}")
    return problems


def collect_errors() -> list[str]:
    return [*check_links(), *check_code_fences(), *check_glossary_anchors()]


if __name__ == "__main__":
    problems = collect_errors()
    if problems:
        for p in problems:
            print("ERROR:", p)
        sys.exit(1)
    print("check-docs: OK")
