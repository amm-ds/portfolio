# Dynamic Pricing with RL

**Working showcase; primary hypothesis failed.** A constrained `91`-day pricing
simulator calibrated from `600` M5 store-item series, four executable baselines,
a fluid upper bound, and a masked `MaskablePPO` policy with a custom history
encoder. The final test and stress sets were pre-registered and evaluated once.

- Problem: can a learned pricing policy beat the best tuned rule without ever
  breaking price-ladder, cooldown, or inventory constraints?
- Design: [DESIGN.md](DESIGN.md)
- Story: [story.yaml](story.yaml) (served at `/projects/15-dynamic-pricing-rl/story`)
- Full report: [reports/report.html](reports/report.html)

## Why

Dynamic pricing needs more than a high simulator score. The comparison must use
common random numbers, the comparator must be tuned before the learned policy,
and a final sealed set must remain untouched until the hypothesis is frozen.
This project makes that protocol the deliverable and reports the negative result
rather than moving the goalposts.

## Quickstart

```bash
uv sync --all-packages --dev
cd projects/15-dynamic-pricing-rl
uv run pytest -q
uv run python -m dynamic_pricing.cli figures  # presentation only; no policy evaluation
```

The committed `reports/metrics.json`, `reports/test_episodes.json`, and figures
are the sealed-run evidence. Rebuilding figures never runs a policy.

## Results

On the single sealed `1,000`-episode test set, selected seed `1` reaches mean
normalised profit **0.5120** versus **0.5217** for tuned static `B1` (`1.30×`
reference price). The pre-registered relative lift is **-1.86%**, so **P1 fails**.
The paired episode-bootstrap difference is **-0.009696**, with 95% CI
**[-0.011437, -0.007998]** (`2,000` resamples, seed `42`). **P2 passes:** every
executable policy has zero violations on every test episode.

| Policy | Mean normalised profit | 95% mean CI | Fluid-bound share | Violations |
|---|---:|---:|---:|---:|
| B0 — reference price | 0.4105 | [0.4052, 0.4160] | 77.59% | 0 |
| B1 — static 1.30× | **0.5217** | [0.5160, 0.5277] | **98.60%** | 0 |
| B2 — tuned markdown | 0.3978 | [0.3933, 0.4022] | 75.19% | 0 |
| B3 — Thompson pricing | 0.5028 | [0.4970, 0.5090] | 95.03% | 0 |
| RL — masked PPO, seed 1 | 0.5120 | [0.5065, 0.5177] | 96.76% | 0 |
| UB — relaxed fluid ceiling | 0.5291 | [0.5237, 0.5348] | 100.00% | n/a |

RL beats `B0` by `24.72%`, `B2` by `28.69%`, and `B3` by `1.82%`, but those are
secondary comparisons. Under both shifted elasticity priors, `B1` remains ahead
of RL; stress results are context, not new gates.

**Interpretation:** under the assumed Bijmolt elasticity prior and this reward,
the tuned static `1.30×` rule captures margin that PPO does not recover through
adaptive prices. Learning a policy was not enough to beat a strong, simple rule.

## Limits

- **Simulator results only.** No real retailer changed prices and no revenue was
  observed. Normalised profit is a simulation score, not a financial forecast.
- Elasticity is an assumption anchored to the Bijmolt et al. (`2005`)
  meta-analysis, **not causal price elasticity estimated from M5**. M5 calibrates
  demand scale, weekday seasonality, dispersion, and reference price.
- The model has no reference-price or substitution effects. Customers do not
  remember past prices or switch between products.
- The fluid upper bound knows elasticity and relaxes execution details; it is a
  ceiling, not a deployable policy.
- Test and stress sets are now consumed. Any changed policy or hypothesis needs
  a fresh pre-registered sealed set.

## Reproduce

The ordered development pipeline is:

```bash
uv run python -m dynamic_pricing.cli calibrate
uv run python -m dynamic_pricing.cli benchmark-env
uv run python -m dynamic_pricing.cli tune-baselines
uv run python -m dynamic_pricing.cli preregister
uv run python -m dynamic_pricing.cli train-smoke
uv run python -m dynamic_pricing.cli train
uv run python -m dynamic_pricing.cli seal-read
uv run python -m dynamic_pricing.cli figures
```

`preregister` and `train` must complete before `seal-read`. The evaluator refuses
to run when any prior `seal_read` exists. **Do not use blanket `dvc repro` to
refresh presentation artifacts:** use `dvc repro --single-item figures` or the
`figures` CLI command. Reproducing the sealed experiment from scratch requires a
new protocol version and fresh sealed specs, not deleting the access log.

The three PPO runs use `3,000,000` requested steps each and `SubprocVecEnv(8)`.
Only the validation-winning `reports/models/ppo_seed_1.zip` is retained through
DVC; the other checkpoints are deleted.

## Tests

```bash
uv run pytest --cov=src -q
```

Tests cover split disjointness and source hashes, deterministic common-random-
number demand, action masks and constraint accounting, Gymnasium compatibility,
fluid-bound dominance on zero-noise fixtures, baseline tuning, pre-registration
hashes, training/validation contracts, one-read guards, sealed artifact
integrity, and non-clipping figure ranges.

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| Calibration raises a SHA mismatch | An M5 parquet input differs from the pinned snapshot | Restore project 02's pinned files; do not edit hashes to bypass drift |
| `seal-read` refuses to start | A sealed set has already been consumed | Inspect `reports/sealed_access.json`; design a fresh protocol instead of deleting history |
| `dvc repro --single-stage figures` fails | This DVC version has no `--single-stage` option | Use `dvc repro --single-item figures` |
| Figure regeneration cannot find metrics | Sealed artifacts are not present locally | Restore the committed reports; never create placeholder metrics |

## Figures

| Figure | Interactive artifact |
|---|---|
| Profit versus baselines | [reports/figures/profit_vs_baselines.html](reports/figures/profit_vs_baselines.html) |
| Fixed-seed price traces | [reports/figures/price_traces.html](reports/figures/price_traces.html) |
| Fluid-bound share by inventory pressure | [reports/figures/bound_share_by_rho.html](reports/figures/bound_share_by_rho.html) |
| M5 calibration overview | [reports/figures/calibration_overview.html](reports/figures/calibration_overview.html) |
