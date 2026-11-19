# 08 LLM inference and serving: investigation

Date: 2026-11-19 (searches on 2026-11-18). Labels: SB / SEC / GAP. Source IDs map to `99-sources.md`.

## Current state (committed)
- One laptop, five serving setups, 19 cells, 760 requests, zero failures; 4-bit MoE 0.81 s p95 (0.63 s median) at about $0.12 per 1M output tokens (electricity only); reasoning disabled before committed runs; percentiles re-derived from the raw record. Source: `projects/08-inference-serving/story.yaml`; metrics `projects/08-inference-serving/reports/metrics.json`.
- Quality guardrail saturated (1.00 on schema and keyword checks) so it cannot support a quantization-quality claim (experiment review `collaboration/reviews/20261117-experiment-review/08-inference-serving.md`). About 40 requests per cell at c=1, so p99 is unreliable.
- Roadmap "next": prove values on shipping hardware; MLX build for the MoE.

## Gaps against the state of the art
| # | Gap | Label | Source |
|---|---|---|---|
| G1 | Serving metrics now centre on TTFT, TPOT/inter-token latency, tail percentiles and goodput (rate at which a set share of requests meets TTFT and TPOT SLOs). TPOT definitions differ by tool (GuideLLM vs vLLM claimed); not confirmed in primary docs. | SEC | S41 |
| G2 | Quantization quality: 4-bit effects depend on model size; mixed-precision variants hold up better; no rigorous recent MLX-vs-GGUF study with MMLU and perplexity found. | SEC (general), GAP (MLX vs GGUF) | S44 |
| G3 | Energy and cost basis: package power, whole-SoC power and assumed system power give different numbers; GreenBench (Apple Silicon) uses package power and an assumed 10 W system figure; energy per token = average power x decode time / decode tokens. Idle and amortisation usually omitted. | SEC | S42, S43 |
| G4 | No production-server comparison (vLLM or similar); stated as a limit already. Whether a comparable vLLM run exists on Apple Silicon: GAP. | GAP | none |

## Candidate improvements
**A. Replace the saturated guardrail with a held-out quality check that can move.**
- Method: add a harder fixed task set (for example 30-50 items with graded rubrics or exact-answer checks) and report accuracy per arm with Wilson CIs; the point is to give the quantization comparison a score that is not at ceiling. Local only, no hosted calls.
- Reference: lm-evaluation-harness is the tool named in guides (S44, SEC); primary docs not read (GAP).
- Cost: compute (local inference time per arm), about 1-2 days.
- Stop condition: all arms still at ceiling; report that the arms are indistinguishable on that set, do not claim harmlessness.

**B. Goodput and SLO view of the existing raw records.**
- Method: re-derive goodput (share of requests meeting a declared TTFT and per-token SLO) from committed raw records at each concurrency; no new runs.
- Reference: https://www.cncf.io/blog/2026/07/20/why-goodput-matters-more-than-throughput-for-llm-serving/ (S41; blog, SEC).
- Cost: compute only, under 1 day.
- Stop condition: raw records lack per-token timings; then report TTFT only.

**C. Energy measurement with a stated power scope.**
- Method: on the next hardware run, log package power with `powermetrics` per cell, report J/token with the scope (package, SoC, assumed system) beside the figure and keep the existing $0.12 as a labelled assumption-based number.
- Reference: https://arxiv.org/pdf/2608.28667 (S42); https://arxiv.org/pdf/2603.23640 (S43).
- Cost: needs sudo and a quiet-hardware run; about 1 day on the laptop. Owner action.
- Stop condition: power sampling disturbs latency by more than the arm-to-arm gap.

**D. Add a vLLM or llama.cpp-server reference arm on hardware where it runs.**
- Method: wait for target hardware (roadmap); same harness.
- Reference: S41 for SLO definitions.
- Cost: hardware access.
- Stop condition: no target hardware.

## Ranked recommendation
1. A (quality check that can move): high value for the quantization story.
2. B (goodput view from raw records): near-free.
3. C (energy scope), then D.

## Queries used (standard, 2026-11-18)
- "LLM inference benchmarking methodology TTFT TPOT goodput tail latency vLLM guidellm"
- "quantized LLM quality evaluation 4-bit MLX GGUF perplexity MMLU degradation lm-evaluation-harness"
- "LLM inference energy per token measurement Apple Silicon powermetrics cost per million tokens methodology"
