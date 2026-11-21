# Agent-loop bounds report

Date: 2026-11-21
Handoff: `collaboration/designs/20261120-agent-loop-bounds/03-implementation-handoff.md`
(approved: design + step-7 hosted cap, $2.50 hard, stop $2.20, kimi-for-coding only)
Branch: `agent-loop-bounds-2026-11-20` from `prompt-size-investigation-2026-11-20`
(`499f128`). No merge, no deploy. Committed reports, copy, and the 58/62
question files untouched.

## Commits

- `335785b` — `feat(01): agent usage limits in config (defaults bound the tool loop)`
- `f2cc771` — `feat(01): per-answer usage limits applied at every agent run`
- `520e3b2` — `feat(01): search_documents top_k clamped to 1..10`
- `2a356bf` — `test(01): usage-limit and clamp tests`
- `aa33f4c` — `docs(01): local repro input for agent-loop bounds (3 questions, hashed)`
- `e2d933e` — `feat(01): local reproduction of usage limits on the three large cases`
- `5c7f41b` — `feat(01): sealed-v2 120 re-measure under agent-loop bounds (hosted, $1.13)`

## Step 1 — call sites and field check

Agent-run call sites in `projects/01-rag-agent/src/`: `cli.py:461` (chat),
`evaluate.py:181` (eval answer loop) — the analysis agent; `judge.py:55`,
`verify.py:392`, `verify.py:416` — judge/verify agents already carrying
`budget_limits()`, left unchanged per the no-judge/verify-change constraint.
pydantic-ai 2.55.0 supports all required `UsageLimits` fields
(`tool_calls_limit`, `request_limit`, `input_tokens_limit`,
`total_tokens_limit`) — stop condition not triggered.

## What shipped

Per-answer bounds from `RAGConfig` (`agent_tool_calls_limit=8`,
`agent_request_limit=12`, `agent_input_tokens_limit=200000`, 4M total-token
backstop), wired at both analysis-agent call sites; the limit that fires is
recorded in the trace as `usage_limit_hit` and rows still classify as
`budget-terminated`. `search_documents` `top_k` clamped to [1, 10] with a
per-answer clamp counter (`top_k_clamps`). `budget_limits()` local path now
finite (12 / 8 / 200k / 4M) — previously `None`, i.e. unbounded.

## Gates (actual output)

- Step 5: `uv run pytest -q projects/01-rag-agent` → **219 passed, 0
  failed**; exit 1 solely on the known coverage gate (78.45% vs 80%,
  reported separately; threshold untouched).
- `uv run pytest -q libs/portfolio-core` → green, coverage 96.00%.
- Step 5 `check_headline_numbers.py` → `11 claims checked, 0 finding(s)` / OK.
- Step 8 re-run `check_headline_numbers.py` → `11 claims checked, 2
  finding(s)`: `[NEW] 02-demand-forecasting/README.md/story.yaml: headline
  '0.6211' not found` — **caused by uncommitted working-tree modifications
  to `projects/02-demand-forecasting/reports_m5_full/{metrics.json,
  evaluation_metadata.json}` (848 + 128 lines) made outside this handoff
  during the session** (none of the 7 commits above touch project 02; the
  files are left uncommitted and un-reverted for the owner). Project 01's
  claims pass.
- `check_docs.py` → `check-docs: OK` (both runs).
- ruff check/format and mypy on all changed sources → clean.

## Step 6 — local reproduction (zero hosted, after an incident)

Proper local runs (`ollama:qwen3.6:35b`, $0): all three questions stopped at
the 9th tool call (`tool_calls_limit=8` held), zero clamps, no
input-limit termination. **Incident (reported, ~$0.0196 hosted):** the first
repro attempt ran hosted because an old untracked
`projects/01-rag-agent/.env` loaded via pydantic-settings despite an
`unset`; those runs are kept as `*_hosted_incident`. There, the hosted model
completed 58[23]/58[35] with verdicts at **9,145 / 9,503 input tokens** —
vs the old configuration's 4,005,788 / 4,010,952 total-token aborts (~400×
reduction) — and 62[26] stopped at the same tool-call limit.

| question | local verdict | limit hit | clamps | hosted-incident verdict | hosted-incident input tok |
|---|---|---|---|---|---|
| 62[26] (unanswerable) | budget-terminated | tool_calls=9 | 0 | budget-terminated | (not metered) |
| 58[23] (single_hop) | budget-terminated | tool_calls=9 | 0 | unsupported-claim | 9,145 |
| 58[35] (single_hop) | budget-terminated | tool_calls=9 | 0 | unsupported-claim | 9,503 |

