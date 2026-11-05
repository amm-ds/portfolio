import type { DiagramSpec } from "./types";

// Facts: projects/12-tabular-ml-lifecycle/{README.md,reports/metrics.json}.
export const LIFECYCLE_PIPELINE_SPEC = {
  id: "12-lifecycle-pipeline",
  title: "One pipeline, six stages: pinned ingest to scored-once test",
  direction: "LR",
  canvasHeight: 300,
  nodes: [
    {
      id: "ingest",
      label: "Pinned ingest + DQ gates",
      kind: "source",
      facts: [
        "UCI Bike Sharing hour.csv: 17,379 hourly rows, 2011–2012.",
        "26 DQ checks; the 165 missing hours (~1%) are bounded by a 2% gate.",
      ],
    },
    {
      id: "split",
      label: "Time split",
      kind: "gate",
      facts: [
        "Train 14,523 / validation 1,344 / test 1,344 — the final 8 weeks scored once.",
        "No choice ever touches the test window.",
      ],
    },
    {
      id: "features",
      label: "Leakage-safe features + selection",
      kind: "tool",
      facts: [
        "Cyclical hour/weekday/month + lags 1h/24h/168h, past-only positional shifts.",
        "Mutual information ranks the three lags first; atemp is pruned at r = 0.987 by rule.",
      ],
    },
    {
      id: "ladder",
      label: "Seeded ladder",
      kind: "model",
      facts: [
        "Seasonal naive → ridge → random forest → LightGBM (50 Optuna trials) → PyTorch MLP.",
        "Champion MLP: 25.4 test MAE / 39.3 RMSE, chosen by validation MAE (34.2).",
      ],
    },
    {
      id: "test",
      label: "Scored-once test",
      kind: "gate",
      facts: [
        "One pass per candidate on the frozen 1,344-row window.",
        "The test column is evidence, never a selector.",
      ],
    },
    {
      id: "ci",
      label: "Bootstrap CI",
      kind: "output",
      facts: [
        "Champion beats the 83.2 floor by 57.8 rentals/hour on average.",
        "95% paired CI [52.5, 63.1] over 2,000 resamples — excludes zero.",
      ],
    },
  ],
  edges: [
    { id: "ingest-split", source: "ingest", target: "split", kind: "task", label: "DQ pass" },
    { id: "split-features", source: "split", target: "features", kind: "task", label: "train rows" },
    { id: "features-ladder", source: "features", target: "ladder", kind: "task", label: "fit + select" },
    { id: "ladder-test", source: "ladder", target: "test", kind: "result", label: "champion" },
    { id: "test-ci", source: "test", target: "ci", kind: "result", label: "paired resamples" },
  ],
} as const satisfies DiagramSpec;
