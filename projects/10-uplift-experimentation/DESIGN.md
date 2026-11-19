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
| Causal forests (grf / econml DML) | Out of scope (library form) | The 2026-11-19 single-protocol comparison used a hand-rolled cross-fitted DR-learner forest on sklearn only (no new dependency); see `reports/single_protocol/`. A library causal forest (grf/econml) stays out of scope: heavyweight deps, weaker interpretability for a showcase. |
| In-sample uplift scores | Rejected | Meta-learners overfit; Qini on training rows flatters every model. 5-fold cross-fitting gives honest out-of-fold scores. |
| Multi-arm (Mens + Womens vs control) | Rejected for the primary read | A two-arm treatment keeps every estimand unambiguous. The secondary read now separates observed-outcome DR/IPW policy value (`policy_value.py`) from model-estimated planning (`multiarm.py`); the two-arm read stays primary and unchanged. |
| Qini vs AUUC (uplift ROC) | Unnormalized Qini/AUUC | The committed coefficient is the area under the Qini curve minus the random line, in conversions × fraction. The per-arm summary labels this AUUC and keeps the existing tie handling and conversion-relevant units. |
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
10. **Multi-treatment uplift is secondary and has two separate layers.** Each
    arm is scored against the shared control with a cross-fitted T-learner; the
    arm matching `treatment_segment` reuses the binary seed stream and reproduces
    the committed T-learner exactly. The best-arm policy recommends
    argmax(uplift_mens, uplift_womens, 0) per customer ("none" on ties or
    non-positive scores). The `multi_arm.policies` curves remain model-estimated
    planning (summed predicted uplift), with hot magnitudes (~2× in the decile
    check); per-arm Qini/A-B contrasts use the randomized pairs.
11. **Observed multi-arm policy value uses cross-fitted DR/IPW.** Arm-specific
    outcome models produce five-fold out-of-fold `mu_mens`, `mu_womens`, and
    `mu_control`; known randomization supplies propensity 1/3 per arm. DR adds
    the observed-arm residual correction to the policy-weighted outcome mean;
    IPW uses the weighted observed outcome alone. Best-arm and single-arm are
    deterministic top-25% rules, while random targeting is a stochastic policy
    with 25% assignment probability. One shared row bootstrap (seed + 2999)
    gives paired percentile CIs for every policy difference. Models and policy
    rules stay fixed during resampling, so these intervals omit refit variance.

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

- 2026-11-16 — added five-fold out-of-fold arm outcome models and observed-
  outcome multi-arm DR/IPW policy values with paired 1,000-row-bootstrap CIs
  (seed + 2999). Best-arm beats stochastic random on DR profit by $6,990
  [$1,107, $13,282], but its difference from single-arm Mens spans zero
  [−$7,702, $1,965]. Replaced the duplicated per-arm/binary curve overlay with
  per-arm AUUC bars and intervals; non-finite metrics now serialize as JSON null.
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
