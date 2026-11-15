# eval-workbench web

Standalone Vite + React + TypeScript frontend for the eval-workbench FastAPI service.
It provides a versioned dataset registry, run history, case-level run inspection, and
same-dataset model comparison charts. It is deliberately read-only: the browser does
not execute models, alter expected outputs, or synthesize aggregate metrics.

## Run

```bash
npm ci
npm run dev
```

Vite listens on `http://localhost:4324` and proxies `/datasets`, `/runs`, `/health`,
and `/ready` to `http://localhost:8002`. Set `VITE_API_PROXY_TARGET` to change the
proxy or `VITE_API_BASE_URL` to use a different API origin.

For a provider-free interface preview:

```bash
VITE_MOCK=1 npm run dev
```

Fixture mode uses synthetic support-routing and refusal-probe records. The banner and
footer identify those numbers as fixtures, not live model-quality evidence.

## API contract

- `GET /datasets` returns an array of dataset records.
- `GET /runs` returns an array of run summaries.
- `GET /runs/{id}` returns one run summary plus its `cases` array.
- Completed runs carry `accuracy` and `f1` scores in `[0, 1]`, non-negative
  `p95_latency_ms`, and non-negative `cost_usd`. Incomplete runs use `metrics: null`.
- A wrong prediction (`passed: false`) is distinct from an execution failure (`error`
  present and the run's `failed_cases` count). Comparisons include completed runs from
  one dataset version only.

Response validators reject malformed records before they reach the interface. Both
visual bars and a table expose the exact comparison values; quality charts use a fixed
0–1 axis while latency and cost charts scale to the largest displayed run.

## Checks

```bash
npm test
npm run lint
npm run build
```