GO decision for step 7: every limit held (the stop condition's failure
definition — "a limit does not hold" — was not met); the budget-terminated
rows are the bound firing on the known pathological trio. Documented
tension: criterion 3 (0 budget-terminated) is not met locally; step 7
proceeded to measure that cost honestly on the hosted 120.

## Step 7 — hosted 120-question re-measure under the bounds

One run, `data/golden_sealed_v2.json` (parent hash re-verified), kimi-for-
coding, ledger stop $2.20. **Metered spend $1.128938** (caps untouched).
Verdicts: correct 67, unsupported-claim 31, empty-answer 5,
**budget-terminated 17** — every termination at `tool_calls_limit of 8`
(9th call refused), zero input-limit terminations, zero top_k clamps. Agent
phase: 779,721 input tokens over 103 completed answers (~7.6k average).

## Success criteria (design brief, measured on the 120)

1. **Per-answer input ≤ 200,000 — PASS.** No answer hit the input ceiling
   (pre-request check); the largest per-answer figures the meter shows are
   an order of magnitude under it (~7.6k average; total 0.78M where the old
   config's three worst answers alone exceeded 6.9M).
2. **≤ 8 tool calls; ≤ 10 citations per search — PASS.** 17 answers were
   refused a 9th tool call; searches never exceeded 10 (0 clamps needed).
3. **Budget-terminated rows = 0 — FAIL.** 17 rows (indices 20, 21, 23, 27,
   29, 53, 55, 56, 58, 59, 83, 84, 87, 113, 114, 116, 119 of the 120-file),
   vs 2 under the old configuration. 16 of the 17 were `correct` under the
   old configuration — the bound converts completing answers into
   no-verdict rows on this model.
4. **Paired change ≤ +0.05 absolute — PASS at the point estimate.** Paired
   per question (n=120, seed 42, 2000-rep paired bootstrap): unsupported
   28/120 → 31/120, **Δ = +0.0250**, 95% paired interval [−0.0417, +0.1000];
   false abstention 7/92 → 5/92, **Δ = −0.0217**, 95% interval [−0.0761,
   +0.0217]. The upper interval bound for unsupported (+0.100) exceeds
   +0.05 — the point change is within tolerance, the uncertainty is not.
   Caveat: the 17 terminated rows carry no verdict; their would-be outcomes
   are unmeasured mass (same understated-unknown structure as the old
   4M-abort rows).
5. **Spend inside cap — PASS.** $1.128938 of $2.20 stop / $2.50 hard.

## Verdict and owner decision

The mechanism is a precise, well-instrumented bound: criteria 1, 2, 4
(point), 5 pass; spend per answer is now predictable (~$0.009 average,
worst case bounded by construction). **Criterion 3 fails: `tool_calls_limit=8`
is too tight for this model on ~14% of the sealed set.** The brief's
fallback applies — this is reported as a quality cost; the owner decides
whether to keep it, raise the limit (e.g. 12–16 tool calls; the 200k input
ceiling still bounds cost), or design a graceful answer-from-partial-work on
cap exhaustion (a code change for a separate handoff). Per-question
comparisons for all 120 rows are committed in the run's traces;
`reports/agent_loop_bounds/sealed_v2_120/` holds metrics + traces.

## S1 follow-up (owner-approved 2026-11-21): hosted-call hygiene

Root cause of the step-6 incident: pydantic-settings loads the CWD-relative
`.env` — including the untracked `projects/01-rag-agent/.env` (predating this
work) — even when the operator unsets shell variables; the earlier attempt's
`unset` never reached `Settings`. The step-6 hosted incident spend is
recorded here per the plan: **$0.0196 cloud-equivalent** (q58_23 $0.0099,
q58_35 $0.0097, q62_26 $0.0000 on the meter), kimi-for-coding, on 2026-11-20.

Guard shipped: `projects/01-rag-agent/scripts/run_local_eval.sh` exports
empty `LLM_API_KEY`/`LLM_BASE_URL` (which beat the `.env` file in
pydantic-settings precedence and make `is_hosted_active()` false) and execs
the CLI — every local evaluate/chat run sets the endpoint explicitly to
local. `calibrate_judge.py` was already immune (forced-local `Settings`
kwargs).

## Deviations

1. ~$0.0196 accidental hosted spend during step 6 (project `.env` incident,
   documented; proper local runs re-done at $0).
2. Step 7 proceeded despite criterion 3 not holding locally, per the stop
   condition's own definition of failure ("a limit does not hold") — all
   limits held; the cost is measured, not assumed.
3. `check_headline_numbers.py` findings at step 8 are external to this
   handoff (uncommitted project-02 working-tree edits; see Gates).
4. Judge/verify call sites were listed in step 1 but left on
   `budget_limits()` per the standing no-change constraint.
