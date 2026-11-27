# Model Card — Dynamic Pricing with RL

## Intended use

Simulator research only. This masked-PPO policy exists to study constrained
pricing under an explicit protocol: an item-level split, one retained seed,
one sealed evaluation, and a negative primary result (P1 fails, P2 passes).
It is **not for deployment**. No real prices were changed and no actual
revenue was measured. The useful artifact is the comparison protocol, not a
pricing service.

## Data

- Source: Walmart M5 panel, calibrated per store-item series (mean daily
  units, weekday shares, negative-binomial dispersion, reference price).
  Window: 2011-01-29 through 2016-04-24; files SHA-256 pinned.
- Split: `item_id` with seed 42 — 140 train / 30 validation / 30 test items
  (267 / 57 / 58 series). No item crosses a split.
- Price response is an assumption, not measured data: a truncated normal
  elasticity prior (mean −2.5, SD 0.8, range [−5.0, −0.8]) anchored to
  Bijmolt et al. (2005). Stress means −1.5 and −3.5 vary the assumption.
- Evaluation inputs are frozen and hashed before the single sealed read:
  1,000 test specs and 2 × 500 stress specs.

## Metrics

Sealed test (1,000 paired episodes, `reports/metrics.json`). RL masked PPO
reaches 0.5120 mean normalised profit against tuned static B1 at 0.5217:
relative lift −1.86%, paired difference −0.009696 with 95% CI
[−0.011437, −0.007998]. All executable policies have zero violations.

By slice, from `analysis.gap_by_slice` (computed by
`src/dynamic_pricing/analyse_gap_by_slice.py`, episode-unit percentile
bootstrap, 2,000 resamples, seed 42):

| Slice | RL − B1 mean gap | 95% CI | n |
|---|---:|---:|---:|
| |epsilon| ≤ 2.178 (least sensitive) | −0.0174 | [−0.0205, −0.0143] | 334 |
| 2.178 < |epsilon| ≤ 2.878 | −0.0105 | [−0.0138, −0.0073] | 333 |
| |epsilon| > 2.878 (most sensitive) | −0.0012 | [−0.0033, +0.0010] | 333 |
| rho = 0.7 | −0.0082 | [−0.0107, −0.0055] | 334 |
| rho = 1.0 | −0.0107 | [−0.0137, −0.0080] | 333 |
| rho = 1.3 | −0.0102 | [−0.0139, −0.0070] | 333 |

RL wins 35.1% of paired episodes; all 2,000 resamples keep the learner
behind, so the gap is not luck in this test. The fixed markup hurts most
where shoppers are least price-sensitive, and the learner closes the gap as
sensitivity rises.

## Limits

- **One retained seed:** only seed 1's checkpoint was kept (validation means
  0.512536 / 0.514370 / 0.514288 for seeds 0/1/2). B1 also beat RL on
  validation (0.5225 vs 0.5144, `reports/baselines_val.json` and
  `reports/ppo_val.json`), so the test loss was visible before the sealed
  read. Seed-level variance is not measured.
- **Simulator only:** elasticity is an assumption, not causal M5 elasticity;
  reference-price and substitution effects are absent — shoppers neither
  remember earlier prices nor switch products. UB is a relaxed
  known-elasticity ceiling, not an achievable service level.
- **No tuning reuse:** the consumed test and stress sets must not become
  tuning data. `reports/sealed_access.json` records exactly three ordered
  reads and the evaluator hard-fails a second invocation.
