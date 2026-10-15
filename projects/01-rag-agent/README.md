# Project 01 — RAG & Agentic AI Assistant

Agentic-AI flagship of the portfolio: a grounded question-answering assistant
over a curated slice of English Wikipedia, built on `pydantic-ai` with
structured, cited outputs. Retrieval is embeddings + FAISS with cross-encoder
reranking; the agent runs on a **local model via Ollama (default
`qwen3.6:35b-a3b-q4_K_M` platform default; `qwen3:32b` and `gpt-oss:20b` are documented alternatives)** or any
OpenAI-compatible endpoint — there is no runtime mock, and quality is measured
with RAGAS using the local model as evaluator ($0 API cost).

- Design record: [DESIGN.md](DESIGN.md)
- Live artifacts: `reports/report.html`, `reports/metrics.json`, `reports/figures/`, `reports/cost_telemetry.json`
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
ADR-0004 (amended wave 10): env-configured OpenAI-compatible endpoint first,
local Ollama second (default `qwen3.6:35b-a3b-q4_K_M`). There is no runtime mock. See
[DESIGN.md](DESIGN.md) for options considered and SLOs.

## Results

Measured on this machine with a **local Ollama model** (`qwen3.6:35b-a3b-q4_K_M`,
the platform default at run time — reproduce with
`OLLAMA_MODEL=qwen3.6:35b-a3b-q4_K_M`; any OpenAI-compatible endpoint works
too). Retrieval metrics use the full graded set; the LLM phases (agent answers,
judges, RAGAS) are bounded to the **first 10 questions** because local
inference is the bottleneck — stated plainly, not hidden. Full detail in
`reports/metrics.json` (`dvc metrics show`); interactive figures in
`reports/figures/`.

<!-- RESULTS:START -->
Corpus: **593 articles** (5 topics, ≤120 each plus exact-title anchors),
**26 graded questions** (retrieval), **10 questions** (LLM phases), 0 skipped.
Backend: `ollama:qwen3.6:35b-a3b-q4_K_M` — local inference, $0 API cost.
Run date: 2026-10-14/15; eval wall time ≈ 116 min for the bounded run.

**Retrieval HPO** — chunk-size sweep against a seeded uniform-random baseline,
plus embedding-model comparison, rerank ablation and a top_k sweep; the
production config (`retrieval_best` in `params.yaml`, mirrored in
`metrics.json → detail.hpo.chosen`) is selected from these measurements:

| Configuration | recall@5 | recall@10 | MRR@5 | random recall@5 | Δ MRR@5 vs random |
|---|---|---|---|---|---|
| chunks=200, top_k=10 | **0.962** | 1.000 | **0.936** | 0.038 | +0.897 |
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
  chosen config matches the earlier default quality (Δ MRR@5 +0.032) at
  **≈804 input tokens/query instead of ≈2,279 (−65%)** — see the
  [HPO frontier](reports/figures/retrieval_hpo_frontier.html) with the chosen
  point starred and the [retrieval funnel](reports/figures/retrieval_funnel.html).

**RAG quality — RAGAS** (10-question bounded subset, local model as evaluator,
chosen config; `evaluate --ragas`):

| RAGAS metric | Value | Reading |
|---|---|---|
| faithfulness | **0.805** | the answer is supported by the retrieved context |
| answer_relevancy | **0.904** | the answer addresses the question |
| context_recall | **0.952** | retrieved contexts cover the reference (graded article lead) |
| context_precision | **0.333** | on average 1 of the top-3 contexts is graded-relevant — expected at top_k=3 with saturated recall; precision at the top of the list is the reranker's job |

**CI-offline floor** — the deterministic keyword judge on the same subset
(`evaluate --offline`): faithfulness 0.36, answer_relevance 0.37. The delta
vs RAGAS is the point of having both: keyword overlap is a cheap lower-bound
proxy (it cannot recognize paraphrase or entailment), while RAGAS asks the
model whether claims are actually supported. Judge failures fall back per-
verdict to the keyword floor, so numbers never block a run.

