# Architecture proposal: bound the agent's tool loop

Date: 2026-11-20
Designer: Claude Code
Status: draft for owner approval.
Source brief: `collaboration/designs/20261120-agent-loop-bounds/01-design-brief.md`

## Decision

Bound the loop with three independent limits and one input clamp. No history trimming in this change.

1. **Per-answer usage limits** (pydantic-ai `UsageLimits`), passed to every agent run:
   - `tool_calls_limit = 8`
   - `request_limit = 12` (down from 400)
   - `input_tokens_limit = 200_000` (per answer, not total)
   - `total_tokens_limit` stays as it is, as the outer backstop.
   Limits are read from `RAGConfig` so they can be changed without code edits. The default values are the ones above.
2. **Clamp `top_k`** inside the `search_documents` tool, not in the prompt: `top_k = min(max(top_k, 1), 10)`. The tool signature doesn't change, so the model's calls still succeed.
3. **Local-provider limit**: `budget_limits()` returns a finite default for the local path, using the same per-answer ceilings, so no path runs unbounded.

## Why caps before history trimming

Trimming history changes what the model sees, so it changes answers and needs its own quality study. Caps change only how long the loop can run. They are the smaller change, and their effect can be measured directly from the existing traces (tool-call counts and input tokens per answer). If caps alone bring criteria 1–3 in line and quality stays within criterion 4, trimming is not needed. If they don't, trimming becomes its own design.

## Where the limits go

- Limits are set where the agent run is started, in the evaluation and chat paths that call the agent. Find the call sites with a search for the run call; do not guess them.
- `top_k` clamp goes in the `search_documents` tool body in `agent.py`, before `ctx.deps.search`.
- Local budget default goes in `llm_budget.py` (in `libs/portfolio-core`), next to the existing `budget_limits()`.

## Alternatives considered

| Alternative | Why not now |
|---|---|
| Trim tool results from old turns | Changes model input and answers. Needs a quality study. Held as a fallback. |
| Lower `request_limit` only | Doesn't bound per-call size. The `top_k` case would still produce one huge result. |
| Remove the total-token ceiling | Removes the outer backstop. Not acceptable. |
| Summarise tool output | New model call, new cost, new failure mode. |

## Failure modes

| Failure | Detection | Behaviour |
|---|---|---|
| Caps cut a legitimate multi-hop answer | Criterion 4 and tool-call counts by category | Reported as quality cost; owner decides |
| `UsageLimits` raises mid-answer | Run returns an error with a limit name | Recorded as a budget-terminated row, not an unsupported claim. Count reported separately. |
| Clamp hides a real need for >10 citations | Count of clamped calls per answer | Logged; reported |
| Local path now stops on a limit | Local-run traces | Reported; the local default can be raised by config |

## Verification plan (no hosted spend until approved)

1. Unit tests: the clamp; that `UsageLimits` values are read from config; that a budget-terminated run is recorded separately.
2. Local reproduction (zero hosted): run index 26 and the two 58-question rows (indices 23 and 35) on the local judge and local model. Confirm that each answer ends within the limits and that the trace records the limit that fired. This checks the mechanism, not the quality. It is not a hosted measurement.
3. Hosted re-measure: all 120 sealed-v2 questions on the new bounds, paired against the current configuration on the same questions. Cost cap set by the owner before the run.

## Rollback

Set the limits back to the current values in config (`request_limit = 400`, no tool-call or input-token cap) and remove the clamp. Each part is one config value or one line, so rollback is a revert of a small diff.

## Open questions for the owner

1. Re-measure cost cap. Estimate from the earlier runs: a bounded 120-question pass should cost well under the $2.50 stop used in the last run, but the variance is high. Proposed hard cap $2.50, stop at $2.20. Needs your approval.
2. Whether a budget-terminated answer should count as a failure in the headline. Proposed: no. It is reported as its own count, as now.
3. Whether to keep the local default limit at the same value as hosted.
