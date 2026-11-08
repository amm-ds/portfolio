"""FastAPI app factory with injectable adapters and stable errors."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from document_intelligence.analysis.page_analyzer import PageAnalyzer, build_page_analyzer
from document_intelligence.analysis.page_chat import PageChat, build_page_chat
from document_intelligence.analysis.service import (
    AnalysisService,
    DocumentBusyError,
    DocumentNotFoundError,
    PageNotFoundError,
)
from document_intelligence.api.routes import router
from document_intelligence.api.schemas import HealthResponse, LivenessResponse
from document_intelligence.api.state import AppState
from document_intelligence.clock import Clock, SystemClock
from document_intelligence.config import Settings
from document_intelligence.documents.storage import BlobNotFoundError, BlobStore
from document_intelligence.jobs.queue import JobQueue
from document_intelligence.runtime import build_blobs, build_queue, build_repository
from document_intelligence.store.repository import Repository

logger = logging.getLogger(__name__)


class RequestIdMiddleware:
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
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_header)


def error_body(request: Request, code: str, message: str) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


def create_app(
    *,
    settings: Settings | None = None,
    repository: Repository | None = None,
    queue: JobQueue | None = None,
    blobs: BlobStore | None = None,
    analyzer: PageAnalyzer | None = None,
    page_chat: PageChat | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    resolved_clock = clock or SystemClock()
    resolved_repository = repository or build_repository(resolved_settings, resolved_clock)
    resolved_queue = queue or build_queue(resolved_settings, resolved_clock)
    resolved_blobs = blobs or build_blobs(resolved_settings)
    resolved_analyzer = analyzer or build_page_analyzer(resolved_settings)
    resolved_page_chat = page_chat or build_page_chat(resolved_settings)
    service = AnalysisService(
        resolved_repository,
        resolved_queue,
        resolved_blobs,
        resolved_analyzer,
        resolved_page_chat,
        resolved_clock,
        resolved_settings.max_job_attempts,
        resolved_settings.max_upload_bytes,
        resolved_settings.page_concurrency,
        resolved_settings.page_text_max_chars,
    )
    state = AppState(
        settings=resolved_settings,
        repository=resolved_repository,
        queue=resolved_queue,
        blobs=resolved_blobs,
        service=service,
        page_chat=resolved_page_chat,
        clock=resolved_clock,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        resolved_queue.close()
        resolved_repository.close()

    app = FastAPI(
        title="document-intelligence",
        version="0.2.0",
        description="Page-level, evidence-grounded document analysis with cited page chat.",
        lifespan=lifespan,
    )
    app.state.app_state = state
    app.add_middleware(RequestIdMiddleware)
    app.include_router(router)

    @app.get("/health", response_model=LivenessResponse, tags=["health"])
    def health() -> LivenessResponse:
        return LivenessResponse(status="ok")

    @app.get("/ready", response_model=HealthResponse, tags=["health"])
    def ready() -> Response | HealthResponse:
        repository_ok = resolved_repository.ping()
        queue_ok = resolved_queue.ping()
        response = HealthResponse(
            status="ok" if repository_ok and queue_ok else "not_ready",
            repository=repository_ok,
            queue=queue_ok,
        )
        if repository_ok and queue_ok:
            return response
        return JSONResponse(status_code=503, content=response.model_dump(mode="json"))

    @app.exception_handler(DocumentNotFoundError)
    async def not_found(request: Request, exc: DocumentNotFoundError) -> JSONResponse:
        return JSONResponse(
            content=error_body(request, "document_not_found", str(exc)), status_code=404
        )

    @app.exception_handler(PageNotFoundError)
    async def page_not_found(request: Request, exc: PageNotFoundError) -> JSONResponse:
        return JSONResponse(
            content=error_body(request, "page_not_found", str(exc)), status_code=404
        )

    @app.exception_handler(BlobNotFoundError)
    async def blob_not_found(request: Request, exc: BlobNotFoundError) -> JSONResponse:
        return JSONResponse(
            content=error_body(request, "blob_not_found", str(exc)), status_code=404
        )

    @app.exception_handler(DocumentBusyError)
    async def document_busy(request: Request, exc: DocumentBusyError) -> JSONResponse:
        return JSONResponse(content=error_body(request, "document_busy", str(exc)), status_code=409)

    @app.exception_handler(ValueError)
    async def bad_request(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            content=error_body(request, "invalid_request", str(exc)), status_code=400
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            content=error_body(request, f"http_{exc.status_code}", str(exc.detail)),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        body = error_body(request, "validation_error", "Request validation failed")
        details = jsonable_encoder(exc.errors())
        for detail in details:
            detail.pop("input", None)
        body["details"] = details
        return JSONResponse(content=body, status_code=422)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error", exc_info=exc)
        return JSONResponse(
            content=error_body(request, "internal_error", "Internal server error"),
            status_code=500,
        )

    return app
