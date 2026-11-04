"""FastAPI app: /predict, /predict/batch, /health, /ready.

One app factory, two backends (``--backend native|onnx`` in the loader).
Every response carries a request id; unexpected failures return a structured
error envelope instead of a stack trace. Malformed payloads are rejected by
the pydantic schema with the framework's standard 422 shape.
"""

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from model_serving.service.model import BackendName, ModelLoader
from model_serving.service.schemas import (
    BatchPredictRequest,
    PredictRequest,
    PredictResponse,
)

DEFAULT_MODELS_DIR = Path("data/models")


def _envelope(code: str, message: str, request_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    loader: ModelLoader = app.state.loader
    loader.warmup()
    yield


def create_app(models_dir: Path | None = None, backend: BackendName | None = None) -> FastAPI:
    """Build the service app; env vars win when args are absent (container path)."""
    models_dir = models_dir or Path(os.environ.get("MODELS_DIR", str(DEFAULT_MODELS_DIR)))
    if backend is None:
        backend = "native" if os.environ.get("SERVING_BACKEND") == "native" else "onnx"
    app = FastAPI(title="model-serving — champion tabular MLP", lifespan=_lifespan)
    app.state.loader = ModelLoader(models_dir, backend)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", uuid.uuid4().hex)
        return JSONResponse(
            status_code=500,
            content=_envelope("internal_error", f"{type(exc).__name__}: {exc}", rid),
        )

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Keep the framework's 422 shape; add the request id so failures are traceable.
        rid = getattr(request.state, "request_id", uuid.uuid4().hex)
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "request_id": rid},
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(request: Request) -> JSONResponse:
        loader: ModelLoader = request.app.state.loader
        rid = getattr(request.state, "request_id", uuid.uuid4().hex)
        if not loader.ready:
            return JSONResponse(
                status_code=503,
                content=_envelope("not_ready", "model backend not warmed yet", rid),
            )
        return JSONResponse(
            status_code=200,
            content={"status": "ready", "backend": loader.backend, "request_id": rid},
        )

    @app.post("/predict")
    async def predict(request: Request, body: PredictRequest) -> PredictResponse:
        loader: ModelLoader = request.app.state.loader
        (value,) = loader.predict_rows([body.row])
        return PredictResponse(
            prediction=float(value),
            backend=loader.backend,
            request_id=request.state.request_id,
        )

    @app.post("/predict/batch")
    async def predict_batch(request: Request, body: BatchPredictRequest) -> PredictResponse:
        loader: ModelLoader = request.app.state.loader
        values = loader.predict_rows(list(body.rows))
        return PredictResponse(
            predictions=[float(v) for v in values],
            backend=loader.backend,
            request_id=request.state.request_id,
        )

    return app
