# Next steps: refine experiments, apps, or new work

Date: 2026-11-19
Author: Claude Code (designer)
Status: proposal for owner decision
Inputs: `collaboration/reviews/20261119-sonnet-investigation/00-summary.md` (ranked table), `collaboration/reviews/20261119-execution-review/00-review.md`, `collaboration/designs/20261119-open-questions-closed/00-decisions.md`

## Are the results decent?

Yes for a public portfolio. The headline numbers are committed, reproducible and mostly reported with their limits, and several results are honest negatives (for example 03's detector challenge and 07's rejected test leader). The weak spots are narrower than the whole portfolio:

1. **RAG verify-on (01).** The copy relies on the citation check, but the judges are not calibrated. The committed local judge accepts about 44% of unsupported claims (kappa 0.54). The hosted judge accepts about 40% of unsupported claims when counted strictly (kappa 0.61). This is the most important weakness, because the flagship's main claim depends on it.
2. **Document intelligence (15).** Seven synthetic documents and entity F1 0.677. The sample is too small to support more than a smoke-level claim.
3. **Agent-chat (14).** The 108/108 result comes from one model with three repetitions. The two other models were single runs with a different grader set.
4. **Uplift (10).** The protocol compares T-learner and rankers, but there is no single-protocol comparison across causal forest, T, X and two-model learners.
5. **NAB (03).** Not scored on the official benchmark, and VUS-PR is single-fit per series.

Everything else is either a finished result with its limits stated, or a gap that is already listed as pending in the plan.

## Recommendation: one bounded round, then stop refining

Do not refine every experiment. Spend one round on the four items with the highest value per cost and no new dependencies:

| Order | Item | Why | Cost | Needs your approval |
|---|---|---|---|---|
| 1 | **Q4a: uplift single protocol (10)** | Compute only, on committed folds. Closes the most visible protocol gap. | about 2 days compute, $0 | yes, one item |
| 2 | **Decide the verify-on claim (01)** | Either approve Q3b (hosted warrant check, $3 cap, kimi-for-coding) or soften the copy to match the measured judge error. Do not leave the claim as is. | $3 max if approved, $0 for copy | yes: Q3b or copy change |
| 3 | **Document-intelligence sample (15)** | Add documents to the existing set, then re-run the committed live metrics. Makes the entity F1 claim less fragile. | small, mostly reading | yes |
| 4 | **Q4b: AG News risk-coverage (04)** | Compute only on the fresh holdout. Adds selective classification, which the portfolio lacks. | under 1 day, $0 | yes, one item |

Stop condition for the round: when items 1–4 are reported, re-run the headline check and the public copy gates. Then decide whether to continue.

## Not recommended now

- **New projects (14+).** Each new project needs a design, a handoff, copy and a deploy. It spreads effort across thirteen projects that already have results to refine.
- **Q4c (NAB on TSB-AD), Q4d (PyVRP arm).** Both need new downloads or dependencies. Worth doing later, after the round above.
- **Q4e–h and most of the 15 ranked rows.** Lower expected value per cost. Revisit after the round.
- **Hosted 09 pass^k run.** Needs an owner cap and a multi-trial design. Worth a separate handoff later, not in this round.

## Owner decisions needed

1. Approve Q4a, Q4b, and the 15 document-intelligence expansion (or decline any).
2. Choose for the RAG verify-on claim: approve Q3b, or change the copy to the measured error.
3. Confirm the round is worth doing before starting new projects.
