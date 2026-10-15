"""Unit tests for the human-in-the-loop checkpoint flow (offline)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agentic_workflows.hitl import (
    describe_checkpoint,
    load_checkpoint,
    request_approval,
    resume,
    save_checkpoint,
)
from agentic_workflows.schemas import ApprovalDecision

if TYPE_CHECKING:
    from conftest import ScriptedModelFactory


def test_request_approval_pauses_with_typed_checkpoint(
    tmp_path: Path, make_scripted_model: ScriptedModelFactory
) -> None:
    checkpoint = request_approval("Convert 48 km to miles", model=make_scripted_model())
    assert checkpoint.status == "awaiting_approval"
    assert len(checkpoint.request.plan) == 2
    assert checkpoint.state.task == "Convert 48 km to miles"

    path = save_checkpoint(checkpoint, tmp_path / "checkpoint.json")
    restored = load_checkpoint(path)
    assert restored == checkpoint
    summary = describe_checkpoint(restored)
    assert "Convert 48 km to miles" in summary
    assert "Plan:" in summary


def test_approve_continues_at_execute(make_scripted_model: ScriptedModelFactory) -> None:
    checkpoint = request_approval("weekly diesel?", model=make_scripted_model())
    result = resume(checkpoint, ApprovalDecision(approved=True), model=make_scripted_model())
    assert "75.6" in result.answer
    # the plan from the checkpoint is reused, not re-planned
    assert result.steps_taken[0] == "plan (2 steps)"
    assert "execute (attempt 1)" in result.steps_taken


def test_reject_replans_with_feedback(make_scripted_model: ScriptedModelFactory) -> None:
    prompts: list[str] = []
    checkpoint = request_approval(
        "weekly diesel?", model=make_scripted_model(on_prompt=prompts.append)
    )
    result = resume(
        checkpoint,
        ApprovalDecision(approved=False, feedback="Avoid the highway route"),
        model=make_scripted_model(on_prompt=prompts.append),
    )
    assert "75.6" in result.answer
    assert "checkpoint: rejected → re-plan" in result.steps_taken
    # re-plan saw the human feedback
    assert any("Avoid the highway route" in p for p in prompts)
    assert result.steps_taken.count("plan (2 steps)") == 2


def test_checkpoint_round_trip_preserves_full_state(
    tmp_path: Path, make_scripted_model: ScriptedModelFactory
) -> None:
    checkpoint = request_approval("task one", model=make_scripted_model())
    path = save_checkpoint(checkpoint, tmp_path / "nested" / "checkpoint.json")
    restored = load_checkpoint(path)
    assert restored.state.plan == checkpoint.state.plan
    assert restored.request.question == "Approve this plan?"
