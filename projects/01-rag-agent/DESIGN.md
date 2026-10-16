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

Per ADR-0004 (amended wave 10) all LLM access goes through
`portfolio_core.llm.build_model`: env-configured OpenAI-compatible endpoint
first, local Ollama second (default `qwen3.6:35b-a3b-q4_K_M`; `OLLAMA_MODEL` overrides —
`gpt-oss:20b` is the documented lighter alternative). The project never
imports an LLM SDK. The deterministic runtime mock is **removed by owner
directive** — `evaluate`/`chat` require a provider and fail with actionable
guidance otherwise (`--offline` keeps a retrieval-only CI path); test-only
mocks live in `portfolio_core.llm.mock_model_for_tests`.

For the wave-10 evaluation qwen3 thinking is disabled (`think: false` via
`extra_body`, ~4× lower per-call latency) — a documented latency/depth
trade-off. The RAGAS evaluator (§3.5) and the LLM rubric judge use the same
provider, so the full quality evaluation costs $0 in API calls.

### 3.4 Chunking: fixed-size vs paragraph-aware

Fixed-size splitting cuts sentences mid-thought and separates definitional
leads from their bodies. The chosen splitter packs whole paragraphs up to the
token budget, splits long paragraphs at sentence boundaries, and only falls back
to word windows (with overlap) for pathological sentences. Guarantees are
unit-tested as properties (max size, exact overlap, determinism).

### 3.5 RAGAS evaluation (wave 10)

`evaluate --ragas` computes the RAGAS metric set — faithfulness,
answer_relevancy, context_precision, context_recall — on the agent's answers
with the **local model as evaluator** (via `langchain_openai.ChatOpenAI`
pointed at the same endpoint), so the run costs $0 in API calls. Embeddings
for `answer_relevancy` come from the project's MiniLM encoder, not an external
API. Implementation notes: ragas 0.3.1 pins `langchain-community<0.4`;
`RunConfig(timeout=900, max_workers=4)` accommodates multi-minute 32B calls;
failed samples are NaN-skipped, never fatal. `context_recall`'s reference is
the graded relevant article's lead. Because local 32B inference is the
bottleneck (full 65-question run ≈ hours), the documented real run bounds the
LLM phases with `--max-questions 30`; retrieval metrics always use the full
65-question graded set.

### 3.6 Golden-set v2: abstention, failure taxonomy, bootstrap CIs (wave 11)

The graded set was expanded to **65 questions**: 44 single-hop, 11 multi-hop,
and **10 unanswerable** questions whose topics deliberately sit outside the
corpus and whose `expected_behavior` is `abstain`. Answerable questions must
have a relevant chunk in the top-10 of the production retriever
(`validate_golden_set`); unanswerable ones are validated at authoring time
(topic disjointness) and accepted on schema.

Three measurement mechanisms were added on top of the existing judges:

- **Abstention metrics** (`_meta.abstention` in `metrics.json`): refusal
  accuracy (unanswerable questions the agent refused), cite-when-expected
  (answerable questions citing a graded-relevant article), and false-abstention
  rate (answerable questions the agent refused). Each rate is a mean over
  per-question 0/1 indicators with a **percentile bootstrap 95% CI**
  (n_resamples=1000, seeded from `config.seed`). Refusal detection is the
  deterministic documented rule `is_abstention`: confidence < 0.3 OR explicit
  no-evidence phrasing in the summary.
- **Failure taxonomy** (`_meta.taxonomy` + `reports/figures/failure_taxonomy`):
  every question is classified by deterministic first-match rules —
  `format-failure` (agent raised / schema-invalid output), abstain-expected +
  abstained → `correct`, abstain-expected + answered → `unsupported-claim`,
  answerable without relevant evidence in top_k → `retrieval-miss`,
  answerable with judge faithfulness < 0.5 → `unsupported-claim`, else
  `correct`. A correct refusal on an unanswerable question counts as correct,
  so the taxonomy sums to the question count.
- **Bootstrap CIs everywhere else**: the rag_agent row (judge faithfulness,
  answer relevance, context recall) gets `_meta.rag_ci` over its per-question
  scores, and the RAGAS row gets `_meta.ragas_ci` over per-row RAGAS scores —
  same n=1000 seeded percentile bootstrap as the abstention CIs.

