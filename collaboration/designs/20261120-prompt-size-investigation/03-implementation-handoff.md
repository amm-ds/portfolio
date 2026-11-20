# Implementation handoff: why some sealed-v2 questions send ~1.4M-token prompts

Date: 2026-11-20
Designer: Claude Code
Executor: Kimi Code
Status: approved (owner, 2026-11-20): read-only investigation. $0 hosted. No code change, no copy change.
Source: `collaboration/reviews/20261120-g4-heldout-retry-report/00-report.md` (health check and retry: index 26 cost $0.518 and $0.363 in single calls, about 1.4M tokens); `reports/sealed_v2/question_traces_heldout.json` (58-question run: rows 23 and 35 hit the 4,000,000-token per-answer limit).

## Objective

Find out why some sealed-v2 questions produce prompts of about 1.4M tokens or more, and whether that is a defect. The cost is a few questions per run, but it can also stall production answers. Report a root cause or a ranked set of hypotheses with evidence. Propose a fix as a separate design; do not implement it.

## Standing rules

- Branch `prompt-size-investigation-2026-11-20` from `g4-heldout-62-2026-11-20` (head `522ca2b`). Commit with trailer `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`. Push with upstream. No merge, no deploy.
- Zero hosted calls. Do not run the pipeline on any question. Read code and existing artifacts only.
- No edits to `src/`, `params.yaml`, prompts, committed reports, or copy. New files under `collaboration/reviews/20261120-prompt-size-investigation/` only.
- No new dependency, no download.

## Steps

1. Establish token counts per question from existing artifacts. Check the meter logs under `reports/sealed_v2*/` and `reports/sealed_v2_62_retry/` for per-call token usage. Record, per question index, the input and output tokens if present, or state that they are not present.
2. Identify the 1.4M-token cases: 62-file indices 26 (and any others the meters show as large), and 58-file indices 23 and 35. Record their categories and expected behaviour.
3. Trace the context path in `projects/01-rag-agent/src/rag_agent/` from retrieval to the final prompt. For each source of added text, state whether it is bounded: retrieved chunks, reranked chunks, evidence gate output, verify-loop repair history, tool-call result accumulation across turns, and any retry that re-sends the full history. Record file and line.
4. Compare with a typical question. Note what is different about the large cases: chunk count, chunk length, number of tool calls, number of repair rounds, or a retry that re-appends context.
5. Rank hypotheses. For each: the mechanism, the evidence for it, the evidence against it, and what single read-only check would settle it.
6. Write `collaboration/reviews/20261120-prompt-size-investigation/00-report.md` with: per-question token table (or the statement that it is unavailable), the code path with file and line references, the ranked hypotheses, the settling checks, and a recommendation: defect or expected behaviour. Include an explicit line on whether the 26% and 28/120 numbers are affected, and how.
7. Do not spend hosted money to settle a hypothesis. If a hypothesis can only be settled by a hosted call, list it as an open question for the owner.

## Gates

No gate is required for this phase: no code changes. If you run any check, report its actual output.

## Stop conditions

- Any hosted call: stop and report.
- The root cause needs a code change to confirm: stop, write the hypotheses and checks, and say so.
- A committed artifact would change: stop.

## Deliverable boundary

Report what the artifacts and code show. Do not recommend a copy change in this report.
