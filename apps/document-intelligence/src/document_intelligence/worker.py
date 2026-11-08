"""Separate leased worker with heartbeats and bounded retries."""

import asyncio
import logging
import signal
import threading
from types import FrameType
from uuid import uuid4

from document_intelligence.analysis.page_analyzer import build_page_analyzer
from document_intelligence.analysis.page_chat import build_page_chat
from document_intelligence.analysis.service import AnalysisService
from document_intelligence.clock import SystemClock
from document_intelligence.config import Settings
from document_intelligence.jobs.queue import Job, JobQueue
from document_intelligence.runtime import build_blobs, build_queue, build_repository

logger = logging.getLogger(__name__)

MAX_ERROR_CHARS = 500


class Worker:
    def __init__(
        self,
        service: AnalysisService,
        queue: JobQueue,
        settings: Settings,
        owner: str | None = None,
        stop: threading.Event | None = None,
    ) -> None:
        self.service = service
        self.queue = queue
        self.settings = settings
        self.owner = owner or f"worker-{uuid4().hex[:12]}"
        self.stop = stop or threading.Event()

    def run_once(self) -> bool:
        job = self.queue.acquire(self.owner, self.settings.lease_seconds)
        if job is None:
            return False
        logger.info("Job %s started (%s, document %s)", job.id, job.stage, job.document_id)
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop, args=(job, heartbeat_stop), daemon=True
        )
        heartbeat.start()
        try:
            asyncio.run(self.service.process(job))
            if not self.queue.complete(job.id, self.owner):
                raise RuntimeError("Lease lost before completion")
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            failed = self.queue.fail(job.id, self.owner, message[:MAX_ERROR_CHARS])
            if failed is None:
                logger.warning("Job %s: lease lost; failure was not recorded", job.id)
            elif failed.status == "failed":
                logger.warning("Job %s failed terminally: %s", job.id, message)
                record = self.service.repository.get_document(job.tenant_id, job.document_id)
                if record:
                    updated = record.model_copy(
                        update={"status": "failed", "updated_at": self.service.clock.now()}
                    )
                    self.service.repository.update_document(updated, record.version)
            else:
                logger.info(
                    "Job %s attempt %s/%s failed; retry queued: %s",
                    job.id,
                    failed.attempts,
                    failed.max_attempts,
                    message,
                )
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=1)
        return True

    def _heartbeat_loop(self, job: Job, stop: threading.Event) -> None:
        while not stop.wait(self.settings.heartbeat_seconds):
            if not self.queue.heartbeat(job.id, self.owner, self.settings.lease_seconds):
                logger.warning("Job %s: heartbeat rejected; lease lost", job.id)
                return

    def run_forever(self) -> None:
        while not self.stop.is_set():
            if not self.run_once():
                self.stop.wait(self.settings.worker_poll_seconds)


def main() -> None:
    settings = Settings()
    if settings.repository_backend == "memory":
        raise RuntimeError("The separate worker requires repository_backend=postgres")
    logging.basicConfig(level=logging.INFO)
    clock = SystemClock()
    repository = build_repository(settings, clock)
    queue = build_queue(settings, clock)
    service = AnalysisService(
        repository,
        queue,
        build_blobs(settings),
        build_page_analyzer(settings),
        build_page_chat(settings),
        clock,
        settings.max_job_attempts,
        settings.max_upload_bytes,
        settings.page_concurrency,
        settings.page_text_max_chars,
    )
    stop = threading.Event()

    def request_stop(signum: int, _frame: FrameType | None) -> None:
        logger.info("Received signal %s; stopping after the current job", signum)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    try:
        Worker(service, queue, settings, stop=stop).run_forever()
    finally:
        queue.close()
        repository.close()


if __name__ == "__main__":
    main()
