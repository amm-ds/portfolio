"""Analysis repository semantics against the SQL implementation (sqlite-backed)."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from document_intelligence.clock import ManualClock
from document_intelligence.domain.analysis import DocumentRecord, PageAnalysis
from document_intelligence.jobs.queue import Job
from document_intelligence.store.db_models import Base, JobRow
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


def _leased_job(document: DocumentRecord, clock: ManualClock) -> Job:
    now = clock.now()
    return Job(
        id=uuid4(),
        tenant_id=document.tenant_id,
        document_id=document.id,
        stage="analyze",
        status="leased",
        attempts=1,
        max_attempts=2,
        available_at=now,
        lease_owner="worker-a",
        lease_expires_at=now + timedelta(seconds=60),
        created_at=now,
        updated_at=now,
    )


def _insert_job(repository: PostgresRepository, job: Job) -> None:
    with Session(repository.engine) as session:
        session.add(JobRow(**job.model_dump()))
        session.commit()


def test_analysis_begin_and_page_progress_updates() -> None:
    clock = ManualClock()
    repository = PostgresRepository("sqlite+pysqlite:///:memory:", clock)
    Base.metadata.create_all(repository.engine)
    document = _document(clock)
    assert repository.create_document(document)

    job = _leased_job(document, clock)
    _insert_job(repository, job)
    assert repository.begin_analysis(job, "test-analyzer", 2)
    assert repository.get_analysis("tenant-a", document.id) is not None
    assert repository.get_analysis("tenant-b", document.id) is None

    assert repository.save_page_result(job, _page(1))
    assert repository.save_page_result(job, _page(2, "failed"))
    stored = repository.get_analysis("tenant-a", document.id)
    assert stored is not None
    assert stored.progress.page_count == 2
    assert stored.progress.processed_pages == 2
    assert stored.progress.failed_pages == 1
    assert [page.page for page in stored.analysis.pages] == [1, 2]  # type: ignore[union-attr]

    # Reanalysis resets: a new job id replaces state and ignores the old job.
    replacement_job = _leased_job(document, clock)
    _insert_job(repository, replacement_job)
    assert repository.begin_analysis(replacement_job, "test-analyzer", 2)
    assert repository.save_page_result(job, _page(1)) is False
    assert repository.save_page_result(replacement_job, _page(1))
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
        job = _leased_job(document, clock)
        if repository is sql:
            _insert_job(sql, job)
        assert repository.begin_analysis(job, "test-analyzer", 2)
        assert repository.save_page_result(job, _page(2))
        assert repository.save_page_result(job, _page(1))
        # A duplicate save replaces the page instead of appending it.
        assert repository.save_page_result(job, _page(1))
        stored = repository.get_analysis("tenant-a", document.id)
        assert stored is not None
        assert stored.progress.processed_pages == 2
        assert [page.page for page in stored.analysis.pages] == [1, 2]  # type: ignore[union-attr]
    sql.close()


def test_memory_repository_fences_a_superseded_attempt_of_the_same_job() -> None:
    clock = ManualClock()
    repository = InMemoryRepository(clock)
    document = _document(clock)
    assert repository.create_document(document)
    first = _leased_job(document, clock)
    assert repository.begin_analysis(first, "test-analyzer", 2)
    second = first.model_copy(update={"attempts": 2, "lease_owner": "worker-b"})
    assert repository.begin_analysis(second, "test-analyzer", 2)

    assert not repository.save_page_result(first, _page(1))
    assert repository.complete_analysis(first) is None
    assert repository.save_page_result(second, _page(1))
    assert repository.save_page_result(second, _page(2))
    completed = repository.complete_analysis(second)
    assert completed is not None and completed.progress.processed_pages == 2
