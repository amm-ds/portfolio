# 13 Model serving (ONNX, FastAPI): investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- Champion MLP from experiment 12 (25.4316 test MAE re-derived) exported to ONNX behind a parity gate (max-abs 7.2e-07 on 512 seeded rows vs 1e-4 gate); native torch vs ONNX Runtime under seeded paired load: 1.6 ms p50 (p95 2.0, p99 2.2; n = 300 requests per cell), about 950 req/s knee, about 56k rows/s batched, 4,320 requests per backend with zero errors, median of 3 repeats; full image 6.5 GB, slim 291 MB (22.2x smaller); electricity about $0.000012 per 1k predictions from a declared wattage assumption. Single laptop, no GPU, one uvicorn worker. Source: `projects/13-model-serving/story.yaml`; metrics `projects/13-model-serving/reports/metrics.json`, `reports/results.md`.
- Experiment review: hand-rolled load driver; p99 needs an n caveat.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | Closed-loop load generators under-sample slow periods ("coordinated omission"); open-loop (constant arrival rate) tools report higher tails under stalls. A vendor test shows p95 about 67 ms closed vs about 1 s open under a controlled stall (single vendor). Whether our hand-rolled driver is closed or open loop was not established from committed files; the knee at about 950 req/s suggests a rate sweep but I did not confirm. | SEC (blogs); GAP (our driver's loop type) | S46, S47 |
| G2 | Parity practice: PyTorch's verification module defaults to rtol 1e-3 and atol 1e-7; guides advise checking task metrics, saving golden inputs and outputs, and repeating the check on the deployment provider. Our gate is max-abs 1e-4 with 7.2e-07 observed. | SEC (search snippet of PyTorch source; page not fetched) | S45 |
| G3 | Reference stack: no ONNX Runtime Server, Triton or TorchServe comparison; the baselines are the two backends. | GAP (no source needed; a missing arm) | none |
| G4 | Energy and cost basis: same issues as project 08 (scope of power measurement). | SEC | S42, S43 |

## Candidate improvements
**A. Open-loop arrival-rate arm in the existing harness.**
- Method: add a constant-arrival-rate mode (scheduled send times, latency measured from the scheduled time) alongside the current mode; report p50/p95/p99 side by side at 0.5x, 0.9x and 1.1x of the knee. Shows whether tails near the knee are understated.
- Reference: https://artillery.io/blog/load-testing-workload-models (S46); https://dev.to/speed_engineer/coordinated-omission-why-your-load-testing-tool-is-lying-about-your-p99-4p7k (S47). Both blogs; k6 and wrk2 primary docs not read (GAP).
- Cost: compute only, about 1-2 engineering days.
- Stop condition: open-loop and current p99 agree within 10% at all three rates; then say so and stop.

**B. p99 with sample-size caveat and confidence band in the headline table.**
- Method: bootstrap CI of p95 and p99 over the n = 300 requests per cell from committed raw records; no new runs.
- Reference: none primary (GAP); statistical practice.
- Cost: compute only, under 1 day.
- Stop condition: raw per-request latencies not committed.

**C. Reference server arm (ONNX Runtime Server or Triton) on the same payloads.**
- Method: run the same ONNX file behind a standard server; compare p50/p99 and req/s.
- Reference: none primary read (GAP).
- Cost: installs and about 2 days.
- Stop condition: server requires GPU or container runtime not available.

**D. Golden-file regression for parity.**
- Method: store input/output golden pairs and assert on re-export; add task-level check (prediction delta in MAE units).
- Reference: https://pytorch.org/docs/stable/_modules/torch/onnx/verification (S45).
- Cost: under 1 day. A new file; no change to committed parity numbers.
- Stop condition: parity test already asserts tolerance; check before adding.

## Ranked recommendation
1. A (open-loop arm): high value for a serving claim.
2. B (p99 intervals from raw records): near-free.
3. D, then C.

## Queries used (standard, 2026-11-18)
- "ONNX Runtime numerical parity validation exported PyTorch model tolerance best practice"
- "load testing open-loop vs closed-loop coordinated omission latency benchmark k6 locust wrk2"
- "LLM inference energy per token measurement Apple Silicon powermetrics cost per million tokens methodology"
