# DESIGN — Retention Uplift & Experimentation

## Requirements

- Turn a randomized email campaign into an operating decision: who should
  receive the next wave, and what is that worth in money — not in clicks.
- Show the full experimentation stack on one canonical public benchmark:
  balance checks → A/B read → CUPED variance reduction → power analysis →
  uplift modeling (vs the response-modeling practice it replaces) → Qini and
  profit evaluation → a budget-constrained targeting policy.
- Fully CI-runnable: no LLM, no network in tests, deterministic under
  `seed: 42`, end-to-end in minutes.

## Options considered

| Option | Verdict | Why |
|---|---|---|
| causallib / causalml for T/X-learners | Rejected | Extra deps (causallib pulls statsmodels) for ~80 lines of code; hand-rolling on sklearn keeps the platform dependency-light and the method auditable line-by-line. |
| Causal forests (grf / econml DML) | Deferred | Stronger non-parametrics, but heavyweight deps and weaker interpretability for a showcase; noted in roadmap as forward work. |
| In-sample uplift scores | Rejected | Meta-learners overfit; Qini on training rows flatters every model. 5-fold cross-fitting gives honest out-of-fold scores. |
| Multi-arm (Mens + Womens vs control) | Rejected for the primary read | A two-arm treatment keeps every estimand unambiguous; the Womens arm is retained in EDA and could back a per-customer channel choice later. **Delivered 2026-10-22 as a secondary read** (`multiarm.py`): per-arm cross-fitted T-learners + a best-arm policy, evaluated model-estimated; the two-arm read stays primary and unchanged. |
| Qini vs AUUC (uplift ROC) | Qini | Qini counts incremental conversions directly (money-relevant units); AUUC is rate-based and needs careful tie handling at this base rate (~0.9%). |
| Normalized Qini (Radcliffe Q) | Rejected for the headline | Requires a "perfect model" curve definition that is unstable at rare-binary outcomes; the unnormalized coefficient (conversions × fraction) plus the profit frontier is the decision-relevant read. |
| scipy for power analysis | Rejected | `statistics.NormalDist.inv_cdf` gives z-quantiles in the stdlib; one less dependency for a closed-form formula. |

## Decisions

1. **Primary outcome = conversion.** Visit is the arm-sensitive metric in
   Hillstrom (~15% base vs 0.9%), but money attaches to conversion; spend
   secondary. The honest finding (visits move in both arms — 10.6% control to
   15.1% Womens / 18.3% Mens; conversions move mainly in the Mens arm, 0.57%
   to 1.25%) is a feature, not a bug — it is the classic uplift lesson.
2. **CUPED covariate = `log_history`** (log1p of prior-year spend). It is
   strictly pre-treatment and correlates with purchase propensity; the demo
   measures exactly how much variance it removes.
3. **Base learners: HistGradientBoosting** (classifier/regressor) inside a
   one-hot `ColumnTransformer`, single-threaded fits
   (`threadpool_limits(1)` — OpenMP oversubscription slows HistGB ~200x).
4. **X-learner combination**: `tau = g(x)*tau0(x) + (1-g(x))*tau1(x)` with a
   regularized logistic propensity `g`, clipped to [0.05, 0.95].
5. **Cost model** (all values in `params.yaml`, documented here):
   `revenue_per_conversion = $114` is the measured mean spend among converters
   in the snapshot — i.e. **revenue** per incremental conversion, not margin:
   the snapshot exposes no COGS, so profit here is revenue minus the email
   send cost alone (a true engagement would net out COGS and subtract
   fulfillment). `cost_per_email = $0.01` (marginal ESP send cost).
   `profit(f) = inc(f)·revenue − mailed(f)·cost`.
6. **Qini slice convention**: a top-f slice with no control rows counts its
   treated conversions as fully incremental; with no treated rows it
   contributes 0. At f=1 the curve ends at `n_t·(p_t − p_c)`.
