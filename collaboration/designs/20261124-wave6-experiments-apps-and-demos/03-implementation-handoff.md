# Implementation handoff: Wave 6 (Refined / Opus-Aligned) — RAG Truth & Visuals, 13-Project Validation, Apps & Demo Sizing

Date: 2026-11-24
Designer: Claude Code (incorporating Opus Review `collaboration/reviews/20261124-orchestrator-review/00-review.md`)
Executor: Kimi Code
Status: **ready pending owner sign-off on Blockers D1 & D2** (zero hosted LLM calls)
Branch: `wave6-polish-2026-11-24` (from `main`)

## Owner sign-offs required before Kimi starts

1. **D1 (Judge calibration attribution):** Either (a) hand-label `reports/judge_calibration_v2/owner_sample.json` (V2) now, or (b) approve interim truthful wording (`"model labels audited 30/30 against passage text by a reviewer agent; owner hand-label pending"`) across `01-rag-agent` README/story/docs/`cardCopy.ts` (Task 1).
2. **D2 (Faithfulness CI):** Confirm updating `[0.7983, 0.9155]` → committed `[0.8092, 0.9304]` (`reports/final_v3_e2e/metrics.json`) after V1 offline re-aggregation confirms exact values (Tasks 2–3).
3. **D3–D11 (Scope approvals for Tasks 6, 7, 11–13):** Confirm:
   - `agent-chat` video/screenshot re-capture mode (`VITE_MOCK=1` with scripted caption vs local Ollama);
   - Deleting the 6 dead web PNGs + 6 orphan docs PNGs (Task 12);
   - Scrubbing `/Users/...` absolute home paths from `final_v3_file_access.json` and `02-demand-forecasting` report metadata (Task 13);
   - Rewriting the `02-demand-forecasting` erratic paragraph (`0.6235`, `+0.0025`, `57.2%`) and disclosing `final_v3` as consumed (new `final_v4` required for future RAG tuning).

## Ordered implementation steps (Tasks 1–15 from Opus Review §6)

### Part A — RAG 01 Truth Fixes, Headline Guard & Visualizations (Tasks 1–7)

1. **Task 1 — Fix judge-calibration attribution:** Update `projects/01-rag-agent/{README.md,story.yaml}`, `docs/projects/01-rag-agent.md`, and `apps/showcase-web/src/lib/cardCopy.ts` to either state the true audit attribution (`"audited 30/30 against passage text by a reviewer agent; owner hand-label pending"`) or record the owner's V2 hand-labels (`validated_by: owner`). Regenerate `storyShort.ts` (`scripts/gen_story_short.py`).
2. **Task 2 & 3 — V1 offline re-aggregation + Fix faithfulness CI:** Run `scripts/run_e2e_eval.py --summarize reports/final_v3_e2e` ($0), confirm exact match with `f1_summary.json` and `metrics.json` (`faithfulness.ci95 = [0.8092, 0.9304]`), and fix `[0.7983, 0.9155]` → `[0.8092, 0.9304]` in `projects/01-rag-agent/README.md:92`, `story.yaml:372`, and `docs/projects/01-rag-agent.md:84`.
3. **Task 4 — Extend `check_headline_numbers.py` to `01-rag-agent`:** Add extractors for `final_v3_e2e/f1_summary.json:f1` (`0.9091`) and S3 `recall_at_5` (`0.946`), remove `uncovered:01-rag-agent`, and add unit tests in `scripts/tests/test_check_headline_numbers.py`.
4. **Task 5 & 6 — Regenerate RAG 01 figures & static PNGs:**
   - Rebuild `failure_taxonomy` (`n=120`: `104/10/4/1/1`), `retrieval_ladder` (`R0/S1/S2/S3` across `dev_v1/dev_40/dev_65/heldout_55/final_v3` with Wilson whiskers), `final_outcome` (`TP/FP/TN/FN` + slices), and `verify_funnel` (`166 → 16 mech fail → 150 judged → 148 supported → 159 accepted / 7 dropped`).
   - Rewrite `story.yaml` captions (and fix the `fusion_arm_comparison` "not promoted" contradiction) and clearly label 65-tuning charts as development history.
   - Retarget `scripts/export_readme_figures.py` (`rag-quality-cost-frontier.png` + `DOCS_FIGURES["01-rag-agent"]`), re-export PNGs, and update `README.md` / `docs/projects/01-rag-agent.md`.
