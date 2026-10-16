# RAG & Agentic AI Assistant

**Domain:** Agentic AI / LLM · **Data:** Wikipedia (HF, real) · **Status:** Flagship — complete

A grounded question-answering agent over a curated topical slice of English
Wikipedia. A `pydantic-ai` agent answers **only** from retrieved evidence and
returns a structured `AnalysisResult` — summary, per-claim citations, and a
calibrated confidence — with no LLM SDK in the project (provider abstraction
per ADR-0004, as amended: env-configured OpenAI-compatible endpoint
first, local Ollama second — default `qwen3.6:35b-a3b-q4_K_M`; no runtime
mock, `--offline` keeps a retrieval-only CI path).

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

## Key results (2026-10-15/16, this machine, local `qwen3.6:35b-a3b-q4_K_M`)

**Golden set: 65 graded questions** — 44 single-hop, 11 multi-hop, 10
unanswerable (expected behavior: abstain). Questions validated against the
actual corpus; the earlier 10-question LLM pass was retired because a 65-question
set with bootstrap CIs is the minimum an audit should accept.

| Metric | Value (95% CI) |
|---|---|
| Retrieval recall@5 / recall@10 | 0.962 / 1.000 (random baseline 0.038) |
| **Production config** (`retrieval_best`) | MiniLM, chunks=200, top_k=3, rerank ON — −65% context cost at equal recall |
| RAGAS faithfulness (30-q bounded LLM pass, local judge, n=1000 bootstraps) | **0.651 [0.52, 0.78]** |
| RAGAS answer relevancy | 0.879 [0.82, 0.93] |
| RAGAS context precision / recall | 1.000 / 0.979 |
| Keyword-judge CI floor on the same subset | 0.36 / 0.37 faithfulness / relevance |
| Refusal accuracy (unanswerable questions) | **0.857 [0.57, 1.00]** (6/7 correctly declined) |
| False-abstention rate | 0.000 — never declines a question it can answer |
| p50 / p95 agent latency (local model, honest) | 61 s / 245 s |
| Cost | **$0 API** (local inference); cloud-equivalent ≈ $0.0043/query |

Takeaway: retrieval is solved (recall 0.98, precision 1.0), so **generation
grounding is the bottleneck** — the failure taxonomy on the 30-question pass
shows 12 correct vs 18 unsupported-claim answers. The honest faithfulness
number (0.651 with a wide CI) replaces the earlier 10-question 0.805, which
overstated quality on a too-small subset. The next lever is
answer-construction (citation forcing / answer-then-verify loops), not
retrieval. Figures: corpus composition, chunk-size sweep with random baseline,
embedding model comparison, retrieval funnel, HPO frontier (chosen config
starred), latency histogram (all in `projects/01-rag-agent/reports/figures/`).

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
