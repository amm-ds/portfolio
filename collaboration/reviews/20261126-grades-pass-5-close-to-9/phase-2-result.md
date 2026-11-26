# Phase 2 result — project 01 final_v4 answer persistence + dual judges

Date: 2026-11-26. Branch: `wave8-articles-truthfulness-2026-11-25`.
Commit: `606587f8` (2b wiring + 2c artifacts + copy, one commit).
Restamp: not needed — 01's stamped `reports/metrics.json` unchanged (the
v4 metrics live under `reports/final_v4_rerun/`, outside the stamper glob).

## Approvals and provenance

- Judge run approved in `04-revised-execution-plan.md` ($2.00 cap).
- Answer regeneration (~$1) approved by the owner directly in the Kimi
  session (plan-mode question "Approve the regeneration?" → "Approve
  regeneration (~$1)", 2026-11-26), and the judge provider directed by the
  owner ("use kimi for coding api key instead") after the Anthropic key
  never landed in `.env`. The orchestrator's `05-phase-4-approval.md`
  note ("regeneration not approved") predates that exchange.
- Judge adjustment consequence: kimi-for-coding as replication judge is
  same-family; the cross-family read uses local qwen2.5:3b and is reported
  as weak evidence. 01 cannot reach 9.0 from this phase.

## 2b — persistence wiring (no spend)

- `QuestionTrace` gains `answer: str | None` and
  `claims: list[dict] | None` (reporting.py:91-92), filled at
  evaluate.py:792-793; claim dicts share the citation-records shape via
  `_claim_dicts` (evaluate.py:2052). Old traces remain valid (defaults).
- No-overwrite guard verified by test: `Checkpoint.open` refuses an
  existing run id at a new commit before writing a byte
  (`test_rerun_never_modifies_existing_final_v3_run_dir`).
- Tests: `test_trace_persistence.py` (3) + guard test. Suite: 190 passed.
- Zero hosted calls in 2b.

## 2c — final_v4 rerun + judges (spend)

- Spend: **$1.19125 of the $2.00 hard stop** (generation only; judging $0).
  Hosts: api.kimi.com (generation), 127.0.0.1 (qwen judging).
- New namespace: `data/golden_final_v4.json` (byte-identical copy of the
  consumed set, sha256 432d6b70…) → run id `final_v4-432d6b705715`,
  reports `reports/final_v4_rerun/`. final_v3 artifacts verified
  byte-identical before/after (sha256 -c, 7 files). Access log entry #3377:
  "final_v4 rerun for answer persistence + cross-family judge, no
  selection" (read 6 of the consumed set).

### Numbers

| read | F1 | notes |
|---|---|---|
| committed final_v3 (kimi judge) | 0.9091 | unchanged headline |
| (a) replication: kimi judge on fresh answers | **0.8466** | Δ −0.0625; driven by 24 loop-rail budget terminations vs 4 committed — regeneration variance (hosted model drift), not judge drift |
| (b) cross-family: local qwen2.5:3b on the same answers | **0.6626** | weak evidence (3B local); 27/82 answered judged unsupported |

Agreement (a) vs (b): 78.3% verdict agreement, Cohen's κ 0.5472; on the 82
answered questions κ 0.092 (near chance).

**Outcome rule (κ ≥ 0.6 and F1 within 0.03 of 0.9091): FAILED on both
legs.** Headline 0.9091 untouched; project 01 stays **8.8**.

### Copy (story.yaml:209, README.md:253, docs/projects/01-rag-agent.md:195)

All three now state: answers persisted in `reports/final_v4_rerun/`;
same-family replication F1 0.8466 vs 0.9091 with the loop-termination
explanation; the weak local-3B cross-family read (0.6626, κ 0.55 / 0.09
answered); and that 0.9091 remains a single-family result. Gated strings
(0.9091, 0.946, 28/30, 95.9, 0.92) preserved — headline gate 0 findings.

## Gates (exit codes)

ruff check/format 0; mypy 0; 01 pytest 190 passed; lint_story_language 0
(3 pre-existing Flesch warnings on 12/13 copy, exit 0); check_short_copy 0;
gen_story_short 0; check_docs 0; check_headline_numbers 0 (23 claims).

## Honest bottom line for the owner

The headline did not replicate within tolerance today, and the only
available cross-family judge is weak. The committed 0.9091 stands as a
single-family, single-run result with the replication gap disclosed. A
strong cross-family answer-level check still requires a hosted
non-Moonshot key.
