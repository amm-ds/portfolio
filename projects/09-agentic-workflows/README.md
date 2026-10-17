# Agentic AI Workflows

> Status: **working** — multi-step, stateful LLM workflows with typed graphs,
> tool orchestration, human checkpoints, budget-capped evaluation, and a
> cross-project retrieval arm on real data.

- Problem: single-shot agents demo well, but production agentic systems need
  explicit multi-step control flow — planning, tool use, bounded retries, and
  human checkpoints — all of it auditable and measurable.
- Design: [DESIGN.md](DESIGN.md)
- Story: [story.yaml](story.yaml) (served at `/projects/09-agentic-workflows/story`)

## What is here

| Module | What it does |
|---|---|
| `tools.py` | Research-ops toolset (`calculator`, `unit_convert`, `search_handbook`, `search_documents`, `note_store`) over a deterministic synthetic corpus + real retrieval, plus a `PrefixedToolset` composition demo (`math_*` tools, zero collisions) |
| `documents.py` | Cross-project arm: `search_documents` loads project 01's persisted FAISS index + chunk metadata **read-only** (`rag_agent.index` workspace dependency) — dense retrieval over 3.5k Wikipedia chunks, no re-indexing |
| `workflow.py` | pydantic-graph `Plan → Execute → Critique → End` workflow with typed state, a bounded repair path on validation failure, a one-shot critique loop-back, per-node step traces, and hosted/local model presets |
| `hitl.py` | Human-in-the-loop checkpoint: plan, pause with a typed `ApprovalRequest`, serialize to `data/checkpoint.json`, resume via CLI (approve / reject-with-feedback) |
| `evals.py` | 15-task suite with exact ground truths, `pydantic-evals` graders (answer success, tool selection, step budget, latency budget), spend-ledger budget wiring, per-call tool-trace capture, offline tooling decomposition, report builder with five figures |
| `cli.py` | `prepare` / `run` / `run-all` / `evaluate` / `checkpoint request|approve|reject` |

## Results

All **15 suite tasks** ran end-to-end on the hosted Kimi coding endpoint
(`kimi-for-coding`) via plain `run-all` with per-call tool capture on.
See `reports/metrics.json` and `reports/report.html` (written by
`evaluate`); grading is deterministic and runs fully offline from
`data/run_records.json`.

| task | category | answer | tool set | latency | calls |
|---|---|---|---|---|---|
| t01 | lookup | ✓ | +note_store | 16.3s | 2 |
| t02 | lookup | ✓ | exact | 9.7s | 1 |
| t03 | calculation | ✓ | exact* | 17.1s | 3 |
| t04 | calculation | ✓ | exact | 17.8s | 2 |
| t05 | calculation | ✓ | +note_store, search_documents | 25.4s | 4 |
| t06 | calculation | ✓ | exact* | 20.4s | 6 |
| t07 | conversion | ✓ | exact | 10.9s | 1 |
| t08 | conversion | ✓ | exact | 9.8s | 1 |
| t09 | conversion | ✓ | +calculator | 10.3s | 2 |
| t10 | multi_step | ✓ | +note_store | 22.3s | 4 |
| t11 | multi_step | ✓ | +note_store | 21.4s | 5 |
| t12 | note_keeping | ✓ | exact* | 27.3s | 6 |
| t13 | calculation | ✓ | +search_documents | 16.6s | 3 |
| t14 | multi_step | ✓ | exact* | 18.0s | 4 |
| t15 | lookup (real corpus) | ✓ | +calculator | 15.6s | 3 |

\* exact tool set, but with duplicate in-set calls (e.g. t12 searched the
handbook 4×) — free under exact-set grading, now visible in the captured
`tool_calls` traces.

Headline numbers (hosted full run): **answer success 15/15**, step budget
15/15, latency budget 15/15 (t14 — the previous runaway at 266.9 s —
finished in 18.0 s), **tool selection 8/15** exact-set (up from 3/15) — the
misses are 8 unplanned calls: `note_store` ×4 (t01/t05/t10/t11),
`calculator` ×2 (t09/t15), `search_documents` ×2 (t05/t13). Median latency
**17.1s** per task; call precision 83% (39 of 47 calls planned), tool recall
100%. Totals: 93k in + 13k out tokens; ledger spend **$0.10** of the $2.00
suite cap ($0.14 pre-cache rate-card sum).

Figures (in `reports/figures/`, `.html` + `.json` per figure):
`per_task_grading` (answers vs exact-set tool selection),
`tool_usage_matrix` (captured calls per task × tool), `node_waterfall`
(latency stacked per graph visit), `cost_latency_bars` (tokens, cost,
latency per task), `agent_architecture` (the graph itself: nodes, retry
bound, revise loop, HITL lane). Every record's `tool_calls` trace shows
each tool invocation with args, latency, result size, and success.

## Cost

Costs are **labelled cloud-equivalent estimates** at the public reference card
($1.00/Mtok input, $4.00/Mtok output) — the hosted key is membership-quota,
not pay-per-token, so nothing is a billed amount. `run-all` resets the spend
ledger, caps the suite at `LLM_SUITE_COST_LIMIT_USD` ($2.00), enforces a
$0.25 per-task cap through the meter callback (a capped task is recorded as
`budget_exceeded`, the suite continues), and prints the totals. The same
estimates price local inference at $0.

## Reproduce

```bash
# 1. Suite definition (offline)
uv run python -m agentic_workflows.cli prepare

# 2. Live run — needs a provider (ADR-0004):
#    hosted:  LLM_BASE_URL/LLM_API_KEY/LLM_MODEL in the repo-root .env
#             (Kimi Code membership endpoint is the reference hosted setup)
#    local:   Ollama with qwen3:32b pulled — or LM Studio, an equivalent
#             OpenAI-compatible local preset the same branch serves:
#             LLM_BASE_URL=http://localhost:1234/v1, LLM_API_KEY=lm-studio
ollama pull qwen3:32b
uv run python -m agentic_workflows.cli run-all

# 3. Grading + figures + report (offline)
uv run python -m agentic_workflows.cli evaluate
```

Or via DVC: `dvc repro` (stages `prepare → run → evaluate`). Note the
`search_documents` tool (task t15) reads project 01's index from
`projects/01-rag-agent/data/index/chunks_200`, which must be materialized
(01's `dvc repro`).

Single task and human checkpoint demos:

```bash
uv run python -m agentic_workflows.cli run t05
uv run python -m agentic_workflows.cli checkpoint request "Convert 48 km to miles"
uv run python -m agentic_workflows.cli checkpoint approve
uv run python -m agentic_workflows.cli checkpoint reject --feedback "Use fewer steps"
```

## Tests

Offline (scripted `FunctionModel`; the search tool uses a fixture index — no
network, no dependency on 01's data; one skip-marked integration test loads
01's real index when present):

```bash
uv run pytest projects/09-agentic-workflows/tests
```
