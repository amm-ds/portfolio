# 05 · Churn Modeling with Production-Grade sklearn Pipelines

Classical-ML showcase: predict customer churn on deliberately messy tabular
data with a single self-contained `sklearn.Pipeline` — custom transformers,
DQ gates, grid-searched regularization, calibration, permutation importance,
and business-cost-driven threshold tuning.

**Status:** working showcase on the standard platform (flagship projects are
[01](../01-rag-agent/README.md) and [07](../07-open-data-mobility/README.md)).

## Problem

Which customers will churn next month, what is that prediction worth, and at
what alert threshold should the retention team act? The primary track is the
real **IBM telco churn dataset** (7,043 customers, 26.5% base churn, behind
the same DQ gates and DatasetContract — see
[data-registry/telco-churn](../../docs/data-registry/telco-churn.md)); the
platform's seeded synthetic generator (`portfolio_core.synthetic.churn` —
NaN gaps, a 9,999 charge outlier, 8.8% base rate) remains as the clearly
labeled CI path (`data_source: synthetic`). Accuracy alone is misleading in
either regime, and missed churners (false negatives) must cost more than
false alarms (FP=1, FN=5).

## Design

Everything from raw DataFrame to probability lives **inside one fitted
Pipeline** — no preprocessing happens outside the estimator, so the persisted
artifact is safe to score on equally messy raw data and cannot leak between
train and holdout.

```text
raw frame ──▶ DQ gates ──▶ stratified 80/20 split ──▶ GridSearchCV(C)
                                                              │
        ColumnTransformer                                     │
        ├─ numeric: OutlierCapper(1%/99%) → MissingValueIndicator
        │           → SimpleImputer(median) → StandardScaler  │
        └─ categorical: SimpleImputer(most_frequent)          │
                        → OneHotEncoder(ignore unknown)       │
        LogisticRegression(class_weight="balanced") ◀─────────┘
```

- Custom transformers (`features.py`): `OutlierCapper` clips at train-time
  quantiles (the 9,999 outlier can never reach the scaler), and
  `MissingValueIndicator` appends `<col>_was_missing` flags **before**
  imputation, so "missing" itself can be learned as signal.
- Model selection (`model.py` + `hpo.py`): `GridSearchCV` over
  C ∈ {0.01, 0.1, 1, 10} keeps the baseline logistic row; **Optuna** (seeded TPE,
  median pruning) then chooses among four arms — LogisticRegression
  (C log 1e-3..1e2, l1_ratio 0..1), HistGradientBoostingClassifier, and the
  sklearn-API **XGBClassifier / LGBMClassifier** — on a **cost-aware
  objective**: stratified CV with out-of-fold probabilities, each trial
  scored by the business cost (FP=1/FN=5) at its own cost-optimal threshold.
  All arms consume the same ColumnTransformer output inside the Pipeline —
  one preprocessing contract, no native-categorical bypass. The winning
  config is written back to [`params.yaml`](params.yaml).
- Calibration: the selected model is compared raw vs **isotonic-calibrated**
  (calibration split carved from training only, disjoint from the fit data and
  the holdout) via ECE and the same business-cost curve.
- Operating policy: stratified training-side OOF predictions select and freeze
  the logistic, raw-selected, and calibrated thresholds before holdout scoring.
  `data/operating_policy.json` is the single source for evaluation and serving.
- Evaluation (`evaluate.py`): five `RunResult` rows — fixed contact-everyone,
  baseline logreg at 0.5 and its OOF-frozen threshold, and both selected models
  at their OOF-frozen thresholds. Seeded paired bootstraps (2,000 resamples)
  compare the exact calibrated policy with contact-everyone and logistic-at-0.5.
  EDA, calibration, importance, precision–recall, decision, cost, and slice
  figures use the resulting metrics.
- Client onboarding (`cli.py`): `prepare --input client.csv` ingests a client
  CRM extract with the same columns (`churned` optional) through the same DQ
  gates and DatasetContract — no downstream pipeline changes.

