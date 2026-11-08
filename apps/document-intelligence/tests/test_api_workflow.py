"""End-to-end page-analysis intake, progress, isolation, and download tests."""

import asyncio
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from document_intelligence.analysis.page_analyzer import DeterministicPageAnalyzer
from document_intelligence.analysis.page_chat import DeterministicPageChat
from document_intelligence.api.app import create_app
from document_intelligence.clock import ManualClock
from document_intelligence.config import Settings
from document_intelligence.documents.parser import ParsedPage
from document_intelligence.documents.storage import LocalBlobStore
from document_intelligence.domain.analysis import (
    PageAnalysis,
    PageAnalysisOutput,
)
from document_intelligence.jobs.memory import InMemoryJobQueue
from document_intelligence.store.memory import InMemoryRepository
from document_intelligence.worker import Worker
from tests.conftest import FIXTURES, HEADERS, app_state, process, upload


def test_duplicate_upload_returns_existing_without_duplicate_job(client: TestClient) -> None:
    first = upload(client)
    second = upload(client)
    assert second["duplicate"] is True
    assert second["document"]["id"] == first["document"]["id"]  # type: ignore[index]
    jobs = client.get("/documents/queue", headers=HEADERS).json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["stage"] == "analyze"


def test_full_analysis_progress_events_and_downloads(client: TestClient) -> None:
    result = process(client)
    document = result["document"]
    document_id = document["id"]  # type: ignore[index]
    assert document["status"] == "completed"  # type: ignore[index]
    assert document["page_count"] == 2  # type: ignore[index]

    analysis = client.get(f"/documents/{document_id}/analysis", headers=HEADERS)
    assert analysis.status_code == 200, analysis.text
    payload = analysis.json()
    assert payload["analysis"]["schema_version"] == "page-analysis-v1"
    assert payload["analyzer"] == "deterministic-page-analysis-v1"
    assert payload["progress"] == {
        "page_count": 2,
        "processed_pages": 2,
        "failed_pages": 0,
    }
    pages = payload["analysis"]["pages"]
    assert [page["page"] for page in pages] == [1, 2]
    assert all(page["status"] == "completed" for page in pages)
    assert all(page["issues"] == [] for page in pages)
    first_page = pages[0]
    assert first_page["summary"]["key_points"]
    assert first_page["summary"]["key_points"][0]["evidence"][0]["resolved"] is True
    assert first_page["summary"]["key_points"][0]["evidence"][0]["page"] == 1
    assert first_page["entities"][0]["evidence"]["resolved"] is True
    assert isinstance(payload["created_at"], str) and isinstance(payload["updated_at"], str)

    full_json = client.get(f"/documents/{document_id}/analysis/export?format=json", headers=HEADERS)
    assert full_json.status_code == 200
    exported = full_json.json()
    assert exported["analysis"]["schema_version"] == "page-analysis-v1"
    assert exported["document"]["id"] == document_id
    assert full_json.content.endswith(b"\n")
    # Canonical export: top-level keys are sorted in the raw document.
    body = full_json.text
    assert (
        body.index('"analyzer"')
        < body.index('"created_at"')
        < body.index('"document"')
        < body.index('"progress"')
    )

    full_md = client.get(f"/documents/{document_id}/analysis/export?format=md", headers=HEADERS)
    assert full_md.status_code == 200
    assert full_md.headers["content-type"].startswith("text/markdown")
    assert "# Document analysis: analysis-multipage.pdf" in full_md.text
    assert "## Page 1" in full_md.text
    assert "## Page 2" in full_md.text
    assert "QUARTERLY RESEARCH REPORT" in full_md.text
    assert "not OCRed" in full_md.text

    page_json = client.get(f"/documents/{document_id}/pages/2/export?format=json", headers=HEADERS)
    assert page_json.status_code == 200
    page_payload = page_json.json()
    assert page_payload["page"]["page"] == 2
    assert page_payload["page"]["status"] == "completed"
    assert page_payload["document"]["id"] == document_id

    page_md = client.get(f"/documents/{document_id}/pages/2/export?format=md", headers=HEADERS)
    assert page_md.status_code == 200
    assert "# Page 2 analysis" in page_md.text
    assert "research program" in page_md.text

    missing_page = client.get(
        f"/documents/{document_id}/pages/9/export?format=json", headers=HEADERS
    )
    assert missing_page.status_code == 404

    content = client.get(f"/documents/{document_id}/content", headers=HEADERS)
    assert content.content == (FIXTURES / "analysis-multipage.pdf").read_bytes()


