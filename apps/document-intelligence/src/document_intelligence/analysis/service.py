"""Application workflow: intake, per-page analysis with partial progress."""

import asyncio
import hashlib
import logging
import threading
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from document_intelligence.analysis.evidence import (
    build_page_analysis,
    failed_page_analysis,
)
from document_intelligence.analysis.page_analyzer import PageAnalyzer
from document_intelligence.analysis.page_chat import PageChat
from document_intelligence.clock import Clock
from document_intelligence.documents.parser import (
    ParsedDocument,
    parse_pdf,
    pdf_page_count,
)
from document_intelligence.documents.storage import BlobStore
from document_intelligence.domain.analysis import (
    AnalysisRecord,
    DocumentRecord,
    PageChatMessage,
    PageChatResponse,
)
from document_intelligence.jobs.queue import Job, JobQueue
from document_intelligence.store.audit import canonical_json
from document_intelligence.store.repository import Repository

logger = logging.getLogger(__name__)


class DocumentNotFoundError(LookupError):
    pass


class PageNotFoundError(LookupError):
    pass


class DocumentBusyError(RuntimeError):
    """A reanalysis was requested while the document is still being analyzed."""


class LeaseLostError(RuntimeError):
    """The current worker no longer owns the exact leased job attempt."""


class AnalysisService:
    def __init__(
        self,
        repository: Repository,
        queue: JobQueue,
        blobs: BlobStore,
        analyzer: PageAnalyzer,
        chat: PageChat,
        clock: Clock,
        max_attempts: int = 3,
        max_upload_bytes: int = 10_000_000,
        page_concurrency: int = 3,
        page_text_max_chars: int = 24_000,
        lease_seconds: int = 60,
        max_pdf_pages: int = 500,
    ) -> None:
        self.repository = repository
        self.queue = queue
        self.blobs = blobs
        self.analyzer = analyzer
        self.page_chat = chat
        self.clock = clock
        self.max_attempts = max_attempts
        self.max_upload_bytes = max_upload_bytes
        self.page_concurrency = page_concurrency
        self.page_text_max_chars = page_text_max_chars
        self.lease_seconds = lease_seconds
        self.max_pdf_pages = max_pdf_pages

    def document(self, tenant_id: str, document_id: UUID) -> DocumentRecord:
        record = self.repository.get_document(tenant_id, document_id)
        if record is None:
            raise DocumentNotFoundError(str(document_id))
        return record

    def upload(
        self, tenant_id: str, actor_id: str, filename: str, content_type: str, content: bytes
    ) -> tuple[DocumentRecord, bool]:
        if not content or len(content) > self.max_upload_bytes:
            raise ValueError("Empty or oversized PDF")
        if content_type != "application/pdf" or not content.startswith(b"%PDF-"):
            raise ValueError("Only PDF uploads are supported")
        digest = hashlib.sha256(content).hexdigest()
        existing = self.repository.get_by_sha(tenant_id, digest)
        if existing:
            return existing, False
        page_count = pdf_page_count(content, self.max_pdf_pages)
        now = self.clock.now()
        record = DocumentRecord(
            id=uuid4(),
            tenant_id=tenant_id,
            sha256=digest,
            filename=Path(filename).name[:512] or "document.pdf",
            content_type=content_type,
            storage_key=f"{tenant_id}/{digest}.pdf",
            status="uploaded",
            version=1,
            page_count=page_count,
            created_at=now,
            updated_at=now,
        )
        self.blobs.put(record.storage_key, content)
        if not self.repository.create_document(record):
            existing = self.repository.get_by_sha(tenant_id, digest)
            if existing is None:
                raise RuntimeError("Duplicate upload could not be reloaded")
            return existing, False
        job = self._new_job(record, "analyze")
        enqueued = self.queue.enqueue(job)
        self.repository.append_event(
            tenant_id,
            record.id,
            "document.uploaded",
            actor_id,
            canonical_json({"job_id": str(enqueued.id), "sha256": digest}),
        )
        return record, True

    def _new_job(self, record: DocumentRecord, stage: Literal["analyze", "reanalyze"]) -> Job:
        timestamp = self.clock.now()
        return Job(
            id=uuid4(),
            tenant_id=record.tenant_id,
            document_id=record.id,
            stage=stage,
            status="queued",
            attempts=0,
            max_attempts=self.max_attempts,
            available_at=timestamp,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def _parse_document(self, record: DocumentRecord) -> ParsedDocument:
        return parse_pdf(
            self.blobs.get(record.storage_key),
            page_text_max_chars=self.page_text_max_chars,
            max_pages=self.max_pdf_pages,
        )

    def _ensure_lease(self, job: Job, lease_lost: threading.Event | None) -> None:
        if (
            (lease_lost is not None and lease_lost.is_set())
            or job.lease_owner is None
            or not self.queue.heartbeat(job.id, job.lease_owner, self.lease_seconds)
        ):
            raise LeaseLostError(f"Lease lost for job {job.id} attempt {job.attempts}")

    async def process(self, job: Job, lease_lost: threading.Event | None = None) -> None:
        """Parse once and persist only while this exact attempt owns the lease."""
        self._ensure_lease(job, lease_lost)
        record = self.document(job.tenant_id, job.document_id)
        parsed = self._parse_document(record)
        self._ensure_lease(job, lease_lost)
        if not self.repository.begin_analysis(job, self.analyzer.name, parsed.page_count):
            raise LeaseLostError(f"Analysis start rejected for job {job.id}")
        self.repository.append_event(
            record.tenant_id,
            record.id,
            "analysis.started",
            self.analyzer.name,
            canonical_json({"job_id": str(job.id), "page_count": parsed.page_count}),
        )

        semaphore = asyncio.Semaphore(self.page_concurrency)

        async def analyze_one(page_index: int) -> None:
            page = parsed.pages[page_index]
            async with semaphore:
                self._ensure_lease(job, lease_lost)
                try:
                    output = await self.analyzer.analyze_page(page)
                    result = build_page_analysis(output, page)
                except Exception as exc:
                    result = failed_page_analysis(page, f"{type(exc).__name__}: {exc}")
                self._ensure_lease(job, lease_lost)
                if not self.repository.save_page_result(job, result):
                    raise LeaseLostError(f"Page write rejected for job {job.id}")

        await asyncio.gather(*(analyze_one(index) for index in range(parsed.page_count)))
        self._ensure_lease(job, lease_lost)
        final = self.repository.complete_analysis(job)
        if final is None:
            raise LeaseLostError(f"Final transition rejected for job {job.id}")
        progress = final.progress
        self.repository.append_event(
            record.tenant_id,
            record.id,
            "analysis.completed",
            self.analyzer.name,
            canonical_json(
                {
                    "job_id": str(job.id),
                    "page_count": progress.page_count,
                    "processed_pages": progress.processed_pages,
                    "failed_pages": progress.failed_pages,
                }
            ),
        )

    def analysis_record(self, tenant_id: str, document_id: UUID) -> AnalysisRecord | None:
        self.document(tenant_id, document_id)
        return self.repository.get_analysis(tenant_id, document_id)

    def reanalyze(self, tenant_id: str, document_id: UUID, actor_id: str) -> Job:
        record = self.document(tenant_id, document_id)
        if record.status in {"processing", "queued"}:
            raise DocumentBusyError(
                f"Document {document_id} is {record.status}; reanalysis is not available yet"
            )
        job = self._new_job(record, "reanalyze")
        enqueued = self.queue.enqueue(job)
        if enqueued.id == job.id:
            self.repository.append_event(
                tenant_id,
                document_id,
                "analysis.reanalyze_requested",
                actor_id,
                canonical_json({"job_id": str(job.id)}),
            )
        return enqueued

    async def chat(
        self,
        tenant_id: str,
        document_id: UUID,
        page_number: int,
        messages: list[PageChatMessage],
    ) -> PageChatResponse:
        record = self.document(tenant_id, document_id)
        if record.page_count is not None and page_number > record.page_count:
            raise PageNotFoundError(f"Page {page_number} does not exist")
        parsed = await asyncio.to_thread(self._parse_document, record)
        page = parsed.page(page_number)
        if page is None:
            raise PageNotFoundError(f"Page {page_number} does not exist")
        return await self.page_chat.chat(page, messages)
