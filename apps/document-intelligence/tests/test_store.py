"""Analysis repository semantics against the SQL implementation (sqlite-backed)."""

from uuid import UUID, uuid4

from document_intelligence.clock import ManualClock
from document_intelligence.domain.analysis import (
    AnalysisRecord,
    DocumentRecord,
    PageAnalysis,
)
from document_intelligence.store.db_models import Base
from document_intelligence.store.memory import InMemoryRepository
from document_intelligence.store.postgres import PostgresRepository


def _document(clock: ManualClock, status: str = "completed") -> DocumentRecord:
    now = clock.now()
    return DocumentRecord(
        id=uuid4(),
        tenant_id="tenant-a",
        sha256="a" * 64,
        filename="report.pdf",
        content_type="application/pdf",
        storage_key="tenant-a/report.pdf",
        status=status,
        version=1,
        page_count=2,
        created_at=now,
        updated_at=now,
    )


def _page(number: int, status: str = "completed") -> PageAnalysis:
    return PageAnalysis(
        page=number,
        status=status,
        error="boom" if status == "failed" else None,
        summary={"summary": "s", "key_points": []},
        text_chars=10,
        image_count=0,
        table_count=0,
    )


def _record(document: DocumentRecord, job_id: UUID | None) -> AnalysisRecord:
    now = ManualClock().now()
    return AnalysisRecord(
        document_id=document.id,
        tenant_id=document.tenant_id,
        analyzer="deterministic-page-analysis-v1",
        job_id=job_id,
        analysis=None,
        page_count=2,
        processed_pages=0,
        failed_pages=0,
        created_at=now,
        updated_at=now,
    )


def test_analysis_upsert_and_page_progress_updates() -> None:
    clock = ManualClock()
    repository = PostgresRepository("sqlite+pysqlite:///:memory:", clock)
    Base.metadata.create_all(repository.engine)
    document = _document(clock)
    assert repository.create_document(document)

    job_id = uuid4()
    record = _record(document, job_id)
    assert repository.upsert_analysis(record)
    assert repository.get_analysis("tenant-a", document.id) is not None
    assert repository.get_analysis("tenant-b", document.id) is None

    assert repository.save_page_result("tenant-a", document.id, job_id, _page(1))
    assert repository.save_page_result("tenant-a", document.id, job_id, _page(2, "failed"))
    stored = repository.get_analysis("tenant-a", document.id)
    assert stored is not None
    assert stored.progress.page_count == 2
    assert stored.progress.processed_pages == 2
    assert stored.progress.failed_pages == 1
    assert [page.page for page in stored.analysis.pages] == [1, 2]  # type: ignore[union-attr]

    # Reanalysis resets: a new job id replaces state and ignores the old job.
    replacement = _record(document, uuid4()).model_copy(update={"processed_pages": 0})
    assert repository.upsert_analysis(replacement)
    stale = repository.save_page_result("tenant-a", document.id, job_id, _page(1))
    assert stale is False
    assert replacement.job_id is not None
    assert repository.save_page_result("tenant-a", document.id, replacement.job_id, _page(1))
    stored = repository.get_analysis("tenant-a", document.id)
    assert stored is not None
    assert stored.failed_pages == 0
    assert len(stored.analysis.pages) == 1  # type: ignore[union-attr]
    repository.close()


def test_memory_and_postgres_share_page_progress_semantics() -> None:
    clock = ManualClock()
    memory = InMemoryRepository(clock)
    sql = PostgresRepository("sqlite+pysqlite:///:memory:", clock)
    Base.metadata.create_all(sql.engine)
    for repository in (memory, sql):
        document = _document(clock)
        assert repository.create_document(document)
        job_id = uuid4()
        repository.upsert_analysis(_record(document, job_id))
        assert repository.save_page_result("tenant-a", document.id, job_id, _page(2))
        assert repository.save_page_result("tenant-a", document.id, job_id, _page(1))
        # A duplicate save replaces the page instead of appending it.
        assert repository.save_page_result("tenant-a", document.id, job_id, _page(1))
        stored = repository.get_analysis("tenant-a", document.id)
        assert stored is not None
        assert stored.progress.processed_pages == 2
        assert [page.page for page in stored.analysis.pages] == [1, 2]  # type: ignore[union-attr]
    sql.close()
