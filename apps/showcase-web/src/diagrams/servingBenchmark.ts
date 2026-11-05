import type { DiagramSpec } from "./types";

// Facts: projects/08-inference-serving/{README.md,reports/metrics.json}.
export const SERVING_BENCHMARK_SPEC = {
  id: "08-serving-benchmark",
  title: "Prompts to committed records: the serving benchmark harness",
  direction: "LR",
  canvasHeight: 380,
  nodes: [
    {
      id: "suite",
      label: "Fixed task suite",
      kind: "source",
      facts: [
        "8 general-knowledge prompts, each with a keyword checklist.",
        "Every request must return a validated Answer schema: sentence, confidence, citation.",
      ],
    },
    {
      id: "envelope",
      label: "Identical request envelope",
      kind: "tool",
      facts: [
        "Temperature 0, bounded output tokens, reasoning disabled — every call.",
        "Model tag and concurrency rung recorded per request.",
      ],
    },
    {
      id: "driver",
      label: "Async load driver",
      kind: "agent",
      facts: [
        "asyncio semaphore sweeps concurrency 1/2/4/8 with cooldown between cells.",
        "Streaming httpx against the local endpoint — no gateway in the path.",
      ],
    },
    {
      id: "ollama",
      label: "Local Ollama 0.40.4",
      kind: "api",
      facts: [
        "chat completions + json_schema; the runner auto-selects llama.cpp vs MLX.",
        "Five serving setups: qwen3.6:35b MoE, gemma4:31b dense + quants, gpt-oss:20b.",
      ],
    },
    {
      id: "record",
      label: "Per-request record",
      kind: "data",
      facts: [
        "Latency, TTFT, aggregate + per-request tok/s, quality, failures per request.",
        "760 requests committed in data/bench_run.json — re-aggregable offline.",
      ],
    },
    {
      id: "cells",
      label: "Cell aggregates",
      kind: "data",
      facts: [
        "Each cell is model × concurrency, 40 requests.",
        "Nearest-rank p50/p95/p99, schema-valid rate, keyword quality rate.",
      ],
    },
    {
      id: "reports",
      label: "Committed reports",
      kind: "output",
      facts: [
        "19 cells, zero failures in the committed full run.",
        "metrics.json, report.html and figures re-derive from the raw record without re-running.",
      ],
    },
  ],
  edges: [
    { id: "suite-envelope", source: "suite", target: "envelope", kind: "task", label: "prompt + schema" },
    { id: "envelope-driver", source: "envelope", target: "driver", kind: "task", label: "bounded request" },
    { id: "driver-ollama", source: "driver", target: "ollama", kind: "task", label: "POST /v1/chat/completions" },
    { id: "ollama-record", source: "ollama", target: "record", kind: "result", label: "stream" },
    { id: "record-cells", source: "record", target: "cells", kind: "result", label: "aggregate" },
    { id: "cells-reports", source: "cells", target: "reports", kind: "result", label: "publish" },
  ],
} as const satisfies DiagramSpec;
