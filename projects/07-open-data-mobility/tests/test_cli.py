"""CLI smoke tests: every command is wired (fixtures keep it offline)."""

from mobility.cli import app
from mobility.config import MobilityConfig
from mobility.validate import load_dq_reports, persist_dq_summary, validate_month
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_help_lists_all_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in (
        "download",
        "validate",
        "join",
        "features",
        "train-baselines",
        "train-nn",
        "evaluate",
        "dashboard",
        "dq-report",
        "all",
    ):
        assert command in result.output


def test_dq_report_roundtrip(cfg: MobilityConfig) -> None:
    """Persisted DQ JSON reloads and re-renders the digest (dq-report logic)."""
    validate_month("2024-01", cfg)
    reports = load_dq_reports(cfg)
    assert [r.dataset for r in reports] == ["tlc_yellow_2024-01"]
    persist_dq_summary(cfg, reports)
    md = (cfg.reports_dir / "dq_validated.md").read_text()
    assert "tlc_yellow_2024-01" in md
    assert (cfg.reports_dir / "dq_validated.html").exists()
