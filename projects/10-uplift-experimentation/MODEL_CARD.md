# Model Card — Retention Uplift & Experimentation

## Intended use

Ranking customers for a retention/marketing campaign by their *estimated
incremental* conversion probability (uplift), evaluated against random and
response-model targeting under an explicit campaign cost model. Not for:
individual-level treatment effects (estimates are ranking scores, not
calibrated CATEs), non-randomized campaign data (the Qini read assumes the
randomized design), or outcome targets other than the trained one (conversion
primary; visit secondary).

## Data

Hillstrom email benchmark. Primary read: two-arm frame, Mens E-Mail arm
(21,307) vs No E-Mail control (21,306). Secondary multi-arm read: all three
arms (64,000 rows) with per-arm assignment indicators. Features are strictly
pre-treatment (recency, prior-year spend, merchandise flags, channel, zip,
newbie). Sha256-pinned snapshot; dataset card
`docs/data-registry/hillstrom.md`. The Womens E-Mail arm is reported in EDA
and, since the multi-arm upgrade, scored for the best-arm channel-choice read.

## Models

- **Response model** (baseline): HistGradientBoosting classifier fit on the
  treated arm only; score = P(convert | X, treated).
- **T-learner**: separate treated/control classifiers; score = mu1 − mu0.
- **X-learner**: imputed effects + propensity-weighted combination
  (g·tau0 + (1−g)·tau1), logistic propensity clipped to [0.05, 0.95].
- All scores are 5-fold **cross-fitted** (out-of-fold); evaluation never sees
  in-sample predictions.
- **Per-arm T-learners** (multi-arm read): each campaign arm vs the shared
  control, same cross-fitting; the configured treatment arm's scores
  reproduce the binary T-learner exactly (shared seed stream). The best-arm
  policy recommends argmax(uplift_mens, uplift_womens, 0) per customer.

## Metrics

Out-of-fold Qini coefficient (area between policy curve and random line),
incremental conversions, and profit at budget under revenue $114 per
conversion / $0.01 per email ($114 is mean spend among converters — revenue,
not margin; COGS is not in the snapshot). Headline: T-learner Qini 12.0,
+$2,812 profit delta vs random at 25% budget; both carry 95% paired-bootstrap
CIs in `reports/metrics.json` (`_meta.ci`). Multi-arm policy-level numbers
(`multi_arm` block) are MODEL-ESTIMATED — summed predicted uplift over the
targeted set, not observed counterfactuals; predicted magnitudes run ~2× hot
(decile check), so they rank policies rather than forecast dollars. Per-arm
Qini contrasts stay empirical (randomized pairs).

## Limits

- ~1% conversion base rate: per-decile empirical uplift is noisy; ranking
  quality is "real but modest", stated plainly in the decile figure. Qini
  point estimates are additionally unstable across model refits — the paired
  bootstrap resamples rows, not models, so CIs are within-model precision.
- The multi-arm block's policy-level numbers are model-estimated planning
  values (no randomized assignment realizes the recommended arm mix); only
  the per-arm Qini/A-B contrasts on the randomized pairs are causal reads.
  The Womens arm's conversion uplift (Qini 3.37, CI spanning zero) is not
  established.
- The X-learner underperforms the T-learner here (near-constant propensity,
  strong overlap — its second stage adds variance); that is a property of
  this regime, not a general verdict.
- The 2008 snapshot is one campaign wave of one retailer; the cost model
  parameters are engagement-specific and live in `params.yaml`.
