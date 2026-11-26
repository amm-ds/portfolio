# Grade pass 5 — execution plan (supersedes 00-plan.md phases 3–4 wording)

Date: 2026-11-26. Branch: `wave8-articles-truthfulness-2026-11-25`.
Owner approvals in this round:
- **Approved:** the project 12 MLP rerun (reproduction gate plus repeated variant runs), CPU only, in scratch.
- **Approved:** hosted LLM judge for project 01, **cap $2.00**.
- **Overall hosted cap:** $5.00 (spent $0.41).
- **Not yet approved:** promoting v2 as the project 12 headline (option B). Decide after the rerun results are in.
- **Accepted:** project 08 at 8.8 (one host).

Execution agent: Kimi. Claude reviews each phase result.

## Global rules
- Work in the working tree on the wave8 branch. No push, deploy, or merge to main except a fast-forward when the owner approves it.
- No model co-author trailer in any commit.
- Before any run that rewrites a committed file, copy it to the scratchpad. Restore any `_meta`, lineage, platform, or processor field a run changes beyond the intended change.
- Experiments run in scratch copies until their phase is approved and committed.
- Do not touch `projects/08-inference-serving/data/bench_run_repeat.json` (gitignored).
- E10 is closed. Do not re-run it.
- If a step would exceed a cap, use hardware not in the plan, or change a committed headline without approval, stop and report.

## Current state (verify first)
- E9 (project 02 refit) may still be running. Check it finished and its reproduction gate result (0.62105 within 1e-6). Do not start another 02 refit.
- Docs handoff edits (`02-kimi-docs-result.md`) are uncommitted. Keep them.
- The earlier E12 scratch run (`scratchpad/e12_v2`) is NOT valid. It used the standard pipeline, not the sensitivity path. Do not use its numbers.
- The E4 sensitivity arm gave the corrected-variant MLP 27.16 and LightGBM 23.76. That is the reference to reproduce.

## Phase 1 — Project 02 refit (E9)
1. When E9 finishes, read its reproduction gate result.
2. If it passes (0.62105 within 1e-6): restore the sample-series figure and headline interval, commit as its own commit, and restamp 02 separately.
3. If it fails: stop, report the failing gate, keep the disclosure copy. Do not publish an unreproduced number.

## Phase 2 — Project 01 cross-family judge (paid, cap $2.00)
1. Add a `final_v4` run that persists answer texts and claims. Do not overwrite `final_v3` outputs.
2. Run one hosted second-family judge over all answers. Stop if spend would exceed $2.00.
3. Report answer-level F1 for both judges, agreement, and kappa.
4. Outcome rules:
   - κ ≥ 0.6 and F1 within 0.03 of 0.9091: keep the headline, state cross-family agreement in Limits. Project 01 → 9.0.
   - Otherwise: do not replace the headline silently. Report both numbers, keep 01 at 8.8, and state the disagreement.
5. Commit as its own commit.

## Phase 3 — Project 12 MLP rerun for option B (approved, CPU only, scratch)
Goal: confirm the corrected-variant MLP number is stable before anything is promoted.

1. Copy project 12 to a scratch directory. Do not run in the repo tree.
2. **Gate 1, v1 reproduction:** run the committed configuration through the sensitivity path (`run_ladder_arm` / `run_sensitivity`). MLP must reproduce 25.4316 (tolerance 1e-4) and LightGBM 25.3732. If it fails, stop.
3. **Gate 2, variant rerun:** run the corrected variant (`params_variant.yaml`) through the same path **three times** with the committed seed (42). Record MLP and LightGBM test MAE for each run, plus the seasonal naive baseline.
4. **Spread rule:** if the MLP range across the three runs is ≤ 0.10 MAE, v2 uses the median. If larger, stop and report; do not promote.
5. Check that the variant seasonal naive matches the E4 value (72.98). The earlier scratch run gave 83.20, so this is the test that distinguishes the two paths. If it doesn't match, stop and report.
6. Write `phase-3-result.md` in this folder: all gate results, the three runs, the median, the seasonal naive check, and a side-by-side with the committed v1 and the E4 arm numbers.
7. **Stop here and wait for owner approval** before any promotion. Do not change any committed file in project 12 or 13 in this phase.

