# Message for Kimi — pass 5 closeout fixes (revised after Opus re-check)

Supersedes `07-kimi-closeout-fixes.md`. Copy and docs only, plus the one script commit. Change no numbers, code paths, or committed metrics. No push, deploy, or fast-forward of `main`. No co-author trailers. Never hide a gate failure.

## Order (follow exactly)

1. **Parity disclosure, commit `docs(13): disclose the parity relative term`.**
   - `docs/projects/13-model-serving.md:11`: state the real gate: "1e-4 rentals plus a float32 term of 1e-5 times the largest prediction, limit 6.8e-3. The measured max-abs is 2.6e-4, above the bare 1e-4, and would fail without the term."
   - Add the bare-1e-4 comparison beside "about 26× inside the limit" at `docs/projects/13-model-serving.md:40` and `projects/13-model-serving/story.yaml:103`.
   - `projects/13-model-serving/README.md:83-84`: add the same sentence beside the limit.
   - Pin the numbers to `projects/13-model-serving/reports/train_run.json`: max_abs 2.646e-4, limit 6.791e-3. 6.791e-3 / 2.646e-4 ≈ 25.7, so "about 26×" holds.
   - **Do not stage `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-4-result.md` or any other untracked review file in this commit.** The owner-acceptance note for `phase-4-result.md` goes in later, with the review-records commit.
   - After editing line 11, run `check_headline_numbers` and confirm it still matches the parity figure. If it fails, record the output and stop.

2. **Mypy fix, commit `fix(01): mypy fix for grade_final_v4_rerun`.**
   - Confirm `uv run mypy libs projects apps` exits 0 before committing `projects/01-rag-agent/scripts/grade_final_v4_rerun.py`.

3. **Table wording in `phase-7-result.md`.**
   - **13 row:** add the parity-miss disclosure, the same wording as step 1.
   - **01 row:** name the capped axis. T is capped at 8 (9/9/8/9 → 8.8). State that replication F1 is 0.8466 against the committed 0.9091, and that the committed headline stays. Keep the disclosure.
   - **15 row:** set per-axis to 9/10/9/8 and the overall to 9.0, consistent with the axes (9+10+9+8 = 36, /4 = 9.0). Keep "9.3 pending the orchestrator's browser check of the five diagrams" in the note column only. Do not run or claim the browser check.
   - **08 row: do not edit.** The axes 9/9/6/9 give 8.25, which rounds to 8.3, not the owner-accepted 8.8. Leave the row as it is and write this line in the phase-7 record: "08: axes 9/9/6/9 give 8.3 by the overall formula; the owner accepted 8.8; pending owner confirmation of which axes back 8.8." Do not change any grade on your own.

4. **Row checks (commit each fix separately as `docs(NN): …` if it changes copy).**
   - Read each artifact, compare it with its row, and fix the copy to match the artifact. Never change a committed metric.
   - **01:** count `budget_terminated` in `reports/final_v4_rerun/question_traces_heldout.json` and in the committed `final_v3_e2e` traces. Confirm the "24 vs 4" figure.
   - **04:** check the paired CI and McNemar values against `reports/llm_cascade_paired_ci.json`.
   - **05:** check the −$392 [−$439, −$340] values against `reports/repeated_splits.json`.
   - **06:** check the 5-vs-8 count and the finding titles.
   - **09:** check the 17/19 count on all four surfaces.
   - **10:** check the "bit-identical to 0c01c45d" claim with `git show 0c01c45d:<metrics path>`.
   - **11:** check the finding titles.
   - **13 p50:** read `projects/13-model-serving/reports/metrics.json` at `serving.native.concurrency.c1.p50_s`. Record the value and the path. Check the copy against it. Do not assume a value. (A prior measurement gave 1.968 ms, so "2.0 ms" is expected to hold; confirm it from the file.)
   - **15:** diagram status — specs registered and the fence gate passing. The browser check stays pending.
   - Report every row you cannot verify. Do not guess.

5. **Phase 6 gates, once, after all edits.**
   - Run every gate in the list below and record each exit code in `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-6-result.md`:
     - `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy libs projects apps`
     - `uv run python scripts/lint_story_language.py`, `check_short_copy.py --check`, `gen_static_registry.py --check`, `gen_story_short.py --check`, `gen_route_manifest.py --check`, `check_headline_numbers.py`, `check_docs.py`, `check_demo_contract.py`, `check_diagram_fences.py`, `check_figure_axes.py`, `check_figure_budget.py`
     - `uv run mkdocs build --strict`, `git diff --check`
     - `cd apps/showcase-web && npm test && npm run lint && npm run build`
     - pytest for every project suite, `scripts/tests`, `libs/portfolio-core`, and `apps/showcase-api`, with an exit code for each.
   - Do not use a subset. The story.yaml edits feed the static registry and the web build.
   - Any non-zero exit: record the output and stop. Do not hide it.

6. **Review records, commit `docs(review): pass 5 closeout records`. Last.**
   - Commit the untracked pass-5 folder, the pass-4 `02-kimi-docs-handoff.md`, and the pass-4 `phase-4-result.md`.
   - Add to `phase-4-result.md` at lines 48–49: the owner accepted the float32 relative term on 2026-11-26, and the gate fails without it.

## Report back
- Commit hashes for steps 1, 2, 4 (any `docs(NN)` commits), and 6.
- Phase 6 exit codes, one line per gate.
- Table rows changed, and why.
- Rows you could not verify.
- The 08 line exactly as it appears in the phase-7 record.

Do not push, deploy, or fast-forward `main`.
