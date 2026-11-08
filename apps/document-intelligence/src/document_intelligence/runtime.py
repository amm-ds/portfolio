"""Runtime adapter factories shared by API and worker."""

from document_intelligence.clock import Clock
from document_intelligence.config import Settings
from document_intelligence.documents.storage import BlobStore, LocalBlobStore, S3BlobStore
from document_intelligence.jobs.memory import InMemoryJobQueue
from document_intelligence.jobs.postgres import PostgresJobQueue
from document_intelligence.jobs.queue import JobQueue
from document_intelligence.store.memory import InMemoryRepository
from document_intelligence.store.postgres import PostgresRepository
from document_intelligence.store.repository import Repository


def build_repository(settings: Settings, clock: Clock) -> Repository:
    if settings.repository_backend == "memory":
        return InMemoryRepository(clock)
    return PostgresRepository(settings.database_url, clock)


def build_queue(settings: Settings, clock: Clock) -> JobQueue:
    if settings.repository_backend == "memory":
        return InMemoryJobQueue(clock)
    return PostgresJobQueue(settings.database_url, clock)


def build_blobs(settings: Settings) -> BlobStore:
    if settings.blob_backend == "local":
        return LocalBlobStore(settings.blob_dir)
    return S3BlobStore(
        settings.s3_bucket,
        settings.s3_prefix,
        settings.s3_endpoint_url,
        settings.s3_region,
    )
