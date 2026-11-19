# Open-loop (constant-arrival) arm

Generated: 2026-11-19T14:29:04.905016+00:00 · rates [50, 100, 200] req/s · 300 requests per cell · both backends.

| backend | rate (req/s) | p50 (s) | p95 (s) | p99 (s) | p99 95% CI | errors |
|---|---|---|---|---|---|---|
| native | 50 | 0.0024 | 0.0038 | 0.0073 | [0.0061, 0.0088] | 0/300 |
| native | 100 | 0.0017 | 0.0020 | 0.0022 | [0.0020, 0.0022] | 0/300 |
| native | 200 | 0.0016 | 0.0020 | 0.0023 | [0.0021, 0.0024] | 0/300 |
| onnx | 50 | 0.0023 | 0.0028 | 0.0032 | [0.0031, 0.0033] | 0/300 |
| onnx | 100 | 0.0016 | 0.0020 | 0.0021 | [0.0020, 0.0021] | 0/300 |
| onnx | 200 | 0.0014 | 0.0018 | 0.0020 | [0.0019, 0.0022] | 0/300 |

Offered load is fixed by the schedule; above the service's capacity, latency inflates rather than the client backing off (the closed-loop concurrency cells measure that side). New files only; existing load reports untouched.
