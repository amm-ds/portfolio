"""Replace whole-document review tables with per-document page analysis state."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261108_0003"
down_revision = "20251107_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("raw_analyses", "revisions", "review_decisions"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    op.drop_table("review_decisions")
    op.drop_table("revisions")
    op.drop_table("raw_analyses")

    op.create_table(
        "document_analyses",
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("analyzer", sa.String(128), nullable=False),
        sa.Column("job_id", sa.Uuid()),
        sa.Column("analysis", postgresql.JSONB()),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("processed_pages", sa.Integer(), nullable=False),
        sa.Column("failed_pages", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("page_count >= 0", name="ck_document_analyses_page_count"),
        sa.CheckConstraint("processed_pages >= 0", name="ck_document_analyses_processed"),
        sa.CheckConstraint("failed_pages >= 0", name="ck_document_analyses_failed"),
    )
    # Review-era statuses no longer exist; queued work restarts on the new path.
    op.execute(
        "UPDATE documents SET status = 'uploaded' "
        "WHERE status IN ('processing', 'pending_review', 'needs_review', 'approved', 'rejected')"
    )


def downgrade() -> None:
    raise RuntimeError("The page-analysis schema migration is one-way")
