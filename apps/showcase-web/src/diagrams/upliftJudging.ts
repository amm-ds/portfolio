import type { DiagramSpec } from "./types";

// Facts: projects/10-uplift-experimentation/{README.md,reports/metrics.json}.
export const UPLIFT_JUDGING_SPEC = {
  id: "10-uplift-judging",
  title: "Randomized anchor to profit verdict: the measurement contract",
  direction: "LR",
  canvasHeight: 400,
  nodes: [
    {
      id: "anchor",
      label: "Randomized assignment",
      kind: "source",
      facts: [
        "Hillstrom benchmark, sha256-pinned: 64,000 customers.",
        "Mens 21,307 / Womens 21,387 / control 21,306 — balance checked first.",
      ],
    },
    {
      id: "response",
      label: "Response model",
      kind: "model",
      facts: [
        "Ranks likely buyers — Qini 13.01 [1.83, 24.36].",
        "Highest curve area yet lowest budget profit: $4,881 at 25%.",
      ],
    },
    {
      id: "tlearner",
      label: "T-learner",
      kind: "model",
      facts: [
        "Cross-fitted out-of-fold scores — the recommended policy.",
        "Qini 12.03; profit $6,838 at the 25% budget, +$2,812 (+69%) vs random.",
      ],
    },
    {
      id: "xlearner",
      label: "X-learner",
      kind: "model",
      facts: [
        "Qini 5.90 [−5.45, 17.48] — the ranking signal is not established.",
        "The second stage adds variance without signal at this propensity overlap.",
      ],
    },
    {
      id: "profit",
      label: "Profit judging",
      kind: "gate",
      facts: [
        "profit(f) = incremental conversions × $114 − mailed × send cost.",
        "At $0.01 per email, mailing everyone wins: $16,103 per wave.",
      ],
    },
    {
      id: "bootstrap",
      label: "1,000 paired bootstraps",
      kind: "tool",
      facts: [
        "The same resampled customers grade every policy — paired CIs rank honestly.",
        "T-learner vs random at 25%: +$2,812, 95% CI [+$718, +$4,767].",
      ],
    },
    {
      id: "verdict",
      label: "Verdict",
      kind: "output",
      facts: [
        "Verdict covers $0.01–$0.50 per email; above ≈$0.30 targeting beats mail-everyone.",
        "Top-25% policy mails 10,653 emails for ~61 of ~145 incremental conversions.",
      ],
    },
  ],
  edges: [
    { id: "anchor-response", source: "anchor", target: "response", kind: "task", label: "out-of-fold" },
    { id: "anchor-tlearner", source: "anchor", target: "tlearner", kind: "task", label: "out-of-fold" },
    { id: "anchor-xlearner", source: "anchor", target: "xlearner", kind: "task", label: "out-of-fold" },
    { id: "response-profit", source: "response", target: "profit", kind: "result", label: "scores" },
    { id: "tlearner-profit", source: "tlearner", target: "profit", kind: "result", label: "scores" },
    { id: "xlearner-profit", source: "xlearner", target: "profit", kind: "result", label: "scores" },
    { id: "profit-bootstrap", source: "profit", target: "bootstrap", kind: "task", label: "same resample" },
    { id: "bootstrap-verdict", source: "bootstrap", target: "verdict", kind: "result", label: "CI" },
  ],
} as const satisfies DiagramSpec;
