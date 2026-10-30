#!/usr/bin/env python3
"""Plain-language lint for the case-study stories (projects/*/story.yaml).

The case studies are the public face of the portfolio; this gate keeps their
prose plain, timeless, and free of repo-process narrative. Stdlib-only on
purpose: no PyYAML (so duplicate top-level keys, which PyYAML silently
overwrites, must be caught by a line scan) and no textstat (Flesch is a local
heuristic). Exit code is 1 when any ERROR-level finding exists; warnings are
reported but never fail the gate.

Checks (per story.yaml):
  ERROR   duplicate top-level YAML key (line scan; PyYAML would silently keep
          the last one, dropping a section or caption block)
  ERROR   first section (background) over FIRST_SECTION_WORD_CAP words — the
          opening must stay skimmable
  ERROR   more than one summary-card marker in a section, or a marker that does
          not open the section's final paragraph (StorySection.tsx renders the
          trailing marker paragraph as the takeaway card; the renderer takes
          the LAST marker, so anything after an earlier one is swallowed)
  ERROR   more than 3 figure cards in a section — the showcase renders at most
          3 per section; move the rest or express them as prose diagrams
  ERROR   changelog/wave narrative ("run and wave record", "wave 15",
          "wave-2", "changelog") in the main sections, or in conclusions
          before the `### Revision notes` heading — revision history belongs
          in that subsection only
  ERROR   bare "pp" for percentage points — write "pp." (a bare "pp" reads as
          "pages"); "pp." is a protected token for sentence splitting
  WARNING section with no figure and no mermaid diagram — every section should
          carry a visual (story template: at least one per section)
  WARNING glossary term (apps/showcase-web/src/lib/glossary.json) used in
          section prose but never in a position the renderer auto-links
          (all its occurrences are inside code spans/fenced blocks, which
          lib/markdown.tsx never links) — its first use stays unlinked
  WARNING section word budget (main sections) and main-thread total budget
          (all main sections combined; conclusions is collapsed <details>)
  WARNING Flesch reading ease below FLESCH_MIN in a main section
  WARNING glossary term (apps/showcase-web/src/lib/glossary.json) used in
          section prose but never in a position the renderer auto-links
          (all its occurrences are inside code spans/fenced blocks, which
          lib/markdown.tsx never links) — its first use stays unlinked
  WARNING section word budget (main sections) and main-thread total budget
          (all main sections combined; conclusions is collapsed <details>)
  WARNING Flesch reading ease below FLESCH_MIN in a main section

Reading ease is the Flesch formula (206.835 - 1.015*W/S - 84.6*Sy/W) over
markdown-stripped prose, with sentences split on protected tokens (decimals,
versions, URLs, "e.g."/"i.e."/"vs."/"pp."/…, ellipses) so measurements and
abbreviations do not inflate the sentence count. Syllables are a vowel-group
heuristic. Both are heuristics — the gate treats them as advisory (warnings).

Usage:
    uv run python scripts/lint_story_language.py            # lint all stories
    uv run python scripts/lint_story_language.py --projects-root PATH
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECTS_ROOT = REPO_ROOT / "projects"
GLOSSARY_JSON = REPO_ROOT / "apps" / "showcase-web" / "src" / "lib" / "glossary.json"

# --- budgets and thresholds ---------------------------------------------------
FIRST_SECTION_WORD_CAP = 150  # hard cap (error) on the opening section
SECTION_WORD_BUDGET = 550  # soft per-section budget (warning), main sections
MAIN_THREAD_WORD_BUDGET = 2600  # soft total across main sections (warning);
# ~a ten-minute read for the always-visible thread (conclusions is collapsed)
FLESCH_MIN = 45.0  # per-section reading-ease floor (warning)

#: Trailing takeaway markers (StorySection.tsx renders the final marker paragraph
#: as the section's summary card). New stories standardize on the business form.
CARD_MARKERS = ("**business summary:**", "**in plain terms:**")
CHANGELOG_SECTION = "conclusions"  # wave/changelog narrative lives in revision notes
REVISION_NOTES_HEADING_RE = re.compile(
    r"^#{2,6}\s*revision notes\s*$", re.MULTILINE | re.IGNORECASE
)

#: Changelog phrasing that must stay inside conclusions (revision-history home).
BANNED_CHANGELOG_RE = re.compile(
    r"\b(?:run and wave record|revision and wave record|changelog)\b"
    r"|\bwave\s*-?\s*\d+\b",
    re.IGNORECASE,
)

#: A dotted "pp." is protected by the sentence splitter; a bare "pp" is an error.
PP_BARE_RE = re.compile(r"\bpp\b(?!\.)")

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['\u2019\-][A-Za-z0-9]+)*")
_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+")

# --- markdown → prose ---------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*```", re.MULTILINE)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[([^]]*)\]\([^)]*\)")
_LINK_RE = re.compile(r"\[([^]]*)\]\([^)]*\)")
_CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
_INLINE_MD_RE = re.compile(r"(\*\*|__|\*|_|~~)(.*?)\1")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+", re.MULTILINE)
_UL_ITEM_RE = re.compile(r"^\s*[-*]\s+", re.MULTILINE)
_OL_ITEM_RE = re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE)
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$", re.MULTILINE)
_HR_RE = re.compile(r"^\s*(?:-{3}|\*{3}|_{3})\s*$", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^\s*>\s?", re.MULTILINE)


def blank_fenced_blocks(md: str) -> str:
    """Replace fenced code blocks (``` … ```, incl. mermaid) with blank lines.

    The renderer never auto-links glossary terms inside them, and they are not
    prose for word/sentence statistics. Line structure is preserved so line
    numbers in findings stay meaningful.
    """
    lines = md.split("\n")
    out = list(lines)
    in_fence = False
    for i, line in enumerate(lines):
        if _FENCE_RE.match(line):
            out[i] = ""
            in_fence = not in_fence
        elif in_fence:
            out[i] = ""
    return "\n".join(out)


def strip_markdown(md: str) -> str:
    """Reduce story markdown to reader-visible prose (best effort, heuristic)."""
    text = blank_fenced_blocks(md)
    text = _HTML_COMMENT_RE.sub(" ", text)
    text = _IMAGE_RE.sub(" ", text)  # figures carry captions; alt text is not prose
    text = _LINK_RE.sub(r"\1", text)  # keep link text, drop the URL
    text = _CODE_SPAN_RE.sub(" ", text)  # inline code is not prose
    text = _INLINE_MD_RE.sub(r"\2", text)
    text = _HEADING_RE.sub("", text)
    text = _TABLE_SEP_RE.sub(" ", text)
    text = _HR_RE.sub(" ", text)
    text = _UL_ITEM_RE.sub("", text)
    text = _OL_ITEM_RE.sub("", text)
    text = _BLOCKQUOTE_RE.sub("", text)
    return text


def prose_words(md: str) -> list[str]:
    """Word tokens of the reader-visible prose."""
    return _WORD_RE.findall(strip_markdown(md))


# --- sentence splitting with protected tokens ---------------------------------

#: Tokens masked whole before the split (their periods can never end a sentence):
#: URLs, "e.g."/"i.e."/"U.S.", abbreviations directly before a number ("vs. 0.68"),
#: decimals, versions, ellipses.
_PROTECTED_RE = re.compile(
    r"https?://[^\s<>)\"\]]+"  # URLs
    r"|\b(?:e\.g|i\.e)\."  # never sentence-final in this corpus
    r"|\bU\.S\."
    r"|\b(?:vs|pp|etc|no|fig|approx|ca|dr|mr|mrs|st)\.\s+(?=\d)"  # abbr. before a number
    r"|\bv?\d+(?:\.\d+)+(?:[A-Za-z]+)?\b"  # decimals & versions: 0.831, 0.40.12, v1.2.3
    r"|\.\.\."
    r"|…",
    re.IGNORECASE,
)

#: Remaining dotted abbreviations mask their letters only, keeping the period so
#: it can still end a sentence ("…2 pp. The next…" must split before "The").
_ABBREV_LETTERS_RE = re.compile(r"\b(?:vs|pp|etc|no|fig|approx|ca|dr|mr|mrs|st)\b", re.IGNORECASE)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])[*_]*\s+(?=[\"'\u201c\u2018*>_A-Z0-9])")
_SENTENCE_EDGE_RE = re.compile(r"^[\s\"'\u201c\u201d\u2018\u2019*>_\-\u2013\u2014]+")
_TRAILING_MD_RE = re.compile(r"(?<=[.!?])[*_]+$")
_PLACEHOLDER_RE = re.compile(r"\x00#(\d+)\x00")


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences without breaking on protected tokens."""
    masked: list[str] = []

    def _mask(m: re.Match[str]) -> str:
        masked.append(m.group(0))
        return f" \x00#{len(masked) - 1}\x00 "

    protected = _ABBREV_LETTERS_RE.sub(_mask, _PROTECTED_RE.sub(_mask, text))
    sentences = []
    for part in _SENTENCE_SPLIT_RE.split(protected):
        s = _TRAILING_MD_RE.sub("", _SENTENCE_EDGE_RE.sub("", part)).strip()
        s = _PLACEHOLDER_RE.sub(lambda m: masked[int(m.group(1))], s)
        s = re.sub(r"\s+", " ", s).strip()
        # masking pads placeholders with spaces; a space before terminal
        # punctuation is never legitimate prose, so glue it back ("pp ." → "pp.")
        s = re.sub(r"\s+(\.\.\.|\.|!|\?)", r"\1", s)
        if not re.search(r"[A-Za-z0-9]", s):
            continue  # punctuation-only fragment
        sentences.append(s)
    return sentences


