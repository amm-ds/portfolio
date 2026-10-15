# 05 · Churn Modeling with Production-Grade sklearn Pipelines

Classical-ML showcase: predict customer churn on deliberately messy tabular
data with a single self-contained `sklearn.Pipeline` — custom transformers,
DQ gates, grid-searched regularization, calibration, permutation importance,
and business-cost-driven threshold tuning.

**Status:** working showcase on the standard platform (flagship projects are
[01](../01-rag-agent/README.md) and [07](../07-open-data-mobility/README.md)).

## Problem

Which customers will churn next month, what is that prediction worth, and at
what alert threshold should the retention team act? The data is the platform's
seeded synthetic churn generator (`portfolio_core.synthetic.churn`): 5,000 rows
with **2% NaN in `age`**, **3% NaN in `support_calls`**, a **9,999 charge
outlier**, and an 8.8% base churn rate — the messiness a real CRM export shows
up with. Churn rate is low, so accuracy alone is misleading and missed
churners (false negatives) must cost more than false alarms (FP=1, FN=5).

## Design

Everything from raw DataFrame to probability lives **inside one fitted
Pipeline** — no preprocessing happens outside the estimator, so the persisted
artifact is safe to score on equally messy raw data and cannot leak between
train and holdout.

```
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
  C ∈ {0.01, 0.1, 1, 10} keeps the wave-2 logistic row; **Optuna** (seeded TPE,
  ~25 trials, median pruning) then chooses among four arms — LogisticRegression
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
- Evaluation (`evaluate.py`): five `RunResult` rows — naive majority, wave-2
  logreg at 0.5 and at its cost-optimum, selected model and its calibrated
  variant at their cost-optima — plus a seeded paired bootstrap (2,000
  resamples) of the cost delta vs naive with a 95% CI, and EDA profile,
  calibration, permutation importance, precision–recall, decision-curve, and
  business-cost figures (takeaway subtitles via
  `portfolio_core.plotting.add_takeaway`).
- Client onboarding (`cli.py`): `prepare --input client.csv` ingests a client
  CRM extract with the same columns (`churned` optional) through the same DQ
  gates and DatasetContract — no downstream pipeline changes.

Full rationale and rejected alternatives: [DESIGN.md](DESIGN.md).

## Results (real run, seed 42, n=5,000)

Holdout: 1,000 rows (churn rate 8.8%). Wave-2 grid search: **C=1.0** (CV F1
0.3433). **Cost-aware Optuna selected LogisticRegression (C=0.6494,
l1_ratio=0.4540)** over 25 seeded trials across **four arms** (logistic,
HistGB, XGBoost, LightGBM — all on the same in-pipeline preprocessing):
best CV business cost 1,220; mean trial cost by family: logistic 1,225 <
histgb 1,339 < lightgbm 1,367 < xgboost 1,409 (xgb arm balanced via
`scale_pos_weight`; `class_weight` is silently ignored by XGBClassifier).
(An F1-objective run picked
HistGB instead — the objective is the lever, documented in DESIGN.md.)

| run | threshold | ROC-AUC | accuracy | P (macro) | R (macro) | F1 (macro) | ECE | business cost |
|---|---|---|---|---|---|---|---|---|
| naive majority | cost-optimal | 0.5000 | **0.912** ⚠️ | 0.4560 | 0.5000 | 0.4770 | – | 440 |
| logreg, default | 0.500 | 0.8344 | 0.722 | 0.5926 | 0.7552 | 0.5796 | – | 350 |
| logreg, tuned | 0.725 | 0.8344 | 0.874 | 0.6576 | 0.7307 | **0.6833** | – | **282** |
| selected (cost-HPO logreg) | 0.700 | 0.8321 | 0.861 | 0.6464 | 0.7390 | 0.6744 | 0.280 | **283** |
| selected + isotonic | 0.125 | 0.8216 | 0.766 | 0.6035 | 0.7588 | 0.6087 | **0.017** | 322 |

Key findings:

- **Against the naive floor, the deliverable cuts business cost 440 → 283
  (−35.7%) and lifts macro F1 0.477 → 0.683 (+43%).** The paired bootstrap
  makes the delta defensible: **−157, 95% CI [−236, −86] — significant**
  (2,000 seeded resamples, fixed operating thresholds).
- **Winner unchanged with more arms.** Adding XGBoost and LightGBM to the
  cost-aware search did not dethrone the logistic: it wins both the best
  single trial and the family mean. Boosting arms land within ~10% on cost
  but never below it at FN/FP = 5.
- **Threshold tuning alone: −19.4%** of the cost win (350 → 282), same model,
  no retraining — the operating point is a business decision made on a cost
  curve (FP=1, FN=5), not a library default.
- **Calibration verdict:** isotonic calibration cuts ECE **0.280 → 0.017
  (−94%)** but does **not** improve the business-cost optimum (322 vs 283) —
  at these cost weights the raw ranking already decides well. Calibration is
  worth deploying when the *probabilities themselves* are consumed (budget
  forecasting, CLV math), not for this thresholded alarm.
- **Cost-model sensitivity** (DVC experiments, see DESIGN.md "Experiment
  versioning"): fn_cost=3 → selected cost 210 vs naive 264, t*=0.775;
  fn_cost=8 → 387 vs 704, t*=0.625. Higher miss cost → alarm earlier; the
  logistic wins across the range.
- Permutation importance of the selected model keeps `monthly_charges` and
  `contract` on top, matching the generator's ground truth.

The naive baseline's **accuracy is the highest of all rows** (0.912) — on an
8.8% churn rate, never ringing the alarm is accurate and useless, which is why
the deliverable is cost and F1, not accuracy.

Artifacts (regenerated by every run):

- `reports/metrics.json` — 5-run ladder + `_meta.cost_delta_ci` (bootstrap CI)
- `reports/report.html` — rendered evaluation report
- `reports/figures/eda_churn_profile.{html,json}` — churn rate by contract +
  monthly_charges / tenure distributions
- `reports/figures/calibration_curve.{html,json}` — raw vs isotonic (ECE in legend)
- `reports/figures/permutation_importance.{html,json}`
- `reports/figures/precision_recall_curve.{html,json}` — naive base-rate floor
- `reports/figures/decision_curve.{html,json}` — net benefit vs treat-all/none
- `reports/figures/business_cost_curve.{html,json}` — all candidates + takeaway
- `reports/figures/bootstrap_ci.{html,json}` — paired bootstrap interval
- `reports/dq_report.md` — 6/6 data-quality gates passed
- `data/model.pkl`, `data/selected_model*.pkl`, `data/model_selection.json`,
  `data/holdout.parquet`, `data/model_meta.json`, `data/dataset_contract.json`

## Reproduce

**Prerequisites:** Python 3.12 via uv. On macOS, `brew install libomp` — the
xgboost/lightgbm PyPI wheels link against brew's OpenMP and do not bundle it
(missing libomp surfaces as a clear, actionable error at import). Linux
wheels bundle libgomp and need nothing.

```bash
cd projects/05-ml-pipeline-churn
uv run python -m churn_pipeline.cli all   # prepare → train (cost-aware HPO) → evaluate, ~35 s
# client extract onboarding:
uv run python -m churn_pipeline.cli prepare --input client.csv
# or stage-wise via DVC:
dvc repro projects/05-ml-pipeline-churn
uv run dvc metrics show projects/05-ml-pipeline-churn   # run ladder from the lockfile
# cost-model sensitivity experiments (see DESIGN.md "Experiment versioning"):
uv run dvc exp run --queue --set-param fn_cost=3 -n fn3 .
uv run dvc exp run --queue --set-param fn_cost=8 -n fn8 .
uv run dvc exp run --run-all && uv run dvc exp show --no-pager
```

Deterministic: seed 42 controls data generation, the split, CV, the Optuna
sampler, and permutation importance. With `model_family: auto` (the default in
[`params.yaml`](params.yaml)) every train re-runs selection and rewrites the
file with the winning config; once written, reruns reuse it (bit-identical
artifacts). Tests (39, no network, synthetic fixtures only):

```bash
uv run pytest projects/05-ml-pipeline-churn -q
```

## What this demonstrates for a client

- **Leakage-safe preprocessing as a deployment contract**: imputation,
  scaling, outlier handling, and missingness features ship *inside* the model
  artifact. The serving layer's contract is "hand us the raw CRM row" — one
  line of Python, no ETL rewrite, no train/serve skew, and no way for a future
  data bug to silently bypass the guards built during training.
- **DQ as a gate, not a hope**: the pipeline halts loudly
  (`DQGateError`) if null rates or ranges drift out of contract.
- **Models are products, not Kaggle scores**: every claim is relative to a
  visible naive floor (cost 440 → 282, −35.9%, bootstrap 95% CI [−237, −87]),
  classification metrics are paired with calibration and a business-cost
  curve, and the deliverable includes the *operating threshold* (0.700), not
  just AUC.
- **Honest uncertainty**: permutation importance carries error bars; cost
  deltas carry paired bootstrap CIs; the `age_was_missing`-style flags are
  evaluated rather than assumed useful.
- **Full reproducibility**: seeded end-to-end run in ~10 s (including HPO),
  with DVC stages, a dataset contract (SHA-256), and CI-friendly tests.

## Roadmap

Delivered in waves 7 + 11: cost-aware HPO objective, `prepare --input
client.csv` onboarding, paired bootstrap CIs, and XGBoost/LightGBM arms in
the selection (logistic still wins).

Remaining:

- **Real-data track**: swap the synthetic generator for a public telco churn
  export behind the same `DatasetContract`, or onboard a client extract
  directly via `prepare --input`.
- **Wider boosting search spaces**: the wave-11 arms used deliberately tight
  ranges to stay fast; budget-aware widening (early stopping, successive
  halving) is the next step if a client needs the last few percent.
