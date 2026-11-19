# P2 report: language and roadmap pass (+ H9 heading slash)

Date: 2026-11-19
Handoff: `collaboration/designs/20261119-p2-language-roadmap/00-kimi-message.md`
Rules: `collaboration/reviews/20261119-gap-analysis/01-language-and-roadmap-pass.md` §2–§7
Open items: `collaboration/designs/20261119-p2-language-roadmap/OPEN_QUESTIONS.md`
H9 (separate): `collaboration/reviews/20261119-h9-report/00-report.md`

## What changed

**Schema** — `libs/portfolio-core/src/portfolio_core/story.py`: `RoadmapItem` is now
`{status: shipped|next|blocked, title (≤60 chars), detail (≤90 chars)}` (was
`delivered|remaining|deferred` + free text ≤300). Core tests updated
(`libs/portfolio-core/tests/test_story.py`), including a new 90-char detail cap test.

**Web** — `apps/showcase-web/src/api.ts` (`RoadmapItemData` type + `isStory`
validator), `src/components/RoadmapBlock.tsx` (shipped milestones keep the
horizontal timeline with the title as label and `title + detail` as hover text;
`next`/`blocked` cards now render visibly below the timeline as a tagged list —
previously hidden as "authoring state"), `src/styles/tokens-base.css` (pending
list styles, `.shipped` dot selector), `src/__tests__/RoadmapBlock.test.tsx` and
`src/__tests__/ProjectDetail.test.tsx` rewritten to the new shape (pending items
asserted visible).

**Stories** — all 13 `story.yaml` roadmaps rewritten (3–4 shipped + 1–2
next/blocked, ≤5 cards, detail ≤90 chars, schema-enforced); language rules §4/§7
applied to 03, 09, 10, 12, 13, 02, 06, 01 (finding-first leads, question-first
openings for 02/03/12, decision-first endings, metric-named numbers, "proves"→
"measured", >35-word two-number sentences split, caveats beside numbers);
cohesion/figure items §5/§6 for 03/09/10/12 (limits in one bullet format —
10 converted; captions state metric + test set; 03 `threshold_sweep` caption
gained "test-window"; 09 `node_waterfall` caption corrected — no retry segments
render; 12 `residual_heatmap` color meaning corrected — red = over-forecast).

**Template/docs** — `scripts/new_project.py` STORY_YAML roadmap block and
`docs/engineering/repo-conventions.md:18` now describe the new card spec;
`scripts/gen_static_registry.py` stale "300-char cap" comment corrected to 90.

**Regenerated** — `gen_story_short.py` → `storyShort.ts`; `gen_static_registry.py`
→ `staticRegistry.ts`; route manifest already current.

## Per-project summary

Roadmap counts are `cards (shipped+next/blocked), longest detail`. "Numbers" are
the values written into new/edited copy, each verified against the committed
file listed.