7. **Recommended policy = argmax profit at the policy budget** (default 25%),
   not argmax Qini: the policy is chosen on the money it makes, the Qini
   curve is the diagnostic that explains why. Model-vs-model statements about
   the Qini ranking carry a paired-bootstrap CI on the difference; when that
   interval spans zero the ranking is reported as not established.
8. **Uncertainty = paired row bootstrap** over the out-of-fold scores
   (`bootstrap_reps = 1000`, seeded `seed + 999`): one shared row-resample per
   replication across all policies, so per-policy Qini/profit percentile CIs
   and every policy-pair difference are paired on identical resamples.
9. **Cost sensitivity** is a first-class read: for a `cost_grid` sweep of
   `cost_per_email`, the profit-maximizing targeting fraction of the
   recommended policy is recomputed against the mail-everyone profit, plus the
   analytic break-even send cost at the policy budget,
   `c* = revenue·(inc(1) − inc(budget)) / (N·(1 − budget))`.
10. **Multi-treatment uplift is a secondary, model-estimated read**
    (2026-10-22). Each arm is scored against the shared control with a
    cross-fitted T-learner; the arm matching `treatment_segment` reuses the
    binary run's seed stream, so its scores reproduce the committed T-learner
    exactly (continuity by construction). The best-arm policy recommends
    argmax(uplift_mens, uplift_womens, 0) per customer ("none" on ties or
    non-positive scores). Because no randomized assignment realizes the
    recommended arm mix, all policy-level multi-arm numbers are
    model-estimated (summed predicted uplift); only per-arm Qini/A-B contrasts
    on the randomized pairs are empirical. Predicted magnitudes run hot
    (~2×, see the decile check), so multi-arm dollar levels are planning
    numbers for ranking policies; the bootstrap resamples rows, not models.

## Cost model rationale

Email is nearly free relative to a conversion's revenue, so under a response
model nearly everyone looks worth mailing — and at these prices mail-everyone
is the profit maximum even at random ($16,103 vs the top-25% policy's $6,838
under this cost model): the frontier says so honestly. The uplift read changes
the sign for some segments (sure things would convert anyway; some customers
are actively annoyed), and the uplift model's value at these prices is
**concentration** — the top-25% policy buys ~68% more conversions for the same
number of emails, and it overtakes mail-everyone on profit once sends cost
more than the analytic break-even (≈$0.30/email at a 25% budget). The profit
frontier, not an accuracy metric, is where that shows up — hence the
revenue/cost pair is a first-class config surface, swept by `cost_grid`.

## Changelog

- 2026-10-22 — multi-treatment upgrade (secondary read): three-arm frame
  (`hillstrom_multi.parquet`) with per-arm assignment indicators; per-arm
  cross-fitted T-learner scores (`uplift_mens`, `uplift_womens`) persisted to
  `scores.parquet` (new columns; existing columns and the committed two-arm
  metrics unchanged) and `scores_multi.parquet`; best-arm policy
  (argmax per customer, ties/none on non-positive) with model-estimated profit
  frontier + paired bootstrap (seed `seed + 1999`); per-arm empirical Qini on
  the randomized pairs; recommended-arm distribution; best-arm break-even vs
  mail-everyone-mens (≈$0.31/email); multivariate CUPED read adding `recency`
  alongside `log_history` (additive `_meta.cuped_multivariate`; the univariate
  read keeps its keys/values). New figures: `qini_per_arm`,
  `profit_frontier_multi_arm`, `recommended_arm_distribution`.
- 2026-10-16 — audit pass 2: bootstrap CIs (paired row resampling, n=1000,
  seeded) on per-policy Qini + profit-at-budget and on policy-pair
  differences; Qini figure bands; cost-sensitivity sweep with mail-everyone
  break-even; `margin_per_conversion` relabeled `revenue_per_conversion`
  ($114 is mean spend among converters — revenue, not margin; COGS not in the
  snapshot); headline restated to lead with mail-everyone as the profit max
  at current costs and the top-25% policy's value as concentration.
- 2026-10-16 — initial design: two-arm Hillstrom read, hand-rolled T/X on
  sklearn, CUPED + power + Qini + profit, cross-fitted OOF scoring.
