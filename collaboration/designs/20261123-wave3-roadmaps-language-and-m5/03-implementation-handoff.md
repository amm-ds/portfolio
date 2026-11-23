# Implementation handoff: Wave 3 — Standardized Roadmaps, Language Pass & Demand Forecasting (`02-demand-forecasting`) Erratic-Series Investigation

Date: 2026-11-23
Designer: Claude Code
Executor: Kimi Code
Status: approved for execution (100% local, zero hosted LLM calls)
Branch: `phase0-infra-2026-11-22`
Source design: `collaboration/designs/20261123-portfolio-release-roadmap/01-master-plan.md`

## Objective

1. **Standardized Ad-Hoc Roadmaps (All 13 `projects/*/story.yaml`):**
   Unify all 13 experiments around the 5-card lifecycle progression (`Data` → `Training` → `Evaluation` → `Production/Serving` → `Next`), keeping `01-rag-agent`'s already-updated roadmap as the template.
   - Contract (`docs/engineering/repo-conventions.md:18-24`): 4 `shipped` + 1 `next`, titles 3–6 words verb-first, no metric in title, detail <= 90 chars with one number or decision.
2. **Language & Projects-Page Card Pass (`projects/*/story.yaml`, `README.md`, `docs/projects/*.md`, `apps/showcase-web/src/lib/cardCopy.ts`):**
   - Polish prose across projects 02–13 for clarity, variety, and engaging technical storytelling (fixing any repetitive phrasing or em-dash clause joins; keeping every number traceable to `reports/metrics.json` or `README.md`).
   - Update `cardCopy.ts` (`CARD_DOES`, `CARD_ACHIEVES`) for any project whose numbers or descriptions improved (especially `02-demand-forecasting`).
3. **Demand Forecasting (`02-demand-forecasting`) — Erratic-Series Investigation & Headline Reconciliation:**
   - The working tree already has updated `reports_m5_full/{metrics.json,evaluation_metadata.json}` (10 origins, 30,490 series: `convex_ensemble` `official_wrmsse = 0.6211`, `erratic_routed` `0.6235` rejected).
   - Investigate targeted improvements on the 2,288 erratic dense series (`ADI < 1.32, CV2 >= 0.49`) — e.g., Tweedie power / Huber / asymmetric loss, intermittent/erratic stratified blending weights, or spike-lag / calendar features — scored **on the 9 selection origins first**; only promote/score on the 1 test origin if the selection screen improves without regressing pooled WRMSSE (`0.6211`) or zero-day accuracy.
   - Update `projects/02-demand-forecasting/{README.md,story.yaml}`, `docs/projects/02-demand-forecasting.md`, and `apps/showcase-web/src/lib/cardCopy.ts` to match the committed `reports_m5_full/metrics.json` (`0.6211` or improved winner), clearing the 2 `check_headline_numbers.py` drift findings.

## Affected surfaces

- `projects/02-demand-forecasting/` (challenger evaluation + `README.md`, `story.yaml`, `reports_m5_full/demo_payload.json` if updated)
- `projects/{03..13}-*/story.yaml` (roadmap + language polish)
- `docs/projects/*.md`, `README.md`, `docs/projects/index.md` (via `gen_story_short.py` / `check_short_copy.py`)
- `apps/showcase-web/src/lib/cardCopy.ts`, `storyShort.ts`, `staticRegistry.ts`
- `collaboration/reviews/20261123-wave3/00-closeout.md` (new)

## Gates & Close-out

Run from repo root:
```bash
uv run python scripts/gen_story_short.py
uv run python scripts/gen_static_registry.py
uv run python scripts/lint_story_language.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_headline_numbers.py
uv run python scripts/check_docs.py
uv run python scripts/check_demo_contract.py
```
And in `apps/showcase-web`: `npm test && npm run lint && npm run build`.
Write `collaboration/reviews/20261123-wave3/00-closeout.md`. Do not commit.
