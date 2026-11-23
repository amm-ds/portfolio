# Final review response: Phase E — Pipeline Bug Fixes, `dev_v1` Gate, and `final_v3` 120-Question Evaluation

Date: 2026-11-23
Reviewer: Claude Code
Implementation: working tree on `phase0-infra-2026-11-22`, reported in `collaboration/reviews/20261123-rag-phase-e-e2e-and-judge-fix/00-closeout.md`
Status: approved

## Verdict

Phase E (Revision 1 + Step 3 `final_v3` + `runner.py` checkpoint dedupe fix) is **approved and complete**, achieving the RAG roadmap's north-star target (**0.85–0.90 per-question F1**):

- **`dev_v1` (20 questions):** `TP 16 / TN 4 / FP 0 / FN 0` — **`F1 = 1.0000`**, `precision = 1.0000`, `recall = 1.0000`, `overall_accuracy = 1.0000` (Wilson 95% `[0.8389, 1.0000]`), zero errors of any kind.
- **`final_v3` (120 questions, one-time pass):** `TP 80 / FP 4 / TN 24 / FN 12` — **`F1 = 0.9091`**, `precision = 0.9524`, `recall = 0.8696`, `overall_accuracy = 0.8667` (Wilson 95% `[0.7944, 0.9162]`).
  - **Faithfulness:** `0.8717` (95% CI `[0.7983, 0.9155]`, n=92 answerable); `answer_relevance = 0.8804`; `context_recall = 0.9891`.
  - **Unsupported-claim rate:** **`1 / 120 (0.83%)`** (down from 25–30% before `_judge_context` + `S3` + `verify.py` fixes).
  - **Slices:** `single_hop` 60/68 correct, `multi_hop` 20/24 correct, `unanswerable` 24/28 correct abstentions.
  - **Verify loop:** 116 answers verified, claim retention `0.9578`, repair rate `0.0904`, `0` verifier failures, `0` mechanical false rejections.
- **`Checkpoint.merged_traces` fix (`runner.py`):** Cleanly caught and fixed the 240-vs-120 row duplication bug on fresh checkpointed runs, backed by `test_merged_traces_dedupes_fresh_run_rows`, and regenerated `reports/final_v3_e2e/` from the clean 120-row checkpoint.
- **Total Spend:** `$2.0392` cumulative of the `$3.00` cap (`$0.1994` Step 1 + `$0.3819` `dev_v1` + `$1.4579` `final_v3`; `$0.96` remaining).
- **Gates:** `185 passed`, `ruff check` & `ruff format --check` clean, `mypy` (38 files) clean, `check_docs.py` OK.

## Disposition of queued decision

- **4 `budget-terminated` rows on `final_v3` (all unanswerable):** Accept as-is (`final_v3` was a one-time pass; the 4 rows are the soft tool ceiling converting runaway loops into typed failures, and reporting them transparently alongside `F1 = 0.9091` preserves strict `final_v3` evaluation hygiene).

## Recommended next step

Commit Phase E, then execute **Wave 1C (RAG 01 docs, `story.yaml`, and `cardCopy.ts` finalization)** and **Wave 2 (UI light-mode green alignment, Contact disclaimer simplification, and About/Home/Services/Projects pass)**.