Full rationale and rejected alternatives: [DESIGN.md](DESIGN.md).

## Results (real run: IBM telco churn, 7,043 rows -> 1,409-row holdout)

Holdout churn rate 26.5% - a different regime from the 8.8% synthetic track.
Grid search: **C=0.01**. The persisted selection is **XGBoost**
(n_estimators 211, learning_rate 0.0309, max_depth 3, subsample 0.5187).
`data/model_selection.json` retains no valid trial count or search score, so
neither is claimed here. On the synthetic track the search picked a logistic.

| run | threshold | ROC-AUC | accuracy | P (macro) | R (macro) | F1 (macro) | ECE | business cost |
|---|---|---|---|---|---|---|---|---|
| contact everyone (fixed) | 0.000 | 0.5000 | 0.265 | 0.1327 | 0.5000 | 0.2098 | - | 1,035 |
| logreg, default | 0.500 | 0.8292 | 0.731 | 0.6999 | 0.7503 | 0.7022 | - | 691 |
| logreg, OOF-frozen | 0.450 | 0.8292 | 0.700 | 0.6922 | 0.7461 | 0.6796 | - | 655 |
| selected raw (cost-HPO XGB) | 0.225 | 0.8387 | 0.722 | 0.7020 | 0.7568 | 0.6981 | 0.028 | 644 |
| selected + isotonic (served) | 0.175 | 0.8317 | 0.690 | 0.6982 | 0.7539 | 0.6745 | **0.016** | **601** |

Key findings:

- **The frozen calibrated policy cuts business cost 1,035 -> 601 (-41.9%) at
  t=0.175 versus contact everyone** (cost weights: $5 per missed churner,
  $1 per contact, from `params.yaml`). The paired delta is **-434, 95% CI
  [-508, -353]** over 2,000 paired row resamples. The committed reports
  do not retain a numeric interval against logistic-at-0.5.
