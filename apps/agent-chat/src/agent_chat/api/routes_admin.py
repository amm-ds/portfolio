"""Ops endpoints: health, readiness, ingest, and the approval decision route.

``/health`` answers without touching anything; ``/ready`` probes the stores
and reports 503 until the app can actually serve a conversation.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from agent_chat.api.security import require_api_key
from agent_chat.api.state import AppState
from agent_chat.models import primary_model_name
from agent_chat.rag.ingest import ingest

router = APIRouter()


class IngestRequest(BaseModel):
    paths: list[Path] = Field(min_length=1)


def _validate_ingest_paths(paths: list[Path], roots: list[Path]) -> None:
    """Restrict ingestion to explicitly configured document roots."""
    resolved_roots = [root.expanduser().resolve() for root in roots]
    for path in paths:
        candidate = path.expanduser().resolve()
        if not any(candidate == root or root in candidate.parents for root in resolved_roots):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"ingest path is outside configured roots: {path}",
            )


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    """Liveness plus the configured primary model, for client display."""
    settings = request.app.state.agent_chat.settings
    return {
        "status": "ok",
        "provider": settings.provider,
        "model": primary_model_name(settings),
    }


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
    _validate_ingest_paths(body.paths, state.settings.ingest_roots)
    result = await ingest(body.paths, store=state.vector_store, embedder=state.embedder)
    if result.files == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no supported documents (.md/.txt) found in the given paths",
        )
    return {"files": result.files, "chunks": result.chunks}
