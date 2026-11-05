"""Conversation CRUD: list, read (full pydantic-ai conversation), delete."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic_ai.conversation import ConversationTypeAdapter

from agent_chat.api.security import require_api_key
from agent_chat.api.state import AppState

router = APIRouter()


@router.get("/conversations")
async def list_conversations(request: Request) -> dict[str, object]:
    """All conversations, newest first — ids and listing metadata only."""
    state: AppState = request.app.state.agent_chat
    metas = await state.conversation_store.list()
    return {"conversations": [meta.__dict__ for meta in metas]}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request) -> dict[str, object]:
    """One conversation: metadata plus the full message history."""
    state: AppState = request.app.state.agent_chat
    stored = await state.conversation_store.get(conversation_id)
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
) -> dict[str, bool]:
    """Delete a conversation and its history."""
    state: AppState = request.app.state.agent_chat
    if not await state.conversation_store.delete(conversation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown conversation {conversation_id!r}",
        )
    return {"deleted": True}
