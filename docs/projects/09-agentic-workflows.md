# 09 · Agentic AI Workflows

**Domain:** Agentic AI · **Data:** 12-document synthetic "Atlas Valley"
handbook + project 01's Wikipedia FAISS index (read-only) · **Status:**
working showcase on the standard platform

> A client deciding where LLM agents may run unsupervised needs graded
> evidence, not a demo.
> Headline: a 15-task deterministic suite grades a hosted multi-step
> workflow at 15/15 on every grader — answers, exact tool-set, step budget,
> latency — for ~$0.01 cloud-equivalent per task, and a 10-task held-out
> set (3 designed-to-fail probes) verifies the behavior generalizes beyond
> the tuning prompts.
>
> [Interactive case study with figures →](https://github.com/amm-ds/portfolio/tree/main/projects/09-agentic-workflows)

Single-shot agents are the demo; workflows are the product. This project is
the platform's dedicated agentic-AI-workflows showcase: multi-step, stateful
LLM workflows as explicit typed graphs — planning, tool orchestration,
bounded retries, self-critique, and human-in-the-loop checkpoints — graded by
a deterministic evaluation harness with per-run cost and latency budgets,
plus a cross-project retrieval arm on real data.

## Key results (full 15-task hosted run, `kimi-for-coding`)

Plain `run-all` on the hosted Kimi coding endpoint with per-call tool
capture on, after a tool-discipline pass (tightened prompts/docstrings;
Critique now audits tools used against the plan). How to read this table:
counts are tasks passed out of 15; tool selection is an exact-set match, so
unprompted extra calls count as misses.

| metric | value |
|---|---|
| tasks run | **15/15** ok, zero retries, every critique passed |
| answer success | **15/15** |
| tool-selection accuracy | **15/15** exact-set — up from 8/15; all 30 captured calls planned (call precision 100%, tool recall 100%), `detail.tooling` |
| step budget | 15/15 |
| latency | median **18.2 s**, p95 31.1 s per task; 180 s budget held 15/15 |
| tokens / cost | ~85k in + ~12k out; ledger total **$0.086** cloud-equivalent of the $2.00 suite cap (~$0.009/task) |
| held-out set | 7/7 answer success, 7/7 exact tool set, **3/3 should-fail probes refused gracefully** (`detail.heldout`) |

![All 15 hosted tasks pass every grader — answers and exact-set tool selection now agree at 15/15 after the tool-discipline pass.](../assets/projects/09-agentic-workflows/per_task_grading.png){ width="100%" }

| suite | 15 tuning tasks + 10 held-out, 5 categories — 14 tuning tasks over the deterministic Atlas Valley corpus, 1 real-data lookup over 01's Wikipedia index (t15), held-out tasks reuse both corpora unseen |
|---|---|
| graders | answer success (exact keywords), tool selection (exact tool set), step budget, latency budget — deterministic `pydantic-evals` evaluators; `evaluate` runs fully offline from `data/run_records.json` |
| should-fail probes | 3 held-out tasks ask for a nonexistent tool or an impossible conversion; `RefusalSuccess` grades the failure behavior (no crash + a stated refusal) — a fabricated number fails |
| capture | every run record carries per-node `StepTrace`s plus per-call `tool_calls` (name, args, latency, result size, ok), the plan's step list, and the critique verdict |
| budgets | spend-ledger caps: $2.00 suite (`LLM_SUITE_COST_LIMIT_USD`), $0.25 per task; `budget_limits` on every live call |
| model | hosted `kimi-for-coding` via the repo-root `.env` (ADR-0004); local Ollama or any OpenAI-compatible server (e.g. LM Studio: `http://localhost:1234/v1`) through the same branch |

The tool-discipline pass is the story the traces tell: on the earlier run
8 of 47 calls were unplanned (`note_store` ×4 as a scratchpad habit,
`search_documents` ×2 as planner "supplements", `calculator` ×2 as duplicate
verification). The fixes were wording, not model swaps — `note_store`'s
docstring now says "use ONLY when the task explicitly asks to record", the
planner may not add supplement steps, the executor must call only planned
tools, and Critique audits TOOLS USED against the PLAN. Two tuning entries
were re-scoped honestly: t15's expected set gained `calculator` (the
119-year gap is arithmetic) and t05's prompt pins "before inverter losses".
Result: 30/30 planned calls.

![Every plan/execute/critique transition, retry and loop bound is explicit code — the graph the workflow runs, including the bounded-repair loop and the human-approval checkpoint lane.](../assets/projects/09-agentic-workflows/agent_architecture.png){ width="100%" }

Read the architecture diagram as a control-flow contract, not a picture: every transition, retry bound, and critique loop-back is executable code (Critique now also audits the tools used against the plan), and the approval lane marks exactly where a human can pause a run — typed state on disk, resumed by approve or reject-with-feedback — before execution continues.

