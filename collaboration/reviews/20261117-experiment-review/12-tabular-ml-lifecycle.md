# 12 · Tabular ML lifecycle (UCI bike sharing): technical review

## Verdict
Clean protocol: validation-selected champion, a frozen test window, paired bootstrap intervals at three block sizes, and an ablation grid. The main weakness is that the champion beats LightGBM by 0.2 validation MAE, which is inside noise.

## Architecture
- Candidates: seasonal naive floor, ridge, random forest, LightGBM with Optuna (50 trials), and a PyTorch MLP. Right ladder for hourly tabular demand.
- Feature selection by mutual information and a correlated-pair rule (dropped `atemp`, r = 0.987). Decided by rule, not by hand. Good.

## Results vs benchmarks and SOTA
- The floor (same hour last week) is weak. A stronger public reference for this dataset would be a tuned gradient-boosting model with lag features, which LightGBM already is. The copy should say the floor is seasonal naive, which is what it is.
- No published SOTA on this split; say so on the card.

## Metrics and statistics
- **Major.** Champion selection: MLP val MAE 34.2 vs LightGBM 34.4. Difference is 0.2 MAE with no interval on the validation difference. Either give a paired interval on validation or describe the two as tied and pick by a stated tie-break.
- Test MAE 25.4 for both. The headline "25.4 vs 83.2" is solid; the champion label is the weak part.
- Block-bootstrap sensitivity (week 38.8–73.4) is a good honesty check. Keep it.
- Ablation: early stopping is the load-bearing control. Good finding.

## Code and tests
- 7 test files. Add a test that the champion selection reads validation only.

## Visuals
- `model_comparison`, `ablation_dotplot`, and `residual_vs_fitted` are the right set. Check `residual_heatmap` has a legend.

## Copy and articles
- "The champion was chosen by validation MAE, never by test": keep, and add the tie note.
- Description should say MLP and LightGBM are statistically tied on test.

## Kimi refinement tasks
1. (major) Add a paired interval on the validation difference between MLP and LightGBM, and state the tie explicitly.
2. (major) Reframe "champion" wording if the interval includes zero, or pick by a stated secondary rule.
3. (minor) Add a validation-only selection test.
4. (minor) Confirm legend and units on `residual_heatmap`.
