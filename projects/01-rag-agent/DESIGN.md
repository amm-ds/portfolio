# DESIGN — Project 01: RAG & Agentic AI Assistant

Status: implemented and evaluated. See [README](README.md) for results and
`reports/` for the generated artifacts.

## 1. Requirements

| # | Requirement | How it is met |
|---|---|---|
| R1 | Answers grounded **only** in retrieved evidence, with per-claim citations | Agent tools are the *only* corpus access; system prompt enforces citation; output schema (`AnalysisResult`) makes citations mandatory |
| R2 | Structured, machine-checkable agent output | `output_type=AnalysisResult` (pydantic); invalid outputs fail the run loudly (`UnexpectedModelBehavior`) |
| R3 | Works offline / in CI | Platform factory (ADR-0004) returns a deterministic FunctionModel when no `LLM_BASE_URL`/`LLM_API_KEY` is set; `MOCK_ANALYSIS_JSON` drives the full pipeline incl. `chat` |
| R4 | Reproducible data | Deterministic article ids, bounded streaming scan, dataset contract with sha256, DVC stages + lock |
| R5 | Retrieval quality measured, not assumed | Graded question set; recall@5/10, MRR@5 per chunk size; RAG faithfulness/relevance/recall via judge |
| R6 | Cost/latency awareness | Per-query latency (p50/p95), token usage recorded, estimated USD/query, cost-vs-quality frontier |
| R7 | CPU-only, no GPU | `sentence-transformers` (MiniLM-L6) + FAISS `IndexFlatIP` + cross-encoder reranker on CPU |

## 2. Architecture

```mermaid
flowchart LR
    subgraph Data
        A[Wikimedia/Wikipedia<br/>20231101.en stream] --> B[prepare-corpus<br/>topic filter + DQ gates]
        B --> C[(data/raw<br/>corpus.jsonl + contract)]
    end
    subgraph Index
        C --> D[chunking<br/>paragraph-aware, sizes 200/400/800]
        D --> E[MiniLM-L6-v2 embeddings<br/>L2-normalized]
        E --> F[(FAISS IndexFlatIP<br/>per chunk size)]
    end
    subgraph Agent
        U[User question] --> G[pydantic-ai Agent<br/>AnalysisResult output]
        G -->|search_documents / read_excerpt| H[Retriever]
        H --> F
        H --> I[cross-encoder rerank<br/>ms-marco-MiniLM]
        I --> G
    end
    subgraph Eval
        G --> J[RAGEvaluator<br/>faithfulness / relevance / recall]
        H --> K[recall@k, MRR sweep]
        J & K --> L[reports/<br/>metrics.json + report.html + figures]
    end
```

## 3. Options considered

### 3.1 Vector store: ChromaDB vs FAISS

- **ChromaDB (+LangChain)**: batteries included (embedding, persistence, filtering),
  but a heavier dependency, implicit embedding behavior that is harder to pin,
  and less control over index internals.
- **FAISS `IndexFlatIP`** (chosen): exact search over normalized MiniLM embeddings,
  zero external service, trivially portable artifact (`faiss.index` + `chunks.jsonl`),
  fully reproducible offline. IVF/HNSW were unnecessary at ~10k-chunk scale and would
  add recall-vs-parameters tuning surface for no latency benefit on CPU at this size.

Decision rationale: portfolio projects value inspectable, dependency-light
artifacts; `IndexFlatIP` on normalized vectors is the smallest thing that is
exactly correct.

### 3.2 Reranking: none vs cross-encoder

- **None**: one embedding model, one latency hop; acceptable for top-5 over small corpora.
- **Cross-encoder `ms-marco-MiniLM-L-6-v2`** (chosen): re-scores the top `5 × top_k`
  candidates with full query-passage attention. Cost is ~25 small model calls per
  query — single-digit milliseconds each on CPU — a negligible fraction of the
  end-to-end budget and a visible MRR gain on natural questions.

### 3.3 Provider abstraction

