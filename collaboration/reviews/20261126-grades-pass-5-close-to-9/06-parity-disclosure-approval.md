# Owner decision — ONNX parity gate: accept the float32 relative term

Date: 2026-11-26. Owner: accepted the float32 relative term in the project 13 parity gate.

## What the gate is
- Tolerance: `parity_tolerance` = 1e-4 (config default, `projects/13-model-serving/src/model_serving/config.py:112`).
- Float32 relative term added in commit `96b25cbb`: `1e-5 × max(1, max|native prediction|)`. On this run that gives a limit of 6.8e-3.
- Measured max-abs on 512 seeded probe rows: 2.65e-4 rentals. Inside the limit, and **outside the bare 1e-4 tolerance**.

## Required disclosure (Kimi, copy only, no number changes)
The gate was widened from 1e-4 to 1e-4 + a relative term, and the measured 2.6e-4 is above the bare 1e-4. Say so in one plain sentence wherever the parity gate is named:

- `docs/projects/13-model-serving.md`: line 11 ("behind a 2.6e-4-rental parity gate") and line 37 (the hard parity gate paragraph). Add: "The gate is 1e-4 rentals plus a float32 term of 1e-5 times the largest prediction, a limit of 6.8e-3; the measured max-abs is 2.6e-4, above the bare 1e-4."
- `projects/13-model-serving/README.md`: line 83. Same sentence.
- `projects/13-model-serving/story.yaml`: line 28 and line 41 (name the limit alongside the measured value); line 204 already says "inside the 1e-4 + relative-term gate (limit 6.8e-3)"; keep it.
- `collaboration/reviews/20261126-grades-pass-5-close-to-9/phase-4-result.md`: line 48–49. Record that the owner accepted the relative term on 2026-11-26, and that without it the gate would fail.

## Then
1. Run the copy gates: `lint_story_language`, `check_short_copy --check`, `gen_story_short --check`, `gen_static_registry --check`, `check_headline_numbers`, `check_docs`, `mkdocs build --strict`. Record exit codes.
2. Commit as its own commit (`docs(13): disclose the parity relative term`), no co-author trailer.
3. Do not change the parity code, the limit, or any number.

## Still open (not part of this decision)
- Phase 6 gate batch and the uncommitted mypy fix.
- Opus review of the closeout and the 14-project table before anything is called final.
- Fast-forward of `main`: not approved.
