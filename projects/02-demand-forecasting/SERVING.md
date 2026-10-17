# Serving artifact contract

The showcase API serves Project 02 demand forecasts from a compact artifact
that `demand_forecasting.cli build-serving` produces:

Directory: `projects/02-demand-forecasting/reports/models/serving/`

- `model.joblib` — a dict with:
  - `model`: fitted champion regressor (sklearn Pipeline; ColumnTransformer
    one-hot on `series_id` + booster)
  - `feature_names`: ordered list of input column names
    (`["t", "dow", "is_weekend", "month", "week", "doy_sin", "doy_cos",
    "lag_1", "lag_7", "lag_14", "series_id"]` for the default lags;
    `series_id` is always last and is a string like `"store_0|product_0"`)
  - `target_transform`: `null` (all arms predict raw daily units)
- `meta.json` — `{"feature_names": [...], "n_features": int, "built_at": str,
  "train_runs": ["lgbm_tuned"],
  "model_selection": {"champion": str, "val_mae_by_arm": {arm: float},
  "rule": str},
  "example_row": {name: float, ..., "series_id": str}}`

Champion selection (no retraining): the served arm is the tuned booster with
the lowest HPO validation MAE read from `data/hpo_best*.json` — the same
numbers the `evaluate` stage reports in `reports/metrics.json`. On the
current synthetic ladder `lgbm_tuned` wins (CV MAE 8.413 vs `hgb_tuned`
8.529 and `xgb_tuned` 8.539), so the bundle loads the already-fitted
`lgbm_tuned` from `data/models.pkl`. Ties keep the `hgb` incumbent.

API: `POST /projects/02-demand-forecasting/forecast`
body `{"features": {name: float, ..., "series_id": str}}`
→ `{"series_id": str, "prediction": float}` (503 when artifacts absent).

Example curl:

```bash
curl -s -X POST http://localhost:8000/projects/02-demand-forecasting/forecast \
  -H 'Content-Type: application/json' \
  -d '{"features": {"t": 400.0, "dow": 3.0, "is_weekend": 0.0, "month": 7.0,
       "week": 29.0, "doy_sin": 0.5, "doy_cos": -0.8, "lag_1": 112.0,
       "lag_7": 108.0, "lag_14": 115.0, "series_id": "store_0|product_0"}}'
```

Rebuild: `uv run python -m demand_forecasting.cli build-serving` (seconds —
it loads `data/models.pkl` and the HPO jsons; it never trains). Re-run after
any `hpo` / `train` stage, then `dvc repro serving`.
