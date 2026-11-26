# Grade pass 5 — revised execution plan

Supersedes `02-execution-plan.md` and the Kimi draft pasted 2026-11-26. Branch `wave8-articles-truthfulness-2026-11-25`.

## Owner approvals (unchanged)
- Project 12 MLP rerun (Phase 3), CPU only, in scratch: **approved**.
- Project 01 hosted judge, cap **$2.00**: **approved** as a judge run.
- Overall hosted cap $5.00. Spent $0.41.
- Promotion of v2 as project 12 headline (option B): **not approved**; decided after Phase 3.
- Project 08 at 8.8: accepted.

## Global rules
- No push, no deploy, no merge. Fast-forward of `main` only after the owner approves (not in this pass by default).
- No model co-author trailers.
- Never touch `projects/08-inference-serving/data/bench_run_repeat.json`.
- E10 is closed. Do not re-run it.
- Before any run that rewrites a committed file, copy it to scratch. Restore any `_meta`, lineage, platform or processor field the run changes beyond the intended change.
- Experiments run in scratch copies until their phase is approved and committed.
- Stop and report, don't improvise, on: a failed reproduction or parity gate; spread over 0.10 MAE; spend past a cap; a committed headline changing without approval; any step needing unplanned hardware or data.

## Verified state (from Kimi's check, to re-verify at start)
- E9 (agent-889) still running. Its in-flight 02 files (`cli.py`, `m5_full_refit.py`) and forecast-workbench demo files must not be touched until it completes.
- Docs-handoff edits are uncommitted. They get their own commit in Phase 7.
- The E4 path is `run_ladder_arm` (`projects/12-.../sensitivity.py:112`) and `run_sensitivity` (`:205`).
- Project 01 `reporting.py:560-563` reads `answer` and `claims` via getattr. The writer side is not yet confirmed to fill them.
- Scratch `scratchpad/e12_v2` holds invalid numbers. Do not read or cite them.

## Phase 1 — E9 landing (02)
1. Wait for agent-889's completion report. Read it.
2. If the reproduction gate passed (0.62105 ±1e-6):
   - review the forecast-workbench diff before committing; the demo contract gate must pass;
   - commit E9 as its own commit;
   - restamp 02 as its own commit.
   - **Do not fast-forward main.** Leave that for the owner.
3. If it failed: stop, report, keep the disclosure copy.

## Phase 2 — Project 01 cross-family judge (approved judge run, cap $2.00)

Split into three sub-steps. Only 2c spends money.

**2a. Credential check (no spend).** Look for ANTHROPIC, OPENAI, or GEMINI keys in the repo `.env`, project `.env`, and `libs/portfolio-core` config. The last check found only Moonshot.
- Key found: the hosted cross-family judge is the plan.
- No key: stop before any spend and report. The fallback is the local qwen2.5:3b judge, which the owner has already called weak evidence. Do not use it to decide the headline. Ask the owner whether to add a key or accept the local judge.

**2b. Persistence wiring (no spend).** Make the E2E eval path fill `answer` and `claims` in the output, with a unit test. Confirm it writes under a new directory and never overwrites `final_v3` outputs.
- Gate: unit test passes; project 01 suite passes.

**2c. final_v4 run (spend, cap $2.00).** Two separate costs:
- **Answer generation** (kimi-for-coding, re-running the 120 consumed final_v3 questions): this is **not** covered by the approval for "a paid run for the LLM judge". The E8 note said a ~$1 regeneration needed an owner call. **Ask the owner before generating.** If the owner declines, the cross-family judge can't run on new answers; report that.
- **Judge** (hosted second-family model over persisted answers): covered by the approval. Set a hard meter stop so generation plus judge stays under $2.00. The meter stop must be set at or below $2.00 in total, not $1.60 for generation alone.
- Log the rerun in `final_v3_file_access.json` as a read: "final_v4 rerun for answer persistence + cross-family judge, no selection".
- Report answer-level F1 under both judges, agreement, and Cohen's κ.

**Outcome rules.**
- κ ≥ 0.6 and F1 within 0.03 of 0.9091: keep the headline, add the cross-family sentence to Limits. Project 01 → 9.0 candidate.
- Otherwise: report both numbers, leave the headline untouched, 01 stays at 8.8.

