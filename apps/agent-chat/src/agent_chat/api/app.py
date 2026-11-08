"""The FastAPI app factory.

``create_app`` assembles state (agent, stores, approval hub) from settings or
explicit overrides — tests pass every dependency, so no monkeypatching and no
environment reads. Uvicorn serves it with ``--factory
agent_chat.api.app:create_app``.
"""

import logging
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_ai.models import Model
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from agent_chat.agent import build_agent
from agent_chat.api.routes_admin import router as admin_router
from agent_chat.api.routes_chat import router as chat_router
from agent_chat.api.routes_conversations import router as conversations_router
from agent_chat.api.state import ApprovalHub, AppState
from agent_chat.config import Settings
from agent_chat.memory import (
    ConversationStore,
    FileNotebook,
    NotebookStore,
    build_conversation_store,
)
from agent_chat.models import build_model
from agent_chat.rag.embeddings import Embedder, build_embedder
from agent_chat.rag.store import VectorStore, build_vector_store

logger = logging.getLogger(__name__)


class RequestIdMiddleware:
    """Pure-ASGI request-id: stamps every response, safe for SSE streams."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.get("headers") or []
                message["headers"] = [*headers, (b"x-request-id", request_id.encode())]
            await send(message)

        await self.app(scope, receive, send_with_header)


def _error_body(request: Request, code: str, message: str) -> dict[str, dict[str, str | None]]:
    request_id = getattr(request.state, "request_id", None)
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def create_app(
    *,
    settings: Settings | None = None,
    model: Model | None = None,
    conversation_store: ConversationStore | None = None,
    notebook: NotebookStore | None = None,
    vector_store: VectorStore | None = None,
    embedder: Embedder | None = None,
) -> FastAPI:
    """Build the app; overrides exist so tests inject fakes for everything."""
    resolved_settings = settings or Settings()
    resolved_embedder = embedder or build_embedder(resolved_settings)
    resolved_model = model or build_model(resolved_settings)
    resolved_vector_store = vector_store or build_vector_store(
        resolved_settings, resolved_embedder.dim
    )
    resolved_conversation_store = conversation_store or build_conversation_store(resolved_settings)
    resolved_notebook = notebook or FileNotebook(resolved_settings.memory_data_dir)
    executor = ThreadPoolExecutor(
        max_workers=resolved_settings.executor_workers,
        thread_name_prefix="agent-chat-worker",
    )
    state = AppState(
        settings=resolved_settings,
        agent=build_agent(
            model=resolved_model,
            settings=resolved_settings,
            vector_store=resolved_vector_store,
            embedder=resolved_embedder,
            executor=executor,
        ),
        conversation_store=resolved_conversation_store,
        notebook=resolved_notebook,
        vector_store=resolved_vector_store,
        embedder=resolved_embedder,
        approval_hub=ApprovalHub(timeout_s=resolved_settings.approval_timeout_s),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            await state.conversation_store.init()
            await state.vector_store.init()
            yield
        finally:
            await state.conversation_store.close()
            await state.vector_store.close()
            executor.shutdown(wait=True)

    app = FastAPI(title="agent-chat", version="0.1.0", lifespan=lifespan)
    app.state.agent_chat = state
    app.add_middleware(RequestIdMiddleware)

    app.include_router(chat_router)
    app.include_router(conversations_router)
    app.include_router(admin_router)

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, f"http_{exc.status_code}", str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,  # HTTP_422_UNPROCESSABLE_CONTENT (starlette renamed the constant)
            content=_error_body(request, "validation_error", str(exc.errors())),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(request, "internal_error", type(exc).__name__),
        )

    return app
