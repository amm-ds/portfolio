"""The named toolsets and how the agent assembles them."""

from collections.abc import Iterable
from typing import Any

from pydantic_ai.toolsets import AbstractToolset, FunctionToolset

from agent_chat.agent import build_agent
from agent_chat.config import Settings
from agent_chat.testing import scripted_model
from agent_chat.toolsets import (
    TOOLSETS,
    core_toolset,
    memory_toolset,
    messaging_toolset,
    web_toolset,
)


def _names(toolsets: Iterable[AbstractToolset[Any]]) -> set[str]:
    """Tool names across toolsets, walking agent-side wrappers recursively."""

    def _walk(toolset: Any) -> set[str]:
        if isinstance(toolset, FunctionToolset):
            return set(toolset.tools)
        for attr in ("toolsets", "wrapped"):
            inner = getattr(toolset, attr, None)
            if inner is None:
                continue
            if isinstance(inner, (list, tuple)):
                names: set[str] = set()
                for child in inner:
                    names |= _walk(child)
                return names
            return _walk(inner)
        return set()

    names: set[str] = set()
    for toolset in toolsets:
        names |= _walk(toolset)
    return names


class TestToolsets:
    def test_core_has_calculator_and_clock(self) -> None:
        assert _names([core_toolset()]) == {"calculator", "clock"}

    def test_web_is_just_fetch_url(self) -> None:
        assert _names([web_toolset()]) == {"fetch_url"}

    def test_messaging_carries_the_gated_tool(self) -> None:
        assert _names([messaging_toolset()]) == {"send_message"}

    def test_memory_has_remember_and_recall(self) -> None:
        assert _names([memory_toolset()]) == {"remember", "recall"}

    def test_registry_names_match_builders(self) -> None:
        assert set(TOOLSETS) == {"core", "web", "messaging", "memory"}


class TestAgentAssembly:
    def test_fetch_url_hidden_by_default(self) -> None:
        agent = build_agent(model=scripted_model([]), settings=Settings(embedder="hashing"))
        names = _names(agent.toolsets)
        assert {"calculator", "clock", "send_message"} <= names
        assert "fetch_url" not in names

    def test_fetch_url_attached_when_enabled(self) -> None:
        agent = build_agent(
            model=scripted_model([]),
            settings=Settings(embedder="hashing", fetch_url_enabled=True),
        )
        assert "fetch_url" in _names(agent.toolsets)
