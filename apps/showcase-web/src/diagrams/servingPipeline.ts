import type { DiagramSpec } from "./types";

// Facts: projects/13-model-serving/{README.md,reports/metrics.json}.
export const SERVING_PIPELINE_SPEC = {
  id: "13-serving-pipeline",
  title: "From committed recipe to measured container",
  direction: "LR",
  canvasHeight: 320,
  nodes: [
    {
      id: "rederive",
      label: "Re-derive champion",
      kind: "tool",
      facts: [
        "Experiment 12's MLP re-derived bit-for-bit from the committed recipe + seed.",
        "Reproduced test MAE 25.4316 exactly.",
      ],
    },
    {
      id: "onnx",
      label: "ONNX export + parity gate",
      kind: "gate",
      facts: [
        "Probe grid: native vs ONNX max-abs difference 7.2e-07.",
        "The export must compute the same function before any serving.",
      ],
    },
    {
      id: "serve",
      label: "Serve · two backends",
      kind: "api",
      facts: [
        "FastAPI POST /predict: pydantic bounds, 422 on malformed, request_id on every response.",
        "Native state_dict vs warmed ONNX Runtime behind one backend flag.",
      ],
    },
    {
      id: "loadtest",
      label: "Paired load test",
      kind: "tool",
      facts: [
        "Byte-identical seeded request streams — the comparison is paired.",
        "1.7 ms p50 and ~950 req/s at the concurrency knee (committed harness).",
      ],
    },
    {
      id: "container",
      label: "Measured container",
      kind: "output",
      facts: [
        "Multi-stage image: 6.5 GB, non-root user, healthcheck-gated readiness.",
        "A compose smoke test runs against the built image before it ships.",
      ],
    },
  ],
  edges: [
    { id: "rederive-onnx", source: "rederive", target: "onnx", kind: "task", label: "export" },
    { id: "onnx-serve", source: "onnx", target: "serve", kind: "result", label: "gate passed" },
    { id: "serve-loadtest", source: "serve", target: "loadtest", kind: "task", label: "seeded stream" },
    { id: "loadtest-container", source: "loadtest", target: "container", kind: "result", label: "bake" },
  ],
} as const satisfies DiagramSpec;
