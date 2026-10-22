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
prepare   fetch Hillstrom (sha256-pinned) → DQ gates → two-arm frame (+ three-arm
          frame for the multi-arm read) + EDA
train     5-fold cross-fitting → out-of-fold scores per policy:
          response model | T-learner | X-learner | per-arm T-learners
          (uplift_mens, uplift_womens vs the shared control)
evaluate  Qini coefficients, profit frontier, CUPED, power analysis, policy
          + multi-arm best-arm policy (model-estimated), per-arm Qini
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
**0.52%**. Adding `recency` as a second covariate (multivariate read,
`_meta.cuped_multivariate`) moves conversion only to 0.12% and visit to
**0.95%** — recency roughly doubles the (still small) visit read. CUPED is
exactly as good as its covariate; covariate selection is the design decision.

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

The recommendation is anchored against both non-model baselines on the same
paired bootstrap (T-learner minus comparator): vs random targeting at the
25% budget **+$2,812, 95% CI [+$718, +$4,767]** — the concentration
advantage is established; vs mail-everyone at $0.01/email **−$9,265, 95% CI
[−$13,125, −$5,808]** — entirely below zero, consistent with the headline:
at these prices mailing everyone is the profit maximum, and the model's
value is efficiency, not raw profit.

Qini area and profit-at-budget disagree for the response model (highest
area, lowest budget profit): the policy is chosen on the money, the curve
explains why.

## Multi-arm read (three-arm frame, model-estimated — new capability)

The experiment is upgraded to a multi-treatment read while the two-arm results
above stay the primary, committed comparison. Each arm is scored against the
shared No E-Mail control with a cross-fitted T-learner (`uplift_mens`,
`uplift_womens`; the Mens-arm fit reuses the binary run's seed stream, so its
per-arm scores reproduce the committed T-learner exactly). A **best-arm
policy** then recommends, per customer, the arm with the highest estimated
uplift — no send when both scores are ≤ 0 or tied.

Because no randomized assignment realizes the recommended arm mix, every
policy-level number here is **model-estimated** (incremental conversions =
summed predicted uplift over the targeted set — planning numbers, not
counterfactual claims; predicted magnitudes run ~2× hot per the decile check,
so use the levels to rank policies, not to forecast revenue). Only the
per-arm Qini contrasts below are empirical causal reads.

**Per-arm Qini** (randomized arm-vs-control pairs; 95% CIs from the paired
bootstrap, n=1000, seeded):

| arm | Qini [95% CI] | incremental conversions @ full send |
|---|---|---|
| Mens (per-arm = committed binary T-learner) | 12.03 [−0.47, 24.21] | 145.0 |
| Womens | 3.37 [−6.78, 13.75] — spans zero, not established | 66.5 |
| binary T-learner (two-arm, committed) | 12.03 | 145.0 |

The Womens arm's conversion lift is small and its ranking signal is not
established — consistent with the EDA read (0.88% vs 0.57% conversions).

**Recommended-arm distribution** (argmax per customer): Mens 76.0% /
Womens 20.2% / none 3.8%.

**Policy ladder** (model-estimated profit, $114 revenue / $0.01 per email;
95% CIs from a paired row bootstrap of the per-arm scores, n=1000,
seed 2041):

| policy | Qini (model-est.) | profit @ 25% budget [95% CI] |
|---|---|---|
| **best-arm** | 121.20 | **$35,514 [$35,060, $35,973]** |
| single-arm (Mens only) | 131.73 | $29,487 [$29,158, $29,800] |
| random | 0.0 | $16,563 [$16,429, $16,699] |
| mail-everyone-mens | 0.0 | — (full-mail $49,819) |
| mail-everyone-womens | 0.0 | — (full-mail $21,287) |

Paired differences (best-arm minus comparator) exclude zero across the board:
vs single-arm **[+$5,742, +$6,347]**, vs random **[+$18,619, +$19,269]**.
Break-even vs mail-everyone-mens: the best-arm policy overtakes full mailing
above **≈$0.31/email** — essentially the same fatigue threshold as the
two-arm read (≈$0.30). The model-estimated Qini area ranks single-arm above
best-arm (paired diff [−12.48, −8.63]) while the budget profit ranks
best-arm higher — same lesson as the two-arm ladder: Qini explains, profit
decides. Caveat: these intervals resample rows, not models; within-model
precision only (the two-arm ranking verdict shows how wide Qini gets across
refits). Full numbers in `reports/metrics.json` under `multi_arm`.

**The honest caveat:** predicting conversions ≠ changing them — same lesson
as Project 05's fairness finding on the retention side. The decile check
(`uplift_by_decile`) shows predicted ordering only roughly tracking the
empirical arm contrast; at a ~1% conversion base, per-decile empirical uplift
is noisy, and the X-learner's second stage adds variance without signal here
(near-constant propensity, strong overlap).

## Artifacts

- Figures (`reports/figures/`, `.html` + `.json`): `eda_segment_profile`,
  `qini_curves` (with 95% bootstrap bands), `uplift_by_decile`,
  `profit_frontier`, `cost_sensitivity`, `cuped_variance`, plus the multi-arm
  set: `qini_per_arm`, `profit_frontier_multi_arm`,
  `recommended_arm_distribution`
- Metrics: `reports/metrics.json` (policy ladder + `_meta.cuped/power/deciles`
  + `_meta.ci` bootstrap intervals and `_meta.cost_sensitivity` sweep +
  `_meta.cuped_multivariate`; the multi-arm read lives in the top-level
  `multi_arm` block)
- Report: `reports/report.html` · Segment summary: `reports/segment_summary.json`
- Scores: `data/scores.parquet` (two-arm + per-arm uplift columns) ·
  `data/scores_multi.parquet` (three-arm scored frame)
- Dataset identity: `data/dataset_contract.json` ·
  [dataset card](../../docs/data-registry/hillstrom.md)

## Reproduce

```bash
uv sync --all-packages --dev
uv run python -m uplift_experimentation.cli all
```

Deterministic under `seed: 42`; tests are offline (fixture slices, no
network).
