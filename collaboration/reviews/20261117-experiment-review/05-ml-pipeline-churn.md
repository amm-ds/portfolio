# 05 · ML pipeline churn (IBM Telco): technical review

## Verdict
The cleanest statistical hygiene in the set: frozen threshold from out-of-fold predictions, paired bootstrap intervals, calibration reported, and a synthetic track that disagrees with the real track in a stated way. Ready to present with minor fixes.

## Architecture
- Real-data track (7,043 rows, 1,409-row holdout) and synthetic track. Keeping both and reporting where they disagree is good engineering.
- Threshold is frozen from training OOF predictions and never re-read on the holdout. This is the decision that makes the cost claim credible.
- Calibration (isotonic) is part of the served policy and evaluated paired.

## Results vs benchmarks and SOTA
- ROC-AUC 0.83–0.84 is in line with published results on this dataset (**verify** the citation; typical reports are around 0.84).
- The comparator set includes contact-everyone and logistic regression, which is the right floor set.
- No gradient-boosting SOTA beyond XGBoost. Acceptable; the card should say the search budget (25 trials × 4 arms).

## Metrics and statistics
- Business cost is the decision metric. It depends on cost weights. The card must state them next to every cost number (1,035 vs 601).
- Paired bootstrap, 2,000 resamples, CI [-508, -353] for the headline: correct framing.
- Caution: ECE moves 0.028 → 0.016 on one holdout. Report it as a single-holdout measurement.
- The headline cost reduction is (601 − 1035) / 1035 = −41.9%. Consistent.

## Code and tests
- 12 test files. Check that the frozen-threshold path has a test asserting the holdout is not read during threshold choice.

## Visuals
- `business_cost_curve` and `decision_curve` directly support the claim. Mark the chosen threshold on the curve.
- `fairness_slices` is a good addition; keep its denominators visible.

## Copy and articles
- short_version is accurate and says to re-select the cutoff when costs change. Keep that sentence.

## Kimi refinement tasks
1. (major) Put the cost weights on every cost figure and in the card.
2. (major) Add a test that the holdout is not read during threshold selection.
3. (minor) Mark the chosen threshold on `business_cost_curve`.
4. (minor) Cite the churn benchmark for the AUC sentence (**verify**).
