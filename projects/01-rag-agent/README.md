# Project 01 — RAG & Agentic AI Assistant

A grounded question-answering assistant over a pinned 593-article English
Wikipedia corpus. `pydantic-ai` restricts corpus access to retrieval tools and
returns structured, cited answers. Retrieval combines MiniLM embeddings, FAISS,
and cross-encoder reranking.

The runtime default is local Ollama (`qwen3.6:35b-a3b-q4_K_M`); any
OpenAI-compatible endpoint uses the same path. There is no runtime mock.
**`kimi-for-coding` is the selected provider for the reported evaluation**,
which covers a 65-question tuning set and a sealed 15-question held-out set.

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
**0.831 versus 0.031 for the random floor**. The selected provider is hosted
**`kimi-for-coding`**: 46 answers are correct, but 17 retain unsupported claims,
so citations make answers auditable but not safe for unattended use.

| metric | selected `kimi-for-coding`, 65 tuning questions |
|---|---:|
| failure taxonomy | 46 correct / 17 unsupported / 2 retrieval-miss / 0 format |
| rubric faithfulness | **0.6209** (incumbent 0.5504) |
| rubric answer relevance | **0.6458** (incumbent 0.5573) |
| rubric context recall | 0.9636 |
| RAGAS faithfulness (95% CI) | **0.7337 [0.6562, 0.8131]** |
| RAGAS answer relevancy | **0.8602** (small regression from 0.8775) |
| RAGAS context precision / recall | 0.7609 / 0.9826 |
| refusal accuracy | 1.0 |
| false-abstention rate | 0.0545 |
| cite-when-expected | 0.9636 |
| answer latency p50 / p95 | 25.888 s / 108.836 s |
| answer-generation cost | $0.000906/query before judge/verify costs |

The provider comparison improves rubric faithfulness, answer relevance, and
RAGAS faithfulness, but the RAGAS answer-relevancy regression is real and stays
in the headline table. Retrieval remains stronger than generation grounding.

### Sealed held-out set

The held-out set contains 15 fresh questions: 8 single-hop, 2 multi-hop, and 5
unanswerable. Programmatic gates check corpus support, absent terms, and
Jaccard separation from the tuning set before scoring. The selected hosted pass
uses verification and the rubric judge, without RAGAS.

| metric | sealed held-out result |
|---|---:|
| retrieval recall@5 / recall@10 | 0.600 / 0.667 |
| retrieval MRR@5 (random floor) | 0.567 (0.022) |
| rubric faithfulness, 10 answerable | 0.64 |
| rubric answer relevance, 10 answerable | 0.595 |
| rubric context recall, 10 answerable | 0.9 |
| required refusals | 5/5 |
| latency p50 / p95 | 28.025 s / 52.176 s |
| whole-pass meter | 61 calls / $0.240699 cloud-equivalent |

Held-out retrieval is harder than tuning-set retrieval. The sealed set is one
small slice, not evidence of broad-corpus or unattended readiness.

### Cost and budget operation

Costs use the public reference rate card ($1/Mtok input, $4/Mtok output, cached
reads at 30%). They are cloud-equivalent estimates, not billed amounts. Only
successful calls are metered. Tuning cost is reported as answer generation per
query before judging and verification; no replacement end-to-end tuning-suite
total is claimed.

The sealed 15-question pass meters:

| phase | calls | cloud-equivalent spend |
|---|---:|---:|
| agent | 14 | $0.144457 |
| judge | 28 | $0.037550 |
| verify | 19 | $0.058692 |
| RAGAS | 0 | $0.000000 |
| **total** | **61** | **$0.240699** |

`LLM_COST_LIMIT_USD` caps each run through the platform spend ledger. A cap
violation stops the CLI with setup guidance; it does not silently select a
fallback judge. `LLM_TOTAL_TOKENS_LIMIT` separately stops runaway tool loops.
Exact telemetry is in `reports/metrics.json → detail.heldout.meter`.

## Figures

| figure | file |
|---|---|
| corpus composition | [reports/figures/eda_corpus_composition.html](reports/figures/eda_corpus_composition.html) |
| retrieval quality vs chunk size | [reports/figures/chunk_size_sweep.html](reports/figures/chunk_size_sweep.html) |
| embedding model comparison | [reports/figures/model_comparison.html](reports/figures/model_comparison.html) |
| retrieval funnel | [reports/figures/retrieval_funnel.html](reports/figures/retrieval_funnel.html) |
| retrieval HPO frontier | [reports/figures/retrieval_hpo_frontier.html](reports/figures/retrieval_hpo_frontier.html) |
| per-query latency | [reports/figures/latency_histogram.html](reports/figures/latency_histogram.html) |
| selected-provider comparison | [reports/figures/kimi_generation_comparison.json](reports/figures/kimi_generation_comparison.json) |
| full report | [reports/report.html](reports/report.html) |

## Limits

Answers are not trustworthy unattended: the selected tuning pass retains 17
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
