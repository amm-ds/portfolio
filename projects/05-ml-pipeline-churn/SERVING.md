# Serving artifact contract

The showcase API serves Project 05 churn scores from a compact artifact that
`churn_pipeline.cli build-serving` produces:

Directory: `projects/05-ml-pipeline-churn/reports/models/serving/`

- `model.joblib` — a dict with:
  - `model`: fitted isotonic-calibrated sklearn Pipeline (preprocessing —
    outlier capping, missing-value flags, imputation, scaling, one-hot — is
    embedded in the artifact, so raw CRM-style rows score directly)
  - `feature_names`: ordered raw input columns (telco track:
    `["tenure_months", "monthly_charges", "contract", "internet_service"]`)
  - `decision`: `{"threshold": 0.175, "fp_cost": 1.0, "fn_cost": 5.0}` —
    alarm when P(churn) ≥ threshold, under the FP=1 / FN=5 cost model
- `meta.json` — `{"feature_names": [...], "n_features": int, "built_at": str,
  "model_selection": {family, params, objective, ...} (from
  data/model_selection.json),
  "threshold_selection": {"threshold": float, "training_oof_min_cost": float,
  "rule": str},
  "example_row": {name: float|str, ...}}`

Threshold selection (no retraining): `train` uses stratified training-side OOF
predictions to minimize FP·1 + FN·5 over params.yaml `threshold_grid`, then
persists `data/operating_policy.json` before holdout scoring. Both `evaluate`
and `build-serving` load that frozen policy. The current threshold is **0.175**;
its holdout cost is 601 and its training OOF cost is 2,425. The model itself is
the already-fitted `data/selected_model_calibrated.pkl` (XGBoost arm,
cost-aware Optuna selection).

API: `POST /projects/05-ml-pipeline-churn/score`
body `{"features": {name: float|str, ...}}`
→ `{"churn_probability": float, "churn": bool, "threshold": float}`
(503 when artifacts absent).

Example curl:

```bash
curl -s -X POST http://localhost:8000/projects/05-ml-pipeline-churn/score \
  -H 'Content-Type: application/json' \
  -d '{"features": {"tenure_months": 12.0, "monthly_charges": 80.0,
       "contract": "month-to-month", "internet_service": "fiber"}}'
```

Rebuild: `uv run python -m churn_pipeline.cli build-serving` (seconds — it
loads the calibrated model and `data/operating_policy.json`; the holdout only
supplies the example row). Re-run after any `train` stage, then
`dvc repro serving`.
