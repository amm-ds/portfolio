# 09 · Agentic AI Workflows

**Domain:** Agentic AI · **Data:** 12-document synthetic "Atlas Valley"
handbook + project 01's Wikipedia FAISS index (read-only) · **Status:**
working showcase on the standard platform

> A client deciding where LLM agents may run unsupervised needs graded
> evidence, not a demo.
> Headline: a 15-task deterministic suite grades a hosted multi-step
> workflow at 15/15 answer success for ~$0.01 cloud-equivalent per task —
> and catches the extra tool calls that demos hide (exact-set tool match
> 3/15).
>
> [Interactive case study with figures →](https://github.com/amm-ds/portfolio/tree/main/projects/09-agentic-workflows)

Single-shot agents are the demo; workflows are the product. This project is
the platform's dedicated agentic-AI-workflows showcase: multi-step, stateful
LLM workflows as explicit typed graphs — planning, tool orchestration,
bounded retries, self-critique, and human-in-the-loop checkpoints — graded by
a deterministic evaluation harness with per-run cost and latency budgets,
plus a cross-project retrieval arm on real data.

## Key results (full 15-task hosted run, `kimi-for-coding`)

Plain `run-all` on the hosted Kimi coding endpoint (thinking disabled) — ~9.5
minutes of wall clock where the local 32B reasoning model needed >2 hours for
8 tasks. How to read this table: counts are tasks passed out of 15; tool
selection is an exact-set match, so unprompted extra calls count as misses —
which is why a "failure" there can still be a correct answer.

| metric | value |
|---|---|
| tasks run | **15/15** (no `--ids` bound) |
| answer success | **15/15** |
| tool-selection accuracy | **3/15 (20%)** exact-set — the suite catching what demos hide: graders flagged unprompted `note_store`/`calculator` calls on otherwise-correct answers |
| step budget | 15/15 |
| latency | median **19.9 s**, p95 266.9 s per task (180 s budget held 14/15; t14 had one runaway execute loop, cut by the 4M-token `UsageLimits`, recovered on the bounded retry) |
| tokens / cost | 163k in + 14k out; ledger total **$0.13** cloud-equivalent of the $2.00 suite cap ($0.22 pre-cache-discount rate-card sum) |

| suite | 15 tasks, 5 categories — 14 over the deterministic Atlas Valley corpus + 1 real-data lookup over 01's Wikipedia index (t15) |
|---|---|
| graders | answer success (exact keywords), tool selection (exact tool set), step budget, latency budget — deterministic `pydantic-evals` evaluators; `evaluate` runs fully offline from `data/run_records.json` |
| budgets | spend-ledger caps: $2.00 suite (`LLM_SUITE_COST_LIMIT_USD`), $0.25 per task; `budget_limits` on every live call; per-node `StepTrace` in each record |
| model | hosted `kimi-for-coding` via the repo-root `.env` (ADR-0004); local Ollama (`qwen3:32b`) or any OpenAI-compatible server (e.g. LM Studio: `http://localhost:1234/v1`) through the same branch |

For comparison, the earlier bounded local run (8 of the 14 tasks then in the
suite, on `qwen3:32b`) scored 6/8 answers, 3/8 tool selection, median 474
s/task — and t07/t09 died at the plan node to reasoning-model empty-turn
flakiness.

## Architecture

- **Workflow graph** — pydantic-graph `Plan → Execute → Critique → End` over a
  typed `WorkflowState`. Execute repairs on validation failure (bounded);
  Critique can loop back once; the graph ends with a structured
  `WorkflowResult` (answer, steps, tools used, calibrated confidence, tokens,
  per-node step traces).
- **Human-in-the-loop** — a checkpoint node plans, then pauses: the typed
  `ApprovalRequest` + full state serialize to `data/checkpoint.json`; the CLI
  resumes with approve (continue at Execute) or reject-with-feedback (re-plan,
  then Execute). State on disk is the single source of truth.
- **Tools & toolsets** — a "research ops" domain (fictional Atlas Valley field
  station): `calculator` (locked-down AST evaluator), `unit_convert`,
  `search_handbook` (deterministic 12-doc corpus), `note_store` (per-run
  notebook), plus `search_documents`: dense retrieval over project 01's
  persisted FAISS Wikipedia index, loaded read-only via the `rag_agent`
  workspace dependency (no re-indexing). A second math toolset is composed via
  `PrefixedToolset` (`math_percent_change`, `math_round_to`) — two toolsets,
  one agent, zero name collisions, unit-tested.
- **Hosted/local model presets** — when a hosted provider is configured, every
  node agent is built with the platform preset: thinking disabled (big token
  saving) and temperature omitted (the endpoint rejects explicit values).
  LM Studio (`LLM_BASE_URL=http://localhost:1234/v1`, `LLM_API_KEY=lm-studio`)
  is the documented equivalent local preset — any OpenAI-compatible local
  server rides the same branch.
- **Evaluation** — `pydantic-evals` dataset + custom evaluators (suite in
  `src/agentic_workflows/evals.py`); run stage (live LLM) and evaluate stage
  (offline grading) are separate DVC stages.

## Figures

The showcase figures — per-task grading (answer success vs tool selection),
per-task latency vs the 180 s budget, answer success by category, and
per-task cost/latency — live in `reports/figures/` (one `.html` + `.json`
per figure, served by the showcase API). Aggregates in
`reports/metrics.json` (key `agentic_suite`); full report in
`reports/report.html`.

## Where things live

- Code + design: [projects/09-agentic-workflows](https://github.com/amm-ds/portfolio/tree/main/projects/09-agentic-workflows) —
  CLI `prepare | run | run-all | evaluate | checkpoint request|approve|reject`, DVC stages in `dvc.yaml`
- Options & rationale: [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/09-agentic-workflows/DESIGN.md)
- 57 offline tests cover the graph, HITL, tools, documents, budget wiring, and eval machinery.

## Reproduce

```bash
cd projects/09-agentic-workflows
uv run python -m agentic_workflows.cli prepare
uv run python -m agentic_workflows.cli run-all     # live run (hosted or local provider)
uv run python -m agentic_workflows.cli evaluate    # offline grading → reports/
```

Provider: repo-root `.env` (see `.env.example`) with `LLM_BASE_URL` +
`LLM_API_KEY` for hosted, Ollama running for local, or LM Studio with the
local preset above. Task t15 needs 01's index materialized
(`projects/01-rag-agent/data/index/chunks_200`).

Tests are fully offline (scripted `FunctionModel`, fixture search index):
`uv run pytest projects/09-agentic-workflows/tests`
