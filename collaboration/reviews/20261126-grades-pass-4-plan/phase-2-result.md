# Grade pass 4, Phase 2 (contents): result

Branch: `wave8-articles-truthfulness-2026-11-25`.

## Commit

- `61514cab` docs(portfolio): grade pass 4 phase 2 contents (32 files).

## Scope

All §4 contents edits from `00-plan.md` applied across root `README.md`,
`docs/projects/index.md`, and the stories/READMEs/docs pages of projects
01–13. Highlights:

- Root README reproducibility claim rewritten (per-project caveats: LLM
  endpoints for 01/04/09, hardware for 08/13, ~375 CPU-hours for 02).
- Stack "Where" column updated (12/13 pytorch, 10/12/13 scikit-learn,
  09 pydantic-ai, 11 polars; new rows lightgbm, duckdb, onnxruntime+Docker,
  stable-baselines3), checked against each `pyproject.toml`.
- `docs/projects/index.md` 02 Pinned corrected 0.6161 → 0.6211 (TRU).
- "champion" wording replaced with served/recommended-detector language in
  the passages listed in §4 (PROC).
- Short-version rewrites for 01, 03, 09 (regenerated via
  `gen_story_short.py`; 01/03/09 backgrounds trimmed under the 150-word
  first-section cap).

## Gates (all exit 0 at commit time)

- `check_short_copy.py --check`, `gen_story_short.py --check`,
  `gen_static_registry.py --check`
- `check_headline_numbers.py` (0 findings)
- `lint_story_language.py` (0 errors, 0 warnings)
- `check_docs.py`, `mkdocs build --strict`
- jargon grep clean except accepted model-selection uses

## Notes

- Phase B was written against the evidence available at the time; no
  experiment results were pre-announced (per plan §3).
- The "after E-n" sentences are deferred to the Phase D experiments that
  produce them.
