"""Typed contracts for the agentic-workflows project (ADR-0002).

Everything that crosses a node, tool, checkpoint or eval boundary is a
validated pydantic model here — no dicts, no loose strings.
"""

from __future__ import annotations

from typing import Literal

from portfolio_core.schemas import PortfolioBaseModel
from pydantic import Field

# ---------------------------------------------------------------------------
# Graph state and node I/O
# ---------------------------------------------------------------------------


class PlanStep(PortfolioBaseModel):
    """One step of the execution plan emitted by the Plan node."""

    id: int = Field(ge=1)
    description: str = Field(min_length=1)
    tool: str | None = Field(default=None, description="Tool to call for this step, if any.")
    expected_output: str = Field(default="", description="What this step should produce.")


class WorkflowState(PortfolioBaseModel):
    """Mutable state threaded through the Plan → Execute → Critique graph.

    Kept a pydantic model (not a dataclass) so a human-in-the-loop checkpoint
    can serialize it to disk with ``model_dump_json`` and resume exactly.
    """

    task: str = Field(min_length=1)

    plan: list[PlanStep] = Field(default_factory=list)
    plan_notes: str = ""
    findings: list[str] = Field(default_factory=list)
    draft: str = ""
    self_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    steps_taken: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)

    execute_feedback: str = ""
    retries: int = Field(default=0, ge=0)
    critique_feedback: str = ""
    critique_loops: int = Field(default=0, ge=0)
    max_execute_retries: int = Field(default=1, ge=0)
    max_critique_loops: int = Field(default=1, ge=0)


class PlanOutput(PortfolioBaseModel):
    """Structured output of the Plan node's agent."""

    steps: list[PlanStep] = Field(min_length=1)
    notes: str = ""


class ExecutionOutput(PortfolioBaseModel):
    """Structured output of the Execute node's agent (the tool-using run)."""

    findings: list[str] = Field(default_factory=list, description="Facts gathered from tool calls.")
    draft: str = Field(min_length=1, description="Draft answer assembled from the findings.")
    self_confidence: float = Field(ge=0.0, le=1.0)


class CritiqueOutput(PortfolioBaseModel):
    """Structured verdict of the Critique node."""

    verdict: Literal["pass", "revise"]
    issues: list[str] = Field(default_factory=list)
    suggestion: str = ""


class WorkflowResult(PortfolioBaseModel):
    """Final structured output of the workflow graph."""

    answer: str
    steps_taken: list[str]
    tools_used: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    retries: int = Field(default=0, ge=0)
    critique_loops: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Human-in-the-loop checkpointing
# ---------------------------------------------------------------------------


class ApprovalRequest(PortfolioBaseModel):
    """What the checkpoint node asks a human to decide."""

    task: str
    plan: list[PlanStep]
    question: str = "Approve this plan?"
    context: str = ""


class ApprovalDecision(PortfolioBaseModel):
    """The human's answer; rejection carries free-text feedback."""

    approved: bool
    feedback: str = ""


class Checkpoint(PortfolioBaseModel):
    """Serialized pause point (``data/checkpoint.json``).

    Holds the typed approval request plus the full workflow state, so resume
    is deterministic and auditable — nothing lives only in process memory.
    """

    version: int = Field(default=1, ge=1)
    status: Literal["awaiting_approval"] = "awaiting_approval"
    request: ApprovalRequest
    state: WorkflowState


# ---------------------------------------------------------------------------
# Evaluation suite
# ---------------------------------------------------------------------------


class EvalTask(PortfolioBaseModel):
    """One graded task of the synthetic suite.

    ``expected_keywords`` are ground-truth substrings the final answer must
    contain (case-insensitive); ``expected_tools`` is the exact set of tools a
    correct solution needs. Both are derived deterministically from the canned
    research-ops corpus, so grading is exact rather than model-judged.
    """

    id: str = Field(min_length=1, pattern=r"^t\d{2}$")
    prompt: str = Field(min_length=1)
    category: Literal["lookup", "calculation", "conversion", "multi_step", "note_keeping"]
    expected_keywords: list[str] = Field(min_length=1)
    expected_tools: list[str] = Field(min_length=1)
    max_steps: int = Field(default=8, ge=1)
    latency_budget_s: float = Field(default=180.0, gt=0)


class TaskRunRecord(PortfolioBaseModel):
    """Recorded result of running one suite task through the workflow."""

    task_id: str = Field(min_length=1)
    status: Literal["ok", "workflow_error"]
    answer: str
    steps_taken: list[str]
    tools_used: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    retries: int = Field(default=0, ge=0)
    critique_loops: int = Field(default=0, ge=0)
    duration_s: float = Field(ge=0.0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    error: str | None = None
