"""Bound the conversation carried into later runs and model requests.

The default ``ProcessHistory`` capability keeps the last N user turns, including
their tool calls/results and the current request. It is synchronous and makes no
model call. With ``history_summarize_enabled=True``, overflow alone triggers a
separate small agent request that summarizes the turns about to be dropped; the
summary replaces them while the recent window stays verbatim. The template's
whole-``Conversation`` store persists that bounded result; durable user facts
belong in the separate notebook rather than in an ever-growing chat history.
"""

from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import ProcessHistory
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model

from agent_chat.config import Settings
from agent_chat.deps import ChatDeps

_SUMMARY_PREFIX = "<conversation-summary>"


def _turn_starts(messages: list[ModelMessage]) -> list[int]:
    starts: list[int] = []
    for index, message in enumerate(messages):
        if isinstance(message, ModelRequest) and any(
            isinstance(part, UserPromptPart)
            and isinstance(part.content, str)
            and not part.content.startswith(_SUMMARY_PREFIX)
            for part in message.parts
        ):
            starts.append(index)
    return starts


def trim_history(messages: list[ModelMessage], *, max_turns: int) -> list[ModelMessage]:
    """Keep at most ``max_turns`` user turns; never split a turn's tool leg."""
    if max_turns < 1:
        raise ValueError("max_turns must be at least 1")
    starts = _turn_starts(messages)
    if len(starts) <= max_turns:
        return messages.copy()
    return messages[starts[-max_turns] :]


def _summary_request(summary: str) -> ModelRequest:
    return ModelRequest(
        parts=[UserPromptPart(content=f"{_SUMMARY_PREFIX}\n{summary}\n</conversation-summary>")]
    )


def _render_for_summary(messages: list[ModelMessage]) -> str:
    lines: list[str] = []
    for message in messages:
        for part in message.parts:
            if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                lines.append(f"User: {part.content}")
            elif isinstance(part, TextPart):
                lines.append(f"Assistant: {part.content}")
            elif isinstance(part, ToolCallPart):
                lines.append(f"Assistant called {part.tool_name}: {part.args}")
            elif isinstance(part, ToolReturnPart):
                lines.append(f"Tool {part.tool_name} returned: {part.content}")
    return "\n".join(lines)


async def _summarize(model: Model, messages: list[ModelMessage]) -> str:
    summarizer = Agent(
        model,
        instructions=(
            "Summarize the supplied earlier conversation for a later assistant turn. "
            "Preserve durable facts, decisions, unresolved requests, and tool outcomes. "
            "Be concise; do not answer the user or invent details."
        ),
    )
    result = await summarizer.run(_render_for_summary(messages))
    return result.output


def build_history_capability(model: Model, settings: Settings) -> ProcessHistory[ChatDeps]:
    """Build the default trimmer or the opt-in summarize-on-overflow processor."""

    async def process(
        ctx: RunContext[ChatDeps], messages: list[ModelMessage]
    ) -> list[ModelMessage]:
        del ctx
        starts = _turn_starts(messages)
        max_turns = settings.history_max_turns
        if len(starts) <= max_turns:
            return messages.copy()
        dropped = messages[: starts[-max_turns]]
        recent = messages[starts[-max_turns] :]
        if not settings.history_summarize_enabled:
            return recent
        summary = await _summarize(model, dropped)
        return [_summary_request(summary), *recent]

    return ProcessHistory(process, id="conversation-history")
