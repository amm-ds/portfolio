# Design brief: Phase E — End-to-End Evaluation Bug Fixes, Dev Verification, and `final_v3` Pass (project 01)

Date: 2026-11-23
Designer: Claude Code
Owner: session owner (portfolio repo)
Status: approved for execution (Phases A–D complete and validated; 30-claim judge sample audited at 30/30 = 100.0% agreement)

## Context & Problem

Phases A–D (`collaboration/reviews/20261123-rag-sota-retrieval-and-pipeline/00-closeout.md` and `01-review-response.md`) are complete:

1. **Judge Calibration V2 Validated:** 147 claims (`data/judge_v2_claims.json`: 75 supported + 72 one-detail same-subject negatives) were labelled by `kimi-for-coding` ($0.0948 spend, $0.1994 cumulative of the $3.00 cap, leaving **$2.80**). The 30-item blind sample (`owner_sample.json`, seed 44) achieved **30/30 (100.0%, Wilson 95% [0.8865, 1.0000])** agreement against `chunk_text`, clearing the 85% threshold.
2. **SOTA Retrieval Promoted (`S3` — `structure_hybrid_diverse`):** Lifted `final_v3` `recall@5` from `0.9239 -> 0.9457`, `MRR@5` from `0.8793 -> 0.8877`, `single_hop` from `0.9706 -> 0.9853` (67/68), `multi_hop` from `0.7917 -> 0.8333`, and article-level `recall@10` to `92/92 = 1.0000` (`validate_heldout_set` passes on `data/golden_final_v3.json` with 0 problems).

Before spending hosted budget on the 120-question `final_v3` end-to-end pass, a forensic audit of the 53 non-correct traces in the prior 120-question run (`5c7f41b`: 67 correct, 31 `unsupported-claim`, 17 `budget-terminated`, 5 `empty-answer`) uncovered **three deterministic bugs in `src/rag_agent/`** that caused nearly all 53 failures:

1. **Bug 1 (`src/rag_agent/evaluate.py` line 740 — 240-Char `c.excerpt` Judge Context Truncation):**
   In `5c7f41b`, **31 out of 31 (`100%`)** of the answerable `unsupported-claim` rows had `cited_relevant == True` and `n_surviving_claims > 0` (meaning `verify_result` had already verified every surviving claim and its verbatim spans against the full 1,200+ char `chunk.text`). They were misclassified as `unsupported-claim` ONLY because line 740 of `evaluate.py` passed `context = "\n".join(c.excerpt for c in evidence)` (the 240-character preview of the static initial search, truncating off ~80% of every 200-word chunk and omitting `output.citations`) to `selected.judge` (`LLMRubricJudge`).
2. **Bug 2 (`src/rag_agent/verify.py` lines 262, 266, 271 — `s.split()` Punctuation Attachment in `check_claim_spans`):**
   `check_claim_spans` tokenizes claims via `_WORD_RE = re.compile(r"[a-z0-9]+")` (punctuation stripped), but checked `span_texts` via `s.split()` (leaving commas and periods attached, e.g. `"september,"`, `"july."`). A verbatim span containing `"in September, 2006,"` fails `any("september" in s.split() for s in span_texts)` with `date/temporal token 'september' not in any span`.
3. **Bug 3 (`src/rag_agent/agent.py` `SYSTEM_PROMPT` Rule 5 — Unbounded Search Loops on Unanswerable Questions):**
   15 of the 17 `budget-terminated` rows in `5c7f41b` were unanswerable (`abstain`) questions where the agent kept reformulating `search_documents` queries until hitting `tool_calls_limit`. Bounding search attempts on absent topics in Rule 5 (2–3 searches max when the queried subject is absent from returned passages) eliminates runaway tool loops on unanswerable rows.

## Goal

1. Fix the 3 pipeline bugs in `evaluate.py`, `verify.py`, and `agent.py` with unit tests (`0` hosted spend).
2. Run a 20-question end-to-end verification pass on `dev_v1` (`kimi-for-coding`, est. ~$0.15–$0.25) to confirm per-question F1 $\ge 0.85$ and 0 budget terminations before touching `final_v3`.
3. Execute the single checkpointed 120-question end-to-end pass on `data/golden_final_v3.json` (`--reports-dir reports/final_v3_e2e`) within the remaining $2.80 spend cap ($2.50 soft stop, $2.80 hard stop; cumulative Step 1 + Phase E $\le \$3.00$) and report per-question F1, precision, recall, accuracy, Wilson 95% CIs, and error breakdown.
