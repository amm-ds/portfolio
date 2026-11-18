# 02 · Demand forecasting (M5): technical review

## Verdict
The best-specified forecasting experiment in the set: multi-origin protocol, a single scored-once test origin, seeded fits, and volume classes computed on history only. Two things block it from being presented well today: the live page does not load its metrics, and two selection origins with no bootstrap interval bound the headline.

## Architecture
- Full M5 panel (30,490 series, 42,840 WRMSSE nodes). Candidate ladder: seasonal naive, global LightGBM, Tweedie twin, pooled LightGBM by store, store×category, and department, AutoETS, and a convex ensemble fit only on selection origins. Sound.
- Protocol `m5_full_v1` keeps the test origin unread at fit and selection time. This is the key rigour point and it is stated clearly.
- The live demo payload is sliced from the raw panel and joins to committed forecasts with zero drift. Good reproducibility design.

## Results vs benchmarks and SOTA
- The competition's public winning solutions reported WRMSSE near 0.5 on the private leaderboard (**verify** against the competition writeup and the exact nodes used).
- The headline 0.6161 is on a single test origin (the competition window) and compares to seasonal naive 0.8929. That is a useful internal ladder but not a SOTA claim. The card should say so.
- A strong commonly cited baseline is a global LightGBM with hierarchical reconciliation. The reconciliation artifact exists; surface its number next to the ensemble.

## Metrics and statistics
- WRMSSE is the official metric. Use it consistently in all copy.
- Two selection origins and one test origin: the copy already says no bootstrap bound exists. Keep that caveat next to the headline, not only in the README.
- Interval: the member envelope is explicitly not a calibrated interval. The card says so. Good.
- Check that the 31.0% reduction is computed from unrounded values: (0.6161 − 0.8929) / 0.8929 = −31.0%. Consistent.

## Code and tests
- 30 test files. Confirm a test asserts that no test-origin column is read during selection. If it exists, name it on the card; if not, add one. This is the single most valuable test in the repo.

## Visuals
- `m5_full_sample_series`: three panels, height 300 × 3. Layout puts history (`d-55`…`d0`) and forecast dates on one categorical axis. Likely cause of the empty tail. Confirm in browser (see figure-review handoff).
- Prod page currently shows "Metrics could not be loaded" for this project. Fix in `collaboration/designs/20261117-metrics-guard-fix/`.

## Copy and articles
- Short copy is accurate and states the limits. Keep it.
- README is 241 lines and DESIGN.md is 1,182 lines. The design doc is the real case study; consider linking it from the card as the methods record.

## Kimi refinement tasks
1. (blocker, prod) Ship the metrics-guard fix; re-verify the page on prod.
2. (major) Add reconciled global LightGBM to the headline table next to the ensemble, with the same origin.
3. (major) Add or confirm a test that the selection path never reads the test origin.
4. (minor) Fix the `m5_full_sample_series` axis per the figure-review handoff.
5. (minor) Cite the M5 competition writeup for any SOTA sentence (**verify**).
