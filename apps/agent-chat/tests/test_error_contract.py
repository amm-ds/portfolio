"""Error contract: every client-visible error is the structured envelope and
no traceback or internal path leaks. Health/readiness endpoints are covered
in ``test_api_admin`` (both exist and answer)."""

import asyncio
import json as jsonlib
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol, cast

from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from agent_chat.api.app import create_app
from agent_chat.config import Settings
from agent_chat.rag.embeddings import HashingEmbedder
from tests import fakes


class _JsonBody(Protocol):
    """The response surface this test needs; TestClient responses satisfy it."""

    def json(self) -> Any: ...


def _envelope(response: _JsonBody) -> dict[str, Any]:
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "request_id"}
    return cast("dict[str, Any]", body["error"])


def test_unknown_path_returns_envelope_without_traceback(client: TestClient) -> None:
    response = client.get("/no-such-route")
    assert response.status_code == 404
    error = _envelope(response)
    assert error["code"] == "http_404"
    assert "Traceback" not in response.text
    assert "/Users/" not in response.text
    assert error["request_id"]


def test_validation_error_returns_envelope(client: TestClient) -> None:
    response = client.post("/chat", json={"not-a-field": 1})
    assert response.status_code in (401, 422)  # 401 only if a key is configured
    if response.status_code == 422:
        error = _envelope(response)
        assert error["code"] == "validation_error"
        assert "Traceback" not in response.text


def test_unhandled_errors_return_envelope_with_type_name_only(tmp_path: Path) -> None:
    """The catch-all handler logs server-side and ships only the type name."""
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/errors.db",
        embedder="hashing",
    )
    app = create_app(settings=settings, model=fakes.app_model(), embedder=HashingEmbedder())

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/chat",
        "headers": [],
        "query_string": b"",
        "state": {"request_id": "rid-1"},
    }
    request = Request(scope)
    handler = cast(
        "Callable[[Request, Exception], Awaitable[Response]]",
        app.exception_handlers[Exception],
    )

    async def _invoke() -> Response:
        return await handler(request, RuntimeError("secret internal detail /Users/x"))

    response = asyncio.run(_invoke())
    assert response.status_code == 500
    raw = bytes(response.body)
    body = jsonlib.loads(raw)
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "RuntimeError"
    assert "secret internal detail" not in raw.decode()
    assert "Traceback" not in raw.decode()
    assert body["error"]["request_id"] == "rid-1"
