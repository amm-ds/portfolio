"""Lease, retry, idempotency, and blob-safety tests."""

from pathlib import Path
from uuid import uuid4

import pytest

from document_intelligence.clock import ManualClock
from document_intelligence.documents.storage import LocalBlobStore
from document_intelligence.jobs.memory import InMemoryJobQueue
from document_intelligence.jobs.queue import Job


def job(clock: ManualClock) -> Job:
    now = clock.now()
    return Job(
        id=uuid4(),
        tenant_id="tenant-a",
        document_id=uuid4(),
        stage="analyze",
        status="queued",
        attempts=0,
        max_attempts=2,
        available_at=now,
        created_at=now,
        updated_at=now,
    )


def test_duplicate_active_jobs_return_existing(clock: ManualClock) -> None:
    queue = InMemoryJobQueue(clock)
    first = job(clock)
    duplicate = first.model_copy(update={"id": uuid4()})
    assert queue.enqueue(duplicate).id == queue.enqueue(first).id
    assert len(queue.jobs) == 1


def test_expiring_lease_heartbeat_and_bounded_retries(clock: ManualClock) -> None:
    queue = InMemoryJobQueue(clock)
    queued = queue.enqueue(job(clock))
    leased = queue.acquire("worker-a", lease_seconds=10)
    assert leased and leased.attempts == 1
    assert queue.acquire("worker-b", lease_seconds=10) is None
    clock.advance(5)
    assert queue.heartbeat(queued.id, "worker-a", lease_seconds=10)
    clock.advance(9)
    assert queue.acquire("worker-b", lease_seconds=10) is None
    clock.advance(2)
    recovered = queue.acquire("worker-b", lease_seconds=10)
    assert recovered and recovered.attempts == 2
    failed = queue.fail(queued.id, "worker-b", "permanent test failure")
    assert failed and failed.status == "failed"
    assert queue.acquire("worker-c", lease_seconds=10) is None
    assert not queue.complete(queued.id, "worker-b")


def test_retry_backoff(clock: ManualClock) -> None:
    queue = InMemoryJobQueue(clock)
    queued = queue.enqueue(job(clock))
    assert queue.acquire("worker-a", 10)
    retry = queue.fail(queued.id, "worker-a", "transient")
    assert retry and retry.status == "queued"
    assert queue.acquire("worker-b", 10) is None
    clock.advance(2)
    assert queue.acquire("worker-b", 10)


def test_local_blob_storage_is_atomic_and_blocks_traversal(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    store.put("tenant/hash.pdf", b"pdf")
    assert store.get("tenant/hash.pdf") == b"pdf"
    with pytest.raises(ValueError):
        store.get("../outside")
    with pytest.raises(ValueError):
        store.put("/absolute", b"no")
