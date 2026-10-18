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

- **Suite**: 15 tasks — 14 over a 12-document in-code corpus ("Atlas Valley"
  field station) plus one cross-project lookup over 01's real Wikipedia corpus.
  All numbers in the ground truths come from the corpora and the tools, so
  grading is exact — answer keywords and expected tool sets are derived, not
  judged (`tests/test_evals.py::TestSuiteHonesty` and
  `tests/test_documents.py` pin them).
- **Graders**: `pydantic-evals` `Evaluator` subclasses — `AnswerSuccess`
  (all expected keywords present), `ToolSelection` (exact tool-set equality),
  `StepBudget`, `LatencyBudget`. No model in the judge → the `evaluate` DVC
  stage is fully offline.
- **Cost/latency**: token usage is accumulated per node from `result.usage`
  and traced per node (`StepTrace`); per-task latency is wall time. Cost is
  reported at a cloud-equivalent reference rate card (local inference is $0;
  the rate card answers "what would this cost hosted").
- **Stages**: `run` (live LLM) and `evaluate` (offline grading) are separate
  DVC stages so grading is reproducible without a provider.
- **Held-out set**: `HELDOUT_SUITE` is 10 unseen tasks over the same corpora
  (7 answer tasks + 3 designed-to-fail probes). Probes ask for what the tools
  cannot do; they are graded by `RefusalSuccess` (status `ok` + a refusal
  marker in the answer — a fabricated number or a crash fails). `run-all
  --heldout` / `evaluate --heldout` run and grade them; the summary lands in
  `metrics.json detail.heldout`. Small by design (n=10): it checks for
  prompt overfitting and confabulation, it does not re-measure the headline
  rates.

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

### Hosted provider (Kimi Code membership endpoint)

Any OpenAI-compatible endpoint works through the same branch (ADR-0004 env
provider). For the hosted Kimi coding endpoint (`https://api.kimi.com/coding/v1`,
model `kimi-for-coding`) the platform preset applies automatically when a
hosted provider is configured:

- **Thinking disabled** (`hosted_model_settings()`): `extra_body={"thinking":
  {"type": "disabled"}}` — the big token saving; without it the model always
  reasons and reasoning tokens bill as output.
- **Temperature omitted**: the endpoint rejects explicit values (both 0 and 1
  with thinking disabled); the preset sets none. This project never passes a
  temperature — determinism comes from the typed contracts and canned tools.
- Every model construction routes through `provider_model_settings()`, and the
  suite's env file resolves at the monorepo root, so the hosted branch works
  from any working directory. An equivalent local preset is LM Studio
  (`LLM_BASE_URL=http://localhost:1234/v1`, `LLM_API_KEY=lm-studio`): any
  OpenAI-compatible local server rides the same branch, priced at $0 by the
  ledger's local rate card. Ollama needs no env at all.

### Cost metering and budget caps

Costs are **labelled cloud-equivalent estimates** ($1.00/Mtok input,
$4.00/Mtok output — the public kimi-k2.8-preview reference card): the hosted
key is membership-quota, not pay-per-token, so nothing is a billed amount
(`portfolio_core.llm_budget`).

- `run-all` resets the process ledger at suite start and caps it at
  `LLM_SUITE_COST_LIMIT_USD` ($2.00): crossing it records the current task as
  `budget_exceeded` and aborts the remaining tasks cleanly.
- A per-task cap (`task_cost_limit_usd` in `params.yaml`, $0.25) is enforced by
  the meter callback wired into every node: the node result is recorded, then
  `TaskBudgetError` aborts the task; the suite continues with the next task.
- `budget_limits()` (hosted request/token `UsageLimits`) is forwarded to every
  live model call. The USD caps live in the ledger, not `UsageLimits.cost_limit`
  (genai-prices has no card for `kimi-for-coding` — see llm_budget's design
  note).
- Every node also appends a `StepTrace` (`node`, `input_tokens`,
  `output_tokens`, `latency_s` from `perf_counter`) to the run record, so the
  cost/latency profile is inspectable per node, not just per task.

### Cross-project retrieval (real-data arm)

`search_documents` extends the research toolset with dense retrieval over
project 01's Wikipedia slice: the persisted FAISS index + chunk metadata under
`projects/01-rag-agent/data/index/chunks_200` are loaded **read-only** via
`rag_agent.index` (a workspace dependency) — no re-indexing, no writes under
01's data dir. The same MiniLM embedding model that built the index embeds the
query; results are formatted "chunk_id | title — excerpt" with 600-char
excerpts so a single snippet carries its key fact. Suite task t15 grades a
multi-hop lookup across two articles (Wright brothers → 1903; Wind power →
2022; the gap is 119 years) with the same deterministic graders as the
synthetic tasks.

## Decision

Graph-per-node (option 2) with deterministic evals and disk-serialized HITL
checkpoints; toolsets composed via `FunctionToolset` + `PrefixedToolset`.

## Changelog

- 2026-10-14 — Initial build: tools/toolsets, Plan→Execute→Critique graph,
  HITL checkpointing, 14-task suite with pydantic-evals graders, CLI + DVC
  stages, real run on qwen3:32b.
- 2026-10-17 — Hosted-provider wave: per-node step traces (`StepTrace`) in run
  records; spend-ledger budget wiring (suite cap $2.00, per-task cap $0.25,
  `budget_limits` on every call, totals in the CLI); hosted preset routing
  through `provider_model_settings()`; full 15-task hosted run on
  `kimi-for-coding` (thinking disabled); `cost_latency_bars` figure;
  `search_documents` cross-project retrieval over 01's Wikipedia index
  (read-only) with suite task t15; LM Studio documented as the local preset.
- 2026-10-18 — Tool-discipline wave: prompts/docstrings tightened after the
  traces showed planner "supplement" steps and executor note-taking habits
  (8 unplanned calls); Critique now audits TOOLS USED against the PLAN and
  the Execute node records tools per visit (superseded attempts no longer
  pollute the graded trajectory); held-out suite (`HELDOUT_SUITE`, 10 unseen
  tasks incl. 3 designed-to-fail refusal probes) with `--heldout` CLI mode
  and `detail.heldout` metrics; `evals.py` split into `evals.py` (suite +
  grading), `figures.py` (figure builders) and `report.py` (report/metrics)
  with re-exports for import stability; t15 expected_tools widened to
  `search_documents + calculator` (the year-gap subtraction is arithmetic)
  and the t05 prompt pinned to "before inverter losses" to remove ground-
  truth ambiguity.
