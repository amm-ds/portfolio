# 05 · Churn Modeling with Production-Grade sklearn Pipelines

**Domain:** Classical ML · **Data:** seeded synthetic churn (messy on purpose:
2% NaN age, 3% NaN support calls, a 9,999 charge outlier) · **Status:** working
showcase on the standard platform (flagships: [01](01-rag-agent.md), [07](07-open-data-mobility.md))

## What it shows

A single self-contained `sklearn.Pipeline` — custom `OutlierCapper` and
`MissingValueIndicator` transformers, median imputation, scaling, one-hot
encoding, and a balanced `LogisticRegression` — selected by `GridSearchCV`
over C, then evaluated with a business lens: calibration curve, permutation
importance, and a cost curve (FP=1, FN=5) that chooses the operating
threshold. Preprocessing lives inside the fitted artifact, so the model is
deployable on equally messy raw data with no leakage.

## Key results (seed 42, n=5,000 → 1,000-row holdout)

| run | threshold | ROC-AUC | accuracy | precision (macro) | recall (macro) | F1 (macro) | business cost |
|---|---|---|---|---|---|---|---|
| default | 0.500 | 0.8344 | 0.722 | 0.5926 | 0.7552 | 0.5796 | 350 |
| tuned | **0.725** | 0.8344 | **0.874** | **0.6576** | 0.7307 | **0.6833** | **282** |

- Grid search picked **C=1.0** (3-fold CV, F1); holdout ROC-AUC **0.8344**.
- Cost-optimal threshold tuning: **−19.4% business cost** and +0.10 F1 on the
  *same* model — the operating point, not retraining, is the lever.
- Permutation importance (holdout F1, 5 repeats): `monthly_charges` (0.118) >
  `contract` (0.076) > `tenure_months` (0.020) — matching the generator's
  ground truth; the 9,999 charge outlier never reaches the scaler.
- 6/6 data-quality gates (`DQReport`) enforce null-rate and range contracts
  before training; full run takes ~2 s.

## Artifacts

- Figures: `reports/figures/calibration_curve`, `permutation_importance`,
  `business_cost_curve` (`.html` + `.json` for the showcase app)
- Metrics: `reports/metrics.json` · Report: `reports/report.html` ·
  DQ: `reports/dq_report.md`
- Dataset identity card: `data/dataset_contract.json` (SHA-256, seeded source)

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/05-ml-pipeline-churn/README.md) — full
  results, reproduce commands, client takeaways
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/05-ml-pipeline-churn/DESIGN.md) — requirements,
  options considered, pipeline diagram, changelog
- Source: `projects/05-ml-pipeline-churn/src/churn_pipeline/`
