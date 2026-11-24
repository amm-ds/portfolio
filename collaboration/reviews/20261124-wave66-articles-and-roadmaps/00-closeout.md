# Wave 6.6 Closeout — Articles & Roadmaps Rollout (Projects 02–13)

- **Branch:** `wave66-articles-rollout-2026-11-24` (created from `main` @ `d6aef968`)
- **Scope:** `collaboration/designs/20261124-wave66-articles-and-roadmaps-rollout/03-implementation-handoff.md`, three batches (02–05, 06–09, 10–13), gold template `projects/01-rag-agent/story.yaml` @ `a66de659`
- **State:** all changes uncommitted in the working tree; no push, no merge. Ready for Claude review.
- **Zero hosted LLM calls** throughout (edits only; all gates local).

## What changed (all 12 stories)

Every project received the same four alignment passes, applied only where the
story deviated from the gold template:

1. **Card rename** — `**Business summary:**` → `**In plain terms:**` (8 occurrences per story), matching the 01 gold template. Linter accepts both markers; this is template alignment per §3.2.
2. **Closing transitions** — added a pre-card closing-transition paragraph in all 7 main sections of every story (84 total). Format follows 01: names the table/figures and links the next section with `([Section →](#sec-<id>))`. Next links sit **outside** the In-plain-terms cards everywhere. Wording varies by section; no new jargon terms introduced.
3. **Roadmap retitle** — all shipped/next titles converted to verb-first imperative, 3–6 words, trailing periods stripped. Details brought to ≤90 chars, ≤1 number, no internal IDs.
4. **Word-budget trims** — borderline sections (background ≤150 cap, training ≤550 soft budget) trimmed first so transitions stay net-negative or neutral: 02 bg 149→148, 03 bg 150→146 + training 550→548, 04 bg 148→149 (with transition), 05 bg 150→149, 06 bg 149→150→(final ≤150) + training 546→≤550, 07 bg 150→≤150, 08 bg 144→≤150, 09 bg 148→≤150 + training 550→≤550, 10 bg 150→≤150, 12 bg 145→≤150 (Flesch fixed to ≥45), 13 bg 135→≤150.

## Per-project changelog

### Batch A (02–05)

- **02-demand-forecasting** — cards renamed; background trimmed; 7 transitions added; roadmap retitled ("Pin the full M5 panel", "Screen one compact convex blend", "Score the blend once on test", "Publish the spike-capture negative result", next "Find erratic gains beyond routing"). Next-card detail de-jargonized to "Huber challenger lost its only selection origin and never reached test." **Traceability resolved:** the 0.8683 vs 0.7409 numbers trace to `reports_m5_full/erratic_challenger.json` (origin 1877, `n_origins_scored: 1`), so the results prose stays; only the roadmap carried the internal protocol id, now removed.
- **03-anomaly-detection** — cards renamed; background/objectives/data/eda/evaluation/results transitions added; training transition added net-zero (redundant fusion sentence cut); roadmap retitled ("Lock the event-aware evaluation contract", "Halve paged load with rank averaging", "Publish the detector-challenge negative result", "Ship the champion behind frozen thresholds", next "Re-run the headline on TSB-AD VUS-PR"). Time-relative "Current benchmark" detail → "TSB-AD VUS-PR is the modern reference score for this task." Multi-number detail (66→35 @ 0.604/0.533) → "Like-for-like paged load halves at equal recall."
- **04-nlp-classification** — cards renamed; 7 transitions; roadmap retitled + details de-numbered. **Traceability resolved:** the −0.0048 paired-CI bound is committed in `reports/risk_coverage/metrics.json` and `reports/selection.json` (not only story.yaml as the roadmap review suspected); details still slimmed to the style rule ("The paired confidence interval crosses zero; the default stays."). Time-relative "not stored today" → "Unlocks the paired cascade interval once rows are persisted."
- **05-ml-pipeline-churn** — cards renamed; 7 transitions; roadmap retitled ("Pin one reproducible panel and twin", "Choose the cutoff from OOF cost", "Price the served policy by bootstraps", "Re-freeze the cutoff as prices move", next "Gate rollout on owner data"). Over-number details reduced; blocked status preserved (card content is a rollout gate).

### Batch B (06–09)

- **06-routing-optimization** — cards renamed; 7 transitions; background + training trimmed to fund transitions; roadmap retitled ("Pin the benchmark and merge references", "Build the seeded, machine-checked solver ladder", "Tune search settings with seeded HPO", "Tie hinted CP-SAT to ALNS", next "Extend to larger Gehring-Homberger instances"). "today" → "only" in next detail.
- **07-open-data-mobility** — cards renamed; 7 transitions; background trimmed; roadmap retitled. **Untraceable numbers removed from roadmap:** "tested −4.1% better" → "tested better; the holdout has no vote" (−4.1% and 337,080 zone-hours live only in story/DESIGN/MODEL_CARD, not committed reports); "Green refit on 337,080 zone-hours wins" → "Green refit wins on its own history; drift months stay in-window."
- **08-inference-serving** — cards renamed; 7 transitions; background trimmed; roadmap retitled ("Standardize the task across all arms", "Commit the full measurement grid", "Catch a silent config error pre-run", "Re-derive every published value offline", next "Prove the values on shipping hardware"). "19 cells and 760 requests" detail → "760 requests across the grid on one quiet machine, zero failures."
- **09-agentic-workflows** — cards renamed; 7 transitions; background + training trimmed; roadmap retitled ("Pin typed outcomes and hard deadlines", "Bound retries behind a human checkpoint", "Replace AI judges with deterministic graders", "Audit captured calls against the plan", next "Run the multi-trial reliability study"). "current results are single runs" → "published results are single runs."

