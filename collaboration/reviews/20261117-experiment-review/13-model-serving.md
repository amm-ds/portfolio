# 13 · Model serving (ONNX, FastAPI): technical review

## Verdict
Strong engineering: a reproduction gate (25.4316 vs 25.4316), a parity gate for ONNX (max-abs 7.15e-07), and paired seeded request streams. Two reporting gaps: no p99 in the headline and a hand-rolled load driver instead of a standard tool.

## Architecture
- Real subprocess per backend, readiness gated on `/ready`, warm-up excluded, median of three repeats per cell. Correct load-test hygiene.
- Both backends consume byte-identical seeded request streams. The paired comparison is the right design.
- Slim ONNX-only image (291 MB) vs full image (6.47 GB, about 3.3 GB unused CUDA). Good, concrete deployment finding.

## Results vs benchmarks and SOTA
- Compared to what: the baselines are the two backends, not a standard serving stack. A reference point would be the same ONNX model on a standard server (ONNX Runtime Server, Triton, or TorchServe) (**verify** versions).
- The copy says the harness is the reusable asset and the numbers are one machine. Keep that.

## Metrics and statistics
- Headline latency is p50 (1.6 ms). Tail latency is what serving reviewers look at. Add p95 and p99 to the headline table with n per cell.
- Median of three repeats per cell with 300 requests per cell gives a p99 from about 300 samples: report it with that caveat.
- Electricity estimate (65 W, $0.30/kWh) is a declared assumption; keep it labelled.

## Code and tests
- 10 test files, offline and deterministic. Good.
- Confirm the parity test asserts the tolerance (1e-4) and fails when it is exceeded.

## Visuals
- `backend_comparison_slope`, `latency_concurrency_lines`, and `batch_throughput_curve` are appropriate. Add p99 bands to the latency figure.

## Copy and articles
- short_version: "~950 req/s knee" and "~56k rows/s batched" are one-machine numbers; keep "one machine" in the same sentence.

## Kimi refinement tasks
1. (major) Add p95 and p99 with n per cell to the headline table and latency figure.
2. (major) Run one standard load tool (for example `locust` or `wrk`) on the top cell and report it beside the harness numbers, or state why not.
3. (minor) Add a test that the parity gate fails above tolerance.
4. (minor) Add a reference point from a standard serving stack (**verify**).
