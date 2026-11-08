"""Skills: disk folders -> deferred capabilities, and the summarize tool."""

from pathlib import Path

import pytest
from pydantic_ai import Capability

from agent_chat.capabilities.loader import (
    _search_resources,
    build_skill_capability,
    load_skills,
    parse_skill,
    summarize_text,
)
from agent_chat.deps import ChatDeps

SKILLS_DIR = Path(__file__).resolve().parents[1] / "src" / "agent_chat" / "skills"


class TestLoadSkills:
    def test_both_builtin_skills_load(self) -> None:
        skills = load_skills(SKILLS_DIR)
        assert [skill.id for skill in skills] == ["handbook", "summarize"]

    def test_skills_are_deferred(self) -> None:
        for skill in load_skills(SKILLS_DIR):
            assert skill.defer_loading is True
            assert skill.id is not None and skill.description

    def test_folders_without_skill_md_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "notes").mkdir()
        (tmp_path / "notes" / "random.txt").write_text("not a skill", encoding="utf-8")
        assert load_skills(tmp_path) == []

    def test_empty_skill_md_is_an_error(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "broken"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("  \n  \n", encoding="utf-8")
        with pytest.raises(ValueError, match="first paragraph"):
            parse_skill(skill_dir)


class TestHandbookQa:
    def test_description_is_first_paragraph(self) -> None:
        skill = parse_skill(SKILLS_DIR / "handbook")
        assert skill.description.startswith("Answer questions about the Example Co.")

    def test_resource_search_tool_is_auto_generated(self) -> None:
        skill = parse_skill(SKILLS_DIR / "handbook")
        tool_names = [fn.__name__ for fn in skill.tools]
        assert "search_handbook" in tool_names

    def test_capability_carries_instructions_and_tools(self) -> None:
        skill = parse_skill(SKILLS_DIR / "handbook")
        capability: Capability[ChatDeps] = build_skill_capability(skill)
        assert capability.id == "handbook"
        assert "handbook" in (capability.description or "")

    async def test_search_returns_relevant_sla_paragraph_beyond_prefix(self) -> None:
        body = (SKILLS_DIR / "handbook" / "resources" / "handbook.md").read_text(encoding="utf-8")
        search = _search_resources("handbook", {"handbook": body})
        hits = await search("severity-1 first response and update cadence")

        assert "within 1 hour" in hits[0]
        assert "30 minutes" in hits[0]
        assert "first 400" not in hits[0]

    async def test_search_uses_matching_paragraphs_not_unrelated_prefix(self) -> None:
        body = (SKILLS_DIR / "handbook" / "resources" / "handbook.md").read_text(encoding="utf-8")
        search = _search_resources("handbook", {"handbook": body})
        hits = await search("refund policy")

        assert "full refund within 30 days" in hits[0]
        assert "within 1 hour" not in hits[0]


class TestSummarize:
    def test_skill_has_the_bespoke_tool(self) -> None:
        skill = parse_skill(SKILLS_DIR / "summarize")
        assert "summarize_text" in [fn.__name__ for fn in skill.tools]

    def test_summarize_is_deterministic(self) -> None:
        text = (
            "The export pipeline moved to a nightly batch window. The old realtime "
            "exporter was retired in March. Failure alerts now route to the on-call "
            "rotation instead of the data team."
        )
        first = summarize_text(text, max_sentences=2)
        second = summarize_text(text, max_sentences=2)
        assert first == second
        assert len(first.split(". ")) <= 2

    def test_short_text_passes_through(self) -> None:
        assert summarize_text("One sentence only.", max_sentences=3) == "One sentence only."
