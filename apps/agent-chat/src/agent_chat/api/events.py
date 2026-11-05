"""The SSE event schema: typed, discriminated by ``type``.

Every event the chat stream emits is one of these models, serialized as one
``data:`` line each. Clients dispatch on ``type``; unknown types should be
ignored so the schema can grow without breaking old frontends.
"""

from typing import Annotated, Literal

from pydantic import BaseModel

from agent_chat.schemas import Answer


class UsageSummary(BaseModel):
    """Token/request totals for one run."""

    input_tokens: int
    output_tokens: int
    requests: int


class TextDeltaEvent(BaseModel):
    type: Literal["text_delta"] = "text_delta"
    delta: str


class ToolCallStartEvent(BaseModel):
    type: Literal["tool_call_start"] = "tool_call_start"
    call_id: str
    name: str
    args: dict[str, object]


class ToolCallEndEvent(BaseModel):
    type: Literal["tool_call_end"] = "tool_call_end"
    call_id: str
    name: str
    result: str


class ApprovalRequestEvent(BaseModel):
    type: Literal["approval_request"] = "approval_request"
    approval_id: str
    tool: str
    summary: str


class ApprovalResponseEvent(BaseModel):
    type: Literal["approval_response"] = "approval_response"
    approval_id: str
    approved: bool


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    answer: Answer
    usage: UsageSummary
    conversation_id: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


ChatEvent = Annotated[
    TextDeltaEvent
    | ToolCallStartEvent
    | ToolCallEndEvent
    | ApprovalRequestEvent
    | ApprovalResponseEvent
    | DoneEvent
    | ErrorEvent,
    "type",
]
"""The full client-facing event union (discriminator: ``type``)."""


def encode_sse(event: BaseModel) -> str:
    """One SSE frame for ``event``."""
    return f"data: {event.model_dump_json()}\n\n"
