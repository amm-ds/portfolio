"""The Plan → Execute → Critique graph: a typed multi-step agent workflow.

Each node runs its own pydantic-ai agent with a narrow structured-output
contract (PlanOutput / ExecutionOutput / CritiqueOutput); the graph edges
carry the typed :class:`~agentic_workflows.schemas.WorkflowState`. Failures in
Execute (validation errors from the tool-using run) route back into Execute
with repair feedback, bounded by ``max_execute_retries``; the Critique node
may send a draft back to Execute once for revision before the graph ends with
a structured :class:`~agentic_workflows.schemas.WorkflowResult`.

Model resolution follows ADR-0004: ``build_model()`` (env provider or local
Ollama) unless a model is injected — tests inject a ``FunctionModel``.
Determinism comes from the typed contracts and the canned tool corpus, not
from sampling temperature, so the same task grades identically run to run.
When a hosted provider is configured (LLM_BASE_URL + LLM_API_KEY), every node
agent is built with the hosted preset from ``portfolio_core.llm``
(thinking disabled, temperature omitted — the Kimi coding endpoint rejects
explicit temperature values).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from portfolio_core.llm import (
    build_model,
    hosted_model_settings,
    is_hosted_provider,
)
from portfolio_core.logging import get_logger
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models import Model
from pydantic_graph import BaseNode, End, Graph, GraphBuilder, GraphRunContext

from agentic_workflows.config import get_settings
from agentic_workflows.schemas import (
    CritiqueOutput,
    ExecutionOutput,
    PlanOutput,
    StepTrace,
    ToolCallTrace,
    WorkflowResult,
    WorkflowState,
)
from agentic_workflows.tools import Notebook, traced_research_ops_toolset

logger = get_logger(__name__)

MeterFn = Callable[[Any], None]
"""Callback receiving each node's agent result (used by the suite to meter spend)."""

PLAN_SYSTEM = """You are the PLANNER of a research-ops workflow.
Break the user's task into a short ordered plan (1-5 steps). Each step names
the tool it needs from: calculator, unit_convert, search_handbook,
search_documents, note_store — or none (reasoning only). Never invent tools.
search_documents is for facts from the Wikipedia document corpus; search_handbook
is for Atlas Valley station facts. Reply with the structured plan.
"""

EXECUTE_SYSTEM = """You are the EXECUTOR of a research-ops workflow.
Follow the given plan. Use tools to gather facts — search_handbook for any
station fact, search_documents for facts from the Wikipedia document corpus,
calculator for arithmetic, unit_convert for unit changes, note_store when the
task asks to record something. Never answer station facts from memory; always
verify via search_handbook first. Then reply with the structured output:
findings (facts with their numbers), a draft answer that cites the numbers,
and your self_confidence.
"""

CRITIQUE_SYSTEM = """You are the CRITIQUE of a research-ops workflow.
Check the draft answer against the task and the listed findings. Reply 'pass'
when the draft answers the task with numbers grounded in the findings; reply
'revise' with concrete issues and a suggestion when it is wrong, incomplete,
or ungrounded. Be strict: any missing number or unsupported claim is a 'revise'.
"""


@dataclass
class WorkflowDeps:
    """Graph dependencies: the model, the run's notebook, and suite hooks.

    ``meter`` (optional) receives each node's agent result — the eval suite
    uses it to record cloud-equivalent spend against the budget caps.
    ``usage_limits`` (optional) is passed to every agent run so hosted request
    and token limits are enforced natively per call.
    ``tool_traces`` is the per-run tool-call buffer: the Execute node's traced
    toolset appends a :class:`~agentic_workflows.schemas.ToolCallTrace` per
    invocation, and the node mirrors the buffer into the workflow state.
    """

    model: Model
    notebook: Notebook
    meter: MeterFn | None = None
    usage_limits: Any | None = None
    tool_traces: list[ToolCallTrace] = field(default_factory=list)


def provider_model_settings() -> Any | None:
    """Hosted preset (thinking disabled, temperature omitted) when a hosted
    OpenAI-compatible provider is configured, else ``None`` (local default).

    Uses this project's settings (env file at the monorepo root) so the hosted
    branch is detected regardless of the caller's working directory.
    """
    if is_hosted_provider(get_settings()):
        return hosted_model_settings()
    return None


