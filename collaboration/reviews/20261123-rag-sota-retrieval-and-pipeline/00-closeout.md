# Close-out: Judge Calibration V2 (Rev 5) + SOTA Retrieval & Agent Loop Readiness

Date: 2026-11-23
Executor: Kimi Code
Handoffs executed:
- `collaboration/designs/20261122-rag-execution-plan/03-implementation-handoff.md` (Revision 5, Phase A)
- `collaboration/designs/20261123-rag-sota-retrieval-and-pipeline/03-implementation-handoff.md` (Phases A–D; Phase E end-to-end run remains gated on owner review of the judge sample)
Review context: `collaboration/reviews/20261122-rag-execution-plan/01-review-response.md`
Branch: `phase0-infra-2026-11-22`. **No commits, no pushes, no merges; project 02 untouched.**

## Phase A — Judge Calibration V2 (Revision 5)

Stuck Revision-4 builder interrupted; all 5 Revision-5 fixes applied to
`scripts/build_judge_calibration_v3.py`:

1. Draft cache: `generate(..., temperature, seed)` returns the cached response
   when `prompt_sha256` matches — 51 prior `attempt1` drafts reused instantly.
2. 8-gram scope by claim text: collision check is
   `(token8(negative) - src_grams) & (other_supported_grams | accepted_neg_grams)`
   — a negative no longer collides with its own source claim (the Rev-4
   blocker); duplicate supported texts in the archive are excluded by claim text.
3. `changed_term_ok`: word-boundary match for alphanumeric-bounded terms
   ("complete" no longer matches "incomplete"); `<4`-char terms allowed when
   they contain a digit ("25%" passes).
4. Retries: attempt > 1 appends the failure reason to the prompt and varies
   `temperature = 0.25 * (attempt - 1)`, `seed = SEED + attempt`.

**Build result**: 147 claims (75 supported kept unchanged + 72 negatives,
**3 dropped** after 3 redrafts each — acceptance is ≥ 70 negatives: PASS).
Shared-content-word overlap distribution (negatives vs their chunk):
5:2, 6:6, 7:5, 8:7, 9:5, 10:8, 11:19, 12:6, 13:4, 14:4, 15:2, 16:2, 17:2.
Manifest: `data/judge_v2_claims.sha256.json` (digest `07d35212591f…`,
supersedes pointer to `superseded_v2a/`).

**Labelling**: 147/147 claims labelled with kimi-for-coding (named host
api.kimi.com, recorded before the first call), same prompt as Revision 3,
blind to construction. Zero errors, zero parse failures.
**Spend: $0.094784 estimated this run (147 calls); $0.199375 cumulative across
the v2a ($0.104551) and v3 ($0.094784) runs — $2.80 remains of the $3.00 cap.**
Model labels match construction truth 147/147 — reported as information only;
**agreement against the owner's hand labels is NOT computed** (stop rule).

Owner sample: `reports/judge_calibration_v2/owner_sample.json` — 30 items,
seed 44, unlabelled, each with `index`, `claim`, `chunk_id`, **and
`chunk_text`** (Revision-4 requirement; found missing on first draw, fixed in
`draw_owner_sample`, redrawn with the same seed so the item set is unchanged).

## Phase B — SOTA Retrieval Ladder (100% local, $0 hosted spend)

`measure_retrieval.py` extended: `heldout_55` split (`golden_heldout.json`),
`fusion_rrf` / `rrf_pool_size` / `max_per_article` (wired into `Retriever`),
and multi-hop metrics — `all_articles_at_5`, `article_coverage_at_5`,
`gold_chunk_coverage_at_5` — top-level and per slice. A
`gold_chunk_coverage` empty-list division bug was found on the first ladder
attempt, fixed, and the 5 bogus `not_run` log rows removed.

All 16 runs `HF_HUB_OFFLINE=1`, request_hosts `[]` (or `127.0.0.1` for the
Ollama arm — none this phase). Format: all_articles@5 / recall@5 / MRR@5.

| arm | dev_v1 | dev_40 | dev_65 | heldout_55 |
|---|---|---|---|---|
| R0 baseline (size 200) | 0.875 / 1.000 / 0.969 | 0.719 / 1.000 / 0.969 | 0.745 / 0.964 / 0.945 | 0.952 / 0.976 / 0.940 |
| S1 structure_200 | 0.875 / 1.000 / 1.000 | 0.781 / 1.000 / 0.984 | 0.836 / 1.000 / 0.976 | 0.929 / 1.000 / 0.982 |
| S2 structure_hybrid_rrf | 0.812 / 1.000 / 1.000 | 0.719 / 1.000 / 0.984 | 0.782 / 0.982 / 0.973 | 0.929 / 1.000 / 0.982 |
| **S3 structure_hybrid_diverse** | **0.938 / 1.000 / 1.000** | **0.906 / 1.000 / 0.984** | **0.891 / 0.982 / 0.973** | **0.976 / 1.000 / 0.982** |

Winner by `(all_articles_at_5, recall_at_5, mrr_at_5)` on dev_65 and
heldout_55 (tie-break S1<S2<S3): **S3** — best on both splits at the first
tuple element (0.891 dev_65, 0.976 heldout_55).

**Single one-time final_v3 run (S3)** — `reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json`,
gold mode `chunk_exact`, hosts `[]`:

