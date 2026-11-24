# Review: portfolio roadmap and story roadmaps

Date: 2026-11-24
Reviewer: Claude Code (read-only; `story.yaml` files and the tracker are
**not** edited; no hosted LLM or paid API calls)
Repo state: `main` @ `2a7d9b7a`
Sources reviewed:

- `collaboration/ITERATION_TRACKER.md` (55 lines: north star, iteration ledger,
  release waves 1–7)
- `collaboration/designs/20261123-portfolio-release-roadmap/01-master-plan.md`
  (the 5-wave release roadmap)
- `roadmap:` blocks in all 13 `projects/*/story.yaml`, mainly
  `projects/01-rag-agent/story.yaml:523-538`
- Validation baseline: `collaboration/reviews/20261124-rag-article-review/00-review.md`
  (RAG 01 claims checked against committed reports)
- Contract: `docs/engineering/repo-conventions.md` (Roadmaps: 3–4 `shipped`
  plus 1–2 `next`/`blocked`, at most 5; title 3–6 words, verb-first, no
  metric; detail ≤ 90 chars with one number or one decision; only `shipped`
  cards render on the web)

Legend: **[V]** verified in this session; **[I]** inference.

---

## 0. Summary

1. **The tracker is a changelog, not a roadmap.** It is titled "Project 01
   (RAG Agent) — Iteration & Plan Tracker", still names the old branch
   `phase0-infra-2026-11-22` and "Last updated: 2026-11-23" (`:3-4`), and
   mixes per-iteration metrics, commit ids and wave scopes. A reader cannot
   see the major milestones or which ones rest on what evidence.
2. **Three tracker statements conflict with committed results** (section 3):
   the "blind" owner sample, the stale faithfulness interval, and the claim
   that project 14 will be evaluated on "147 owner-labelled judge_v2 claims".
3. **The RAG 01 story roadmap has two conflicts and two wording problems**
   (section 4): a "Validated the judge" card while the owner label is
   pending, and an empty-answer count that disagrees with the false-abstention
   rate in the same file.
4. **Other projects:** no roadmap number contradicts a committed file in the
   spot check, but four numbers do not appear verbatim in any committed
   report (section 5).
5. **Proposal:** a 6-milestone portfolio roadmap with neutral labels, a
   status, and one evidence path each (section 2), and a 5-card template for
   project roadmaps (section 4.3).

---

## 1. Problems with the current roadmap texts

| Where | Problem | Example |
|---|---|---|
| Tracker title and header (`:1-6`) | Scoped to RAG 01 but now tracks the whole portfolio; stale branch and date | `Branch: phase0-infra-2026-11-22` |
| Tracker §1 north star (`:12`) | Target "zero errors" is not met and the tracker does not say so | final pass: 1 unsupported answer, 10 false abstentions, 4 budget stops (`reports/final_v3_e2e/f1_summary.json` → `errors`) [V] |
| Tracker §2 ledger | Too detailed for a roadmap (file:line, test counts, commit ids); "Committing this turn" left in three rows (`:24-31`) | `Committing this turn` |
| Tracker §3 waves | Status words carry weight they cannot hold: "DONE & VALIDATED", "pending optional human owner 30-sample sign-off" | The owner label is a truth-in-copy dependency, not optional (`owner_sample_validated.json:288`) [V] |
| Master plan (`01-master-plan.md`) | Written as an active plan ("[ACTIVE NOW]", "Current committed…"); still says "judge_v2 (30/30 = 100% owner-validated)" (Wave 1C) | Superseded wording; no status block marks it historical |
| Language across both | Time-relative words: "current", "now", "active", "latest", "finalized" | The owner asked for neutral language |

---

## 2. Proposed portfolio roadmap (replaces tracker §3 as the reader-facing view)

Six milestones, each with a neutral one-line label, a status, and the evidence
it rests on. Status vocabulary: **done**, **done with open items**,
**approved**, **planned**. The iteration ledger moves to an appendix or to
`DESIGN.md`/close-outs, where history belongs (`repo-conventions.md`, Truth in
copy: "development history belongs in DESIGN.md changelogs").

| # | Milestone | Status | Evidence | Open items |
|---|---|---|---|---|
| M1 | Reproducible evidence base: pinned data, story contract, copy gates | done | `registry/`, `docs/data-registry/`, `scripts/check_headline_numbers.py` (12 claims checked, 0 findings [V]), `scripts/lint_story_language.py` (0 errors, 1 warning [V]) | 01 Evaluation over the word budget |
| M2 | Thirteen published case studies | done | `projects/01…13/story.yaml`, `reports/` per project | Article restructure pilot (see RAG article review) |
| M3 | Grounded question answering: final evaluation | done with open items | `projects/01-rag-agent/reports/final_v3_e2e/{f1_summary,metrics}.json` (F1 0.9091, 104/120 correct) [V]; `retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json` (recall@5 0.9457) [V] | owner hand-label of the 30-item sample; same model generates, verifies and judges; the final set is consumed (new sealed set needed for the next claim); $2.0392 spend untraceable |
| M4 | Site, apps and interactive demos | done with open items | `apps/showcase-web`, `apps/agent-chat`, `apps/document-intelligence`; Wave 6 close-out `collaboration/reviews/20261124-wave6/00-closeout.md` | UI layout regression (`collaboration/designs/20261124-ui-layout-regression/`) |
| M5 | Deployment readiness and public-repo hygiene | done | merge `c09d9166`; `deploy/DEPLOYMENT-REPORT.md` | none recorded |
| M6 | Next experiments: claim-verifier fine-tuning (14) and pricing under uncertainty (15) | approved | `collaboration/designs/20261124-next-experiments/` | not started; project 14's evaluation set wording must change (section 3, T3) |

