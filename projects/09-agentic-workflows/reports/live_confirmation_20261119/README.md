# Held-out live confirmation (2026-11-19)

One all-hosted live run of the 19 held-out tasks against `kimi-for-coding`,
graded offline with no model calls. The published held-out rates in
`reports/metrics.json → detail.heldout` remain the legacy recorded run; this
folder is the evidence for the single live confirmation the article cites.

| file | content |
|---|---|
| `heldout_live_records.json` | the 19 live run records: 13 `ok` answer tasks, 6 `refused` probes |
| `live_grading_metrics.json` | offline grading of those records (`detail.heldout`) |

`live_grading_metrics.json → detail.heldout` reads `answer_success 1.0`
(13/13), `should_fail_pass_rate 1.0` (6/6), `step_budget 1.0` (19/19) and
`latency_budget 1.0` (19/19). Its `run_label` string is the grader's default
label, not a description of this run.

Run: `uv run python -m agentic_workflows.cli run-all --heldout --records-path <records>`
with `LLM_MODEL=kimi-for-coding` and a `$5` suite cap; grading:
`cli evaluate --heldout --records-path <records> --reports-dir <dir>`.
The run's ledger recorded 50 metered calls, 96,166 input and 11,984 output
tokens, and an estimated $0.094112 spend (cloud-equivalent estimate).

These are single runs of 19 tasks; see
`reports/metrics.json → detail.heldout.pass_rate_intervals` for the Wilson
intervals on the legacy rates.

Both files are byte-identical copies of the originals recorded with the run
(sha256 `b1561ec6…d3b3` and `d3a6fbed…c793`).
