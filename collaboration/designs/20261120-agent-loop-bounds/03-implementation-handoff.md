# Implementation handoff: bound the agent's tool loop

Date: 2026-11-20
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-20): design as proposed, and step 7 hosted re-measure with `kimi-for-coding` only, hard cap $2.50, stop at cumulative $2.20. Step 7 runs only if step 6 shows criteria 1–3 hold locally.
Source: `collaboration/designs/20261120-agent-loop-bounds/01-design-brief.md`, `02-architecture-proposal.md`.

## Objective

Bound per-answer tool calls, requests and input tokens; clamp `top_k`; give the local path a finite per-answer limit. Verify the mechanism locally, then measure quality on the 120 sealed-v2 questions under an approved hosted cap.

## Amendment 3 (owner-approved, 2026-11-21): raise the tool-call limit and re-measure

Approved: set `agent_tool_calls_limit = 16` (from 8). Keep `agent_request_limit = 12`, `agent_input_tokens_limit = 200_000`, and the 4M total-token backstop unchanged.

Re-measure: all 120 sealed-v2 questions on branch `agent-loop-bounds-2026-11-20`, into `reports/agent_loop_bounds/sealed_v2_120_limit16/`. Hosted `kimi-for-coding` only. Hard cap $1.20, stop at cumulative $1.00 for this amendment.

Reporting:
- Count budget-terminated rows as FAILURES in the headline, not as excluded. Report the count separately as well.
- Report unsupported-claim rate and false-abstention rate over all 120 and over answerable only, each with Wilson 95%.
- Paired comparison against the old bounds (limit 8, run `sealed_v2_120`) on the same questions, and against the pre-bounds configuration (committed 58 and 62 runs, pooled).
- Per-answer maximum input tokens and maximum tool calls.
- Spend from the meter.

Stop conditions in this amendment: if the 16-call run hits the stop figure, stop and report completed items. If budget-terminated rows exceed 10% of answers, do not claim criterion 3 passes; report it as failed.

Do not run this step until S1 is complete (local runs must not load `projects/01-rag-agent/.env`).

## Standing rules

- Branch `agent-loop-bounds-2026-11-20` from `prompt-size-investigation-2026-11-20` (head `499f128`). Commit each step with the trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`. Push with upstream. No merge. No deploy.
- Hosted calls: `kimi-for-coding` only, only in step 6, only under the approved cap.
- Do not change retrieval, reranking, the verify loop, the judge, prompts, schemas, or thresholds.
- Do not edit committed reports (`reports/sealed_v2/`, `reports/sealed_v2_62*/`, `reports/sealed_v2_120_pooled/`), copy, or the 58 or 62 question files. New folders for new runs only.
- No new dependency. No download.

## Steps

1. **Read first.** Find every call site that starts an agent run (search for the run call in `projects/01-rag-agent/src/` and the CLI). List them in the commit message of step 2. Confirm the installed pydantic-ai version supports `UsageLimits` with `tool_calls_limit`, `request_limit`, `input_tokens_limit`, and `total_tokens_limit`. If a field is missing, stop and report.
2. **Config.** Add `RAGConfig` fields with the proposed defaults: `agent_tool_calls_limit=8`, `agent_request_limit=12`, `agent_input_tokens_limit=200000`. Mirror them in `params.yaml` only if the existing pattern requires it. Commit: `feat(01): agent usage limits in config (defaults bound the tool loop)`.
3. **Wire the limits.** Pass `UsageLimits` to every agent run found in step 1. Record the limit that fired in the trace, and add a `usage_limit_hit` field, optional, default None. Ensure a limit error is recorded as `budget_terminated`, not as an unsupported claim. Commit: `feat(01): per-answer usage limits applied at every agent run`.
4. **Clamp `top_k`.** In the `search_documents` tool body in `agent.py`, clamp `top_k` to [1, 10] before `ctx.deps.search`. Count clamped calls per answer and record the count in the trace (optional field). Commit: `feat(01): search_documents top_k clamped to 1..10`.
5. **Local default and tests.** Give `budget_limits()` in `libs/portfolio-core/src/portfolio_core/llm_budget.py` a finite default for the local path, using the same per-answer ceilings. Add tests: clamp boundaries (0, 1, 10, 11, 1000); `UsageLimits` read from config; a limit error becomes a `budget_terminated` row; the local default is finite. Run `uv run pytest -q projects/01-rag-agent` and the portfolio-core tests; report actual output (coverage gate 78.19% vs 80% remains a known gap; report separately). Run `check_headline_numbers.py` and `check_docs.py`. Commit: `test(01): usage-limit and clamp tests`.
6. **Local reproduction (zero hosted).** Run indices 26 (62-file), 23 and 35 (58-file) on the local judge and local model. Stop if the local model is not available. Record, per answer: input tokens, tool calls, requests, which limit fired. Write to `reports/agent_loop_bounds/local_repro/`. This checks the mechanism only. Commit: `feat(01): local reproduction of usage limits on the three large cases`.
7. **Hosted re-measure (only after owner approval of the cap).** All 120 sealed-v2 questions on the new bounds, into `reports/agent_loop_bounds/sealed_v2_120/`. Pair against the current configuration on the same questions. Compute: budget-terminated count; per-answer maximum input tokens; tool-call maximum; unsupported-claim rate and false abstention, each with Wilson 95%; the paired difference against the current configuration with a paired interval. Stop at the approved stop figure; report completed items and the rest.
8. **Report.** Write `collaboration/reviews/20261120-agent-loop-bounds-report/00-report.md`: commits and hashes, the call sites found in step 1, the limits fired, the local reproduction table, the hosted measurement with the success criteria in the brief (criteria 1–5), spend from the meter, gate output, and any deviation from this handoff.

## Gates

- `uv run pytest -q projects/01-rag-agent` (coverage gate reported separately)
- `uv run pytest -q libs/portfolio-core` (or the project's equivalent command; state the one you used)
- `uv run python scripts/check_headline_numbers.py`
- `uv run python scripts/check_docs.py`
- `ruff check` and `ruff format --check` on changed files; `mypy` on changed source.

Report actual output. Do not claim a gate passed unless it ran.

## Budget

- Steps 1–6: $0 hosted.
- Step 7: approved hard cap $2.50, stop at cumulative $2.20 (owner, 2026-11-20). Do not exceed either figure. If a single call would cross the stop, stop before making it and report.

## Stop conditions

- Step 1 finds the installed pydantic-ai lacks a required `UsageLimits` field: stop.
- Any hosted call before step 7 is approved: stop.
- Local model unavailable in step 6: stop and report.
- Criteria 1–3 fail in step 6 (a limit does not hold): stop and report before step 7.
- A committed report or the 58/62 files would change: stop.
- Spend reaches the stop figure: stop and report.
