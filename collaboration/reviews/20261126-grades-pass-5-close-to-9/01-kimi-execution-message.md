# Message for Kimi — execute grade pass 5 (close to 9)

Plan: `collaboration/reviews/20261126-grades-pass-5-close-to-9/00-plan.md`. Read it in full first. The stop rules in it apply to every step.

Branch: `wave8-articles-truthfulness-2026-11-25`. Work only in the working tree. Do not push, deploy, or merge to main. Do not add model co-author trailers to commits.

## Current state (verify before starting)
- E9 (project 02 refit) may still be running. Do not start a second refit. Check it has finished and its reproduction gate result before Phase 1.
- Uncommitted docs changes from the docs handoff are in the tree. Keep them; check `02-kimi-docs-result.md`.
- The E12 scratch run (`scratchpad/e12_v2`) is NOT a valid v2. Do not use it. Phase 3 redoes it through `run_ladder_arm`.
- E10 is closed. Do not re-run it.

## Owner approvals in this round
- Hosted LLM judge for project 01 (Phase 2): **cap $2.00**. Stop if the spend would exceed it.
- Overall hosted cap across the project: $5.00. Spent so far: $0.41.
- Project 12 option B (Phase 3–4): **not yet approved**. Run Phase 3 reproduction and v2 in scratch only, then stop and report before any commit to 12 headline or 13.
- Project 08: accept 8.8. No second host, no quantization pair.

## Steps, in order

1. **Phase 1 — 02 refit.** When E9 finishes: check the reproduction gate (0.62105 within 1e-6). If it passes, restore the sample-series figure and the headline interval, commit as its own commit, restamp 02 separately. If it fails, stop and report. Do not publish any number that did not reproduce.

2. **Phase 2 — 01 cross-family judge.** New `final_v4` run that persists answer texts and claims. Do not overwrite `final_v3` outputs. Run one hosted second-family judge on all answers, cap $2.00. Report answer-level F1 for both judges, agreement, and kappa. Apply the outcome rules in the plan. Commit with its own message.

3. **Phase 3 — 12 option B, valid v2 (scratch only).** Copy project 12 to scratch. Run the variant through `run_ladder_arm` / `run_sensitivity`, not the standard pipeline. First gate: reproduce v1 (MLP 25.4316, LightGBM 25.3732). Then produce v2 outputs under `reports/v2/` in the scratch copy. Report the numbers and both gates. **Stop here and wait for owner approval** before promoting.

4. **Phase 4 — only if the owner approves Phase 3.** Fix the `_meta` dict-literal clobber in `projects/13-model-serving/src/model_serving/report.py` first. Regenerate 13 from v2 (reproduction target, ONNX parity 1e-4, images, load bench). Update 12 and 13 copy per the plan, and re-key the headline and reproduction gates in one commit.

5. **Phase 5 — copy and figure close-out.** Items per project are in the plan (03, 04, 05, 06, 07, 09, 10, 11). Put the 10 CI into `metrics.json` as an additive `analysis` key (D0 rule). Keep committed numbers unchanged. Regenerate `storyShort.ts` and the static registry as the repo rules require.

6. **Phase 6 — verification.** Run the full gate set in the plan. Record each exit code in `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-N-result.md`, one file per phase. Include: commits, files changed, gate exit codes, experiments run with cost, any number that changed and why, and before/after grades per axis.

7. **Phase 7 — commit and report.** One commit per phase, message names the phase and gate results. Write the final grade table: 14 projects (01–13 and 15; there is no project 14). Note 08 at 8.8 on one host. Report the wave8 branch head and whether main was fast-forwarded (only if the owner has approved that).

## Do not
- Do not run any experiment in the main tree before its phase is approved.
- Do not touch `projects/08-inference-serving/data/bench_run_repeat.json` (gitignored; must stay untracked).
- Do not replace a committed headline number unless the owner has approved that phase.
- Do not spend beyond the caps above. Stop and report if a step would.

## Report back
- Each phase result file path, the commit hashes, the gate exit codes, the spend, and anything not done and why.
- Stop and wait for the owner at: Phase 3 end (option B decision), any failed reproduction gate, and any judge outcome that moves a headline.
