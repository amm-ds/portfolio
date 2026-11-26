import type { DiagramSpec } from "../types";

// Hand-built from 15-dynamic-pricing-rl/story.yaml (data section); the story
// had no mermaid source, so scripts/mermaid-to-flow.mjs never emitted it.
// Draws only what that section states. facts stay empty, as on every auto
// spec.
export const AUTO_15_DYNAMIC_PRICING_RL_2_SPEC = {
  id: "auto-15-dynamic-pricing-rl-2",
  title: "Dynamic Pricing with RL — Data",
  direction: "LR",
  nodes: [
    {
      id: "m5",
      label: "3 pinned M5 files from project 02 · SHA-256 check, 2011-01-29 to 2016-04-24",
      kind: "gate",
      facts: [],
    },
    {
      id: "calib",
      label: "600 series calibrated · mean units, weekday shares, k, p_ref",
      kind: "task",
      facts: [],
    },
    {
      id: "split",
      label: "item_id split, seed 42 · 140 / 30 / 30 items = 267 / 57 / 58 series",
      kind: "gate",
      facts: [],
    },
    {
      id: "prior",
      label: "elasticity prior (assumption) · truncated normal, mean −2.5, sd 0.8",
      kind: "source",
      facts: [],
    },
    {
      id: "specs",
      label: "frozen, hashed specs · 1,000 test + 2 × 500 stress",
      kind: "data",
      facts: [],
    },
  ],
  edges: [
    { id: "m5-calib", source: "m5", target: "calib", kind: "task" },
    { id: "calib-split", source: "calib", target: "split", kind: "task" },
    { id: "split-specs", source: "split", target: "specs", kind: "task" },
    { id: "prior-specs", source: "prior", target: "specs", kind: "task" },
  ],
} as const satisfies DiagramSpec;
