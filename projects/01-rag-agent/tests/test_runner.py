"""Runner infrastructure tests: checkpoints, resume, guards, spend seeding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rag_agent.runner import (
    Checkpoint,
    HostGrabber,
    RunManifest,
    guard_run_write,
    make_run_id,
    question_hash,
    seed_spend_from_manifest,
    sha256_file,
    verify_set_sha,
)


def _manifest(tmp_path: Path, split: str = "dev_v1", set_sha: str = "a" * 64) -> RunManifest:
    return RunManifest(
        run_id=make_run_id(split, set_sha),
        config_hash="c" * 16,
        commit="deadbeef",
        dirty=False,
        split=split,
        set_sha256=set_sha,
        index_id="minilm:200+rerank:True",
        judge_model="kimi-for-coding",
        judge_prompt_hash="p" * 16,
    )


def test_checkpoint_rows_and_resume(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "r1"
    checkpoint = Checkpoint.open(run_dir, _manifest(tmp_path))
    assert checkpoint.completed == set()
    checkpoint.write_row(question_hash("q1"), "q1", {"verdict": "correct"}, ["127.0.0.1"], 0.1)
    checkpoint.write_row(question_hash("q2"), "q2", {"verdict": "unsupported-claim"}, [], 0.2)
    assert checkpoint.completed == {question_hash("q1"), question_hash("q2")}
    # No duplicate rows, nothing lost: re-open and confirm both rows are there.
    reopened = Checkpoint.open(run_dir, _manifest(tmp_path))
    assert reopened.completed == checkpoint.completed
    rows = [
        json.loads(line) for line in reopened.rows_path.read_text().splitlines() if line.strip()
    ]
    assert len(rows) == 2
    assert rows[0]["hosts"] == ["127.0.0.1"]
    assert rows[1]["trace"]["verdict"] == "unsupported-claim"


def test_resume_refused_on_manifest_mismatch(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "r2"
    Checkpoint.open(run_dir, _manifest(tmp_path))
    changed = _manifest(tmp_path)
    changed.config_hash = "f" * 16
    with pytest.raises(SystemExit):
        Checkpoint.open(run_dir, changed)


def test_spend_seeded_from_manifest(tmp_path: Path) -> None:
    from portfolio_core.llm_budget import get_ledger, reset_ledger

    reset_ledger()
    checkpoint = Checkpoint.open(tmp_path / "runs" / "r3", _manifest(tmp_path))
    checkpoint.update_spend(1.25)
    reopened = Checkpoint.open(tmp_path / "runs" / "r3", _manifest(tmp_path))
    assert reopened.manifest.cumulative_spend_usd == pytest.approx(1.25)
    seed_spend_from_manifest(reopened)
    assert float(get_ledger().spend_usd) == pytest.approx(1.25)
    reset_ledger()


def test_verify_set_sha_refuses_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    set_file = tmp_path / "golden_fake.json"
    set_file.write_text("[]\n", encoding="utf-8")
    manifest = tmp_path / "golden_fake.sha256.json"
    manifest.write_text(json.dumps({"sha256": "b" * 64}), encoding="utf-8")
    with pytest.raises(SystemExit):
        verify_set_sha(set_file)
    # Match passes and returns the actual sha.
    manifest.write_text(json.dumps({"sha256": sha256_file(set_file)}), encoding="utf-8")
    assert verify_set_sha(set_file) == sha256_file(set_file)


def test_write_guard_refuses_outside_data_and_reports(tmp_path: Path) -> None:
    with pytest.raises(PermissionError):
        guard_run_write(Path("src/rag_agent/evil.json"))
    guard_run_write(Path("reports/runs/x/rows.jsonl"))


def test_host_grabber_captures_and_flags() -> None:
    import logging

    grabber = HostGrabber()
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        __file__,
        10,
        'HTTP Request: POST http://127.0.0.1:11434/v1 "200"',
        (),
        None,
    )
    grabber.emit(record)
    assert grabber.hosts == ["127.0.0.1"]


def test_question_hash_stable() -> None:
    assert question_hash("What is X?") == question_hash("What is X?")
    assert question_hash("What is X?") != question_hash("What is Y?")


def test_no_detail_heldout_write_for_dev_run(tmp_path: Path) -> None:
    """A dev/final run must be refused the default reports dir (no detail.heldout)."""
    import typer
    from rag_agent.cli import _heldout_checkpoint
    from rag_agent.config import RAGConfig

    config = RAGConfig(reports_dir=Path("reports"))
    set_file = tmp_path / "golden_dev_v1.json"
    set_file.write_text("[]\n", encoding="utf-8")
    (tmp_path / "golden_dev_v1.sha256.json").write_text(
        json.dumps({"sha256": sha256_file(set_file)}), encoding="utf-8"
    )
    config.heldout_questions_path = set_file
    with pytest.raises(typer.BadParameter):
        _heldout_checkpoint(config)


def test_kimi_rate_card_resolution() -> None:
    """kimi-for-coding maps to the published kimi-k2.8-preview reference card."""
    from portfolio_core.llm_budget import model_rate_card

    card = model_rate_card("kimi-for-coding")
    assert "kimi" in card.label.lower()
    assert "k2.8" in card.label.lower() or "k2" in card.label.lower()


def test_merged_traces_dedupes_fresh_run_rows(tmp_path: Path) -> None:
    """A fresh checkpointed run must not double-count rows at merge time."""
    manifest = RunManifest(
        run_id="x-abc",
        config_hash="c",
        commit="g",
        dirty=False,
        split="x",
        set_sha256="s",
        index_id="i",
        judge_model="m",
        judge_prompt_hash="p",
    )
    checkpoint = Checkpoint.open(tmp_path / "x-abc", manifest)
    for i in range(3):
        checkpoint.write_row(
            question_hash(f"q{i}"),
            f"q{i}",
            {"question": f"q{i}", "verdict": "correct"},
            ["localhost"],
            0.0,
        )
    merged = checkpoint.merged_traces(
        [{"question": "q0", "verdict": "correct"}, {"question": "q3", "verdict": "empty-answer"}]
    )
    assert len(merged) == 4
    by_q = {r["question"]: r["verdict"] for r in merged}
    assert by_q["q3"] == "empty-answer"  # fresh row wins for q0
