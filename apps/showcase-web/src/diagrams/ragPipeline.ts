import type { DiagramSpec } from "./types";

// Facts: projects/01-rag-agent/{README.md,reports/metrics.json,
// reports/final_v3_e2e/, reports/retrieval_sweeps/}.
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
      label: "Title-anchored chunks + MiniLM",
      kind: "model",
      facts: [
        "200/40-token chunks with the article title prefixed (the S1 structure arm).",
        "all-MiniLM-L6-v2 embeddings, chosen by the committed HPO sweep; CPU only.",
      ],
    },
    {
      id: "faiss",
      label: "Dense FAISS + BM25 · RRF k=60",
      kind: "data",
      facts: [
        "FAISS IndexFlatIP dense search fused with BM25 lexical scores via RRF (k=60) over a pool of 50 (the S2 hybrid arm).",
        "Promoted S3 reaches recall@5 0.946 on the 120-question final_v3 set; seeded-random floor is 0.031.",
      ],
    },
    {
      id: "rerank",
      label: "Cross-encoder rerank",
      kind: "model",
      facts: [
        "ms-marco-MiniLM-L-6-v2 re-scores the top 6×k candidates (18 at serving top_k 3).",
        "Tuning ablation: rerank ON lifts MRR@5 to 0.808 vs 0.718 OFF at the same recall@5 0.831, so reranking buys rank, not recall.",
      ],
    },
    {
      id: "funnel",
      label: "Per-article cap 2 → top 3",
      kind: "gate",
      facts: [
        "S3 caps each article at 2 chunks with backfill, then serves the top 3 passages (measurement reads top 5).",
        "Mean context is 443 tokens at top 3, so prompt size stays predictable.",
      ],
    },
    {
      id: "draft",
      label: "Agent draft with citations",
      kind: "agent",
      facts: [
        "The pydantic-ai agent's only corpus access is two tools: search_documents, read_excerpt.",
        "Final pass p50 latency is 16.5 s per answer (p95 40.5 s) including verification.",
      ],
    },
    {
      id: "verifier",
      label: "Claim verifier · ≥ 60% survive",
      kind: "gate",
      facts: [
        "Each claim gets a boolean entailment check against the full text of its cited chunk; an answer ships only if at least 60% of its claims survive.",
        "At most 2 repair calls per answer; final pass: 166 drafted claims, 159 kept (95.8%).",
      ],
    },
    {
      id: "answer",
      label: "Cited answer or abstention",
      kind: "output",
      facts: [
        "Final pass faithfulness 0.872, 95% CI [0.8092, 0.9304] (rubric judge, bootstrap).",
        "F1 0.9091; 24/28 unanswerable questions refused correctly.",
      ],
    },
  ],
  edges: [
    { id: "corpus-contract", source: "corpus", target: "contract", kind: "task", label: "pin + gate" },
    { id: "contract-embeddings", source: "contract", target: "embeddings", kind: "task", label: "chunk 200/40" },
    { id: "embeddings-faiss", source: "embeddings", target: "faiss", kind: "result", label: "vectors + lexical" },
    { id: "faiss-rerank", source: "faiss", target: "rerank", kind: "result", label: "RRF pool 50" },
    { id: "rerank-funnel", source: "rerank", target: "funnel", kind: "result", label: "ranked" },
    { id: "funnel-draft", source: "funnel", target: "draft", kind: "task", label: "top 3 passages" },
    { id: "draft-verifier", source: "draft", target: "verifier", kind: "result", label: "draft + citations", offset: -34 },
    { id: "verifier-draft", source: "verifier", target: "draft", kind: "error", label: "repair ≤ 2", offset: 34 },
    { id: "verifier-answer", source: "verifier", target: "answer", kind: "result", label: "pass / abstain" },
  ],
} as const satisfies DiagramSpec;
