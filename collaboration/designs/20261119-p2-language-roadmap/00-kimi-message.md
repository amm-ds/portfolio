# Message for Kimi: P2 language and roadmap pass (approved 2026-11-19)

Read first:
1. `collaboration/reviews/20261119-gap-analysis/01-language-and-roadmap-pass.md` (sections 2–7 are the rules; section 3 has rewrites for 03, 09 and 12)
2. `collaboration/reviews/20261119-gap-analysis/00-gaps-benchmarks-approaches.md` (only for the conflicts list; do not change numbers from it)

Do:
1. Roadmap cards, all 13 projects, per section 2 of the pass: 3–4 `shipped` cards, 1–2 `next` or `blocked` cards, each detail line 90 characters or fewer. Use the rewrites in section 3 for 03, 09 and 12 as written, then apply the same rules to the rest.
2. Language rules (section 4) in article bodies, longest copy first: 03, 09, 10, 12, 13, 02, 06, 01.
3. Cohesion and figure-relation items (sections 5–6) for 03, 09, 10 and 12. Captions state the test set where a figure reports one.

Do not:
- Change any number, interval or headline. If an edit would change a number, stop and write `OPEN_QUESTIONS.md` beside this message.
- Cite or add any PyVRP gap value. The routing table conflict is unresolved.
- Apply P1 copy changes unless they are needed to keep a sentence accurate under item 2 (P1 is not approved as a whole).
- Make hosted calls, git mutations, or deploys. Do not touch `.env`, permissions or config.
- Hand-edit generated files. Regenerate them with their scripts (`gen_story_short.py`, `gen_static_registry.py`, `gen_route_manifest.py` where relevant).

Gates after each project:
- `uv run python scripts/lint_story_language.py`
- `uv run python scripts/check_docs.py`
- `uv run python scripts/check_short_copy.py --check`
- `uv run python scripts/gen_story_short.py --check`
- `uv run python scripts/check_headline_numbers.py`
- `cd apps/showcase-web && npm test && npm run lint && npm run build` after any change to roadmap rendering or copy.

At the end: `uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps` and `uv run pytest -q`.

Write the report to `collaboration/reviews/20261119-p2-report/00-report.md`:
- one row per project: roadmap cards before and after (count, longest detail length), language edits, figure or caption edits, gate results you actually ran;
- every number you checked against its committed metrics file, with the file path;
- every item you could not finish, with an `OPEN_QUESTIONS.md` path.

Quote numbers exactly. Do not claim a gate passed unless you ran it.
