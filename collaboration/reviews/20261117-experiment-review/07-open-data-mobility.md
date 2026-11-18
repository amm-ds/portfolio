# 07 · Open data mobility (NYC taxi demand): technical review

## Verdict
Strong holdout discipline: a Q4 test window, validation-based selection, and coverage reported per borough. One rounding inconsistency and one band-coverage caveat to fix before it is presented as final.

## Architecture
- Next-hour zone demand from 41.2M real trips and public weather. Persistence baseline (`naive_lag24`) is the right floor for hourly demand.
- Served model is `gbm_tuned`, chosen on validation MAE. Challengers (XGBoost, LightGBM) score lower on the test window but lose on validation. The copy explains this, and it is the correct rule.
- Torch-free subprocess for challengers to avoid an OpenMP conflict on macOS: a real engineering fix, worth a sentence on the card.

## Results vs benchmarks and SOTA
- Reductions versus persistence are reported. A stronger public reference for hourly taxi demand is a seasonal model with weather covariates, or a global deep model (**verify** the literature before citing). The card should say the GBM is compared against persistence only.
- `temporal_net_tuned` has the lowest test MAE (5.178) among neural models, but it does not win; the card should explain why the GBM is preferred (fewer parameters, lower RMSE, validation choice).

## Metrics and statistics
- **Rounding.** Table: gbm_tuned MAE 4.676 vs naive 6.517 gives −28.2%, and the table reports −28.3%. Confirm which unrounded values the −28.3% uses, and make the copy match the table.
- 90% band coverage 90.8% is good, but borough coverage ranges from 84.7% (no-borough bucket) to 98.5% (Staten Island). The headline should say coverage holds overall and name the outlier groups.
- MAPE is secondary; the copy already explains zero-demand instability. Good.

## Code and tests
- 15 test files. Confirm a test that validation selection, not test MAE, picks the served model.

## Visuals
- `conformal_coverage` should show the per-borough bars with the 90% target line. Check it does.
- `zone_residual_map` is useful for the no-borough finding.

## Copy and articles
- short_version: "28.3% below same-hour-yesterday (4.68 vs 6.52 MAE)" is consistent with the table only after the rounding check above.

## Kimi refinement tasks
1. (major) Reconcile −28.2% vs −28.3% from unrounded values; fix copy or table.
2. (major) Name the no-borough and Staten Island coverage outliers in the headline sentence, not only in the table.
3. (minor) Add a test that validation, not test, selects the served model.
4. (minor) State on the card that the GBM is compared against persistence only.
