# Verifier cascade — frozen DEV-only calibration rule

Date: 2026-11-20
Handoff: `collaboration/designs/20261120-verifier-cascade-dev/03-implementation-handoff.md`
(approved: offline DEV-only calibration, $0 hosted)
Status: **frozen before any cascade scoring.** Items 1–8 below do not change
after scoring starts. Rule file sha256 recorded in the calibration report.

## 1. Score source

- File: `reports/verifier_challenger/predictions.jsonl` — committed per-claim
  MiniCheck-FT5 score (`score` field) from the Phase 1 challenger run.
- sha256: `d3336e8e5e7265fffe6cf06b50d46e984b9d3c97ec53be922b75c17211a54976`

## 2. Split source

- File: `data/calibration/verifier_split.json` — DEV rows only (96 claims:
  48 supported, 48 unsupported). TEST rows are not touched for selection.
- sha256: `5cc2c8b661df7a883d93eaab36bfd771bf9e51ab1d33a31ce4fc627879fb01ea`
- Calibration claims source (labels): `data/calibration/claims.jsonl`
  sha256 `675ac742796a273f47c743148b9e33829e7de26ff4e8d68e170e980e885859bc`

## 3. Grid

- Function: `rag_agent.verifier_cascade.generate_grid` — the full pair grid
  over the **sorted unique DEV MiniCheck scores**: every `(t_lo, t_hi)` with
  `t_lo < t_hi`. No exclusions, no pruning, no grid change after results.

## 4. Folds

- Stratified 5-fold over DEV by label, seed 42
  (`rag_agent.verifier_cascade.assign_folds`, per-label shuffle seeded
  `"42:<label>"`, round-robin by position).
- Assignment committed at `reports/verifier_cascade_dev/folds.json`,
  sha256 `76c76fc4a5a12fe4723c45604eabd117f5e9d4d5423ca9f6736f7287ab9e5d47`,
  written **before** any cascade scoring.

## 5. Qualifying rule

A band qualifies iff, on cross-validated DEV (out-of-fold aggregation over
all 5 folds):

- FA over unsupported claims `<= 0.10`, AND
- FR over supported claims `<= 0.10`.

## 6. Selection among qualifying bands

Lowest deferred share; ties broken by lower FA, then lower `t_hi`, then
lower `t_lo` (deterministic total order). Selection input is DEV rows only —
the selector asserts this (`select_band` raises on any non-DEV id).

## 7. Deferred claims (middle band)

- Deferred claims (`t_lo < s < t_hi`) are scored by the local
  `qwen2.5:3b` via Ollama, run **once on all 194 claims** and cached at
  `local_verdicts.jsonl`.
- Prompt and parsing: exactly `src/rag_agent/judge.py`'s
  `LLMRubricJudge` recipe — `RUBRIC_SYSTEM_PROMPT`, user prompt
  `Question: …\n\nContext: …\n\nAnswer: …` with (question, evidence, claim),
  structured `JudgeVerdict{score 0–1, reason}` via pydantic-ai
  (`NativeOutput`, the documented local workaround), retries `{"output": 2}`.
- Binary cut (fixed here, before scoring): `score >= 0.5` accepts; below
  rejects (rubric midpoint: 1.0 = fully supported, ~0 = contradicts).
- Unparseable verdicts (exception after retries) **count as unsupported**
  and are reported as a count.
- The model is forced-local by construction
  (`Settings(llm_base_url=None, llm_api_key=None)`, `OLLAMA_MODEL=qwen2.5:3b`);
  zero hosted calls.

## 8. No re-scan

No re-scan after results. Items 3–7 do not change after scoring. TEST is read
once, after selection, only if a band qualifies, and only as a descriptive
reading labeled "second use of TEST; not used for selection". If no band
qualifies, TEST is not read at all.
