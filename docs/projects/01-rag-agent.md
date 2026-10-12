# RAG & Agentic AI Assistant

**Domain:** Agentic AI / LLM · **Data:** Wikipedia (HF, real) · **Status:** Flagship — complete

A grounded question-answering agent over a curated topical slice of English
Wikipedia. A `pydantic-ai` agent answers **only** from retrieved evidence and
returns a structured `AnalysisResult` — summary, per-claim citations, and a
calibrated confidence — with no LLM SDK in the project (provider abstraction
per ADR-0004: live OpenAI-compatible endpoint, or a deterministic mock fully
offline).

## Pipeline

1. **Corpus** — bounded stream of `wikimedia/wikipedia` (`20231101.en`),
   five topics (Climate, Renewable energy, Aviation, Machine learning,
   Photosynthesis), ≤120 articles each plus exact-title anchors; DQ gates and a
   sha256-pinned dataset contract. Result: 593 articles.
2. **Index** — paragraph-aware chunking at 200/400/800 tokens →
   MiniLM-L6-v2 embeddings (L2-normalized) → FAISS `IndexFlatIP` per size;
   cross-encoder (`ms-marco-MiniLM-L-6-v2`) reranks the top 5×k on CPU.
3. **Agent** — tools `search_documents` / `read_excerpt` are the only corpus
   access; output schema is validated on every run and fails loudly.
4. **Evaluation** — 26 graded questions: recall@5/10 + MRR@5 sweep over chunk
   sizes, RAG faithfulness / answer relevance / context recall via judge, and
   per-query latency + estimated cost, all written to `reports/`.

## Key results (2026-10-12, this machine, CPU-only, offline mock mode)

| Metric | Value |
|---|---|
| Retrieval recall@5 / recall@10 | 0.962 / 1.000 (all chunk sizes) |
| MRR@5 — chunk 200 / 400 / 800 | 0.936 / 0.904 / 0.869 |
| RAG context_recall | 0.962 |
| RAG faithfulness / answer_relevance (mock answer) | 0.245 / 0.436 |
| p50 / p95 agent latency (local floor) | 3.0 ms / 4.1 ms |
| Estimated live cost per query | ≈ $0.00037 |

Takeaway: 200-token chunks dominate the frontier — saturated recall, best MRR,
roughly half the context cost of 400. Figures: chunk-size sweep, cost-vs-quality
frontier, latency histogram (all in `reports/figures/`).

## Links

- [Project README](https://github.com/amm-ds/portfolio/tree/main/projects/01-rag-agent/README.md) — results, reproduce instructions, client-facing summary
- [DESIGN.md](https://github.com/amm-ds/portfolio/tree/main/projects/01-rag-agent/DESIGN.md) — requirements, options considered (ChromaDB vs FAISS, reranking, provider abstraction), SLOs, failure modes
- Interactive report: `projects/01-rag-agent/reports/report.html`

## Data attribution

Corpus text is from Wikipedia (`wikimedia/wikipedia`, dump `20231101.en`),
licensed under
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) and
[GFDL](https://www.gnu.org/licenses/fdl-1.3.html); content remains the property
of its authors. Article selection and all transformations are reproducible via
`dvc repro` in the project directory.
