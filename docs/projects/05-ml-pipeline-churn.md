# 05 · Churn Modeling with Production-Grade sklearn Pipelines

**Domain:** Classical ML · **Data:** seeded synthetic churn (messy on purpose:
2% NaN age, 3% NaN support calls, a 9,999 charge outlier) · **Status:** working
showcase on the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

## What it shows

A single self-contained `sklearn.Pipeline` — custom `OutlierCapper` and
`MissingValueIndicator` transformers, median imputation, scaling, one-hot
encoding — followed by **Optuna model selection** (logistic vs histogram
gradient boosting, seeded TPE with median pruning) whose winning config is
written back to `params.yaml` as the production config. Evaluation is a
five-run ladder on one holdout: naive majority → wave-2 logistic (default and
cost-tuned thresholds) → selected model raw and isotonic-calibrated — with
calibration (ECE), permutation importance, PR curves, decision-curve analysis,
and a business-cost curve (FP=1, FN=5) that chooses the operating threshold.

## Key results (seed 42, n=5,000 → 1,000-row holdout)

| run | threshold | ROC-AUC | F1 (macro) | ECE | business cost |
|---|---|---|---|---|---|
| naive majority | cost-optimal | 0.5000 | 0.4770 | – | 440 |
| logistic, default 0.5 | 0.500 | 0.8344 | 0.5796 | – | 350 |
| logistic, tuned | 0.725 | 0.8344 | **0.6833** | – | **282** |
| selected (HistGB) | 0.700 | 0.8125 | 0.6593 | 0.157 | 321 |
| selected + isotonic | 0.225 | 0.8008 | 0.6642 | **0.017** | 328 |

- Optuna (25 trials) selected **HistGradientBoostingClassifier** on CV F1
  (0.3648 vs 0.3433 for the logistic grid) — but on the business cost the
  tuned logistic still wins (282 vs 321): selection objective ≠ deployment
  objective, so both are reported.
- Best deliverable vs naive: **cost −35.9%, F1 +43%**; threshold tuning alone
  −19.4% of cost.
- Isotonic calibration cuts ECE **−89%** (0.157 → 0.017) without improving
  the cost optimum — a probability-quality upgrade, not a decision upgrade.
- 6/6 data-quality gates; full pipeline (incl. HPO) ~15 s, deterministic.

## Artifacts

- Figures: `eda_churn_profile`, `calibration_curve`, `permutation_importance`,
  `precision_recall_curve`, `decision_curve`, `business_cost_curve`
  (`.html` + `.json` for the showcase app)
- Metrics: `reports/metrics.json` (5-run ladder) · Report:
  `reports/report.html` · DQ: `reports/dq_report.md`
- Selection record: `data/model_selection.json` · Dataset identity card:
  `data/dataset_contract.json` (SHA-256, seeded source)

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/05-ml-pipeline-churn/README.md) — full
  results, reproduce commands, client takeaways
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/05-ml-pipeline-churn/DESIGN.md) — requirements,
  options considered, pipeline diagram, changelog
- Story: `projects/05-ml-pipeline-churn/story.yaml` (8 canonical sections,
  served by the showcase API)
- Source: `projects/05-ml-pipeline-churn/src/churn_pipeline/`
