# 10 · Uplift experimentation (Hillstrom): technical review

## Verdict
The analysis is careful: CUPED variance reduction is reported honestly as near zero, the power calculation is explicit, and the "mailing everyone wins at $0.01" result is stated plainly. Two copy problems must be fixed: the short copy's customer count and the word "profit".

## Architecture
- Experiment read (ATE), CUPED with a pre-treatment covariate, Qini curves with out-of-fold scoring, and profit at a fixed budget. A complete and standard uplift workflow.
- Models: response model, T-learner, X-learner. The recommended policy is the T-learner.

## Results vs benchmarks and SOTA
- Qini and uplift-by-decile are standard. The comparison set (random, treat-everyone, response model, X-learner) is appropriate.
- Published uplift benchmarks on Hillstrom exist (**verify** a citation before claiming SOTA); the card should say the T-learner is chosen by a stated rule, not by SOTA.

## Metrics and statistics
- **Blocker (copy).** short_version says "64,000-customer randomized email data". The analysis uses 42,613 customers (Men's E-Mail vs No E-Mail). Both numbers may be true, but the card must say the analysis subset is 42,613 of 64,000.
- **Major (metric naming).** "Profit" is revenue minus email cost: the snapshot has no COGS, and the code comments say so. Rename to "net revenue" or "revenue minus send cost" everywhere, including figure titles.
- Recommended policy is T-learner (Qini 12.03) while the response model has higher Qini (13.01). The choice is by profit at budget, which is a defensible rule, but the card must state it, since the Qini intervals overlap.
- Headline "+69%": 2,812 / 4,026 = 69.9%. Round to +70% or show one decimal.

## Code and tests
- 10 test files. Confirm CUPED is tested with a synthetic case where the true variance reduction is known.

## Visuals
- `profit_frontier` and `qini_curves` support the claims. Label the revenue basis on the axis.
- `cuped_variance` should show the near-zero result honestly; keep it.

## Copy and articles
- The "mailing everyone wins at $0.01" sentence is the most useful finding. Keep it prominent.

## Kimi refinement tasks
1. (blocker) Fix short_version to state 42,613 analysed customers within the 64,000-row dataset.
2. (major) Rename "profit" to "revenue minus send cost" in copy, figures, and metrics keys.
3. (major) State the policy-selection rule on the card and show the Qini interval overlap.
4. (minor) Fix +69% to +70% or report one decimal.
5. (minor) Add a synthetic CUPED test with known variance reduction.
