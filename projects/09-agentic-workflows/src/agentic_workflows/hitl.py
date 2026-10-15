"""Human-in-the-loop checkpointing: plan, pause, approve/reject, resume.

``request_approval`` runs a small graph whose single checkpoint node plans the
task and then *pauses*: it returns ``End`` carrying a typed
:class:`~agentic_workflows.schemas.Checkpoint`, which the caller serializes to
``data/checkpoint.json``. ``resume`` rebuilds the workflow graph re-entering
at :class:`~agentic_workflows.schemas.ExecuteNode` (approval) or back at
:class:`~agentic_workflows.schemas.PlanNode` with the reviewer's feedback
(rejection) — the state on disk is the single source of truth, so an
interrupted run resumes exactly where the human left it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from portfolio_core.llm import build_model
from portfolio_core.logging import get_logger
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_graph import BaseNode, End, Graph, GraphBuilder, GraphRunContext

from agentic_workflows.schemas import (
    ApprovalDecision,
    ApprovalRequest,
    Checkpoint,
    PlanOutput,
    WorkflowResult,
    WorkflowState,
)
from agentic_workflows.tools import Notebook
from agentic_workflows.workflow import (
    PLAN_SYSTEM,
    ExecuteNode,
    PlanNode,
    WorkflowDeps,
    build_workflow_graph,
    render_plan,
    run_agent_with_retries,
)

logger = get_logger(__name__)


class ApprovalCheckpointNode(BaseNode[WorkflowState, WorkflowDeps, Checkpoint]):
    """The checkpoint node: plans the task, then pauses with an approval request.

    Returning ``End`` here is the pause — the graph stops, and the serialized
    checkpoint on disk is what a human reviews and a later process resumes.
    """

    async def run(self, ctx: GraphRunContext[WorkflowState, WorkflowDeps]) -> End[Checkpoint]:
        state = ctx.state
        agent: Agent[None, PlanOutput] = Agent(
            ctx.deps.model,
            output_type=PlanOutput,
            system_prompt=PLAN_SYSTEM,
        )
        result = await run_agent_with_retries(agent, f"TASK: {state.task}")
        state.plan = result.output.steps
        state.plan_notes = result.output.notes
        state.input_tokens += int(result.usage.input_tokens or 0)
        state.output_tokens += int(result.usage.output_tokens or 0)
        state.steps_taken.append(f"plan ({len(state.plan)} steps)")
        checkpoint = Checkpoint(
            request=ApprovalRequest(
                task=state.task,
                plan=list(state.plan),
                context=(
                    "A research-ops workflow wants to execute the plan below. "
                    "Approve to continue with tool use, or reject with feedback to re-plan."
                ),
            ),
            state=state,
        )
        return End(checkpoint)


def build_approval_graph() -> Graph:
    """One-node graph whose output is the paused checkpoint."""
    builder = GraphBuilder(state_type=WorkflowState, deps_type=WorkflowDeps, output_type=Checkpoint)
    builder.add(builder.edge_from(builder.start_node).to(ApprovalCheckpointNode))
    builder.add(builder.node(ApprovalCheckpointNode))
    return builder.build()


async def request_approval_async(
    task: str,
    *,
    model: Model | None = None,
) -> Checkpoint:
    """Plan the task and return the typed checkpoint (callers persist it)."""
    resolved_model = model if model is not None else build_model()
    graph = build_approval_graph()
    return await graph.run(
        state=WorkflowState(task=task),
        deps=WorkflowDeps(model=resolved_model, notebook=Notebook()),
        inputs=ApprovalCheckpointNode(),
    )


def request_approval(task: str, *, model: Model | None = None) -> Checkpoint:
    """Synchronous wrapper around :func:`request_approval_async`."""
    return asyncio.run(request_approval_async(task, model=model))


def save_checkpoint(checkpoint: Checkpoint, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(checkpoint.model_dump_json(indent=2) + "\n", encoding="utf-8")
    logger.info("checkpoint written: %s", path)
    return path


def load_checkpoint(path: Path) -> Checkpoint:
    return Checkpoint.model_validate_json(path.read_text(encoding="utf-8"))


async def resume_async(
    checkpoint: Checkpoint,
    decision: ApprovalDecision,
    *,
    model: Model | None = None,
) -> WorkflowResult:
    """Resume from a checkpoint per the human's decision.

    Approve  → continue at ExecuteNode with the plan as approved.
    Reject   → back to PlanNode; the feedback becomes the re-plan brief.
    """
    resolved_model = model if model is not None else build_model()
    state = checkpoint.state
    if decision.approved:
        logger.info("checkpoint approved; continuing at ExecuteNode")
        graph = build_workflow_graph(ExecuteNode)
        return await graph.run(
            state=state,
            deps=WorkflowDeps(model=resolved_model, notebook=Notebook()),
            inputs=ExecuteNode(),
        )
    state.critique_feedback = decision.feedback or (
        "The reviewer rejected the plan without comments; reconsider the approach."
    )
    state.steps_taken.append("checkpoint: rejected → re-plan")
    logger.info("checkpoint rejected; re-planning with feedback")
    graph = build_workflow_graph(PlanNode)
    return await graph.run(
        state=state,
        deps=WorkflowDeps(model=resolved_model, notebook=Notebook()),
        inputs=PlanNode(),
    )


def resume(
    checkpoint: Checkpoint, decision: ApprovalDecision, *, model: Model | None = None
) -> WorkflowResult:
    """Synchronous wrapper around :func:`resume_async`."""
    return asyncio.run(resume_async(checkpoint, decision, model=model))


def describe_checkpoint(checkpoint: Checkpoint) -> str:
    """Human-readable summary of the pending checkpoint (CLI output)."""
    request = checkpoint.request
    lines = [f"Task: {request.task}", "", "Plan:", render_plan(checkpoint.state), ""]
    if request.context:
        lines.append(request.context)
    return "\n".join(lines)
