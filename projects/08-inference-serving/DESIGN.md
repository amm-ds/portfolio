# DESIGN — LLM Inference & Serving

## Requirements

- Benchmark LLM **serving**, not modeling: latency percentiles, throughput,
  TTFT, structured-output reliability, and cost per token, measured on the
  portfolio's real serving stack (local Ollama, ADR-0004).
- Fixed, bounded task (validated pydantic schema, 8 fixed prompts, bounded
  output tokens) so numbers are comparable across models, quantizations,
  engines, and concurrency levels.
- Apple Silicon engine comparison: Ollama's default llama.cpp runner vs its
  MLX runner, using the exact mechanism this Ollama build provides.
- Offline-testable harness (fake-server integration tests); live runs are
  Ollama-gated, like every other LLM project in this portfolio.
- Reproducible: DVC stages, params.yaml mirrors the pydantic config.

## Options considered

### Serving surface: raw llama.cpp server vs Ollama

- **Raw llama.cpp server** (`llama-server`): maximal control (per-slot
  batching flags, `--parallel`, KV-cache types), but we would own model
  lifecycle, template handling, and client glue — a second serving stack to
  build, version, and keep honest.
- **Ollama's OpenAI-compatible endpoint** (`http://localhost:11434/v1`): the
  platform's already-standardized serving layer (ADR-0004, `build_model()`).
  Multi-model scheduler, MLX runner integration, `json_schema`
  response_format, and `/api/ps` runner introspection come for free.

### Engine selection mechanism (what this Ollama actually supports)

Detected empirically on Ollama **0.40.4** (macOS app, Apple Silicon):

- The runner is **auto-selected from the model artifact**: GGUF manifests run
  on the llama.cpp runner; safetensors MLX builds run on the MLX runner.
  Verified via the `RUNNER` column of `ollama ps` and `/api/ps` (the harness
  records this at run time).
- There is **no `OLLAMA_RUNNER` env override** in this build (verified against
  the binary's env-var table; MLX variants are selected by pulling `-mlx`
  tags, e.g. `gemma4:31b-mlx`, whose manifests carry runner metadata).
- MLX builds do not exist for every model: the registry has **no MLX tag for
  `qwen3.6:35b-a3b`** (consistent with the earlier wave-10 attempt that failed
  with "missing switch expert weights"). Such cases are recorded as data
  points with reasons, never forced.

### Concurrency driver

- `asyncio` + `httpx` streaming client against `/v1/chat/completions`, with a
  semaphore for concurrency levels 1/2/4/8. This measures the serving stack
  end-to-end (queueing + scheduling included), which is what production sees.

## Decision

**Benchmark Ollama as the serving layer; do not build a gateway.** The
OpenAI-compatible endpoint is the same surface every other portfolio project
uses via `build_model()`; a bespoke FastAPI/llama.cpp wrapper would add moving
parts without adding measurement value, and would diverge from ADR-0004.

Engine comparison is done **within Ollama's own runner selection**: same model
family pulled as GGUF (llama.cpp) vs MLX safetensors, at concurrency 1, with
the quant difference (Q8_0 vs 4-bit) explicitly labelled as a confound —
the registry offers no same-quant cross-runner pair for these models.

## Cost accounting (declared assumptions)

- API cost is **$0** (local inference, data never leaves the machine).
- Electricity is amortized honestly: measured aggregate tok/s × declared
  system draw (100 W) × flat residential price ($0.30/kWh). These are
  declared assumptions, not measurements — labelled as such in the report.
- Cloud equivalents use a **hypothetical, labelled rate card** ($/1M output
  tokens) for context only; they are not quotes.

## Changelog

- **Wave 13** — initial working build: async harness over Ollama
  `/v1/chat/completions` with `json_schema` structured output; per-model
  `reasoning_effort` knob (qwen3.6 needs `none`, gpt-oss needs `low`) so the
  bench measures bounded structured decode; runner auto-detection via
  `/api/ps`; llama.cpp-vs-MLX panel on gemma4:31b; quality-vs-quant on
  gemma4:31b Q8_0 vs QAT-int4 (same runner); offline tests incl. fake-server
  integration via httpx ASGITransport.
