"""In-process per-tenant rate limiting on the model-cost endpoints.

Default 30 requests/minute per tenant (Settings.rate_limit_per_minute; 0
disables). The limiter is per process and not shared across replicas.
"""

from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient

from document_intelligence.analysis.page_analyzer import DeterministicPageAnalyzer
from document_intelligence.analysis.page_chat import DeterministicPageChat
from document_intelligence.api.app import create_app
from document_intelligence.api.rate_limit import RateLimiter
from document_intelligence.clock import ManualClock
from document_intelligence.config import Settings
from document_intelligence.documents.storage import LocalBlobStore
from document_intelligence.jobs.memory import InMemoryJobQueue
from document_intelligence.store.memory import InMemoryRepository
from tests.conftest import FIXTURES, HEADERS


def _limited_client(tmp_path: Path, per_minute: int = 2) -> TestClient:
    settings = Settings(
        environment="test",
        identity_mode="development",
        repository_backend="memory",
        blob_dir=tmp_path / "blobs",
        analyzer_backend="fixture",
        rate_limit_per_minute=per_minute,
    )
    clock = ManualClock()
    app = create_app(
        settings=settings,
        repository=InMemoryRepository(clock),
        queue=InMemoryJobQueue(clock),
        blobs=LocalBlobStore(tmp_path / "blobs"),
        analyzer=DeterministicPageAnalyzer(),
        page_chat=DeterministicPageChat(),
        clock=clock,
    )
    return TestClient(app)


def _upload(client: TestClient, headers: dict[str, str] = HEADERS) -> int:
    response = client.post(
        "/documents",
        headers=headers,
        files={
            "file": (
                "analysis-multipage.pdf",
                (FIXTURES / "analysis-multipage.pdf").read_bytes(),
                "application/pdf",
            )
        },
    )
    return response.status_code


class TestRateLimiterUnit:
    def test_window_allows_up_to_limit_then_retries(self) -> None:
        limiter = RateLimiter(per_minute=3, window_s=60.0)
        assert limiter.check("t", now=0.0) is None
        assert limiter.check("t", now=1.0) is None
        assert limiter.check("t", now=2.0) is None
        retry = limiter.check("t", now=3.0)
        assert retry is not None
        assert 0 < retry <= 60.0

    def test_tenants_are_independent(self) -> None:
        limiter = RateLimiter(per_minute=1, window_s=60.0)
        assert limiter.check("a", now=0.0) is None
        assert limiter.check("a", now=1.0) is not None
        assert limiter.check("b", now=1.0) is None

    def test_window_resets_after_window_s(self) -> None:
        limiter = RateLimiter(per_minute=1, window_s=60.0)
        assert limiter.check("t", now=0.0) is None
        assert limiter.check("t", now=10.0) is not None
        assert limiter.check("t", now=60.0) is None

    def test_zero_disables(self) -> None:
        limiter = RateLimiter(per_minute=0)
        for i in range(1000):
            assert limiter.check("t", now=float(i)) is None


class TestUploadRateLimit:
    def test_n_plus_first_request_gets_429_with_retry_after(self, tmp_path: Path) -> None:
        client = _limited_client(tmp_path, per_minute=2)
        with client:
            assert _upload(client) == 201
            assert _upload(client) == 201
            blocked = client.post(
                "/documents",
                headers=HEADERS,
                files={
                    "file": (
                        "analysis-multipage.pdf",
                        (FIXTURES / "analysis-multipage.pdf").read_bytes(),
                        "application/pdf",
                    )
                },
            )
        assert blocked.status_code == 429
        retry_after = blocked.headers.get("Retry-After")
        assert retry_after is not None and float(retry_after) > 0
        assert blocked.json()["error"]["code"] == "http_429"

    def test_different_tenant_is_not_limited(self, tmp_path: Path) -> None:
        client = _limited_client(tmp_path, per_minute=2)
        other = {**HEADERS, "X-Dev-Tenant": "tenant-b"}
        with client:
            assert _upload(client) == 201
            assert _upload(client) == 201
            assert _upload(client) == 429
            assert _upload(client, headers=other) == 201


def test_page_chat_is_limited(tmp_path: Path) -> None:
    """The page-chat endpoint shares the per-tenant limiter."""
    client = _limited_client(tmp_path, per_minute=3)
    with client:
        from tests.conftest import process

        doc = process(client)
        doc_id = cast("dict[str, Any]", doc["document"])["id"]
        url = f"/documents/{doc_id}/pages/1/chat"
        body = {
            "messages": [{"role": "user", "content": "Which organization produced the report?"}]
        }
        assert client.post(url, headers=HEADERS, json=body).status_code == 200
        assert client.post(url, headers=HEADERS, json=body).status_code == 200
        blocked = client.post(url, headers=HEADERS, json=body)
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") is not None
