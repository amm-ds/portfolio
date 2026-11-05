"""Ops endpoints: health, readiness, ingest, and the approval decision route.

``/health`` answers without touching anything; ``/ready`` probes the stores
and reports 503 until the app can actually serve a conversation.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from agent_chat.api.security import require_api_key
from agent_chat.api.state import AppState
from agent_chat.rag.ingest import ingest

router = APIRouter()


class IngestRequest(BaseModel):
    paths: list[Path] = Field(min_length=1)


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: process is up."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    """Readiness: stores answer."""
    state: AppState = request.app.state.agent_chat
    if not await state.conversation_store.ping():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database not reachable"
        )
    if not await state.vector_store.ping():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="vector store not reachable"
        )
    return {"status": "ready"}


@router.post("/ingest")
async def ingest_documents(
    body: IngestRequest,
    request: Request,
    _: None = Depends(require_api_key),
) -> dict[str, int]:
    """Chunk + embed + index markdown/txt files (server-side paths)."""
    state: AppState = request.app.state.agent_chat
    result = await ingest(body.paths, store=state.vector_store, embedder=state.embedder)
    if result.files == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no supported documents (.md/.txt) found in the given paths",
        )
    return {"files": result.files, "chunks": result.chunks}
