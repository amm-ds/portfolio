# Project 01 — RAG & Agentic AI Assistant

A grounded question-answering assistant over a pinned 593-article English
Wikipedia corpus. `pydantic-ai` restricts corpus access to retrieval tools and
returns structured, cited answers. Retrieval combines MiniLM embeddings, FAISS,
and cross-encoder reranking.

The default provider is local Ollama (`qwen3.6:35b-a3b-q4_K_M`); any
OpenAI-compatible endpoint uses the same path. There is no runtime mock.
Quality evidence covers a 65-question tuning set and a sealed 15-question
held-out set.

- Design record and history: [DESIGN.md](DESIGN.md)
- Evidence: `reports/metrics.json`, `reports/cost_telemetry.json`,
  `reports/report.html`, and `reports/figures/`
- Data contract: `data/raw/dataset_contract.json` (sha256-pinned)

## Reproduce

```bash
cd projects/01-rag-agent
uv run python -m rag_agent.cli prepare-corpus   # streams Wikipedia (bounded scan)
uv run python -m rag_agent.cli build-index      # 3 FAISS indexes (chunk-size sweep)
uv run python -m rag_agent.cli evaluate --ragas --verify   # full provider-backed evaluation
uv run python -m rag_agent.cli evaluate --heldout          # sealed held-out pass
uv run python -m rag_agent.cli chat             # interactive demo

# retrieval-only CI path, with no LLM calls
uv run python -m rag_agent.cli evaluate --offline

# or use the DVC pipeline
uv run dvc repro
uv run dvc metrics show
```

The agent, judge, and RAGAS evaluator need Ollama or an OpenAI-compatible
endpoint configured through `LLM_BASE_URL` and `LLM_API_KEY` in `.env`. The
local evaluation bounds LLM phases to 30 questions; retrieval always uses all
65 tuning questions. The hosted evaluation uses the full set.

Quality gates from the repository root:

```bash
uv run ruff check projects/01-rag-agent
uv run ruff format --check projects/01-rag-agent
uv run mypy projects/01-rag-agent
uv run pytest projects/01-rag-agent -q
```

## Design

The pipeline filters five Wikipedia topics, applies data-quality gates, chunks
articles at 200/400/800 tokens, builds one FAISS `IndexFlatIP` per chunk size,
and reranks the top 5×k passages. The agent exposes only `search_documents`
and `read_excerpt` and returns `AnalysisResult(summary, citations, confidence)`.

The verify loop checks each drafted claim against its full cited chunks. It
repairs or drops unsupported claims and abstains when surviving support falls
below 0.6. Provider selection, verification, and judging follow
[DESIGN.md](DESIGN.md) and ADR-0004.

## Results

Retrieval is provider-independent. On the 65-question tuning set, recall@5 is
**0.831 versus 0.031 for the random floor**. The hosted generation pass keeps
unsupported claims on **18 of 65 answers**, so citations make answers auditable
but not safe for unattended use.

| metric | local qwen3.6-q4, 30-question LLM subset | hosted `kimi-for-coding`, 65 questions |
|---|---:|---:|
| failure taxonomy | 15 correct / 14 unsupported / 1 format | 44 correct / 18 unsupported / 2 retrieval-miss / 1 format |
| RAGAS faithfulness (95% CI) | 0.606 | **0.685 [0.605, 0.760]** |
| RAGAS answer relevancy | 0.720 | **0.878 [0.820, 0.918]** |
| RAGAS context precision / recall | 1.000 / 0.978 | 0.760 [0.667, 0.849] / 0.978 [0.954, 0.995] |
| rubric-judge faithfulness | 0.441 [0.29, 0.61] | 0.550 [0.483, 0.611] |
| refusal accuracy | 0.857 [0.57, 1.00] | 0.900 [0.70, 1.00] |
| false-abstention rate | 0.174 | 0.036 |
| cite-when-expected | 0.957 | 0.964 |
| verify overhead | 33 repair calls | 39 repair calls in 125 verify calls |
| agent latency p50 / p95 | 61 s / 245 s, load-contended | **23 s / 175 s** |
| cost | $0 API | **$3.58 cloud-equivalent** |

The provider comparison is directional because its question counts and judge
models differ. Retrieval is stronger than generation grounding in both passes.

### Sealed held-out set

The held-out set contains 15 fresh questions: 8 single-hop, 2 multi-hop, and 5
unanswerable. Programmatic gates check corpus support, absent terms, and
Jaccard separation from the tuning set before scoring. The hosted pass uses
verification and the rubric judge, without RAGAS.

