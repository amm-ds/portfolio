# Model API Serving & Docker Deployment

**Working showcase.** The portfolio's model-serving case study: experiment 12's
champion tabular MLP (PyTorch, 25.4316 test MAE on UCI Bike Sharing hourly)
re-derived bit-for-bit from its committed recipe, exported to ONNX under a hard
parity gate, served behind a small FastAPI service with interchangeable
native/ONNX backends, load-tested by a hand-written async harness, and baked
into a measured multi-stage Docker image.

- Problem: what does serving a champion tabular model actually look like —
  latency percentiles, throughput, batch curves, memory, image size, cost?
- Design: [DESIGN.md](DESIGN.md)
- Story: [story.yaml](story.yaml) (served at `/projects/13-model-serving/story`)

## Pipeline

```bash
uv run python -m model_serving.cli train       # re-derive champion + ONNX export + gates
uv run python -m model_serving.cli benchmark   # paired load-test, both backends
uv run python -m model_serving.cli docker      # image build, size, compose smoke
uv run python -m model_serving.cli report      # metrics.json + figures + report.html
# or: uv run dvc repro
```

DVC: `train → benchmark → docker → report` (`dvc.yaml`). `benchmark` starts
the real service as a subprocess per backend; `docker` needs the daemon
(it records an honest not-measured note when absent).

## Service

```bash
uv run python -m model_serving.cli serve --backend onnx --port 8137
curl -s -X POST http://127.0.0.1:8137/predict -H 'Content-Type: application/json' \
  -d '{"row": {"hour": 8, "temp": 0.5, "hum": 0.6, "windspeed": 0.1, "weathersit": 1,
       "hour_sin": 0.5, "hour_cos": 0.5, "weekday_sin": 0.0, "weekday_cos": 1.0,
       "month_sin": 0.2, "month_cos": 0.9, "holiday": 0, "workingday": 1,
       "cnt_lag_1h": 120.0, "cnt_lag_24h": 150.0, "cnt_lag_168h": 140.0}}'
```

- `POST /predict` — one contract row; `POST /predict/batch` — up to 1024 rows.
- `GET /health` (process alive), `GET /ready` (backend warmed; 503 before).
- Every response carries a `request_id`; malformed payloads get the standard
  422 shape; unexpected failures get a structured error envelope.
- The request schema mirrors experiment 12's feature contract exactly: raw
  `hour` feeds the embedding, the 15 selected numerics feed the trunk,
  `atemp` never appears (pruned at r = 0.987).

## Docker

```bash
docker build -f projects/13-model-serving/Dockerfile -t portfolio-model-serving:13 .
docker run --rm -p 8137:8000 -e SERVING_BACKEND=onnx portfolio-model-serving:13
docker compose -f projects/13-model-serving/docker-compose.yml up --build --wait api
docker compose -f projects/13-model-serving/docker-compose.yml run --rm smoke
```

Multi-stage: frozen `uv sync` into a self-contained venv at its final path,
slim runtime base, model baked in, non-root user, healthcheck-gated readiness.
The build context is the repository root (uv workspace); the root
.dockerignore keeps data/, .venv, and caches out. The docker stage stages
`data/models/` into `image/serving/` because every `data/` path is excluded
from the context.

The separate `docker-slim` command builds and smoke-tests the ONNX-only
`Dockerfile.slim` image. Its committed measurement is 291 MB versus 6,466 MB
for the full two-backend image; the slim image fixes `SERVING_BACKEND=onnx`
and records its readiness/prediction smoke in `reports/docker_slim.json`.

## Benchmark design

- Real subprocess service per backend; readiness gated on `/ready`.
- Warm-up requests excluded; median of 3 repeats per cell.
- Concurrency sweep 1/4/16/64 at 300 requests/cell; batch sizes 1/8/32/128.
- Both backends consume byte-identical seeded request streams (the parity
  probe grid) — the comparison is paired.
- Fresh-process RSS probed per backend; nearest-rank percentiles.

## Results

Author run, one laptop (no GPU, one uvicorn worker): the reproduction gate is
exact (**25.4316 vs 25.4316**) and the ONNX parity max-abs is **7.15e-07** on
512 seeded probe rows (tolerance 1e-4). Single-request **p50 1.6 ms** (native/ONNX
p95 **2.0/1.9 ms**, p99 **2.2 ms**; n = **300** requests per cell, nearest-rank) with a
**~950 req/s** knee near concurrency 4 and zero errors in every measured
cell; the explicit batch endpoint reaches **~56k rows/s** at size 128. The
full image measures **6.47 GB**; the smoke-passed ONNX-only slim image is
**291 MB**. Full record in `reports/metrics.json` and
`reports/docker_slim.json`.

## Limits

Numbers, curve shapes, and paired deltas come from one machine with no GPU and
a single worker — the paired harness is the reusable asset, not demonstrated
transfer of those observations. The full image contains unused
CUDA libraries a CPU service never loads; the per-prediction electricity cost
is a declared-assumption estimate (65 W, $0.30/kWh), not a metered bill.

## Tests

Offline, synthetic data only, deterministic; no network, no daemon:

```bash
uv run pytest
```

Parity gate (native vs ONNX on the probe grid), schema 422s, batch == per-row,
harness statistics against fixtures, training-path determinism, and
lint-level Dockerfile/compose contract checks.

## Common errors

| symptom | cause | fix |
|---|---|---|
| `docker compose ... up --build` cannot connect / `cli serve` dies on bind | the Docker daemon is down, or port 8137 is already taken | start the daemon (`open -a Docker` on macOS); free the port (`lsof -nP -iTCP:8137 -sTCP:LISTEN`) or move the service — `serve --port 8138` and `docker run -p 8138:8000`; `cli docker`/`benchmark` record an honest not-measured note when no daemon answers |

## Cost

API cost is $0 (local). The report adds an amortized-electricity estimate —
measured throughput at the committed concurrency-16 basis, declared 65 W system
draw and $0.30 per kWh. This cost basis is distinct from the observed
concurrency-4 throughput knee; assumptions sit next to the number, same framing
as experiment 08.

## Figures

| figure | file |
|---|---|
| backend comparison slope | [reports/figures/backend_comparison_slope.html](reports/figures/backend_comparison_slope.html) |
| batch throughput curve | [reports/figures/batch_throughput_curve.html](reports/figures/batch_throughput_curve.html) |
| footprint cost bars | [reports/figures/footprint_cost_bars.html](reports/figures/footprint_cost_bars.html) |
| latency concurrency lines | [reports/figures/latency_concurrency_lines.html](reports/figures/latency_concurrency_lines.html) |

