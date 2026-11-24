# Close-out: RAG execution plan (project 01) — steps 0, 2–6

Date: 2026-11-23
Executor: Kimi Code
Handoff: `collaboration/designs/20261122-rag-execution-plan/03-implementation-handoff.md`
(approved incl. Revision 1). Branch: `phase0-infra-2026-11-22`.
Step 1 skipped (blocked until the owner sets a Claude budget).
Constraints honored: zero hosted calls; no final_v3/sealed-120 read before step 5;
no writes outside the allowed surfaces; no `.gitignore`/`pyproject.toml` edits;
no `git add -f`; no push/merge; project 02 untouched; the 35 pre-existing
uncommitted paths never staged.

## Step 0 — prerequisites

- Branch confirmed: `phase0-infra-2026-11-22`.
- Coverage, handoff's literal gate `uv run pytest --cov` (from
  `projects/01-rag-agent`): `176 passed, 2 warnings in 7.83s`, combined TOTAL
  86.76%; project source aggregate (src/rag_agent, 21 files): **79.59%**
  (2847 stmts, 581 missed) — **floor 78.45% PASSES** (+1.14 pp).
  The earlier "No data was collected" defect did not reproduce: it appears only
  when addopts' `--cov=libs` applies alone; the bare `--cov` gate collects the
  project fine.
- Cross-check, stricter `--cov=src --cov-report=term-missing`: TOTAL 77.82%
  (2912 stmts) — below the floor, because source-scoping additionally counts
  the never-imported `local_models.py` at 0%. Recorded for the owner; the
  handoff's own command is the binding measurement.
- `git status --short` (35 paths, none staged by this work): 2 modified
  project-02 files (`reports_m5_full/`, untouched per handoff), 6 untracked
  design dirs under `collaboration/designs/`, and 27 untracked
  `reports/final_v3_drafts/redraft_*` files.

## Step 2 — pinned baseline on dev_v1

`scripts/measure_retrieval.py` (new) + `configs/sweeps/baseline.yaml`;
report `reports/retrieval_baseline/dev_v1.json`. Baseline arm reuses the
committed production index (`data/index/chunks_200`).

- Pinned config: chunk 200 / overlap 40 (size mode), MiniLM, top_k 3,
  rerank ON (`ms-marco-MiniLM-L-6-v2`).
- README "reranks the top 5 x k" vs top_k 3: the code fetches
  `k * rerank_multiplier = 15` candidates and reranks down to 3
  (`index.py` `Retriever.search`). Measurement ranks top_k=5 (25 candidates),
  production serving slice stays top_k=3; both token means are reported.
- **Baseline dev_v1: recall@5 1.0000 (16/16, Wilson 95% [0.8064, 1.0]),
  MRR@5 0.9688, mean context tokens 469 (top-3) / 793 (top-5).**
  request_hosts: none (local file loads only).
- Dev gold is article-level (relevant_titles → corpus articles → all their
  chunks), the only faithful mapping for tuning questions.

## Step 3 — sweeps on dev_v1

One change at a time vs baseline; full reports under
`reports/retrieval_sweeps/` (written, gitignored — see "Files" below).

| change | recall@5 | MRR@5 | tok top-3 | tok top-5 | hosts |
|---|---|---|---|---|---|
| baseline (200/MiniLM/ms-marco) | 1.0000 | 0.9688 | 469 | 793 | — |
| chunk_400 | 1.0000 | 0.9271 | 1023 | 1675 | none |
| chunk_800 | 1.0000 | 0.9531 | 1928 | 3102 | none |
| embed_bge (bge-small-en-v1.5) | 1.0000 | 0.9219 | 476 | 801 | none |
| embed_qwen3 (qwen3-embedding:0.6b via Ollama) | 1.0000 | 0.9375 | 469 | 798 | 127.0.0.1 |
| rerank_qwen (Qwen3-Reranker-0.6B) | 1.0000 | 0.9219 | 455 | 764 | none |

- **Structure-aware chunking arm: not triggered.** The handoff runs it "if one
  of the sizes wins"; all three sizes tie at recall@5 1.0 (no winner), and the
  larger sizes regress MRR while multiplying context tokens.
- **Embedding substitution (Revision 1 binding 4):** `qwen3-embedding:0.6b`
  (local Ollama) replaces `intfloat/e5-small-v2`, which is absent from the
  local HF cache and cannot be downloaded under the local-only rule. Recorded
  here and in `reports/experiment_log.json`.