| metric | held-out, n=15 | tuning set, n=65 |
|---|---:|---:|
| retrieval recall@5 / recall@10 | 0.600 / 0.667 | 0.831 / 0.846 |
| retrieval MRR@5, random floor | 0.567 (0.022) | 0.808 (0.018) |
| rubric-judge faithfulness (95% CI) | 0.62 [0.45, 0.79], 10 answerable | 0.550 [0.483, 0.611] |
| failure taxonomy | 10 correct / 4 unsupported / 1 retrieval-miss | 44 / 18 / 2 / 1 |
| refusal accuracy | 1.00 (5/5 unanswerable) | 0.900 [0.70, 1.00] |
| latency p50 / p95 | 24.7 s / 36.6 s | 23 s / 175 s |
| cost | $0.25 cloud-equivalent | $3.58 cloud-equivalent |

Held-out retrieval is harder than tuning-set retrieval. All five unanswerable
questions produce abstentions with zero false abstentions.

### Cost and budget operation

Costs use the public reference rate card ($1/Mtok input, $4/Mtok output, cached
reads at 30%). They are cloud-equivalent estimates, not billed amounts. Only
successful calls are metered.

| phase | calls | input tokens | output tokens | cached share | cloud-equivalent spend |
|---|---:|---:|---:|---:|---:|
| agent | 64 | 3.72M | 103K | 90.0% | $1.79 |
| RAGAS | 605 | 713K | 167K | 50.4% | $1.13 |
| verify | 125 | 220K | 75K | 35.7% | $0.47 |
| judge | 128 | 106K | 22K | 1.5% | $0.19 |
| **total** | **922** | **4.76M** | **367K** | **79.6%** | **$3.58** |

`LLM_COST_LIMIT_USD` caps each run through the platform spend ledger. A cap
violation stops the CLI with setup guidance; it does not silently select a
fallback judge. `LLM_TOTAL_TOKENS_LIMIT` separately stops runaway tool loops.
Exact telemetry is in `reports/cost_telemetry.json`.

## Figures

| figure | file |
|---|---|
| corpus composition | [reports/figures/eda_corpus_composition.html](reports/figures/eda_corpus_composition.html) |
| retrieval quality vs chunk size | [reports/figures/chunk_size_sweep.html](reports/figures/chunk_size_sweep.html) |
| embedding model comparison | [reports/figures/model_comparison.html](reports/figures/model_comparison.html) |
| retrieval funnel | [reports/figures/retrieval_funnel.html](reports/figures/retrieval_funnel.html) |
| retrieval HPO frontier | [reports/figures/retrieval_hpo_frontier.html](reports/figures/retrieval_hpo_frontier.html) |
| per-query latency | [reports/figures/latency_histogram.html](reports/figures/latency_histogram.html) |
| full report | [reports/report.html](reports/report.html) |

## Limits

Answers are not trustworthy unattended: the hosted tuning pass retains 18
unsupported-claim outcomes and held-out recall@5 falls to 0.600. Local repair
is weak, and local verification gains come mainly through abstention. Broader
corpus quality and always-on public chat remain unproven; `RAG_CHAT_ENABLED=1`
stays opt-in and hosted calls require an explicit budget.

## Client-corpus onboarding

The same intake accepts JSONL records with `{title, text, topic?}` fields:

```bash
uv run python -m rag_agent.cli prepare-corpus --source client /path/to/jsonl --license "MIT"
uv run python -m rag_agent.cli build-index
uv run python -m rag_agent.cli evaluate
```

The dataset contract records `source: client://<dir>` and the supplied license.
Chunking, indexing, evaluation, and data-quality gates remain unchanged.

`JUDGE=keyword` and `VERIFY_JUDGE=keyword` select deterministic offline floors.
Provider failures can fall back per verdict or batch to those floors, while a
spend-cap violation always stops the run.

## Common errors

| symptom | cause | fix |
|---|---|---|
| `evaluate --ragas --verify`, `evaluate --heldout`, or `chat` prints setup guidance and exits | no model provider answers; there is no runtime mock | pull the local model with `ollama pull qwen3.6:35b-a3b-q4_K_M` or set `LLM_BASE_URL`/`LLM_API_KEY` in `.env`; use `evaluate --offline` for CI |

## Data attribution

Corpus text comes from Wikipedia (`wikimedia/wikipedia`, dump `20231101.en`)
under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) and
[GFDL](https://www.gnu.org/licenses/fdl-1.3.html). Article titles and content
remain the property of their respective authors; see
`data/raw/dataset_contract.json`.
