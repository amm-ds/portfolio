# Message for Kimi — 09 deadline test change (owner approved 2026-11-27)

Owner approved a **test-only** change to the two project 09 deadline tests that fail under load.

## Scope
- Test files only. No product code, no graph code, no copy, no metric.
- Change the deadline the two tests use from 10 ms to about 0.25 s. Or, if that is not enough, assert the terminal result (`deadline_exceeded`) rather than a timing. Pick the one that keeps each test's meaning. Say which you chose.
- The product already enforces the deadline correctly at 0.01–0.5 s (`deadline_exceeded`), per your characterisation. The test must still prove that.

## Steps
1. Make the change in the two 09 deadline tests only.
2. Run `uv run pytest projects/09-agentic-workflows -q -o addopts=""` five times. Record each exit code and pass count.
3. Run `uv run ruff check`, `uv run ruff format --check`, and `uv run mypy libs projects apps` on the changed test files. Record exit codes.
4. Commit as `test(09): deadline tests assert terminal result under load`, or the same subject with the chosen approach. No co-author trailer.
5. Add a short addendum to `phase-6-result.md` with the five runs and the chosen approach.

## Do not
- Change any `src/` file in project 09.
- Change any copy or the 09 headline numbers.
- Push, deploy, or fast-forward `main`.

## Still open (not approved)
- The 13 short-version rewrite in `f88b259d` is still waiting for the owner's acknowledgement. Do not change that wording.

## Report back
Commit hash, the choice made, and the five run results.