## Phase 4 — Option B promotion (only after the owner approves Phase 3)
1. Fix the `_meta` dict-literal in `projects/13-model-serving/src/model_serving/report.py` before any 13 re-run. Commit that fix on its own.
2. Write v2 artifacts into the repo, keeping v1 under `previous_runs.v1` in `metrics.json` (additive, D0 rule). Restore any `_meta` field that changes beyond the intended change.
3. Regenerate project 13 from v2: reproduction target (v2 MLP median), ONNX parity at 1e-4, images, load bench. Stop if parity fails.
4. Update 12 and 13 copy: "v2 fixes two disclosed defects; v1 remains for comparison and moved by `<Δ>`"; 13's "reproduces 25.4316" becomes "reproduces v2's `<x>`". Re-key the headline and reproduction gates in one commit.
5. If LightGBM beats the MLP under v2 on validation, the served model changes. Report that as its own decision point before committing 13's served model.
6. Commit in separate commits: fix, v2 artifacts, 13 regeneration, copy update.

## Phase 5 — Copy and figure close-out (all projects)
Use the per-project items in `00-plan.md` section "Phase 5". Summary:
- 03: 0.527 collision resolved; no "champion" in titles.
- 04: broken-sentence fix committed; paired cascade CI in copy and figure (E6: gain not distinguishable from zero).
- 05: titles and results lead on the headline; threshold-selection note in the CI copy.
- 06: titles; 5-vs-8 count fixed.
- 07: E2 CI in copy; coverage source named in metrics or figure JSON.
- 09: 17/19 on all four surfaces; `storyShort.ts` regenerated.
- 10: CI from `report.html` added to `metrics.json` as additive `analysis` key; titles; 12.03 interval wording.
- 11: two non-finding titles.
- Keep committed numbers unchanged. Regenerate short copy and static registry per repo rules.

## Phase 6 — Verification
Run and record exit codes:
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy libs projects apps`
- `uv run python scripts/lint_story_language.py`, `check_short_copy.py --check`, `gen_static_registry.py --check`, `gen_story_short.py --check`, `gen_route_manifest.py --check`, `check_headline_numbers.py`, `check_docs.py`, `check_demo_contract.py`, `check_diagram_fences.py`, `check_figure_axes.py`, `check_figure_budget.py`
- `uv run mkdocs build --strict`, `git diff --check`
- `cd apps/showcase-web && npm test && npm run lint && npm run build`
- pytest for every project suite and `scripts/tests`, `libs/portfolio-core`, `apps/showcase-api`
Then Opus review of the closeout and the final grade table.

## Phase 7 — Commit and final table
1. One commit per phase, message names the phase and gate results, no co-author trailer.
2. Final grade table: **14 projects** (01–13 and 15). There is no project 14. Per axis before and after, with the cause of any downgrade.
3. Project 08 stays at 8.8 (one host). Project 01 at 9.0 only if the judge outcome rule passes. Project 02 at 9.0 only if E9 reproduces. Project 12 and 13 at 9.0 only if option B is promoted.
4. Report: branch head, whether `main` was fast-forwarded (only with owner approval), and the list of phase result files.

## Stop and report (do not improvise)
- Any reproduction or parity gate fails.
- Spread across the three variant MLP runs exceeds 0.10 MAE.
- Hosted spend would exceed $2.00 (Phase 2) or $5.00 overall.
- A committed headline number would change without owner approval.
- Any step needs hardware or data outside this plan.

## Report back, per phase
Commit hashes, files changed, gate exit codes, experiments run with cost, any number that changed and why, and grades before and after per axis. Save as `phase-N-result.md` in this folder.
