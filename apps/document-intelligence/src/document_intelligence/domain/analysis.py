"""Versioned page-analysis and persistence contracts.

Page coordinates are resolved from parsed PDF spans by application code. Model
output never provides trusted coordinates; each evidence quote resolves within
exactly one parser page.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from document_intelligence.domain.base import StrictModel

BBox = tuple[float, float, float, float]
DocumentStatus = Literal["uploaded", "processing", "completed", "failed"]
EntityType = Literal[
    "person",
    "organization",
    "email",
    "date",
    "money",
    "location",
    "skill",
    "job_title",
    "equipment",
    "document_id",
    "region",
    "other",
]
PageStatus = Literal["completed", "failed"]


class Evidence(StrictModel):
    """A verbatim quote and its deterministic parser-resolved coordinates."""

    quote: str = Field(min_length=1, max_length=4000)
    page: int | None = Field(default=None, ge=1)
    bbox: BBox | None = None
    resolved: bool = False


class CitedText(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)


class PageSummary(StrictModel):
    summary: str = Field(min_length=1, max_length=4000)
    key_points: list[CitedText] = Field(default_factory=list, max_length=20)


class PageEntity(StrictModel):
    text: str = Field(min_length=1, max_length=1000)
    name: str = Field(min_length=1, max_length=1000)
    type: EntityType
    evidence: Evidence


class PageTopic(StrictModel):
    label: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=4000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)


class ValidationIssue(StrictModel):
    code: str
    path: str
    message: str
    severity: Literal["error", "warning"] = "error"


class PageAnalysis(StrictModel):
    """Resolved, validated analysis of one parser page."""

    page: int = Field(ge=1)
    status: PageStatus
    error: str | None = Field(default=None, max_length=2000)
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=100)
    summary: PageSummary
    entities: list[PageEntity] = Field(default_factory=list, max_length=200)
    topics: list[PageTopic] = Field(default_factory=list, max_length=50)
    text_chars: int = Field(ge=0)
    image_count: int = Field(ge=0)
    table_count: int = Field(ge=0)


class PageAnalysisResult(StrictModel):
    schema_version: Literal["page-analysis-v1"] = "page-analysis-v1"
    pages: list[PageAnalysis] = Field(default_factory=list, max_length=5000)


class PageAnalysisOutput(StrictModel):
    """Raw one-page model output before evidence resolution and validation."""

    summary: PageSummary
    entities: list[PageEntity] = Field(default_factory=list, max_length=200)
    topics: list[PageTopic] = Field(default_factory=list, max_length=50)


class AnalysisProgress(StrictModel):
    page_count: int = Field(ge=0)
    processed_pages: int = Field(ge=0)
    failed_pages: int = Field(ge=0)


class DocumentRecord(StrictModel):
    id: UUID
    tenant_id: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    filename: str
    content_type: str
    storage_key: str
    status: DocumentStatus
    version: int = Field(ge=1)
    page_count: int | None = Field(default=None, ge=1)
    created_at: datetime
    updated_at: datetime


class AnalysisRecord(StrictModel):
    """Mutable per-document analysis state keyed by document id."""

    document_id: UUID
    tenant_id: str
    analyzer: str
    job_id: UUID | None = None
    analysis: PageAnalysisResult | None = None
    page_count: int = Field(ge=0)
    processed_pages: int = Field(ge=0)
    failed_pages: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime

    @property
    def progress(self) -> AnalysisProgress:
        return AnalysisProgress(
            page_count=self.page_count,
            processed_pages=self.processed_pages,
            failed_pages=self.failed_pages,
        )


class AuditEvent(StrictModel):
    id: UUID
    document_id: UUID
    tenant_id: str
    sequence: int = Field(ge=1)
    event_type: str
    actor_id: str
    payload_json: str
    created_at: datetime


class PageChatMessage(StrictModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class PageChatRequest(StrictModel):
    messages: list[PageChatMessage] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def last_message_must_be_user(self) -> "PageChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("The last chat message must have role 'user'")
        return self


class PageChatResponse(StrictModel):
    answer: str = Field(min_length=1, max_length=10_000)
    citations: list[Evidence] = Field(min_length=1, max_length=20)