# --- Flesch reading ease (local heuristic) ------------------------------------


def count_syllables(word: str) -> int:
    """Vowel-group syllable heuristic with a trailing silent-e adjustment."""
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = len(_VOWEL_GROUP_RE.findall(w))
    if len(w) > 3 and w.endswith("e") and not w.endswith(("le", "ee", "ye")):
        groups -= 1
    return max(groups, 1)


def flesch_ease(text: str) -> float | None:
    """Flesch reading ease over prose; None when there is too little to score."""
    sentences = split_sentences(text)
    words = _WORD_RE.findall(text)
    if len(sentences) < 2 or len(words) < 25:
        return None
    syllables = sum(count_syllables(w) for w in words)
    return 206.835 - 1.015 * len(words) / len(sentences) - 84.6 * syllables / len(words)


# --- stdlib-only story.yaml access --------------------------------------------

_TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s|$)")
_SECTION_ITEM_RE = re.compile(r"^(\s*)-\s+id:\s*([A-Za-z0-9_-]+)\s*$")
_TEXT_MD_RE = re.compile(r"^(\s*)text_md:\s*(.*?)\s*$")
_FIGURES_KEY_RE = re.compile(r"^(\s*)figures:\s*(.*?)\s*$")
_FIGURE_ITEM_RE = re.compile(r"^\s*-\s+(\S.*?)\s*$")
_BLOCK_SCALAR_RE = re.compile(r"^([|>])([+-]?)$")
_DOC_MARK_RE = re.compile(r"^\s*(?:---|\.\.\.)\s*$")