5. **Task 7 — Fix Project 02 erratic copy:** Update `projects/02-demand-forecasting/story.yaml` (and README/docs if mirrored) so the erratic paragraph states `0.6235` (`+0.0025` delta), `57.2%` zero-day accuracy, and notes the wave-34 early stop (`0.8683` vs `0.7409`).

### Part B — Apps & UI Polish: Remove Traffic-Light Dots, Demo Sizing & Media (Tasks 8–12)

6. **Task 8 — Remove `.terminal-dots` in all 3 apps:**
   - `apps/showcase-web/src/components/Terminal.tsx` (lines 3, 8–12) + `apps/showcase-web/src/styles/shell.css` (lines 178–201).
   - `apps/agent-chat/web/src/components/chat/ChatSurface.tsx` (lines 46–50) + `apps/agent-chat/web/src/styles.css` (lines 183–206).
   - `apps/document-intelligence/web/src/App.tsx` (line 25) + `apps/document-intelligence/web/src/styles.css` (lines 118–121, 364).
   - Verify `git grep -n "terminal-dots" apps` returns empty.
7. **Task 9 & 10 — Demo/Card & Workbench Sizing (Proposal A):**
   - Cap `.demo-grid` / `.project-grid` / `.study-card` container widths (`apps/showcase-web/src/styles/cards-grids.css`) so demo cards stay `<= ~570px` at `1920px`/`2560px` with no horizontal scroll at `375px`.
   - Bound `.demo-shell` and `.wb-*` chart widths (`apps/showcase-web/src/styles/{demos,demos-workbench}.css`) to `<= ~1,400px` at `2560px` while keeping `375px` mobile unchanged.
   - Verify visually via Playwright screenshots at `375, 768, 1280, 1440, 1920, 2560` (saved under gitignored `artifacts/`).
8. **Task 11 & 12 — Re-capture App Media & Delete Dead Media:**
   - Re-capture `agent-chat` (`*-v3.png`, `agent-chat-demo.{webm,mp4}`) and `document-intelligence` (`document-intelligence-{summary,qa}.png`) with the dot-free UIs, and sync `docs/assets/apps/*.png` (identical md5).
   - Delete the 6 dead web PNGs (`agent-chat-{ui,approval,memory}{,-v2}.png`) and 6 orphan docs PNGs (`docs/assets/projects/{01.../failure_taxonomy,02.../forecast_vs_actual,02.../metrics_bars,04.../epochs_probe,05.../cost_surface,11.../normalized_heatmap}.png`).

### Part C — Repo Hygiene, Compose & Em-Dash Pass (Tasks 13–15)

9. **Task 13 — Scrub `/Users/` home paths:** Update path writers in `projects/01-rag-agent/scripts/build_final_v3.py` and `02-demand-forecasting` report writers to emit repo-relative paths, and regenerate `final_v3_file_access.json` and `reports_m5*` metadata so `git grep -c "/Users/" -- projects` = 0.
10. **Task 14 — Env & Compose hygiene:** Add an anonymous `/app/apps/showcase-web/node_modules` volume to `web-dev` in `docker-compose.yml` so container `npm ci` does not overwrite host `arm64` `node_modules`, align healthcheck on `/ready`, and document the `arm64` Node requirement.
11. **Task 15 — Em-dash pass:** Replace `" — "` clause joins with colons/periods/parentheses on the top-offending docs (`projects/{06,04,02,11}-*/README.md`, `docs/projects/{09,01,10}-*.md`, `docs/apps/chatbot-agent.md`) to bring prose `" — "` counts under 8 per file.

## Gates & Close-out

Run the full verification suite from Opus Review §8 (`arm64` node `npm ci`, `ruff`, `mypy`, `pytest`, all 8 repo check scripts, `mkdocs build --strict`, `showcase-web` + `agent-chat` + `document-intelligence` tests/builds, and targeted `git grep` checks). Write `collaboration/reviews/20261124-wave6/00-closeout.md`. Do NOT commit or push.
