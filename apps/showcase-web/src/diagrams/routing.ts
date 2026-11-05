import type { DiagramSpec } from "./types";

// Facts: projects/04-nlp-classification/reports/{fresh_holdout,latency_probe}.json.
export const ROUTING_SPEC = {
  id: "04-routing",
  title: "Keyword-first routing with neural escalation",
  direction: "LR",
  canvasHeight: 340,
  nodes: [
    {
      id: "input",
      label: "AG News item",
      kind: "source",
      facts: [
        "Headline-plus-description input across four AG News topics.",
        "The fresh holdout contains 1,000 articles disjoint from model selection.",
      ],
    },
    {
      id: "keyword",
      label: "TF-IDF + logistic regression",
      kind: "model",
      facts: [
        "Fresh-holdout macro-F1: 0.8785 (88%), versus 0.9529 (95%) for full-data DistilBERT.",
        "Apple M4 Max, CPU batch=1: 4,477.8 predictions/s at zero token cost.",
        "75.4% of items stay on this path at τ=0.50 — about 3 of 4 at keyword cost.",
      ],
    },
    {
      id: "gate",
      label: "Confidence gate · τ = 0.50",
      kind: "gate",
      facts: [
        "Raw TF-IDF maximum class probability drives the routing decision.",
        "At τ=0.50, 24.6% of items escalate; the routed system scores 0.9020 fresh macro-F1.",
      ],
    },
    {
      id: "distilbert",
      label: "Fine-tuned DistilBERT · 120k rows",
      kind: "model",
      facts: [
        "Fresh-holdout macro-F1: 0.9529 (95%), versus 0.8785 (88%) for the keyword model.",
        "Apple M4 Max, CPU batch=1: 110.7 predictions/s for the bounded served transformer.",
        "Cloud-equivalent estimate: $0.0656 (~$0.07) per 1,000 items.",
      ],
    },
    {
      id: "output",
      label: "Sorted item",
      kind: "output",
      facts: [
        "Confidence routing reaches 0.9020 fresh macro-F1 while 75.4% of items use keyword economics.",
        "High-value traffic can use the full-data model at 0.9529 fresh macro-F1.",
      ],
    },
  ],
  edges: [
    { id: "input-keyword", source: "input", target: "keyword", kind: "task", label: "every item" },
    { id: "keyword-gate", source: "keyword", target: "gate", kind: "result", label: "confidence" },
    { id: "gate-output", source: "gate", target: "output", kind: "result", label: "confident · 75.4%" },
    { id: "gate-distilbert", source: "gate", target: "distilbert", kind: "error", label: "doubt · 24.6%" },
    { id: "distilbert-output", source: "distilbert", target: "output", kind: "result", label: "prediction" },
  ],
} as const satisfies DiagramSpec;
