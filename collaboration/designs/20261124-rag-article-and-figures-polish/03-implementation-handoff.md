# Implementation Handoff: RAG 01 Article, Figures, Diagrams & Honest Provenance Polish (Wave 6.5C)

Date: 2026-11-24
Designer: Claude Code + Neon Reviewer
Executor: Kimi Code
Status: **approved (ready for Kimi execution on a new branch from `main`)**
Source Reviews:
- `collaboration/reviews/20261124-rag-article-deep-review/00-review.md` (Opus deep review)
- `collaboration/reviews/20261124-rag-deep-article-audit/00-review.md` (Neon deep audit)

---

## 1. Objective

Elevate `projects/01-rag-agent/` to publication-grade **5/5 quality** (serving as the validated gold template before rolling out the same structure, 8-rule style guide, and neutral roadmap pattern across `02–13`) by completing four coordinated tracks:
1. **Honest judge provenance** across every copy surface (`story.yaml`, `README.md`, `docs/projects/01-rag-agent.md`, `cardCopy.ts`, `ITERATION_TRACKER.md`).
2. **Regenerate & fix visuals/diagrams** (`retrieval_ladder`, `final_outcome`, `failure_taxonomy`, `verify_funnel`, plus `01-rag-pipeline` and `auto-01-rag-agent-1..4`), and remove the 4 stranded tuning figures from `evaluation` and `conclusions`.
3. **Deepen & polish the narrative** using Opus's **8-rule style guide** + the `[opening intro & description -> diagram -> mid paragraph + bullets/table -> **In plain terms:** -> figures]` rhythm (no `[Next: ...]` links inside cards; left scroll-spy rail handles section navigation).
4. **Align `README.md`, `docs/projects/01-rag-agent.md`, and `DESIGN.md`** with the committed `S3` + `final_v3` architecture and numbers.

Zero hosted LLM calls, zero paid APIs, and no changes to `projects/01-rag-agent/src/rag_agent/*.py` logic or committed evaluation JSONs. Kimi never commits, pushes, or merges.

---

## 2. Scope & Affected Files

### In Scope
- `projects/01-rag-agent/story.yaml` (prose, `short_version` if trimmed for provenance honesty, `figures:` lists, `figure_captions:`)
- `projects/01-rag-agent/README.md`, `projects/01-rag-agent/DESIGN.md`, `docs/projects/01-rag-agent.md`
- `projects/01-rag-agent/src/rag_agent/figures.py` & `projects/01-rag-agent/scripts/build_final_figures.py` + regenerated `reports/figures/*.json` & `docs/assets/**` via `scripts/export_readme_figures.py`
- `apps/showcase-web/src/diagrams/ragPipeline.ts` (`01-rag-pipeline`) and `apps/showcase-web/src/diagrams/auto/01-rag-agent-{1..4}.ts` (or regenerated via `scripts/mermaid-to-flow.mjs` — check tests in `diagramSpecs.test.ts` and `mermaidToFlow.test.ts`)
- `apps/showcase-web/src/lib/cardCopy.ts` (sync `01-rag-agent` provenance wording) + `apps/showcase-web/src/__tests__/ProjectsIndex.test.tsx` (only if `cardCopy.ts` test assertions match updated provenance string)
- Generated snapshots via scripts: `staticRegistry.ts`, `storyShort.ts`, `route_manifest.json`

### Out of Scope
- Do **not** alter `projects/01-rag-agent/story.yaml` `roadmap:` (5 neutral cards already approved) or `RoadmapBlock.tsx`.
- Do **not** edit `projects/02–13` yet (wait for owner review of `01-rag-agent` closeout before rolling out).

---

## 3. Ordered Implementation Steps

### Step 1: Accurate Judge Provenance Across Public Copy
`owner_sample.json` and `owner_sample_validated.json` on `main` now hold the 30 owner-labelled items (`11 supported, 19 unsupported`): labelled blind to Kimi's model labels, with 7 passage-level discrepancies reviewed and accepted against `chunk_text` during the reviewer audit.
- Update wording across `story.yaml` (`short_version`, `evaluation`, `conclusions`), `README.md`, `docs/projects/01-rag-agent.md`, and `cardCopy.ts`:
  - Remove stale `"owner hand-label pending"` everywhere.
  - State cleanly: `"30/30 owner-labelled sample (blind to model labels; 7 items reconciled against passage text with reviewer audit)"` (or concise `"30/30 owner-labelled"` in tight card slots, with the 7-item reconciliation note in `evaluation`/`conclusions`).
  - Keep `short_version <= 280` chars (`gen_story_short.py --check` + `check_short_copy.py --check`).

