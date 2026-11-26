# Message for Kimi — pass 5 closeout fixes (Opus verdict: HOLD)

Source: Opus review of the pass 5 closeout and grade table. Owner decisions are unchanged (option B promoted with LightGBM served; float32 relative term accepted for the 13 parity gate; $2.00 judge cap and regeneration approved; 08 accepted at 8.8; no fast-forward of `main`; no co-author trailers).

Do these in order. Copy and documentation only, plus the one script commit. Change no numbers, no code paths, and no committed metrics.

## 1. Parity disclosure (blocker)
Owner ordered this in `06-parity-disclosure-approval.md`. It has not been done.
- `docs/projects/13-model-serving.md:11` says "behind a 2.6e-4-rental parity gate". Replace with the gate as it is: "1e-4 rentals plus a float32 term of 1e-5 times the largest prediction (limit 6.8e-3). The measured max-abs is 2.6e-4, above the bare 1e-4, and would fail without the term."
- `docs/projects/13-model-serving.md:40` and `projects/13-model-serving/story.yaml:103` say "about 26× inside the limit". Keep the figure, but add the bare-1e-4 comparison in the same sentence.
- `projects/13-model-serving/README.md:83-84`: add the same bare-1e-4 sentence next to the limit.
- `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-4-result.md:48-49`: record that the owner accepted the term on 2026-11-26 and that the gate fails without it.
- Commit: `docs(13): disclose the parity relative term`. No co-author trailer.

## 2. Mypy fix (blocker)
- `projects/01-rag-agent/scripts/grade_final_v4_rerun.py` is modified and uncommitted (3+/3−). Confirm `uv run mypy libs projects apps` passes with it, then commit as `fix(01): mypy fix for grade_final_v4_rerun`.

## 3. Phase 6 result (blocker)
Write `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-6-result.md`. Run and record exit codes for:
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy libs projects apps`
- `uv run python scripts/lint_story_language.py`, `check_short_copy.py --check`, `gen_static_registry.py --check`, `gen_story_short.py --check`, `gen_route_manifest.py --check`, `check_headline_numbers.py`, `check_docs.py`, `check_demo_contract.py`, `check_diagram_fences.py`, `check_figure_axes.py`, `check_figure_budget.py`
- `uv run mkdocs build --strict`, `git diff --check`
- `cd apps/showcase-web && npm test && npm run lint && npm run build`
- pytest for each project suite, `scripts/tests`, `libs/portfolio-core`, `apps/showcase-api`
Any non-zero exit: record the output and stop; do not hide it.

## 4. Commit the review files (blocker)
- Commit the untracked pass 5 folder, the pass 4 `02-kimi-docs-handoff.md`, and the pass 4 `phase-4-result.md`, as `docs(review): pass 5 closeout records`. No co-author trailer.

## 5. Grade-table wording (note)
In `phase-7-result.md`:
- **13 row:** add the parity miss, the same wording as item 1.
- **01 row:** name the capped axis. The table caps T at 8 (9/9/8/9). Say that replication F1 is 0.8466 against 0.9091, and that the committed 0.9091 headline stays while the fresh rerun disagrees. Keep the disclosure.
- **15 row:** V is 9 in the table with an overall of "9.0 (9.3 pending)". Either set V to 8 until the browser check passes and show overall 9.0, or show overall 9.3 once the check passes. Pick one and make it consistent.

## 6. Rows Opus could not verify (note)
Check each against its artifact and fix any mismatch:
- 01: the "24 vs 4 loop-rail terminations" detail.
- 04: the paired CI and McNemar values in `reports/llm_cascade_paired_ci.json`.
- 05: the −$392 [−$439, −$340] values against `reports/repeated_splits.json`.
- 06: the 5-vs-8 count and finding titles.
- 09: the 17/19 count on all four surfaces.
- 10: the "bit-identical to 0c01c45d" claim.
- 11: the finding titles.
- 13: the p50 2.0 ms. The metrics `p50_s` values are about 54 ms, which may be load-bench figures. Name the source file for 2.0 ms, or correct the number to match its source.
- 15: the diagram status.

## Gates to re-run after the edits
`lint_story_language`, `check_short_copy --check`, `gen_story_short --check`, `gen_static_registry --check`, `check_headline_numbers`, `check_docs`, `mkdocs build --strict`, `git diff --check`. Record exit codes in `phase-6-result.md`.

## Report back
Commit hashes for items 1, 2 and 4, the phase 6 exit codes, the list of table rows changed and why, and any row you could not verify. Do not push, deploy, or fast-forward `main`.
