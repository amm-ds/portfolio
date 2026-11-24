# Implementation handoff: Wave 1C (Finalize RAG 01 Docs, Story & Card) + Wave 2 (UI Light-Mode Green, Contact Disclaimer & About/Projects Copy)

Date: 2026-11-23
Designer: Claude Code
Executor: Kimi Code
Status: approved for execution (zero hosted LLM calls)
Branch: `phase0-infra-2026-11-22`
Source design: `collaboration/designs/20261123-portfolio-release-roadmap/01-master-plan.md`

## Objective

1. **Wave 1C (Finalize Experiment 01 RAG Docs, Story, and Card):**
   Update `projects/01-rag-agent/story.yaml`, `projects/01-rag-agent/README.md`, `projects/01-rag-agent/DESIGN.md`, `docs/projects/01-rag-agent.md`, and `apps/showcase-web/src/lib/cardCopy.ts` (`"01-rag-agent"`) to reflect the finalized SOTA `S3` retrieval (`0.9457` recall@5, `0.8333` multi-hop recall@5, `0.8877` MRR@5), the owner-validated `judge_v2` calibration (`30/30 = 100%`, Wilson 95% `[0.8865, 1.0]`), and the `final_v3` 120-question end-to-end results (`F1 = 0.9091`, `precision = 0.9524`, `recall = 0.8696`, `faithfulness = 0.8717`, `1/120` unsupported-claim, `4/120` budget-terminated on unanswerable rows, `$2.04` total spend). Regenerate `storyShort.ts` and `staticRegistry.ts`.