Rules for this view: one line per milestone; no metric in the label; at most
one headline number in the evidence column; status changes only when its
evidence file changes.

---

## 3. Tracker and master-plan statements that conflict with committed results

| # | Statement (file:line) | Committed evidence | Conflict | Suggested neutral wording |
|---|---|---|---|---|
| T1 | "≥ 85% agreement against the 30-claim **blind** sample … Achieved: 30/30" (`ITERATION_TRACKER.md:13`); "30-item blind sample audit" (`:24`) | `owner_sample_validated.json`: `validated_by: "claude-role-audit (pending human owner hand-label confirmation)"`; each item stores `kimi_label` next to `validated_label` [V] | Not blind, not owner | "Reviewer-agent audit 30/30 (Wilson [0.887, 1.0]); owner hand-label pending" |
| T2 | final_v3 faithfulness "`[0.7983, 0.9155]`" (`ITERATION_TRACKER.md:29`) | `final_v3_e2e/metrics.json` → `detail.final_v3.faithfulness.ci95 = [0.8092, 0.9304]` [V] | Stale interval | Use `[0.8092, 0.9304]` |
| T3 | Project 14 evaluated on "147 **owner-labelled** `judge_v2` claims" (`ITERATION_TRACKER.md:46`) | `judge_v2` labels come from `kimi-for-coding` (`label_judge_calibration_v2.py`, tracker `:24`); only 30 were audited, by an agent [V] | False attribution; would carry into a new public project | "147 model-labelled judge_v2 claims (30 audited)" |
| T4 | Wave 1 "DONE (pending **optional** human owner 30-sample sign-off)" (`:40`) | Public copy depends on that label (RAG article review C10) | "Optional" understates it | "done with open items: owner hand-label" |
| T5 | North star "zero errors" (`:12`) and Wave 1 "DONE" | `f1_summary.json` → `errors`: 1 unsupported, 10 false abstentions, 4 budget-terminated [V] | Target not met; status silent | "F1 target met (0.909); zero-error target not met" |
| T6 | Iter 3 "`$2.0392` cumulative of `$3.00` cap" (`:29`) | No committed report contains 2.0392; final pass meter `$1.457917` [V] | Untraceable | Commit a ledger or cite $1.46 for the final pass |
| T7 | Master plan Wave 1C "judge_v2 (30/30 = 100% owner-validated)" (`01-master-plan.md`, Wave 1, item 3) | as T1 | Superseded wording | Add a "Status: historical; see tracker" line at the top |

---

## 4. RAG 01 story roadmap (`projects/01-rag-agent/story.yaml:523-538`)

### 4.1 Entry-by-entry check

| Card | Status | Title / detail | Evidence | Verdict |
|---|---|---|---|---|
| R1 | shipped | "Pinned corpus and frozen contracts." / "593 articles; final_v3 (120 questions) and judge_v2 (147 claims) contracts." | 593 articles (data contract), final_v3 120 questions (`f1_summary.json` `n_questions`) [V] | No conflict. Internal ids (`final_v3`, `judge_v2`); trailing period on title; two numbers in detail (contract allows one) |
| R2 | shipped | "Promoted hybrid title-anchored retrieval." / "S3: structure chunks, dense+BM25 RRF, per-article cap; 0.946 recall@5." | `s3_structure_hybrid_diverse__final_v3.json` 0.94565 [V] | Traceable. Note: the E2E file reports a different recall@5 (0.7583 over 120 rows, `final_v3_e2e/metrics.json` → `retrieval`) [V]; the card should say "retrieval-only" or drop the number |
| R3 | shipped | "Validated the judge and final pass." / "Reviewer-agent audit 30/30 on the judge sample; owner hand-label pending." | `owner_sample_validated.json` (agent audit, not owner) [V] | **Conflict**: the title claims validation; the detail admits it is pending. Shipped status overstates |
| R4 | shipped | "Hardened the agent loop." / "Soft tool budget 12/16/200k, verify loop, checkpointed runs." | `config.py:201-203` (12, 16, 200_000) [V]; `reports/runs/final_v3-432d6b705715/` [V] | Traceable. Three numbers in one detail |
| R5 | next | "Cut false abstentions and rail stops." / "final_v3 has 10/92 empty-answers and 4 unanswerable budget-terminated rows." | `f1_summary.json` false_abstention 10, budget_terminated 4 [V]; but `metrics.json` → `abstention.false_abstention_rate 0.1196` = 11/92 [V] | **Conflict in denominators**: 10/92 vs 11/92. The `next` card also names no gate (contract: "`next` names the gate") |

