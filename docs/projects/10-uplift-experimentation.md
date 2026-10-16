# 10 · Retention Uplift & Experimentation

**Domain:** Decision Science · **Data:** Hillstrom email marketing
(MineThatData, ~64k customers, sha256-pinned from the author's site) ·
**Status:** working showcase on the standard platform

## What it shows

The full experimentation stack that turns a randomized campaign into an
operating targeting policy. On the canonical Hillstrom benchmark (Mens E-Mail
arm vs no-email control, 42,613 customers): DQ gates and balance checks on
the pinned snapshot; the honest difference-in-means read (conversion +0.68pp,
SE 0.09pp); **CUPED** variance reduction with a strictly pre-period covariate
(measured, not assumed: 0.08% on conversion, 0.52% on visit — covariate
quality is the whole game); an **analytic power analysis** (3,063 per arm
required at alpha 0.05 / power 0.8 vs 21,306 available); and three targeting
policies — the marketing-practice **response model**, a hand-rolled **T-learner**
and **X-learner** on sklearn (5-fold cross-fitted scores, no causallib) —
judged by **Qini curves/coefficient** and by **incremental profit under a
documented campaign cost model** ($114 margin per conversion = measured mean
converter spend, $0.01 per email) against random, treat-everyone, and
no-campaign baselines.

## Key results (out-of-fold, seed 42)

| policy | Qini coefficient | profit @ 25% budget | Δ vs random |
|---|---|---|---|
| response model | 13.01 | $4,881 | +$856 |
| **T-learner (recommended)** | **12.03** | **$6,838** | **+$2,812** |
| X-learner | 5.90 | $4,564 | +$539 |
| random | 0.0 | $4,026 | — |
| treat-everyone | 0.0 | — (full-mail $16,103) | — |

- Recommended policy: **top 25% by T-learner score — +$2,812 (+69%) vs
  random at the same budget** (~61 vs ~36 incremental conversions from
  10,653 emails).
- Qini area and budget profit disagree for the response model (highest area,
  lowest budget profit): the policy is chosen on the money, the curve
  explains why.
- CUPED: ATE unchanged (+0.00680 vs +0.00681) — unbiased by construction;
  conversion variance reduction is only 0.08% because prior spend barely
  predicts a ~1% event. Predicting conversions ≠ changing them — the same
  lesson as Project 05's fairness finding.
- 14/14 DQ checks on the pinned snapshot; full pipeline ~30 s, deterministic.

## Artifacts

- Figures: `eda_segment_profile`, `qini_curves`, `uplift_by_decile`,
  `profit_frontier`, `cuped_variance` (`.html` + `.json` for the showcase app)
- Metrics: `reports/metrics.json` (policy ladder + `_meta.cuped/power/deciles`)
  · Report: `reports/report.html` · Segments: `reports/segment_summary.json`
- Dataset identity: `data/dataset_contract.json` ·
  [dataset card](../data-registry/hillstrom.md)

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/10-uplift-experimentation/README.md) —
  results, reproduce commands, client takeaways
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/10-uplift-experimentation/DESIGN.md) —
  meta-learner options, cost-model rationale, Qini conventions, changelog
- Story: `projects/10-uplift-experimentation/story.yaml` (8 canonical sections
  + roadmap, served by the showcase API)
- Source: `projects/10-uplift-experimentation/src/uplift_experimentation/`
