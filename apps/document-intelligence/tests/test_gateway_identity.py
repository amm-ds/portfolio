"""Production identity must be gateway-authenticated, not a tenant header."""

import hashlib
import hmac
import time
from pathlib import Path

import pytest
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
        repository_backend="postgres",
        analyzer_backend="model",
        model_api_key="offline-test-key",
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


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"identity_mode": "development"}, "gateway identity"),
        ({"gateway_shared_secret": ""}, "GATEWAY_SHARED_SECRET"),
        ({"repository_backend": "memory"}, "Postgres persistence"),
        ({"analyzer_backend": "fixture"}, "fixture analyzer"),
        ({"model_api_key": ""}, "MODEL_API_KEY"),
    ],
)
def test_invalid_production_configuration_fails_at_startup(
    override: dict[str, str], message: str
) -> None:
    values = {
        "environment": "production",
        "identity_mode": "gateway",
        "gateway_shared_secret": "test-gateway-secret",
        "repository_backend": "postgres",
        "analyzer_backend": "model",
        "model_api_key": "offline-test-key",
    }
    values.update(override)
    with pytest.raises(ValueError, match=message):
        Settings.model_validate(values)
