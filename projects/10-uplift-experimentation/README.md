# Retention Uplift & Experimentation

Decision-science showcase: turn a randomized email campaign into an operating
targeting policy. Everything runs on the canonical Hillstrom email benchmark —
fetched checksum-pinned, gated, modeled, and evaluated end-to-end in minutes,
fully offline in CI.

- **Problem:** who should get the next campaign email — and what is that worth?
- **Why uplift > response modeling here:** a response model ranks *likely
  buyers*; the campaign's profit comes from *persuadables* (would not convert
  untreated). Ranking by P(convert) targets sure things the campaign can't
  create, and can target customers whose purchase probability the email
  actually *lowers*.
- **Design:** [DESIGN.md](DESIGN.md) — meta-learners hand-rolled on sklearn,
  cost model rationale, Qini conventions
- **Story:** [story.yaml](story.yaml) (served at `/projects/10-uplift-experimentation/story`)

## What runs

```
prepare   fetch Hillstrom (sha256-pinned) → DQ gates → two-arm frame + EDA
train     5-fold cross-fitting → out-of-fold scores per policy:
          response model | T-learner | X-learner
evaluate  Qini coefficients, profit frontier, CUPED, power analysis, policy
```

```bash
uv run python -m uplift_experimentation.cli all     # minutes, end-to-end
uv run dvc repro                                      # the same, staged
```

## Results (Mens E-Mail vs No E-Mail, 42,613 customers, seed 42)

**Experiment read.** Conversion 1.253% (treated, n=21,307) vs 0.573%
(control, n=21,306): ATE **+0.68pp**, SE 0.09pp — a real but small effect on a
~1% base rate, exactly the regime where naive targeting wastes budget.

**CUPED** (covariate `log_history` = log1p prior-year spend, strictly
pre-treatment): the adjusted ATE is unchanged by construction (+0.00680 vs
+0.00681), but the variance story is the lesson — prior spend explains almost
none of conversion variance: **0.08% variance reduction**. On the secondary
`visit` outcome, where history is informative, the same machinery removes
**0.52%**. CUPED is exactly as good as its covariate; covariate selection is
the design decision.

**Power.** For the measured +0.68pp effect at α=0.05, power 0.8 (two-sided
two-proportion, Fleiss variance form): **3,063 customers per arm required**;
21,306 available → the experiment is comfortably overpowered — and the formula
tells you the smallest effect this audience could ever resolve (~±0.26pp).

**Uplift models** (out-of-fold Qini coefficient — area between the policy
curve and the random line, in incremental conversions — with 95% CIs from a
paired row bootstrap of the out-of-fold scores, n=1000, seed 1041):

| policy | Qini [95% CI] | profit @ 25% budget [95% CI] | Δ vs random |
|---|---|---|---|
| response model | 13.01 [1.83, 24.36] | $4,881 [$2,246, $7,386] | +$856 |
| **T-learner (recommended)** | **12.03 [0.77, 24.39]** | **$6,838 [$4,430, $9,370]** | **+$2,812** |
| X-learner | 5.90 [−5.45, 17.48] | $4,564 [$2,150, $7,306] | +$539 |
| random | 0.0 | $4,026 | — |
| treat-everyone | 0.0 | — (full-mail: $16,103) | — |

Cost model: **revenue** $114 per incremental conversion (measured mean spend
among converters — this is revenue, not margin: the snapshot exposes no COGS,
so profit here is revenue minus the email send cost alone), $0.01 per email.
`profit(f) = inc(f)·revenue − mailed(f)·cost`.

**Headline, honestly stated.** At the current $0.01 send cost, **mailing
everyone is the profit maximum** — $16,103 per wave vs $6,838 for the
top-25% policy. The uplift model's value at these prices is **efficiency, not
raw profit**: the top-25% T-learner policy delivers ~61 of the ~145 total
incremental conversions (≈42%) while mailing a quarter of the list — and vs
random targeting at the same budget it earns **+$2,812 (+69%)**: ~61
incremental conversions from 10,653 emails vs ~36 at random. The value flips
to outright selection the moment sends get expensive: the profit-maximizing
fraction drops below full-mail by ≈$0.20 per email, and the top-25% policy
**beats mail-everyone on profit above ≈$0.30 per email** (the analytic
break-even `c* = revenue·(inc(1)−inc(0.25)) / (N·0.75)`; see the
`cost_sensitivity` figure and `_meta.cost_sensitivity`). If the cost model
priced fatigue or list wear anywhere near that, targeting is the difference
between profit and loss.

**Ranking verdict, with the interval.** The response model's Qini area is
nominally higher than the T-learner's (13.01 vs 12.03), but the 95% CI on
the paired Qini difference (response − T-learner) is **[−8.18, 9.52] and
spans zero — the curve-area ranking is not established**. What is
established is the money: the paired profit-at-budget difference CI is
[−$3,617, −$48] (response − T-learner), entirely below zero. The overlapping
single-policy profit CIs ($4,881 vs $6,838) understate the separation; the
paired difference is the honest read. The recommendation stands on profit,
and the Qini ranking is stated with its interval rather than asserted.

Qini area and profit-at-budget disagree for the response model (highest
area, lowest budget profit): the policy is chosen on the money, the curve
explains why.

**The honest caveat:** predicting conversions ≠ changing them — same lesson
as Project 05's fairness finding on the retention side. The decile check
(`uplift_by_decile`) shows predicted ordering only roughly tracking the
empirical arm contrast; at a ~1% conversion base, per-decile empirical uplift
is noisy, and the X-learner's second stage adds variance without signal here
(near-constant propensity, strong overlap).

## Artifacts

- Figures (`reports/figures/`, `.html` + `.json`): `eda_segment_profile`,
  `qini_curves` (with 95% bootstrap bands), `uplift_by_decile`,
  `profit_frontier`, `cost_sensitivity`, `cuped_variance`
- Metrics: `reports/metrics.json` (policy ladder + `_meta.cuped/power/deciles`
  + `_meta.ci` bootstrap intervals and `_meta.cost_sensitivity` sweep)
- Report: `reports/report.html` · Segment summary: `reports/segment_summary.json`
- Dataset identity: `data/dataset_contract.json` ·
  [dataset card](../../docs/data-registry/hillstrom.md)

## Reproduce

```bash
uv sync --all-packages --dev
uv run python -m uplift_experimentation.cli all
```

Deterministic under `seed: 42`; tests are offline (fixture slices, no
network).
