import type { DiagramSpec } from "./types";

// Facts: projects/03-anomaly-detection/{README.md,reports/metrics.json}.
export const DETECTION_PIPELINE_SPEC = {
  id: "03-detection-pipeline",
  title: "Fixed-budget alerting over NAB telemetry",
  direction: "LR",
  canvasHeight: 420,
  nodes: [
    {
      id: "nab",
      label: "NAB telemetry",
      kind: "source",
      facts: [
        "12 labelled series — AWS CloudWatch, traffic, known-cause failures.",
        "9 of 12 series evaluable; 3 all-train series are excluded, not scored as misses.",
      ],
    },
    {
      id: "synthetic",
      label: "Synthetic stream",
      kind: "source",
      facts: [
        "Seeded CI path: 20,000 minutes at a 2% anomaly rate, seed 42.",
        "Demonstrates mechanics only — its injected anomalies are trivially separable.",
      ],
    },
    {
      id: "features",
      label: "Rolling features",
      kind: "tool",
      facts: [
        "Rolling mean/std per signal over windows [10, 60] minutes.",
        "Warm-up rows are dropped so the scoring matrix is complete.",
      ],
    },
    {
      id: "detector",
      label: "IsolationForest scores",
      kind: "model",
      facts: [
        "Fit on the first 70% of the timeline only; tuned on train-side validation.",
        "Pointwise PR-AUC 0.527 overall on the nine evaluable series.",
      ],
    },
    {
      id: "threshold",
      label: "Top-2% train threshold",
      kind: "gate",
      facts: [
        "Alert budget fixed a priori at 2% from the train window — never tuned on test.",
        "Raw stream: 1,609 alerts touching 16 of 17 labelled windows.",
      ],
    },
    {
      id: "budget",
      label: "Dedup + 24 h page cap",
      kind: "tool",
      facts: [
        "Contiguous runs fire one page at the run's max-score minute.",
        "1,609 alerts become 80 pages; range-F1 0.157 → 0.315.",
      ],
    },
    {
      id: "scoring",
      label: "Event-aware scoring",
      kind: "output",
      facts: [
        "16 of 17 windows touched; overlap-weighted range recall 0.729.",
        "Range precision 0.107 — the false-positive firehose is the open wall.",
      ],
    },
  ],
  edges: [
    { id: "nab-features", source: "nab", target: "features", kind: "task", label: "series" },
    { id: "synthetic-features", source: "synthetic", target: "features", kind: "task", label: "CI path" },
    { id: "features-detector", source: "features", target: "detector", kind: "task", label: "fit" },
    { id: "detector-threshold", source: "detector", target: "threshold", kind: "result", label: "scores" },
    { id: "threshold-budget", source: "threshold", target: "budget", kind: "task", label: "raw stream" },
    { id: "budget-scoring", source: "budget", target: "scoring", kind: "result", label: "pages" },
  ],
} as const satisfies DiagramSpec;
