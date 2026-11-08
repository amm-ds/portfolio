"""Tenant-scoped document and page-analysis persistence boundary."""

from typing import Protocol
from uuid import UUID

from document_intelligence.domain.analysis import (
    AnalysisRecord,
    AuditEvent,
    DocumentRecord,
    PageAnalysis,
)


class Repository(Protocol):
    def create_document(self, record: DocumentRecord) -> bool: ...
    def get_document(self, tenant_id: str, document_id: UUID) -> DocumentRecord | None: ...
    def get_by_sha(self, tenant_id: str, sha256: str) -> DocumentRecord | None: ...
    def update_document(self, record: DocumentRecord, expected_version: int) -> bool: ...
    def list_documents(
        self, tenant_id: str, status: str | None = None, limit: int = 100
    ) -> list[DocumentRecord]: ...
    def upsert_analysis(self, record: AnalysisRecord) -> bool: ...
    def get_analysis(self, tenant_id: str, document_id: UUID) -> AnalysisRecord | None: ...
    def save_page_result(
        self,
        tenant_id: str,
        document_id: UUID,
        job_id: UUID,
        page: PageAnalysis,
    ) -> bool: ...
    def append_event(
        self,
        tenant_id: str,
        document_id: UUID,
        event_type: str,
        actor_id: str,
        payload_json: str,
    ) -> AuditEvent: ...
    def ping(self) -> bool: ...
    def close(self) -> None: ...
