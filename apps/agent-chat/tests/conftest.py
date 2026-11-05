"""Shared test fixtures: tmp stores, the hashing embedder, and the app.

Everything runs against SQLite files in ``tmp_path``, the hashing embedder,
and the scripted fake model — no network, no Ollama, no API keys, no docker.
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_chat.api.app import create_app
from agent_chat.config import Settings
from agent_chat.memory import SQLiteConversationStore, build_conversation_store
from agent_chat.rag.embeddings import HashingEmbedder
from agent_chat.rag.store import SQLiteVectorStore, build_vector_store
from tests import fakes


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run every async test on anyio's asyncio backend (no per-test marker)."""
    for item in items:
        if isinstance(item, pytest.Function) and asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.anyio)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Every test runs on SQLite files under tmp_path."""
    return Settings(
        database_url=f"sqlite:///{tmp_path}/agent_chat.db",
        embedder="hashing",
    )


@pytest.fixture
def embedder() -> HashingEmbedder:
    return HashingEmbedder()


@pytest.fixture
def vector_store(settings: Settings, embedder: HashingEmbedder) -> SQLiteVectorStore:
    store = build_vector_store(settings, embedder.dim)
    assert isinstance(store, SQLiteVectorStore)
    return store


@pytest.fixture
def conversation_store(settings: Settings) -> SQLiteConversationStore:
    store = build_conversation_store(settings)
    assert isinstance(store, SQLiteConversationStore)
    return store


@pytest.fixture
async def seeded_store(
    vector_store: SQLiteVectorStore, embedder: HashingEmbedder, tmp_path: Path
) -> AsyncIterator[SQLiteVectorStore]:
    """A vector store pre-loaded with two small documents."""
    from agent_chat.rag.ingest import ingest

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "refunds.md").write_text(
        "Customers may request a full refund within 30 days of purchase. "
        "After 30 days, refunds need manager approval.\n",
        encoding="utf-8",
    )
    (docs / "sla.md").write_text(
        "Severity-1 incidents receive a first response within 1 hour. "
        "Severity-2 within 4 business hours.\n",
        encoding="utf-8",
    )
    await ingest([docs], store=vector_store, embedder=embedder)
    yield vector_store


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """An API client with the scripted fake model and SQLite stores."""
    fakes.queue.clear()  # each test scripts exactly its own steps
    app = create_app(settings=settings, model=fakes.app_model(), embedder=HashingEmbedder())
    with TestClient(app) as test_client:
        yield test_client
