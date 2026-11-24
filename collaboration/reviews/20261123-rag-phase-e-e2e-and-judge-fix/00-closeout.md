# Close-out: Phase E — Pipeline Bug Fixes, dev_v1 E2E Gate, and final_v3 120-Question Evaluation (COMPLETE)

Date: 2026-11-23
Executor: Kimi Code
Handoffs:
- `collaboration/designs/20261123-rag-phase-e-e2e-and-judge-fix/03-implementation-handoff.md` (Steps 1–4 + **Revision 1**)
- Review: `collaboration/reviews/20261123-rag-phase-e-e2e-and-judge-fix/01-review-response.md`
Status: **COMPLETE**. Branch `phase0-infra-2026-11-22`. No commits, no pushes,
no merges; project 02 untouched. Hosted calls only to the named host
`api.kimi.com` (plus one disclosed embedding-library status ping, below).

## Step 1 — Pipeline bug fixes (local, $0)

1. `evaluate.py`: `_judge_context(evidence, cited, retriever)` — full
   `chunk.text` (dedup by chunk_id, excerpt fallback) for the rubric judge;
   `retrieved_relevant = retrieved_relevant or cited_relevant`.
2. `verify.py`: `check_claim_spans` tokenizes spans with `[a-z0-9]+` for the
   entity co-occurrence, month/temporal, and negation-union checks
   (`"September,"` no longer false-rejects); the number-presence check stays
   substring so decimals (`"1.2"`) are unaffected.
3. `agent.py` Rule 5: bounded searches on absent topics (2–3, then an honest
   empty refusal).

## Revision 1 — deterministic rails + multi-hop guard

1. **Soft tool ceiling** (`agent.py`): at `requests >= max(3, limit-3)` or
   `tool_calls >= max(4, limit-4)`, `search_documents` returns `[]` and
   `read_excerpt` returns the "TOOL BUDGET REACHED" notice — the row finishes
   instead of crashing with `UsageLimitExceeded`. Unit-tested via a
   FunctionModel observing both blocked paths.
2. **Multi-hop synthesis** (`agent.py` Rule 10 + `verify.py:559`): Rule 10
   instructs per-leg answers over separate articles with citations,
   `confidence >= 0.7`, and no refusal phrases inside substantive answers;
   verification is only skipped when `not result.claims or confidence < 0.3`.
3. **`--retry-failed`** (`run_e2e_eval.py`): prunes the checkpoint to
   `verdict == "correct"` rows; `wrong_abstention` no longer counts
   `budget-terminated` / `format-failure` rows.

## Step 2 — dev_v1 E2E gate (kimi-for-coding)

First pass: f1 0.9032 but 1 `budget-terminated` (gate fail → stopped, reported).
After Revision 1, `--retry-failed` re-ran the 3 failed rows for $0.0473
(17 rows reused at $0):

**dev_v1 FINAL: TP 16 / TN 4 / FP 0 / FN 0 — precision 1.0000, recall 1.0000,
f1 1.0000, overall_accuracy 1.0000 (Wilson 95% [0.8389, 1.0000]); every error
count 0 (unsupported_claim 0, false_abstention 0, wrong_abstention 0,
budget_terminated 0, format_failure 0, uncited_relevant 0).**
Gate `f1 >= 0.85 and budget_terminated == 0`: **PASS**.

## Step 3 — final_v3 120-question checkpointed pass (one-time)

CLI `evaluate --heldout --heldout-file data/golden_final_v3.json
--reports-dir reports/final_v3_e2e`, `LLM_COST_LIMIT_USD=2.40`,
`HF_HUB_OFFLINE=1`. Completed all 120 questions in one process;
**metered spend $1.4579** of the $2.40 cap. Checkpoint
`reports/runs/final_v3-432d6b705715/` (120 rows).

