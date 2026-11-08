"""Replace obsolete extraction-owned tables with immutable analysis records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20251107_0002"
down_revision = "20251107_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS raw_extractions_immutable ON raw_extractions")
    op.execute("DROP TRIGGER IF EXISTS revisions_immutable ON revisions")
    op.execute("DROP TRIGGER IF EXISTS review_decisions_immutable ON review_decisions")
    op.drop_constraint("review_decisions_revision_id_fkey", "review_decisions", type_="foreignkey")
    # Decisions reference incompatible old revisions and cannot be backfilled.
    op.execute("DELETE FROM review_decisions")
    op.drop_table("revisions")
    op.drop_table("raw_extractions")

    op.create_table(
        "raw_analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("analyzer", sa.String(128), nullable=False),
        sa.Column("analysis", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("raw_id", sa.Uuid(), sa.ForeignKey("raw_analyses.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("analysis", postgresql.JSONB(), nullable=False),
        sa.Column("issues", postgresql.JSONB(), nullable=False),
        sa.Column("author_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "revision", name="uq_revision_number"),
        sa.CheckConstraint("revision >= 1", name="ck_revision_number"),
    )
    op.create_foreign_key(
        "review_decisions_revision_id_fkey",
        "review_decisions",
        "revisions",
        ["revision_id"],
        ["id"],
    )
    op.create_check_constraint("ck_documents_version", "documents", "version >= 1")
    op.execute("UPDATE jobs SET stage = 'analyze' WHERE stage = 'extract'")
    op.execute("UPDATE jobs SET stage = 'reanalyze' WHERE stage = 'reprocess'")
    op.execute("UPDATE documents SET status = 'uploaded', page_count = NULL")
    for table in ("raw_analyses", "revisions", "review_decisions"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_mutation()"
        )


def downgrade() -> None:
    raise RuntimeError("The analysis schema migration is one-way")
