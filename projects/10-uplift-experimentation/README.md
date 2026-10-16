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
curve and the random line, in incremental conversions):

| policy | Qini coefficient | profit @ 25% budget | Δ vs random |
|---|---|---|---|
| response model | 13.01 | $4,881 | +$856 |
| **T-learner (recommended)** | **12.03** | **$6,838** | **+$2,812** |
| X-learner | 5.90 | $4,564 | +$539 |
| random | 0.0 | $4,026 | — |
| treat-everyone | 0.0 | — (full-mail: $16,103) | — |

Cost model: margin $114 per incremental conversion (measured mean spend among
converters), $0.01 per email. `profit(f) = inc(f)·margin − mailed(f)·cost`.

**Recommended policy:** target the top 25% by T-learner score —
**+$2,812 expected incremental profit per campaign wave vs random targeting
at the same budget (+69%)**: ~61 incremental conversions from 10,653 emails vs
~36 at random. Note the trade the table makes visible: with a $0.01 send cost
even random full-mail is profitable ($16,103), so the uplift model's value is
concentration — the same budget, ~70% more conversions — and it becomes the
difference between profit and loss the moment the cost model includes
fatigue or list wear (raise `cost_per_email` in `params.yaml` and watch the
frontier). Qini area and profit-at-budget disagree for the response model
(highest area, lowest budget profit): the policy is chosen on the money, the
curve explains why.

**The honest caveat:** predicting conversions ≠ changing them — same lesson
as Project 05's fairness finding on the retention side. The decile check
(`uplift_by_decile`) shows predicted ordering only roughly tracking the
empirical arm contrast; at a ~1% conversion base, per-decile empirical uplift
is noisy, and the X-learner's second stage adds variance without signal here
(near-constant propensity, strong overlap).

## Artifacts

- Figures (`reports/figures/`, `.html` + `.json`): `eda_segment_profile`,
  `qini_curves`, `uplift_by_decile`, `profit_frontier`, `cuped_variance`
- Metrics: `reports/metrics.json` (policy ladder + `_meta.cuped/power/deciles`)
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
