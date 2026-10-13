# Project 01 — RAG & Agentic AI Assistant

Agentic-AI flagship of the portfolio: a grounded question-answering assistant
over a curated slice of English Wikipedia, built on `pydantic-ai` with
structured, cited outputs. Retrieval is embeddings + FAISS with cross-encoder
reranking; everything runs CPU-only and works fully offline (deterministic
mock LLM) when no provider is configured.

- Design record: [DESIGN.md](DESIGN.md)
- Live artifacts: `reports/report.html`, `reports/metrics.json`, `reports/figures/`
- Data contract: `data/raw/dataset_contract.json` (sha256-pinned)

## Problem

Give a user (or downstream system) answers that are **traceable to evidence**:
every claim cites the exact Wikipedia passage it came from, the assistant
refuses to answer beyond the retrieved context, and the quality of both
retrieval and generation is measured on a graded question set — not demoed
anecdotally.

## Design summary

Bounded stream of `wikimedia/wikipedia` (`20231101.en`) → topic-filtered
corpus (5 topics, ≤120 articles each) with DQ gates and a checksum-pinned
dataset contract → paragraph-aware chunking at 200/400/800 tokens →
MiniLM-L6-v2 embeddings in a FAISS `IndexFlatIP` per chunk size →
cross-encoder (`ms-marco-MiniLM-L-6-v2`) rerank of the top 5×k →
`pydantic-ai` agent whose only corpus access is two tools
(`search_documents`, `read_excerpt`) and whose output is the structured
`AnalysisResult(summary, citations, confidence)`. Provider behaviour follows
ADR-0004: live OpenAI-compatible endpoint when env-configured, deterministic
mock otherwise. See [DESIGN.md](DESIGN.md) for options considered and SLOs.

## Results

Measured on this machine (CPU-only, offline mock LLM mode), over a graded set
of questions with known relevant articles. Full detail in
`reports/metrics.json`; interactive figures in `reports/figures/`.

<!-- RESULTS:START -->
Measured on this machine (Apple Silicon, CPU-only) in offline mock-LLM mode,
2026-10-12. Corpus: **593 articles** (5 topics, ≤120 each plus exact-title
anchors), **26 graded questions**, 0 skipped. Machine-readable:
`reports/metrics.json`.

**Retrieval HPO** — chunk-size sweep against a seeded uniform-random baseline,
plus embedding-model comparison, rerank ablation and a top_k sweep; the
production config (`retrieval_best` in `params.yaml`, mirrored in
`metrics.json → detail.hpo.chosen`) is selected from these measurements:

| Configuration | recall@5 | recall@10 | MRR@5 | random recall@5 | Δ MRR@5 vs random |
|---|---|---|---|---|---|
| chunks=200, top_k=10 (wave-2 default arm) | **0.962** | 1.000 | **0.936** | 0.038 | +0.897 |
| chunks=400, top_k=10 | **0.962** | 1.000 | 0.904 | 0.000 | +0.904 |
| chunks=800, top_k=10 | **0.962** | 1.000 | 0.869 | 0.000 | +0.869 |
| + model = BGE-small (vs MiniLM, chunks 200) | 0.962 | 1.000 | 0.936 | — | 0.000 (tie) |
| + rerank OFF (chunks 200) | 1.000 | 1.000 | 0.833 | — | −0.103 |
| **chosen: MiniLM, chunks=200, top_k=3, rerank ON** | **0.962** | — | **0.936** | 0.038 | +0.897 |

Key findings:

- **Embeddings beat random by +0.92 recall@5** (0.962 vs 0.038) — the random
  baseline is the flat dashed series in the
  [chunk-size sweep figure](reports/figures/chunk_size_sweep.html).
- **The stronger encoder (BGE-small) ties MiniLM exactly** at this corpus scale —
  both saturate recall, so the cheaper/smaller model stays.
- **Rerank trade-off is real**: with rerank off, recall@5 rises to 1.000 but
  MRR@5 drops to 0.833 — the cross-encoder puts the *right* passage at the top,
  which is what a reading LLM needs. Rerank stays on.
- **top_k=3 already saturates recall at chunks=200** (recall@3 = 0.962): the
  chosen config matches the wave-2 default quality (Δ MRR@5 +0.032 vs the
  400/k=5 default) at **≈804 input tokens/query instead of ≈2,279 (−65%)** —
  see the [HPO frontier](reports/figures/retrieval_hpo_frontier.html) with the
  chosen point starred, the [model comparison](reports/figures/model_comparison.html),
  and the [retrieval funnel](reports/figures/retrieval_funnel.html)
  (25/26 questions keep a relevant article after rerank).

**RAG quality** (`RAGEvaluator`, keyword judge, mock-mode answers, chosen config):

| Metric | Value | Note |
|---|---|---|
| context_recall | 0.962 | retrieval-side recall@3, matches the HPO |
| answer_relevance | 0.442 | scored against the fixed mock answer text |
| faithfulness | 0.273 | mock answer is canned, so grounding is intentionally weak offline |

