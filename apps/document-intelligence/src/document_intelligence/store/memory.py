"""Thread-safe single-process repository for deterministic tests."""

from threading import RLock
from uuid import UUID, uuid4

from document_intelligence.clock import Clock
from document_intelligence.domain.analysis import (
    AnalysisRecord,
    AuditEvent,
    DocumentRecord,
    PageAnalysis,
    PageAnalysisResult,
)
from document_intelligence.jobs.queue import Job


class InMemoryRepository:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.documents: dict[UUID, DocumentRecord] = {}
        self.analyses: dict[UUID, AnalysisRecord] = {}
        self.analysis_leases: dict[UUID, tuple[str | None, int]] = {}
        self.events: list[AuditEvent] = []
        self.sequence = 0
        self.lock = RLock()

    def create_document(self, record: DocumentRecord) -> bool:
        with self.lock:
            if any(
                item.tenant_id == record.tenant_id and item.sha256 == record.sha256
                for item in self.documents.values()
            ):
                return False
            self.documents[record.id] = record
            return True

    def get_document(self, tenant_id: str, document_id: UUID) -> DocumentRecord | None:
        with self.lock:
            record = self.documents.get(document_id)
            return record if record and record.tenant_id == tenant_id else None

    def get_by_sha(self, tenant_id: str, sha256: str) -> DocumentRecord | None:
        with self.lock:
            return next(
                (
                    record
                    for record in self.documents.values()
                    if record.tenant_id == tenant_id and record.sha256 == sha256
                ),
                None,
            )

    def update_document(self, record: DocumentRecord, expected_version: int) -> bool:
        with self.lock:
            current = self.documents.get(record.id)
            if (
                not current
                or current.tenant_id != record.tenant_id
                or current.version != expected_version
            ):
                return False
            self.documents[record.id] = record
            return True

    def list_documents(
        self, tenant_id: str, status: str | None = None, limit: int = 100
    ) -> list[DocumentRecord]:
        with self.lock:
            records = [
                record
                for record in self.documents.values()
                if record.tenant_id == tenant_id and (status is None or record.status == status)
            ]
            return sorted(records, key=lambda record: record.created_at, reverse=True)[:limit]

    def get_analysis(self, tenant_id: str, document_id: UUID) -> AnalysisRecord | None:
        with self.lock:
            record = self.analyses.get(document_id)
            return record if record and record.tenant_id == tenant_id else None

    def _current_analysis(self, job: Job) -> AnalysisRecord | None:
        record = self.analyses.get(job.document_id)
        if (
            not record
            or record.tenant_id != job.tenant_id
            or record.job_id != job.id
            or self.analysis_leases.get(job.document_id) != (job.lease_owner, job.attempts)
        ):
            return None
        return record

    def begin_analysis(self, job: Job, analyzer: str, page_count: int) -> bool:
        with self.lock:
            document = self.documents.get(job.document_id)
            if not document or document.tenant_id != job.tenant_id:
                return False
            previous = self.analyses.get(job.document_id)
            now = self.clock.now()
            self.analyses[job.document_id] = AnalysisRecord(
                document_id=job.document_id,
                tenant_id=job.tenant_id,
                analyzer=analyzer,
                job_id=job.id,
                analysis=None,
                page_count=page_count,
                processed_pages=0,
                failed_pages=0,
                created_at=previous.created_at if previous else now,
                updated_at=now,
            )
            self.analysis_leases[job.document_id] = (job.lease_owner, job.attempts)
            self.documents[job.document_id] = document.model_copy(
                update={
                    "status": "processing",
                    "version": document.version + 1,
                    "page_count": page_count,
                    "updated_at": now,
                }
            )
            return True

    def save_page_result(self, job: Job, page: PageAnalysis) -> bool:
        with self.lock:
            record = self._current_analysis(job)
            if record is None:
                return False
            pages = [item for item in (record.analysis.pages if record.analysis else [])]
            pages = [item for item in pages if item.page != page.page]
            pages.append(page)
            pages.sort(key=lambda item: item.page)
            self.analyses[job.document_id] = record.model_copy(
                update={
                    "analysis": PageAnalysisResult(pages=pages),
                    "processed_pages": len(pages),
                    "failed_pages": sum(item.status == "failed" for item in pages),
                    "updated_at": self.clock.now(),
                }
            )
            return True

    def complete_analysis(self, job: Job) -> AnalysisRecord | None:
        with self.lock:
            record = self._current_analysis(job)
            document = self.documents.get(job.document_id)
            if (
                record is None
                or not document
                or record.page_count == 0
                or record.processed_pages != record.page_count
            ):
                return None
            self.documents[job.document_id] = document.model_copy(
                update={
                    "status": "completed",
                    "version": document.version + 1,
                    "page_count": record.page_count,
                    "updated_at": self.clock.now(),
                }
            )
            return record

    def append_event(
        self,
        tenant_id: str,
        document_id: UUID,
        event_type: str,
        actor_id: str,
        payload_json: str,
    ) -> AuditEvent:
        with self.lock:
            self.sequence += 1
            event = AuditEvent(
                id=uuid4(),
                document_id=document_id,
                tenant_id=tenant_id,
                sequence=self.sequence,
                event_type=event_type,
                actor_id=actor_id,
                payload_json=payload_json,
                created_at=self.clock.now(),
            )
            self.events.append(event)
            return event

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None
