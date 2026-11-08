"""Current metadata and one-way replacement migration contracts."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from document_intelligence.store.db_models import Base, DocumentAnalysisRow


def test_current_metadata_exposes_page_analysis_tables() -> None:
    assert "document_analyses" in Base.metadata.tables
    assert "documents" in Base.metadata.tables
    assert "jobs" in Base.metadata.tables
    assert "audit_events" in Base.metadata.tables
    assert "raw_analyses" not in Base.metadata.tables
    assert "revisions" not in Base.metadata.tables
    assert "review_decisions" not in Base.metadata.tables
    assert [column.name for column in DocumentAnalysisRow.__table__.primary_key] == ["document_id"]


def test_migration_chain_replaces_review_schema_with_page_analysis() -> None:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    scripts = ScriptDirectory.from_config(config)
    heads = scripts.get_heads()
    assert heads == ["20261108_0003"]
    revisions = list(scripts.walk_revisions())
    assert [script.revision for script in revisions] == [
        "20261108_0003",
        "20251107_0002",
        "20251107_0001",
    ]
    initial = (root / "migrations/versions/20251107_0001_initial.py").read_text()
    assert "Base.metadata" not in initial
    replacement = (root / "migrations/versions/20261108_0003_page_analysis.py").read_text()
    assert "document_analyses" in replacement
    assert "DROP TRIGGER" in replacement


def test_page_analysis_migration_downgrade_is_one_way() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = root / "migrations/versions/20261108_0003_page_analysis.py"
    assert "one-way" in migration.read_text()
    assert "def downgrade()" in migration.read_text()
