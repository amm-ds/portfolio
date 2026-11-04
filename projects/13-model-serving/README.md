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

## Benchmark design

- Real subprocess service per backend; readiness gated on `/ready`.
- Warm-up requests excluded; median of 3 repeats per cell.
- Concurrency sweep 1/4/16/64 at 300 requests/cell; batch sizes 1/8/32/128.
- Both backends consume byte-identical seeded request streams (the parity
  probe grid) — the comparison is paired.
- Fresh-process RSS probed per backend; nearest-rank percentiles.

## Tests

Offline, synthetic data only, deterministic; no network, no daemon:

```bash
uv run pytest
```

Parity gate (native vs ONNX on the probe grid), schema 422s, batch == per-row,
harness statistics against fixtures, training-path determinism, and
lint-level Dockerfile/compose contract checks.

## Cost

API cost is $0 (local). The report adds an amortized-electricity estimate —
measured throughput at the concurrency knee, declared 65 W system draw and
$0.30 per kWh, assumptions stated next to the number, same framing as
experiment 08.