**Merge-bug found and fixed post-run** (no model rerun, $0): on a fresh
checkpointed run, `Checkpoint.merged_traces` concatenated recorder rows (already
in the checkpoint) with the run's traces → 240 rows for 120 questions and
doubled aggregates in `question_traces_heldout.json` / `metrics.json`.
Fixed in `runner.py` (dedupe by question hash, fresh rows win) with a
regression test (`test_merged_traces_dedupes_fresh_run_rows`); the artifacts
were regenerated from the clean 120-row checkpoint.

**final_v3 FINAL metrics** (`reports/final_v3_e2e/f1_summary.json` +
`metrics.json detail.final_v3`):

- TP 80, FP 4, TN 24, FN 12 — **precision 0.9524, recall 0.8696,
  f1 0.9091**, overall_accuracy 0.8667 (Wilson 95% [0.7944, 0.9162]).
- Faithfulness **0.8717** (95% CI [0.7983, 0.9155], answerable n=92);
  answer_relevance 0.8804; context_recall 0.9891.
- Taxonomy: correct 104, empty-answer 10, budget-terminated 4,
  unsupported-claim 1, retrieval-miss 1, format-failure 0.
  correct_share 0.8667 (CI [0.8167, 0.9083]).
- Slices: single_hop 60/68 correct (1 retrieval-miss, 7 empty-answer);
  multi_hop 20/24 (1 unsupported-claim, 3 empty-answer);
  unanswerable 24/28 correct abstentions (4 budget-terminated).
- Verify loop: 116 answers verified, claim retention 0.9578, repair rate
  0.0904, 0 verifier failures, 0 mechanical false rejections.
- request_hosts: `api.kimi.com` only.

## Spend (cloud-equivalent estimates, kimi-k2.8 reference card)

| Phase | Spend |
|---|---|
| Step 1 (judge v2a + v3 labelling) | $0.1994 |
| dev_v1 attempt 1 | $0.3346 |
| dev_v1 `--retry-failed` | $0.0473 |
| final_v3 (120 questions) | $1.4579 |
| **Total of the $3.00 cap** | **$2.0392** |

## Disclosures

- The first dev_v1 attempt made a `huggingface.co` embedding-library status
  ping (no model call; the script now sets `HF_HUB_OFFLINE=1`). All model
  calls went to `api.kimi.com`.
- `run_e2e_eval.py` does not persist cumulative spend into the dev_v1
  checkpoint manifest; spend is reconstructed from the meter logs above.

## Step 4 — Gates (verbatim)

- `uv run pytest --cov` → exit 0, **`185 passed, 2 warnings in 7.44s`**
- `uv run ruff check .` → **`All checks passed!`**
- `uv run ruff format --check .` → **`71 files already formatted`**
- `uv run mypy .` → **`Success: no issues found in 38 source files`**
- `uv run python scripts/check_docs.py` (repo root) → **`check-docs: OK`**

## Files (uncommitted; Claude reviews, validates, commits)

- src: `evaluate.py` (`_judge_context` + accounting), `verify.py` (span tokens
  + abstention guard), `agent.py` (Rule 5/10, soft ceiling), `runner.py`
  (merge dedupe).
- scripts: `run_e2e_eval.py` (new; `--split dev_v1`, `--summarize`,
  `--retry-failed`).
- tests: `test_verify.py`, `test_heldout.py`, `test_agent.py`,
  `test_runner.py` (+4 tests total across the phase).
- reports: `reports/e2e_dev_v1/`, `reports/final_v3_e2e/`,
  `reports/runs/dev_v1-ed9013955903/`, `reports/runs/final_v3-432d6b705715/`,
  `reports/experiment_log.json`.

## Owner decisions next

1. Commit Phase E (Revision 1) — Claude's pass.
2. The 4 final_v3 `budget-terminated` rows (all unanswerable) are the soft
   ceiling converting would-be runaway rows into typed failures; whether to
   retry them with `--retry-failed` or accept is the owner's call (a retry is
   ~$0.05–0.10).
3. Optional: persist cumulative spend into checkpoint manifests for dev runs.
