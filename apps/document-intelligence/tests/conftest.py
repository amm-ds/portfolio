"""Fully offline fixtures: no Postgres, network, model, or credentials."""

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from document_intelligence.analysis.page_analyzer import DeterministicPageAnalyzer
from document_intelligence.analysis.page_chat import DeterministicPageChat
from document_intelligence.api.app import create_app
from document_intelligence.api.state import AppState
from document_intelligence.clock import ManualClock
from document_intelligence.config import Settings
from document_intelligence.documents.storage import LocalBlobStore
from document_intelligence.jobs.memory import InMemoryJobQueue
from document_intelligence.store.memory import InMemoryRepository
from document_intelligence.worker import Worker

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
HEADERS = {"X-Dev-Tenant": "tenant-a", "X-Dev-Actor": "analyst-a"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        identity_mode="development",
        repository_backend="memory",
        blob_dir=tmp_path / "blobs",
        analyzer_backend="fixture",
        heartbeat_seconds=1,
        lease_seconds=60,
        max_job_attempts=3,
    )


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def repository(clock: ManualClock) -> InMemoryRepository:
    return InMemoryRepository(clock)


@pytest.fixture
def queue(clock: ManualClock) -> InMemoryJobQueue:
    return InMemoryJobQueue(clock)


@pytest.fixture
def client(
    settings: Settings,
    repository: InMemoryRepository,
    queue: InMemoryJobQueue,
    clock: ManualClock,
    tmp_path: Path,
) -> Iterator[TestClient]:
    app = create_app(
        settings=settings,
        repository=repository,
        queue=queue,
        blobs=LocalBlobStore(tmp_path / "blobs"),
        analyzer=DeterministicPageAnalyzer(),
        page_chat=DeterministicPageChat(),
        clock=clock,
    )
    with TestClient(app) as test_client:
        yield test_client


def upload(client: TestClient, fixture: str = "analysis-multipage.pdf") -> dict[str, object]:
    response = client.post(
        "/documents",
        headers=HEADERS,
        files={"file": (fixture, (FIXTURES / fixture).read_bytes(), "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def app_state(client: TestClient) -> AppState:
    return cast(AppState, cast(FastAPI, client.app).state.app_state)


def process(client: TestClient, fixture: str = "analysis-multipage.pdf") -> dict[str, object]:
    result = upload(client, fixture)
    state = app_state(client)
    worker = Worker(
        state.service,
        state.queue,
        state.settings,
        owner="test-worker",
    )
    assert worker.run_once()
    document_id = result["document"]["id"]  # type: ignore[index]
    detail = client.get(f"/documents/{document_id}", headers=HEADERS)
    assert detail.status_code == 200, detail.text
    result["document"] = detail.json()
    return result
