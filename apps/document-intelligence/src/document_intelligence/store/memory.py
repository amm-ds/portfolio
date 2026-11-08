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


class InMemoryRepository:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.documents: dict[UUID, DocumentRecord] = {}
        self.analyses: dict[UUID, AnalysisRecord] = {}
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

    def upsert_analysis(self, record: AnalysisRecord) -> bool:
        with self.lock:
            self.analyses[record.document_id] = record
            return True

    def get_analysis(self, tenant_id: str, document_id: UUID) -> AnalysisRecord | None:
        with self.lock:
            record = self.analyses.get(document_id)
            return record if record and record.tenant_id == tenant_id else None

    def save_page_result(
        self,
        tenant_id: str,
        document_id: UUID,
        job_id: UUID,
        page: PageAnalysis,
    ) -> bool:
        with self.lock:
            record = self.analyses.get(document_id)
            if not record or record.tenant_id != tenant_id or record.job_id != job_id:
                return False
            pages = [item for item in (record.analysis.pages if record.analysis else [])]
            pages = [item for item in pages if item.page != page.page]
            pages.append(page)
            pages.sort(key=lambda item: item.page)
            completed = [item for item in pages if item.status == "completed"]
            failed = [item for item in pages if item.status == "failed"]
            self.analyses[document_id] = record.model_copy(
                update={
                    "analysis": PageAnalysisResult(pages=pages),
                    "processed_pages": len(completed) + len(failed),
                    "failed_pages": len(failed),
                    "updated_at": self.clock.now(),
                }
            )
            return True

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