| # | Roadmap before → after | Language / cohesion edits | Numbers verified against |
|---|---|---|---|
| 01 | 5 delivered, longest 178 → 5 (4+1), longest 72 | 4: question opening; denominators paragraph split with metric names; "prove"→"measure"; CI sentence split | 593, recall@5 0.831, $0.000906/query, 15→55, 9 of 11, 0.733 [0.567, 0.867], 5/30, 0.633 — `reports/metrics.json`, `reports/sealed_retrieval.json`, `reports/figures/eda_corpus_composition.json` |
| 02 | 6, longest 280 → 5 (4+1), 63 | 8: question opening; metric named beside WRMSSE 0.6161 / 0.350 / zero-day 66.6% vs 57.3% (×4 spots); decision-first ending | 30,490; 3-of-6, mean+1.0×std; 28 days; 66.6%/57.3%; 2 origins — `reports_m5_full/evaluation_metadata.json`, `reports_m5_full/metrics.json` |
| 03 | 7, longest 285 → 5 (3+2), 67 | 5: question opening; "proves"→"does not show"; results lead finding-first; CI sentence split; threshold_sweep caption += "test-window" | 66→35, recall 0.604, F1 0.533 — `reports/nab_sweep.json`; negative-result verdict — `reports/nab_refinement.json`; 0.527 [0.230, 0.811], 2,000, 42, 0.804/0.228 [0.081, 0.401]/0.944, 897 — `reports/nab_metrics.json`, `reports/figures/nab_timelines.json`; tune-surface (0.5%, 24 h, +0.05, +0.010) — `reports/nab_tune.json` |
| 04 | 5, longest 103 → 5 (4+1), 59 | roadmap only (not in B/C lists) | 0.9460, 0.1000, 0.2533 — `reports/metrics.json`; CI [−0.0048, +0.0204] — `reports/selection.json`; ECE 0.0360→0.0227, 37% — DESIGN.md/README.md only (see OPEN_QUESTIONS §8) |
| 05 | 6, longest 99 → 5 (4+1 blocked), 78 | roadmap only | 7,043 — `docs/data-registry/telco-churn.md`; 25 trials — `params.yaml`; 2,000, CI excludes zero, 0.250→0.150, 3→8 — `reports/sensitivity.json` |
| 06 | 5, longest 79 → 5 (4+1), 67 | 6: question opening + finding-first; "130 seconds of runtime"; one-definition gap; runtime↔solver mapping; decision-first ending | 42 — DESIGN.md:139 + `reports/results.md`; 8 solvers, 0.12 points, k=1, 12.0 s tie — `reports/metrics.json`; 100 customers — `reports/solutions.json`; headline CI [3.22, 5.28] restored — `reports/metrics.json` |
| 07 | 5, longest 88 → 5 (4+1), 78 | roadmap only | 41.2M — `reports/dq_validated.md`; −4.1% — `reports/metrics.json`; 90.8%/84.7% — `reports/figures/p90_calibration.json`; 337,080 — `reports/green_transfer.json`; drift — `reports/drift/*.json` |
| 08 | 5, longest 87 → 5 (4+1), 57 | roadmap only | 8 prompts — `data/prompts.json`; 19 cells, 0 failures — `reports/metrics.json`; 760 — `data/bench_run.json` |
| 09 | 7, longest 133 → 5 (4+1), 66 | 2: t15 sentence split (31.1 s; 7,709/862 tokens); node_waterfall caption corrected (no retry segments; median on 15-task suite) | 13/13 — `reports/kimi-for-coding/metrics.json`; 52 calls — `reports/metrics.json`; four graders — `src/agentic_workflows/evals.py`; 18.2 s, 31.1 s — `reports/metrics.json` + recomputed from run records |
| 10 | 5, longest 151 → 5 (4+1), 65 | 5: metric named beside $16,103; two conclusion sentence splits; "outcome panel" singular; 7 captions gained metric + test-set frame; limits converted to bullets | +0.68 pp, 3,063, 21,306, ≈$0.30 — `reports/report.html`; five-fold, top-25%, DR/IPW spans — `reports/metrics.json`; 64,000, 42,613 — `reports/metrics.json`; caption numbers — `reports/figures/*.json`, `reports/demo_payload.json` |
| 11 | 5, longest 153 → 5 (4+1), 69 | roadmap only | 39 cells, 5 repeats, 1,658 trips, slopes 0.31–0.76 / 0.98–1.09, 10M — `reports/metrics.json`, `reports/evaluation_metadata.json` |
| 12 | 5, longest 216 → 5 (4+1), 82 | 4: question opening; "served model" defined once; results lead finding-first; decision-first ending; residual_heatmap color meaning + metric + test set; bootstrap_ci caption += metric + test set | 26 — `reports/dq_report.md`; 25.4/83.2 — `reports/metrics.json`; CIs exclude zero — `reports/results.md`, `reports/figures/bootstrap_ci.json`; caption re-verified — `reports/figures/*.json` |
| 13 | 5, longest 166 → 5 (4+1), 70 | 4: question opening; "prove"→"verify"; training lead finding-first; decision-first ending | 7.2e-07, 512, 1e-4, 4,320, 3 repeats — `reports/metrics.json`; 291 MB, 22.2× — `reports/docker_slim.json` |

## Coordinator corrections during integration (post-swarm)

The swarm diffed against HEAD, but several projects carried uncommitted
earlier-wave text; three "reverts to HEAD" I made from the diff alone clobbered
that text, and the gates caught two of them:

