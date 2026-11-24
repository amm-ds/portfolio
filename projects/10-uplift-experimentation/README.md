# Retention Uplift & Experimentation

Decision-science showcase: turn a randomized email campaign into an operating
targeting policy. Everything runs on the canonical Hillstrom email benchmark —
fetched checksum-pinned, gated, modeled, and evaluated end-to-end in minutes,
fully offline in CI.

- **Problem:** who should get the next campaign email, and what is that worth?
- **Why uplift > response modeling here:** a response model ranks *likely
  buyers*; the campaign's revenue minus send cost comes from *persuadables*
  (would not convert untreated). Ranking by P(convert) targets sure things the
  campaign can't create, and can target customers whose purchase probability
  the email actually *lowers*.
- **Design:** [DESIGN.md](DESIGN.md), meta-learners hand-rolled on sklearn,
  cost model rationale, Qini conventions
- **Story:** [story.yaml](story.yaml) (served at `/projects/10-uplift-experimentation/story`)

## What runs

```text
prepare   fetch Hillstrom (sha256-pinned) → DQ gates → two-arm frame (+ three-arm
          frame for the multi-arm read) + EDA
train     5-fold cross-fitting → out-of-fold scores per policy:
          response model | T-learner | X-learner | per-arm T-learners
          + Mens/Womens/control outcome nuisances for DR/IPW
evaluate  Qini coefficients, revenue-minus-send-cost frontier, CUPED, power analysis, per-arm
          AUUC + observed-outcome multi-arm DR/IPW + separate planning curves
```

```bash
uv run python -m uplift_experimentation.cli all     # minutes, end-to-end
uv run dvc repro                                      # the same, staged
```

## Results (Mens E-Mail vs No E-Mail, 42,613 customers, seed 42)

**Experiment read.** Conversion 1.253% (treated, n=21,307) vs 0.573%
(control, n=21,306): ATE **+0.68pp**, SE 0.09pp, a real but small effect on a
~1% base rate, exactly the regime where naive targeting wastes budget.

**CUPED** (covariate `log_history` = log1p prior-year spend, strictly
pre-treatment): the adjusted ATE is unchanged by construction (+0.00680 vs
+0.00681), but the variance story is the lesson, prior spend explains almost
none of conversion variance: **0.08% variance reduction**. On the secondary
`visit` outcome, where history is informative, the same machinery removes
**0.52%**. Adding `recency` as a second covariate (multivariate read,
`_meta.cuped_multivariate`) moves conversion only to 0.12% and visit to
**0.95%**: recency roughly doubles the (still small) visit read. CUPED is
exactly as good as its covariate; covariate selection is the design decision.

**Power.** For the measured +0.68pp effect at α=0.05, power 0.8 (two-sided
two-proportion, Fleiss variance form): **3,063 customers per arm required**;
21,306 available → the experiment is comfortably overpowered, and the formula
tells you the smallest effect this audience could ever resolve (~±0.26pp).

**Uplift models** (out-of-fold Qini coefficient, area between the policy
curve and the random line, in incremental conversions, with 95% CIs from a
paired row bootstrap of the out-of-fold scores, n=1000, seed 1041):

| policy | Qini [95% CI] | revenue minus send cost @ 25% budget [95% CI] | Δ vs random |
|---|---|---|---|
| response model | 13.01 [1.83, 24.36] | $4,881 [$2,246, $7,386] | +$856 |
| **T-learner (recommended)** | **12.03 [0.77, 24.39]** | **$6,838 [$4,430, $9,370]** | **+$2,812** |
| X-learner | 5.90 [−5.45, 17.48] | $4,564 [$2,150, $7,306] | +$539 |
| random | 0.0 | $4,026 | — |
| treat-everyone | 0.0 | — (full-mail: $16,103) | — |

