"""Ops endpoints: health, readiness, ingest, auth stub, and request ids."""

import json
import queue as thread_queue
import threading
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from agent_chat.api.app import create_app
from agent_chat.config import Settings
from agent_chat.rag.embeddings import HashingEmbedder
from agent_chat.testing import FakeStep
from tests import SESSION_HEADERS, fakes


class TestHealth:
    def test_health(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "provider": "ollama", "model": "qwen3:8b"}

    def test_kimi_health_reports_selected_model(self, tmp_path: Path) -> None:
        settings = Settings(
            provider="kimi",
            kimi_model="k3-256k",
            database_url=f"sqlite:///{tmp_path}/kimi.db",
            embedder="hashing",
        )
        app = create_app(settings=settings, model=fakes.app_model(), embedder=HashingEmbedder())
        with TestClient(app) as kimi_client:
            response = kimi_client.get("/health")
        assert response.json() == {"status": "ok", "provider": "kimi", "model": "k3-256k"}

    def test_ready(self, client: TestClient) -> None:
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


class TestIngestEndpoint:
    def test_ingest_documents(self, client: TestClient, tmp_path: Path) -> None:
        docs = tmp_path / "kb"
        docs.mkdir()
        (docs / "policies.md").write_text(
            "Passwords rotate every 60 days. Badge access is audited quarterly.\n",
            encoding="utf-8",
        )
        response = client.post("/ingest", json={"paths": [str(docs)]})
        assert response.status_code == 200
        body = response.json()
        assert body["files"] == 1
        assert body["chunks"] >= 1

    def test_ingest_nothing_found_is_400(self, client: TestClient, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        response = client.post("/ingest", json={"paths": [str(empty)]})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "http_400"

    def test_ingest_outside_configured_roots_is_403(self, client: TestClient) -> None:
        response = client.post("/ingest", json={"paths": ["/etc"]})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "http_403"


class TestApiKey:
    def _authed_app(self, tmp_path: Path, key: str) -> Any:
        settings = Settings(
            database_url=f"sqlite:///{tmp_path}/auth.db",
            embedder="hashing",
            api_key=key,
        )
        return create_app(settings=settings, model=fakes.app_model(), embedder=HashingEmbedder())

    def test_missing_and_wrong_key_rejected(self, tmp_path: Path) -> None:
        app = self._authed_app(tmp_path, "s3cret")
        with TestClient(app) as client:
            assert client.post("/chat", json={"message": "hi"}).status_code == 401
            assert client.post("/chat", json={"message": "hi"}).status_code == 401
            denied = client.post("/ingest", json={"paths": ["/tmp"]})
            assert denied.status_code == 401

    def test_wrong_key_also_rejected(self, tmp_path: Path) -> None:
        app = self._authed_app(tmp_path, "s3cret")
        with TestClient(app) as client:
            response = client.post("/chat", json={"message": "hi"}, headers={"X-API-Key": "wrong"})
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "http_401"

    def test_correct_key_streams(self, tmp_path: Path) -> None:
        app = self._authed_app(tmp_path, "s3cret")
        with TestClient(app) as client:
            fakes.queue.append(
                FakeStep(
                    tool_call=(
                        "final_result",
                        {"text": "ok", "citations": [], "uncertainty": "low"},
                    )
                )
            )
            sink: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue()

            def _run() -> None:
                with client.stream(
                    "POST",
                    "/chat",
                    json={"message": "hi"},
                    headers={"X-API-Key": "s3cret", **SESSION_HEADERS},
                ) as response:
                    assert response.status_code == 200
                    for line in response.iter_lines():
                        if line.startswith("data: ") and line != "data: [DONE]":
                            sink.put(json.loads(line.removeprefix("data: ")))

            thread = threading.Thread(target=_run, daemon=True)
            thread.start()
            done = sink.get(timeout=10)
            assert done["type"] == "done"
            thread.join(timeout=10)

    def test_health_stays_open(self, tmp_path: Path) -> None:
        app = self._authed_app(tmp_path, "s3cret")
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200


class TestRequestId:
    def test_header_echoed_on_every_response(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.headers["x-request-id"]

    def test_error_envelope_carries_request_id(self, client: TestClient) -> None:
        response = client.get("/conversations/nope")
        request_id = response.json()["error"]["request_id"]
        assert request_id == response.headers["x-request-id"]
