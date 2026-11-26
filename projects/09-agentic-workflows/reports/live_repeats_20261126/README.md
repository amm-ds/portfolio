# Held-out live repeats (2026-11-26)

Five identical all-hosted live runs of the 19-task held-out suite against
`kimi-for-coding` (hosted Kimi coding endpoint, OpenAI-compatible,
membership-quota key), graded offline with no model calls — the repeat
consistency measurement behind the article's `pass^5` line. Same runner,
model, and grading as `reports/live_confirmation_20261119/` (which stays
byte-untouched); this folder is the evidence for the repeated-run claims.

| file | content |
|---|---|
| `run<i>/heldout_live_records.json` | the 19 live run records of repeat `i` (13 answer tasks, 6 refusal probes) |
| `run<i>/live_grading_metrics.json` | offline grading of those records (`detail.heldout`) |
| `run<i>/run.log` | runner + grader log, including the metered-spend ledger line |
| `repeats_summary.json` | derived aggregate: per-task pass^5 / pass@5, pooled p50/p95 latency, per-run spend |
| `run_repeats.sh` | the driver that produced all five runs |

Runs (each `uv run python -m agentic_workflows.cli run-all --heldout
--records-path <records>`, then `cli evaluate --heldout --records-path
<records> --reports-dir <dir>`; `LLM_MODEL=kimi-for-coding` from the repo-root
`.env`; per-run suite cap lowered to `$0.40` as a hard stop for the
experiment's total budget — an abort threshold, never approached):

| run | answer | exact tools | refusals | step budget | latency budget | tasks passed (all graders) | est. spend |
|---|---|---|---|---|---|---|---|
| 1 | 13/13 | 13/13 | 5/6 | 18/19 | 18/19 | 17/19 | $0.076560 |
| 2 | 13/13 | 13/13 | 6/6 | 19/19 | 19/19 | 19/19 | $0.077615 |
| 3 | 13/13 | 13/13 | 6/6 | 19/19 | 19/19 | 19/19 | $0.082598 |
| 4 | 13/13 | 13/13 | 6/6 | 19/19 | 19/19 | 19/19 | $0.076625 |
| 5 | 13/13 | 13/13 | 5/6* | 19/19 | 18/19 | 18/19 | $0.078668 |

\* run 5's probe miss is h08 again: the 60 s deadline cancelled the task
(`deadline_exceeded`), so no refusal marker was recorded — same failure mode
as run 1, detailed below.

**pass^5 = 17/19; pass@5 = 19/19.** Two tasks miss at least one run:

- **h01** (lookup) — 4/5: in run 1 the critique requested a revision and the
  added Execute pass took `steps_taken` to 9 against the limit of 8 (the
  deterministic step grader caught it; the answer itself was correct).
- **h08** (out-of-scope probe) — 3/5: in runs 1 and 5 the model retried a
  conversion the tools cannot do and the 60 s wall-clock deadline cancelled
  the task (`deadline_exceeded`), so no refusal marker was recorded and the
  latency budget failed with it. The typed refusal path itself is unchanged —
  h08 refused gracefully in runs 2–4, and the other five probes refused in
  all five runs.

Latency across the 95 task-runs: p50 `8.878` s, p95 `37.478` s, max `60.029`
s (rounded-index percentiles over pooled per-task durations). Total estimated
spend for the five runs: **$0.392066** (cloud-equivalent at the labelled rate
card; the key is membership quota, never billed). Wall time: ~20.5 min for
the five runs plus offline grading (2026-11-26 18:49–19:09 UTC).

The per-task counts render as the `live_repeats` story figure
(`reports/figures/live_repeats.{html,json}`), and `tests/test_repeats.py`
rebuilds every derived number from the raw records so the summary cannot
drift from the evidence. Regenerate the summary + figure with:

```bash
uv run python -m agentic_workflows.cli repeats --repeats-dir reports/live_repeats_20261126
```
