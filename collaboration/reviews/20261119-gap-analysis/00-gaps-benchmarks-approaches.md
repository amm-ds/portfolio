# Gap analysis: results vs benchmarks, and approaches to refine

Date: 2026-11-19
Reviewer: Claude Code
Builds on: `collaboration/reviews/20261117-sota-research/00-research-and-recommendations.md` and its delta note `14-research-deltas-2026-11-18.md`. This pass adds searches on each project's main gap. Confidence: **source-backed** (primary text read), **secondary** (abstract or snippet), **gap** (no source found).

Searches were run on 2026-11-19 in standard mode. Several results are snippets, not full papers, so no number here should be published until the source is read.

## Summary

| # | Project | Our result | Closest benchmark found | Gap | Best next step |
|---|---|---|---|---|---|
| 01 | RAG | 0.733 correct on stress set, 5/30 unsupported | RAGAS faithfulness; warrant-strength checks (ForceBench, secondary) | No claim-level warrant check | Add warrant-strength judge with calibration set |
| 02 | M5 | 0.6161 vs 0.8929 (−31.0%), one origin, no interval | Nixtla MinT full-M5 run (secondary): dense configs did not finish | No reconciled row; one origin | Scoped reconciliation of committed forecasts; add rolling origins |
| 03 | NAB | Precision 0.527 at 2% budget; NAB score not reported | TSB-AD, VUS-PR primary (secondary); no current NAB leaderboard found | Not on the field's current benchmark | Run VUS-PR on TSB-AD subset |
| 04 | AG News | Cascade no measurable change; 0.954 macro-F1 | LabelFusion 92.4% (Dec 2025, secondary); no cascade benchmark found | No selective-classification evaluation | Report coverage vs accuracy curve |
| 06 | VRPTW | Mean gap 4.23% (ALNS-hinted), CI [3.22, 5.28] | PyVRP and HGS tables on 1000-customer instances (see conflict below) | Solomon-100 vs 1000-customer benchmarks not comparable | Report against SINTEF Solomon best-known values only |
| 09 | Agentic | 13/13 answers, 6/6 refusals (h19 guard error), single runs | τ-bench pass^k (source-backed, from its paper) | No multi-trial reliability | Run k≥3 under a cap, or state single-run wording |
| 10 | Uplift | +$2,812 (+70%) at 25% budget, CI [+$718, +$4,767] | 2607.03999 Qini AUC: honest forest 0.0346, causal forest 0.0214, T-learner 0.0192 (secondary); UpliftBench SoloModel 49.1 (different scale) | No single-protocol comparison; TOM not in our set | Rerun causal forest, TOM, T-learner on one split; report Qini and AUUC |
| 12 | Tabular | MLP 25.4 MAE vs 83.2 floor; tie with LightGBM | No TabPFN-vs-LightGBM bike study found; T-STAR 2026 (different task) | No strong external reference | Use the 2026 bike-sharing papers as context only |

## Per project

### 01 RAG agent
- **Gap:** the grounding check accepts a relevant citation even when it does not warrant the claim. ForceBench (2026 preprint, secondary) reports 47.2% monotonicity violation across four judges with generic prompts, and 24.5% with explicit warrant-strength prompting.
- **Approach:** add a warrant-strength rubric to the claim check; calibrate the judge on a labelled set of supported, overstated and unsupported claims; report agreement with the human set. Store judge model and calibration date with each threshold (RAGAS practice, secondary).
- **Cost:** hosted judge calls. Needs an owner-approved cap.
- **Result to expect:** a number for overstated-claim rate, which the current card cannot give.

### 02 M5 forecasting
- **Gap:** no reconciled global LightGBM row (no committed output), one scored test origin, no interval. The 2026 Nixtla MinT paper (secondary) reconciles the full M5 hierarchy but only sparse configurations finished, and dense MinT did not run. So a full dense reconciliation is itself an open benchmark problem.
- **Approach:** (a) reconcile the committed test-origin forecasts only (no retraining), as the open-questions plan proposed; (b) add rolling origins for a stability check, which the M5 literature (Makridakis et al., IJF 2022) uses as its standard, once verified; (c) keep decision 12 (no full rerun).
- **Not verified:** the 0.52 WRMSSE top score, and any published MinT WRMSSE on M5. Do not cite either.

