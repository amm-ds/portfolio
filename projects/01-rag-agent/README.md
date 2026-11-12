# Project 01 — RAG & Agentic AI Assistant

A grounded question-answering assistant over a pinned 593-article English
Wikipedia corpus. `pydantic-ai` restricts corpus access to retrieval tools and
returns structured, cited answers. Retrieval combines MiniLM embeddings, FAISS,
and cross-encoder reranking.

The runtime default is local Ollama (`qwen3.6:35b-a3b-q4_K_M`); any
OpenAI-compatible endpoint uses the same path. There is no runtime mock.
**`kimi-for-coding` is the selected provider for the reported evaluation**,
which covers a 65-question tuning set and a sealed 55-question held-out set.

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

The held-out set holds 55 fresh questions: 32 single-hop, 10 multi-hop, and
13 unanswerable — the original 15 plus 40 expansions written after tuning
froze. Programmatic gates check corpus support, absent terms, and Jaccard
separation from the tuning set before scoring; the 40 expansions also pass an
answerability gate. The selected hosted pass uses verification and the rubric
judge, without RAGAS.

| metric | sealed held-out result |
|---|---:|
| failure taxonomy | 44 correct / 9 unsupported-claim / 1 retrieval-miss / 1 format-failure |
| correct share (95% CI) | **0.80 [0.69, 0.89]** |
| operational retrieval recall@5 / recall@10 | 0.745 / 0.764 |
| retrieval MRR@5 (random floor) | 0.718 (0.055) |
| Δ over the random floor | recall@5 +0.691 · MRR@5 +0.688 |
| rubric faithfulness, 42 answerable | 0.6338 [0.5726, 0.7021] |
| rubric answer relevance, 42 answerable | 0.7114 |
| rubric context recall, 42 answerable | 0.9762 |
| required refusals | 12/13 (accuracy 0.92, CI [0.77, 1.0]) |
| latency p50 / p95 | 24.443 s / 126.811 s |
| whole-pass meter | 241 calls / $1.950667 cloud-equivalent |

The failure taxonomy is the headline: of the 11 failures, 9 retrieved the
relevant article at rank 1 (fetched and cited) yet kept unsupported claims,
one was a top-k demotion (relevant at rank 7, outside the fetch), and none
was a raw retrieval miss. Held-out retrieval reads are bounded by the
answerability gate, so the honest read is that generation grounding — not
retrieval — remains the bottleneck. The sealed set is still one small slice,
not evidence of broad-corpus or unattended readiness.

A dedicated citation-correctness pass re-answers the sealed set once with
claim-level verify records persisted (`evaluate --citations`, reported under
`metrics.json → detail.heldout_citations`; the headline `detail.heldout` is
never touched). Across 42 verified answers: 258 claims drafted, 0.903
supported by the cited passage at first check (CI [0.868, 0.938]), 16
repaired, 11 dropped, mean answer support 0.978 — and the five
unsupported-claim answers drafted at 0.74 first-check support vs 0.93 for
correct ones. The pass meters 236 calls / $1.583466 cloud-equivalent
(p50 25.351 s, p95 84.681 s).

An independent stress set closes the loop the audits asked for: 30 questions
admitted at article level only, with no production-retriever answerability
gate — negation, cross-article comparisons, temporal traps, and six
questions built to tempt an answer from plausible-but-unjustified chunks.
The stress pass (`evaluate --stress`, `metrics.json → detail.stress`) keeps
16 of 30 correct (0.53, CI [0.37, 0.70]) against 0.80 on the gated set; 11
of the 14 non-correct outcomes keep unsupported claims with retrieval intact;
refusal accuracy falls to 0.60 (6/10) on the abstain rows. The gated set
measured consistency — this set measures the drop: 123 calls, $1.932540
cloud-equivalent.

R6 hardened grounding against that baseline, measured pre-registered
(`detail.stress_after_r6`, `reports/question_traces_stress_after_r6.json`,
per-row outcomes in `reports/stress_failure_ledger.md`): schema-v2 answers
draft claims with verbatim evidence spans; deterministic number/date/
negation checks run ahead of the entailment judge; repair-and-drop; the
evidence gate refuses on empty evidence. Normalized comparison (same
classifier both sides, baseline row 14 reclassified budget-terminated):
overall 0.500 → 0.733 (CI [0.567, 0.867]); answer-expected 0.450 → 0.700;
unsupported claims 11 → 5; refusal accuracy 0.600 → 0.800; false abstention
0.050 → 0.050. Claim pipeline: 54 drafted / 8 mech-failed / 9 repaired /
54 surviving; the mech checker's false-rejection rate is 8.6% on tuning
diagnostics (≤10% guardrail). Latency layers: end-to-end hosted answer p50
23.0 s / p95 532 s (retrieval + generation + verify/repair in the critical
path); verify overlay mean 5.9 s (6.6% of answer time); the full 30-question
pass ran ≈50 min wall at the 80M-token rail, $9.74 cloud-equivalent (129
calls). The measurement also exposed a schema defect: the pre-R6 citation
mandate made honest refusal unrepresentable, burning up to ~33M tokens in
tool loops on unanswerable rows — fixed (refusal = empty citations/claims +
stop), which is what let all six unanswerable rows refuse correctly.
Independent set B (`data/golden_stress_b.json`, absolute targets
pre-registered in the story) is scored once under `detail.stress_b`.

### Cost and budget operation

Costs use the public reference rate card ($1/Mtok input, $4/Mtok output, cached
reads at 30%). They are cloud-equivalent estimates, not billed amounts. The
meter records successful calls; the UsageLimits token counter additionally
counts failed/retried traffic (cached prefix re-reads and aborted rows) —
the two diverged by ~5x on one pass, which is how a schema-level tool loop
was found. Tuning cost is reported as answer generation per
query before judging and verification; no replacement end-to-end tuning-suite
total is claimed.

The sealed 55-question pass meters:

| phase | calls | cloud-equivalent spend |
|---|---:|---:|
| agent | 54 | $1.574388 |
| judge | 108 | $0.145988 |
| verify | 79 | $0.230291 |
| RAGAS | 0 | $0.000000 |
| **total** | **241** | **$1.950667** |

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
unsupported-claim outcomes, and the sealed pass keeps 44 of 55 correct with
9 of 11 failures grounded anyway at rank-1 retrieval. Local repair
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