def test_partial_page_failure_stays_on_that_page(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = upload(client)
    app = app_state(client)
    original = app.service.analyzer.analyze_page

    async def failing(page: ParsedPage) -> PageAnalysisOutput:
        if page.page == 2:
            raise RuntimeError("simulated page failure")
        return await original(page)

    analyzer = Mock(wraps=app.service.analyzer)
    analyzer.name = "failing-test-analyzer"
    analyzer.analyze_page.side_effect = failing
    monkeypatch.setattr(app.service, "analyzer", analyzer)
    job = app.queue.acquire("manual", 60)
    assert job
    asyncio.run(app.service.process(job))

    document_id = result["document"]["id"]  # type: ignore[index]
    payload = client.get(f"/documents/{document_id}/analysis", headers=HEADERS).json()
    assert payload["document"]["status"] == "completed"
    assert payload["progress"] == {"page_count": 2, "processed_pages": 2, "failed_pages": 1}
    pages = {page["page"]: page for page in payload["analysis"]["pages"]}
    assert pages[1]["status"] == "completed"
    assert pages[2]["status"] == "failed"
    assert "simulated page failure" in pages[2]["error"]
    assert pages[2]["text_chars"] > 0


def test_progress_is_persisted_after_every_page(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = upload(client)
    app = app_state(client)
    observed: list[tuple[int, bool]] = []
    original = app.repository.save_page_result

    def spy(tenant_id: str, document_id: UUID, job_id: UUID, page: PageAnalysis) -> bool:
        observed.append((page.page, page.status == "completed"))
        return original(tenant_id, document_id, job_id, page)

    monkeypatch.setattr(app.repository, "save_page_result", spy)
    job = app.queue.acquire("manual", 60)
    assert job
    asyncio.run(app.service.process(job))
    assert sorted(observed) == [(1, True), (2, True)]
    document_id = UUID(str(result["document"]["id"]))  # type: ignore[index]
    stored = app.repository.get_analysis("tenant-a", document_id)
    assert stored is not None
    assert stored.progress.processed_pages == 2


def test_reanalyze_resets_progress_and_is_idempotent(client: TestClient) -> None:
    result = process(client)
    document_id = result["document"]["id"]  # type: ignore[index]
    before = client.get(f"/documents/{document_id}/analysis", headers=HEADERS).json()
    assert before["progress"]["processed_pages"] == 2

    first = client.post(f"/documents/{document_id}/reanalyze", headers=HEADERS)
    second = client.post(f"/documents/{document_id}/reanalyze", headers=HEADERS)
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["stage"] == "reanalyze"

    app = app_state(client)
    assert Worker(app.service, app.queue, app.settings, owner="test-worker").run_once()
    after = client.get(f"/documents/{document_id}/analysis", headers=HEADERS).json()
    assert after["progress"]["processed_pages"] == 2
    assert after["document"]["page_count"] == 2
    assert after["analyzer"] == "deterministic-page-analysis-v1"
    stored = app.repository.get_analysis("tenant-a", UUID(document_id))
    assert stored is not None
    assert stored.job_id == UUID(first.json()["id"])


def test_reanalyze_is_idempotent_per_stage(client: TestClient) -> None:
    result = upload(client)
    document_id = result["document"]["id"]  # type: ignore[index]
    first = client.post(f"/documents/{document_id}/reanalyze", headers=HEADERS)
    second = client.post(f"/documents/{document_id}/reanalyze", headers=HEADERS)
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    jobs = client.get("/documents/queue", headers=HEADERS).json()["jobs"]
    reanalyze = [job for job in jobs if job["stage"] == "reanalyze"]
    assert len(reanalyze) == 1
    assert reanalyze[0]["status"] in {"queued", "leased"}


def test_reanalyze_while_processing_is_conflict(client: TestClient) -> None:
    result = upload(client)
    document_id = result["document"]["id"]  # type: ignore[index]
    app = app_state(client)
    record = app.repository.get_document("tenant-a", UUID(str(document_id)))
    assert record is not None
    busy = record.model_copy(update={"status": "processing", "version": record.version + 1})
    assert app.repository.update_document(busy, record.version)

    response = client.post(f"/documents/{document_id}/reanalyze", headers=HEADERS)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "document_busy"


def test_missing_blob_returns_404(client: TestClient, tmp_path: Path) -> None:
    result = upload(client)
    document_id = result["document"]["id"]  # type: ignore[index]
    record = app_state(client).repository.get_document("tenant-a", UUID(str(document_id)))
    assert record is not None
    (tmp_path / "blobs" / record.storage_key).unlink()

    content = client.get(f"/documents/{document_id}/content", headers=HEADERS)
    assert content.status_code == 404
    assert content.json()["error"]["code"] == "blob_not_found"
    chat = client.post(
        f"/documents/{document_id}/pages/1/chat",
        headers=HEADERS,
        json={"messages": [{"role": "user", "content": "Any text?"}]},
    )
    assert chat.status_code == 404
    assert chat.json()["error"]["code"] == "blob_not_found"


def test_app_lifespan_closes_repository_and_queue(
    settings: Settings,
    repository: InMemoryRepository,
    queue: InMemoryJobQueue,
    clock: ManualClock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_close = Mock(wraps=repository.close)
    queue_close = Mock(wraps=queue.close)
    monkeypatch.setattr(repository, "close", repository_close)
    monkeypatch.setattr(queue, "close", queue_close)
    app = create_app(
        settings=settings,
        repository=repository,
        queue=queue,
        blobs=LocalBlobStore(tmp_path / "blobs"),
        analyzer=DeterministicPageAnalyzer(),
        page_chat=DeterministicPageChat(),
        clock=clock,
    )
    with TestClient(app):
        pass
    repository_close.assert_called_once_with()
    queue_close.assert_called_once_with()


def test_cross_tenant_access_is_404(client: TestClient) -> None:
    result = process(client)
    document_id = result["document"]["id"]  # type: ignore[index]
    other = {"X-Dev-Tenant": "tenant-b", "X-Dev-Actor": "analyst-b"}
    for suffix in (
        "",
        "/content",
        "/analysis",
        "/analysis/export",
        "/pages/1/export",
    ):
        response = client.get(f"/documents/{document_id}{suffix}", headers=other)
        assert response.status_code == 404, suffix
        assert response.json()["error"]["code"] == "document_not_found"
    chat = client.post(
        f"/documents/{document_id}/pages/1/chat",
        headers=other,
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert chat.status_code == 404
    reanalyze = client.post(f"/documents/{document_id}/reanalyze", headers=other)
    assert reanalyze.status_code == 404


def test_list_documents_filters_by_new_statuses(client: TestClient) -> None:
    upload(client)
    pending = client.get("/documents?status=uploaded", headers=HEADERS)
    assert pending.status_code == 200
    assert len(pending.json()) == 1
    process(client)
    completed = client.get("/documents?status=completed", headers=HEADERS)
    assert len(completed.json()) == 1
    legacy = client.get("/documents?status=pending_review", headers=HEADERS)
    assert legacy.status_code == 422


def test_identity_stable_errors_and_old_routes_are_gone(client: TestClient) -> None:
    missing = client.get("/documents")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "http_401"
    assert missing.headers["x-request-id"]
    invalid = client.post(
        "/documents", headers=HEADERS, files={"file": ("x.txt", b"x", "text/plain")}
    )
    assert invalid.status_code == 400
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/documents/{document_id}/analysis" in paths
    assert "/documents/{document_id}/pages/{page}/chat" in paths
    assert "/documents/{document_id}/analysis/export" in paths
    assert "/documents/{document_id}/pages/{page}/export" in paths
    for removed in (
        "/documents/themes",
        "/documents/{document_id}/review",
        "/documents/{document_id}/decision",
        "/documents/{document_id}/ask",
        "/documents/{document_id}/events",
    ):
        assert removed not in paths, removed


def test_crash_mid_run_resets_cleanly_on_retry(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = upload(client)
    app = app_state(client)
    job = app.queue.acquire("manual", 60)
    assert job
    save_page_result = app.repository.save_page_result

    def crash(*args: object, **kwargs: object) -> bool:
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(app.repository, "save_page_result", crash)
    with pytest.raises(RuntimeError, match="simulated crash"):
        asyncio.run(app.service.process(job))
    monkeypatch.setattr(app.repository, "save_page_result", save_page_result)
    asyncio.run(app.service.process(job))
    document_id = result["document"]["id"]  # type: ignore[index]
    payload = client.get(f"/documents/{document_id}/analysis", headers=HEADERS).json()
    assert payload["progress"]["processed_pages"] == 2
    assert payload["document"]["status"] == "completed"
