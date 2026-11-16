"""Postgres repository with tenant predicates and single-row progress updates."""

from uuid import UUID, uuid4

from sqlalchemy import create_engine, desc, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from document_intelligence.clock import Clock
from document_intelligence.domain.analysis import (
    AnalysisRecord,
    AuditEvent,
    DocumentRecord,
    PageAnalysis,
    PageAnalysisResult,
)
from document_intelligence.jobs.queue import Job
from document_intelligence.store.db_models import (
    AuditEventRow,
    DocumentAnalysisRow,
    DocumentRow,
    JobRow,
)


def _document(row: DocumentRow) -> DocumentRecord:
    return DocumentRecord.model_validate(
        {column.name: getattr(row, column.name) for column in DocumentRow.__table__.columns}
    )


def _analysis(row: DocumentAnalysisRow) -> AnalysisRecord:
    columns = DocumentAnalysisRow.__table__.columns
    values = {column.name: getattr(row, column.name) for column in columns}
    if values["analysis"] is not None:
        values["analysis"] = PageAnalysisResult.model_validate(values["analysis"])
    return AnalysisRecord.model_validate(values)


def _event(row: AuditEventRow) -> AuditEvent:
    return AuditEvent.model_validate(
        {column.name: getattr(row, column.name) for column in AuditEventRow.__table__.columns}
    )


class PostgresRepository:
    def __init__(self, database_url: str, clock: Clock) -> None:
        self.engine: Engine = create_engine(database_url, pool_pre_ping=True)
        self.clock = clock

    def create_document(self, record: DocumentRecord) -> bool:
        try:
            with Session(self.engine) as session:
                session.add(DocumentRow(**record.model_dump()))
                session.commit()
            return True
        except IntegrityError:
            return False

    def get_document(self, tenant_id: str, document_id: UUID) -> DocumentRecord | None:
        with Session(self.engine) as session:
            row = session.get(DocumentRow, document_id)
            return _document(row) if row and row.tenant_id == tenant_id else None

    def get_by_sha(self, tenant_id: str, sha256: str) -> DocumentRecord | None:
        with Session(self.engine) as session:
            row = session.scalar(
                select(DocumentRow).where(
                    DocumentRow.tenant_id == tenant_id, DocumentRow.sha256 == sha256
                )
            )
            return _document(row) if row else None

    def update_document(self, record: DocumentRecord, expected_version: int) -> bool:
        values = record.model_dump()
        document_id = values.pop("id")
        tenant_id = values.pop("tenant_id")
        with Session(self.engine) as session:
            result = session.execute(
                update(DocumentRow)
                .where(
                    DocumentRow.id == document_id,
                    DocumentRow.tenant_id == tenant_id,
                    DocumentRow.version == expected_version,
                )
                .values(**values)
            )
            session.commit()
            return getattr(result, "rowcount", 0) == 1

    def list_documents(
        self, tenant_id: str, status: str | None = None, limit: int = 100
    ) -> list[DocumentRecord]:
        statement = select(DocumentRow).where(DocumentRow.tenant_id == tenant_id)
        if status is not None:
            statement = statement.where(DocumentRow.status == status)
        with Session(self.engine) as session:
            rows = session.scalars(
                statement.order_by(desc(DocumentRow.created_at)).limit(limit)
            ).all()
            return [_document(row) for row in rows]

    def get_analysis(self, tenant_id: str, document_id: UUID) -> AnalysisRecord | None:
        with Session(self.engine) as session:
            row = session.get(DocumentAnalysisRow, document_id)
            return _analysis(row) if row and row.tenant_id == tenant_id else None

    def _current_lease(self, session: Session, job: Job) -> JobRow | None:
        if job.lease_owner is None:
            return None
        return session.scalar(
            select(JobRow)
            .where(
                JobRow.id == job.id,
                JobRow.tenant_id == job.tenant_id,
                JobRow.document_id == job.document_id,
                JobRow.status == "leased",
                JobRow.lease_owner == job.lease_owner,
                JobRow.attempts == job.attempts,
                JobRow.lease_expires_at > self.clock.now(),
            )
            .with_for_update()
        )

    def begin_analysis(self, job: Job, analyzer: str, page_count: int) -> bool:
        """Reset analysis and mark processing only while this attempt owns the lease."""
        with Session(self.engine) as session:
            row = session.get(DocumentAnalysisRow, job.document_id, with_for_update=True)
            document = session.get(DocumentRow, job.document_id, with_for_update=True)
            if document is None or document.tenant_id != job.tenant_id:
                return False
            if self._current_lease(session, job) is None:
                return False
            now = self.clock.now()
            values = {
                "document_id": job.document_id,
                "tenant_id": job.tenant_id,
                "analyzer": analyzer,
                "job_id": job.id,
                "analysis": None,
                "page_count": page_count,
                "processed_pages": 0,
                "failed_pages": 0,
                "created_at": row.created_at if row else now,
                "updated_at": now,
            }
            if row is None:
                session.add(DocumentAnalysisRow(**values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            document.status = "processing"
            document.page_count = page_count
            document.version += 1
            document.updated_at = now
            session.commit()
            return True

    def save_page_result(self, job: Job, page: PageAnalysis) -> bool:
        """Atomically replace one page after fencing the job attempt and owner."""
        with Session(self.engine) as session:
            row = session.get(DocumentAnalysisRow, job.document_id, with_for_update=True)
            if row is None or row.tenant_id != job.tenant_id or row.job_id != job.id:
                return False
            if self._current_lease(session, job) is None:
                return False
            stored = PageAnalysisResult.model_validate(row.analysis) if row.analysis else None
            pages = [item for item in (stored.pages if stored else []) if item.page != page.page]
            pages.append(page)
            pages.sort(key=lambda item: item.page)
            row.analysis = PageAnalysisResult(pages=pages).model_dump(mode="json")
            row.processed_pages = len(pages)
            row.failed_pages = sum(item.status == "failed" for item in pages)
            row.updated_at = self.clock.now()
            session.commit()
            return True

    def complete_analysis(self, job: Job) -> AnalysisRecord | None:
        """Fence and complete the document only after every page was persisted."""
        with Session(self.engine) as session:
            row = session.get(DocumentAnalysisRow, job.document_id, with_for_update=True)
            if row is None or row.tenant_id != job.tenant_id or row.job_id != job.id:
                return None
            document = session.get(DocumentRow, job.document_id, with_for_update=True)
            if document is None or document.tenant_id != job.tenant_id:
                return None
            if self._current_lease(session, job) is None:
                return None
            if row.page_count == 0 or row.processed_pages != row.page_count:
                return None
            document.status = "completed"
            document.page_count = row.page_count
            document.version += 1
            document.updated_at = self.clock.now()
            session.commit()
            return _analysis(row)

    def append_event(
        self,
        tenant_id: str,
        document_id: UUID,
        event_type: str,
        actor_id: str,
        payload_json: str,
    ) -> AuditEvent:
        row = AuditEventRow(
            id=uuid4(),
            tenant_id=tenant_id,
            document_id=document_id,
            event_type=event_type,
            actor_id=actor_id,
            payload_json=payload_json,
            created_at=self.clock.now(),
        )
        with Session(self.engine) as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return _event(row)

    def ping(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def close(self) -> None:
        self.engine.dispose()
