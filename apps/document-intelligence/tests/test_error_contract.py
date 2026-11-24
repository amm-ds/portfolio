"""Error contract: every client-visible error is the structured envelope and
no traceback or internal path leaks. Health/readiness endpoints exist and are
tested in ``test_api_workflow``."""

import asyncio
import json as jsonlib
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, cast

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from tests.conftest import HEADERS


class _JsonBody(Protocol):
    """The response surface this test needs; TestClient responses satisfy it."""

    def json(self) -> Any: ...


def _envelope(response: _JsonBody) -> dict[str, Any]:
    body = response.json()
    assert "error" in body
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


def test_domain_404_uses_the_same_envelope(client: TestClient) -> None:
    import uuid

    response = client.get(f"/documents/{uuid.uuid4()}", headers=HEADERS)
    assert response.status_code == 404
    error = _envelope(response)
    assert error["code"] == "document_not_found"
    assert "Traceback" not in response.text


def test_validation_error_returns_envelope(client: TestClient) -> None:
    response = client.post("/documents", headers=HEADERS, json={"not": "multipart"})
    assert response.status_code == 422
    error = _envelope(response)
    assert error["code"] == "validation_error"


def test_unhandled_errors_return_generic_message(client: TestClient) -> None:
    """The catch-all handler ships a generic message; details stay server-side."""

    app = cast("FastAPI", client.app)
    handler = cast(
        "Callable[[Request, Exception], Awaitable[Response]]",
        app.exception_handlers[Exception],
    )
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/documents",
        "headers": [],
        "query_string": b"",
        "state": {"request_id": "rid-9"},
    }
    request = Request(scope)

    async def _invoke() -> Response:
        return await handler(request, RuntimeError("secret internal detail /Users/x"))

    response = asyncio.run(_invoke())
    assert response.status_code == 500
    raw = bytes(response.body)
    body = jsonlib.loads(raw)
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["message"] == "Internal server error"
    assert "secret internal detail" not in raw.decode()
    assert "Traceback" not in raw.decode()
    assert body["error"]["request_id"] == "rid-9"