@dataclass
class ParsedStory:
    """What the lint needs from a story.yaml: ordered section prose + figures."""

    section_ids: list[str]
    sections: dict[str, str]  # id → raw markdown (first occurrence wins)
    figures: dict[str, list[str]]  # id → figure names (first occurrence wins)


def duplicate_top_level_keys(raw: str) -> list[tuple[str, int]]:
    """Top-level keys appearing more than once, as (key, line) — PyYAML would
    silently keep the last value, so this is a line scan, not a parse."""
    seen: dict[str, None] = {}
    dups: list[tuple[str, int]] = []
    for n, line in enumerate(raw.splitlines(), 1):
        if not line or line[0] in " \t#-" or _DOC_MARK_RE.match(line):
            continue
        m = _TOP_KEY_RE.match(line)
        if m and m.group(1) in seen:
            dups.append((m.group(1), n))
        elif m:
            seen[m.group(1)] = None
    return dups


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_story(raw: str) -> ParsedStory:
    """Minimal stdlib parser for the story.yaml subset the lint reads: the
    ``sections:`` list with its ``text_md`` block scalars and figure lists."""
    section_ids: list[str] = []
    sections: dict[str, str] = {}
    figures: dict[str, list[str]] = {}
    current_id: str | None = None
    i = 0
    lines = raw.splitlines()
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#") or _DOC_MARK_RE.match(line):
            continue
        m = _SECTION_ITEM_RE.match(line)
        if m:
            current_id = m.group(2)
            if current_id not in sections:
                section_ids.append(current_id)
                sections[current_id] = ""
            continue
        if not line.startswith((" ", "\t")):
            if _TOP_KEY_RE.match(line):
                current_id = None  # left the sections list
            continue
        fm = _FIGURES_KEY_RE.match(line)
        if fm and current_id is not None:
            if current_id not in figures:
                names, i = _parse_figures_value(fm.group(2), lines, i, len(fm.group(1)))
                figures[current_id] = names
            continue
        m = _TEXT_MD_RE.match(line)
        if not m or current_id is None:
            continue
        i = _parse_text_md(m, lines, i, sections, current_id)
    return ParsedStory(section_ids, sections, figures)


