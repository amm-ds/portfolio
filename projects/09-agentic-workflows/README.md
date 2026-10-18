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
| `workflow.py` | pydantic-graph `Plan → Execute → Critique → End` workflow with typed state, a bounded repair path on validation failure, a one-shot critique loop-back (now auditing tools used against the plan), per-node step traces, and hosted/local model presets |
| `hitl.py` | Human-in-the-loop checkpoint: plan, pause with a typed `ApprovalRequest`, serialize to `data/checkpoint.json`, resume via CLI (approve / reject-with-feedback) |
| `evals.py` | 15-task tuning suite + 10-task held-out set (3 designed-to-fail refusal probes) with exact ground truths, `pydantic-evals` graders (answer success, tool selection, step budget, latency budget, refusal success), spend-ledger budget wiring, per-call tool-trace capture |
| `figures.py` / `report.py` | The four story figure builders and the report/metrics assembly (`reports/metrics.json` + `detail.tooling` + `detail.heldout`, HTML report) — split out of `evals.py` (audit P1), re-exported for import stability |
| `cli.py` | `prepare [--heldout]` / `run` / `run-all [--heldout]` / `evaluate [--heldout]` / `checkpoint request|approve|reject` |

## Results

All **15 tuning-suite tasks** ran end-to-end on the hosted Kimi coding
endpoint (`kimi-for-coding`) via plain `run-all` with per-call tool capture
on, after a tool-discipline pass (tightened prompts + tool docstrings; the
Critique node now audits tools against the plan). See
`reports/metrics.json` and `reports/report.html` (written by `evaluate`);
grading is deterministic and runs fully offline from
`data/run_records.json`.

| task | category | answer | tool set | latency | calls |
|---|---|---|---|---|---|
| t01 | lookup | ✓ | exact | 16.1s | 1 |
| t02 | lookup | ✓ | exact | 11.7s | 1 |
| t03 | calculation | ✓ | exact | 17.4s | 2 |
| t04 | calculation | ✓ | exact | 23.3s | 3 |
| t05 | calculation | ✓ | exact | 31.6s | 3 |
| t06 | calculation | ✓ | exact | 18.2s | 2 |
| t07 | conversion | ✓ | exact | 11.7s | 1 |
| t08 | conversion | ✓ | exact | 11.5s | 1 |
| t09 | conversion | ✓ | exact | 11.8s | 1 |
| t10 | multi_step | ✓ | exact | 19.9s | 2 |
| t11 | multi_step | ✓ | exact | 20.3s | 2 |
| t12 | note_keeping | ✓ | exact | 22.0s | 3 |
| t13 | calculation | ✓ | exact | 17.0s | 2 |
| t14 | multi_step | ✓ | exact | 24.8s | 3 |
| t15 | lookup (real corpus) | ✓ | exact | 31.1s | 3 |

Headline numbers (hosted full run): **answer success 15/15**, **tool
selection 15/15** exact-set (from 8/15 — the previous run's 8 unplanned
calls: `note_store` ×4, `calculator` ×2, `search_documents` ×2), step budget
15/15, latency budget 15/15. All 30 captured calls were planned (call
precision 100%, tool recall 100%). Median latency **18.2s** per task (p95
31.1s). Totals: ~85k in + ~12k out tokens; ledger spend **$0.086** of the
$2.00 suite cap (~$0.009/task cloud-equivalent).

Two suite entries were re-scoped while tuning — disclosed, not silent grader
edits: t15's expected set gained `calculator` (the 119-year gap is
arithmetic), and t05's prompt now pins "before inverter losses" (both 38.4
and 36.9 kWh were defensible readings of the old wording).

### Held-out set (audit finding 6)

10 unseen tasks over the same corpora (`data/tasks_heldout.json`; 7 answer
tasks across all five categories + 3 designed-to-fail probes that ask for a
nonexistent tool or an impossible conversion — graded by `RefusalSuccess`:
no crash, a stated refusal). Run on hosted **after** the tuning set was
clean (`run-all --heldout` → `evaluate --heldout`):

| split | n | result |
|---|---|---|
| answer tasks | 7 | answer success 7/7, exact tool set 7/7 (12 calls, all planned) |
| should-fail probes | 3 | graceful refusal 3/3 — no crash, no fabricated number |

Honest caveat: n=10 (7 + 3) is a small sample — the held-out set checks for
prompt overfitting and confabulation/failure behavior, it does not
re-estimate the headline rates. It already earned its keep once: the first
held-out run caught a probe confabulating a "1 kg/L basis" conversion; the
conversion docstrings now forbid invented factors. Details in
`metrics.json detail.heldout`.

Figures (in `reports/figures/`, `.html` + `.json` per figure):
`suite_summary` (outcomes by split: tuning × 4 graders, held-out answers,
should-fail probes), `tool_usage_matrix` (captured calls per task × tool),
`node_waterfall` (latency stacked per graph visit), `cost_latency_bars`
(tokens, cost, latency per task). The workflow graph itself is a mermaid
diagram in `story.yaml` and the docs page. Every record's `tool_calls` trace
shows each tool invocation with args, latency, result size, and success.

## Cost

Costs are **labelled cloud-equivalent estimates** at the public reference card
($1.00/Mtok input, $4.00/Mtok output) — the hosted key is membership-quota,
not pay-per-token, so nothing is a billed amount. `run-all` resets the spend
ledger, caps the suite at `LLM_SUITE_COST_LIMIT_USD` ($2.00), enforces a
$0.25 per-task cap through the meter callback (a capped task is recorded as
`budget_exceeded`, the suite continues), and prints the totals. The same
estimates price local inference at $0. All hosted runs of this wave (6 suite
runs incl. tuning iterations + held-out runs) totaled ~$0.46
cloud-equivalent combined — each individual run sits under the $2.00 cap, so
the cap was never raised.

## Reproduce

```bash
# 1. Suite definition (offline)
uv run python -m agentic_workflows.cli prepare
uv run python -m agentic_workflows.cli prepare --heldout

# 2. Live run — needs a provider (ADR-0004):
#    hosted:  LLM_BASE_URL/LLM_API_KEY/LLM_MODEL in the repo-root .env
#             (Kimi Code membership endpoint is the reference hosted setup)
#    local:   Ollama with qwen3:32b pulled — or LM Studio, an equivalent
#             OpenAI-compatible local preset the same branch serves:
#             LLM_BASE_URL=http://localhost:1234/v1, LLM_API_KEY=lm-studio
ollama pull qwen3:32b
uv run python -m agentic_workflows.cli run-all
uv run python -m agentic_workflows.cli run-all --heldout   # held-out set

# 3. Grading + figures + report (offline)
uv run python -m agentic_workflows.cli evaluate
uv run python -m agentic_workflows.cli evaluate --heldout  # → detail.heldout
```

Or via DVC: `dvc repro` (stages `prepare → run → evaluate`). Note the
`search_documents` tool (tasks t15, h02) reads project 01's index from
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