- **03 short_version**: restored to the earlier-wave text ("NAB (9 series): …
  One fit per series; no-skill = 16 seeded baselines…") — docs/projects
  (mtime 14:37, pre-swarm) already carry it; `check_short_copy` failed until
  restored. Not a swarm edit.
- **03 limits CI**: earlier waves had aligned the copy to the gate's rounding
  (`f"{0.2305:.3f}"` = `0.230`); restored `[0.230, 0.811]`.
- **06 headline CI**: the gate requires `3.22`/`5.28` in the story surface;
  restored as "(95 % bootstrap CI [3.22 %, 5.28 %] over the 56 instances)"
  beside the 4.23% headline in training (rule B6 placement).
- **10 body**: two agent edits had flipped committed `+69%` to `+70%` — both
  restored to `+69%` (B3 rewording kept). One out-of-scope `key_concepts` edit
  ("profit gaps"→"value gaps") reverted.
- **First-section word cap** (150): B7 question openings pushed 01/02/03/06/10
  over; trimmed each background by 2–20 words (no number changes) until the
  lint was clean. 06 conclusions: moved the new "What to do with this"
  paragraph above the `**Business summary:**` marker (summary-card placement
  rule).

## Unfinished / stopped items

All in `collaboration/designs/20261119-p2-language-roadmap/OPEN_QUESTIONS.md`
(8 sections): 03 threshold_sweep 115/14.8% vs committed 17/120; 06 "8
references" vs 5–6 negative gaps; 09 `short_version` live claims vs committed
5/6 metrics; 09 "8 unplanned calls" untraceable; 13 three unverifiable numbers
(15% lead / 3.3 GB / ~20% threshold); 10 profit_frontier.html $6,698 vs $6,838
and the +69/+70 tension; 12 mandated-text deviations (8-word title, headline in
card, dangling "research deltas" pointer); numbers traced only to design docs
(02, 04, 11).

## Gates actually run

After each integration step and finally whole:
- `lint_story_language.py` — 13 stories, 0 errors, 0 warnings.
- `check_docs.py` — OK.
- `check_short_copy.py --check` — OK (39 surfaces).
- `gen_story_short.py --check` — current.
- `check_headline_numbers.py` — 11 claims, 0 findings.
- `gen_static_registry.py --check` — current; route manifest — current.
- Web: `npm test` — 56 files, **753 tests passed** (three consecutive full
  runs; one earlier run showed a single order-dependent failure in
  App.test.tsx "renders the About page" title assertion — passed in isolation
  and in the three follow-up full runs; flagged as flaky, worth watching);
  `npm run lint` clean; `npm run build` succeeded.
- `ruff check .` — all checks passed; `ruff format --check .` — 773 files
  already formatted; `mypy libs projects apps` — no issues (233 files).
- `uv run pytest -q` (full repo) — **all suites pass, 97.70% total coverage**
  (one first-run failure: the committed OpenAPI golden
  `apps/showcase-api/tests/openapi.json` was stale after the RoadmapItem
  schema change; regenerated from `app.openapi()` — the diff is exactly the
  new `{status, title, detail}` shape — and the rerun is green;
  `apps/showcase-api` alone: 102 passed).

## Verification notes

- **Owner overrides applied 2026-11-19 (after the pass shipped):** (a) the
  web roadmap block renders `shipped` cards only — `next`/`blocked` remain in
  the schema and stories but are not rendered; the pending-list styles were
  removed again. (b) The heading gap between the section number and title is
  now a single literal space (removed the `.sec-num` `margin-right` that
  stacked on the JSX space and read as a double space); both article types
  verified. Web gates re-run after these: 753 tests, lint, build — green.

- Roadmap rendering verified at the component level (RoadmapBlock +
  ProjectDetail tests), at the API level (a temporary API on :8012 serves the
  new `{status, title, detail}` shape), and in the browser after the dev API on
  :8002 was restarted with the new schema: the story endpoint returns 200
  through the Vite proxy and the block renders as designed (03: 3-node shipped
  timeline + 2 `next` cards with tags and detail lines). The old API process
  had been started before the schema change and 500'd on every story — that was
  the "case study could not be loaded" error; restart was required and is now
  done.
- The `load_story` self-check in the swarm brief needed `Path(...)` (not
  `str`); every agent adapted it and reported `cards 5 over90 []`.
- 12's mandated rewrites total 6 cards; reconciled to the 5-card cap by
  merging the two foundation cards (details in OPEN_QUESTIONS §7 notes).
