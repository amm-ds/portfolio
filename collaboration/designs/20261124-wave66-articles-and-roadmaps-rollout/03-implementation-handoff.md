# Implementation Handoff: Roll Out `01-rag-agent` Article, Diagram & Roadmap Standard to `02–13` (Wave 6.6)

Date: 2026-11-24
Designer: Claude Code
Executor: Kimi Code
Status: **ready for owner review / execution on a new branch from `main` after Wave 6.5C merge**
Validated Baseline: `projects/01-rag-agent/story.yaml` (Wave 6.5C) + `collaboration/reviews/20261124-rag-article-deep-review/00-review.md` §9 (8-rule style guide) + `collaboration/reviews/20261124-roadmap-review/00-review.md` §4.3–5.

---

## 1. Objective

Apply the exact editorial, structural, visual-alignment, and neutral-roadmap baseline validated on `01-rag-agent` across the remaining **12 portfolio projects (`02` through `13`)**:
1. **8-rule narrative & section flow:** `[opening intro & description -> diagram -> mid paragraph + bullets/table -> **In plain terms:** -> figures]` (no `[Next: ...]` links inside cards; scroll-spy rail handles navigation).
2. **Real worked example & definitions:** Define domain metrics and deterministic checks in plain English at first use, and include one concrete trace/case walk-through from a committed artifact per project.
3. **Diagram & figure alignment:** Verify each `auto-NN-*` / custom diagram matches the shipped architecture and committed metrics, and confirm every `figures:` entry is narrated in its section's prose (zero stranded or contradictory charts).
4. **Neutral 5-card milestone roadmaps (`§4.3`):** Imperative verb-first titles (3–6 words, no trailing period), plain-language `detail <= 90` chars (max 1 number or 1 decision, no internal IDs like `wave-34` or `origin 1877`), and clear `next` gate. Resolve the 4 roadmap-traceability items flagged in `20261124-roadmap-review/00-review.md §5`.

---

## 2. Batching Plan (Execute in 3 Clean Batches)

To keep context sharp and diffs easy to review, work in three 4-project batches, running `lint_story_language.py`, `check_headline_numbers.py`, and `check_docs.py` after each batch:
- **Batch A (`02`, `03`, `04`, `05`):** Forecasting (`02`: reconcile §5 roadmap numbers + `57.2%` copy), Anomaly Detection (`03`), NLP Classification (`04`), Churn ML Pipeline (`05`).
- **Batch B (`06`, `07`, `08`, `09`):** Routing Optimization (`06`), Open-Data Mobility (`07`), Inference Serving (`08`), Agentic Workflows (`09`).
- **Batch C (`10`, `11`, `12`, `13`):** Uplift Experimentation (`10`), Data Engineering (`11`), Tabular ML Lifecycle (`12`), Model Serving (`13`).

---

## 3. Per-Project Checklist

For each project `NN-*`:
1. Read `projects/NN-*/{story.yaml, README.md, reports/metrics.json}` (plus any primary `reports_*/metrics.json`) and its diagram specs in `apps/showcase-web/src/diagrams/`.
2. **Prose & 8-rule pass (`story.yaml`):**
   - Plain-English lead (`background <= 145` words), `**In plain terms:**` cards (`bi-card`), crisp sentences (`Flesch >= 45` on all main sections, every section `< 540` words, zero em-dash clause joins).
   - One concrete worked example per project traced to a committed artifact.
   - Move stale multi-pass tuning decimals into `conclusions -> ## Exact numbers` (`<details>`).
3. **Visuals & diagrams:** Ensure `figures:` in each section match that section's narrative; update any stale numbers in `apps/showcase-web/src/diagrams/`.
4. **Roadmap (`story.yaml`):** Verify 5 neutral cards (`4 shipped + 1 next`) with zero unbacked numbers or internal run IDs.
5. **Sync `README.md` and `docs/projects/NN-*.md`** where needed so headline metrics and limits agree 1:1.

---

## 4. Verification Gates (Full Suite Before Closeout)

```bash
uv run python scripts/gen_static_registry.py
uv run python scripts/gen_story_short.py
uv run python scripts/gen_route_manifest.py
uv run python scripts/lint_story_language.py        # 0 errors, 0 warnings across all 13 stories
uv run python scripts/check_headline_numbers.py     # 0 findings
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
uv run python scripts/check_figure_budget.py
uv run python scripts/check_figure_axes.py
uv run python scripts/check_demo_contract.py
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
uv run mkdocs build --strict
uv run ruff check . && uv run ruff format --check .
cd apps/showcase-web && npm test && npm run lint && npm run build
```

Write closeout to `collaboration/reviews/20261124-wave66-articles-and-roadmaps/00-closeout.md` and stop without committing.