![Which tools each task called, and how often — the per-call matrix the exact-set grader reads; on the final run every invocation lands in a task's expected set.](../assets/projects/09-agentic-workflows/tool_usage_matrix.png){ width="100%" }

The tool matrix is the behavioral x-ray: each row is one task, so a bright
cell under a tool no task planned for is an unplanned habit rather than a
need. On the earlier hosted run `note_store` lit up on 4 tasks and
`search_documents` on 2 — the exact misses grading recorded; the final run
shows zero unplanned calls, which is what 15/15 exact-set means in calls
rather than in bars.

![Where the time goes per task: stacked plan/execute/critique visits — the slowest task finished in 32 s, far under the 180 s budget; a retry appears as an extra labelled segment, never as one stretched visit.](../assets/projects/09-agentic-workflows/node_waterfall.png){ width="100%" }

## Architecture

- **Workflow graph** — pydantic-graph `Plan → Execute → Critique → End` over a
  typed `WorkflowState`. Execute repairs validation failures on a bounded
  self-loop (`repair ≤ max_execute_retries`, then `End(failure)`); Critique
  loops `revise` back to **Execute** at most once (never back to Plan), now
  with a tools-vs-plan audit; the graph ends with a structured
  `WorkflowResult` (answer, steps, tools used, per-call tool traces,
  calibrated confidence, tokens, per-node step traces). Tool calls are
  recorded per Execute visit, so superseded attempts do not pollute the
  graded trajectory.
- **Human-in-the-loop** — a checkpoint node plans, then pauses: the typed
  `ApprovalRequest` + full state serialize to `data/checkpoint.json`; the CLI
  resumes with approve (re-enter at Execute) or reject-with-feedback (back to
  Plan with the feedback as the re-plan brief). State on disk is the single
  source of truth.
- **Tools & toolsets** — a "research ops" domain (fictional Atlas Valley field
  station); every call is traced into the run record by signature-preserving
  wrappers (the model-visible schema is unchanged):

  | tool | signature | does | guardrail | this run |
  |---|---|---|---|---|
  | `calculator` | `(expr) -> float` | AST arithmetic | no names/calls; exponent ≤ 64; no invented factors | 11 calls / 11 planned |
  | `unit_convert` | `(value, from, to) -> float` | fixed-table unit conversion | dimension match; cross-dimension = decline | 3 / 3 |
  | `search_handbook` | `(query, top_k=3) -> list[str]` | keyword search, 12-doc in-code corpus | deterministic scoring | 13 / 13 |
  | `search_documents` | `(query, top_k=3) -> list[str]` | dense retrieval over 01's FAISS index (read-only) | prebuilt index, no writes | 2 / 2 |
  | `note_store` | `(ctx, action, note="") -> list[str]` | per-run notebook | empty append rejected; only on explicit request | 1 / 1 |

  A second math toolset is composed via `PrefixedToolset`
  (`math_percent_change`, `math_round_to`) — two toolsets, one agent, zero
  name collisions, unit-tested.
- **Hosted/local model presets** — when a hosted provider is configured, every
  node agent is built with the platform preset: thinking disabled (big token
  saving) and temperature omitted (the endpoint rejects explicit values).
  LM Studio (`LLM_BASE_URL=http://localhost:1234/v1`, `LLM_API_KEY=lm-studio`)
  is the documented equivalent local preset — any OpenAI-compatible local
  server rides the same branch.
- **Evaluation** — `pydantic-evals` dataset + custom evaluators (code in
  `evals.py` — suite/grading; `figures.py` + `report.py` for figures and
  report after the audit-P1 split). Run stage (live LLM) and evaluate stage
  (offline grading) are separate DVC stages. `metrics.json detail.tooling`
  decomposes the exact-set tool score offline; `detail.heldout` reports the
  held-out split (answer tasks vs should-fail probes) separately.

## Figures

The showcase figures — per-task grading (answer success vs tool selection),
cost/latency per task, the tool-usage matrix (calls per task × tool from the
captured traces), the node waterfall (per-visit latency stack), and the agent
architecture diagram — live in `reports/figures/` (one `.html` + `.json` per
figure, served by the showcase API). Aggregates in `reports/metrics.json`
(key `agentic_suite`, plus `detail.tooling` and `detail.heldout`); full
report in `reports/report.html`.

## Where things live

- Code + design: [projects/09-agentic-workflows](https://github.com/amm-ds/portfolio/tree/main/projects/09-agentic-workflows) —
  CLI `prepare [--heldout] | run | run-all [--heldout] | evaluate [--heldout] | checkpoint request|approve|reject`, DVC stages in `dvc.yaml`
- Options & rationale: [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/09-agentic-workflows/DESIGN.md)
- 73 offline tests cover the graph, HITL, tools, documents, budget wiring, tool capture, eval machinery, and the held-out graders.

## Reproduce

```bash
cd projects/09-agentic-workflows
uv run python -m agentic_workflows.cli prepare
uv run python -m agentic_workflows.cli run-all           # live run (hosted or local provider)
uv run python -m agentic_workflows.cli evaluate          # offline grading → reports/
# held-out set:
uv run python -m agentic_workflows.cli prepare --heldout
uv run python -m agentic_workflows.cli run-all --heldout
uv run python -m agentic_workflows.cli evaluate --heldout  # → detail.heldout
```

Provider: repo-root `.env` (see `.env.example`) with `LLM_BASE_URL` +
`LLM_API_KEY` for hosted, Ollama running for local, or LM Studio with the
local preset above. Tasks t15/h02 need 01's index materialized
(`projects/01-rag-agent/data/index/chunks_200`).

Tests are fully offline (scripted `FunctionModel`, fixture search index):
`uv run pytest projects/09-agentic-workflows/tests`