Cost model: **revenue** $114 per incremental conversion (measured mean spend
among converters, this is revenue, not margin: the snapshot exposes no COGS,
so "revenue minus send cost" here means revenue minus the email send cost
alone), $0.01 per email.
`value(f) = inc(f)·revenue − mailed(f)·cost`.

**Headline, honestly stated.** At the current $0.01 send cost, **mailing
everyone maximizes revenue minus send cost**, $16,103 per wave vs $6,838 for
the top-25% policy. The uplift model's value at these prices is **efficiency,
not the raw maximum**: the top-25% T-learner policy delivers ~61 of the ~145
total incremental conversions (≈42%) while mailing a quarter of the list —
and vs random targeting at the same budget it earns **+$2,812 (+70%)**: ~61
incremental conversions from 10,653 emails vs ~36 at random. The value flips
to outright selection the moment sends get expensive: the value-maximizing
fraction drops below full-mail by ≈$0.20 per email, and the top-25% policy
**beats mail-everyone on revenue minus send cost above ≈$0.30 per email** (the
analytic break-even `c* = revenue·(inc(1)−inc(0.25)) / (N·0.75)`; see the
`cost_sensitivity` figure and `_meta.cost_sensitivity`). If the cost model
priced fatigue or list wear anywhere near that, targeting is the difference
between a net gain and a net loss.

**Ranking verdict, with the interval.** The response model's Qini area is
nominally higher than the T-learner's (13.01 vs 12.03), but the 95% CI on
the paired Qini difference (response − T-learner) is **[−8.18, 9.52] and
spans zero, the curve-area ranking is not established**. What is
established is the money: the paired at-budget difference CI for revenue minus
send cost is [−$3,617, −$48] (response − T-learner), entirely below zero. The
overlapping single-policy CIs ($4,881 vs $6,838) understate the separation;
the paired difference is the honest read. The recommendation stands on
revenue minus send cost, and the Qini ranking is stated with its interval
rather than asserted.

The recommendation is anchored against both non-model baselines on the same
paired bootstrap (T-learner minus comparator): vs random targeting at the
25% budget **+$2,812, 95% CI [+$718, +$4,767]**, the concentration
advantage is established; vs mail-everyone at $0.01/email **−$9,265, 95% CI
[−$13,125, −$5,808]**, entirely below zero, consistent with the headline:
at these prices mailing everyone maximizes revenue minus send cost, and the
model's value is efficiency, not the raw maximum.

Qini area and revenue minus send cost at budget disagree for the response
model (highest area, lowest budget value): the policy is chosen on the money,
the curve explains why. The selection rule is fixed in advance: the
recommended policy is the one with the highest revenue minus send cost at the
25% budget, the response model is not chosen even though its Qini is
nominally higher, because the paired Qini interval overlaps while the
at-budget money interval does not.

## Multi-arm read (observed policy value + separate planning)

The two-arm results above stay primary. Each three-arm row has out-of-fold
Mens/Womens/control outcome predictions, plus per-arm cross-fitted T-learner
uplift scores. A **best-arm policy** recommends the highest estimated uplift,
with no send when both scores are ≤0 or tied. The observed-outcome and planning
evaluations below are deliberately separate.

**Per-arm AUUC** (the unnormalized Qini coefficient on randomized
arm-vs-control pairs; paired-bootstrap 95% CIs, n=1000):

| arm | AUUC [95% CI] | incremental conversions @ full send |
|---|---|---|
| Mens (same score as the primary binary T-learner) | 12.03 [−0.47, 24.21] | 145.0 |
| Womens | 3.37 [−6.78, 13.75] — spans zero, not established | 66.5 |

**Observed-outcome policy value.** Five-fold outcome nuisances and known 1/3
assignment probabilities support cross-fitted doubly robust (DR) and IPW reads.
Best-arm and single-arm mail exactly 25%; random is stochastic, with 25% offered
the recommended arm and `none` offers reassigned to control (24.1% mailed).
Revenue minus send cost uses $114 revenue per incremental conversion and $0.01
per email.