def _parse_text_md(
    m: re.Match[str], lines: list[str], i: int, sections: dict[str, str], current_id: str
) -> int:
    """Consume a ``text_md:`` value (plain, block `|`, or folded `>`) into
    ``sections[current_id]``; returns the next line index."""
    indent = len(m.group(1))
    value = m.group(2)
    bm = _BLOCK_SCALAR_RE.match(value)
    if not bm:
        sections[current_id] = _unquote(value)
        return i
    style, _chomp = bm.groups()
    block: list[str] = []
    content_indent: int | None = None
    while i < len(lines):
        nxt = lines[i]
        if not nxt.strip():
            block.append("")
            i += 1
            continue
        stripped = len(nxt) - len(nxt.lstrip())
        if stripped <= indent:
            break
        if content_indent is None:
            content_indent = stripped
        block.append(nxt[content_indent:])
        i += 1
    while block and block[-1] == "":
        block.pop()
    sections[current_id] = "\n".join(block) if style == "|" else _fold_lines(block)
    return i


def _parse_figures_value(
    value: str, lines: list[str], i: int, indent: int
) -> tuple[list[str], int]:
    """Figure names after ``figures:`` — flow style (``[a, b]``, possibly on a
    later, more-indented line) or a block list of ``- name`` lines. Returns
    (names, next line)."""
    if value:
        return [_unquote(n.strip()) for n in value.strip("[]").split(",") if n.strip()], i
    # Multi-line flow list: the "[" may open on a subsequent indented line.
    j = i
    while j < len(lines) and not lines[j].strip():
        j += 1
    if (
        j < len(lines)
        and len(lines[j]) - len(lines[j].lstrip()) > indent
        and lines[j].lstrip().startswith("[")
    ):
        acc: list[str] = []
        while j < len(lines):
            acc.append(lines[j].strip())
            if "]" in lines[j]:
                break
            j += 1
        joined = " ".join(acc)
        return [_unquote(n.strip()) for n in joined.strip("[]").split(",") if n.strip()], j + 1
    names: list[str] = []
    while i < len(lines):
        nxt = lines[i]
        if not nxt.strip():
            i += 1
            continue
        stripped = len(nxt) - len(nxt.lstrip())
        if stripped <= indent:
            break
        item = _FIGURE_ITEM_RE.match(nxt)
        if not item:
            break
        names.append(_unquote(item.group(1)))
        i += 1
    return names, i


def _fold_lines(block: list[str]) -> str:
    """Folded scalar (>): join wrapped lines with spaces, keep paragraph breaks."""
    out: list[str] = []
    paragraph: list[str] = []
    for line in [*block, ""]:
        if line == "":
            if paragraph:
                out.append(" ".join(paragraph))
                paragraph = []
        else:
            paragraph.append(line.strip())
    return "\n".join(out)


# --- glossary (mirrors apps/showcase-web/src/lib/markdown.tsx) -----------------


@dataclass
class GlossaryTerm:
    term: str
    slug: str

    @property
    def pattern(self) -> str:
        return re.escape(self.term)


def load_glossary(path: Path) -> list[GlossaryTerm]:
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"lint-story-language: cannot read glossary {path}: {e}")
    terms = [GlossaryTerm(term=e["term"], slug=e["slug"]) for e in entries]
    return sorted(terms, key=lambda t: len(t.term), reverse=True)  # longest first


def glossary_matcher(terms: list[GlossaryTerm]) -> re.Pattern[str]:
    """Combined first-occurrence matcher with the renderer's word boundaries:
    letters/digits/hyphen disallowed on both sides (longest term first)."""
    body = "|".join(t.pattern for t in terms)
    return re.compile(rf"(?<![A-Za-z0-9-])(?:{body})(?![A-Za-z0-9-])", re.IGNORECASE)


