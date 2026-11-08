"""Production identity must be gateway-authenticated, not a tenant header."""

import hashlib
import hmac
import time
from pathlib import Path

from fastapi.testclient import TestClient

from document_intelligence.analysis.page_analyzer import DeterministicPageAnalyzer
from document_intelligence.analysis.page_chat import DeterministicPageChat
from document_intelligence.api.app import create_app
from document_intelligence.clock import ManualClock
from document_intelligence.config import Settings
from document_intelligence.documents.storage import LocalBlobStore
from document_intelligence.jobs.memory import InMemoryJobQueue
from document_intelligence.store.memory import InMemoryRepository


def gateway_client(tmp_path: Path, secret: str) -> TestClient:
    settings = Settings(
        environment="production",
        identity_mode="gateway",
        gateway_shared_secret=secret,
        repository_backend="memory",
        blob_dir=tmp_path / "blobs",
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


def test_unsigned_tenant_header_is_rejected(tmp_path: Path) -> None:
    with gateway_client(tmp_path, "test-gateway-secret") as client:
        response = client.get("/documents", headers={"X-Gateway-Tenant": "tenant-a"})
        assert response.status_code == 401


def test_valid_signed_gateway_identity_is_accepted(tmp_path: Path) -> None:
    timestamp = str(int(time.time()))
    message = f"v1\n{timestamp}\ntenant-a\nactor-a"
    signature = hmac.new(b"test-gateway-secret", message.encode(), hashlib.sha256).hexdigest()
    with gateway_client(tmp_path, "test-gateway-secret") as client:
        response = client.get(
            "/documents",
            headers={
                "X-Gateway-Tenant": "tenant-a",
                "X-Gateway-Actor": "actor-a",
                "X-Gateway-Timestamp": timestamp,
                "X-Gateway-Signature": signature,
            },
        )
        assert response.status_code == 200
        assert response.json() == []


def test_development_identity_fails_closed_in_production(tmp_path: Path) -> None:
    settings = Settings(
        environment="production",
        identity_mode="development",
        repository_backend="memory",
        blob_dir=tmp_path / "blobs",
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
    with TestClient(app) as client:
        response = client.get(
            "/documents", headers={"X-Dev-Tenant": "tenant-a", "X-Dev-Actor": "actor-a"}
        )
        assert response.status_code == 500
