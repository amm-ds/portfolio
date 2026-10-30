# Serving artifact contract (wave 7; per-service extension wave 15)

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
body `{"zone_id": int, "features": {name: float, ...}, "service": "yellow" | "green" = "yellow"}`
→ `{"zone_id", "borough", "zone", "prediction", "p90", "service"}` (503 when
artifacts absent; 422 for an unknown service or missing features).

## Per-service bundles (wave 15)

`build-serving-artifact` additionally produces, in the same run:

- `green/` — a per-service retrained bundle in the **identical three-file
  contract**: `green/model.joblib` (run `gbm_green_served`: default GBM family
  + quantile-0.9 p90 twin fit on all curated green zone-hours, the measured
  wave-14 control recipe), `green/meta.json` (adds `service: "green"` and a
  `fit` block with the recipe/train rows), `green/zones.json`.
- `services.json` — typed registry (`mobility.schemas.ServingRegistry`):
  `{"services": {"yellow": {"dir": ".", "train_runs": [...], "n_features": int,
  "built_at": str}, "green": {"dir": "green", ...}}}`.

The showcase API routes the optional request `service` through
`services.json` and loads the selected directory with the existing
`showcase_api.serving.load_artifacts` cache. The committed bundle is covered by
API tests for default-yellow behavior, a green prediction cross-checked
against the bundle, unknown-service 422, and readiness.

`mobility.serving.predict_service(cfg, service, zone_id, features)` is the
typed mobility-side reference for per-service inference (returns a
`mobility.schemas.ServiceForecast`; unknown zone_id or missing features raise
`ValueError`, matching the API's 422 behavior; a missing bundle raises
`FileNotFoundError`, matching the 503).