def unlinked_glossary_uses(
    text_md: dict[str, str], order: list[str], matcher: re.Pattern[str]
) -> dict[str, str]:
    """Terms whose every occurrence sits in code the renderer never links.

    The showcase app auto-links a glossary term at its first linkable
    occurrence (lib/markdown.tsx, threaded page-wide); occurrences inside
    code spans or fenced blocks are skipped — so a term used only there is
    never linked and its first use stays plain. Returns term → first section.
    """
    linked: set[str] = set()
    unlinked: dict[str, str] = {}
    for sid in order:
        text = blank_fenced_blocks(text_md[sid])
        prose_terms = {m.group(0).lower() for m in matcher.finditer(_CODE_SPAN_RE.sub(" ", text))}
        for m in matcher.finditer(text):
            term = m.group(0).lower()
            if term in prose_terms:
                linked.add(term)
            else:
                unlinked.setdefault(term, sid)
    return {term: sid for term, sid in unlinked.items() if term not in linked}


# --- findings ------------------------------------------------------------------


@dataclass
class Finding:
    level: str  # "ERROR" | "WARNING"
    project: str
    location: str
    rule: str
    message: str

    def line(self) -> str:
        return f"{self.level}: {self.project}: {self.location} [{self.rule}] {self.message}"


def _check_structure(raw: str, parsed: ParsedStory, project: str, errors: list[Finding]) -> None:
    for key, line in duplicate_top_level_keys(raw):
        errors.append(
            Finding(
                "ERROR",
                project,
                f"line {line}",
                "duplicate-key",
                f"top-level key '{key}' is duplicated (PyYAML would silently drop one)",
            )
        )
    if not parsed.section_ids:
        errors.append(Finding("ERROR", project, "file", "parse", "no sections found in story.yaml"))


def _check_summary_card(
    sid: str, text: str, project: str, errors: list[Finding], warnings: list[Finding]
) -> None:
    """Exactly one trailing summary card per section (the renderer takes the
    LAST marker and everything after it as the card). Missing card: warning so
    not-yet-rewritten stories stay green; multiples or a non-final marker: error."""
    low = text.lower()
    count = sum(low.count(m) for m in CARD_MARKERS)
    if count == 0:
        warnings.append(
            Finding(
                "WARNING",
                project,
                f"section {sid}",
                "no-summary-card",
                "section has no trailing **Business summary:** card",
            )
        )
        return
    if count > 1:
        errors.append(
            Finding(
                "ERROR",
                project,
                f"section {sid}",
                "summary-card-count",
                f"{count} summary-card markers; exactly one trailing card per section",
            )
        )
    blocks = re.split(r"\n\s*\n", text.rstrip())
    last = blocks[-1].lower() if blocks else ""
    if not any(m in last for m in CARD_MARKERS):
        errors.append(
            Finding(
                "ERROR",
                project,
                f"section {sid}",
                "summary-card-placement",
                "summary-card marker must open the section's final paragraph block",
            )
        )


def _check_changelog(sid: str, text: str, project: str, out: list[Finding]) -> None:
    if sid == CHANGELOG_SECTION:
        # Allowed inside the collapsed `### Revision notes` subsection only.
        # Stories without that heading are legacy: conclusions as a whole stays
        # the revision-history home (no findings).
        m = REVISION_NOTES_HEADING_RE.search(text)
        if m is None:
            return
        text = text[: m.start()]
    for m in BANNED_CHANGELOG_RE.finditer(text):
        out.append(
            Finding(
                "ERROR",
                project,
                f"section {sid}",
                "changelog-phrase",
                f"changelog phrasing '{m.group(0)}' belongs only in the revision notes block",
            )
        )


def _check_figures(
    parsed: ParsedStory, project: str, errors: list[Finding], warnings: list[Finding]
) -> None:
    for sid in parsed.section_ids:
        figs = parsed.figures.get(sid, [])
        text = parsed.sections.get(sid, "")
        if len(figs) > 3:
            errors.append(
                Finding(
                    "ERROR",
                    project,
                    f"section {sid}",
                    "figure-cap",
                    f"{len(figs)} figure cards; the showcase renders at most 3 per section",
                )
            )
        has_mermaid = re.search(r"^\s*```mermaid", text, re.MULTILINE) is not None
        if not figs and not has_mermaid:
            warnings.append(
                Finding(
                    "WARNING",
                    project,
                    f"section {sid}",
                    "no-visual",
                    "section has no figure card and no mermaid diagram",
                )
            )


