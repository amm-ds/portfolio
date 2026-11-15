import type { DiagramSpec } from "./types";

// Facts: apps/eval-workbench/{story.yaml,web/README.md,web/src/api/contracts.ts}.
export const EVAL_WORKBENCH_ARCHITECTURE_SPEC = {
  id: "app-eval-workbench-architecture",
  title: "Recorded evaluation → validated views → like-for-like comparison",
  direction: "LR",
  canvasHeight: 400,
  nodes: [
    {
      id: "api",
      label: "FastAPI evaluation records",
      kind: "api",
      facts: [
        "GET /datasets supplies versioned registries, GET /runs supplies summaries, and GET /runs/{id} supplies case-level detail.",
        "The browser is read-only: it neither executes models nor changes expected outputs or recorded metrics.",
      ],
    },
    {
      id: "contracts",
      label: "runtime response validation",
      kind: "gate",
      facts: [
        "TypeScript parsers reject malformed records, unsupported states, non-finite values, and quality scores outside 0–1 before rendering.",
        "Incomplete runs can carry null metrics; they are not silently included in completed-run rankings.",
      ],
    },
    {
      id: "registry",
      label: "versioned dataset registry",
      kind: "data",
      facts: [
        "Selecting a dataset version determines both the available run history and the comparison population.",
        "The provider-free preview labels its small synthetic records as fixtures, not live model-quality evidence.",
      ],
    },
    {
      id: "detail",
      label: "case-level run view",
      kind: "output",
      facts: [
        "Inputs, expected outputs, actual outputs, errors, and latency remain visible behind each aggregate.",
        "A Needs review filter isolates incorrect predictions and execution failures without rewriting the run.",
      ],
    },
    {
      id: "comparison",
      label: "same-dataset comparison",
      kind: "output",
      facts: [
        "Accuracy and F1 use fixed 0–1 axes; p95 latency and cost have separate axes and lower-is-better labels.",
        "Each bar is one run, while an exact table preserves the values and avoids a composite ranking.",
      ],
    },
  ],
  edges: [
    { id: "api-contracts", source: "api", target: "contracts", kind: "result", label: "JSON records" },
    { id: "contracts-registry", source: "contracts", target: "registry", kind: "result", label: "validated datasets" },
    { id: "contracts-detail", source: "contracts", target: "detail", kind: "result", label: "selected run + cases" },
    { id: "contracts-comparison", source: "contracts", target: "comparison", kind: "result", label: "completed runs" },
    { id: "registry-comparison", source: "registry", target: "comparison", kind: "task", label: "same version only" },
  ],
} as const satisfies DiagramSpec;
