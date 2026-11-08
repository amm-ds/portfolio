"""Load skills from disk folders into deferred pydantic-ai capabilities.

Skill folder convention (adding a skill = adding one of these)::

    skills/<name>/SKILL.md          instructions; first paragraph = description
    skills/<name>/resources/*.md    optional documents, searchable via the
                                    auto-generated ``search_<name>`` tool

A skill whose folder has resources automatically gets a deterministic
keyword-search tool over them — no per-skill code. A skill that needs a
bespoke tool (like ``summarize``) adds one builder in ``EXTRA_TOOL_BUILDERS``
below. Every skill is ``defer_loading=True``: hidden from the model until it
calls ``load_capability("<name>")`` — progressive disclosure by construction.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai import Capability

from agent_chat.deps import ChatDeps

_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "to",
        "in",
        "per",
        "is",
        "are",
        "what",
        "how",
        "many",
        "much",
        "does",
        "do",
        "and",
        "for",
        "at",
        "on",
        "it",
        "its",
        "that",
        "this",
        "with",
        "by",
        "or",
        "as",
        "be",
        "can",
        "i",
        "you",
    }
)

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS]


def _excerpt_for_terms(body: str, terms: list[str], *, limit: int = 600) -> str:
    """Return complete query-relevant paragraphs, never an arbitrary prefix."""
    if len(body) <= limit:
        return body
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    matches = [
        paragraph for paragraph in paragraphs if any(term in paragraph.lower() for term in terms)
    ]
    if not matches:
        return body[:400].rsplit(" ", 1)[0] + "…"
    matches.sort(key=lambda paragraph: -sum(term in paragraph.lower() for term in terms))
    excerpts: list[str] = []
    remaining = limit
    for paragraph in matches[:2]:
        if remaining <= 0:
            break
        excerpts.append(paragraph[:remaining])
        remaining -= len(paragraph) + 2
    return "\n\n".join(excerpts).rsplit(" ", 1)[0] + "…"


def _search_resources(skill_name: str, resources: dict[str, str]) -> Callable[..., Any]:
    """Deterministic keyword-overlap search over a skill's resource documents."""

    async def search_resource(query: str, top_k: int = 3) -> list[str]:
        """Search this skill's reference documents (deterministic ranking).

        Args:
            query: Natural-language question or topic.
            top_k: Maximum number of snippets to return (1-5).

        Returns:
            Snippets "doc — excerpt", best match first.
        """
        terms = _tokens(query)
        if not terms:
            terms = _WORD_RE.findall(query.lower())
        k = max(1, min(top_k, 5))
        scored: list[tuple[int, str]] = []
        for title, body in resources.items():
            score = sum(1 for t in terms if t in body.lower())
            if score:
                scored.append((score, title))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        hits = []
        for _, title in scored[:k]:
            hits.append(f"{title} — {_excerpt_for_terms(resources[title], terms)}")
        return hits

    search_resource.__name__ = f"search_{skill_name.replace('-', '_')}"
    search_resource.__doc__ = search_resource.__doc__ or ""
    return search_resource


def summarize_text(text: str, max_sentences: int = 3) -> str:
    """Extractive summary: the highest-scoring sentences, in original order.

    Sentences score by content-word frequency (stopwords discarded); ties
    keep document order. Deterministic — same text, same summary.

    Args:
        text: The text to summarize.
        max_sentences: How many sentences to keep (1-10).

    Returns:
        The selected sentences joined by spaces.
    """
    k = max(1, min(max_sentences, 10))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if len(sentences) <= k:
        return " ".join(sentences)
    freq: dict[str, int] = {}
    for sentence in sentences:
        for tok in _tokens(sentence):
            freq[tok] = freq.get(tok, 0) + 1

    def score(sentence: str) -> int:
        return sum(freq.get(tok, 0) for tok in _tokens(sentence))

    ranked = sorted(range(len(sentences)), key=lambda i: (-score(sentences[i]), i))
    keep = sorted(ranked[:k])
    return " ".join(sentences[i] for i in keep)


#: Bespoke tool builders by skill name, for skills that do more than search
#: their resources. Adding one = one line here.
EXTRA_TOOL_BUILDERS: dict[str, Callable[[], Callable[..., Any]]] = {
    "summarize": lambda: summarize_text,
}


@dataclass
class Skill:
    """A skill folder parsed and ready to become a capability."""

    name: str
    description: str
    instructions: str
    tools: list[Callable[..., Any]] = field(default_factory=list)


def parse_skill(skill_dir: Path) -> Skill:
    """Read one skill folder: SKILL.md body + description + built tools."""
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError(f"skill folder {skill_dir} has no SKILL.md")
    markdown = skill_file.read_text(encoding="utf-8").strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", markdown) if p.strip()]
    # description = first paragraph that is not a markdown heading
    body_paragraphs = [p for p in paragraphs if not p.startswith("#")]
    if not body_paragraphs:
        raise ValueError(f"{skill_file} has no prose; the first paragraph is the description")
    description = " ".join(body_paragraphs[0].split())

    tools: list[Callable[..., Any]] = []
    resources_dir = skill_dir / "resources"
    resources: dict[str, str] = {}
    if resources_dir.is_dir():
        for path in sorted(resources_dir.iterdir()):
            if path.suffix in {".md", ".txt"}:
                resources[path.stem] = path.read_text(encoding="utf-8")
    if resources:
        tools.append(_search_resources(skill_dir.name, resources))
    builder = EXTRA_TOOL_BUILDERS.get(skill_dir.name)
    if builder is not None:
        tools.append(builder())

    return Skill(name=skill_dir.name, description=description, instructions=markdown, tools=tools)


def build_skill_capability(skill: Skill) -> Capability[ChatDeps]:
    """Wrap a parsed skill as a deferred (progressive-disclosure) capability."""
    return Capability(
        id=skill.name,
        description=skill.description,
        instructions=skill.instructions,
        tools=skill.tools,
        defer_loading=True,
    )


def load_skills(skills_dir: Path | None = None) -> list[Capability[ChatDeps]]:
    """One capability per skill folder, sorted by name for determinism.

    A directory without SKILL.md is skipped, so resources/ and friends can
    live anywhere under the skills root.
    """
    root = skills_dir or Path(__file__).resolve().parents[1] / "skills"
    if not root.is_dir():
        return []
    capabilities: list[Capability[ChatDeps]] = []
    for skill_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if not (skill_dir / "SKILL.md").is_file():
            continue
        capabilities.append(build_skill_capability(parse_skill(skill_dir)))
    return capabilities


__all__ = ["Skill", "build_skill_capability", "load_skills", "parse_skill", "summarize_text"]
