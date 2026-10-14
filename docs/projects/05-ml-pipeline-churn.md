# 05 · Churn Modeling with Production-Grade sklearn Pipelines

**Domain:** Classical ML · **Data:** seeded synthetic churn (messy on purpose:
2% NaN age, 3% NaN support calls, a 9,999 charge outlier) · **Status:** working
showcase on the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

## What it shows

A single self-contained `sklearn.Pipeline` — custom `OutlierCapper` and
`MissingValueIndicator` transformers, median imputation, scaling, one-hot
encoding — followed by **cost-aware Optuna model selection** (logistic vs
histogram gradient boosting, seeded TPE with median pruning; trials scored by
CV business cost at per-trial cost-optimal thresholds) whose winning config is
written back to `params.yaml` as the production config. Client CRM extracts
onboard via `prepare --input client.csv` through the same DQ gates and
contract. Evaluation is a five-run ladder on one holdout: naive majority →
logistic baseline (default and cost-tuned thresholds) → selected model raw and
isotonic-calibrated — with calibration (ECE), permutation importance, PR
curves, decision-curve analysis, a business-cost curve (FP=1, FN=5) that
chooses the operating threshold, and a paired bootstrap CI on the cost delta
vs naive.

## Key results (seed 42, n=5,000 → 1,000-row holdout)

| run | threshold | ROC-AUC | F1 (macro) | ECE | business cost |
|---|---|---|---|---|---|
| naive majority | cost-optimal | 0.5000 | 0.4770 | – | 440 |
| logistic, default 0.5 | 0.500 | 0.8344 | 0.5796 | – | 350 |
| logistic, tuned | 0.725 | 0.8344 | **0.6833** | – | **282** |
| selected (cost-HPO logistic) | 0.700 | 0.8318 | 0.6756 | 0.281 | **282** |
| selected + isotonic | 0.175 | 0.8298 | 0.6380 | **0.014** | 311 |

- Cost-aware HPO selected **LogisticRegression (C=0.2365, l1_ratio=0.1388)**
  (mean trial cost 934 vs 1,215 for HistGB); an earlier F1-objective run
  picked HistGB, which loses on holdout cost (321) — winner changed with the
  objective.
- Best deliverable vs naive: **cost −35.9%, F1 +43%**, and the paired
  bootstrap (2,000 resamples) confirms it: **−158, 95% CI [−237, −87]**.
- Isotonic calibration cuts ECE **−95%** (0.281 → 0.014) without improving
  the cost optimum — a probability-quality upgrade, not a decision upgrade.
- 6/6 data-quality gates; full pipeline (incl. HPO) ~10 s, deterministic.

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
  options considered, pipeline diagram, changelog
- Story: `projects/05-ml-pipeline-churn/story.yaml` (8 canonical sections,
  served by the showcase API)
- Source: `projects/05-ml-pipeline-churn/src/churn_pipeline/`