Missing from the roadmap: the open items that limit the headline (owner label,
self-judging, consumed final set). They belong in the `next`/`blocked` cards,
which are authored but not rendered.

### 4.2 Proposed RAG 01 roadmap (neutral, high level)

Five cards, contract-compliant (titles 3–6 words, verb-first, no metric;
details ≤ 90 chars, one number or one decision). Wording only; the owner
chooses.

| Status | Title | Detail | Evidence |
|---|---|---|---|
| shipped | Pin the corpus and test sets | 593 Wikipedia articles, checksum-pinned; test sets frozen before tuning. | data contract; `data/golden_final_v3.json` |
| shipped | Promote hybrid retrieval | Relevant article in the top 5 for 95% of answerable questions. | `retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json` |
| shipped | Bound and verify every answer | Claims below the 0.6 support floor are repaired, dropped, or refused. | `config.py:201-203`; `final_v3_e2e/metrics.json` → `verify` |
| shipped | Score the full pipeline once | 104 of 120 test questions answered or refused correctly. | `final_v3_e2e/f1_summary.json` |
| blocked | Confirm the judge independently | Owner decision: hand-label the 30-claim sample or fund a cross-judge run. | `owner_sample_validated.json:288` |

Optional second `next` card (not rendered): "Measure on a fresh test set" /
"Gate: a new sealed set before any further quality claim."

Compared with the Wave 6.5 draft
(`collaboration/designs/20261124-wave65-ui-and-rag-article-polish/01-design-and-handoff.md` §3):
that draft's card "Validate grounding and judge audit" / "Calibrate automated
claim verification against audited golden samples" still implies validation
the owner has not done, and it has no card for the scored end-to-end pass.
The table above replaces it.

### 4.3 Template for all project roadmaps

The Wave 3 arc (Data → Training → Evaluation → Production → Next,
`01-master-plan.md` Wave 3) fits most projects. Keep it, with three rules:

1. Imperative verb-first titles without trailing periods ("Pin the panel",
   not "Pinned the full M5 panel.").
2. The detail states the evidence in plain words; one number at most; no
   internal ids (`final_v3`, `wave-34`, `S3`, `origin 1877`).
3. The last card names the gate or the owner decision, never a result.

---

## 5. Other projects: roadmap entries to check

Spot check: every number in each roadmap detail was searched in the project's
committed `reports/` and README (`git grep -F`) [V]. Numbers that are not in a
committed report:

| Project | Card | Number | Found in | Verdict |
|---|---|---|---|---|
| 02 | next: "Find erratic gains beyond routing." | 0.8683 vs 0.7409 | 0.7409 in `reports_m5_full/erratic_challenger.json`; 0.8683 appears as `pooled` in `reports_m5/demo_payload.json:339` (a different report) [V] | Traceability unclear; also uses internal ids ("Wave-34", "origin 1") |
| 04 | shipped: "Kept the default under inconclusive tuning." | −0.0048 | only `story.yaml:487` [V]; 04 metrics are DVC-tracked (`repo-conventions.md`, exception for 11 and 12 only) | Not traceable in git |
| 07 | shipped: "Served validation winner, not test leader." / "Retrained per service…" | −4.1%, 337,080 | `DESIGN.md:243`, `MODEL_CARD.md:77`, `story.yaml` only; no committed `reports/` for 07 [V] | Not traceable to a report |
| 13 | shipped: "Passed both backends through load testing." | 4,320 | not verbatim in `reports/metrics.json` (holds `requests_per_concurrency 300`, `batch_requests_per_size 60`) [V] | Derived number; state the derivation or cite a stored total |

Style issues seen across projects (not conflicts): trailing periods on every
title; internal ids in 01, 02; "Current benchmark" (03 next card) and
"not stored today" (04 next card) use time-relative language; 12's `next`
card ("Drop the external TabPFN-2 challenger route") records a closed decision
as a next step.

---

## 6. Owner decisions

| # | Decision |
|---|---|
| R-1 | Adopt the 6-milestone portfolio view (section 2) as the reader-facing roadmap, and move the iteration ledger to an appendix? |
| R-2 | Which milestones to keep, merge, or rename (M1–M6)? |
| R-3 | Approve the RAG 01 five-card roadmap in 4.2 (especially R3 → a `blocked` card for the judge)? |
| R-4 | Fix tracker statements T1–T7 now (a Claude doc edit, no code), or with the next wave? |
| R-5 | Roll the 4.3 template to projects 02–13 after the 01 pilot? |
