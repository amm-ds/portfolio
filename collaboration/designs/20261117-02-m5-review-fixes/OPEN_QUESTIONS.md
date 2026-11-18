# OPEN QUESTIONS — 02 M5 reconciled global LightGBM

Date: 2026-11-19 (overnight queue, item 4)
Executor: Kimi Code

## Blocked step

Handoff step 2: "Check `reports/reconciliation.json` for the reconciled
global LightGBM WRMSSE on the same origin. If committed, add it to the
headline table beside the ensemble."

## Finding

The only committed reconciliation artifacts are for the **UCI/local
hierarchy** (`reports/reconciliation.json`, `reports_uci/reconciliation.json`
— 4 stores / 6 children, `eval_fold: 3`). No reconciliation artifact exists
for the **M5 full panel** protocol `m5_full_v1`:

- `reports_m5_full/` contains metrics/candidates/figures but no
  reconciliation output for a global LightGBM.
- The `hierarchy` block in `reports_m5_full/metrics.json` is descriptive
  (level counts + WRMSSE levels of the hierarchy itself), not a reconciled
  forecast evaluation.
- The committed candidates are `seasonal_naive, lgbm, lgbm_tweedie,
  lgbm_pool_store, lgbm_pool_storecat, lgbm_pool_dept, auto_ets,
  convex_ensemble` — the plain global `lgbm` is committed (test-origin
  official WRMSSE 0.6601) but there is no *reconciled* variant of it on the
  test origin.

Computing it would require running hierarchical reconciliation over the full
30,490-series panel (a new pipeline run on the multi-hour M5 path), which the
overnight hard limits forbid ("No full M5 panel rerun").

## What was done instead

Steps 1 (selection-isolation test) and 3 (single-origin caveat) were
completed. This step is deferred to the owner: either approve a one-off
reconciliation evaluation of the committed global-LGBM forecasts on the test
origin (no retraining), or drop the reconciled-baseline row from the
headline table.