| policy | DR revenue minus send cost [95% CI] | IPW revenue minus send cost [95% CI] |
|---|---|---|
| best-arm @25% | $17,967 [$10,881, $25,459] | $18,650 [$11,468, $26,174] |
| single-arm Mens @25% | $20,869 [$13,853, $28,247] | $20,702 [$13,862, $27,893] |
| random, stochastic | $10,977 [$8,089, $14,202] | $10,363 [$7,370, $13,526] |
| mail-everyone-Mens | $48,684 [$36,051, $62,016] | $48,950 [$35,612, $62,288] |
| mail-everyone-Womens | $21,953 [$10,680, $33,971] | $22,274 [$11,330, $33,911] |

Paired DR differences show best-arm beating random by **$6,990
[$1,107, $13,282]**, but not beating single-arm Mens: **−$2,902
[−$7,702, $1,965]** spans zero. Full Mens mailing beats best-arm by $30,718
[$19,787, $42,306] at this send cost. Thus the data support useful targeting
over random, not superiority of per-customer channel choice. Bootstrap intervals
hold the cross-fitted models and rules fixed and omit model-refit uncertainty.

**Model-estimated planning.** The original summed-predicted-uplift layer remains
available for cost/fraction simulation; it is not observed revenue minus send
cost. Predicted
magnitudes run ~2× hot per the decile check. Recommended-arm shares are Mens
76.0% / Womens 20.2% / none 3.8%.

| policy | Qini (model-est.) | planning revenue minus send cost @25% [95% CI] |
|---|---|---|
| best-arm | 121.20 | $35,514 [$35,060, $35,973] |
| single-arm (Mens only) | 131.73 | $29,487 [$29,158, $29,800] |
| random | 0.0 | $16,563 [$16,429, $16,699] |
| mail-everyone-mens | 0.0 | — (full-mail $49,819) |
| mail-everyone-womens | 0.0 | — (full-mail $21,287) |

Planning-only paired differences and the ≈$0.31 best-arm break-even must not be
read as randomized outcomes. Full numbers live under `multi_arm.policy_value`
(observed DR/IPW) and `multi_arm.policies` (planning) in `reports/metrics.json`.

**The honest caveat:** predicting conversions ≠ changing them, same lesson
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
  `_meta.cuped_multivariate`; `multi_arm.policy_value` holds observed DR/IPW and
  `multi_arm.policies` holds model-estimated planning; unavailable values are null)
- Report: `reports/report.html` · Segment summary: `reports/segment_summary.json`
- Scores: `data/scores.parquet` (two-arm + per-arm uplift columns) ·
  `data/scores_multi.parquet` (three-arm scores + out-of-fold outcome nuisances)
- Demo: `reports/demo_payload.json` (planning grids + observed DR/IPW scalars)
- Dataset identity: `data/dataset_contract.json` ·
  [dataset card](../../docs/data-registry/hillstrom.md)

## Limits

At $0.01 per email, mailing everyone beats uplift targeting (paired CI below
zero), targeting pays only when sending is costly (break-even ≈ $0.30). The
response-versus-T and per-arm AUUC rankings are not established. Multi-arm
best-arm beats random on observed DR/IPW, but its advantage over single-arm Mens
is inconclusive. Planning dollars remain model-estimated, and every row bootstrap
omits model-refit uncertainty. One 2008 campaign still needs prospective validation.

## Reproduce

```bash
uv sync --all-packages --dev
uv run python -m uplift_experimentation.cli all
```

Deterministic under `seed: 42`; tests are offline (fixture slices, no
network).

## Common errors

| symptom | cause | fix |
|---|---|---|
| `prepare` (or `cli all`) fails fetching Hillstrom | the sha256-pinned CSV downloads once from the registry source — it is not committed | run once with network (`uv run python -m uplift_experimentation.cli prepare` or `uv run dvc repro`); everything downstream, and the tests, run offline |
