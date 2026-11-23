# Close-out (STOPPED at Step 2 gate): Phase E — Pipeline Bug Fixes & dev_v1 E2E Gate

Date: 2026-11-23
Executor: Kimi Code
Handoff: `collaboration/designs/20261123-rag-phase-e-e2e-and-judge-fix/03-implementation-handoff.md`
Status: **STOPPED at the Step 2 gate** — `budget_terminated == 1`. Step 3
(`final_v3`) was NOT touched. No commits, no pushes; project 02 untouched.

## Step 1 — Pipeline bug fixes (complete, local, $0)

1. `evaluate.py`: `_judge_context(evidence, cited, retriever)` — full
   `chunk.text` for the rubric judge (dedup by chunk_id, excerpt fallback for
   mock retrievers); `retrieved_relevant = retrieved_relevant or cited_relevant`.
2. `verify.py`: `check_claim_spans` uses `span_token_sets`
   (`re.findall(r"[a-z0-9]+", s)`) for the entity co-occurrence, month/temporal,
   and negation-union checks — `"September,"` / `"2006,"` no longer false-reject.
   (The number-presence check stays substring per the handoff's line scope, so
   decimals like `"1.2"` are unaffected.)
3. `agent.py`: SYSTEM_PROMPT Rule 5 now bounds search attempts on absent topics
   (2–3 searches, then an honest empty refusal).

Unit tests: `tests/test_verify.py::test_span_check_month_with_trailing_comma_passes`,
`tests/test_heldout.py::test_judge_context_uses_full_chunk_text`. Gates:
`183 passed`, ruff clean, format clean, mypy 37 files clean.

## Step 2 — dev_v1 E2E gate (kimi-for-coding, $0.60 process cap)

Run: 20 questions, checkpointed `reports/runs/dev_v1-ed9013955903/`; artifacts
`reports/e2e_dev_v1/{metrics.json, question_traces.json, f1_summary.json}`.

**Result: precision 0.9333, recall 0.8750, f1 0.9032 (>= 0.85 PASS),
overall_accuracy 0.85 (Wilson 95% [0.6396, 0.9476]) — but
budget_terminated == 1 (GATE FAIL → STOP).**

Error counts: unsupported_claim 0, false_abstention 2 (empty-answer),
wrong_abstention 1, **budget_terminated 1**, format_failure 0,
uncited_relevant 1.

Failure traces:

1. `budget-terminated` — "What is the capital of Australia?" (unanswerable):
   `UsageLimitExceeded: the next request would exceed the request_limit of 12`.
   The agent kept calling tools despite Rule 5; the deterministic rail caught
   it and the taxonomy classified it correctly. Prompt-level bounds are
   probabilistic — this row class is what Rule 5 targets, but one row in 20
   still looped.
2. `empty-answer` — "How does climate change adaptation relate to greenhouse
   gas inventories in national climate policy?" (multi_hop): retrieved_relevant,
   verify support floor left 0 surviving claims → abstention.
3. `empty-answer` — "Compare space-based solar power with wind power in Europe
   as large-scale renewable strategies." (multi_hop): cited_relevant, 0
   surviving claims → abstention.
4. `wrong_abstention` (the FP) — one unanswerable row answered anyway.

Spend: **$0.335** of the $0.60 process cap (run completed without hitting the
cap). Cumulative Step 1 $0.1994 + dev_v1 $0.335 = **$0.5344 of $3.00**.

## Disclosures

- Attempt 1 of the dev_v1 run made a `huggingface.co` embedding-library status
  ping (no model call; the handoff command does not set `HF_HUB_OFFLINE`).
  The script now sets `HF_HUB_OFFLINE=1` (the run itself is unaffected — all
  models load from the local cache). The historical ping is recorded in the
  checkpoint row hosts and disclosed here.
- A checkpoint-resume bug in `run_e2e_eval.py` (empty fresh traces on full
  resume) was fixed by merging checkpoint rows; the host guard was scoped to
  the current process so historical hosts cannot re-trigger a stop.

## What the owner decides next

- The gate is one deterministic rail termination away from passing. Options:
  (a) accept the single `budget-terminated` row on an unanswerable tuning
  question as a rail doing its job and proceed to Step 3 with the same rails;
  (b) rerun dev_v1 after further prompt/tool hardening (e.g. a deterministic
  2–3 search cap in the tool wrapper) and re-gate. Per the handoff as written,
  Step 3 was not started.
