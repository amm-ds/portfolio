# 09 held-out live confirmation vs legacy recorded run

Date: 2026-11-19 (overnight queue, item 15)
Executor: Kimi Code
Run: `LLM_MODEL=kimi-for-coding LLM_COST_LIMIT_USD=5 LLM_SUITE_COST_LIMIT_USD=5 uv run python -m agentic_workflows.cli run-all --heldout --records-path collaboration/reviews/20261118-live-confirmation/heldout_live_records.json`
Ledger: `50 metered calls, 96,166 in + 11,984 out tokens; estimated spend $0.094112 of $5.0 suite cap (cloud-equivalent, labelled estimate)` — cap never approached; run exited 0.

Grading: offline (`cli evaluate --heldout --records-path ... --reports-dir live-grading`), no model calls.
Records: `heldout_live_records.json` (19 records: 13 `ok` answer tasks, 6 `refused` probes).

## Comparison (counts with denominators)

| row | live confirmation (2026-11-19) | legacy recorded run (committed) |
|---|---|---|
| answer preservation | 13/13 (100%) | 13/13 (100%) |
| graceful refusals (should-fail probes) | 6/6 (100%) | 5/6 (83.3%) |
| step budget | 19/19 (100%) | 18/19 (94.7%) |
| latency budget | 19/19 (100%) | 12/19 (63.2%) |
| deadline cancellations | 0/19 | 0/19 |

Legacy values are quoted unchanged from
`projects/09-agentic-workflows/reports/metrics.json → detail.heldout`
(answer_success 1.0, should_fail_pass_rate 0.833, step_budget 0.947,
latency_budget 0.632). No committed file under
`projects/09-agentic-workflows/data/` or `reports/` was touched by the run or
the grading (verified with `git status`).

## Reading

The live run confirms the new contracts end-to-end against the hosted
`kimi-for-coding` model: every unseen answer is preserved with the exact tool
set, every designed-to-fail probe refuses gracefully, and no task exceeded the
step or latency budget. The legacy run's single refusal miss and seven
latency-budget misses did not reproduce live. These are single runs of 19
tasks each — the live row is one confirmation pass, not a tightened estimate;
see `metrics.json:detail.heldout.pass_rate_intervals` (Wilson intervals) for
the uncertainty on the legacy rates.

## Files

- `heldout_live_records.json` — the 19 live run records (scratch, uncommitted)
- `run.log` / `run.log.previous` — full console log (previous run's log preserved)
- `live-grading/metrics.json` — offline grading output (`detail.heldout`)
