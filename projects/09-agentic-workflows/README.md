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
| `evals.py` | 15-task suite with exact ground truths, `pydantic-evals` graders (answer success, tool selection, step budget, latency budget), spend-ledger budget wiring, report builder with four figures |
| `cli.py` | `prepare` / `run` / `run-all` / `evaluate` / `checkpoint request|approve|reject` |

## Results

All **15 suite tasks** ran end-to-end on the hosted Kimi coding endpoint
(`kimi-for-coding`, thinking disabled) via plain `run-all` — ~9.5 minutes of
wall clock for the suite, where the local 32B reasoning model needed >2 hours
for 8 tasks. See `reports/metrics.json` and `reports/report.html` (written by
`evaluate`); grading is deterministic and runs fully offline from
`data/run_records.json`.

| task | category | answer | tool set | latency | tokens (in/out) | est. cost |
|---|---|---|---|---|---|---|
| t01 | lookup | ✓ | +note_store | 17.1s | 4,637/595 | $0.0070 |
| t02 | lookup | ✓ | +note_store | 16.5s | 4,678/654 | $0.0073 |
| t03 | calculation | ✓ | +note_store | 22.5s | 7,619/859 | $0.0111 |
| t04 | calculation | ✓ | +note_store | 27.2s | 8,084/1,289 | $0.0132 |
| t05 | calculation | ✓ | +note_store, search_documents | 33.9s | 9,257/1,126 | $0.0138 |
| t06 | calculation | ✓ | +note_store, search_documents | 28.7s | 11,189/1,158 | $0.0158 |
| t07 | conversion | ✓ | +calculator | 13.3s | 4,411/467 | $0.0063 |
| t08 | conversion | ✓ | +calculator | 13.5s | 4,343/451 | $0.0061 |
| t09 | conversion | ✓ | +calculator | 11.6s | 4,361/494 | $0.0063 |
| t10 | multi_step | ✓ | +note_store, search_documents | 45.9s | 44,470/1,777 | $0.0516 |
| t11 | multi_step | ✓ | exact | 13.3s | 4,945/685 | $0.0077 |
| t12 | note_keeping | ✓ | exact | 19.9s | 6,961/948 | $0.0108 |
| t13 | calculation | ✓ | exact | 23.3s | 5,459/959 | $0.0093 |
| t14 | multi_step | ✓ | +search_documents | 266.9s | 36,125/1,527 | $0.0422 |
| t15 | lookup (real corpus) | ✓ | +calculator | 14.9s | 6,718/742 | $0.0097 |

Headline numbers (hosted full run): **answer success 15/15**, step budget
15/15, latency budget 14/15 (t14 had one runaway execute loop — cut by the
4M-token `UsageLimits`, recovered on the bounded retry), **tool selection
3/15** — exact-set grading records the hosted model's unprompted extra tool
calls (`note_store`, `calculator`) as misses on otherwise-correct answers.
Median latency **19.9s** per task (local 32B: 474s). Totals: 163k in + 14k out
tokens; ledger spend **$0.13** of the $2.00 suite cap (per-task costs above
are pre-cache-discount rate-card estimates, summing to $0.22).

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
