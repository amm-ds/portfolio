# OPEN QUESTIONS — P2 language and roadmap pass

Raised by Kimi Code during P2 execution (2026-11-19). Every item here is an
existing-copy number that could not be reconciled against a committed artifact
under the no-number-changes constraint, or a mandated-text deviation the owner
should confirm. Nothing below was changed.

## 1. 03-anomaly-detection — `threshold_sweep` numbers unsupported

The story caption and Conclusions body say "115 flags … about 15% precision and
recall (14.8%)". The committed figure takeaway
(`projects/03-anomaly-detection/reports/figures/threshold_sweep.json`) reads
"17/120 flags hit real incidents" (17 TP / 120 flags = 14.2% precision). No
committed artifact supports 115 or 14.8%. The 17 hits do match. Left verbatim;
the C5 test-set qualifier was still applied.

## 2. 06-routing-optimization — "8 published references" does not match the committed table

Existing copy (training bullet, results business summary, conclusions bullet,
`gap_pct` caption) claims ALNS undercuts 8 references. Parsing the committed
`projects/06-routing-optimization/reports/results.md` gives ALNS negative gaps
on **5** instances (R202 −1.03, R207 −3.51, R211 −3.43, RC105 −2.78,
RC202 −3.85), or 6 counting `alns_fleet` (adds RC102 −1.78; RC202 −5.79).
README/DESIGN say 8 against an older reference table. Left verbatim; kept "8"
out of the new roadmap cards (the 12.0 s CP-SAT tie card is used instead).

## 3. 09-agentic-workflows — `short_version` live claims unsupported by committed metrics

`short_version` claims "Live 2026-11-19: …6/6 refusals, 19/19 budgets". The
committed `projects/09-agentic-workflows/reports/kimi-for-coding/metrics.json`
shows `should_fail_pass_rate: 0.833` (5/6; h19 refusal 0.0) and the h19 record
still ends in a failure message; the body itself says fresh live 6/6
confirmation is pending. `short_version` was out of scope (and its numbers must
not change under P2). Flagged for the owner — this is a truth-in-copy issue, not
a style issue.

## 4. 09-agentic-workflows — "An earlier run had 8 unplanned calls" not traceable

The `tool_usage_matrix` caption sentence is not backed by any committed artifact
found (no `extra_calls` in either metrics file). Left as-is.

## 5. 13-model-serving — three unverifiable existing numbers

- "up to 15%" ONNX lead (evaluation/results/conclusions): committed medians show
  a max ONNX lead of **13.8%** at the c64 throughput cell
  (`reports/metrics.json`); ≤4% on p50 medians.
- "3.3 GB CUDA stack" (results, conclusions) and "12.8 GB earlier build"
  (results): not recorded in metrics.json, docker_run.json, docker_slim.json,
  report.html, or any figure JSON.
- `backend_comparison_slope` caption "~20%" noise threshold: not committed
  anywhere (max committed ratio gap ~4% on p50, 13.8% on throughput).

All left verbatim per the constraint.

## 6. 10-uplift-experimentation — two observations

- `reports/figures/profit_frontier.html` annotation says "$6,698 (t_learner)"
  while committed metrics and the story table say **$6,838** — inside a committed
  figure artifact, outside story.yaml edit scope. Follow-up data check needed.
- Body/captions say "+69%" while `short_version`/background say "+70%" for the
  same +$2,812 (69.86% unrounded). Both left untouched.

## 7. 12-tabular-ml-lifecycle — mandated-text deviations to confirm

- The approved card 3 title "Gap to the floor holds under block resampling." is
  8 words (guideline is 3–6); kept verbatim per "use the rewrites as written".
- The approved card 2 detail restates the headline 25.4-vs-83.2 comparison,
  overriding rule A5 (no headline restatement) — kept per the mandate.
- The TabPFN-2.5 "see research deltas" pointer has no matching committed
  artifact inside project 12; the pointer may dangle.

## 8. Numbers traced only to design docs (kept out of cards, left in body)

- 02 spike-capture values (0.845/0.839, 0.621/0.601) — committed only in
  `projects/02-demand-forecasting/DESIGN.md`, not under `reports*/`.
- 04 ECE pair 0.0360 → 0.0227 and "37% cut" — committed only in DESIGN.md and
  README.md, not under `reports/`.
- 11 "tracing made pandas's group-by look 4x slower" — appears only in
  story.yaml itself; no committed artifact records the comparison.

## Notes

- The self-check snippet in the swarm brief passed a `str` to `load_story`,
  which requires a `pathlib.Path`; every agent adapted the call and the check
  passed (`cards 5 over90 []` on all 13 projects).
- The 12-merge: to respect the 5-card cap, the two mandated foundation cards
  (pipeline + features) were merged into one shipped card; every given claim is
  kept ("Frozen test window; 26 DQ gates; sha256-pinned source; contract
  features; CI twin.").
