"""Platform-contract tests: the portfolio_core/eval APIs this project relies on.

These are integration checks of the STABLE platform surface (fetch with pinned
checksums, mock-model factory, run comparison, HTML report writing) — offline,
using file:// URLs and temporary directories.
"""

from pathlib import Path

import pytest
from portfolio_core.io import fetch, sha256_of
from portfolio_core.llm import MockProviderUnsetError, build_model
from portfolio_eval.metrics import MetricResult, RunResult, compare_runs
from portfolio_eval.report import EvalReport
from typer.testing import CliRunner


def test_sha256_and_fetch_with_checksum(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("deterministic payload", encoding="utf-8")
    digest = sha256_of(src)
    dest = tmp_path / "dest.txt"
    fetch(src.as_uri(), dest, expected_sha256=digest)
    assert dest.read_text(encoding="utf-8") == "deterministic payload"
    # Second fetch hits the checksum cache (idempotent).
    fetch(src.as_uri(), dest, expected_sha256=digest)
    assert dest.exists()


def test_fetch_checksum_mismatch_is_loud(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("payload", encoding="utf-8")
    dest = tmp_path / "dest.txt"
    with pytest.raises(ValueError, match="checksum mismatch"):
        fetch(src.as_uri(), dest, expected_sha256="0" * 64)
    assert not dest.exists()


def test_build_model_mock_mode_and_error_without_response() -> None:
    model = build_model(mock_response="hello")
    assert model is not None
    with pytest.raises(MockProviderUnsetError):
        build_model(mock_response=None)


def test_compare_runs_ranks_best_first() -> None:
    runs = [
        RunResult(name="b", metrics=[MetricResult(name="acc", value=0.8)]),
        RunResult(name="a", metrics=[MetricResult(name="acc", value=0.9)]),
    ]
    result = compare_runs(runs, "acc")
    assert result["ranking"] == ["a", "b"]
    assert result["a"] == 0.9


def test_eval_report_writes_standalone_html(tmp_path: Path) -> None:
    report = EvalReport(title="t")
    report.add_markdown_table("M", "| a | b |\n|---|---|\n| 1 | 2 |")
    report.add_html("Raw", "<p>hi</p>")
    out = report.write(tmp_path / "report.html")
    text = out.read_text(encoding="utf-8")
    assert "<table>" in text and "<p>hi</p>" in text


def test_cli_help_lists_commands() -> None:
    from rag_agent.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("prepare-corpus", "build-index", "evaluate", "chat"):
        assert command in result.output
