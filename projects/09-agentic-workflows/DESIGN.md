# DESIGN — Agentic AI Workflows

## Requirements

- Multi-step agent workflows with explicit, typed control flow: planning, tool
  orchestration, retries, and a self-critique that can loop back.
- Human-in-the-loop checkpointing: pause with a typed approval request,
  persist state to disk, resume deterministically (approve / reject-with-feedback).
- An evaluation harness with step-level success criteria and per-run cost
  budgets — deterministic graders, no LLM in the judge.
- Everything offline-capable in tests; the real run uses the platform model
  factory (ADR-0004: env provider or local Ollama, default `qwen3:32b`).

## Options considered

### 1. Pure agent loop (one agent, system-prompted to plan/act/reflect)

- *Pros*: least machinery; a single `Agent` with tools and an output type.
- *Cons*: control flow lives inside the model's head. Retries, loop bounds and
  "critique once, then finish" are prompt conventions, not guarantees; a flaky
  or stubborn model can loop or skip steps silently. Human pauses require
  framework-native interrupts anyway. Nothing is auditable at the step level.

### 2. Explicit graph (pydantic-graph) with one agent per node  ← chosen

- *Pros*: every transition is code. Typed `WorkflowState` is threaded through
  nodes; each node has a narrow structured-output contract (`PlanOutput`,
  `ExecutionOutput`, `CritiqueOutput`); the final `WorkflowResult` is a pydantic
  model. Repair and critique loops are bounded by config values, so worst-case
  behavior is statically known. State is a pydantic model → serializes to disk
  verbatim for the HITL checkpoint. The graph mirrors how these systems are
  operated in production (plan/execute/review stages with gates).
- *Cons*: more boilerplate; new node types require code, not prompt edits.

### Toolset composition

`FunctionToolset` groups the four research-ops tools; a second, independently
authored math toolset is attached via `PrefixedToolset("math_")` inside a
`CombinedToolset`, so composed agents see `math_percent_change` next to
`calculator` with zero collision risk — and unit tests prove all six tools stay
callable. The workflow's Execute node deliberately uses only the research-ops
toolset: the eval suite grades exact tool selection, and extra available tools
would blur that signal.

### Eval design

- **Suite**: 14 synthetic tasks over a 12-document in-code corpus ("Atlas
  Valley" field station). All numbers in the ground truths come from the corpus
  and the tools, so grading is exact — answer keywords and expected tool sets
  are derived, not judged (`tests/test_evals.py::TestSuiteHonesty` pins them).
- **Graders**: `pydantic-evals` `Evaluator` subclasses — `AnswerSuccess`
  (all expected keywords present), `ToolSelection` (exact tool-set equality),
  `StepBudget`, `LatencyBudget`. No model in the judge → the `evaluate` DVC
  stage is fully offline.
- **Cost/latency**: token usage is accumulated per node from `result.usage`;
  per-task latency is wall time. Cost is reported at a reference rate card
  (local Ollama is $0; the rate card answers "what would this cost hosted").
- **Stages**: `run` (live LLM) and `evaluate` (offline grading) are separate
  DVC stages so grading is reproducible without a provider.

### HITL design

The checkpoint node runs the planner and returns `End[Checkpoint]` — the pause
is explicit in the graph, not an exception. The checkpoint carries the typed
`ApprovalRequest` plus the full `WorkflowState`; resume rebuilds the workflow
graph re-entering at `ExecuteNode` (approved) or `PlanNode` with the feedback
as re-plan brief (rejected). Because state is the single source of truth on
disk, an interrupted approval resumes exactly.

### Model reliability

`qwen3:32b` is a reasoning model: Ollama (0.40) cannot disable thinking via the
OpenAI-compatible endpoint (`think` is ignored), and occasional turns come back
with empty content after reasoning. Each node therefore wraps its agent run in
a bounded 3-attempt retry (`run_agent_with_retries`); the Execute node's
existing repair path sits on top of that. Worst case per task is statically
bounded: 3 attempts × (1 + max_execute_retries) executes + bounded critique loop.

## Decision

Graph-per-node (option 2) with deterministic evals and disk-serialized HITL
checkpoints; toolsets composed via `FunctionToolset` + `PrefixedToolset`.

## Changelog

- 2026-10-14 — Initial build: tools/toolsets, Plan→Execute→Critique graph,
  HITL checkpointing, 14-task suite with pydantic-evals graders, CLI + DVC
  stages, real run on qwen3:32b.
