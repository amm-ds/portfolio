"""Unit tests for the research-ops tools and toolset composition."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest
from agentic_workflows.tools import (
    Notebook,
    calculator,
    composed_toolset,
    note_store,
    percent_change,
    round_to,
    search_handbook,
    unit_convert,
)
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel


class TestCalculator:
    def test_arithmetic(self) -> None:
        assert calculator("1.8*6*7") == 75.6
        assert calculator("(2400 + 380) / 7") == pytest.approx(397.142857, abs=1e-4)
        assert calculator("2**10") == 1024
        assert calculator("-4 + 10 % 3") == -3.0

    def test_rejects_non_arithmetic(self) -> None:
        with pytest.raises(ValueError, match=r"unsupported|invalid"):
            calculator("__import__('os')")
        with pytest.raises(ValueError):
            calculator("open('/etc/passwd')")


class TestUnitConvert:
    def test_length(self) -> None:
        assert unit_convert(48, "km", "mi") == 29.8258
        assert unit_convert(1, "mi", "km") == 1.6093

    def test_mass_and_volume(self) -> None:
        assert unit_convert(25, "kg", "lb") == 55.1156
        assert unit_convert(10, "l", "gal") == pytest.approx(2.6418, abs=1e-4)

    def test_temperature(self) -> None:
        assert unit_convert(-20, "c", "f") == -4.0
        assert unit_convert(32, "f", "c") == 0.0

    def test_rejects_cross_dimension(self) -> None:
        with pytest.raises(ValueError, match="cannot convert"):
            unit_convert(1, "km", "kg")
        with pytest.raises(ValueError, match="unknown unit"):
            unit_convert(1, "furlong", "km")


class TestSearchHandbook:
    def test_deterministic_and_relevant(self) -> None:
        hits = search_handbook("How many liters of water does the tank hold?", top_k=2)
        assert hits
        assert "water" in hits[0].lower()
        again = search_handbook("How many liters of water does the tank hold?", top_k=2)
        assert hits == again

    def test_top_k_bounded(self) -> None:
        assert len(search_handbook("fuel", top_k=2)) <= 2
        assert len(search_handbook("fuel", top_k=99)) <= 5

    def test_unmatched_query_returns_empty(self) -> None:
        assert search_handbook("xyzzy plugh quantum teapot") == []


class TestNoteStore:
    def test_append_and_list(self) -> None:
        notebook = Notebook()

        class _Ctx:
            deps = notebook

        note_store(_Ctx(), "append", "first")  # type: ignore[arg-type]
        note_store(_Ctx(), "append", "second")  # type: ignore[arg-type]
        assert note_store(_Ctx(), "list") == ["first", "second"]  # type: ignore[arg-type]

    def test_empty_append_rejected(self) -> None:
        notebook = Notebook()

        class _Ctx:
            deps = notebook

        with pytest.raises(ValueError, match="non-empty"):
            note_store(_Ctx(), "append", "   ")  # type: ignore[arg-type]


class TestMathHelpers:
    def test_percent_change(self) -> None:
        assert percent_change(10, 12) == 20.0
        assert percent_change(10, 8) == -20.0
        with pytest.raises(ValueError, match="non-zero"):
            percent_change(0, 5)

    def test_round_to(self) -> None:
        assert round_to(3.14159, 2) == 3.14
        with pytest.raises(ValueError):
            round_to(1.0, 9)


def _force_call_model(tool_name: str, args: dict[str, Any]) -> FunctionModel:
    """A FunctionModel whose first response forces one exact tool call."""

    def respond(messages: list[Any], info: Any) -> ModelResponse:
        for message in messages:
            if isinstance(message, ModelResponse):
                return ModelResponse(parts=[TextPart(content="done")])
        from pydantic_ai.messages import ToolCallPart

        return ModelResponse(
            parts=[ToolCallPart(tool_name=tool_name, args=args, tool_call_id="call_1")]
        )

    return FunctionModel(respond)


class TestPrefixedComposition:
    """Two toolsets composed via CombinedToolset + PrefixedToolset: no collisions."""

    CALLS: ClassVar[list[tuple[str, dict[str, Any]]]] = [
        ("calculator", {"expr": "1.8*6*7"}),
        ("unit_convert", {"value": 48, "from_unit": "km", "to_unit": "mi"}),
        ("search_handbook", {"query": "water storage"}),
        ("note_store", {"action": "append", "note": "ops log"}),
        ("math_percent_change", {"old_value": 10, "new_value": 12}),
        ("math_round_to", {"value": 3.14159, "digits": 2}),
    ]

    def test_all_six_tools_callable_without_collision(self) -> None:
        for tool_name, args in self.CALLS:
            agent: Agent[Notebook, str] = Agent(
                _force_call_model(tool_name, args),
                deps_type=Notebook,
                toolsets=[composed_toolset()],
                output_type=str,
            )
            notebook = Notebook()
            result = agent.run_sync("exercise the tool", deps=notebook)
            assert result.output == "done", f"tool {tool_name} did not complete"

    def test_prefixed_names_differ_from_bare_names(self) -> None:
        bare = {t.__name__ for t in (percent_change, round_to)}
        prefixed = {name for name, _ in self.CALLS if name.startswith("math_")}
        assert prefixed == {f"math_{n}" for n in bare}
        research = {name for name, _ in self.CALLS if not name.startswith("math_")}
        assert not (research & prefixed), "toolset names collide"
