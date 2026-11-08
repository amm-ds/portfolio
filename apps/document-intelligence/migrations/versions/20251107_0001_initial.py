"""Initial generic document review schema, replaced for analysis by 0002.

This migration deliberately uses explicit historical tables instead of current
SQLAlchemy metadata so a fresh database can still replay the complete chain.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20251107_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "sha256", name="uq_documents_tenant_sha"),
    )
    op.create_index("ix_documents_tenant_status", "documents", ["tenant_id", "status"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_jobs_tenant_created", "jobs", ["tenant_id", "created_at"])
    op.create_table(
        "raw_extractions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("extractor", sa.String(128), nullable=False),
        sa.Column("extraction", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("raw_id", sa.Uuid(), sa.ForeignKey("raw_extractions.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("extraction", postgresql.JSONB(), nullable=False),
        sa.Column("issues", postgresql.JSONB(), nullable=False),
        sa.Column("author_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "revision", name="uq_revision_number"),
    )
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("revision_id", sa.Uuid(), sa.ForeignKey("revisions.id"), nullable=False),
        sa.Column("document_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", name="uq_review_decisions_document_id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sequence", sa.Integer(), sa.Identity(), nullable=False, unique=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_document_sequence", "audit_events", ["document_id", "sequence"])
    op.execute(
        "CREATE UNIQUE INDEX uq_jobs_active_document_stage ON jobs "
        "(tenant_id, document_id, stage) WHERE status IN ('queued', 'leased')"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'append-only table'; END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in ("raw_extractions", "revisions", "review_decisions", "audit_events"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
        )


def downgrade() -> None:
    for table in ("raw_extractions", "revisions", "review_decisions", "audit_events"):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_mutation()")
    op.drop_table("audit_events")
    op.drop_table("review_decisions")
    op.drop_table("revisions")
    op.drop_table("raw_extractions")
    op.drop_table("jobs")
    op.drop_table("documents")
