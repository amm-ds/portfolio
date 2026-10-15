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

## Results (real run: IBM telco churn, 7,043 rows -> 1,409-row holdout)

Holdout churn rate 26.5% - a different regime from the 8.8% synthetic track.
Wave-2 grid search: **C=0.01**. **Cost-aware Optuna selected XGBoost**
(25 trials x 4 arms: n_estimators 211, learning_rate 0.0309, max_depth 3,
subsample 0.5187; best CV business cost 2,416). On the synthetic track the
same search picked a logistic - the winner tracks the data.

| run | threshold | ROC-AUC | accuracy | P (macro) | R (macro) | F1 (macro) | ECE | business cost |
|---|---|---|---|---|---|---|---|---|
| naive majority | cost-optimal | 0.5000 | **0.735** ⚠️ | 0.1327 | 0.5000 | 0.2098 | - | 1,035 |
| logreg, default | 0.500 | 0.8292 | 0.731 | 0.6999 | 0.7503 | 0.7022 | - | 691 |
| logreg, tuned | 0.300 | 0.8292 | 0.620 | 0.6861 | 0.7253 | 0.6151 | - | 611 |
| selected (cost-HPO XGB) | 0.150 | 0.8387 | 0.663 | 0.6890 | 0.7398 | 0.6512 | 0.028 | 619 |
| selected + isotonic | 0.175 | 0.8317 | 0.690 | 0.6982 | 0.7539 | 0.6745 | **0.016** | **601** |

Key findings:

- **Against the naive floor, the deliverable cuts business cost 1,035 -> 601
  (-41.9%) at t=0.175.** Paired bootstrap: **-416, 95% CI [-485, -343] -
  significant**. The naive row's "accuracy" is 0.735: never alarming is the
  accuracy trap, inverted - on a 26.5% base rate the ignore-all policy looks
  accurate and burns 1,035 cost units.
- **The winner changes on real data.** XGBoost beats the logistic family on
  CV business cost (the synthetic track's winner); after isotonic calibration
  it also holds the holdout cost optimum (601 vs the tuned logistic's 611 -
  within noise, but the calibrated booster is the deliverable).
- **Calibration verdict flips:** isotonic improves *both* ECE
  (0.028 -> 0.016) and the business-cost optimum (619 -> 601). On the noisier
  real regime, trustworthy probabilities pay; the synthetic conclusion
  (calibration doesn't move the optimum) does not transfer.
- **The operating point does not transfer - the procedure does.** Synthetic
  t*=0.700 vs telco t*=0.175: the threshold must be re-derived per regime on
  the cost curve; re-tuning alone moved the logistic 691 -> 611.
- **Fairness slices** (at t=0.150): recall is uniform across gender
  (0.90 both) and *higher* for senior citizens (0.97 vs 0.88 - they churn at
  41.7% and are easier to catch). The real gap is by contract: month-to-month
  recall 0.98 vs one-year 0.47 and two-year 0.00 - the cost-optimal threshold
  is tuned to the dominant short-contract churn and misses nearly all 45
  long-contract churners in the holdout. That is a business choice (they cost
  little at FN=5), not a bug - and the cost-surface figure shows exactly
  where a different FN cost would move it.
- Permutation importance on the selected model ranks `tenure_months`,
  `monthly_charges`, and `contract` first - matching the EDA splits
  (churners: ~74 vs ~61 mean monthly charges, ~18 vs ~38 months tenure;
  fiber-optic internet churns at 41.9%).

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
