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
| `workflow.py` | pydantic-graph `Plan → Execute → Critique → End` workflow with typed state, bounded repair/critique loops, typed ok/refused/failed/deadline outcomes, generic no-evidence stopping, per-node traces, and hosted/local model presets |
| `hitl.py` | Human-in-the-loop checkpoint: plan, pause with a typed `ApprovalRequest`, serialize to `data/checkpoint.json`, resume via CLI (approve / reject-with-feedback) |
| `evals.py` | 15-task tuning suite + 19-task held-out set (13 answer tasks + 6 refusal probes) with exact ground truths, deterministic graders, hard per-task wall-clock deadlines, spend-ledger caps, and per-call traces |
| `figures.py` / `report.py` | The four story figure builders and the report/metrics assembly (`reports/metrics.json` + `detail.tooling` + `detail.heldout`, HTML report) — split out of `evals.py` (audit P1), re-exported for import stability |
| `cli.py` | `prepare [--heldout]` / `run` / `run-all [--heldout]` / `evaluate [--heldout]` / `checkpoint request|approve|reject` |

## Results

These are **legacy recorded measurements**, regenerated offline without new
model calls. The new terminal-outcome/no-evidence/deadline contracts have
deterministic tests. A 2026-11-19 all-hosted live rerun confirmed 13/13
answers, 6/6 graceful refusals, and 19/19 step and latency budgets
([`reports/live_confirmation_20261119/`](reports/live_confirmation_20261119/));
it remains one confirmation run, not repeated efficacy evidence.

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

Headline numbers (legacy recorded run — each task executed once):
**answer success 15/15** (Wilson 95% CI [0.796, 1.000]), **tool
selection 15/15** exact-set, step budget 15/15, latency budget 15/15 (same
interval for each 15/15 rate). All 30
captured calls were planned (call precision 100%, tool recall 100%). Median
latency is **18.2 s** per task (p95 31.1 s). Totals are ~85k input + ~12k
output tokens; suite cost is **$0.13 cloud-equivalent** of the $2.00 suite cap
(~$0.0088/task). Intervals: Wilson score interval (z = 1.96), committed at
`metrics.json:detail.pass_rate_intervals`.

### Held-out set

19 unseen tasks cover the same corpora (`data/tasks_heldout.json`): 13 answer
tasks across all five categories and 6 designed-to-fail probes. The probes ask
for a nonexistent capability, an impossible conversion, or an absent fact;
`RefusalSuccess` requires no crash and a stated refusal.

The records are mixed-provider by design (`data/heldout_records.json`):
h01-h10 use the hosted endpoint and h11-h19 use local Ollama
(`qwen3.6:35b-a3b-q4_K_M`). The local tasks ran under the same $0.25/$2.00
guards with hosted credentials blanked, metering **$0.00** for 27 calls, 111k
input tokens, and 32k output tokens.

| split | n | result |
|---|---|---|
| answer tasks | 13 | answer success 13/13 (Wilson 95% CI [0.772, 1.000]), exact tool set 13/13 (22 calls, all planned; precision/recall/exact-set 100%) |
| should-fail probes | 6 | graceful refusal 5/6 (Wilson 95% CI [0.436, 0.970]) — h17/h18 stated grounded refusals; h19 see below |
| all tasks | 19 | step budget 18/19 (CI [0.754, 0.991]); latency budget 12/19 (CI [0.410, 0.809]) |

Each task ran once in the legacy recorded run; the intervals price only the
binomial sampling uncertainty of those single passes
(`metrics.json:detail.heldout.pass_rate_intervals`).

Measured negatives, kept honest:

- **h19 (2^500), legacy record:** the model kept calling the capped calculator
  (two Execute attempts burned on "exponent too large") and the
  graph returned a failure message with no refusal marker, so
  `RefusalSuccess` scores it a miss. No fabricated number left the workflow.
  Terminal tool failures now return typed `refused` results in deterministic
  tests; the 2026-11-19 live run returned typed `refused` for h19.
- **Latency budget is provider-sensitive:** the 60 s ceiling was tuned on
  the hosted endpoint (all 10 hosted held-out tasks ran 9.0-40.9 s); 7/9
  local tasks exceeded it (67.1-1,430.9 s on this machine's qwen3.6
  generation speeds). h17's critique revise → re-execute loop on ~2.5 min
  generations also produced the suite's only step-budget miss (10 > 8).
  Step budget overall 18/19; the USD caps were never at risk ($0.00 local).

