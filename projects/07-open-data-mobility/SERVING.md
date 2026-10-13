# Serving artifact contract (wave 7)

The showcase API serves Project 07 forecasts from a compact artifact that
`mobility.cli build-serving-artifact` produces:

Directory: `projects/07-open-data-mobility/reports/models/serving/`

- `model.joblib` — a dict with:
  - `gbm`: fitted mean model (HistGradientBoostingRegressor)
  - `p90`: fitted quantile model (same class, loss="quantile", quantile=0.9)
  - `feature_names`: ordered list of input column names (e.g.
    `["lag_1", "lag_2", "lag_24", "lag_168", "hour", "dow", "month", ...]`)
  - `target_transform`: either `null` (raw counts) or `"log1p"` with
    `{"y_mu": float, "y_sigma": float}` used to invert predictions
- `meta.json` — `{"feature_names": [...], "n_features": int, "built_at": str,
  "train_runs": ["gbm_tuned"], "example": {"zone_id": 132, "features": { ... }} }`
- `zones.json` — `[{"location_id": int, "borough": str, "zone": str}]`

API: `POST /projects/07-open-data-mobility/forecast`
body `{"zone_id": int, "features": {name: float, ...}}`
→ `{"zone_id", "borough", "zone", "prediction", "p90"}` (503 when artifacts absent).
