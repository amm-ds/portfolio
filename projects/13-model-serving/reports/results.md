# 13 — Model API Serving & Docker Deployment (served LightGBM, UCI Bike Sharing)

## Protocol

Served-model re-derivation: experiment 12's committed v2 recipe (same sha256-pinned UCI hour.csv, same v2 feature contract — timestamp lags, keep-higher-MI pruning —, same seeded LightGBM HPO + final fit, seed 42), scored once on the frozen 8-week test window; reproduction gate |ΔMAE| ≤ params reproduction_tolerance. Serving: native LightGBM vs ONNX Runtime behind one FastAPI service, warmed at startup; parity gate on a seeded probe grid (max-abs on the raw prediction, plus a float32 relative term) before any serving stage may run. Benchmark: real subprocess service per backend, warm-up excluded, ~300 requests per concurrency cell (1/4/16/64), median of 3 repeats, batch sizes 1/8/32/128, fresh-process RSS probes, byte-identical seeded payload streams. Docker: multi-stage build from the repo-root context, model baked in, image size + layer breakdown measured with the daemon, compose smoke against /health /ready /predict.

## Served model + gates

- Reproduction: derived test MAE 23.7636 vs committed 23.7636 (|Δ| = 0).
- Parity: max-abs 0.000265 rentals on 512 probe rows (tolerance 0.0001 + rel term, limit 0.00679, opset 15).

## Concurrency sweep

| backend | concurrency | p50 s | p95 s | p99 s | throughput req/s | errors |
|---|---|---|---|---|---|---|
| native | 1 | 0.0020 | 0.0029 | 0.0036 | 451.5 | 0/300 |
| native | 4 | 0.0037 | 0.0047 | 0.0053 | 1012.2 | 0/300 |
| native | 16 | 0.0265 | 0.0744 | 0.1016 | 468.3 | 0/300 |
| native | 64 | 0.0685 | 0.2550 | 0.3634 | 606.4 | 0/300 |
| onnx | 1 | 0.0024 | 0.0084 | 0.0122 | 237.4 | 0/300 |
| onnx | 4 | 0.0069 | 0.0109 | 0.0130 | 528.2 | 0/300 |
| onnx | 16 | 0.0356 | 0.1320 | 0.1795 | 316.9 | 0/300 |
| onnx | 64 | 0.1255 | 0.4782 | 0.7405 | 332.0 | 0/300 |

## Batch curve

| backend | batch size | p50 s/request | throughput rows/s | errors |
|---|---|---|---|---|
| native | 1 | 0.0543 | 428.7 | 0/60 |
| native | 8 | 0.0610 | 3974.6 | 0/60 |
| native | 32 | 0.0648 | 13644.9 | 0/60 |
| native | 128 | 0.2127 | 28223.2 | 0/60 |
| onnx | 1 | 0.0851 | 382.0 | 0/60 |
| onnx | 8 | 0.0592 | 4431.8 | 0/60 |
| onnx | 32 | 0.0507 | 19209.4 | 0/60 |
| onnx | 128 | 0.1071 | 40871.6 | 0/60 |

## Footprint + cost

| item | native | onnx |
|---|---|---|
| fresh-process RSS (MB, median of probes) | 213 | 113 |
| cost per 1k predictions (USD, declared 65 W / $0.30 per kWh) | 0.000012 | 0.000017 |
| docker image total (MB, measured) | 1060 | base 145 + venv 983 + model 2.0 |

## Docker

Image `portfolio-model-serving:13` total 1060 MB (base 145 + venv 983 + model 2.0); compose smoke passed: True. ONNX-only slim image `portfolio-model-serving:13-slim` total 292 MB; readiness/prediction smoke passed: True.

## Limits

- Single laptop, no GPU, one uvicorn worker, one model: absolute numbers, paired native-vs-ONNX deltas, and curve shapes are host-specific observations, not demonstrated transfer; re-measure with the paired harness.
- The load driver runs on the same machine as the service — localhost latency has no network term, and the CPU is shared between driver and service under high concurrency.
- Fresh-process RSS is the steady state after warm-up, not a peak under load; the image size is the uncompressed on-disk total.
- Cost per 1k predictions uses measured throughput with a declared 65 W system draw (no wall meter) and $0.30 per kWh — an assumption, stated next to the number, not a measurement.

Figures: `reports/figures/` (JSON + HTML). Full record: `reports/metrics.json`, `reports/evaluation_metadata.json`, `reports/train_run.json`, `data/bench_run.json`, `reports/docker_run.json`.
