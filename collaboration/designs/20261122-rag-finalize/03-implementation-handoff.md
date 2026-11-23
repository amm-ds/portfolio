# Implementation handoff: finalize project 01 (RAG) on hosted evals

Date: 2026-11-22
Designer: Claude Code
Executor: Kimi Code
Status: draft, pending owner decisions on items B and C (item A can start)

## Owner decisions (2026-11-22)

1. Judge copy: hosted judge figures only. The local judge (qwen2.5:3b, 0.4433) is dropped from the README, docs and `story.yaml`. The hosted figure cited is the one in the committed `projects/01-rag-agent/reports/judge_calibration_hosted/results.json` (0.4536, kappa 0.5361), since the 0.3966 figure is not in any committed JSON. Kimi must label the source.
2. Headline: hosted only. The README, docs and story use hosted G4 pooled-120 numbers. Merging the G4 branch data into main is not yet approved; confirm with owner before any merge.
3. S3 spec approved: the 120-question sealed-v2 run at `agent_tool_calls_limit=16`, stop $2.50, hard cap $3.00. Kimi still needs the exact command (reconstruct from commit `5c7f41b`) and the checkpointing check before the run starts.
7. Project 02 (out of scope here): pending owner direction, see below.
Source: the close-out record (`20261122-rag-close-out`) was discarded with the local trials at owner request, so the figures below are the reference, with their sources named.

## Objective

Make the project 01 RAG documentation match the hosted evaluation of record, with no local-model claims left in the public copy. Hosted numbers only.

## Facts to check against (recompute, do not copy blindly)

- G4 pooled 120 (sealed v2), hosted: unsupported 28/120 = 0.2333, Wilson 95% [0.1667, 0.3166]; answerable-only 28/92 = 0.3043 [0.2197, 0.4046]; false abstention 7/92 = 0.0761; budget-terminated 2 (listed separately). Source: `collaboration/reviews/20261120-g4-heldout-retry-report/00-report.md` (branch `g4-heldout-62-2026-11-20`, final numbers section).
- Judge calibration on main, with discrepancies found in review:
  - Local judge qwen2.5:3b: committed `projects/01-rag-agent/reports/judge_calibration/results.json` gives false acceptance 0.4433 (Wilson 95% [0.3752, 0.5136]), kappa 0.5464. Reproduction failed: re-running the unmodified script gave 0/194 and 1/194 false acceptances, not 86/194. The figure is committed but not reproducible.
  - Hosted judge qwen3:4b: committed `judge_calibration_hosted/results.json` gives 0.4536 and kappa 0.5361. The README, docs and `story.yaml` cite 0.3966 [0.3269, 0.4707], kappa 0.6052, which is recomputed and appears only in `collaboration/reviews/20261119-execution-report/00-report.md` (lines ~70-80). A per-run file in the same folder gives 0.3563 and 0.6557. No committed JSON holds the cited figures.
- Correction to my earlier note: the `0.4433` sentence is an existing 2026-11-19 result, not from the local-model trials. `projects/01-rag-agent/story.yaml:291` repeats the same judge sentence.
- Main does not contain the G4 pooled-120 numbers. The README, docs and story still use older stress and sealed figures.

## Scope

### A. Consistency check (can start now, read-only)

1. Open `projects/01-rag-agent/README.md`, `docs/projects/01-rag-agent.md`, and `projects/01-rag-agent/story.yaml` (if present). Find every RAG headline number (unsupported rate, judge figures, sample sizes).
2. For each number, find its committed source and recompute it. Record PASS, or the discrepancy with file and line.
3. Do not edit any file in this item. Output a table to `collaboration/reviews/20261122-rag-finalize-check/00-check.md`.

### B. Copy change (blocked: needs owner-approved text)

Do not edit until the owner approves wording. Candidate change the owner may choose: keep the local judge sentence but state its role precisely. Options are for the owner; the designer does not pick.

### C. S3 (blocked: owner decision)

Owner decision (2026-11-22): run the full limit-16 pass at a higher stop. Approved spend cap: stop at cumulative $2.50, hard cap $3.00.

Definition (corrected after review): "limit-8 / limit-16" is `RAGConfig.agent_tool_calls_limit`, the per-answer tool-call cap for the analysis agent. Default 8 (commit `335785b`), raised to 16 at `6a1e6bf` (Amendment 3). Both are on the unmerged branch `agent-loop-bounds-2026-11-20`, file `projects/01-rag-agent/src/rag_agent/config.py` around lines 172-174, not on main.

Records:
- limit-8: commit `5c7f41b`, hosted sealed-v2 120 re-measure, spend $1.128938, 17 of 120 budget-terminated (criterion 3 failed).
- limit-16: `collaboration/reviews/20261120-agent-loop-bounds-report/00-report.md`, section "S3 follow-up (Amendment 3)". The 120-question attempt hit its $1.00 stop at $1.001784 (hard cap $1.20) and committed nothing, because the CLI writes results only at the end. The report estimates $1.5–1.8 for a full pass, which is consistent with the $2.50 stop.

Blockers before any spend:
1. The exact run command is not recorded in a located file. Reconstruct it from commit `5c7f41b` and the trace folder `reports/agent_loop_bounds/sealed_v2_120/`, and confirm it with the owner.
2. Decide whether to merge or cherry-pick the config from the unmerged branch first.
3. Mitigate the write-at-end risk: the earlier abort lost all results. Check whether the CLI can checkpoint, or run in chunks that each write.

Kimi must not start the run until all three are settled. If not, stop and report.

## Out of scope

- Any local-model run, download, or deletion.
- Any change to `src/rag_agent/`, `params.yaml`, prompts, or the judge.
- Any hosted call (no evals run in this handoff).
- Git: no merge, no push, no branch deletion. If a commit is needed for item A's report, use a new branch `rag-finalize-2026-11-22`, no `Co-Authored-By` trailer for any model.
- The two project 02 metrics files (`projects/02-demand-forecasting/reports_m5_full/`), modified in the working tree, origin unknown. Do not revert, stage, or commit them.

## Commands

```bash
cd /Users/alejandro/work/portfolio
uv run python scripts/check_docs.py
```

Report the actual output. Do not claim a check passed unless it ran.

## Acceptance

- [ ] Item A table produced; every headline RAG number has a PASS or a located discrepancy.
- [ ] No file in `src/` or `params.yaml` changed.
- [ ] No hosted call made.
- [ ] `scripts/check_docs.py` output reported verbatim.
- [ ] Items B and C left untouched until owner decides, and reported as blocked.

## Stop conditions

- Any discrepancy that changes a headline RAG claim: stop and report; do not fix it silently.
- Any request to a non-local host outside the approved hosted path: stop.