**Operations (chosen config, local model):**

| Metric | Value |
|---|---|
| p50 agent latency | **61 s** per query (retrieval + tool round-trips + generation) |
| p95 agent latency | **245 s** per query |
| API cost | **$0** — local inference (eval is compute-bound) |
| Equivalent cloud cost (rate-card hypothetical) | mean ≈ $0.0043/query (p50 $0.0025, p95 $0.0113) at the `params.yaml` rate card |
| Avg tokens per query | ≈ 13.7k in / ≈ 3.7k out |
| Latency distribution | [histogram](reports/figures/latency_histogram.html) |
| Telemetry | [reports/cost_telemetry.json](reports/cost_telemetry.json) |

These are honest local-model timings: quality is free at the API line but
costs wall clock — the trade a client weighs against hosted-model per-token
pricing. qwen3 thinking was disabled for the evaluation (`think: false`, ~4×
faster per call), a documented latency/depth trade-off.
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
uv run python -m rag_agent.cli evaluate --ragas --max-questions 10   # real run (needs Ollama)
uv run python -m rag_agent.cli chat             # interactive demo (needs Ollama)
```

The agent, the LLM judge and the RAGAS evaluator need a model provider: local
Ollama (default `qwen3.6:35b-a3b-q4_K_M`, already pulled on this machine; `gpt-oss:20b` is a
documented lighter alternative) or an OpenAI-compatible endpoint via
`LLM_BASE_URL`/`LLM_API_KEY` in `.env`. There is no runtime mock — when no
provider answers, the CLI prints the setup guidance and exits. `evaluate
--offline` is the CI-safe path (retrieval HPO only, no LLM calls).

Local 32B inference is the bottleneck: the full 26-question RAGAS evaluation
takes hours, so the documented real run bounds the LLM phases to the first 10
graded questions with `--max-questions 10` (retrieval metrics always use the
full 26). qwen3 thinking is disabled for the evaluation (`think: false`, ~4×
faster per call) — a documented latency/depth trade-off.

or, with DVC: `dvc repro` (stages in `dvc.yaml`, knobs in `params.yaml`), then
`dvc metrics show` to read `reports/metrics.json` as tracked metrics.

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

- `evaluate` writes `reports/cost_telemetry.json`: per-query input/output
  tokens, eval wall time, and the active backend (`ollama:qwen3.6:35b-a3b-q4_K_M` or
  `env:<model>`). **Local inference = $0 API cost**; the rate-card numbers in
  the file are a clearly-labelled hypothetical for budget comparisons with
  hosted models.
- The RAG judge defaults to the provider model (LLM rubric judge returning
  structured `JudgeVerdict`s); `JUDGE=keyword` selects the deterministic
  platform keyword judge (used by `--offline` and CI). Runtime judge failures
  fall back per-verdict to the keyword judge.
- `--ragas` adds the RAGAS metric set (faithfulness, answer_relevancy,
  context_precision, context_recall) scored by the same local model — $0
  evaluation, honest local latencies.

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
- **Measured quality**: graded retrieval metrics (recall@k, MRR), RAGAS
  faithfulness/relevance/precision/recall scored by the local model, plus a
  chunk-size/top_k HPO with a seeded random floor — every quality claim has a
  number and a baseline.
- **Production hygiene**: dataset contracts with checksums, DQ gates, DVC
  reproducibility, CPU-only retrieval, $0-API local inference with honest
  latency reporting, and a client-corpus onboarding path.
- **Provider portability**: one code path runs against any OpenAI-compatible
  endpoint or local Ollama (ADR-0004, amended wave 10) — no runtime mocks.

## Data attribution

Corpus text is from Wikipedia (`wikimedia/wikipedia`, dump `20231101.en`),
licensed under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)
and [GFDL](https://www.gnu.org/licenses/fdl-1.3.html). Article titles and
content remain the property of their respective authors; see the dataset
contract in `data/raw/dataset_contract.json`.