- **The winner changes on real data.** XGBoost beats the logistic family on
  CV business cost (the synthetic track's winner). The served isotonic policy
  costs 601 versus 655 for OOF-tuned logistic and 644 for the raw XGB policy.
- **Calibration improves this evaluation:** ECE moves 0.028 -> 0.016 and frozen
  policy cost moves 644 -> 601. These are measured paired outcomes, not a claim
  that isotonic calibration always helps.
- **The operating point does not transfer - the procedure does.** Every cutoff
  is selected on training-side OOF predictions, then frozen before the holdout
  is scored. Moving logistic from 0.5 to its OOF-frozen 0.450 changes cost
  691 -> 655.
- **Cost-model sensitivity is in `reports/sensitivity.json`:** at FN=3/5/8,
  OOF-frozen isotonic thresholds are 0.250/0.175/0.150 and holdout costs are
  514/601/718. All three contact-everyone delta intervals exclude zero.
  Calibration helps at FN=3 (518 -> 514), FN=5 (644 -> 601), and FN=8 (725 -> 718).
- **Raw-model fairness slices (not the served policy):** at raw XGB t=0.225,
  recall is 0.834 female / 0.829 male and 0.898 senior / 0.808 non-senior.
  Contract recall is 0.918 month-to-month, 0.250 one-year and 0.000 two-year:
  the raw model misses **27 of 36** one-year churners and **all 9** two-year
  churners. The served model is isotonic-calibrated at t=0.175, so these raw
  counts do not describe its decisions.
- Permutation importance on the selected model ranks `tenure_months`
  (0.213), `contract` (0.174), `internet_service` (0.088), and
  `monthly_charges` (0.033) in that order. The real-telco EDA figure shows
  contract, charges, and tenure only. The outlier
  and NaN examples elsewhere in the project are synthetic CI fixtures, not
  real-telco EDA findings.

## Limits

Thresholds are frozen before holdout scoring, but all final metrics still come
from one random snapshot split. The bootstrap estimates row-sampling variation
at fixed thresholds; it does not measure model or threshold-selection
instability. The snapshot has no time axis; fresh, time-stamped data is required
for temporal validation, served-policy fairness, drift, and seasonality. Wider
boosting searches require a defined compute budget.

## Reproduce

**Prerequisites:** Python 3.12 via uv. On macOS, `brew install libomp` — the
xgboost/lightgbm PyPI wheels link against brew's OpenMP and do not bundle it
(missing libomp surfaces as a clear, actionable error at import). Linux
wheels bundle libgomp and need nothing.

```bash
cd projects/05-ml-pipeline-churn
uv run python -m churn_pipeline.cli all   # prepare (telco) → train (cost-aware HPO) → evaluate, ~35 s
# CI path (no network): edit params.yaml to `data_source: synthetic`, then the same command
# client extract onboarding:
uv run python -m churn_pipeline.cli prepare --input client.csv
# or stage-wise via DVC (requires a valid workspace-wide DVC graph):
uv run dvc repro
uv run dvc metrics show   # run ladder from the lockfile
# cost-model sensitivity experiments (see DESIGN.md "Experiment versioning"):
uv run python -m churn_pipeline.cli sensitivity            # FN=3/5/8 -> reports/sensitivity.json
# canonical tracking is queued DVC experiments (needs a working libomp for the
# experiment venv): uv run dvc exp run --queue --set-param fn_cost=3 -n fn3  # etc.
```

Deterministic: seed 42 controls data generation, the split, CV, the Optuna
sampler, and permutation importance. With `model_family: auto` (the default in
[`params.yaml`](params.yaml)) every train re-runs selection and rewrites the
file with the winning config; once written, reruns reuse it (bit-identical
artifacts). Tests (no network, synthetic fixtures only):

```bash
uv run pytest projects/05-ml-pipeline-churn -q
```

## Common errors

| symptom | cause | fix |
|---|---|---|
| `import xgboost` or `import lightgbm` fails on macOS | the PyPI wheels link against Homebrew's OpenMP runtime | run `brew install libomp`, then `uv run pytest projects/05-ml-pipeline-churn -q`; Linux wheels bundle libgomp and need no extra package |

## What this demonstrates for a client

- **Leakage-safe preprocessing as a deployment contract**: imputation,
  scaling, outlier handling, and missingness features ship *inside* the model
  artifact. The serving layer's contract is "hand us the raw CRM row" — one
  line of Python, no ETL rewrite, no train/serve skew, and no way for a future
  data bug to silently bypass the guards built during training.
- **DQ as a gate, not a hope**: the pipeline halts loudly
  (`DQGateError`) if null rates or ranges drift out of contract.
- **Models are products, not Kaggle scores**: on the real telco holdout, the
  training-frozen policy costs 601 versus 1,035 for contact everyone (−41.9%),
  with paired bootstrap 95% CI [−508, −353]. The served threshold is 0.175;
  classification metrics, calibration and the cost curve remain visible.
- **Honest uncertainty and limitations**: permutation importance carries error
  bars; paired CIs match the exact served policy; training-side threshold
  selection and raw-versus-served fairness are labeled explicitly.
- **Full reproducibility**: seeded real-data and synthetic-CI tracks, DVC
  stages, a dataset contract (SHA-256), and offline tests.

## Figures

| figure | file |
|---|---|
| bootstrap ci | [reports/figures/bootstrap_ci.html](reports/figures/bootstrap_ci.html) |
| business cost curve | [reports/figures/business_cost_curve.html](reports/figures/business_cost_curve.html) |
| calibration curve | [reports/figures/calibration_curve.html](reports/figures/calibration_curve.html) |
| decision curve | [reports/figures/decision_curve.html](reports/figures/decision_curve.html) |
| eda churn profile | [reports/figures/eda_churn_profile.html](reports/figures/eda_churn_profile.html) |
| fairness slices | [reports/figures/fairness_slices.html](reports/figures/fairness_slices.html) |
| permutation importance | [reports/figures/permutation_importance.html](reports/figures/permutation_importance.html) |
| precision recall curve | [reports/figures/precision_recall_curve.html](reports/figures/precision_recall_curve.html) |

