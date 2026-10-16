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
| Multi-arm (Mens + Womens vs control) | Rejected for the primary read | A two-arm treatment keeps every estimand unambiguous; the Womens arm is retained in EDA and could back a per-customer channel choice later. |
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
   `margin_per_conversion = $114` grounded in the measured mean spend among
   converters in the snapshot (~$114 AOV; a revenue proxy for margin —
   configurable for a real engagement); `cost_per_email = $0.01`
   (marginal ESP send cost). `profit(f) = inc(f)·margin − mailed(f)·cost`.
6. **Qini slice convention**: a top-f slice with no control rows counts its
   treated conversions as fully incremental; with no treated rows it
   contributes 0. At f=1 the curve ends at `n_t·(p_t − p_c)`.
7. **Recommended policy = argmax profit at the policy budget** (default 25%),
   not argmax Qini: the policy is chosen on the money it makes, the Qini
   curve is the diagnostic that explains why.

## Cost model rationale

Email is nearly free relative to a conversion margin, so under a response
model nearly everyone looks worth mailing (and at these prices full-mail is
profitable even at random — the frontier says so honestly). The uplift read
changes the sign for some segments (sure things would convert anyway; some
customers are actively annoyed). The uplift model earns its keep when the
budget is constrained: at a 25% budget it buys ~68% more conversions for the
same number of emails. The profit frontier, not an accuracy metric, is where
that shows up — hence the margin/cost pair is a first-class config surface.

## Changelog

- 2026-10-16 — initial design: two-arm Hillstrom read, hand-rolled T/X on
  sklearn, CUPED + power + Qini + profit, cross-fitted OOF scoring.