def render_plan(state: WorkflowState) -> str:
    """Human/LLM-readable rendering of the current plan."""
    lines = [f"{step.id}. {step.description}" for step in state.plan]
    if state.plan_notes:
        lines.append(f"Planner notes: {state.plan_notes}")
    return "\n".join(lines)


def _tool_names(messages: list[object]) -> list[str]:
    """Ordered tool-call names across all model messages of a run.

    The structured-output tool call (pydantic-ai's ``final_result``) is not a
    domain tool and is excluded.
    """
    names: list[str] = []
    for message in messages:
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if isinstance(part, ToolCallPart) and part.tool_name != "final_result":
                    names.append(part.tool_name)
    return names


async def run_agent_with_retries(
    agent: Agent[Any, Any],
    prompt: str,
    *,
    deps: Notebook | None = None,
    attempts: int = 3,
    usage_limits: Any | None = None,
) -> Any:
    """Run an agent with bounded retries around flaky providers.

    Reasoning models served through Ollama occasionally answer with empty
    content (thinking consumed the turn); the internal single retry then
    raises ``UnexpectedModelBehavior``. A few bounded attempts at the node
    level keep the workflow robust without hiding real failures.
    ``usage_limits`` is forwarded to every model call (hosted budget guard).
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            if deps is not None:
                return await agent.run(prompt, deps=deps, usage_limits=usage_limits)
            return await agent.run(prompt, usage_limits=usage_limits)
        except Exception as exc:  # broad: agent failures vary; bounded retries then re-raise
            last_error = exc
            logger.warning("agent run attempt %d/%d failed: %s", attempt, attempts, exc)
    assert last_error is not None  # noqa: S101 - loop ran and every attempt raised
    raise last_error


def _record_step(
    state: WorkflowState,
    node: Literal["plan", "execute", "critique"],
    result: Any,
    latency_s: float,
    meter: MeterFn | None,
) -> None:
    """Append the node's step trace and meter its usage when a meter is wired."""
    trace = StepTrace(
        node=node,
        input_tokens=int(result.usage.input_tokens or 0),
        output_tokens=int(result.usage.output_tokens or 0),
        latency_s=round(latency_s, 3),
    )
    state.step_traces.append(trace)
    if meter is not None:
        meter(result)


class PlanNode(BaseNode[WorkflowState, WorkflowDeps, WorkflowResult]):
    """Turns the task into a typed step plan (optionally re-plans on feedback)."""

    async def run(self, ctx: GraphRunContext[WorkflowState, WorkflowDeps]) -> ExecuteNode:
        state = ctx.state
        agent: Agent[None, PlanOutput] = Agent(
            ctx.deps.model,
            output_type=PlanOutput,
            system_prompt=PLAN_SYSTEM,
            model_settings=provider_model_settings(),
        )
        prompt = f"TASK: {state.task}"
        if state.critique_feedback:
            prompt += (
                "\n\nThe previous plan was rejected. Feedback from the human reviewer:\n"
                f"{state.critique_feedback}\nProduce a revised plan."
            )
        start = time.perf_counter()
        result = await run_agent_with_retries(agent, prompt, usage_limits=ctx.deps.usage_limits)
        state.plan = result.output.steps
        state.plan_notes = result.output.notes
        state.input_tokens += int(result.usage.input_tokens or 0)
        state.output_tokens += int(result.usage.output_tokens or 0)
        _record_step(state, "plan", result, time.perf_counter() - start, ctx.deps.meter)
        state.steps_taken.append(f"plan ({len(state.plan)} steps)")
        logger.info("planned task into %d steps", len(state.plan))
        return ExecuteNode()


