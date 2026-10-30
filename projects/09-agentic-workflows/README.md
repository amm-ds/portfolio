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
| `evals.py` | 15-task tuning suite + 19-task held-out set (13 answer tasks across five categories + 6 designed-to-fail refusal probes) with exact ground truths, `pydantic-evals` graders (answer success, tool selection, step budget, latency budget, refusal success), spend-ledger budget wiring, per-call tool-trace capture |
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
31.1s). Totals: ~85k in + ~12k out tokens; suite total **$0.13** of the
$2.00 suite cap (~$0.0088/task mean cloud-equivalent).

Two suite entries were re-scoped while tuning — disclosed, not silent grader
edits: t15's expected set gained `calculator` (the 119-year gap is
arithmetic), and t05's prompt now pins "before inverter losses" (both 38.4
and 36.9 kWh were defensible readings of the old wording).

### Held-out set (audit finding 6)

19 unseen tasks over the same corpora (`data/tasks_heldout.json`; 13 answer
tasks across all five categories + 6 designed-to-fail probes that ask for a
nonexistent capability, an impossible conversion, or an absent fact — graded
by `RefusalSuccess`: no crash, a stated refusal). The original 10 (h01-h10)
ran on hosted **after** the tuning set was clean; the 2026-10-30 expansion
wave added 6 answer tasks over previously unexercised corpus facts (radio
call sign, battery base-load-only remainder, ft→m conversion, weekly drone
endurance, freezer box capacity, and the photosynthesis topic of 01's
Wikipedia slice) and 3 refusal probes (currency conversion, fact absent from
the handbook, arithmetic outside the calculator's AST bounds). The new tasks
ran under the existing $0.25/$2.00 guards on local Ollama
(`qwen3.6:35b-a3b-q4_K_M`; hosted credentials blanked for the run, metered
**$0.00** by the local rate card — 27 metered calls, 111k in / 32k out
tokens, ~35 min for 9 tasks). Records are mixed-provider by design
(`data/heldout_records.json`): h01-h10 hosted, h11-h19 local.

| split | n | result |
|---|---|---|
| answer tasks | 13 | answer success 13/13, exact tool set 13/13 (22 calls, all planned; precision/recall/exact-set 100%) |
| should-fail probes | 6 | graceful refusal 5/6 — h17/h18 stated grounded refusals; h19 see below |

Measured negatives, kept honest:

- **h19 (2^500):** the model kept calling the capped calculator (both
  bounded-retry Execute visits burned on "exponent too large") and the graph
  exited through its failure End — whose message ("Workflow could not
  complete: …") carries no refusal marker, so `RefusalSuccess` scores it a
  miss. A failure-message wording gap, not confabulation: no fabricated
  number left the workflow.
- **Latency budget is provider-sensitive:** the 60 s ceiling was tuned on
  the hosted endpoint (all 12 hosted held-out tasks ran 9.0-40.9 s); 7/9
  local tasks exceeded it (67.1-1,430.9 s on this machine's qwen3.6
  generation speeds). h17's critique revise → re-execute loop on ~2.5 min
  generations also produced the suite's only step-budget miss (10 > 8).
  Step budget overall 18/19; the USD caps were never at risk ($0.00 local).

Honest caveat: n=19 (13 + 6) is still a small sample — the held-out set
checks for prompt overfitting and confabulation/failure behavior, it does
not re-estimate the headline rates. It already earned its keep twice: the
first hosted run caught a probe confabulating a "1 kg/L basis" conversion
(conversion docstrings now forbid invented factors), and the local wave
exposed the failure-message wording gap. Details in
`metrics.json detail.heldout`.

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
estimates price local inference at $0. All hosted runs to date (8 suite
runs incl. tuning iterations, held-out runs, and the two 2026-10-29 repeat
passes) totaled ~$0.65 cloud-equivalent combined — each individual run sits
under the $2.00 cap (repeat passes metered $0.10 and $0.09 on the ledger), so
the cap was never raised. The 2026-10-30 held-out expansion (9 new tasks)
ran entirely on local Ollama: $0.00 metered of the $2.00 suite cap, with the
hosted credentials blanked for the process so no hosted quota could be
touched.

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