def _check_pp(sid: str, text: str, project: str, out: list[Finding]) -> None:
    n = len(PP_BARE_RE.findall(strip_markdown(text)))
    if n:
        out.append(
            Finding(
                "ERROR",
                project,
                f"section {sid}",
                "pp-abbreviation",
                f"{n}x bare 'pp' — write percentage points as 'pp.' ('pp' alone reads as 'pages')",
            )
        )


def _check_lengths(
    parsed: ParsedStory, project: str, errors: list[Finding], warnings: list[Finding]
) -> None:
    order = parsed.section_ids
    if not order:
        return
    first_words = len(prose_words(parsed.sections[order[0]]))
    if first_words > FIRST_SECTION_WORD_CAP:
        errors.append(
            Finding(
                "ERROR",
                project,
                f"section {order[0]}",
                "first-section-cap",
                f"opening section is {first_words} words; cap is {FIRST_SECTION_WORD_CAP}",
            )
        )
    main_total = 0
    for sid in order:
        is_main = sid != CHANGELOG_SECTION
        n = len(prose_words(parsed.sections[sid]))
        if not is_main:
            continue
        main_total += n
        if n > SECTION_WORD_BUDGET:
            warnings.append(
                Finding(
                    "WARNING",
                    project,
                    f"section {sid}",
                    "section-budget",
                    f"{n} words; soft budget is {SECTION_WORD_BUDGET}",
                )
            )
    if main_total > MAIN_THREAD_WORD_BUDGET:
        warnings.append(
            Finding(
                "WARNING",
                project,
                "main thread",
                "main-thread-budget",
                f"main sections total {main_total} words; soft budget is {MAIN_THREAD_WORD_BUDGET}",
            )
        )


def _check_reading_ease(parsed: ParsedStory, project: str, warnings: list[Finding]) -> None:
    for sid in parsed.section_ids:
        if sid == CHANGELOG_SECTION:
            continue
        score = flesch_ease(strip_markdown(parsed.sections[sid]))
        if score is not None and score < FLESCH_MIN:
            warnings.append(
                Finding(
                    "WARNING",
                    project,
                    f"section {sid}",
                    "reading-ease",
                    f"Flesch reading ease {score:.1f} (floor {FLESCH_MIN:.0f})",
                )
            )


def lint_story(path: Path, glossary: re.Pattern[str]) -> list[Finding]:
    project = path.parent.name
    raw = path.read_text(encoding="utf-8")
    parsed = parse_story(raw)
    errors: list[Finding] = []
    warnings: list[Finding] = []
    _check_structure(raw, parsed, project, errors)
    for sid in parsed.section_ids:
        text = parsed.sections[sid]
        _check_summary_card(sid, text, project, errors, warnings)
        _check_changelog(sid, text, project, errors)
        _check_pp(sid, text, project, errors)
    _check_figures(parsed, project, errors, warnings)
    for term, sid in unlinked_glossary_uses(parsed.sections, parsed.section_ids, glossary).items():
        warnings.append(
            Finding(
                "WARNING",
                project,
                f"section {sid}",
                "glossary-first-use",
                f"glossary term '{term}' occurs only inside code; its first use will not link",
            )
        )
    _check_lengths(parsed, project, errors, warnings)
    _check_reading_ease(parsed, project, warnings)
    return errors + warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects-root", type=Path, default=DEFAULT_PROJECTS_ROOT)
    parser.add_argument("--glossary", type=Path, default=GLOSSARY_JSON)
    args = parser.parse_args(argv)

    terms = load_glossary(args.glossary)
    matcher = glossary_matcher(terms)
    stories = sorted(args.projects_root.glob("*/story.yaml"))
    if not stories:
        print(f"lint-story-language: no story.yaml under {args.projects_root}", file=sys.stderr)
        return 1

    findings: list[Finding] = []
    for story in stories:
        findings.extend(lint_story(story, matcher))
    for f in findings:
        print(f.line())
    errors = sum(1 for f in findings if f.level == "ERROR")
    warnings = len(findings) - errors
    print(
        f"lint-story-language: {len(stories)} stories — "
        f"{errors} error{'' if errors == 1 else 's'}, "
        f"{warnings} warning{'' if warnings == 1 else 's'}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
