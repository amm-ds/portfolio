# Project 01 — RAG & Agentic AI Assistant

Agentic-AI flagship of the portfolio: a grounded question-answering assistant
over a curated slice of English Wikipedia, built on `pydantic-ai` with
structured, cited outputs. Retrieval is embeddings + FAISS with cross-encoder
reranking; the agent runs on a **local model via Ollama (default
`qwen3.6:35b-a3b-q4_K_M` platform default; `qwen3:32b` and `gpt-oss:20b` are documented alternatives)** or any
OpenAI-compatible endpoint — there is no runtime mock, and quality is measured
as a **provider A/B**: local qwen3.6 (30-q subset, $0 API) vs hosted
`kimi-for-coding` (full 65-q golden set, every LLM phase metered under a USD
cap).

- Design record: [DESIGN.md](DESIGN.md)
- Live artifacts: `reports/report.html`, `reports/metrics.json`, `reports/figures/`, `reports/cost_telemetry.json`
- Data contract: `data/raw/dataset_contract.json` (sha256-pinned)

## Problem

Give a user (or downstream system) answers that are **traceable to evidence**:
the agent is constrained to retrieved Wikipedia passages, returns citations, and
can abstain when support is insufficient. This reduces unauditable answers but
does not eliminate unsupported claims; retrieval, generation, and abstention are
therefore measured on a graded question set rather than demoed anecdotally.

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
local Ollama second (default `qwen3.6:35b-a3b-q4_K_M`). There is no runtime mock.
The runtime path is drawn as a mermaid diagram in the
[case study](https://amm-ds.github.io/portfolio/projects/01-rag-agent/) —
retrieval lanes, provider seam, verify loop. See
[DESIGN.md](DESIGN.md) for options considered and SLOs.

## Results

Measured twice on the same pipeline — a **provider A/B**. Retrieval metrics
are provider-independent (embeddings-only) and identical in both passes;
`reports/metrics.json` holds the hosted pass.

- **Local** `qwen3.6:35b-a3b-q4_K_M` via Ollama — LLM phases bounded to the
  first 30 graded questions (local inference wall clock), verify loop ON.
- **Hosted** `kimi-for-coding` (OpenAI-compatible endpoint, membership
  quota) — the full 65-question golden set with `evaluate --ragas --verify`;
  every LLM phase metered into the platform spend ledger under a hard USD
  cap. Costs are **cloud-equivalent estimates** at the public kimi-k2.8
  reference card ($1/Mtok in, $4/Mtok out, cached reads 30%) — the key is
  membership quota, so these are rate-card equivalents, never billed amounts.

| Metric | Local qwen3.6-q4 (n=30) | Hosted kimi-for-coding (n=65) |
|---|---|---|
| Failure taxonomy | 15 correct / 14 unsupported / 1 format | 44 correct / 18 unsupported / 2 retrieval-miss / 1 format |
| RAGAS faithfulness (95% CI) | 0.606 | **0.685 [0.605, 0.760]** |
| RAGAS answer relevancy | 0.720 | **0.878 [0.820, 0.918]** |
| RAGAS context precision / recall | 1.000 / 0.978 | 0.760 [0.667, 0.849] / 0.978 [0.954, 0.995] |
| Rubric-judge faithfulness | 0.441 [0.29, 0.61] | 0.550 [0.483, 0.611] |
| Refusal accuracy | 0.857 [0.57, 1.00] | 0.900 [0.70, 1.00] |
| False-abstention rate | 0.174 | 0.036 |
| Cite-when-expected | 0.957 | 0.964 |
| Verify overhead | 33 repair calls | 39 repair calls (125 verify calls) |
| Agent latency p50 / p95 | 61 s / 245 s (load-contended local) | **23 s / 175 s** (see caveat below) |
| Cost | $0 API (≈$0.0068/query cloud-equiv) | **$3.58 cloud-equiv, metered per phase** |

Reading: grounding tracks the provider — hosted RAGAS faithfulness is +0.08
over local (directional: different denominators, 30 vs 65 questions, and
different judge models), with refusal behavior sharper hosted (false
abstention 0.036 vs 0.174). Retrieval is solid in both passes (0.831 vs
0.031 random), so generation grounding remains the bottleneck.

### Held-out golden set (wave 16)

Everything above is measured on the 65 tuning questions. A **sealed
held-out set** — 15 fresh questions written after tuning froze (8
single-hop, 2 multi-hop, 5 unanswerable) — is gated programmatically before
it is ever scored (answerable questions must hit a relevant chunk in the
production top-10; unanswerable ones carry `absent_terms` verified against
the whole corpus; a Jaccard check rejects variations of the 65) and then
run with `evaluate --heldout`: retrieval metrics + one verify-on agent pass
(agent + verify + rubric judge, no RAGAS), reported separately under
`metrics.json → detail.heldout`.

Hosted `kimi-for-coding` pass (verify ON, 2026-10-18):

| Metric | Held-out (n=15) | Tuning set (n=65) |
|---|---|---|
| Retrieval recall@5 / recall@10 | 0.600 / 0.667 | 0.831 / 0.846 |
| Retrieval MRR@5 (random floor) | 0.567 (0.022) | 0.808 (0.018) |
| Rubric-judge faithfulness (95% CI) | 0.62 [0.45, 0.79] (n=10 answerable) | 0.550 [0.483, 0.611] |
| Failure taxonomy | 10 correct / 4 unsupported-claim / 1 retrieval-miss | 44 / 18 / 2 / 1 |
| Refusal accuracy (unanswerable) | 1.00 [1.00, 1.00] (5/5) | 0.900 [0.70, 1.00] |
| Verify overhead | 7 repair calls, mean support 0.956 | 39 repair calls |
| Latency p50 / p95 | 24.7 s / 36.6 s | 23 s / 175 s |
| Cost | $0.25 cloud-equivalent (66 calls, 47% cached) | $3.58 cloud-equivalent (922 calls) |

Reading: the held-out set is harder than the tuning set — recall@5 0.600
vs 0.831 — which is the point of a sealed set written fresh (several
held-out articles sit deeper in the ranking, and one multi-hop question
misses the top-5 entirely). Refusal stays perfect (5/5 unanswerable
abstained, zero false abstentions) and the run costs 14x less than the
tuning pass, so it can re-run every wave as a regression gate.

**Golden-set composition**: 65 graded questions — 44 single-hop, 11 multi-hop,
10 unanswerable (expected behavior: abstain), validated against the actual
corpus.

### Hosted cost & budget discipline (wave 15)

`reports/cost_telemetry.json` carries the per-phase meter (calls,
input/output/cached tokens, spend) beside the legacy per-query fields:

| Phase | Calls | Input tok | Output tok | Cached share | Spend (cloud-equiv) |
|---|---|---|---|---|---|
| agent | 64 | 3.72M | 103K | 90.0% | $1.79 |
| ragas | 605 | 713K | 167K | 50.4% | $1.13 |
| verify | 125 | 220K | 75K | 35.7% | $0.47 |
| judge | 128 | 106K | 22K | 1.5% | $0.19 |
| **total** | **922** | **4.76M** | **367K** | **79.6%** | **$3.58** |

The USD cap (`LLM_COST_LIMIT_USD`) is enforced per run by the platform
spend ledger: the first hosted pass tripped it at $3.04 mid-run and the CLI
exited cleanly with actionable guidance; the re-run completed under a
raised, **logged** cap (env override only — `.env` untouched). Only
successful calls are metered, so true quota burn is somewhat higher than
$3.58 (the failed runaway attempt below is not counted).

Honest hosted caveats: the lone format-failure is the per-run token guard
(`LLM_TOTAL_TOKENS_LIMIT`) cutting off a runaway tool-loop question (4.06M
tokens attempted on "How did the French Revolution change European
politics?"), not a schema failure — the wave-15 output-retry (≤2 retries,
counted per question in `question_traces.json`) recovered the run's one
schema-invalid draft. The p95 latency tail is that same looping question;
typical answers are p50 ≈ 23 s including verification. Provider sampling is
fixed server-side — the endpoint rejects explicit temperature, which the
platform preset omits (and RAGAS's per-call temperature mutation is
neutralized in `MeteredChatOpenAI`).

### Wave 14 — verify-then-answer loop (local A/B history)

Every drafted answer now passes a **claim verifier** before it reaches the user or
the judges (`rag_agent.verify`, on by default — design in
[DESIGN.md](DESIGN.md#37-verify-then-answer-loop-wave-14)): the summary is split
into claims, each claim is entailment-checked against the *full text* of its cited
chunks by the local judge (one batched call, validated verdicts; deterministic
keyword entailment as CI/offline fallback), unsupported claims are **repaired**
(one stricter regeneration call each, ≤ `verify.max_repair_calls`) or **dropped**,
and when the surviving-claim fraction stays below `verify.min_support` (0.6) the
answer **falls back to abstention** (refusal + confidence < 0.3, integrating with
the existing abstention path). `evaluate --verify/--no-verify` A/Bs the loop.

**A/B on the same first-30 bounded subset** (local `qwen3.6:35b-a3b-q4_K_M`,
verify ON vs the wave-13 baseline pass):

| Metric | Verify OFF (wave 13) | Verify ON (wave 14) |
|---|---|---|
| failure taxonomy | 12 correct / 18 unsupported-claim | **15 correct / 14 unsupported-claim** (+1 format-failure: an agent output-retry hiccup under load, not verify) |
| RAGAS faithfulness | 0.651 [0.52, 0.78] | 0.606 [0.44, 0.78] |
| RAGAS answer relevancy | 0.879 [0.82, 0.93] | 0.720 [0.56, 0.86] |
| rubric-judge faithfulness | 0.283 | 0.441 [0.29, 0.61] |
| false-abstention rate | 0.000 | 0.174 [0.04, 0.35] (4 support-floor abstentions) |

**Honest verdict.** The target metric moved — unsupported-claim share fell from
60% to 47% — but the mechanism is mostly **abstention, not repair**: of the 6
unsupported→correct conversions, 3 are support-floor refusals (which the rubric
judge scores faithful because a refusal makes no claims) and 3 are kept/repaired
answers; one verify-induced abstention still landed in unsupported-claim (judge
scored the refusal 0.0). RAGAS faithfulness did **not** improve (0.651 → 0.606,
CIs overlapping) and answer relevancy dropped (0.879 → 0.720) as answers got
shorter or became refusals. Judge noise is comparable to the delta — the same
run judged a duplicated question 1.0 and 0.2 — so a 30-question pass cannot
resolve effects this size. Repairs/drops are designed to remove claims judged
unsupported, but 14 unsupported-claim outcomes remain and verifier/judge errors
are still possible. Per-claim repair quality at this local-model scale is weak;
the measured lever that moves the taxonomy is the support floor. Verdict:
**keep verify on (default) — the failure taxonomy improves, but grounding is
not guaranteed and the faithfulness delta is unresolved at n=30**; prefer
retrieval-side or prompt-side grounding gains over repair-call volume.

**Overhead** (`metrics.json → detail.verify`, local, run under machine
contention): mean verify latency **171 s per answer**, i.e. **+157% on top of
the agent phase** (one batched verdict call per answer, 33 repair-regeneration
calls over 29 verified answers ≈ 1.1/answer, plus one re-verification per
successful repair; mean claim-support fraction 0.84). The dominant cost is
repair regeneration — lowering `verify.max_repair_calls` trades taxonomy gain
for latency directly. On hosted models this is seconds of API time, not
minutes of wall clock.


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
uv run python -m rag_agent.cli evaluate --ragas --verify   # real run (needs a provider)
uv run python -m rag_agent.cli evaluate --heldout          # sealed held-out pass (needs a provider)
uv run python -m rag_agent.cli chat             # interactive demo (needs a provider)
```

The agent, the LLM judge and the RAGAS evaluator need a model provider: local
Ollama (default `qwen3.6:35b-a3b-q4_K_M`, already pulled on this machine; `gpt-oss:20b` is a
documented lighter alternative) or an OpenAI-compatible endpoint via
`LLM_BASE_URL`/`LLM_API_KEY` in `.env`. There is no runtime mock — when no
provider answers, the CLI prints the setup guidance and exits. `evaluate
--offline` is the CI-safe path (retrieval HPO only, no LLM calls).

Local 32B inference is the bottleneck: on Ollama the documented real run
bounds the LLM phases to the first 30 graded questions with
`--max-questions 30` (retrieval metrics always use the full 65); the hosted
pass runs the full set in ~90 minutes. qwen3 thinking is disabled for the
evaluation (`think: false`, ~4× faster per call; the hosted preset disables
thinking via `extra_body` instead) — a documented latency/depth trade-off.

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
  hosted models. Hosted runs add the wave-15 per-phase meter
  (agent/judge/verify/ragas calls, tokens, cached share, cloud-equivalent
  spend) with the platform spend ledger enforcing `LLM_COST_LIMIT_USD` per
  run — a tripped cap stops the CLI cleanly (exit 2), it never degrades into
  fallback judges.
- The RAG judge defaults to the provider model (LLM rubric judge returning
  structured `JudgeVerdict`s); `JUDGE=keyword` selects the deterministic
  platform keyword judge (used by `--offline` and CI). Runtime judge failures
  fall back per-verdict to the keyword judge.
- The wave-14 claim verifier follows the same contract: provider-model
  entailment verdicts by default, `VERIFY_JUDGE=keyword` for the deterministic
  CI/offline floor, per-batch keyword fallback on runtime failures.
- `--ragas` adds the RAGAS metric set (faithfulness, answer_relevancy,
  context_precision, context_recall) scored by the active provider — $0 on
  local Ollama, metered on hosted endpoints (RAGAS's own cost callbacks don't
  recognize this OpenAI-compatible endpoint, so usage is captured at the
  wrapped-call boundary in `MeteredChatOpenAI`).
- `evaluate --heldout` scores the sealed 15-question held-out golden set (see
  **Results**): retrieval metrics + one verify-on agent pass (agent + verify +
  rubric judge, deliberately no RAGAS), reported under
  `metrics.json → detail.heldout` and `question_traces_heldout.json`, metered
  under the same USD cap.

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

## Roadmap

- **Delivered:** reproducible retrieval (checksum-pinned corpus, CPU FAISS +
  MiniLM + cross-encoder rerank), a provider seam running one code path on
  local Ollama or any OpenAI-compatible endpoint, the verify-then-answer loop
  (batched claim entailment, capped repair, support-floor abstention),
  separate rubric/RAGAS judges with bootstrap CIs, a sealed 15-question
  held-out regression gate ($0.25 cloud-equivalent per re-run), and per-phase
  cost/latency metering under a hard USD cap.
- **Deferred:** grounding and repair improvement, then re-measurement on
  noisier corpora — blocked on a fresh external corpus (the data registry
  holds only this Wikipedia slice); the current local A/B gains mainly come
  through abstention, and repair quality at local-model scale is weak.
- **Deferred:** no broad-corpus quality claim and no always-on public chat —
  held-out retrieval drops to 0.600, and live hosted calls need an explicit
  cost budget (`RAG_CHAT_ENABLED=1` stays opt-in).

## Data attribution

Corpus text is from Wikipedia (`wikimedia/wikipedia`, dump `20231101.en`),
licensed under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)
and [GFDL](https://www.gnu.org/licenses/fdl-1.3.html). Article titles and
content remain the property of their respective authors; see the dataset
contract in `data/raw/dataset_contract.json`.
