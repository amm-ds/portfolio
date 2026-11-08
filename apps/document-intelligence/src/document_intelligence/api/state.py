"""Application state assembled once by the app factory."""

from dataclasses import dataclass

from document_intelligence.analysis.page_chat import PageChat
from document_intelligence.analysis.service import AnalysisService
from document_intelligence.clock import Clock
from document_intelligence.config import Settings
from document_intelligence.documents.storage import BlobStore
from document_intelligence.jobs.queue import JobQueue
from document_intelligence.store.repository import Repository


@dataclass
class AppState:
    settings: Settings
    repository: Repository
    queue: JobQueue
    blobs: BlobStore
    service: AnalysisService
    page_chat: PageChat
    clock: Clock