### 03 NAB anomaly detection
- **Gap:** NAB score is not reported (decision 2), which is correct. But the field's current benchmark is TSB-AD (40 algorithms, 40 datasets in the NeurIPS 2024 paper, source-backed), and recent papers use VUS-PR as the primary score (secondary, 2026 papers).
- **Approach:** run VUS-PR on the TSB-AD univariate subset with the same detector families; report alongside NAB range-F1. Report the number of runs (the W6 disclosure). Note Lyu 2026 (preprint) on VUS-ROC inflation.
- **Cost:** compute only, no hosted calls.

### 04 AG News cascade
- **Gap:** the cascade shows no measurable change, which is honest. There is no selective-classification evaluation, so we cannot say how the cascade trades coverage against accuracy.
- **Approach:** report accuracy at coverage levels (the sub-threshold reviewed set), and compare with LabelFusion (92.4%, secondary) and the cost-aware comparison in arXiv 2602.06370 (secondary, full text not read). Our 0.954 macro-F1 is on a different split and metric, so do not present it as beating 92.4%.
- **Cost:** none if coverage is computed from committed predictions.

### 06 Routing
- **Gap:** the Solomon-100 gap (4.23%, ALNS-hinted) is not comparable to published 1000-customer PyVRP or HGS tables. The benchmark table in the search snippets conflicts with the direct table read in W9 (see conflict below). The unhinted arm has no distances.
- **Approach:** cite only SINTEF's Solomon best-known values for gaps (source-backed, SINTEF page). Keep the ALNS-hinted label. Solve the unhinted arm with a longer budget only as a separate experiment.
- **Conflict to resolve before any citation:** Kimi's W9 read of arXiv 2403.13795v2 gives PyVRP mean gap 0.40%, HGS-DIMACS 0.32%, DIMACS reference 0.29%. A search snippet of the same paper gives PyVRP 0.27%, HGS-2012 0.28%, HGS-CVRP 0.16%. Both cannot be the same table. Read the table myself before the owner decides.

### 09 Agentic workflows
- **Gap:** single runs; no reliability measure. τ-bench reports pass^k, the chance of success on all k trials (source-backed, Sierra). The live run shows 13/13 answers and 6/6 refusals, but h19 is a guard error, so the refusal score overstates the contract.
- **Approach:** run k≥3 on the held-out set under a cap (this changes the cost picture: 19 tasks × 3 × ~$0.094 / 19 ≈ $0.28 at the observed rate; suggested cap $5), or state "single run per task" everywhere. Keep h19 labelled as a guard error.
- **Cost:** hosted calls. Owner approval needed.

### 10 Uplift
- **Gap:** no single-protocol comparison of causal forest, TOM and T-learner on Hillstrom. Our model choice (T-learner) was made on revenue minus send cost, which is a policy metric, not Qini. The 2026 papers use Qini and AUUC.
- **Approach:** rerun causal forest, TOM and T-learner on one fixed Hillstrom split; report Qini and AUUC with bootstrap intervals beside revenue minus send cost. Our policy rule (choose by revenue minus send cost, not Qini) should be stated as a choice, not a finding.
- **Cost:** compute only.

### 12 Tabular bike demand
- **Gap:** the MLP-vs-LightGBM tie is correct. The TabPFN-2.5 challenger is still blocked, and the licence needs an owner decision (see 14-research-deltas §1). No external benchmark of TabPFN vs LightGBM on bike data was found.
- **Approach:** keep the tie claim. If the challenger runs, state its licence and scope. Compare against the 2026 T-STAR result only as context (different task, metric and resolution).

## Conflicts and corrections to carry forward

1. **PyVRP table values** (06): two different readings of the same paper; resolve before citing (see section 06).
2. **M5 0.52 WRMSSE** and "MinT on M5": not confirmed. Do not cite.
3. **NAB leaderboard**: none found for 2025–2026. The earlier SOTA table (NAB v1.0 standard scores) is from 2016 and stays as history, not current SOTA.
4. **AG News 94.74%** (community BERT card): not peer-reviewed; do not use as SOTA.

## Not searched in this pass
- Full text of arXiv 2602.06370 (cost-aware classification): snippet only.
- 2607.03999 and 2608.00915 (Hillstrom): abstracts and snippets only.
- Solomon ALNS and HGS gap tables for 2025–2026.