Per ADR-0004 all LLM access goes through `portfolio_core.llm.build_model`:
OpenAI-compatible endpoint when configured, deterministic FunctionModel otherwise.
The project never imports an LLM SDK. The same code path powers the mock-mode
evaluation, the interactive `chat`, and a live deployment — only env vars change.

### 3.4 Chunking: fixed-size vs paragraph-aware

Fixed-size splitting cuts sentences mid-thought and separates definitional
leads from their bodies. The chosen splitter packs whole paragraphs up to the
token budget, splits long paragraphs at sentence boundaries, and only falls back
to word windows (with overlap) for pathological sentences. Guarantees are
unit-tested as properties (max size, exact overlap, determinism).

## 4. SLOs and operating envelope

| SLO | Target | Measured (2026-10-12, CPU-only, mock mode) |
|---|---|---|
| Retrieval recall@5 (graded set) | ≥ 0.60 | **0.962** (all chunk sizes); recall@10 = 1.000 |
| RAG context_recall (keyword judge) | ≥ 0.60 | **0.962** |
| p95 end-to-end query latency | ≤ 5.0 s live; mock measures local floor | 4.1 ms local floor (live adds provider RTT) |
| Estimated cost per query | ≤ $0.01 | ≈ $0.00037 (context-sized estimate at 400-token chunks) |
| Corpus size | 500–600 articles | 593 articles / 3,589 chunks @200 |
| Random-retrieval baseline (seeded floor) | reported for contrast | recall@5 0.038/0.000/0.000, MRR@5 0.038/0.000/0.000 → Δ recall@5 up to +0.92 |

Fallback chain (ADR-0004): live provider → deterministic mock. There is **no**
silent degradation inside retrieval: if the embedding model cannot be loaded or
downloaded, `EmbeddingModelError` halts the pipeline with an actionable message.

## 5. Failure modes and mitigations

| Failure | Behavior |
|---|---|
| No LLM credentials | Mock model; pipeline + chat fully functional offline (documented in output) |
| Embedding model download fails | `EmbeddingModelError` with HF connectivity hint; no keyword fallback |
| Index/chunk metadata mismatch | `ValueError` on load (ntotal vs rows) |
| Eval question references missing article | Skipped with warning; run continues on the resolvable subset |
| Provider returns schema-invalid JSON | pydantic-ai retries, then raises `UnexpectedModelBehavior` |
| `JUDGE=llm` without credentials | Silent fallback to the deterministic keyword judge |
| LLM judge call fails mid-run | That verdict falls back to the keyword judge; the run continues |
| Client corpus has no usable records | `ValueError`/`FileNotFoundError` at intake, before any indexing |

## 5b. Operations artifacts

- **Cost telemetry** — `evaluate` writes `reports/cost_telemetry.json`:
  per-query input/output tokens, per-query estimated cost against the rate
  card, and aggregates (n queries, totals, mean/p50/p95 cost per answer).
  Mode is `"live"` when provider credentials are configured, `"mock"` for the
  deterministic offline floor. This is the data source for the roadmap's
  cost-drift alerting.
- **Client-corpus onboarding** — `prepare-corpus --source client <dir>
  --license <spdx>` maps client JSONL (`{title, text, topic?}`) onto the same
  Article schema and dataset contract (`source: client://<dir>`); chunking,
  indexing and evaluation run unchanged. See the runbook-style usage in the
  README.

## 6. Changelog

- 0.2.0 (2026-10-13) — client-corpus onboarding path (`--source client`),
  cost telemetry (`reports/cost_telemetry.json`), LLM rubric judge behind
  `JUDGE=llm` with keyword fallback.
- 0.1.0 (2026-10-12) — initial implementation: corpus prep, chunking, FAISS
  indexes (3 chunk sizes), cross-encoder rerank, pydantic-ai agent with
  structured citations, retrieval + RAG + ops evaluation, offline mock mode,
  DVC pipeline. See git history and `reports/metrics.json` for the evaluated
  configuration.
