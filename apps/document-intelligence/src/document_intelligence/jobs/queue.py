"""Leased job contract shared by in-memory and Postgres queues."""

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from document_intelligence.domain.base import StrictModel

JobStatus = Literal["queued", "leased", "completed", "failed"]


class Job(StrictModel):
    id: UUID
    tenant_id: str
    document_id: UUID
    stage: Literal["analyze", "reanalyze"]
    status: JobStatus
    attempts: int
    max_attempts: int
    available_at: datetime
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class JobQueue(Protocol):
    def enqueue(self, job: Job) -> Job: ...
    def acquire(self, owner: str, lease_seconds: int) -> Job | None: ...
    def heartbeat(self, job_id: UUID, owner: str, lease_seconds: int) -> bool: ...
    def complete(self, job_id: UUID, owner: str) -> bool: ...
    def fail(self, job_id: UUID, owner: str, error: str) -> Job | None: ...
    def list(self, tenant_id: str, limit: int = 100) -> list[Job]: ...
    def ping(self) -> bool: ...
    def close(self) -> None: ...
