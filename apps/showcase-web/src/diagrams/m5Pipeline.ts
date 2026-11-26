import type { DiagramSpec } from "./types";

// Facts: projects/02-demand-forecasting/{README.md,reports/metrics.json}.
export const M5_PIPELINE_SPEC = {
  id: "02-m5-pipeline",
  title: "Full M5 panel to one screened ensemble forecast",
  direction: "LR",
  canvasHeight: 300,
  nodes: [
    {
      id: "panel",
      label: "M5 full panel",
      kind: "source",
      facts: [
        "30,490 daily store-item series × 1,969 days, 2011-01-29..2016-06-19.",
        "59.5% of panel days are zero-demand; 91% of series are intermittent.",
      ],
    },
    {
      id: "features",
      label: "Leakage-safe features",
      kind: "tool",
      facts: [
        "Lags 1/7/14/21/28 and rolling means/stds are shifted per series — never the current row.",
        "Price, SNAP and event codes join the calendar features.",
      ],
    },
    {
      id: "candidates",
      label: "8 candidates",
      kind: "model",
      facts: [
        "Seasonal-naive floor, global LightGBM + Tweedie twin, three pooled fits, per-series AutoETS.",
        "Pooled fits: one per store (10 groups), per store×category (30), per department (7).",
      ],
    },
    {
      id: "screen",
      label: "Stability screen · 9 selection origins",
      kind: "gate",
      facts: [
        "Best three of the six-candidate pool by mean + 1.0×population std of per-origin WRMSSE.",
        "Selection reads the 9 selection origins only — never the test origin.",
      ],
    },
    {
      id: "ensemble",
      label: "Convex ensemble",
      kind: "model",
      facts: [
        "Weights 0.95 store×category / 0.00 store / 0.05 department on a 0.05 simplex grid.",
        "Champion official WRMSSE 0.6211 — a −30.4% cut vs the 0.8929 seasonal-naive floor.",
      ],
    },
    {
      id: "test",
      label: "Final 28 days · headline + disclosed reread",
      kind: "gate",
      facts: [
        "The competition window from 2016-05-22 supplies the champion headline; a later rejected challenger reread it.",
        "Official hierarchical WRMSSE across all 42,840 revenue-weighted nodes.",
      ],
    },
  ],
  edges: [
    { id: "panel-features", source: "panel", target: "features", kind: "task", label: "shift per series" },
    { id: "features-candidates", source: "features", target: "candidates", kind: "task", label: "fit 8 arms" },
    { id: "candidates-screen", source: "candidates", target: "screen", kind: "result", label: "per-origin WRMSSE" },
    { id: "screen-ensemble", source: "screen", target: "ensemble", kind: "task", label: "best three" },
    { id: "ensemble-test", source: "ensemble", target: "test", kind: "result", label: "champion headline" },
  ],
} as const satisfies DiagramSpec;
