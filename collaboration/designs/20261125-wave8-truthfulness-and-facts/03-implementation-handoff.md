# Implementation Handoff — Wave 8: Truthfulness, Facts, Diagrams & Roadmaps (Projects 02–13)

Date: 2026-11-25
Designer: Claude / Antigravity
Executor: Kimi Code
Base branch: `main` @ `c05accd0`
Execution branch: `wave8-articles-truthfulness-2026-11-25`
Source reviews: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/02..13.md`

---

## Objective

Resolve every verified truthfulness, factual, roadmap, diagram, and language defect identified in the 12 Opus Round-2 reviews (`projects/02`–`13`) while preserving the `e69bba84` presentation standard (single hero diagram + 3-step intro walkthrough, uniform inline backtick tagging in prose, clean minimal-tag tables, closing section transitions, and everyday plain-English `**In plain terms:**` cards).

**Non-negotiable evidence rule:** Do NOT accept or reject any review claim on faith. Before editing a number, formula, protocol detail, or roadmap card, open the committed source artifact (`reports/metrics.json`, `reports/*.json`, `src/**/*.py`, `params.yaml`, `apps/showcase-web/src/diagrams/**/*.ts`) and verify the ground truth directly.

---

## Priority Order (Execute Strictly in This Sequence)

### Tier 1 — False or Contradicted Claims (P0)
Fix every false/contradicted statement in `story.yaml` (including plain-terms overclaims introduced in `e69bba84`), `README.md` / `docs/projects/*.md` / `cardCopy.ts` if the same claim appears there:

1. **`02-demand-forecasting`** (`opus-round2/02-demand-forecasting.md`):
   - Fix selection protocol wording (`2` origins vs `9` origins — verify against committed `m5_full.py` / `reports_m5_full/`).
   - Fix feature list (L124: `"7/14/21/28-day rolling means"` vs actual lags/rollings in `m5_track.py`).
   - Fix `next` roadmap card (must be an open next step, not a misstated past Huber failure).
   - Fix diagram weights in `apps/showcase-web/src/diagrams/` where contradicted by code.
2. **`03-anomaly-detection`** (`opus-round2/03-anomaly-detection.md`):
   - Fix contradicted `"Pages still miss incidents about half the time, but that miss rate roughly halves"` (verify exact range precision/miss rates in `reports/nab_sweep.json` / `nab_metrics.json`).
   - Fix false `shipped` roadmap card `"The showcase demo replays committed alerts"` — no anomaly demo exists in `apps/showcase-web`; replace with a true shipped milestone from committed artifacts.
3. **`04-nlp-classification`** (`opus-round2/04-nlp-classification.md`):
   - Fix `"At most +0.001"` vs actual `+0.003` (verify against `reports/llm_cascade.json` / `metrics.json`).
   - Reconcile `"lifting accuracy slightly"` / `"nudges it to 95.4%"` in plain-terms cards with the `"no measurable change"` CI framing.
   - Fix the two wrong roadmap cards (`Keep the default under inconclusive tuning` and `Ship the cascade with calibrated confidence`) against `reports/hpo_*.json` and `reports/llm_cascade.json`.
4. **`05-ml-pipeline-churn`** (`opus-round2/05-ml-pipeline-churn.md`):
   - Fix training set size (`5,634` trained rows, not `7,043` total panel rows — verify exact split sizes in `reports/metrics.json` / `train.py`).
   - Fix stale CI labels in `apps/showcase-web/src/diagrams/` for project `05`.
5. **`06-routing-optimization`** (`opus-round2/06-routing-optimization.md`):
   - Fix `"8 plans undercut"` vs `5 of 56` (verify exact count in `reports/metrics.json`).
   - Fix fleet-first `"more trucks"` / `0.07%` trade-off wording against committed `alns_fleet` vs `alns` metrics.
6. **`07-open-data-mobility`** (`opus-round2/07-open-data-mobility.md`):
   - Fix Bronx-only and sign errors against committed `reports/` files.
   - Fix plain-terms overclaim `"90.8% coverage holds in busy zones"` (verify exact slice/overall coverage in `reports/metrics.json`).
   - Trace or remove all 12 unsourced numbers flagged in the review.
7. **`08-inference-serving`** (`opus-round2/08-inference-serving.md`):
   - Fix dense/MoE (`gpt-oss`) factual error against `data/bench_run.json` / `reports/metrics.json`.
   - Fix `"Nothing is downloaded, so no license applies"` (prompts are local; models are downloaded under their own licenses).
   - Fix dimensionally wrong electricity cost formula (cost divides by `tok/s`, not multiplies).
   - Remove overclaims in the new plain-terms cards.
8. **`09-agentic-workflows`** (`opus-round2/09-agentic-workflows.md`):
   - Fix `"52 captured calls"` contradiction and `"95% of tasks"` `p95` explanation for `n = 15`.
   - Fix `cost_latency_bars` attribution for local-model latency misses (verify which split the chart actually plots).
9. **`10-uplift-experimentation`** (`opus-round2/10-uplift-experimentation.md`):
   - Fix all five factual errors flagged in `opus-round2/10-uplift-experimentation.md`.
   - Replace `"net profit"` with `"revenue minus send cost"` everywhere (including the Section `07 Results` table, `background`, and `**In plain terms:**` cards — COGS and contact fatigue are excluded).
10. **`11-data-engineering`** (`opus-round2/11-data-engineering.md`):
    - Remove or source the unsourced EDA claims (including `"rush-hour"` added in `e69bba84`) and the three unsourced numbers flagged in the review.
11. **`12-tabular-ml-lifecycle`** (`opus-round2/12-tabular-ml-lifecycle.md`):
    - Fix `"No global bias"` (residuals average `+9.2` — verify in `reports/metrics.json`).
    - Fix season mislabels and the correlated-pair feature-selection description (`feature_selection` keeps vs prunes which member — verify in `src/`).
12. **`13-model-serving`** (`opus-round2/13-model-serving.md`):
    - Fix batch `p50` column wording (holds means, not medians — verify in `reports/metrics.json`).
    - Fix `"three orders"` claim.
    - Add the standardized-space qualification to `1.2e-04` everywhere it appears.

### Tier 2 — Mislabelled Numbers, Captions & Diagrams
- Fix every mislabelled figure caption, table header, and diagram spec (`apps/showcase-web/src/diagrams/**/*.ts`) flagged across all 12 `opus-round2/*.md` reviews.
- Keep `apps/showcase-web/src/lib/staticRegistry.ts`, `storyShort.ts`, and `route_manifest.json` regenerated if any `short_version`, `figures`, `metrics_keys`, or `story.yaml` metadata changes.

### Tier 3 — Style, Language & Plain-Terms Integrity
- Preserve the `e69bba84` structure: 1 hero diagram + 3-step intro walkthrough, uniform inline backtick tagging in prose, clean minimal-tag tables, closing transitions (`[Section →](#sec-<id>)`), and jargon-free `**In plain terms:**` cards — **strictly truthful** to the committed artifacts.
- Keep every section `>= 45` Flesch reading ease, `background <= 150` words, and `lint_story_language.py` at **0 errors, 0 warnings**.

---

## Required Gates (All Must Pass)

```bash
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
uv run python scripts/lint_story_language.py
uv run python scripts/check_headline_numbers.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
uv run python scripts/check_demo_contract.py
uv run mkdocs build --strict
uv run ruff check . && uv run ruff format --check .
uv run mypy libs projects apps
cd apps/showcase-web && npm test && npm run lint && npm run build
```

---

## Closeout & Stop Rules

- Write a per-project verification closeout to `collaboration/reviews/20261125-wave8-truthfulness-and-facts/00-closeout.md` listing, for each project `02`–`13`, every Opus Round-2 finding, the exact committed file/key checked, and the fix applied (or evidence-backed refutation).
- Leave `projects/15-dynamic-pricing-rl/` and `projects/01-rag-agent/` untouched.
- **Do NOT commit, push, or merge.** Stop cleanly on `wave8-articles-truthfulness-2026-11-25` for owner + Claude verification before merging to `main`.
