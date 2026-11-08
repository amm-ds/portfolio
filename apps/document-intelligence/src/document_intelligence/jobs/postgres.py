"""Postgres leased queue using row locks and skip-locked acquisition."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import create_engine, desc, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from document_intelligence.clock import Clock
from document_intelligence.jobs.queue import Job
from document_intelligence.store.db_models import JobRow


def _job(row: JobRow) -> Job:
    return Job.model_validate(
        {column.name: getattr(row, column.name) for column in JobRow.__table__.columns}
    )


class PostgresJobQueue:
    def __init__(self, database_url: str, clock: Clock) -> None:
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.clock = clock

    def enqueue(self, job: Job) -> Job:
        try:
            with Session(self.engine) as session:
                session.add(JobRow(**job.model_dump()))
                session.commit()
            return job
        except IntegrityError:
            with Session(self.engine) as session:
                row = session.scalar(
                    select(JobRow).where(
                        JobRow.tenant_id == job.tenant_id,
                        JobRow.document_id == job.document_id,
                        JobRow.stage == job.stage,
                        JobRow.status.in_(["queued", "leased"]),
                    )
                )
                if row is None:
                    raise
                return _job(row)

    def acquire(self, owner: str, lease_seconds: int) -> Job | None:
        now = self.clock.now()
        with Session(self.engine) as session:
            row = session.scalar(
                select(JobRow)
                .where(
                    or_(
                        (JobRow.status == "queued") & (JobRow.available_at <= now),
                        (JobRow.status == "leased") & (JobRow.lease_expires_at <= now),
                    )
                )
                .order_by(JobRow.available_at, JobRow.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                return None
            row.status = "leased"
            row.attempts += 1
            row.lease_owner = owner
            row.lease_expires_at = now + timedelta(seconds=lease_seconds)
            row.updated_at = now
            session.commit()
            return _job(row)

    def heartbeat(self, job_id: UUID, owner: str, lease_seconds: int) -> bool:
        now = self.clock.now()
        with Session(self.engine) as session:
            result = session.execute(
                update(JobRow)
                .where(
                    JobRow.id == job_id,
                    JobRow.status == "leased",
                    JobRow.lease_owner == owner,
                    JobRow.lease_expires_at > now,
                )
                .values(lease_expires_at=now + timedelta(seconds=lease_seconds), updated_at=now)
            )
            session.commit()
            return getattr(result, "rowcount", 0) == 1

    def complete(self, job_id: UUID, owner: str) -> bool:
        with Session(self.engine) as session:
            result = session.execute(
                update(JobRow)
                .where(JobRow.id == job_id, JobRow.status == "leased", JobRow.lease_owner == owner)
                .values(
                    status="completed",
                    lease_owner=None,
                    lease_expires_at=None,
                    updated_at=self.clock.now(),
                )
            )
            session.commit()
            return getattr(result, "rowcount", 0) == 1

    def fail(self, job_id: UUID, owner: str, error: str) -> Job | None:
        now = self.clock.now()
        with Session(self.engine) as session:
            row = session.scalar(
                select(JobRow)
                .where(JobRow.id == job_id, JobRow.status == "leased", JobRow.lease_owner == owner)
                .with_for_update()
            )
            if row is None:
                return None
            terminal = row.attempts >= row.max_attempts
            row.status = "failed" if terminal else "queued"
            row.available_at = now if terminal else now + timedelta(seconds=2**row.attempts)
            row.lease_owner = None
            row.lease_expires_at = None
            row.last_error = error[:1000]
            row.updated_at = now
            session.commit()
            return _job(row)

    def list(self, tenant_id: str, limit: int = 100) -> list[Job]:
        with Session(self.engine) as session:
            rows = session.scalars(
                select(JobRow)
                .where(JobRow.tenant_id == tenant_id)
                .order_by(desc(JobRow.created_at))
                .limit(limit)
            ).all()
            return [_job(row) for row in rows]

    def ping(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def close(self) -> None:
        self.engine.dispose()