### Batch C (10–13)

- **10-uplift-experimentation** — cards renamed; 7 transitions; background trimmed (Flesch-safe); roadmap retitled ("Validate randomization and size the read", "Cross-fit three rankers on pre-treatment features", "Keep observed and estimated value separate", "Price the win against email costs", next "Decide the next live-campaign test"). Over-number details reduced to ≤1 number.
- **11-data-engineering** — cards renamed; **background intro bolded** (was plain — gold cadence); 7 transitions; roadmap retitled ("Gate every timing on identical rows", "Keep timings honest with untraced medians", "Catch dropped rows with parity checks", "Show the fast two scale sub-linearly", next "Benchmark real trips at 10M rows"). Multi-number details reduced.
- **12-tabular-ml-lifecycle** — cards renamed; 7 transitions; background trimmed and simplified (fixed a Flesch 44.8 regression mid-edit); roadmap retitled. **Closed-decision next card replaced with an open gate:** "Drop the external TabPFN-2 challenger route / Dropped by owner decision" → "Test challengers under the frozen-window protocol / A challenger must clear the same interval-on-gain gate first."
- **13-model-serving** — cards renamed; 7 transitions; roadmap retitled. **4,320 kept with context:** detail now "4,320 requests per backend finished with zero errors." (single number ≤ limit; derivation 300 req/cell × 3 repeats × 4 concurrency levels ≈ 3,600 + warm-up streams is not cleanly re-derivable from committed config, so no derivation claim is made — the number traces to `reports/metrics.json` and the story ledger). Internal-id details cleaned ("--backend flag" → "One flag switches the backend").

## Preserved strengths (not touched)

- All committed numbers, tables, figure lists, captions, key_concepts, metrics_keys.
- Concrete worked examples already in every story (02 top-units series; 03 nyc_taxi panel; 04 Business→Sci/Tech 25/250; 05 fairness slice counts; 06 C101 plan; 07 Midtown weekly trace; 08 Gemma4:31b panel; 09 t15 trace; 10 decile reads; 11 the 1,658 dropped N/A trips; 12 rush-hour residual clusters; 13 probe grid) — each traces to committed artifacts, satisfying the one-worked-example rule without new text.
- Figure narration: every `figures:` entry is referenced in its section prose (zero stranded figures) — verified while editing.
- README/docs copies: verified they carry no roadmap/card text (independent copy sourced from `short_version`), so no sync drift from these edits.

## Diagram alignment spot-check (§3.3)

Hand-built diagram specs (`apps/showcase-web/src/diagrams/*.ts`, 12 project specs) cross-checked against committed evidence (`reports/**`, README, story, DESIGN):

- All substantive numbers in specs resolve to committed artifacts. Two flagged items investigated:
  - `04-routing.ts` 4,477.8 items/s — story prose rounds to ~4,478; same value.
  - `09-agentLoop.ts` "400 requests and 4,000,000 total tokens per suite" — traces to `libs/portfolio-core/src/portfolio_core/config.py:36-37` (`LLM_MAX_REQUESTS=400`, `LLM_TOTAL_TOKENS_LIMIT=4_000_000`).
- No stale diagrams; no spec edits needed.

## Gate results (§4 suite, in handoff order)

| Gate | Result |
|---|---|
| `gen_static_registry.py` (plain + `--check`) | current |
| `gen_story_short.py` (plain + `--check`) | current |
| `gen_route_manifest.py` (plain + `--check`) | current (27 routes; only `generated_at` timestamp moved) |
| `lint_story_language.py` | **0 errors, 0 warnings** (13 stories) |
| `check_headline_numbers.py` | OK, 0 findings |
| `check_short_copy.py --check` | OK (39 surfaces) |
| `check_docs.py` | OK |
| `check_figure_budget.py` | OK (1 pre-existing warn: 03 telemetry_flags 594 KiB — identical on base) |
| `check_figure_axes.py` | OK (2 pre-existing warns: 01 retrieval_ladder yaxis — identical on base) |
| `check_demo_contract.py` | OK |
| `mkdocs build --strict` | built cleanly |
| `ruff check .` / `ruff format --check .` | all passed / 899 files formatted |
| `showcase-web`: `npm ci` → `npm test` | **754 passed** (npm ci needed: stale `@rollup/rollup-darwin-arm64`) |
| `showcase-web`: `npm run lint` | clean |
| `showcase-web`: `npm run build` | built in 8.01 s |

Batch-level gates (lint + headline + docs) were also run after each batch as the handoff requires.

## Notes for the reviewer

- Card rename (`Business summary` → `In plain terms`) is a style-alignment choice per §3.2; the linter accepts both markers, so this is template fidelity, not gate repair.
- Roadmap details deliberately drop numbers that live only in narrative prose (07) or that exceed the ≤1-number style rule; the numbers remain in story sections with their evidence tables.
- The 05 blocked-status roadmap card was kept as `status: blocked` (content is a rollout gate); only its title/detail were restyled.
- Nothing committed, pushed, or merged. Working tree contains the 12 story.yaml edits plus the route-manifest timestamp refresh from the required plain generator run.
