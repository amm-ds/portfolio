# Statistical intervals — the portfolio's conventions

One definition per method, so every card quotes uncertainty the same way.
Each experiment card keeps a one-line method note next to its numbers; this
page is the canonical reference those lines point to.

The house rule: **an interval prices one source of uncertainty — it is not
proof.** Cards say what the interval covers (sampling noise of the frozen
window, series-level heterogeneity, binomial pass-rate uncertainty) and what
it does not (model-selection variance, transfer, unmeasured covariates).

## Wilson score interval

- **Used for:** binomial pass rates (project 09 pass rates, per-grader and
  held-out; any k-of-n success count).
- **Method:** closed form, no resampling —
  (p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n), z = 1.96 for 95%.
- **Why:** handles the k = n boundary (upper bound = 1), which a normal
  approximation cannot. Single-run suites (each task executed once) get this
  — there are no resamples to bootstrap.
- **Reference implementation:** `agentic_workflows.report.wilson_interval`.

## Percentile bootstrap over instances or series

- **Used for:** a mean taken over a small population of heterogeneous units —
  56 routing instances (06: mean distance gap), 9 NAB series (03: precision at
  the frozen budget), 13 uplift customers-by-row is NOT this (see paired row).
- **Method:** resample the units with replacement, recompute the headline
  statistic per draw, take the 2.5/97.5 percentiles.
  **2,000 resamples, fixed seed (convention: seed 42).** The operating point
  itself is never re-fit.
- **Caveat stated on cards:** with 9 units the interval is wide and prices
  pooling uncertainty only — it is not a per-window confidence statement.

## Paired row bootstrap

- **Used for:** differences between two scorers on the SAME rows — uplift
  policy value (10), served-model vs floor MAE (12), champion-vs-floor cost
  (05), fresh-holdout cascade deltas (04, when predictions exist).
- **Method:** resample rows with replacement (paired: both models see the same
  resample), 2,000 resamples, seed fixed per project. Thresholds and operating
  points stay frozen; the interval isolates sampling noise.
- **Reference convention:** project 05 (`churn_pipeline.evaluate`), seed 42.

## Block (day/week) bootstrap

- **Used for:** serially dependent hourly errors (12: 24 h and 168 h blocks;
  07 sensitivity analyses).
- **Method:** resample intact blocks instead of rows; same resample count and
  seed discipline. Reported beside the hourly bootstrap as a sensitivity
  range, never as a second independent confirmation.

## Nearest-rank percentiles

- **Used for:** latency percentiles (08, 13).
- **Method:** order statistics, ceil(q·n) rank — no interpolation. Reported
  with n (requests per cell) and the repeat count (median of repeats).

## Seeded no-skill ensembles

- **Used for:** 03's random baselines (16 seeds) — a band, not a single draw.
- **Method:** run the null model under N fixed seeds; report the mean and the
  2.5/97.5 percentiles of the per-seed statistic. The champion is compared
  against the band, never against one lucky random run.

## Words the cards use

- "95% CI" with the method named in the same sentence or a footnote.
- "spans zero / excludes zero" — never "significant".
- "no measurable change" when a paired interval includes zero (04 cascade, 12
  validation tie).
- Every regenerated metrics artifact carries the provenance `_meta` stamp
  (`scripts/stamp_metrics_meta.py`) after any metrics change.
