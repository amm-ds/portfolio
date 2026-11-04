# 13 — Model API Serving & Docker Deployment (champion MLP, UCI Bike Sharing)

## Protocol

Champion re-derivation: experiment 12's committed recipe (same sha256-pinned UCI hour.csv, same feature contract, same MLP architecture + hyperparameters, seed 42), scored once on the frozen 8-week test window; reproduction gate |ΔMAE| ≤ params reproduction_tolerance. Serving: native torch vs ONNX Runtime behind one FastAPI service, warmed at startup; parity gate on a seeded probe grid (max-abs, standardized-y space) before any serving stage may run. Benchmark: real subprocess service per backend, warm-up excluded, ~300 requests per concurrency cell (1/4/16/64), median of 3 repeats, batch sizes 1/8/32/128, fresh-process RSS probes, byte-identical seeded payload streams. Docker: multi-stage build from the repo-root context, model baked in, image size + layer breakdown measured with the daemon, compose smoke against /health /ready /predict.

## Champion + gates

- Reproduction: derived test MAE 25.4316 vs committed 25.4316 (|Δ| = 0).
- Parity: max-abs 7.15e-07 on 512 probe rows (tolerance 0.0001, opset 17).

## Concurrency sweep

| backend | concurrency | p50 s | p95 s | p99 s | throughput req/s | errors |
|---|---|---|---|---|---|---|
| native | 1 | 0.0016 | 0.0020 | 0.0022 | 594.6 | 0/300 |
| native | 4 | 0.0040 | 0.0051 | 0.0057 | 932.5 | 0/300 |
| native | 16 | 0.0252 | 0.0710 | 0.1175 | 470.1 | 0/300 |
| native | 64 | 0.0654 | 0.2491 | 0.3336 | 628.3 | 0/300 |
| onnx | 1 | 0.0016 | 0.0019 | 0.0022 | 612.2 | 0/300 |
| onnx | 4 | 0.0039 | 0.0047 | 0.0057 | 969.9 | 0/300 |
| onnx | 16 | 0.0261 | 0.0662 | 0.0949 | 469.8 | 0/300 |
| onnx | 64 | 0.0631 | 0.2098 | 0.2909 | 714.9 | 0/300 |

## Batch curve

| backend | batch size | p50 s/request | throughput rows/s | errors |
|---|---|---|---|---|
| native | 1 | 0.0530 | 577.2 | 0/60 |
| native | 8 | 0.0586 | 4424.5 | 0/60 |
| native | 32 | 0.0598 | 16796.6 | 0/60 |
| native | 128 | 0.0623 | 55806.3 | 0/60 |
| onnx | 1 | 0.0651 | 513.1 | 0/60 |
| onnx | 8 | 0.0485 | 5104.4 | 0/60 |
| onnx | 32 | 0.0510 | 18673.9 | 0/60 |
| onnx | 128 | 0.0653 | 57451.3 | 0/60 |

## Footprint + cost

| item | native | onnx |
|---|---|---|
| fresh-process RSS (MB, median of probes) | 298 | 318 |
| cost per 1k predictions (USD, declared 65 W / $0.30 per kWh) | 0.000012 | 0.000012 |
| docker image total (MB, measured) | 6466 | base 145 + venv 6192 + model 1.0 |

## Docker

Image `portfolio-model-serving:13` total 6466 MB (base 145 + venv 6192 + model 1.0); compose smoke passed: True.

## Limits

- Single laptop, no GPU, one uvicorn worker, one model: absolute numbers do not transfer; the paired native-vs-ONNX deltas and the shape of the curves are the transferable read.
- The load driver runs on the same machine as the service — localhost latency has no network term, and the CPU is shared between driver and service under high concurrency.
- Fresh-process RSS is the steady state after warm-up, not a peak under load; the image size is the uncompressed on-disk total.
- Cost per 1k predictions uses measured throughput with a declared 65 W system draw (no wall meter) and $0.30 per kWh — an assumption, stated next to the number, not a measurement.

Figures: `reports/figures/` (JSON + HTML). Full record: `reports/metrics.json`, `reports/evaluation_metadata.json`, `reports/train_run.json`, `data/bench_run.json`, `reports/docker_run.json`.
