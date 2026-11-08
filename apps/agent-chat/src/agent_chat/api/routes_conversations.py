"""Conversation CRUD scoped to one anonymous browser session."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic_ai.conversation import ConversationTypeAdapter

from agent_chat.api.security import require_api_key
from agent_chat.api.session import require_session_id
from agent_chat.api.state import AppState

router = APIRouter()


@router.get("/conversations")
async def list_conversations(
    request: Request, session_id: str = Depends(require_session_id)
) -> dict[str, object]:
    """This session's conversations, newest first — listing metadata only."""
    state: AppState = request.app.state.agent_chat
    metas = await state.conversation_store.list(session_id=session_id)
    return {"conversations": [meta.__dict__ for meta in metas]}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str, request: Request, session_id: str = Depends(require_session_id)
) -> dict[str, object]:
    """One session-owned conversation: metadata plus full message history."""
    state: AppState = request.app.state.agent_chat
    stored = await state.conversation_store.get(conversation_id, session_id=session_id)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown conversation {conversation_id!r}",
        )
    return {
        "meta": stored.meta.__dict__,
        "conversation": ConversationTypeAdapter.dump_python(stored.conversation),
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    _: None = Depends(require_api_key),
    session_id: str = Depends(require_session_id),
) -> dict[str, bool]:
    """Delete a conversation owned by this session and its history."""
    state: AppState = request.app.state.agent_chat
    if not await state.conversation_store.delete(conversation_id, session_id=session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown conversation {conversation_id!r}",
        )
    return {"deleted": True}