Commit the copy patch and the result as their own commit. Restamp 01 separately.

## Phase 3 — Project 12 scratch rerun (CPU only, stop at end)
1. Copy project 12 to a **fresh** scratch directory (`scratchpad/e12_v2_rerun/`). Do not read `scratchpad/e12_v2`. Run everything inside the copy.
2. Gate 1: committed config through `run_ladder_arm` / `run_sensitivity`. MLP must reproduce 25.4316 (±1e-4); LightGBM 25.3732. Fail → stop.
3. Gate 2: corrected variant (`params_variant.yaml`) through the same path, three runs, seed 42. Record MLP and LightGBM test MAE and seasonal naive for each run.
4. Spread rule: MLP range ≤ 0.10 → v2 = median. Otherwise stop.
5. Variant seasonal naive must match E4's 72.98. Mismatch → stop.
6. Write `phase-3-result.md`: gates, three runs, median, naive check, side-by-side with committed v1 and the E4 arm.
7. **Stop.** No committed file in 12 or 13 changes in this phase.

## Phase 4 — Option B promotion (only after the owner approves Phase 3)
1. Fix the `_meta` dict literal in `projects/13-model-serving/src/model_serving/report.py`. Own commit.
2. Write v2 artifacts. Keep v1 under `previous_runs.v1` in `metrics.json` (additive, D0 rule). Restore any `_meta` or lineage field that changes beyond the intended change.
3. Regenerate 13 from v2: reproduction target (v2 MLP median), ONNX parity at 1e-4, images, load bench. Parity fail → stop.
4. Copy updates for 12 and 13, and the re-keyed headline and reproduction gates, in one commit.
5. If LightGBM beats the MLP under v2 on validation, stop before changing the served model and report it as its own decision point.

## Phase 5 — Copy and figure sweep
Verify, fix only gaps:
- 03: 0.527 wording; no "champion" in titles.
- 04: broken sentence fixed (docs handoff); paired CI in copy and figure (E6).
- 05: headline-first titles; threshold-selection note.
- 06: 5-vs-8 count.
- 07: E2 CI in copy; coverage source named.
- 09: 17/19 on four surfaces (docs handoff).
- 10: CI in `metrics.json` (E1); 12.03 interval wording check.
- 11: non-finding titles (Phase C).
Regenerate short copy and static registry per repo rules.

## Phase 6 — Verification
Record exit codes for:
- `ruff check`, `ruff format --check`, `mypy libs projects apps`
- `lint_story_language`, `check_short_copy --check`, `gen_static_registry --check`, `gen_story_short --check`, `gen_route_manifest --check`, `check_headline_numbers`, `check_docs`, `check_demo_contract`, `check_diagram_fences`, `check_figure_axes`, `check_figure_budget`
- `mkdocs build --strict`, `git diff --check`
- `apps/showcase-web`: `npm test`, `npm run lint`, `npm run build`
- pytest for each project suite, `scripts/tests`, `libs/portfolio-core`, `apps/showcase-api`

## Phase 7 — Commits and final table
- One commit per phase, messages naming the phase and gate results. No co-author trailer.
- Docs-handoff edits: their own commit.
- Final table: **14 projects** (01–13 and 15; there is no project 14). Per-axis before and after, with the cause of every downgrade.
- 08 stays 8.8. 01 → 9.0 only if the Phase 2 outcome rule passes. 02 → 9.0 only if E9 reproduced. 12 and 13 → 9.0 only if option B is promoted.
- Phase result files: `phase-N-result.md` in `collaboration/reviews/20261126-grades-pass-5-close-to-9/`.

## Reporting after each phase
Result file path, commit hashes, gate exit codes, spend, and any number that changed and why.

## Changes from the Kimi draft
1. **Phase 1:** removed "ff main". Main stays until the owner approves.
2. **Phase 2:** removed the fallback to the local 3B judge as a grader for the headline. Without a hosted key, stop and ask the owner.
3. **Phase 2:** split into 2a/2b/2c. The answer regeneration (about $1) is not covered by the judge approval, so it needs its own owner OK before it runs.
4. **Phase 2:** the meter stop is $2.00 total, not $1.60 for generation plus judge.
