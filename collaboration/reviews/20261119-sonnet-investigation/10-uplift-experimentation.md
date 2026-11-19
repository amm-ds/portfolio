# 10 Uplift experimentation: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- Hillstrom, 42,613 customers (Men's E-Mail vs No E-Mail) from the 64,000-row dataset; uplift targeting beat random by +$2,812 (+70%) at a 25% send budget, CI [+$718, +$4,767]; at $0.01 per email mailing everyone still wins; targeting overtakes mail-everyone above about $0.30 per email. ATE +0.68 pp; power needs 3,063 per arm, 21,306 available. Five-fold cross-fitting; paired bootstraps. Best-arm beats random on DR/IPW; not established over single-arm. Source: `projects/10-uplift-experimentation/story.yaml`; metrics `projects/10-uplift-experimentation/reports/metrics.json` (arms: multi_arm, random, response, t_learner, treat-everyone, x_learner; the 2,812.34 figure is in that file).
- Model choice was made on revenue minus send cost (a policy metric), not Qini.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | A 2026 preprint compares learners on Hillstrom with Qini, 50/50 split, 36 runs: honest forest about 0.0346, GRF causal forest about 0.0214, T-learner about 0.0192 (large standard deviations). Different split and protocol; not comparable to our policy metric. | SEC | S28 |
| G2 | Metric implementation conflict: UpliftBench says causalml/scikit-uplift AUUC integrates the cumulative-gain curve, unlike the prefix-mean variant, and Qini and AUUC can rank models differently. So "Qini" or "AUUC" must be reported with the exact formula. | SEC | S29 |
| G3 | A Criteo benchmark finds the S-learner ahead on Qini (0.3759) with the causal forest lowest (0.2524, on a 10% subsample). Different dataset; shows ranking depends on data. | SEC | S30 |
| G4 | Policy evaluation: doubly robust scores for policy learning and budget-constrained rules (Athey and Wager; Zhou, Athey, Wager); prescriptive-effect-curve across budgets (Hahn et al.); a 2026 paper argues OPE with DR estimators measures policy reward directly where Qini and AUUC only rank. | SEC | S31, S32, S33, S34 |
| G5 | Hillstrom basics: 64,000 records, men's and women's mailings and a control; the women's mailing appeared to reduce spend in some segments. | SEC | S65 |
| G6 | Radcliffe's original Qini definition: not read. | GAP | none |

## Candidate improvements
**A. Single-protocol rerun: causal forest, T-learner, X-learner, two-model on one fixed split; report Qini and AUUC with the formula named, plus revenue minus send cost.**
- Method: same cross-fitting folds as the committed run; add a causal forest (EconML or grf) and a transformed-outcome model; compute Qini (count-based), AUUC (state which variant), and policy value at 10/25/50% budgets with paired bootstrap CIs. New file; existing numbers unchanged.
- Reference: https://arxiv.org/pdf/2607.03999 (S28) for the comparison set; https://arxiv.org/pdf/2608.00915 (S29) for metric definitions.
- Cost: compute only, about 2 engineering days; adds a dependency (owner).
- Stop condition: the ranking by Qini disagrees with the ranking by policy value; report both, do not choose a winner by metric shopping.

**B. DR/IPW policy evaluation across budgets (prescriptive effect curve).**
- Method: compute the DR policy value at every budget from 5% to 100% for each ranker and integrate it as in Hahn et al.; compare with the committed best-arm vs random statement.
- Reference: https://arxiv.org/pdf/1905.05389.pdf (S33); https://arxiv.org/pdf/1702.02896v5 (S31).
- Cost: compute only, about 1 day.
- Stop condition: DR variance too high at small budgets (CI wider than the gain); report as inconclusive.

**C. Women's Email arm as a second contrast.**
- Method: repeat A on the Women's E-Mail vs No E-Mail contrast; check the segment-level negative-effect finding.
- Reference: https://www.stochasticsolutions.com/pdf/HillstromChallenge.pdf (S65).
- Cost: compute only, about 1 day.
- Stop condition: not needed if A shows no stable ranking.

**D. Fresh-holdout design note for the live-campaign test.**
- Method: a design memo only (randomised holdout, per-order margin, fatigue), already named in the roadmap.
- Reference: S34 (OPE for adaptive experiments).
- Cost: writing only.
- Stop condition: owner defers.

## Ranked recommendation
1. A (single-protocol rerun): high value, compute only, offline.
2. B (DR across budgets): medium-high.
3. C (second contrast), then D.

## Queries used (standard, 2026-11-18)
- "uplift modeling Qini coefficient AUUC evaluation Hillstrom causal forest benchmark comparison"
- "policy learning doubly robust off-policy evaluation uplift targeting budget Athey Wager"
- "Hillstrom MineThatData email dataset uplift modeling results Qini men's email women's email"