2. **Wave 2 (UI Light-Mode Green Alignment, Contact Disclaimer & About/Home/Services/Projects):**
   - **UI Light-Mode Green:** In `apps/showcase-web/src/styles/`, align card left borders (`tokens-base.css`, `demos.css`, `demos-workbench.css`, `pages.css`, `story.css`) and clickable accent buttons (`Send inquiry`, `Unlock`, `.btn-primary`, `.demo-btn` / `.channel-unlock-row button`) in `:root[data-theme="light"]` to use the same contrast-safe `--accent-bright` (`#0f766e`) as light-mode text and components (with `#ffffff` button text for AA contrast in light mode, keeping dark mode's `#2dd4bf` + `--accent-ink` unchanged).
   - **Contact Disclaimer (`ChannelCards.tsx:152-157`):** Simplify the verbose 4-line privacy/security-boundary paragraph to a crisp 1–2 line notice.
   - **About, Home, Services & Projects Copy:** Polish `About.tsx` (and `Home.tsx`, `Services.tsx` if needed) for clear, engaging, aligned voice, and update `apps/showcase-web/src/lib/cardCopy.ts` so every card's description and results are accurate and engaging.

## Affected surfaces

- `projects/01-rag-agent/story.yaml`
- `projects/01-rag-agent/README.md`
- `projects/01-rag-agent/DESIGN.md`
- `docs/projects/01-rag-agent.md`
- `apps/showcase-web/src/lib/cardCopy.ts`
- `apps/showcase-web/src/lib/storyShort.ts` (regenerated via `scripts/gen_story_short.py`)
- `apps/showcase-web/src/lib/staticRegistry.ts` (regenerated via `scripts/gen_static_registry.py`)
- `apps/showcase-web/src/styles/tokens-base.css` (and `pages.css`, `demos.css`, `demos-workbench.css`, `story.css` as needed for light-mode `--accent-bright` alignment)
- `apps/showcase-web/src/components/ChannelCards.tsx`
- `apps/showcase-web/src/pages/About.tsx` (and `Home.tsx`, `Services.tsx` if alignment edits are needed)
- `collaboration/reviews/20261123-wave1c-and-wave2/00-closeout.md` (new)

## Ordered implementation steps

### Part 1 — Wave 1C: Finalize RAG 01 Documentation & Story

1. Update `projects/01-rag-agent/story.yaml`:
   - `short_version` (<= 280 chars, plain text): summarize the finalized RAG pipeline and its verified `final_v3` 120-question results (`S3` hybrid title-anchored retrieval `0.946` recall@5; `final_v3` `F1 0.909`, `precision 0.952`, `faithfulness 0.872`, `1/120` unsupported-claim, `4/120` budget-terminated).
   - `roadmap` (4 `shipped` + 1 `next`, titles 3–6 words verb-first, details <= 90 chars):
     1. `shipped`: Data — Pinned 593-article corpus and `final_v3` (120) / `judge_v2` (147) contracts.
     2. `shipped`: Training/Retrieval — Promoted `S3` hybrid title-anchored RRF + diversity cap (`0.946` recall@5).
     3. `shipped`: Evaluation — Validated judge (`30/30` blind sample); `final_v3` `F1 0.909`, `1/120` unsupported.
     4. `shipped`: Production — Wired soft tool-budget ceiling (`12/16/200k`), `verify` loop, and checkpointing.
     5. `next`: Cut `final_v3` false abstentions (`10/92`) and remaining `4` unanswerable rail stops.
   - Update `results` and `conclusions` sections (and `evaluation` / `training` where they describe the old `size`-only dense retriever or pre-Phase-E 0.44 judge failure) to report the finalized `S3` retrieval, `judge_v2` calibration (`30/30 = 100%`, Wilson `[0.8865, 1.0]`), and `final_v3` 120-question numbers (`reports/final_v3_e2e/f1_summary.json`, `reports/final_v3_e2e/metrics.json`), while keeping earlier 65-tuning / 55-heldout numbers clearly contextualized as prior baselines.
   - Remember `story.yaml` style rules: no em-dash clause joining (`check_docs` / `lint_story_language.py`), active present-tense evidence-led prose, every number traceable to a committed file.
2. Update `projects/01-rag-agent/README.md` and `docs/projects/01-rag-agent.md`:
   - Update the opening blockquote/summary, retrieval design (`chunk_mode: structure`, Dense-50 + BM25-50 RRF `k=60`, `ms-marco-MiniLM-L-6-v2` reranker, `max_per_article=2`), judge validation (`judge_v2`, `30/30` blind sample = `100%`), and add the `final_v3` 120-question results table (`F1 0.9091`, `precision 0.9524`, `recall 0.8696`, `accuracy 0.8667`, `faithfulness 0.8717`, `1/120` unsupported-claim, `10` empty-answer, `4` budget-terminated, `$2.0392` cumulative spend).
   - Keep `README.md` and `docs/projects/01-rag-agent.md` aligned with `story.yaml` `short_version` (remember `scripts/check_short_copy.py --check` checks that `short_version` appears verbatim in `README.md` and `docs/projects/01-rag-agent.md`!).
3. Append a concise changelog entry to `projects/01-rag-agent/DESIGN.md` summarizing the 2026-11-23 `S3` retrieval promotion, `judge_v2` validation, and `final_v3` Phase E completion.
4. Update `apps/showcase-web/src/lib/cardCopy.ts` (`"01-rag-agent"` in `CARD_DOES`, `CARD_ACHIEVES`, `CARD_TAGS`) to reflect the finalized `S3` + `final_v3` `0.909` F1 results.
5. Regenerate generated registries from repo root:
   ```bash
   uv run python scripts/gen_story_short.py
   uv run python scripts/gen_static_registry.py
   ```

### Part 2 — Wave 2: UI Light-Mode Green, Contact Disclaimer & About/Projects Copy

1. **UI Light-Mode Green Alignment (`apps/showcase-web/src/styles/`):**
   - Inspect `:root[data-theme="light"]` in `tokens-base.css` and all `border-left: ... var(--accent)` and primary/action button rules (`pages.css`, `demos.css`, `demos-workbench.css`, `story.css`, `cards-grids.css`).
   - Add semantic tokens in `tokens-base.css` (or update light-mode tokens/overrides) so that in light mode:
     - Card left borders (`border-left`) use `var(--accent-bright)` (`#0f766e`) — matching the light-mode green of text and components.
     - Clickable primary/action buttons (`Send inquiry`, `Unlock` / `.channel-unlock-row button`, `.btn-primary`, `.demo-btn--primary`, etc.) use `background: var(--accent-bright)` (`#0f766e`) and `color: #ffffff` (or a `--btn-accent-bg` / `--btn-accent-ink` token pair: `#2dd4bf` + `#042f2e` in dark mode, `#0f766e` + `#ffffff` in light mode).
   - Keep dark mode (`:root[data-theme="dark"]`) visually identical (`#2dd4bf` + `#042f2e`).
2. **Simplify Contact Disclaimer (`apps/showcase-web/src/components/ChannelCards.tsx:152-157`):**
   - Replace the 4-line privacy/security-boundary paragraph with a crisp, friendly 1–2 line notice:
     ```tsx
     Share your email or phone to unlock; requests are logged for ~30 days ({" "}
     <a href={deletionMailtoHref}>request deletion</a>).
     ```
     (Remove `"This is not a security boundary."` and the redundant field-by-field enumeration.)
3. **About & Projects Copy Review (`About.tsx`, `Home.tsx`, `Services.tsx`, `cardCopy.ts`):**
   - Read `apps/showcase-web/src/pages/About.tsx` (and `Contact.tsx`, `Services.tsx`, `Home.tsx`) and refine wording where verbose, repetitive, or misaligned with the rest of the site — keeping all factual claims and links intact.
   - Review `apps/showcase-web/src/lib/cardCopy.ts` (`CARD_DOES` / `CARD_ACHIEVES`) for clarity and consistency across cards (without inventing any numbers not in committed `metrics.json` / `README.md`!).

### Part 3 — Gates & Close-out

Run all touched gates and record verbatim outputs in `collaboration/reviews/20261123-wave1c-and-wave2/00-closeout.md`:

```bash
cd /Users/alejandro/work/portfolio
uv run python scripts/lint_story_language.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_docs.py
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_static_registry.py --check
uv run python scripts/check_headline_numbers.py
cd /Users/alejandro/work/portfolio/apps/showcase-web
npm test && npm run lint && npm run build
```

*(Note: `check_headline_numbers.py` currently has 2 pre-existing findings on `02-demand-forecasting` `0.6211` — verify zero findings on `01-rag-agent` and no new findings anywhere else.)*

Do NOT run `git commit`, `git push`, or modify `projects/02-demand-forecasting/`. Claude will review, validate, and commit.
