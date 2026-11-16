"""Real-Postgres lease fencing and atomic page-write integration coverage."""

import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import delete

from document_intelligence.clock import ManualClock
from document_intelligence.domain.analysis import DocumentRecord, PageAnalysis
from document_intelligence.jobs.postgres import PostgresJobQueue
from document_intelligence.jobs.queue import Job
from document_intelligence.store.db_models import (
    AuditEventRow,
    Base,
    DocumentAnalysisRow,
    DocumentRow,
    JobRow,
)
from document_intelligence.store.postgres import PostgresRepository

DATABASE_URL = os.environ.get("DOCUMENT_INTELLIGENCE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    DATABASE_URL is None,
    reason="Set DOCUMENT_INTELLIGENCE_TEST_DATABASE_URL to a disposable Postgres database",
)


def _page(number: int) -> PageAnalysis:
    return PageAnalysis(
        page=number,
        status="completed",
        summary={"summary": f"page {number}", "key_points": []},
        text_chars=10,
        image_count=0,
        table_count=0,
    )


def test_interleaved_workers_are_fenced_and_concurrent_pages_are_not_lost() -> None:
    if DATABASE_URL is None:
        return
    clock = ManualClock()
    repository = PostgresRepository(DATABASE_URL, clock)
    queue = PostgresJobQueue(DATABASE_URL, clock)
    Base.metadata.create_all(repository.engine)
    now = clock.now()
    document = DocumentRecord(
        id=uuid4(),
        tenant_id=f"lease-test-{uuid4().hex}",
        sha256=uuid4().hex + uuid4().hex,
        filename="interleaving.pdf",
        content_type="application/pdf",
        storage_key="unused.pdf",
        status="uploaded",
        version=1,
        page_count=2,
        created_at=now,
        updated_at=now,
    )
    queued = Job(
        id=uuid4(),
        tenant_id=document.tenant_id,
        document_id=document.id,
        stage="analyze",
        status="queued",
        attempts=0,
        max_attempts=3,
        available_at=now,
        created_at=now,
        updated_at=now,
    )
    try:
        assert repository.create_document(document)
        queue.enqueue(queued)
        first = queue.acquire("worker-a", lease_seconds=10)
        assert first is not None
        assert repository.begin_analysis(first, "test-analyzer", 2)
        assert repository.save_page_result(first, _page(1))

        clock.advance(11)
        second = queue.acquire("worker-b", lease_seconds=10)
        assert second is not None and second.attempts == 2
        assert repository.begin_analysis(second, "test-analyzer", 2)
        assert not repository.save_page_result(first, _page(2))
        assert repository.complete_analysis(first) is None

        # Both writes read/modify/write one JSON row; row locks must retain both pages.
        with ThreadPoolExecutor(max_workers=2) as pool:
            saves: list[Callable[[], bool]] = [
                lambda: repository.save_page_result(second, _page(1)),
                lambda: repository.save_page_result(second, _page(2)),
            ]
            assert list(pool.map(lambda save: save(), saves)) == [True, True]
        stored = repository.get_analysis(document.tenant_id, document.id)
        assert stored is not None and stored.analysis is not None
        assert [page.page for page in stored.analysis.pages] == [1, 2]
        assert stored.progress.processed_pages == 2

        completed = repository.complete_analysis(second)
        assert completed is not None and completed.progress.processed_pages == 2
        assert not queue.complete(first.id, "worker-a")
        assert queue.complete(second.id, "worker-b")
        final = repository.get_document(document.tenant_id, document.id)
        assert final is not None and final.status == "completed"
    finally:
        with repository.engine.begin() as connection:
            connection.execute(
                delete(AuditEventRow).where(AuditEventRow.document_id == document.id)
            )
            connection.execute(
                delete(DocumentAnalysisRow).where(DocumentAnalysisRow.document_id == document.id)
            )
            connection.execute(delete(JobRow).where(JobRow.document_id == document.id))
            connection.execute(delete(DocumentRow).where(DocumentRow.id == document.id))
        queue.close()
        repository.close()
