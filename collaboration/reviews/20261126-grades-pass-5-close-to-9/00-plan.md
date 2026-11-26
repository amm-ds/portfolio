# Grade pass 5 — close the iteration round to 9

Date: 2026-11-26. Branch: `wave8-articles-truthfulness-2026-11-25`. Owner approved: paid LLM-judge run if needed. Owner goal: close every project to 9 where the evidence allows, and say plainly where it does not.

Status going in: pass 4 phases A–D committed (`2beafb93`…`94345c4e`, `c53069eb` E10 harness and STOP record). Docs handoff items done, uncommitted (`02-kimi-docs-result.md`). E9 (02 refit) running. E12 scratch run is NOT valid (different imputation path from the E4 sensitivity arm; see Phase 3). Hosted spend so far $0.41 of the $5 cap.

## Where each project stands (pass-4 projections)

| Project | Now (est.) | Reaches 9 by | Blocker |
|---|---|---|---|
| 01 RAG | 8.3 | Phase 2 (final_v4 + cross-family judge) | Paid judge run |
| 02 Demand | 8.0 | Phase 1 (E9 refit landing) | E9 finish |
| 03 Anomaly | 8.3 | Copy/figure items already done; check | None known |
| 04 NLP | 8.0 | Paired cascade CI (E6 done) | Copy/figure check |
| 05 Churn | 8.3 | E1 done (20 splits); copy and titles | Titles |
| 06 Routing | 8.8 | Titles, 5-vs-8 count | Copy only |
| 07 Mobility | 8.5 | E2 CI done; coverage in metrics | Check committed |
| 08 Inference | 7.8–8.8 | **Not reachable on one host** | Second host (E11), no access |
| 09 Agentic | 8.3 | Short copy fixed (17/19); repeats done | Verify |
| 10 Uplift | 8.0 | Persistence (E3 done); CI in metrics; titles | Copy/figures |
| 11 DataFrame | 8.8 | Two titles | Titles |
| 12 Tabular | 8.0 | Option B (E12 v2 headline) | Owner choice + valid v2 run |
| 13 Serving | 8.5 | Re-derives from 12 option B; 9 needs it | Depends on 12 |
| 15 RL | 9.0 | Already 9.0 | Browser check of diagrams |

Honest ceiling: 08 stays at 8.8 on one host. The plan does not claim 9 for 08 without a second machine.

## Phases

### Phase 1 — Land E9 (02 refit)
- Wait for E9 to finish. Reproduction gate: 0.62105 within 1e-6.
- If it passes: restore the sample-series figure, refresh headline interval, commit, restamp 02 separately.
- If it fails: stop, report the failing gate, keep the disclosure copy. Do not publish a number that did not reproduce.
- Cost: CPU only (~9.4 h, already running).

### Phase 2 — Project 01 paid cross-family judge
- Approved: one hosted cross-family judge run, **cap $2.00** for this phase (proposed by me; within the $5 overall cap, $0.41 spent).
- Persist answer texts and claims in a new `final_v4` run. Do not overwrite `final_v3` outputs.
- Judge all answers with the hosted second-family model; report answer-level F1 for both judges, plus agreement and kappa.
- Stop rule: if the hosted judge's spend would exceed $2.00, stop and report.
- Outcome rules:
  - κ ≥ 0.6 and F1 within 0.03 of 0.9091: keep the headline, state the cross-family agreement in Limits. Project 01 → 9.0.
  - κ < 0.6 or F1 moves more than 0.03: do not replace the headline silently. Report both numbers, keep 8.8 for 01, and state the disagreement.

