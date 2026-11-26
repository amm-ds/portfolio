import type { DiagramSpec } from "./types";

// Facts: projects/15-dynamic-pricing-rl/{story.yaml,reports/metrics.json}.
export const PRICING_PIPELINE_SPEC = {
  id: "15-pricing-pipeline",
  title: "Calibrate, train safely, test once",
  direction: "LR",
  canvasHeight: 320,
  nodes: [
    {
      id: "calibrate",
      label: "Calibrate from M5",
      kind: "source",
      facts: [
        "600 M5 series supply demand, weekday shares and reference prices.",
        "Price response is an assumed elasticity prior, not learned from M5.",
      ],
    },
    {
      id: "train",
      label: "Train with action masks",
      kind: "model",
      facts: [
        "MaskablePPO sees 14 days of price and demand history.",
        "An action mask blocks every illegal price move during training and prediction.",
      ],
    },
    {
      id: "lock",
      label: "Lock tuned B1",
      kind: "gate",
      facts: [
        "Static B1 picks a 1.30× price on train episodes and is locked before the sealed read.",
        "P1 needs RL to beat B1 by at least 1.0% with a paired CI above zero.",
      ],
    },
    {
      id: "test",
      label: "One sealed test",
      kind: "gate",
      facts: [
        "1,000 test episodes plus two 500-episode stress sets, read once.",
        "0 constraint violations for every executable policy.",
      ],
    },
    {
      id: "verdict",
      label: "Negative verdict",
      kind: "output",
      facts: [
        "RL 0.5120 vs B1 0.5217 mean normalised profit: −1.86%.",
        "Paired 95% CI [−0.0114, −0.0080] lies below zero, so P1 fails.",
      ],
    },
  ],
  edges: [
    { id: "calibrate-train", source: "calibrate", target: "train", kind: "task", label: "train specs" },
    { id: "calibrate-lock", source: "calibrate", target: "lock", kind: "task", label: "rule tuning" },
    { id: "train-test", source: "train", target: "test", kind: "task", label: "seed 1 checkpoint" },
    { id: "lock-test", source: "lock", target: "test", kind: "task", label: "comparator" },
    { id: "test-verdict", source: "test", target: "verdict", kind: "result", label: "paired RL − B1" },
  ],
} as const satisfies DiagramSpec;