- **Reranker code review (Revision 1 binding 1):** the cached
  `Qwen/Qwen3-Reranker-0.6B` snapshot `e61197ed45024b0ed8a2d74b80b4d909f1255473`
  contains no remote-code files (no `modeling_*.py`/`configuration_*.py`) —
  standard transformers config + safetensors + sentence-transformers modules.
  Loaded at the pinned revision with `trust_remote_code=False`; the arm ran.
- **Infra incident:** the first `embed_qwen3` attempt crashed with SIGABRT
  (OMP Error #15, duplicate libomp runtime: torch initializing lazily on the
  first rerank call after faiss searches) and the failure was masked by a
  `| tail` pipeline. Fixes in `measure_retrieval.py`: eager reranker load
  while faiss is already imported, per-batch Ollama progress logs, whole-run
  `not_run` recording on exceptions, and `full_config_sha` replacing
  `runner.config_hash` for the dataclass config. Retry passed.

## Step 4 — promote and grow

- Gate: recall@5 lift ≥ +0.10 on dev_v1. Baseline recall@5 = 1.0, so the gate
  is **structurally unreachable** on this dev split (dev_v1 is small, and it
  comes from the tuning set that chose the config — the handoff's own caveat).
- No change qualified; nothing was grown to dev_40/dev_65. All five changes
  are **rejected** and recorded with reasons in `reports/experiment_log.json`:
  zero lift, MRR@5 below baseline on every challenger (0.9219–0.9531 vs
  0.9688), and large token regressions for bigger chunks.

## Step 5 — final check (one-time final uses)

One baseline run on final_v3 (Revision 1 binding 5: this counts as one of the
one-time final uses); no kept candidates, so no candidate runs.
Report: `reports/retrieval_baseline/final_v3.json`, gold mode `chunk_exact`
(all gold ids present in the committed chunks_200 index).

- **final_v3 baseline: recall@5 0.9239 (85/92, Wilson 95% [0.8512, 0.9627]),
  MRR@5 0.8793**, n=92 answerable. Slices: single_hop 0.9706 (66/68),
  multi_hop 0.7917 (19/24). Tokens: 444 (top-3) / 737 (top-5).
  Abstain false-evidence: 0/28 (no absent term appears in any top-5).
  request_hosts: none.
- Read: the unbiased set sits ~7.6 points below dev (0.9239 vs 1.0) with
  multi-hop retrieval the weak slice — consistent with the previous tournament
  read; the incumbent config remains the champion.

## Step 1 — judge calibration

Blocked (owner Claude budget not set). No claims file drafted, no hosted
calls made. `data/judge_v2_claims.json` does not exist.

## Host verification

Every run recorded `request_hosts`: `[]` (pure local file/CPU loads) or
`['127.0.0.1']` (the Ollama embedding arm). No other host was contacted; no
hosted model call was made. The script raises STOP on any non-local host.

## Files

Committed on `phase0-infra-2026-11-22` (after gates):
- `1663dd3` — step 2: `scripts/measure_retrieval.py`,
  `configs/sweeps/*.yaml` (baseline + 5 sweep arms),
  `reports/retrieval_baseline/dev_v1.json`.
- step 6 commit — script robustness fixes, `reports/retrieval_baseline/final_v3.json`,
  this close-out.

Written but NOT committed (gitignored per Revision 1 binding 2; committing
them is an owner decision — narrow `.gitignore` exceptions or an explicit
list): `reports/experiment_log.json` (all run rows + step-4 decisions),
`reports/retrieval_sweeps/*.json` (five arm reports).
Sweep indexes live under `data/index/sweeps/` inside the gitignored
`data/index/`.

Uncommitted provenance (Revision 1 binding 3): the 27
`reports/final_v3_drafts/redraft_*` files supporting `golden_final_v3` remain
untracked; the owner decides whether they go in a separate commit.

## Owner decisions needed next

1. Claude budget for step 1 (Sonnet labels + owner sample of 30).
2. Whether to commit the ignored outputs (`experiment_log.json`,
   `retrieval_sweeps/`) via a `.gitignore` exception.
3. Whether the 27 `redraft_*` provenance files get their own commit.
4. Coverage accounting: adopt the literal-gate aggregate (79.59%) or the
   stricter `--cov=src` measure (77.82%) as the tracked project number.
5. Push/merge of `phase0-infra-2026-11-22` (not done; owner decision).
