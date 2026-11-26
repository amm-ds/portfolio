# Wave 8 round 3 — closeout fix list

Status: issued by the design lane (Claude) on 2026-11-26, after review of `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round3/closeout-kimi.md`. Revision 2 (2026-11-26): corrected after Opus's review of the first version and of Kimi's fix plan. Changes from revision 1 are marked **[rev 2]**.

Scope: fix only the items below. Do not change anything else. No commit, push, merge or stash. HEAD stays `c05accd0`. Projects 01 and 15 stay untouched. No experiments, training or paid or hosted model calls.

## Required fixes

1. **Item 53 — "X; next, the…" transitions.** Turn these into full sentences in every story. **[rev 2]** Counts (grep `; next, the`): 06 (6), 07 (6), 08 (6), 09 (5), 10 (5), 11 (3), 12 (6), 02 (1, `projects/02-demand-forecasting/story.yaml:86`), 03 (1, `projects/03-anomaly-detection/story.yaml:51`). Total 39 = 37 + 2. Projects 04, 05 and 13 already show zero. Re-count with grep before and after, and report the per-project numbers. Example: `projects/08-inference-serving/story.yaml:222`, `projects/06-routing-optimization/story.yaml:209`.

2. **Items 24 and 46 — Conclusions restructure.** **[rev 2]** Project 01 has no `## Results summary` heading. Its gold order is Taught → Limits → Exact numbers → Measured alternatives → Protocol. Apply that pattern to 03 and 12:
   - Project 03 (no Alternatives section): remove the standalone `## Results summary` heading (`story.yaml:156`) and fold its content into the top of "What the experiment taught". Target order: Taught → Limits → Exact numbers → Protocol. Protocol (:229) must come after Limits.
   - Project 12 (no Alternatives section): same treatment for its Results summary (:303). Target order: Taught → Limits → Exact numbers → Protocol.
   - **Keep the `**In plain terms:**` card as the last paragraph block of Limits.** The lint rule `_check_summary_card` in `lint_story_language.py` raises an error if the card is not the final block of its section. Moving Limits earlier must not leave the card in the middle.
   - Project 03 Limits, around :280: the sentence "The final diagram connects these limits…" becomes false once Limits moves earlier. Reword it.
   - Only `#sec-conclusions` is linked from outside (03:149, 12:297, 01:182), so no anchors change.
   - Re-run `lint_story_language.py` after the move.

3. **Forecast Workbench protocol wording.** In `apps/showcase-web/src/demos/forecast-workbench/ForecastWorkbench.tsx` lines 423–428, the "experiment" block says the earlier 0.60/0.10/0.30 blend was chosen on 9 selection origins. `demo_payload.json` `evaluation_metadata.split` records `n_selection: 2`. Change to: the earlier blend used 2 selection origins; the current champion used 9. `staticRegistry.ts` does not mirror the sentence. Confirm with `gen_static_registry.py --check`, and regenerate only if it differs.

4. **Project 03 "real incidents".** `projects/03-anomaly-detection/story.yaml:226` and the `threshold_sweep` caption at :328 read "17 of 120 flags hit real incidents". Change to "injected anomalies" in both places. **[rev 2]** Keep the tail "not 17 distinct anomalies" if present, or make it consistent with the new wording. This string appears only in `story.yaml`.

5. **Routing orphan (`apps/showcase-web/src/diagrams/routing.ts`, `04-routing`).** **[rev 2]** Deleting the file would break the TypeScript build and three test files: `diagrams/index.ts:12,21,58`, `__tests__/FlowDiagram.test.tsx`, `__tests__/diagramSpecs.test.ts`, `__tests__/FlowDiagramImportFailure.test.tsx`. Keep the smaller change instead: correct the stale 0.9020 at `routing.ts:35,53` to 0.9061, as stated in `opus-round3/04-nlp-classification.md:163` (fresh holdout, τ = 0.5). Leave the registration and the tests unchanged. Record in the closeout that this spec is a test fixture and is not embedded in any story.

## Closeout corrections

6. **[rev 2]** Edit `opus-round3/closeout-kimi.md` at the exact lines:
   - :10 "All 57 handoff findings have a final disposition below." Replace with: 57 handoff items were addressed, and list the items not done.
   - :26 "FIXED — APPROVED FALLBACK". Replace with: "fallback taken; owner sign-off pending".
   - :38 "Results summary folded into lessons". False until fix 2 is done. Make it match the actual state.
   - :121 items 24 and 46 as done. Keep only if fix 2 is done.
   - :138 item 53 as FIXED. Keep only if fix 1 is done.
   - Do not close the owner sign-off point for the project 02 fallback.

7. Add the missing evidence: the baseline cheap-gate output taken before any edit, and a change table (file, line, old, new) for every edit in this pass.

## Gates to run after fixes

Run the cheap gates: `gen_static_registry.py --check`, `gen_story_short.py --check`, `gen_route_manifest.py --check`, `lint_story_language.py`, `check_headline_numbers.py`, `check_short_copy.py --check`, `check_docs.py`, `check_demo_contract.py`, `ruff check`, `ruff format --check`, `git diff --check`.

Then run the full set, which the round-3 review did not run: `uv run pytest --cov`, `npm test`, `npm run lint`, `npm run build`, `mypy` (libs, projects and apps, per `AGENTS.md`), and `mkdocs build --strict`.

**[rev 2]** Record an exit code for every gate in both `collaboration/reviews/20261126-wave8-round3-closeout-fixes/01-kimi-report.md` and `closeout-kimi.md`.

## Owner decision still open

Project 02 fallback sign-off: the owner must approve the earlier-blend disclosure before the closeout can say approved. Do not close item 6 on this point.

## Revision 3 (Opus)

Third review, 2026-11-26. Fixes 2–5 and 7 are verified. Fix 1 is not complete.

8. **Fix 1 follow-up (Kimi).** 38 of the 39 replacements read ". Next, the X ([Section →](#sec-…))." and have no main verb. Rewrite each as a full sentence, for example "Next, the Data section lists the 56 pinned test days and their references ([Data →](#sec-data))." Lines: 02:86; 06:55,95,126,209,242,276; 07:91,130,154,223,259,285; 08:93,127,155,222,250,270; 09:66,97,133,208,257; 10:73,104,134,188,215; 11:60,91,279; 12:65,101,135,214,260,296. `03:51` is already a full sentence; leave it. Then re-run `lint_story_language.py`, `check_short_copy.py --check`, `gen_story_short.py --check`, `git diff --check`, record exit codes, and set item 53 in `closeout-kimi.md` to FIXED only after that.
9. **Optional (Kimi).** The section-intro lines of the form "Next, the X ([Objectives →](#sec-objectives))." at 05:19, 03:22, 08:59, 09:32, 12:28, 06:19, 13:31, 10:49, 07:52, 11:19 have the same verbless shape. They predate fix 1 and were not in its scope; fix them in the same pass if the owner wants consistency.
10. Closeout corrections made by Opus in this revision: :10 points to a real "Open items" list; :14 says owner sign-off pending; item 53 set to OPEN; `routing.ts` test-fixture note added under project 04; item 46 reference corrected to the exact-number table at `projects/12-tabular-ml-lifecycle/story.yaml:354`.
