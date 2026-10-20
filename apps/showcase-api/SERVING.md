# Serving endpoints

Four `POST` endpoints serve live model inference alongside the read-only
results/figures routes. 02/05/07 read persisted serving artifacts from
`projects/<pid>/reports/models/serving/` (503 with build instructions when
absent); 06 is a pure function of the request body. Shared loader:
`showcase_api.serving.load_artifacts` / `cached_artifacts` (per-directory
lazy cache; joblib load happens once, not per request).

## `POST /projects/02-demand-forecasting/forecast`

Per-series demand forecast from the tuned pipeline.

- Body: `{"series_id": str, "features": {name: float, ...}}`
- Errors: 503 (artifacts not built), 422 on unknown `series_id` or missing
  feature names.
- 200: `{"forecast": float, "model": str}` — `model` is meta `model_name`,
  falling back to `train_runs[0]`, then `model_selection.champion`/`family`,
  then the estimator class name.

Artifacts: `model.joblib` = `{"model": sklearn Pipeline, "feature_names",
"target_transform": null}`; the pipeline scores an object row built as
`[numeric features in feature_names order (series_id excluded)..., series_id]`
(exactly what demand_forecasting's serving test round-trips). `meta.json` =
`{"feature_names", "example_row": {..., "series_id": str}, ...}`.

Known-series check: meta `series` (fallback keys `series_ids`/`known_series`)
when present; when meta carries no series list it is derived from
`example_row.series_id` (currently the case), so only the example series is
accepted; when neither exists, any series_id passes.

```bash
curl -s localhost:8000/projects/02-demand-forecasting/forecast \
  -H 'content-type: application/json' \
  -d '{"series_id": "store_0|product_0",
       "features": {"t": 371.5, "dow": 4.0, "is_weekend": 0.0, "month": 7.0,
                    "week": 27.0, "doy_sin": -0.0312, "doy_cos": -0.0312,
                    "lag_1": 66.0, "lag_7": 66.0, "lag_14": 65.0}}'
```

## `POST /projects/05-ml-pipeline-churn/score`

Churn probability + cost-threshold alarm.

- Body: `{"features": {name: float | str, ...}}` — string values are allowed,
  `feature_names` include categoricals (`contract`, `internet_service`).
- Errors: 503 (artifacts not built), 422 on missing feature names.
- 200: `{"churn_probability": float,
  "decision": {"alarm": bool, "threshold": float, "expected_cost_note": str}}`
  where `alarm = churn_probability >= threshold` (threshold and the fp/fn cost
  weights come from the artifact's `decision` block: 0.175 / 1 / 5).

Artifacts: `model.joblib` = `{"model": sklearn estimator (single DataFrame row
-> proba), "feature_names", "decision": {...}}`; `meta.json` =
`{"feature_names", "example_row": {...}}` (flat dict, no series list).

```bash
curl -s localhost:8000/projects/05-ml-pipeline-churn/score \
  -H 'content-type: application/json' \
  -d '{"features": {"tenure_months": 29.0, "monthly_charges": 69.05,
                    "contract": "one-year", "internet_service": "DSL"}}'
```

## `POST /projects/06-routing-optimization/solve`

Solve a VRPTW instance with the tuned 2-opt portfolio. No artifacts: the
request body IS the instance, validated by Project 06's pydantic `Problem`
schema (extra keys → 422).

- Body: `Problem` — `{"name": str, "customers": [{id, x, y, demand,
  ready_time, due_time, service_time}, ...]` (customer 0 = depot, ids
  consecutive from 0), `"vehicle_capacity": float, "max_vehicles": int}`.
- Guards: 422 when `n_customers > 200`; `max_iterations` is capped at the
  tuned value from `projects/06-routing-optimization/params.yaml`
  (`solver_best`, currently 50). ALNS is not served (2-opt only, fixed
  seed 42). Measured worst case (200-customer R2-scale synthetic): tuned
  2-opt ~0.01 s, full request ~1 s — far under the 30 s budget.
- 200: the `RoutePlan` JSON (`instance`, `solver` = `"two_opt_tuned"`,
  `routes`, `total_distance`, `n_vehicles`) plus `runtime_s`.

```bash
curl -s localhost:8000/projects/06-routing-optimization/solve \
  -H 'content-type: application/json' \
  -d '{"name": "demo", "vehicle_capacity": 200,
       "customers": [
         {"id": 0, "x": 50, "y": 50, "demand": 0, "ready_time": 0, "due_time": 1000, "service_time": 0},
         {"id": 1, "x": 10, "y": 10, "demand": 10, "ready_time": 0, "due_time": 500, "service_time": 5},
         {"id": 2, "x": 90, "y": 10, "demand": 10, "ready_time": 0, "due_time": 500, "service_time": 5}
       ]}'
```

## `POST /projects/07-open-data-mobility/forecast`

Zone-hour demand forecast from the persisted tuned GBM pair (+p90 band).
Contract: `projects/07-open-data-mobility/SERVING.md`.

- Body: `{"zone_id": int, "features": {name: float, ...}}`
- Errors: 503 (artifacts not built), 422 on unknown `zone_id` or missing
  feature names.
- 200: `{"zone_id", "borough", "zone", "prediction", "p90"}`

```bash
curl -s localhost:8000/projects/07-open-data-mobility/forecast \
  -H 'content-type: application/json' \
  -d '{"zone_id": 132, "features": {"lag_24": 5.0, "lag_168": 4.0, "hour": 8.0}}'
```

## `GET /demos/tape-forecast/` — mounted demo app

The [tape-forecast demo](https://github.com/amm-ds/tape-forecast-demo) is
mounted as a self-contained sub-application (its own lookup routes + SPA) at
`/demos/tape-forecast/`. The `tape-forecast` package is a pinned git
dependency of this app; the payload it serves (serving parquets, Phase 1
reports, built demo SPA) is not in the wheel, so the mount is conditional:

- **Docker image**: a `tape-demo` build stage clones the pinned tag
  (`v0.2.0`), builds the demo web and bakes `data/`, `reports/` and
  `web/dist/` into `/opt/tape-forecast/`; the `TAPE_FORECAST_*` env vars are
  set in the image and the mount registers at startup.
- **Local dev**: point the env vars at a local clone and restart uvicorn:

  ```bash
  TAPE_FORECAST_SERVING_DIR=../tape-forecast-demo/data/serving \
  TAPE_FORECAST_REPORTS_DIR=../tape-forecast-demo/reports \
  TAPE_FORECAST_WEB_DIST=../tape-forecast-demo/web/dist \
  TAPE_FORECAST_LAB_DIR=../tape-forecast-demo/data/lab \
    uv run uvicorn showcase_api.main:app --reload
  ```

- **Absent payload** (unit tests, slim checkouts): the mount is skipped with
  an INFO log and the route 404s; the projects page demo card is the only
  entry point, so nothing user-facing breaks.

The canonical URL carries a trailing slash — the demo SPA uses relative
asset/API paths; `/demos/tape-forecast` (no slash) 307-redirects to it.