| metric | R0 (earlier one-time) | S3 | delta |
|---|---|---|---|
| recall@5 | 0.9239 | **0.9457** | +2.2 pts |
| MRR@5 | 0.8793 | **0.8877** | +0.8 pts |
| single_hop recall@5 | 0.9706 | **0.9853** | +1.5 pts |
| multi_hop recall@5 | 0.7917 | **0.8333** | +4.2 pts |
| all_articles_at_5 | n/a (new metric) | 0.8804 | — |
| gold_chunk_coverage_at_5 | n/a (new metric) | 0.8859 | — |

S3 beat R0 on final_v3 with **no slice regression** → promotion applies.

## Phase C — Production Promotion & Agent Loop Bounds

Promoted into `src/rag_agent/`:

- `config.py`: `RAGConfig` + `RetrievalBest` gained `chunk_mode`
  ("size"|"structure"), `fusion_rrf`, `rrf_pool_size`, `max_per_article`; the
  bounded agent-loop rails `agent_request_limit=12`,
  `agent_tool_calls_limit=16`, `agent_input_tokens_limit=200_000`.
- `index.py`: `chunk_articles(..., chunk_mode)` (structure → title-prefixed
  chunks); `Retriever.search` fuses dense + BM25 via
  `reciprocal_rank_fusion(k=60)` over `rrf_pool_size` when `fusion_rrf`, and
  applies the per-article cap with score-order backfill when `max_per_article`.
- `agent.py`: `search_documents` top_k clamped to 1..10; new
  `agent_usage_limits(config)` combining platform `budget_limits()` with the
  rails (dataclasses.replace — UsageLimits is a frozen dataclass).
- `evaluate.py`: the agent call now uses `agent_usage_limits(config)`;
  `answer_with_output_retries` takes `config`.
- `cli.py`: `build-index` passes `chunk_mode` through.
- `params.yaml`: top-level `chunk_mode: structure`, `fusion_rrf: true`,
  `rrf_pool_size: 50`, `max_per_article: 2`, `rerank_multiplier: 6`;
  `retrieval_best` carries the same (matches `reports/metrics.json
  detail.hpo.chosen` convention — the metrics.json mirror itself is NOT
  edited in this handoff; flagged for Claude's commit pass).
- Production index rebuilt: `data/index/chunks_200` = 3,589 structure-mode
  chunks (MiniLM), matching the promoted winner.

Tests added: `tests/test_index.py` (structure-mode chunking incl. id stability
and token budget; fusion executes with lazy BM25 and valid citations;
max_per_article=2 caps with backfill to k=5) and `tests/test_agent.py`
(`agent_usage_limits` defaults + custom rails; `search_documents` top_k=50
reaches retrieval clamped to 10 via a tool-calling FunctionModel recording
deps). All green.

## Phase D — Gates (verbatim)

From `projects/01-rag-agent`:

- `uv run pytest --cov` → exit 0, **`181 passed, 2 warnings in 7.47s`**
  (was 176; +5 new tests). Gate TOTAL 88%; src/rag_agent precise **81.14%** —
  above the 78.45% floor.
- `uv run ruff check .` → **`All checks passed!`**
- `uv run ruff format --check .` → **`70 files already formatted`**
- `uv run mypy .` → **`Success: no issues found in 37 source files`**

From repo root: `uv run python scripts/check_docs.py` → **`check-docs: OK`**

## Files (all uncommitted, per handoff)

- New/changed code: `scripts/build_judge_calibration_v3.py` (Rev 5),
  `scripts/label_judge_calibration_v2.py` (claim-count gate + sample
  chunk_text), `scripts/measure_retrieval.py` (heldout_55, multi-hop metrics,
  fusion/diversity), `configs/sweeps/s{1,2,3}_*.yaml` (new),
  `src/rag_agent/{config,index,agent,evaluate,cli}.py`,
  `tests/test_index.py`, `tests/test_agent.py`, `params.yaml`.
- Data/reports: `data/judge_v2_claims.json` (+ sha256 manifest),
  `reports/judge_calibration_v2/raw/*.json` (147),
  `reports/judge_calibration_v2/owner_sample.json`,
  `reports/judge_calibration_v2/drafts/neg_*`,
  `reports/retrieval_sweeps/s{1,2,3}__{4 splits}.json` +
  `s3_structure_hybrid_diverse__final_v3.json`,
  `reports/experiment_log.json` (all rows), rebuilt `data/index/chunks_200`.
- Gitignored-written-not-committed (as before): `reports/experiment_log.json`,
  `reports/retrieval_sweeps/`, `reports/judge_calibration_v2/` — committing
  needs the owner's `.gitignore` exception decision (Revision 1 binding 2).
- The 27 `redraft_*` provenance files and 35 pre-existing paths remain
  unstaged. Project 02 untouched. Zero hosted calls outside Phase A labelling.

## Owner decisions needed

1. Hand-label the 30-item owner sample; then agreement vs kimi-for-coding is
   computed (85% gate unchanged) — this unblocks Phase E (end-to-end run).
2. Commit strategy for this handoff's surfaces (Claude reviews/validates/
   commits) + the standing gitignore-exception question for logs/sweeps.
3. `reports/metrics.json detail.hpo.chosen` mirror of `retrieval_best` — update
   to match params.yaml (not in this handoff's surfaces).
4. Spend split: step 1 used $0.199375 of the shared $3.00 cap; the rest is
   reserved for the end-to-end run.
