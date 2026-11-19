# Message for Kimi: next wave (owner approved W1, W2, W4, W5, W6, W9 on 2026-11-18)

You are executing the approved next-wave items. Read first:
1. `collaboration/designs/20261118-next-wave/00-next-wave-plan.md`
2. `collaboration/reviews/20261117-sota-research/14-research-deltas-2026-11-18.md`

Approved items, in this order: W1, W2, W4, W5, W6, W9. Do not run W3, W7, W8, W10, W11 or W12 (not approved; W7 and W8 also need a cap). For W9, read the table only; do not change any PyVRP numbers unless the table check settles the mismatch and the owner approves the change.

Hard limits (same as the overnight brief):
- No git mutations (no add, commit, push, branch, stash, reset). The owner commits.
- No deploys. No changes to `.env`, permissions or config.
- Hosted model calls only where an approved cap says so.
- No full M5 panel rerun. Do not change the 360 px per-row minimum. Do not add `quality_quant` to `DOCS_FIGURES`. Do not compute the NAB official score.
- Do not hand-edit generated files; regenerate them with their scripts.
- Do not edit committed records under `projects/*/data/` in place.

Stop and write `OPEN_QUESTIONS.md` beside the item's handoff if: a handoff's stop condition applies, a gate fails twice, spend reaches $4, or a decision is not recorded.

Gates after each item: `uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps`, `uv run pytest -q`, the showcase-web gates (`npm test`, `npm run lint`, `npm run build`), and the `scripts/` checks listed in the overnight brief. Do not claim a gate passed unless you ran it.

Write a morning report at `collaboration/reviews/20261118-next-wave-report/00-report.md`: one row per item with status, files changed, commands run, gate results, and open questions. Quote numbers exactly.
