"""Shared test helpers: a scripted FunctionModel that plays the workflow roles.

The helper inspects the system prompt of the requesting agent and returns a
valid structured output for that role (planner / executor / critique), so the
full graph runs offline with deterministic, role-aware responses.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel


def scripted_model(
    *,
    plan_steps: list[dict[str, Any]] | None = None,
    draft: str = "The answer is 75.6 liters.",
    findings: list[str] | None = None,
    verdict: str = "pass",
    fail_executions: int = 0,
    on_prompt: Callable[[str], None] | None = None,
) -> FunctionModel:
    """A FunctionModel that answers per role (PLANNER/EXECUTOR/CRITIQUE).

    ``fail_executions`` makes the first N executor calls raise, exercising the
    graph's repair path. ``on_prompt`` optionally observes each user prompt
    (used to assert HITL feedback reaches the re-planner).
    """
    calls = {"exec": 0}

    def respond(messages: list[Any], info: Any) -> ModelResponse:
        role = ""
        user_prompt = ""
        for message in messages:
            for part in getattr(message, "parts", []):
                content = getattr(part, "content", "")
                if isinstance(part, UserPromptPart) and isinstance(content, str):
                    user_prompt = content
                    continue
                if not isinstance(content, str):
                    continue
                if "PLANNER" in content:
                    role = "plan"
                elif "EXECUTOR" in content:
                    role = "exec"
                elif "CRITIQUE" in content:
                    role = "critique"
        if on_prompt is not None and user_prompt:
            on_prompt(user_prompt)
        if role == "plan":
            steps = plan_steps or [
                {
                    "id": 1,
                    "description": "Search the handbook for fuel figures",
                    "tool": "search_handbook",
                    "expected_output": "consumption figures",
                },
                {
                    "id": 2,
                    "description": "Compute weekly consumption",
                    "tool": "calculator",
                    "expected_output": "75.6",
                },
            ]
            payload: dict[str, Any] = {"steps": steps, "notes": "weekly = daily x 7"}
        elif role == "exec":
            calls["exec"] += 1
            if calls["exec"] <= fail_executions:
                raise RuntimeError("simulated executor failure")
            payload = {
                "findings": findings or ["generator burns 1.8 L/h, 6 h/day", "1.8*6*7 = 75.6"],
                "draft": draft,
                "self_confidence": 0.9,
            }
        else:
            payload = {
                "verdict": verdict,
                "issues": [] if verdict == "pass" else ["missing"],
                "suggestion": "",
            }
        return ModelResponse(parts=[TextPart(content=json.dumps(payload))])

    return FunctionModel(respond)


ScriptedModelFactory = Callable[..., FunctionModel]


@pytest.fixture
def make_scripted_model() -> ScriptedModelFactory:
    """Factory fixture: build role-aware scripted models (see ``scripted_model``)."""
    return scripted_model
