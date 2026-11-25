# DESIGN — Dynamic Pricing with RL

Decisions behind experiment 15, in pipeline order. The pre-registered primary
hypothesis failed; this document records the design without rewriting the target.

## 1. Calibrate a simulator, not a causal demand model

Read only project 02's SHA-256-pinned M5 parquet snapshot over
`2011-01-29`–`2016-04-24`. For each of `600` store-item series, estimate recent
mean demand, weekday shares, negative-binomial dispersion, and modal reference
price. Split by `item_id` with seed `42` into `140/30/30` train/validation/test
items so series from one item cannot cross splits.

M5 does not identify a causal price response. Elasticity therefore comes from a
truncated normal prior with mean `-2.5`, standard deviation `0.8`, and support
`[-5.0, -0.8]`, anchored to Bijmolt et al. (2005). Stress means `-1.5` and `-3.5`
probe sensitivity rather than creating new hypotheses.

## 2. Make episodes paired and constraints explicit

`PricingEnv` runs `91` days with a seven-step price ladder from `0.70×` to
`1.30×`, a seven-day cooldown, and one-step movement limits. Inventory pressure
`rho` takes values `0.7`, `1.0`, and `1.3`. Demand uses negative-binomial inverse
CDF sampling from an episode-specific uniform stream. An `EpisodeSpec` fully
determines the series, elasticity, pressure, and seed.

Common random numbers let every policy face the same uniforms for a spec.
`action_masks()` exposes legal actions to both baselines and PPO. Default mode
holds price and counts an invalid action; strict mode raises for development.
The reward includes daily margin and terminal salvage, normalised by reference
revenue so episodes with different demand scales remain comparable.

## 3. Keep a relaxed ceiling and four honest baselines

The fluid bound is a linear program with known elasticity. Daily price mixtures
sum to at most one, allowing an idle/no-sales relaxation when remaining inventory
is scarce. It relaxes executable policy details and is never a competitor.

- `B0`: hold the reference price.
- `B1`: hold one fixed ladder multiplier, tuned on `2,000` train episodes.
- `B2`: tune behind/ahead markdown thresholds on the same train episodes.
- `B3`: update a conjugate normal elasticity posterior daily and re-solve the
  remaining fluid problem, then take the best mask-valid action.

Validation over `300` episodes selects `B1` at `1.30×` as the comparator before
PPO training and before sealed specs are evaluated.

## 4. Train a masked policy with compact history features

`MaskablePPO` uses `SubprocVecEnv(8)`, selected after a `10,000`-step benchmark
against `DummyVecEnv(8)`. `HistoryEncoder` applies two one-dimensional convolution
layers (`16` channels, kernel `3`) to `14` days of price/demand history, combines
them with current scalars, and feeds separate `[64, 64]` policy and value networks.
Other PPO settings remain library defaults and are recorded in training reports.

Seeds `0`, `1`, and `2` each request `3,000,000` steps. Validation always passes
`action_masks` during prediction. Seed `1` wins with mean `0.5143695548`; only its
checkpoint is retained. No test episode participates in model selection.

## 5. Pre-register once, read once, compute verdicts in code

Before sealed evaluation, `params.yaml` fixes P1/P2/P3, comparator `B1`, metric
formulas, spec counts and hashes, paired bootstrap settings (`2,000` resamples,
seed `42`, `95%` CI), and stress protocol. The owner commits the frozen params,
calibration, and splits before the read.

`seal-read` refuses to run if any previous `seal_read` exists. One invocation
runs all policies on `1,000` test specs and `2 × 500` stress specs, in that order.
It logs one access entry per set and captures three fixed-seed price traces during
that same pass. P1 requires at least `+1.0%` relative lift over B1 and a paired-CI
lower bound above zero; P2 requires zero violations for every executable policy.

Sealed outcome: P1 fails at `-1.85846%` with an entirely negative paired interval;
P2 passes with zero violations. The threshold remains unchanged. Figure generation
reads saved artifacts only, so presentation work cannot trigger another sealed read.

## 6. Alternatives considered

- **Unmasked PPO:** rejected because post-hoc penalties would weaken the hard
  constraint claim and make invalid actions part of learning.
- **Dense-only history encoder:** viable, but the convolutional encoder tests
  whether local price/demand patterns help without a large model.
- **Bandit-only solution:** B3 supplies this alternative. It is strong enough to
  beat B0/B2 but remains below B1 on validation and test.
- **Estimate elasticity from M5 price variation:** rejected as a causal claim;
  observational price correlation is not a valid demand elasticity estimate.
- **Select the best test baseline:** rejected. B1 was locked on validation before
  the sealed read; test results cannot redefine the comparator.
- **Rerun until P1 passes:** rejected categorically. The access log is append-only
  and the sealed result stays negative.

## 7. Deliberately not built

No production pricing service, real-money deployment, customer reference-price
memory, cross-product substitution, causal elasticity identification, or hosted
training. The reusable deliverable is the constrained environment, strong rule
baselines, paired evaluation, and audit trail.

## Changelog

- **2026-11-25:** Implemented S-0 and E2-1 through E2-6; owner committed the
  frozen protocol and data inputs. Trained three PPO seeds, selected seed `1`,
  and performed the single sealed read. P1 failed and P2 passed. Generated four
  figures, the standalone report, documentation, article, and repository
  registrations without another policy evaluation.
