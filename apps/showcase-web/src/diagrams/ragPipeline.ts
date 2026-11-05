import type { DiagramSpec } from "./types";

// Facts: projects/01-rag-agent/{README.md,reports/metrics.json}.
export const RAG_PIPELINE_SPEC = {
  id: "01-rag-pipeline",
  title: "Pinned corpus to cited answer: retrieve, draft, verify",
  direction: "LR",
  canvasHeight: 420,
  nodes: [
    {
      id: "corpus",
      label: "Wikipedia snapshot · 5 topics",
      kind: "source",
      facts: [
        "593 articles across 5 topics, at most 120 each, from the 20231101.en dump.",
        "Corpus text is CC BY-SA / GFDL licensed Wikipedia.",
      ],
    },
    {
      id: "contract",
      label: "Dataset contract",
      kind: "data",
      facts: [
        "The corpus is sha256-pinned and DQ-gated before anything runs.",
        "corpus.jsonl plus the indexes ship as pinned artifacts.",
      ],
    },
    {
      id: "embeddings",
      label: "MiniLM embeddings",
      kind: "model",
      facts: [
        "all-MiniLM-L6-v2 is the embedding model chosen by the committed HPO sweep.",
        "Chosen retrieval config: chunk size 200, top_k 3, rerank on.",
      ],
    },
    {
      id: "faiss",
      label: "FAISS exact index · CPU",
      kind: "data",
      facts: [
        "IndexFlatIP exact search; retrieval is CPU-only.",
        "recall@5 is 0.831 on the 65-question tuning set vs 0.031 random.",
      ],
    },
    {
      id: "rerank",
      label: "Cross-encoder rerank",
      kind: "model",
      facts: [
        "ms-marco-MiniLM-L-6-v2 reranks the top 5×k candidates.",
        "Rerank ON lifts MRR@5 to 0.808 vs 0.718 OFF at the same recall@5.",
      ],
    },
    {
      id: "funnel",
      label: "Top 15 → top 3 passages",
      kind: "gate",
      facts: [
        "Retrieval narrows 593 articles to the top 15 passages, then the top 3.",
        "Committed token sweep: ≈802 input tokens per query at top_k = 3.",
      ],
    },
    {
      id: "draft",
      label: "Agent draft with citations",
      kind: "agent",
      facts: [
        "The pydantic-ai agent's only corpus access is two tools: search_documents, read_excerpt.",
        "Hosted pass p50 latency is 23 s per answer including verification.",
      ],
    },
    {
      id: "verifier",
      label: "Claim verifier · 0.6 support floor",
      kind: "gate",
      facts: [
        "Each claim is entailment-checked against the full text of its cited chunk.",
        "0.6 support floor with at most 2 repairs; 39 repair calls on the 65-question pass.",
      ],
    },
    {
      id: "answer",
      label: "Cited answer or abstention",
      kind: "output",
      facts: [
        "Hosted-pass RAGAS faithfulness 0.685, 95% CI [0.605, 0.760].",
        "Refusal accuracy 0.900 with a 0.036 false-abstention rate.",
      ],
    },
  ],
  edges: [
    { id: "corpus-contract", source: "corpus", target: "contract", kind: "task", label: "pin + gate" },
    { id: "contract-embeddings", source: "contract", target: "embeddings", kind: "task", label: "chunk 200" },
    { id: "embeddings-faiss", source: "embeddings", target: "faiss", kind: "result", label: "vectors" },
    { id: "faiss-rerank", source: "faiss", target: "rerank", kind: "result", label: "top 5×k" },
    { id: "rerank-funnel", source: "rerank", target: "funnel", kind: "result", label: "ranked" },
    { id: "funnel-draft", source: "funnel", target: "draft", kind: "task", label: "top 3 passages" },
    { id: "draft-verifier", source: "draft", target: "verifier", kind: "result", label: "draft + citations" },
    { id: "verifier-draft", source: "verifier", target: "draft", kind: "error", label: "repair ≤ 2" },
    { id: "verifier-answer", source: "verifier", target: "answer", kind: "result", label: "pass / abstain" },
  ],
} as const satisfies DiagramSpec;
