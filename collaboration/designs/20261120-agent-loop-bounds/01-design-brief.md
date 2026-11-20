# Design brief: bound the agent's tool loop (project 01)

Date: 2026-11-20
Designer: Claude Code
Status: draft for owner approval. Nothing here is approved for implementation.
Source: `collaboration/reviews/20261120-prompt-size-investigation/00-report.md` (branch `prompt-size-investigation-2026-11-20`, head `499f128`).

## Problem

The analysis agent's tool loop has no effective bound on the work one answer can do:

- Every model turn re-sends the whole transcript; there is no history trimming.
- The only per-run limits are `request_limit=400` and a 4M total-token ceiling. Both are high enough that one answer can burn about 1.5M input tokens (sealed-v2 index 26 in the 62-question set).
- `search_documents` takes `top_k` from the model, unvalidated. A large value can return most of the corpus (about 360k tokens) in one tool result.
- The local-provider path has no budget limit (`budget_limits()` returns `None`).
- Consequences measured so far: two answerable questions in the 58-question run were aborted at the token ceiling and produced no verdict. Cost per run is unpredictable (single calls of about $0.36 and $0.52 in the retry).

## Goal

Make every answer's cost and tool work bounded, with a predictable ceiling, without lowering answer quality more than a pre-registered amount.

## Non-goals

- No change to retrieval, reranking, the verify loop, the judge, or the thresholds.
- No new model, no new provider.
- No change to the committed 58-question or 62-question numbers. A new measurement will be a separate, labelled run.

## Success criteria (fixed now, measured after implementation)

1. No answer exceeds a per-answer input-token ceiling of 200,000, on the sealed-v2 set and on the local reproduction.
2. No answer makes more than 8 tool calls. No `search_documents` call returns more than 10 citations.
3. Budget-terminated rows: 0.
4. On the 120 sealed-v2 questions, the change in false abstention and in unsupported-claim rate against the current configuration is no worse than +0.05 absolute. The comparison is paired on the same questions and reported with a paired interval.
5. Spend for the re-measure stays inside the cap the owner approves.

If criterion 4 fails, the change is reported as a quality cost, and the owner decides whether to keep it.

## Constraints

- Hosted spend only on `kimi-for-coding`, with an owner-approved cap.
- Production behaviour changes only by the bounds above. Prompts and schema stay the same.
- Gate suite stays green: pytest, `check_headline_numbers.py`, `check_docs.py`. The known coverage gate (78.19% against 80%) is reported separately and not changed.