class ExecuteNode(BaseNode[WorkflowState, WorkflowDeps, WorkflowResult]):
    """Runs the tool-using agent against the plan; repairs on validation failure."""

    async def run(
        self, ctx: GraphRunContext[WorkflowState, WorkflowDeps]
    ) -> CritiqueNode | ExecuteNode | End[WorkflowResult]:
        state = ctx.state
        state.steps_taken.append(f"execute (attempt {state.retries + 1})")
        agent: Agent[Notebook, ExecutionOutput] = Agent(
            ctx.deps.model,
            output_type=ExecutionOutput,
            deps_type=Notebook,
            toolsets=[traced_research_ops_toolset(ctx.deps.tool_traces)],
            system_prompt=EXECUTE_SYSTEM,
            model_settings=provider_model_settings(),
        )
        prompt = f"TASK: {state.task}\n\nPLAN:\n{render_plan(state)}"
        if state.execute_feedback:
            prompt += f"\n\nRepair note from a failed attempt:\n{state.execute_feedback}"
        start = time.perf_counter()
        try:
            result = await run_agent_with_retries(
                agent,
                prompt,
                deps=ctx.deps.notebook,
                usage_limits=ctx.deps.usage_limits,
            )
        except Exception as exc:  # broad: execute failure recoverable via repair loop
            # Tool calls made before the failure still belong to the record.
            state.tool_traces[:] = ctx.deps.tool_traces
            state.retries += 1
            logger.warning("execute attempt %d failed: %s", state.retries, exc)
            if state.retries <= state.max_execute_retries:
                state.execute_feedback = (
                    f"Attempt failed with: {exc}. Re-check tool usage and retry."
                )
                return ExecuteNode()
            return End(
                _failure_result(state, f"execute failed after {state.retries} attempts: {exc}")
            )
        output = result.output
        state.findings.extend(output.findings)
        state.draft = output.draft
        state.self_confidence = output.self_confidence
        state.tools_used.extend(_tool_names(result.all_messages()))
        state.tool_traces[:] = ctx.deps.tool_traces
        state.input_tokens += int(result.usage.input_tokens or 0)
        state.output_tokens += int(result.usage.output_tokens or 0)
        # Meter outside the repair try: budget cuts must abort the task, not
        # be swallowed by the execute repair path.
        _record_step(state, "execute", result, time.perf_counter() - start, ctx.deps.meter)
        state.steps_taken.append(f"draft (self-confidence {output.self_confidence:.2f})")
        return CritiqueNode()


class CritiqueNode(BaseNode[WorkflowState, WorkflowDeps, WorkflowResult]):
    """Self-checks the draft; loops back to Execute once, then ends."""

    async def run(
        self, ctx: GraphRunContext[WorkflowState, WorkflowDeps]
    ) -> ExecuteNode | End[WorkflowResult]:
        state = ctx.state
        state.steps_taken.append("critique")
        agent: Agent[None, CritiqueOutput] = Agent(
            ctx.deps.model,
            output_type=CritiqueOutput,
            system_prompt=CRITIQUE_SYSTEM,
            model_settings=provider_model_settings(),
        )
        start = time.perf_counter()
        result = await run_agent_with_retries(
            agent,
            f"TASK: {state.task}\n\nFINDINGS:\n- "
            + "\n- ".join(state.findings)
            + f"\n\nDRAFT:\n{state.draft}",
            usage_limits=ctx.deps.usage_limits,
        )
        verdict = result.output
        state.input_tokens += int(result.usage.input_tokens or 0)
        state.output_tokens += int(result.usage.output_tokens or 0)
        state.critique_verdict = verdict.verdict
        _record_step(state, "critique", result, time.perf_counter() - start, ctx.deps.meter)
        if verdict.verdict == "revise" and state.critique_loops < state.max_critique_loops:
            state.critique_loops += 1
            state.execute_feedback = (
                "; ".join(verdict.issues)
                + (f" Suggestion: {verdict.suggestion}" if verdict.suggestion else "")
            ).strip()
            state.steps_taken.append("critique: revise → re-execute")
            logger.info("critique requested revision (%d issues)", len(verdict.issues))
            return ExecuteNode()
        state.steps_taken.append(f"critique: {verdict.verdict}")
        return End(_final_result(state, verdict.issues))


def _confidence(state: WorkflowState, critique_issues: list[str]) -> float:
    """Final confidence: self-reported, damped by critique revisions/issues."""
    confidence = state.self_confidence
    confidence -= 0.10 * state.critique_loops
    confidence -= 0.05 * len(critique_issues)
    return round(max(0.0, min(1.0, confidence)), 3)


def _plan_steps(state: WorkflowState) -> list[str]:
    """The approved plan as rendered step lines (id, description, tool)."""
    lines = []
    for step in state.plan:
        line = f"{step.id}. {step.description}"
        if step.tool:
            line += f" → {step.tool}"
        lines.append(line)
    return lines


