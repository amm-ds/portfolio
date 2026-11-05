"""POST /chat: one SSE stream of typed events, plus the approval endpoint.

The agent runs in a producer task; the route generator drains the queue, so
approval events emitted from inside a tool call reach the client while the
run is still parked waiting for an answer. Disconnecting the client cancels
the run.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pydantic_ai.conversation import Conversation
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    TextPartDelta,
    ToolCallPart,
)
from pydantic_ai.run import AgentRunResult, AgentRunResultEvent

from agent_chat.agent import build_usage_limits
from agent_chat.api.events import (
    ChatEvent,
    DoneEvent,
    ErrorEvent,
    TextDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    UsageSummary,
    encode_sse,
)
from agent_chat.api.security import require_api_key
from agent_chat.api.state import AppState
from agent_chat.deps import ChatDeps
from agent_chat.schemas import Answer

router = APIRouter()

_RESULT_SNIPPET_LIMIT = 500


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = None


class ApprovalDecisionRequest(BaseModel):
    approved: bool


def _args_dict(part: ToolCallPart) -> dict[str, object]:
    """ToolCallPart args arrive as dict or JSON string depending on the model."""
    if isinstance(part.args, dict):
        return part.args
    if isinstance(part.args, str) and part.args:
        try:
            parsed = json.loads(part.args)
        except json.JSONDecodeError:
            return {"raw": part.args}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    return {}


def _content_str(content: object) -> str:
    text = content if isinstance(content, str) else str(content)
    return text if len(text) <= _RESULT_SNIPPET_LIMIT else text[:_RESULT_SNIPPET_LIMIT] + "…"


def _map_event(event: object) -> list[ChatEvent]:
    """Map one agent stream event to zero or more client-facing events."""
    if isinstance(event, FunctionToolCallEvent):
        call = event.part
        return [
            ToolCallStartEvent(
                call_id=call.tool_call_id,
                name=call.tool_name,
                args=_args_dict(call),
            )
        ]
    if isinstance(event, FunctionToolResultEvent):
        result = event.part
        return [
            ToolCallEndEvent(
                call_id=result.tool_call_id,
                # a tool result always names its tool; the None type is a
                # pydantic-ai artifact, never observed on the wire
                name=result.tool_name or "tool",
                result=_content_str(result.content),
            )
        ]
    if isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
        return [TextDeltaEvent(delta=event.delta.content_delta)]
    # Output tool call/result events (the structured final_result call), args
    # deltas, and lifecycle events carry nothing the client needs beyond the
    # events above and the trailing done.
    return []


def _error_code(exc: BaseException) -> str:
    name = type(exc).__name__
    return "".join(f"_{c.lower()}" if c.isupper() else c for c in name).lstrip("_")


async def _save_result(
    state: AppState,
    result: AgentRunResult[Answer],
    *,
    fallback_conversation_id: str | None,
    title: str,
) -> str:
    """Persist the run's conversation; returns its id for the done event."""
    conversation: Conversation = result.conversation
    await state.conversation_store.save(conversation, title=title)
    return conversation.conversation_id or fallback_conversation_id or ""


@router.post("/chat")
async def chat(
    request: Request,
    body: ChatRequest,
    _: None = Depends(require_api_key),
) -> Response:
    """Run one user message; stream typed events (see ``api.events``)."""
    state: AppState = request.app.state.agent_chat

    conversation: Conversation | None = None
    if body.conversation_id is not None:
        stored = await state.conversation_store.get(body.conversation_id)
        if stored is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"unknown conversation {body.conversation_id!r}",
            )
        conversation = stored.conversation

    queue: asyncio.Queue[ChatEvent | None] = asyncio.Queue()
    gate = state.approval_hub.gate(queue.put_nowait)
    deps = ChatDeps(approvals=gate)
    usage_limits = build_usage_limits(state.settings)
    title = body.message[:60]

    async def produce() -> None:
        try:
            async with state.agent.run_stream_events(
                body.message,
                conversation=conversation,
                deps=deps,
                usage_limits=usage_limits,
            ) as stream:
                async for event in stream:
                    if isinstance(event, AgentRunResultEvent):
                        result = event.result
                        conversation_id = await _save_result(
                            state,
                            result,
                            fallback_conversation_id=body.conversation_id,
                            title=title,
                        )
                        usage = result.usage
                        await queue.put(
                            DoneEvent(
                                answer=result.output,
                                usage=UsageSummary(
                                    input_tokens=usage.input_tokens,
                                    output_tokens=usage.output_tokens,
                                    requests=usage.requests,
                                ),
                                conversation_id=conversation_id,
                            )
                        )
                    else:
                        for mapped in _map_event(event):
                            await queue.put(mapped)
        except Exception as exc:  # broad: every failure shape becomes an error event
            await queue.put(
                ErrorEvent(code=_error_code(exc), message=str(exc) or type(exc).__name__)
            )
        finally:
            await queue.put(None)

    async def generate() -> AsyncIterator[str]:
        task = asyncio.create_task(produce())
        try:
            while (item := await queue.get()) is not None:
                yield encode_sse(item)
            yield "data: [DONE]\n\n"
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/approvals/{approval_id}")
async def decide_approval(
    approval_id: str,
    body: ApprovalDecisionRequest,
    request: Request,
    _: None = Depends(require_api_key),
) -> dict[str, bool]:
    """Answer a pending approval_request (see the chat stream)."""
    state: AppState = request.app.state.agent_chat
    if not state.approval_hub.resolve(approval_id, body.approved):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no pending approval {approval_id!r}",
        )
    return {"resolved": True}