### Phase 3 — Project 12 option B (E12), valid version
- The earlier scratch run is discarded (different imputation path from the E4 arm).
- Re-run the variant through `run_ladder_arm` / `run_sensitivity` only, in a scratch copy. Output: `reports/v2/` in the scratch copy, not the repo.
- Gates: reproduction of v1 (25.4316 MLP, 25.3732 LightGBM) must pass first; v2 must pass the 13 parity gate (1e-4).
- Owner decision needed before Phase 4 commits: promote v2 as the headline (option B). If the owner says no, 12 stays 8.8 and Phase 4 is skipped.
- Cost: about 1 CPU min for 12 plus about 2 h for 13 (only if promoted).

### Phase 4 — Project 13 and 12 headline (only if Phase 3 promoted)
- Regenerate 13 from v2: reproduction target, ONNX parity, images, load bench.
- Update 12 and 13 copy: v1 kept for comparison with its delta; "reproduces v2's `<x>`"; re-key headline and reproduction gates in one commit.
- Fix known clobber: `projects/13-model-serving/src/model_serving/report.py` writes a `_meta` dict literal. Fix before re-running 13.
- Expected: 12 → 9.0 (option B), 13 → 9.0.

### Phase 5 — Copy and figure close-out for the rest
- 03: confirm 0.527 collision resolved; titles without "champion".
- 04: confirm the broken-sentence fix is committed; paired cascade CI shown in copy and figure (E6 result: F1 gain not distinguishable from zero — say so).
- 05: titles and results lead on the headline, not fairness; the CI note about threshold selection.
- 06: titles; 5-vs-8 count.
- 07: confirm E2 CI in copy; coverage in metrics or figure JSON, with the source named.
- 09: confirm 17/19 on all four surfaces (done in docs handoff); check `storyShort.ts` regenerated.
- 10: CI from `report.html` surfaced in `metrics.json` (additive `analysis` key, D0 rule); titles; "12.03" interval wording.
- 11: two non-finding titles.
- Gates: lint_story_language, check_short_copy, gen_story_short, gen_static_registry, check_headline_numbers, check_figure_axes, check_figure_budget, check_docs, mkdocs strict.

### Phase 6 — Final verification and grade table
- Run the full gate set (ruff, format, mypy, pytest per project, npm test/lint/build, scripts, mkdocs strict, git diff --check). Record exit codes.
- Opus review of the closeout and the final grade table, same as earlier rounds.
- Final grade table: **14 projects** (01–13 and 15). No project 14.
- Per-axis before/after, and an honest note on 08 at 8.8.

### Phase 7 — Commit and hand to orchestrator
- Commit per phase on the wave8 branch. No model co-author trailer. No push, no deploy, no merge to main except a fast-forward of main to the branch, if the owner approves.
- Write the orchestrator message: branch head, `main` head, gate exit codes, deploy request.

## Stop rules (apply to every phase)
- Any headline number changes without an owner-approved phase: stop and report.
- Hosted spend beyond $2.00 for Phase 2, or beyond the $5.00 overall cap: stop.
- Any reproduction or parity gate fails: stop that item, report, keep the disclosed copy.
- No experiment or training run in the main repo tree; scratch copies only until a phase is approved.
- Do not touch the gitignored `projects/08-inference-serving/data/bench_run_repeat.json`.
- E10 is closed (STOP record `c53069eb`); do not re-attempt.

## Owner decisions still needed
1. Promote 12 option B (v2 headline, 13 regenerated)? Recommended yes, after the Phase 3 reproduction passes. Without it, 12 stays at 8.8.
2. Project 08: accept 8.8 (recommended) or pursue a second host.
3. Keep `c53069eb` (E10 harness and STOP record) on the branch? Recommended yes; it is a record, not a result.
4. Approve the $2.00 Phase 2 cap (or name another figure).

## Expected outcome
- Projects at 9.0: 01 (if judge agrees), 02 (if E9 reproduces), 03, 04, 05, 06, 07, 09, 10, 11, 15, and 12 and 13 if option B is approved.
- Projects that stay at 8.8: 08 (one host), and 01/12 if the owner or the judge says no.
- Each downgrade is named in the final table with its cause.
