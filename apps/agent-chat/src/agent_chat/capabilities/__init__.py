"""Capabilities: skills loaded from disk with progressive disclosure.

A skill is a folder::

    skills/<name>/SKILL.md            instructions (the model-facing doc)
    skills/<name>/resources/*.md      optional material the skill's tools read

The first paragraph of ``SKILL.md`` is the capability description — the text
the model sees to decide whether to load the skill. Skills load on demand
(``defer_loading=True``): their instructions and tools stay hidden until the
model calls ``load_capability("<name>")``, so the base context stays small.
Adding a skill = adding a folder; nothing else changes.
"""

from agent_chat.capabilities.loader import Skill, build_skill_capability, load_skills

__all__ = ["Skill", "build_skill_capability", "load_skills"]
