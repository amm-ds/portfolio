# Serving endpoints

Four `POST` endpoints serve live model inference alongside the read-only
results/figures routes. 02/05/07 read persisted serving artifacts from
`projects/<pid>/reports/models/serving/` (503 with build instructions when
absent); 06 is a pure function of the request body. Shared loader:
`showcase_api.serving.load_artifacts` / `cached_artifacts` (per-directory
lazy in-process cache, including missing-artifact results; restart the process
after replacing a bundle). 06 does not load artifacts.

Other caching is deliberate: `/projects` and `/demos` are compact JSON payloads
held in memory per projects root and revalidated with ETags; figures and demo
payloads use ETags plus `max-age=3600, stale-while-revalidate=86400`; `/health`
and `/ready` are `no-store`; hashed `/assets/` files are immutable for one year; and SPA HTML
and other static files require revalidation. There is no response cache for
POST inference or RAG answers.

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
- Errors: 503 (artifacts not built; "busy" when the 4-slot scoring capacity
  is full — retry), 422 on missing feature names.
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

## Interactive demos (`GET /demos`, `/demos/{id}/manifest`, `/demos/{id}/payload`)

Manifest-driven demo platform. A demo is declared by a `demo.yaml` in its
project directory (`projects/<pid>/demo.yaml`) and validated against
`portfolio_core.demo.DemoManifest`:

- `id` (`^[a-z0-9-]+$`), `title`, `hook` (one-line pitch), `project`
  (`^\\d{2}-[a-z0-9-]+$`), `group` (business-problem grouping key),
  `skills` (optional), `modes` (non-empty: `browser` | `live` | `replay`),
  `hero` (optional `{label, value, ci?}` headline metric),
  `scenarios` (optional named control presets, e.g.
  `{name: base, controls: {threshold: 0.175, fn_ratio: 5}}`),
  `live_endpoints` (optional `{method: GET|POST, path, label, cost}` — `cost`
  is free-form: `free-local` or a $-per-call note).
- `payload`: `{path, schema_version, required_keys}` — `path` is relative to
  the project dir and points at the committed `reports/demo_payload.json`;
  `required_keys` (non-empty) and `schema_version` are validated on serve.

Routes:

- `GET /demos` — the demo registry: one entry per discovered `demo.yaml`,
  sorted by `(group, id)`, shaped exactly
  `{id, title, hook, href, group, project, status, hero}` where `href` is
  `/demos/{id}` and `status` is `live`.
- `GET /demos/{id}/manifest` — the validated `DemoManifest` as JSON.
- `GET /demos/{id}/payload` — the project's committed payload JSON. The
  response carries an ETag and `Cache-Control: public, max-age=3600,
  stale-while-revalidate=86400`. Errors: 404 for an unknown
  demo id or when the payload file is missing, 409 when the payload's keys or
  `schema_version` don't satisfy the manifest's `payload` ref.
