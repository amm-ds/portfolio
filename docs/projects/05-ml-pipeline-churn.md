# 05 · Churn Modeling with Production-Grade sklearn Pipelines

**Domain:** Classical ML · **Data:** seeded synthetic churn (messy on purpose:
2% NaN age, 3% NaN support calls, a 9,999 charge outlier) · **Status:** working
showcase on the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

## What it shows

A single self-contained `sklearn.Pipeline` — custom `OutlierCapper` and
`MissingValueIndicator` transformers, median imputation, scaling, one-hot
encoding — followed by **cost-aware Optuna model selection** across four
arms (logistic, HistGradientBoosting, XGBoost, LightGBM — all sklearn-API on
the same in-pipeline preprocessing; seeded TPE with median pruning; trials
scored by CV business cost at per-trial cost-optimal thresholds) whose
winning config is written back to `params.yaml`. Client CRM extracts onboard
via `prepare --input client.csv` through the same DQ gates and contract.
Evaluation is a five-run ladder on one holdout: naive majority → logistic
baseline (default and cost-tuned thresholds) → selected model raw and
isotonic-calibrated — with calibration (ECE), permutation importance, PR
curves, decision-curve analysis, a business-cost curve (FP=1, FN=5), and a
paired bootstrap CI on the cost delta vs naive.

## Key results (seed 42, n=5,000 → 1,000-row holdout)

| run | threshold | ROC-AUC | F1 (macro) | ECE | business cost |
|---|---|---|---|---|---|
| naive majority | cost-optimal | 0.5000 | 0.4770 | – | 440 |
| logistic, default 0.5 | 0.500 | 0.8344 | 0.5796 | – | 350 |
| logistic, tuned | 0.725 | 0.8344 | **0.6833** | – | **282** |
| selected (cost-HPO logistic) | 0.700 | 0.8321 | 0.6744 | 0.280 | **283** |
| selected + isotonic | 0.125 | 0.8216 | 0.6087 | **0.017** | 322 |

- Cost-aware HPO selected **LogisticRegression (C=0.6494, l1_ratio=0.4540)**
  across 25 trials × 4 arms (best CV cost 1,220; family means 1,225 vs
  1,339–1,409 for the boosters). An earlier F1-objective run picked HistGB,
  which loses on holdout cost — the objective, not the family, decides.
- Best deliverable vs naive: **cost −35.7%, F1 +43%**, confirmed by the
  paired bootstrap: **−157, 95% CI [−236, −86]**.
- Cost-model sensitivity (DVC experiments, DESIGN.md "Experiment
  versioning"): fn_cost 3/5/8 → selected cost 210/283/387, optimal threshold
  0.775/0.700/0.625 — higher miss cost, earlier alarm, logistic still wins.
- Isotonic calibration cuts ECE **−94%** (0.280 → 0.017) without improving
  the cost optimum — a probability-quality upgrade, not a decision upgrade.
- 6/6 data-quality gates; full pipeline (incl. HPO) ~35 s, deterministic.

## Artifacts

- Figures: `eda_churn_profile`, `calibration_curve`, `permutation_importance`,
  `precision_recall_curve`, `decision_curve`, `business_cost_curve`,
  `bootstrap_ci` (`.html` + `.json` for the showcase app)
- Metrics: `reports/metrics.json` (5-run ladder + `_meta.cost_delta_ci`) ·
  Report: `reports/report.html` · DQ: `reports/dq_report.md`
- Selection record: `data/model_selection.json` · Dataset identity card:
  `data/dataset_contract.json` (SHA-256, seeded source)

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/05-ml-pipeline-churn/README.md) — full
  results, reproduce commands, client takeaways
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/05-ml-pipeline-churn/DESIGN.md) — requirements,
  options considered, pipeline diagram, changelog, experiment versioning
- Story: `projects/05-ml-pipeline-churn/story.yaml` (8 canonical sections +
  roadmap, served by the showcase API)
- Source: `projects/05-ml-pipeline-churn/src/churn_pipeline/`