The 19-task sample checks for prompt overfitting and confabulation/failure
behavior; it does not re-estimate the headline rates. Conversion docstrings
forbid invented factors, and the local records preserve the legacy terminal
refusal miss. Details are in `metrics.json detail.heldout`.

### Repeat stability (2026-10-29)

Two further hosted passes of the 15-task tuning suite on `kimi-for-coding`
(`run-all` → `evaluate`, same $0.25/$2.00 caps) kept **answer success 15/15**
and **exact tool sets 15/15** in both passes, with zero unplanned calls and
every task inside the 60 s latency budget. Suite cloud-equivalent estimates
were $0.148 / $0.144 (metrics basis) against $0.131 for the record run; the
metered ledger view was $0.10 / $0.09 of the $2.00 cap. Median task latency
moved from 18.2 s (record run) to 24.1 s / 20.8 s. Each pass scored one
step-budget miss — t03 in the first pass, t10 in the second — when Critique
requested a revision and added an Execute visit; the deterministic step
grader caught both. Captured calls rose from 30 to 33–35 (repeated same-tool
lookups, exact sets unchanged). Stability holds for answers and tool
discipline; latency and step count vary run to run on a hosted endpoint.

Figures (in `reports/figures/`, `.html` + `.json` per figure):
`suite_summary` (outcomes by split: tuning × 4 graders, held-out answers,
should-fail probes), `tool_usage_matrix` (captured calls per task × tool),
`node_waterfall` (latency stacked per graph visit), `cost_latency_bars`
(tokens, cost, latency per task). The workflow graph is interactive React Flow
in `story.yaml` and mermaid on the docs page. Every record's `tool_calls` trace
shows each tool invocation with args, latency, result size, and success.

## Cost

Costs are **cloud-equivalent estimates** at the public reference card
($1.00/Mtok input, $4.00/Mtok output). The hosted key uses membership quota,
so these are not billed amounts. `run-all` resets the spend ledger, caps the
suite at `LLM_SUITE_COST_LIMIT_USD` ($2.00), enforces a $0.25 per-task cap,
and records capped tasks as `budget_exceeded` while the suite continues. Each
task's 60 s latency budget is also an enforced cancellation deadline, recorded
as `deadline_exceeded`, not merely a post-hoc grader. Local
inference meters $0 under the same rate card. The committed local held-out
records used blanked hosted credentials, so they could not consume hosted
quota.

## Limits

Ready for supervised pilots, not unattended use: legacy held-out records pass
only 5/6 refusals, 18/19 step budgets, and 12/19 latency budgets. The
hosted-tuned 60 s latency budget is provider-sensitive — 7 of 9 local Ollama
tasks exceed it. Terminal/deadline behavior has deterministic tests and one
2026-11-19 all-hosted live confirmation; repeated live efficacy is unmeasured.
Suite costs are cloud-equivalent estimates, not invoices.

## Reproduce

```bash
# 1. Suite definition (offline)
uv run python -m agentic_workflows.cli prepare
uv run python -m agentic_workflows.cli prepare --heldout

# 2. Live run — needs a provider (ADR-0004):
#    hosted:  LLM_BASE_URL/LLM_API_KEY/LLM_MODEL in the repo-root .env
#             (Kimi Code membership endpoint is the reference hosted setup)
#    local:   Ollama with the platform default model pulled — or LM Studio,
#             an equivalent OpenAI-compatible local preset the same branch
#             serves: LLM_BASE_URL=http://localhost:1234/v1, LLM_API_KEY=lm-studio
ollama pull qwen3.6:35b-a3b-q4_K_M
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

## Common errors

| symptom | cause | fix |
|---|---|---|
| `run-all` fails at the first LLM call | no provider configured — `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` unset and no local model (ADR-0004, no runtime mock) | hosted: set the three variables in the repo-root `.env`; local: `ollama pull qwen3.6:35b-a3b-q4_K_M`. Tasks t15/h02 additionally need 01's retrieval index — materialize it with `uv run dvc repro projects/01-rag-agent` |

## Figures

| figure | file |
|---|---|
| cost latency bars | [reports/figures/cost_latency_bars.html](reports/figures/cost_latency_bars.html) |
| node waterfall | [reports/figures/node_waterfall.html](reports/figures/node_waterfall.html) |
| suite summary | [reports/figures/suite_summary.html](reports/figures/suite_summary.html) |
| tool usage matrix | [reports/figures/tool_usage_matrix.html](reports/figures/tool_usage_matrix.html) |