Faithfulness/relevance here measure the deterministic offline answer; with
`LLM_BASE_URL`/`LLM_API_KEY` configured the agent retrieves and cites real
evidence, and the same harness scores its outputs.

**Operations (chosen config):**

| Metric | Value |
|---|---|
| p50 agent latency (mock, local floor) | 4.2 ms |
| p95 agent latency (mock, local floor) | 5.0 ms |
| Est. live cost per query (chosen config) | ≈ $0.00015 |
| Mock-mode cost floor per query | ≈ $0.00006 |
| Latency distribution | [histogram](reports/figures/latency_histogram.html) |

Latency in mock mode measures the local pipeline floor (retrieval + schema
validation without a provider round-trip); a live provider adds its network
and generation latency on top. Cost uses the rate card in `params.yaml`
($0.15/M input, $0.60/M output tokens) over the measured prompt+context size.
<!-- RESULTS:END -->

## Figures

| Figure | File |
|---|---|
| Corpus composition (EDA) | [reports/figures/eda_corpus_composition.html](reports/figures/eda_corpus_composition.html) |
| Retrieval quality vs chunk size (with random baseline) | [reports/figures/chunk_size_sweep.html](reports/figures/chunk_size_sweep.html) |
| Embedding model comparison | [reports/figures/model_comparison.html](reports/figures/model_comparison.html) |
| Retrieval funnel (aggregate) | [reports/figures/retrieval_funnel.html](reports/figures/retrieval_funnel.html) |
| Retrieval HPO frontier (chosen config starred) | [reports/figures/retrieval_hpo_frontier.html](reports/figures/retrieval_hpo_frontier.html) |
| Per-query latency histogram | [reports/figures/latency_histogram.html](reports/figures/latency_histogram.html) |
| Full HTML report | [reports/report.html](reports/report.html) |

## Reproduce

```bash
cd projects/01-rag-agent
uv run python -m rag_agent.cli prepare-corpus   # streams Wikipedia (bounded scan)
uv run python -m rag_agent.cli build-index      # 3 FAISS indexes (chunk-size sweep)
uv run python -m rag_agent.cli evaluate         # retrieval HPO + RAG + ops + cost telemetry
uv run python -m rag_agent.cli chat             # interactive demo (offline mock)
```

or, with DVC: `dvc repro` (stages in `dvc.yaml`, knobs in `params.yaml`).

To run with a live LLM instead of the mock, copy `.env.example` to `.env` and
fill in `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` — no code changes.

### Client-corpus onboarding

Point the same pipeline at a client knowledge base (JSONL files with
`{title, text, topic?}` records):

```bash
uv run python -m rag_agent.cli prepare-corpus --source client /path/to/jsonl --license "MIT"
uv run python -m rag_agent.cli build-index && uv run python -m rag_agent.cli evaluate
```

The intake reuses the Article schema, DQ gates, chunking, indexing and eval
unchanged; the dataset contract records `source: client://<dir>` and the given
license. `write_example_client_corpus(dest)` (in `rag_agent.corpus`) generates
a 3-document synthetic client corpus used by the onboarding tests.

### Cost telemetry & judge selection

- `evaluate` always writes `reports/cost_telemetry.json`: per-query
  input/output tokens and estimated cost against the `params.yaml` rate card,
  plus aggregates (n, totals, mean/p50/p95 cost per answer). With a live
  provider the mode is `"live"`; offline runs record the deterministic
  `"mock"` floor entry.
- `JUDGE=llm` (with provider credentials) switches the RAG evaluator to a
  pydantic-ai rubric judge returning structured `JudgeVerdict`s; without
  credentials it falls back gracefully to the keyword judge — the CI default
  stays deterministic.

Quality gates (from the repo root):

```bash
uv run ruff check projects/01-rag-agent
uv run ruff format --check projects/01-rag-agent
uv run mypy projects/01-rag-agent
uv run pytest projects/01-rag-agent -q
```

## What this demonstrates for a client

- **Grounded agents, not chat demos**: tool-restricted evidence access,
  structured citations, output-schema validation that fails loudly.
- **Measured quality**: graded retrieval metrics (recall@k, MRR) and LLM-judged
  faithfulness/relevance, plus a chunk-size sweep showing the
  quality/latency/cost trade-off with real numbers.
- **Production hygiene**: dataset contracts with checksums, DQ gates, DVC
  reproducibility, CPU-only footprint, offline capability, and an explicit
  cost-per-query estimate.
- **Provider portability**: one code path runs against any OpenAI-compatible
  endpoint or fully offline (ADR-0004).

## Data attribution

Corpus text is from Wikipedia (`wikimedia/wikipedia`, dump `20231101.en`),
licensed under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)
and [GFDL](https://www.gnu.org/licenses/fdl-1.3.html). Article titles and
content remain the property of their respective authors; see the dataset
contract in `data/raw/dataset_contract.json`.
