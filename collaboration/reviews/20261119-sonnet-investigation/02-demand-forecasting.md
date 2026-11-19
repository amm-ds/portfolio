# 02 M5 demand forecasting: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- M5 full panel, 30,490 series, one scored test origin (final 28 days), 42,840-node WRMSSE: pooled LightGBM ensemble 0.6161 vs seasonal-naive 0.8929 (-31.0%); no bootstrap interval; quiet days favour the floor (66.6% vs 57.3% zero-day accuracy). Source: `projects/02-demand-forecasting/story.yaml`; metrics `projects/02-demand-forecasting/reports/metrics.json`.
- Selection used 2 origins (story roadmap "next": bootstrap intervals).
- `reports/reconciliation.json` is a toy-scale file (4 stores, 6 children, shrinkage 0.0, store MAE 24.03 before and after, incoherence 26.93 before and after). It is not a full-panel reconciled row.
- `reports/probabilistic.json` exists: target coverage 0.8, quantile-band pooled coverage 0.7274, with a split-conformal section. I did not establish which panel or level it covers; treat its scope as unverified until the owner or Kimi states it.
- Decision 12 (owner-held): no full M5 panel rerun.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | The official M5 accuracy paper is Makridakis, Spiliotis, Assimakopoulos (IJF 38(4), 1346-1364); the winning accuracy submission used LightGBM. I did not read its tables, so no top-score number is cited here. | SEC | S11 |
| G2 | Whether M5 used rolling origins is not confirmed. The earlier gap analysis said rolling origins are "the M5 standard once verified"; my search did not verify it. Rolling-origin evaluation as a general method is documented (Hyndman, `tsCV`). | GAP (M5 claim), SEC (method) | S57 |
| G3 | M5 uncertainty track uses scaled pinball loss over nine quantiles (0.005 ... 0.995), 42,840 series. The repo has quantile-band coverage but I found no committed pinball-loss/WSPL on the same hierarchy. | SEC | S12 |
| G4 | Reconciliation: conformal prediction with a reconciliation step has theory (globally smaller regions) but no M5 experiment found. Nixtla's HierarchicalForecast conformal default calibrates on in-sample fitted values, which breaks split-conformal assumptions; coverage is marginal per series. | SEC | S13, S14 |
| G5 | A 2026 preprint reports global tree forecasters degrading at the hierarchical aggregate across five panels. Directly relevant to a LightGBM pooled ensemble scored by WRMSSE; abstract-level only. | SEC | S66 |
| G6 | Full dense MinT on M5 did not finish in a 2026 Nixtla run (inherited from the 2026-11-19 gap analysis; not re-checked here). | SEC (inherited) | gap-analysis file |

## Candidate improvements
**A. Reconcile the committed test-origin forecasts only (no retraining).**
- Method: take the committed bottom-level forecasts for the final 28 days, apply bottom-up and a sparse/diagonal-weight MinT variant, score 42,840-node WRMSSE as a new row in a new output file (for example `reports/reconciled_wrmsse.json`). Needs the committed forecasts to be stored at series level; if not stored, stop (would require a rerun, which decision 12 blocks).
- Reference: https://nixtlaverse.nixtla.io/hierarchicalforecast/examples/probabilistic-reconciliation-comparison.html (S14).
- Cost: compute only, about 1-2 engineering days.
- Stop condition: forecasts not on disk, or a dense covariance step that does not fit memory (the Nixtla note suggests this is a known problem).

**B. Bootstrap interval for the WRMSSE gap, series-block resampling.**
- Method: resample series (weighted by the WRMSSE weights) and recompute the paired gap model vs floor; report percentile CI as a new file. This is the roadmap "next" item.
- Reference: method, not a paper; WRMSSE definition via S11 (SEC).
- Cost: compute only, under 1 day.
- Stop condition: CI includes zero, which is then the result to report, not a reason to retry.

**C. Rolling-origin stability check on a subset (not the full panel).**
- Method: score the same model recipe at 3-4 earlier 28-day origins on a stratified 3,000-series sample; report WRMSSE spread. This produces a new number about stability; it does not replace 0.6161.
- Reference: https://search.r-project.org/CRAN/refmans/forecast/html/tsCV.html (S57).
- Cost: compute; depends on training time per origin (unknown from committed files).
- Stop condition: more than 2 hours per origin on the laptop, or the sample cannot reproduce 0.6161-type ordering (floor beating model), which would be reported.

**D. Pinball-loss scoring and split-conformal on a held-out calibration window.**
- Method: reuse `probabilistic.json` quantiles; compute scaled pinball loss on M5's nine quantiles; calibrate a conformal width on a window disjoint from the test origin.
- Reference: S12 for the metric (SEC); https://arxiv.org/abs/2106.00170 (S25) if coverage drifts.
- Cost: compute only.
- Stop condition: coverage on the test origin outside 0.75-0.85 for a 0.80 target.

## Ranked recommendation
1. B (bootstrap CI): cheapest, closes the roadmap item, offline.
2. A (reconcile committed forecasts): medium-high; blocked if forecasts are not stored.
3. D (pinball + conformal): medium.
4. C (rolling origins on a subset): medium; cost uncertain.

## Queries used (standard, 2026-11-18)
- "M5 forecasting competition results Makridakis International Journal of Forecasting 2022 WRMSSE winners"
- "conformal prediction intervals M5 hierarchical forecasts reconciliation probabilistic"
- "rolling origin evaluation time series cross-validation Hyndman forecasting principles bootstrap WRMSSE uncertainty"
- "M5 uncertainty competition pinball loss weighted scaled pinball WSPL quantile forecasts results"
- "Makridakis M5 accuracy competition results findings conclusions 2022 abstract LightGBM top methods rolling origin not used"
