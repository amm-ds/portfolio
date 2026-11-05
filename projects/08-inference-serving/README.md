# LLM Inference & Serving

**Working showcase.** The portfolio's LLM inference & serving benchmark: an
async load driver measures the real serving stack (local Ollama,
ADR-0004 — no redundant gateway, see [DESIGN.md](DESIGN.md)) across models,
quantizations, runners (llama.cpp vs MLX on Apple Silicon), and concurrency
levels, on a fixed structured-output task with validated schemas.

- Problem: what do latency percentiles, throughput, structured-output
  reliability, and cost per token actually look like on a local serving stack?
- Design: [DESIGN.md](DESIGN.md)
- Story: [story.yaml](story.yaml) (served at `/projects/08-inference-serving/story`)

## Benchmark design

- **Fixed task**: every request must return a validated pydantic `Answer`
  (one-sentence answer + confidence in [0,1] + citation) over 8 fixed prompts,
  `temperature 0`, bounded output tokens (`max_tokens`), reasoning disabled
  (`reasoning_effort: none`; gpt-oss needs `low` — per-model override).
- **Cells**: (model, concurrency) with concurrency 1/2/4/8 via asyncio
  semaphore, 5 repeats of the prompt suite per cell, cooldown between cells.
  Metrics per cell: p50/p95/p99 latency (nearest-rank), TTFT, aggregate +
  per-request output tok/s, schema-valid rate, keyword quality rate, failures.
- **Engines**: llama.cpp (GGUF) vs MLX (safetensors). This Ollama build
  auto-selects the runner from the artifact — verified via `/api/ps` `runner`
  (no `OLLAMA_RUNNER` env exists here; MLX comes from `-mlx` tags). No MLX
  build exists for qwen3.6 — recorded as a data point, not forced.
- **Models**: qwen3.6:35b-a3b-q4_K_M (MoE), gemma4:31b (dense, MLX),
  gpt-oss:20b (MXFP4); `--full` adds qwen3:32b (dense baseline),
  gemma4:31b-it-q8_0 / -qat (quality-vs-quant on the same runner) and
  gemma4:31b-it-q8_0 vs gemma4:31b-mlx (engine panel; quant confounded).

## CLI

```bash
uv run python -m inference_serving.cli prepare   # materialize data/prompts.json
uv run python -m inference_serving.cli bench      # bounded run (<45 min target)
uv run python -m inference_serving.cli bench --full  # all arms
uv run python -m inference_serving.cli report     # offline figures + report.html
```

`bench` needs a live Ollama with the models pulled; `report` is offline.
DVC: `prepare → bench (--full) → report` (`dvc.yaml`).

The raw full-grid record behind the committed aggregates is versioned at
`data/bench_run.json` (760 requests, 2026-10-15; narrow ignore exception,
force-added like the 02 sidecar), so the published percentiles can be
re-aggregated with `report` without re-running hours of local inference.

## Results

Author run, one laptop (Apple Silicon): 19 cells / 760 requests / 0 failures.
**MLX ≈ 2.9× GGUF tok/s** on the same models; a 4-bit mixture-of-experts model
answers in 0.81 s per request at about $0.12 per 1M output tokens
(electricity only). Aggregates in `reports/metrics.json`; the re-aggregable
record in `data/bench_run.json`.

## Limits

Numbers are hardware-specific — one machine, one Ollama build — so the
reusable asset is the harness for re-measuring any stack on target hardware,
not the constants. 4-bit quantization costs serving headroom, not
structured-output validity; no MLX build exists for qwen3.6 (recorded as a
data point, not forced).

## Tests

Offline only: percentile/tok-s math from fixture records, output validation,
config/params round-trip, and a fake-server integration test (stub ASGI
mimicking Ollama's streaming endpoint via httpx ASGITransport) covering the
full request→SSE-parse→aggregate→BenchRun path.

```bash
uv run pytest projects/08-inference-serving/tests
```

## Common errors

| symptom | cause | fix |
|---|---|---|
| `bench` fails with a connection error or "model not found" | it drives a live Ollama — the daemon must run and the cell models must be pulled | start Ollama, then `ollama pull qwen3.6:35b-a3b-q4_K_M`, `ollama pull gemma4:31b`, `ollama pull gpt-oss:20b` (`--full` adds the remaining arms); `report` stays offline |

## Cost

API cost is $0 (local). The report adds an amortized-electricity estimate
(measured tok/s, declared 100 W / $0.30-per-kWh assumptions) and a labelled
hypothetical cloud rate card per 1M output tokens.
