# 03 · Anomaly detection (NAB): technical review

## Verdict
Honest framing: the copy refuses to claim unattended paging and shows no-skill baselines. The remaining work is to define each metric once and make the budgeted and raw alert counts impossible to confuse.

## Architecture
- Detectors compared on the same stream: IsolationForest with rolling residual features, a rank-average ensemble, and a frozen operating point (2% budget, 24 h cap). Reasonable.
- The frozen operating point is explicitly not chosen on the test window. Good.

## Results vs benchmarks and SOTA
- NAB has a public scoreboard with its own application-profile scoring. The README uses range-F1 and range-PR, not the NAB score. The card should say the NAB score is not reported, or report it. Otherwise readers will compare the wrong number.
- The no-skill band (16 seeds, 0.228 [0.081, 0.401]) is the right kind of comparison.

## Metrics and statistics
- Four counts appear for the same detector: 1,609 raw, 80 budgeted, 66 → 35 like-for-like, and the ensemble. The README explains each, but the headline sentence in `short_version` mixes raw and budgeted alerts in one line. Split it.
- Precision 0.553 vs no-skill 0.082 is a strong claim. Give its CI, not only the point value.
- Range-F1 values move between 0.157, 0.315, 0.388, and 0.533 across tables. Define which configuration each belongs to in every table row.

## Code and tests
- 18 test files. Confirm the range-metric implementation is tested against hand-computed examples.

## Visuals
- `range_pr` and `threshold_sweep` support the no-skill claim. Label the random band on the figure, not only in text.

## Copy and articles
- short_version is accurate but dense. Rewrite as two sentences: detector and raw alerts, then the budgeted comparison.

## Kimi refinement tasks
1. (major) Either report the NAB official score or state on the card that it is not computed, and why.
2. (major) Split `short_version` so raw and budgeted alert counts are not in one sentence.
3. (minor) Add CIs to the precision values quoted in the README.
4. (minor) Label the random band on `range_pr`.
