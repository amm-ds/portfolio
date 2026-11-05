"""Deterministic scripted model for tests and CI evals.

``scripted_model`` plays a fixed queue of :class:`FakeStep`s — text replies,
tool calls, and optional guards asserting what the model "sees" — so every
agent test runs with no network, no Ollama, and no API keys. When the queue
runs dry the model fails loudly instead of improvising: a silent default
would let tests pass on nothing.

This module ships with the package (not under ``tests/``) because the eval
suite builds its per-case models from it; nothing in the app imports it.
"""

import json
from collections import deque
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel
from pydantic_ai.usage import RequestUsage


@dataclass(frozen=True)
class FakeStep:
    """One scripted model turn.

    Exactly one of ``text`` / ``tool_call`` should be set. ``expect`` is an
    optional substring that must appear in the latest user-visible message
    (user prompt or tool result) — a cheap way to pin tool-call sequencing.
    """

    text: str | None = None
    tool_call: tuple[str, dict[str, Any]] | None = None
    expect: str | None = None


def _visible_text(messages: Sequence[ModelMessage]) -> str:
    """Concatenated user prompts and tool returns — what the model observes."""
    parts: list[str] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, (UserPromptPart, ToolReturnPart)):
                parts.append(str(part.content))
    return "\n".join(parts)


def scripted_model_from_queue(
    queue: deque[FakeStep], *, model_name: str = "scripted"
) -> FunctionModel:
    """A ``FunctionModel`` that pops ``queue`` live, then fails loudly.

    Live-popping lets API tests enqueue steps after the app (and model) were
    created. Both request modes are wired so the same script drives
    ``agent.run`` and the API's streamed runs; the stream replays each scripted
    response as deltas (usage is estimated by the stream wrapper either way).
    """
    counter = 0

    def _respond(messages: list[ModelMessage]) -> ModelResponse:
        nonlocal counter
        if not queue:
            raise AssertionError("scripted model: step queue exhausted (script a longer script)")
        step = queue.popleft()
        if step.expect is not None and step.expect.lower() not in _visible_text(messages).lower():
            raise AssertionError(f"scripted model: expected {step.expect!r} in visible text")
        usage = RequestUsage(input_tokens=12, output_tokens=6)
        if step.tool_call is not None:
            name, args = step.tool_call
            counter += 1
            return ModelResponse(
                parts=[
                    ToolCallPart(tool_call_id=f"fake_call_{counter}", tool_name=name, args=args)
                ],
                usage=usage,
            )
        return ModelResponse(parts=[TextPart(step.text or "")], usage=usage)

    def _function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return _respond(messages)

    async def _stream_function(
        messages: list[ModelMessage], info: AgentInfo
    ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        response = _respond(messages)
        for part in response.parts:
            if isinstance(part, TextPart):
                yield part.content
            elif isinstance(part, ToolCallPart):
                args = part.args if isinstance(part.args, str) else json.dumps(part.args or {})
                yield {
                    0: DeltaToolCall(
                        name=part.tool_name, json_args=args, tool_call_id=part.tool_call_id
                    )
                }

    return FunctionModel(_function, stream_function=_stream_function, model_name=model_name)


def scripted_model(steps: Sequence[FakeStep], *, model_name: str = "scripted") -> FunctionModel:
    """A ``FunctionModel`` that replays a private copy of ``steps``."""
    return scripted_model_from_queue(deque(steps), model_name=model_name)