The per-question evidence behind every number ships as
`reports/question_traces.json` (question → top-chunk rank → cited y/n →
faithfulness → verdict) and is linked from a table appended to
`reports/report.html`.

## 4. SLOs and operating envelope

| SLO | Target | Measured (2026-10-14/15, local `qwen3.6:35b-a3b-q4_K_M`) |
|---|---|---|
| Retrieval recall@5 (graded set, n=26) | ≥ 0.60 | **0.962** (all chunk sizes); recall@10 = 1.000 |
| RAGAS faithfulness (n=10 bounded) | ≥ 0.70 | **0.805** |
| RAGAS answer_relevancy (n=10) | ≥ 0.70 | **0.904** |
| RAGAS context_recall (n=10) | ≥ 0.70 | **0.952** |
| p95 end-to-end query latency | report honestly | **245 s** local (p50 61 s) — compute-bound, $0 API |
| Cost per query | $0 API (local) | **$0**; cloud-equivalent ≈ $0.0043 mean at the rate card |
| Corpus size | 500–600 articles | 593 articles / 3,589 chunks @200 |
| Random-retrieval baseline (seeded floor) | reported for contrast | recall@5 0.038/0.000/0.000, MRR@5 0.038/0.000/0.000 → Δ recall@5 up to +0.92 |

Fallback chain (ADR-0004 amended wave 10): env provider → local Ollama → loud
`LLMProviderUnavailableError` (plus a retrieval-only `--offline` CI path).
There is **no** silent degradation inside retrieval: if the embedding model
cannot be loaded or
downloaded, `EmbeddingModelError` halts the pipeline with an actionable message.

## 5. Failure modes and mitigations

| Failure | Behavior |
|---|---|
| No LLM credentials | Mock model; pipeline + chat fully functional offline (documented in output) |
| Embedding model download fails | `EmbeddingModelError` with HF connectivity hint; no keyword fallback |
| Index/chunk metadata mismatch | `ValueError` on load (ntotal vs rows) |
| Eval question references missing article | Skipped with warning; run continues on the resolvable subset |
| Provider returns schema-invalid JSON | pydantic-ai retries, then raises `UnexpectedModelBehavior` |
| No LLM provider available | `LLMProviderUnavailableError` with setup guidance; `evaluate --offline` for retrieval-only CI |
| `JUDGE=keyword` or `--offline` | Deterministic keyword judge (CI default is the LLM judge when a provider exists) |
| LLM judge call fails mid-run | That verdict falls back to the keyword judge; the run continues |
| Client corpus has no usable records | `ValueError`/`FileNotFoundError` at intake, before any indexing |

## 5b. Operations artifacts

- **Cost telemetry** — `evaluate` writes `reports/cost_telemetry.json`:
  backend label (`ollama:<OLLAMA_MODEL>` or `env:<model>`), per-query
  input/output tokens, eval wall time. **Local inference is $0 API cost**;
  rate-card figures are kept as a clearly-labelled hypothetical for hosted-model
  budget comparisons. This is the data source for the roadmap's cost telemetry.
- **Client-corpus onboarding** — `prepare-corpus --source client <dir>
  --license <spdx>` maps client JSONL (`{title, text, topic?}`) onto the same
  Article schema and dataset contract (`source: client://<dir>`); chunking,
  indexing and evaluation run unchanged. See the runbook-style usage in the
  README.

## 6. Changelog

- 0.3.0 (2026-10-14) — wave 10: runtime mock removed (ADR-0004 amended; agent,
  LLM judge and chat now require a provider — local Ollama default), RAGAS
  evaluation behind `evaluate --ragas` (local model as evaluator, $0 API),
  cost telemetry reframed for local inference (`$0 API cost` + wall time),
  `--offline` retrieval-only CI path, `--max-questions` bound for the LLM
  phases, qwen3 `think: false` for eval throughput.
- 0.2.0 (2026-10-13) — client-corpus onboarding path (`--source client`),
  cost telemetry (`reports/cost_telemetry.json`), LLM rubric judge behind
  `JUDGE=llm` with keyword fallback.
- 0.1.0 (2026-10-12) — initial implementation: corpus prep, chunking, FAISS
  indexes (3 chunk sizes), cross-encoder rerank, pydantic-ai agent with
  structured citations, retrieval + RAG + ops evaluation, DVC pipeline. See
  git history and `reports/metrics.json` for the evaluated configuration.
