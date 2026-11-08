"""Deterministic single-process queue for tests, not multi-process production."""

from datetime import timedelta
from threading import RLock
from uuid import UUID

from document_intelligence.clock import Clock
from document_intelligence.jobs.queue import Job


class InMemoryJobQueue:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.jobs: dict[UUID, Job] = {}
        self.lock = RLock()

    def enqueue(self, job: Job) -> Job:
        with self.lock:
            for existing in self.jobs.values():
                if (
                    existing.tenant_id == job.tenant_id
                    and existing.document_id == job.document_id
                    and existing.stage == job.stage
                    and existing.status in {"queued", "leased"}
                ):
                    return existing
            self.jobs[job.id] = job
            return job

    def acquire(self, owner: str, lease_seconds: int) -> Job | None:
        with self.lock:
            now = self.clock.now()
            candidates: list[Job] = []
            for job in self.jobs.values():
                if (
                    job.status == "leased"
                    and job.lease_expires_at is not None
                    and job.lease_expires_at <= now
                ):
                    job = job.model_copy(
                        update={
                            "status": "queued",
                            "lease_owner": None,
                            "lease_expires_at": None,
                        }
                    )
                    self.jobs[job.id] = job
                if job.status == "queued" and job.available_at <= now:
                    candidates.append(job)
            if not candidates:
                return None
            current = min(candidates, key=lambda item: (item.available_at, item.created_at))
            leased = current.model_copy(
                update={
                    "status": "leased",
                    "attempts": current.attempts + 1,
                    "lease_owner": owner,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "updated_at": now,
                }
            )
            self.jobs[leased.id] = leased
            return leased

    def heartbeat(self, job_id: UUID, owner: str, lease_seconds: int) -> bool:
        with self.lock:
            job = self.jobs.get(job_id)
            now = self.clock.now()
            if (
                not job
                or job.status != "leased"
                or job.lease_owner != owner
                or job.lease_expires_at is None
                or job.lease_expires_at <= now
            ):
                return False
            self.jobs[job_id] = job.model_copy(
                update={
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "updated_at": now,
                }
            )
            return True

    def complete(self, job_id: UUID, owner: str) -> bool:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job.status != "leased" or job.lease_owner != owner:
                return False
            self.jobs[job_id] = job.model_copy(
                update={
                    "status": "completed",
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "updated_at": self.clock.now(),
                }
            )
            return True

    def fail(self, job_id: UUID, owner: str, error: str) -> Job | None:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job.status != "leased" or job.lease_owner != owner:
                return None
            now = self.clock.now()
            terminal = job.attempts >= job.max_attempts
            failed = job.model_copy(
                update={
                    "status": "failed" if terminal else "queued",
                    "available_at": now if terminal else now + timedelta(seconds=2**job.attempts),
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "last_error": error[:1000],
                    "updated_at": now,
                }
            )
            self.jobs[job_id] = failed
            return failed

    def list(self, tenant_id: str, limit: int = 100) -> list[Job]:
        with self.lock:
            jobs = [job for job in self.jobs.values() if job.tenant_id == tenant_id]
            return sorted(jobs, key=lambda job: job.created_at, reverse=True)[:limit]

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        return None
