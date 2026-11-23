# Implementation handoff: overnight RAG finish and close (project 01)

Date: 2026-11-22
Designer: Claude Code
Executor: Kimi Code (overnight, unattended)
Status: approved for phases 1-3 and 5 (owner, 2026-11-22: "do overnight, prepare the steps to improve, finish and close rag experiment"). Phase 4 (paid run) is gated; see below.
Related: `collaboration/designs/20261122-rag-finalize/03-implementation-handoff.md` (decisions recorded there: hosted-only judge figures; hosted-only headline; S3 spec approved at limit 16, stop $2.50, hard $3.00)

## Objective

Close the RAG experiment with one defensible result, and leave the repo in a state the owner can review in the morning:

1. Establish whether the hosted judge is trustworthy enough to report, using labels already committed.
2. Produce a reviewable plan and cost estimate for the limit-16 pass, and the checkpointing it needs.
3. Run the limit-16 pass only if every gate in phase 4 is met.
4. Write the close-out: results, what they do and do not show, and the exact owner decisions still open.

Do not improve the pipeline's prompts, code, judge, or params. The experiment is measurement and closure. Any change to the system is a separate, later decision, and is listed as a recommendation only.

## Ground rules

- Branch `rag-finalize-2026-11-22` from `main`. Work on it. Do not merge or push. Do not delete branches. Do not revert or stage the project 02 files (`projects/02-demand-forecasting/reports_m5_full/`).
- Commit only the files this handoff creates, on that branch, with no `Co-Authored-By` trailer for any model. Leave the working tree otherwise clean.
- No edits to `src/`, `params.yaml`, prompts, judge code, or README/docs/story copy. Copy changes wait for owner approval.
- Every hosted call is logged with its host. Hosted calls are allowed only in phase 4.

## Phase 1: judge validation (no spend, read-only on data)

Goal: tell whether the hosted judge's false-acceptance figure reproduces from committed data, before anyone quotes it.

1. Find the committed judge calibration inputs and labels: `projects/01-rag-agent/reports/judge_calibration/` and `judge_calibration_hosted/`, plus the calibration set builder `projects/01-rag-agent/scripts/build_calibration_set.py`.
2. Recompute, from the committed predictions only (no model calls): false acceptance, Wilson 95% interval, and kappa, for the hosted judge (qwen3:4b) and the local judge (qwen2.5:3b).
3. Compare to the committed aggregates: hosted 0.4536 (kappa 0.5361) in `judge_calibration_hosted/results.json`; local 0.4433 (UCB 0.5136, kappa 0.5464) in `judge_calibration/results.json`; the report-only hosted figure 0.3966 (kappa 0.6052) in `collaboration/reviews/20261119-execution-report/00-report.md`.
4. Output `collaboration/reviews/20261122-rag-overnight/01-judge-validation.md` with a table: source, value, reproduced yes/no, and the file and line it came from.

Stop: if the hosted figure committed in `results.json` does not reproduce from its predictions, record it and continue. Do not change it.

## Phase 2: consistency check (no spend)

Run the item A check from the finalize handoff: every headline RAG number in `projects/01-rag-agent/README.md`, `docs/projects/01-rag-agent.md`, and `projects/01-rag-agent/story.yaml`, with its source and a PASS or discrepancy.

Output `collaboration/reviews/20261122-rag-overnight/02-consistency.md`. Do not fix anything.

## Phase 3: prepare the limit-16 pass (no spend)

1. Find the exact run command for the limit-8 record (commit `5c7f41b` on branch `agent-loop-bounds-2026-11-20`, trace folder `reports/agent_loop_bounds/sealed_v2_120/`) and for the limit-16 attempt (`collaboration/reviews/20261120-agent-loop-bounds-report/00-report.md`, section "S3 follow-up (Amendment 3)"). Read them with `git show`. Do not check out or merge that branch.
2. Write `collaboration/reviews/20261122-rag-overnight/03-s3-plan.md` with:
   - the exact command for the 120-question sealed-v2 run at `agent_tool_calls_limit=16`, and where the setting comes from;
   - whether the CLI writes results incrementally. The prior attempt committed nothing because results are written only at the end. If there is no checkpoint, say so and specify the smallest change (for example, chunked runs of 30 questions, each writing its own output). Specify the change; do not make it;
   - the cost estimate and its basis (the report estimates $1.5–1.8 for the full pass; state how the estimate was derived);
   - whether the run's request host is verifiable as hosted-only.
3. If the command cannot be determined from committed files, record exactly what is missing and stop the phase. Do not guess flags.

## Phase 4: paid run (gated)

Run only if ALL of these hold:
- Phase 3 found an unambiguous command and a result-writing method that saves partial results (or the owner has approved a chunked run in writing before the run).
- Phase 1 has finished (its result is recorded, whatever it is).
- Spend cap: stop at cumulative $2.50, hard cap $3.00, as approved. Enforce both through the run's own limit settings. If the run cannot enforce the stop, do not run.

If any gate fails, skip phase 4 and record the reason in the close-out.

If the run runs: record the cumulative spend at each chunk, the host of every request, and the budget-terminated count. Stop at the first request to a non-hosted host, or at any budget error that is not the approved cap.

## Phase 5: close-out

Write `collaboration/reviews/20261122-rag-overnight/00-closeout.md`:

1. **Results.** The hosted pooled-120 figures (from the committed G4 report, cited by file), the phase 4 result if run, and the phase 1 judge validation outcome.
2. **What they show.** Measured hosted unsupported rate, with its interval, and what the judge can and cannot support. Say plainly that the judge's false acceptance is high and the rate is likely an undercount.
3. **Improvement status.** No paired baseline on the same 120 questions exists. Say so. Do not claim improvement.
4. **Experiment closed or open.** Declare one: closed (results final; the remaining items are owner decisions) or open (name the blocker).
5. **Owner decisions still open:** copy wording for README, docs, and story; merge of G4 data into `main`; project 02 headline; any follow-up pipeline or judge change (as recommendations only, not done).

## Commands

```bash
cd /Users/alejandro/work/portfolio
git switch -c rag-finalize-2026-11-22 main
uv run python scripts/check_headline_numbers.py
uv run python scripts/check_docs.py
```

Report the actual output verbatim. Do not claim a check passed unless it ran. Note that `check_headline_numbers` will report the project 02 drift that the owner has chosen to keep; that is expected, not a new failure.

## Acceptance

- [ ] Phase 1 table produced with a reproduced/not-reproduced status for each figure.
- [ ] Phase 2 table produced; no copy edited.
- [ ] Phase 3 plan written, or the missing items named.
- [ ] Phase 4 run only if all gates were met; otherwise the skip reason is in the close-out.
- [ ] Close-out written with one declared status.
- [ ] Nothing merged, pushed, or deleted; no `src/` or copy change; only this handoff's report files committed.

## Stop conditions

- Any non-hosted request during a paid run: stop.
- Cumulative spend above $2.50 or any budget error other than the approved cap: stop.
- Any file change outside `collaboration/reviews/20261122-rag-overnight/` (other than the branch switch): stop and report.
- Phase 1 reveals the judge's committed aggregate is wrong: record it and continue the other phases; do not stop, do not fix.