### Step 2: Regenerate Figures & Update Diagrams
1. **Figures (`projects/01-rag-agent/src/rag_agent/figures.py` & `build_final_figures.py`):**
   - `retrieval_ladder`: Use **distinct colors** for `R0` (baseline) vs `S3` (promoted hybrid) in both panels, clear legend, and annotate metric definitions (`chunk_exact` on `final_v3` vs article-level on dev splits).
   - `final_outcome`: Fix title, subtitle wrapping, and `FP` label clarity.
   - `failure_taxonomy`: Add crisp value labels and updated title (`n = 120`).
   - `verify_funnel`: Clarify `"share of claims kept (95.8%)"` and layout.
   - Re-export PNGs via `uv run python scripts/export_readme_figures.py` (`check_figure_budget.py` & `check_figure_axes.py` must stay green).
2. **Diagrams (`apps/showcase-web/src/diagrams/`):**
   - `01-rag-pipeline` (`ragPipeline.ts`): Update nodes/edges/facts to reflect **S3** (title-anchored chunks, dense FAISS + BM25 RRF fusion, cross-encoder rerank `6×k`, per-article cap `2`, `recall@5 0.946` on `final_v3`, `p50 16.5 s`, `faithfulness 0.872`, `refusal 24/28`).
   - `auto-01-rag-agent-1`: Clarify `Relevant passage in corpus?` node reflects agent search + abstention rather than a pre-search lexical cutoff (`0.0`).
   - `auto-01-rag-agent-2`: Update `ev` node from `"65 tuning, 55 sealed"` to `"65 tuning, 55 gate, 120 final_v3"`.
   - `auto-01-rag-agent-3`: Update `tuning-j` and `gate-g` to reflect `judge_v2` (30/30 owner-reviewed audit) + `final_v3` (120 questions, read 4×; RAGAS on tuning pass).
   - `auto-01-rag-agent-4`: Update title to `"RAG Agent — Final pass results"` and `s15` node to `120 final_v3` (not 55-question set).
   - Verify `npm test -- diagramSpecs mermaidToFlow` passes!
3. **Remove Stranded Figures:**
   - Remove `latency_histogram`, `kimi_generation_comparison`, `fusion_arm_comparison` from `evaluation: figures:` and remove `retrieval_funnel` from `conclusions: figures:` (they remain on disk as tuning artifacts, not stranded in final-pass sections).

### Step 3: Deepen & Refine `story.yaml` Using the 8-Rule Style Guide
Apply Opus `00-review.md §7.1, §7.3, §8, §9` + Neon `00-review.md §6`:
1. **Metric & jargon definitions at first use:**
   - Define `F1`, `recall@5` (`chunk_exact` on `final_v3` vs article-level on dev splits), `all-articles@5` (all gold articles for a multi-hop question appear in top 5), `RRF (k=60)` (rank-based fusion needing no learned weights), and `"mechanical checks"` (`verify.py:check_claim_spans`: verbatim substring, numbers, dates/months, negation polarity) *before* quoting their counts.
2. **Real tension & worked trace (human-like narrative):**
   - Add **one real worked question trace** from `reports/final_v3_e2e/question_traces_heldout.json` (verify exact trace text and `claim_states` before quoting!).
   - Tell the **representable-refusal schema bug** story cleanly (`README.md:184-203`: before making refusal valid output, unanswerable queries searched until the token cap; fixing the schema resolved 6/6 unanswerable stress rows).
   - Add `Unsupported answers: none stated -> 1 / 120` to `objectives` Target vs Result table; clarify stress C's `10/30` (`27` verifier failures) in `conclusions`.
3. **8-rule discipline & lint safety:**
   - Vary bullet shape (not all `**Label:** claim, reason`), eliminate repeated words (`every`, `never`, `honest`), cut redundant restatements of `F1 0.9091` across middle sections, keep `[Next: ...]` omitted inside `**In plain terms:**`, keep `background <= 145` words, every section `< 540` words, and sentences crisp (`Flesch >= 45` on all main sections -> `lint_story_language.py` **0 errors, 0 warnings**).

### Step 4: Cohesive Secondary Surfaces (`README.md`, `docs/projects/01-rag-agent.md`, `DESIGN.md`)
- `README.md`: Clarify `final_v3` read-count disclosure at top, keep earlier stress/tuning history compact in table rows (`G8`).
- `docs/projects/01-rag-agent.md`: Update headings (`Key results` rather than `(selected kimi-for-coding)`, `Superseded grounding configuration` at `:179`), fix `65 graded questions` -> `120 final_v3 + prior 65/55`, and ensure embedded PNGs match regenerated `reports/figures/`.
- `DESIGN.md`: Fix `5 × top_k` (`:64`) -> `6 × top_k` (`params.yaml:68`), add BM25+RRF+cap+verify to architecture summary, and clean up stale `§Wave 14/16` references (`:215-216`).

---

## 4. Verification Gates (All Must Pass)

```bash
uv run python scripts/gen_static_registry.py
uv run python scripts/gen_story_short.py
uv run python scripts/gen_route_manifest.py
uv run python scripts/lint_story_language.py        # 0 errors, 0 warnings
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
uv run pytest -q projects/01-rag-agent
cd apps/showcase-web && npm test && npm run lint && npm run build
```

Write closeout to `collaboration/reviews/20261124-wave65c-rag-article-and-figures/00-closeout.md` and stop without committing.
