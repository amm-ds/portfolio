"""Stable strict page-analysis request and response schemas."""

from typing import Literal
from uuid import UUID

from document_intelligence.domain.analysis import (
    AnalysisProgress,
    DocumentRecord,
    PageAnalysisResult,
    PageChatRequest,
    PageChatResponse,
)
from document_intelligence.domain.base import StrictModel
from document_intelligence.jobs.queue import Job


class UploadResponse(StrictModel):
    document: DocumentRecord
    duplicate: bool
    job_id: UUID | None


class QueueResponse(StrictModel):
    documents: list[DocumentRecord]
    jobs: list[Job]


class AnalysisResponse(StrictModel):
    document: DocumentRecord
    analysis: PageAnalysisResult | None
    progress: AnalysisProgress
    analyzer: str | None
    created_at: str
    updated_at: str


class HealthResponse(StrictModel):
    status: Literal["ok", "not_ready"]
    repository: bool
    queue: bool


class LivenessResponse(StrictModel):
    status: Literal["ok"]


__all__ = [
    "AnalysisResponse",
    "HealthResponse",
    "LivenessResponse",
    "PageChatRequest",
    "PageChatResponse",
    "QueueResponse",
    "UploadResponse",
]
