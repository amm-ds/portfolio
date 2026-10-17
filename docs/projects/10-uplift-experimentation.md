# 10 · Retention Uplift & Experimentation

**Domain:** Decision Science · **Data:** Hillstrom email marketing
(MineThatData, ~64k customers, sha256-pinned from the author's site) ·
**Status:** working showcase on the standard platform

> A campaign owner who mails "most likely to convert" targets sure things —
> and wastes the budget that persuadables would repay.
> Headline: on the canonical Hillstrom benchmark, the recommended top-25%
> T-learner targeting beats random by **+$2,812 (+69%)** at equal budget,
> with the profit ranking established by paired-bootstrap CIs.
>
> [Interactive case study with figures →](https://github.com/amm-ds/portfolio/tree/main/projects/10-uplift-experimentation)

## What it shows

Campaign owners deciding who gets the next send face a counterfactual
question — who buys *because of us*? — that conversion scorers cannot
answer. This project runs the full experimentation stack that turns a
randomized campaign into an operating targeting policy. On the canonical
Hillstrom benchmark (Mens E-Mail arm vs no-email control, 42,613 customers):
DQ gates and balance checks on the pinned snapshot; the honest difference-in-means read (conversion +0.68pp,
SE 0.09pp); **CUPED** variance reduction with a strictly pre-period covariate
(measured, not assumed: 0.08% on conversion, 0.52% on visit — covariate
quality is the whole game); an **analytic power analysis** (3,063 per arm
required at alpha 0.05 / power 0.8 vs 21,306 available); and three targeting
policies — the marketing-practice **response model**, a hand-rolled **T-learner**
and **X-learner** on sklearn (5-fold cross-fitted scores, no causallib) —
judged by **Qini curves/coefficient** and by **incremental profit under a
documented campaign cost model** ($114 revenue per conversion =
`revenue_per_conversion`, measured mean converter spend — no COGS in the
snapshot; $0.01 per email) against random, treat-everyone, and no-campaign
baselines. Every policy number carries a **paired-bootstrap 95% CI** (paired
row bootstrap of the out-of-fold scores, n=1000, seeded — one shared
row-resample per replication), and a **cost sweep** locates the break-even
send cost where targeted mail beats mailing everyone.

## Key results (out-of-fold, seed 42)

How to read this table: Qini is the curve area above random in conversion
units (higher is better); profit is expected incremental profit from mailing
the top 25% by score under the cost model; Δ vs random is at the same 25%
budget, with 95% CIs from a paired row bootstrap.

| policy | Qini [95% CI] | profit @ 25% budget [95% CI] | Δ vs random |
|---|---|---|---|
| response model | 13.01 [1.83, 24.36] | $4,881 [$2,246, $7,386] | +$856 |
| **T-learner (recommended)** | **12.03 [0.77, 24.39]** | **$6,838 [$4,430, $9,370]** | **+$2,812** |
| X-learner | 5.90 [−5.45, 17.48] | $4,564 [$2,150, $7,306] | +$539 |
| random | 0.0 | $4,026 | — |
| treat-everyone | 0.0 | — (full-mail $16,103) | — |

- Headline economics: at $0.01/email, **mail-everyone is the profit maximum
  ($16,103)**. The recommended top-25% T-learner policy's value is
  **concentration**: **+$2,812 (+69%) vs random at the same budget** (~61 of
  ~145 incremental conversions from 10,653 emails).
- Ranking verdict, with intervals: the response model posts the highest Qini
  area but the lowest budget profit; the paired Qini-difference CI
  (response − T) of [−8.18, 9.52] **spans zero — the curve-area ranking is
  NOT established**, while the paired profit-difference CI [−$3,617, −$48]
  is entirely below zero — **T-learner's profit advantage IS established**.
  Policy is chosen on the money; the curve explains why.
- Cost sensitivity: the profit-maximizing fraction drops below full-mail by
  ≈$0.20/email; above ≈$0.30/email (analytic break-even c\* ≈ $0.2999) the
  top-25% policy beats mail-everyone — $1,618 vs −$4,777 at $0.50, the
  list-wear regime where targeting is the difference between profit and loss.
- CUPED: ATE unchanged (+0.00680 vs +0.00681) — unbiased by construction;
  conversion variance reduction is only 0.08% because prior spend barely
  predicts a ~1% event. Predicting conversions ≠ changing them — the same
  lesson as Project 05's fairness finding.
- 14/14 DQ checks on the pinned snapshot; full pipeline ~30 s, deterministic.

## Artifacts

- Figures: one `.html` + `.json` per figure id in `reports/figures/` (served
  to the showcase app; ids referenced from `story.yaml`)
- Metrics: `reports/metrics.json` (policy ladder + `_meta.cuped/power/ci/
  cost_sensitivity/deciles`)
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
