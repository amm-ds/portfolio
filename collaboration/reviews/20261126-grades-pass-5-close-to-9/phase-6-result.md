# Phase 6 result — full verification sweep

Date: 2026-11-27. Branch: `wave8-articles-truthfulness-2026-11-25`.
Scope: the full gate list from `08-kimi-closeout-fixes-revised.md`, run once
after all closeout edits (13 parity disclosure `935d34ed`, mypy fix
`e5d61f13`, phase-7 table wording).

## Pre-edit baseline (batch runs during the pass)

- Lint/type/script gates: all exit 0 except an initial repo-wide mypy
  failure on `projects/01-rag-agent/scripts/grade_final_v4_rerun.py`
  (unannotated mixed-type dict + name collision), fixed and committed as
  `e5d61f13`; mypy re-run exit 0.
- Web: npm test / lint / build all exit 0 (771 tests).
- pytest per suite (pre-closeout-edit baseline, machine under load):
  01: 190 passed · 02: 214 passed · 03: 120 · 04: 92 · 05: 69 · 06: 176 ·
  07: 67 · 08: 18 · **09: 2 failed, 105 passed** · 10: 71 · 11: 47 ·
  12: 44 · 13: 36 · 15: 36 · scripts/tests: 32 · libs/portfolio-core: 131 ·
  apps/showcase-api: 103.

## Known failure, recorded not hidden: 09 timing tests

`tests/test_suite_budget.py::TestSuiteBudget::test_task_wall_clock_deadline_is_enforced`
and
`tests/test_workflow.py::TestTerminalOutcomes::test_deadline_cancels_model_call_and_returns_terminal_result`
fail on this host (deterministic 5/5 in isolation right now; they passed in
E7's run on 2026-11-26 with identical 09 code).

Characterization (probe run): the tests set `deadline_s=0.01` and assert the
slow model responder is cancelled. On the current host the 10 ms deadline
expires during graph setup — before the responder task starts — so the
cancellation flag stays False while the product behavior is correct:
`status='deadline_exceeded'` at every probed deadline (0.01/0.05/0.1/0.5 s),
with cancellation propagating at ≥ 0.05 s. This is a test-design fragility
(deadline below graph-setup time under load), not a product regression and
not caused by pass-4/5 changes (no 09 src/test edits since E7's green run;
the docs-handoff commit touched only story.yaml copy).

Not fixed here: the closeout scope is copy/docs + one script commit, and a
test change is a code path. Recommended follow-up (needs owner approval): in
the two tests, raise the deadline to ~0.25 s or assert on the terminal
result instead of cancellation propagation.

## Row checks (step 4 of the closeout) — all verified against artifacts

| row | check | result |
|---|---|---|
| 01 | `budget_terminated` count, `reports/final_v4_rerun/question_traces_heldout.json` vs committed `final_v3_e2e/question_traces_heldout.json` | **24 vs 4 confirmed** |
| 04 | `llm_cascade_paired_ci.json` | CI [−0.0081, +0.0060], McNemar p = 1.0 — matches copy |
| 05 | `repeated_splits.json` summary | median −391.5, p2.5 −438.6, p97.5 −340.4 — copy's −$392 [−$439, −$340] ✓ |
| 06 | `gap_pct.json` alns trace | 5 values < −0.005 — title's "5 runs undercut" ✓ |
| 09 | 17/19 surfaces | present in story.yaml (×3), docs page (×3), root README, docs index ✓ |
| 10 | `git show 0c01c45d:…/metrics.json` `_meta.ci` vs current `analysis.ci` | deep-equal — bit-identical ✓ |
| 11 | three figure titles | finding titles present ✓ |
| 13 | p50 source | `metrics.json → serving.native.concurrency.c1.p50_s` = 0.001968 s → "2.0 ms" holds (the ~54 ms values are the batch-endpoint cells, a different endpoint) ✓ |
| 15 | diagram status | 4 auto specs + `pricingPipeline.ts` registered; fence gate 71 fences / 0 unresolved; browser check stays pending with the orchestrator ✓ |

No row mismatches; no row-fix commits were needed.

## Final sweep (post-edit, full list) — exit codes

Run on 2026-11-27 after all closeout edits (steps 1–4). One failure found
and fixed during the sweep; final state all zero.

First post-edit sweep:
- `check_short_copy --check`: **exit 1** — my 13 docs-opening rewrite broke
  the short_version mirror. Recorded, fixed (short_version itself updated to
  the honest gate wording on all four surfaces, `f88b259d`), re-run: exit 0.
- everything else exit 0, including **pytest projects/09-agentic-workflows:
  exit 0** — the two timing tests passed on the quieter machine, confirming
  the load-race characterization above.

Final exit codes (after the short_version fix; copy-affected gates re-run,
full pytest sweep from the same post-edit tree):

```
ruff check: 0
ruff format --check: 0
mypy libs projects apps: 0
lint_story_language: 0
check_short_copy --check: 0
gen_static_registry --check: 0
gen_story_short --check: 0
gen_route_manifest --check: 0
check_headline_numbers: 0
check_docs: 0
check_demo_contract: 0
check_diagram_fences: 0
check_figure_axes: 0
check_figure_budget: 0
mkdocs build --strict: 0
git diff --check: 0
npm test: 0
npm run lint: 0
npm run build: 0
pytest projects/01-rag-agent: 0   (190 passed)
pytest projects/02-demand-forecasting: 0   (214)
pytest projects/03-anomaly-detection: 0   (120)
pytest projects/04-nlp-classification: 0   (92)
pytest projects/05-ml-pipeline-churn: 0   (69)
pytest projects/06-routing-optimization: 0   (176)
pytest projects/07-open-data-mobility: 0   (67)
pytest projects/08-inference-serving: 0   (18)
pytest projects/09-agentic-workflows: 0   (107; the 2 timing tests pass on a quiet host — see above)
pytest projects/10-uplift-experimentation: 0   (71)
pytest projects/11-data-engineering: 0   (47)
pytest projects/12-tabular-ml-lifecycle: 0   (44)
pytest projects/13-model-serving: 0   (36)
pytest projects/15-dynamic-pricing-rl: 0   (36)
pytest scripts/tests: 0   (32)
pytest libs/portfolio-core: 0   (131)
pytest apps/showcase-api: 0   (103)
```

