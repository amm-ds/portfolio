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
4. **Evaluation** — 65 graded questions (44 single-hop, 11 multi-hop, 10
   unanswerable): recall@5/10 + MRR@5 sweep over chunk sizes, RAGAS +
   rubric-judge quality runs, a verify-then-answer A/B, and per-query latency
   + estimated cost, all written to `reports/`.

## Key results (2026-10-16, this machine, local `qwen3.6:35b-a3b-q4_K_M`)

**Golden set: 65 graded questions** — 44 single-hop, 11 multi-hop, 10
unanswerable (expected behavior: abstain). Questions validated against the
actual corpus; the earlier 10-question LLM pass was retired because a 65-question
set with bootstrap CIs is the minimum an audit should accept.

| Metric | Value (95% CI) |
|---|---|
| Retrieval recall@5 / recall@10 (65-q golden set) | **0.831 / 0.846** (random baseline 0.031; the earlier 26-q sweep read 0.962 / 0.038 — the harder denominator is the honest one) |
| **Production config** (`retrieval_best`) | MiniLM, chunks=200, top_k=3, rerank ON — −65% context cost at equal recall (≈804 vs ≈2,279 input tokens/query) |
| RAGAS without verify loop (30-q bounded pass, local judge, n=1000 bootstraps) | faithfulness **0.651 [0.52, 0.78]**, relevancy 0.879 [0.82, 0.93] |
| RAGAS with verify loop (new run) | faithfulness 0.6058, relevancy 0.7196, context precision 1.0, context recall 0.9784 |
| Failure taxonomy (n=30) — without → with verify | 12 correct / 18 unsupported-claim → **15 correct / 14 unsupported-claim / 1 format-failure** |
| Verify-loop overhead | 33 repair calls (max 2/answer), mean claim-support 0.8389 vs min_support 0.6; 4 verify-abstentions, 6 skipped |
| Refusal accuracy (unanswerable questions) | **0.857 [0.57, 1.00]** (6/7 correctly declined) |
| False-abstention rate | 0.174 |
| Cite-when-expected | 0.957 |
| Keyword-judge CI floor (this run) | faithfulness 0.44 [0.29, 0.61] — the LLM judge sits well above the lexical floor either way |
| p50 / p95 agent latency (local model, honest) | 61 s / 245 s |
| Cost | **$0 API** (local inference); cloud-equivalent ≈ $0.0068/query with the verify loop |

Takeaway: retrieval is solid (recall@5 0.831 vs 0.031 random on the 65-question
set), so **generation grounding is the bottleneck**. The verify-then-answer loop — claim-split,
entailment-checked against cited chunks, repair-capped at 2 calls, abstention
below support floor 0.6 — measurably improved the failure taxonomy on the
30-question pass: unsupported claims 18→14, correct answers 12→15, while RAGAS
faithfulness moved 0.651→0.606, within judge noise between runs — quality held
while groundness improved. The cost is real: 33 repair calls. Verdict: the loop
is worth its repair-call overhead on high-stakes corpora, and it is not free.
The honest faithfulness number (0.651 without verify, wide CI) replaces the
earlier 10-question 0.805, which overstated quality on a too-small subset.
Figures: corpus composition, chunk-size sweep with random baseline, embedding
model comparison, retrieval funnel, HPO frontier (chosen config starred),
latency histogram, failure taxonomy before/after the verify loop (all in
`projects/01-rag-agent/reports/figures/`).

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