def _final_result(state: WorkflowState, critique_issues: list[str]) -> WorkflowResult:
    return WorkflowResult(
        answer=state.draft,
        steps_taken=list(state.steps_taken),
        tools_used=list(state.tools_used),
        step_traces=list(state.step_traces),
        tool_calls=list(state.tool_traces),
        plan_steps=_plan_steps(state),
        critique_verdict=state.critique_verdict or None,
        confidence=_confidence(state, critique_issues),
        retries=state.retries,
        critique_loops=state.critique_loops,
        input_tokens=state.input_tokens,
        output_tokens=state.output_tokens,
    )


def _failure_result(state: WorkflowState, reason: str) -> WorkflowResult:
    state.steps_taken.append("workflow failed")
    return WorkflowResult(
        answer=f"Workflow could not complete: {reason}",
        steps_taken=list(state.steps_taken),
        tools_used=list(state.tools_used),
        step_traces=list(state.step_traces),
        tool_calls=list(state.tool_traces),
        plan_steps=_plan_steps(state),
        critique_verdict=state.critique_verdict or None,
        confidence=0.0,
        retries=state.retries,
        critique_loops=state.critique_loops,
        input_tokens=state.input_tokens,
        output_tokens=state.output_tokens,
    )


def build_workflow_graph(
    start: type[BaseNode[WorkflowState, WorkflowDeps, WorkflowResult]],
) -> Graph:
    """Build the workflow graph with an explicit start node.

    ``start`` is normally :class:`PlanNode`; the human-in-the-loop resume
    re-enters at :class:`ExecuteNode` (approved plan on disk) or :class:`PlanNode`
    (rejected plan with feedback). PlanNode is only wired in when it is the
    entry, otherwise structure validation would flag it as unreachable.
    """
    builder = GraphBuilder(
        state_type=WorkflowState, deps_type=WorkflowDeps, output_type=WorkflowResult
    )
    builder.add(builder.edge_from(builder.start_node).to(start))
    if start is PlanNode:
        builder.add(builder.node(PlanNode))
    builder.add(builder.node(ExecuteNode))
    builder.add(builder.node(CritiqueNode))
    return builder.build()


async def run_workflow_async(
    task: str,
    *,
    model: Model | None = None,
    notebook: Notebook | None = None,
    max_execute_retries: int = 1,
    max_critique_loops: int = 1,
    start: type[BaseNode[WorkflowState, WorkflowDeps, WorkflowResult]] | None = None,
    state: WorkflowState | None = None,
    meter: MeterFn | None = None,
    usage_limits: Any | None = None,
) -> WorkflowResult:
    """Run the workflow graph; inject ``model``/``state`` for tests and resumes.

    ``meter`` (optional) receives each node's agent result — the eval suite
    wires it to the spend ledger. ``usage_limits`` (optional) is forwarded to
    every model call for hosted request/token budgets.
    """
    resolved_model = model if model is not None else build_model(get_settings())
    entry = start or PlanNode
    workflow_state = state or WorkflowState(
        task=task,
        max_execute_retries=max_execute_retries,
        max_critique_loops=max_critique_loops,
    )
    graph = build_workflow_graph(entry)
    return await graph.run(
        state=workflow_state,
        deps=WorkflowDeps(
            model=resolved_model,
            notebook=notebook or Notebook(),
            meter=meter,
            usage_limits=usage_limits,
        ),
        inputs=entry(),
    )


def run_workflow(
    task: str,
    *,
    model: Model | None = None,
    notebook: Notebook | None = None,
    max_execute_retries: int = 1,
    max_critique_loops: int = 1,
    start: type[BaseNode[WorkflowState, WorkflowDeps, WorkflowResult]] | None = None,
    state: WorkflowState | None = None,
    meter: MeterFn | None = None,
    usage_limits: Any | None = None,
) -> WorkflowResult:
    """Synchronous wrapper for CLI/REPL use (not callable inside a running loop)."""
    return asyncio.run(
        run_workflow_async(
            task,
            model=model,
            notebook=notebook,
            max_execute_retries=max_execute_retries,
            max_critique_loops=max_critique_loops,
            start=start,
            state=state,
            meter=meter,
            usage_limits=usage_limits,
        )
    )
