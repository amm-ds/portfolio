# Implementation handoff: 09 held-out live confirmation on kimi-for-coding

Date: 2026-11-18
Designer: Claude Code
Executor: Kimi Code (coding execution agent)
Status: approved by owner (2026-11-18) for one run, under the caps below. No other hosted calls are approved.
Source review: `collaboration/reviews/20261117-experiment-review/09-agentic-workflows.md`
Related: `collaboration/designs/20261117-09-agentic-review-fixes/03-implementation-handoff.md` (pass-rate intervals; its "no hosted calls" rule still applies to that handoff and is not changed here)

## Objective

Run the held-out suite (19 tasks) once against the hosted `kimi-for-coding` model, to confirm the new contracts live: answer preservation, graceful refusals, and deadline behaviour. Record the results beside the legacy numbers, never over them.

## Approved scope and caps

- Model: `kimi-for-coding` (membership-quota key; cost is a cloud-equivalent estimate, not billed).
- Hard caps for this process: `LLM_COST_LIMIT_USD=5` and `LLM_SUITE_COST_LIMIT_USD=5`. Do not raise them. Do not change `.env`.
- One run only. If it stops at a cap, do not retry; report what completed.
- Output goes to a scratch records file, never to `projects/09-agentic-workflows/data/run_records.json` or `heldout_records.json`.

## Ordered steps

1. Confirm the working tree is clean for `projects/09-agentic-workflows/` and that `collaboration/reviews/20261118-live-confirmation/` exists. If `run.log` or `heldout_live_records.json` already exist there, move them aside to `*.previous` before starting. Do not delete them.
2. Run, from `projects/09-agentic-workflows`:

```bash
LLM_MODEL=kimi-for-coding LLM_COST_LIMIT_USD=5 LLM_SUITE_COST_LIMIT_USD=5 \
  uv run python -m agentic_workflows.cli run-all --heldout \
  --records-path /Users/alejandro/work/portfolio/collaboration/reviews/20261118-live-confirmation/heldout_live_records.json \
  > /Users/alejandro/work/portfolio/collaboration/reviews/20261118-live-confirmation/run.log 2>&1
```

Run it in the foreground or in the background, but wait for it to exit. Do not start a second run while the first is active.

3. Check `run.log` for the ledger line ("metered calls", "estimated spend"), any "budget cap reached" warning, and the final `run-all complete` line. Copy the ledger line into your completion report.
4. Grade the new records offline, without model calls. Use the project's evaluate step against the records file (`evaluate --records-path ... --reports-dir ...` as the CLI allows). Write the report under `collaboration/reviews/20261118-live-confirmation/`, not under `reports/`. If the CLI cannot grade a separate records file without writing into `reports/`, stop and write `OPEN_QUESTIONS.md` beside this handoff.
5. Produce a short comparison table in `collaboration/reviews/20261118-live-confirmation/comparison.md` with these rows, using counts with denominators: answer preservation, refusals, step budget, latency budget, deadline cancellations. Put the legacy values from `projects/09-agentic-workflows/reports/metrics.json` beside them, labelled "legacy recorded run". Do not change any legacy value.

## Acceptance criteria

- [ ] One run completed, or stopped at a cap and reported as such.
- [ ] Ledger spend is at or below $5 and is quoted in the completion report.
- [ ] Records and report exist only under `collaboration/reviews/20261118-live-confirmation/`.
- [ ] `comparison.md` lists live and legacy numbers, with the legacy rows labelled.
- [ ] No committed file under `projects/09-agentic-workflows/data/` or `reports/` has changed. Confirm with `git status`.

## Stop conditions

- Stop and write `OPEN_QUESTIONS.md` beside this handoff if the ledger reports spend above $4 before the run finishes, the provider returns repeated authentication or quota errors, or grading needs to write into a committed path.
- Never call another provider, and never switch the model, without a new owner approval.

## Completion report (required)

Exact files written, the ledger line, the run command, pass and fail counts per row, the cap status, and any remaining risk. Quote numbers exactly. Do not run git mutations; the owner commits.
