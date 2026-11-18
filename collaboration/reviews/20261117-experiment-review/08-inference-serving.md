# 08 · LLM inference and serving: technical review

## Verdict
An honest, reusable benchmark harness on one laptop. The quality guardrail is saturated (1.00 on both checks), so it cannot support any claim about quantization quality. The cost figure needs its assumptions on the card.

## Architecture
- Fixed structured-output task (8 prompts, pydantic `Answer`), temperature 0, bounded output, reasoning disabled per model. Good controlled design.
- Cells over model × concurrency (1/2/4/8), 5 repeats, cooldown between cells. Standard load pattern.
- Engine comparison (llama.cpp vs MLX) with runner verified via `/api/ps`. Careful: the note that no MLX build exists for qwen3.6 is a data point, not a forced comparison. Good.

## Results vs benchmarks and SOTA
- Reports p50/p95/p99, TTFT, and aggregate and per-request tok/s. This matches common serving practice (TTFT, TPOT, throughput).
- Published references for the same model families exist in llama.cpp and MLX community benchmarks (**verify** before citing); the card should say the MLX ≈ 2.9× GGUF result is one machine and one Ollama build.
- Missing: a comparison against a production server (vLLM or similar). Stated as a limit already; keep it prominent.

## Metrics and statistics
- The headline quotes p95 (0.81 s) and median (0.63 s). Report the sample size per cell beside the percentile (40 requests per cell at c=1).
- With 40 requests per cell, p99 is not reliable. Do not quote p99 without the caveat.
- Quality guardrail: schema and keyword checks both tie at 1.00. This shows the task is too easy, not that quantization is harmless. The copy already says so; keep it.
- Electricity cost ($0.12 per 1M output tokens) needs the power and throughput assumptions on the card.

## Code and tests
- 6 test files, the fewest in the set. Add tests for the percentile function (nearest-rank) and the cost calculator.

## Visuals
- `quality_quant` is unreadable on prod and has an empty band (see figure-review handoff). It also shows a saturated check; consider removing it from the visual set or replacing it with a harder task.
- `latency_concurrency` and `engine_panel` are appropriate. Show n on the engine panel.

## Copy and articles
- short_version is accurate. Keep "electricity only".
- Recommend adding one sentence stating the harness's purpose is re-measurement on target hardware, which the copy already says.

## Kimi refinement tasks
1. (major) Make the quality guardrail discriminating: add a harder task or report it as a smoke check only, and drop it from the headline visuals.
2. (major) Put the cost assumptions (power, tok/s, electricity rate) on the card beside the $0.12 figure.
3. (minor) Add unit tests for nearest-rank percentiles and the cost calculator.
4. (minor) Show n per cell on the engine panel.
