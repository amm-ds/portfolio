# Close-out: Wave 1C (RAG 01 docs, story & card) + Wave 2 (UI light-mode green, disclaimer & copy)

Date: 2026-11-23
Executor: Kimi Code
Handoff: `collaboration/designs/20261123-wave1c-rag-docs-and-wave2-ui/03-implementation-handoff.md`
Branch: `phase0-infra-2026-11-22`. Zero hosted LLM calls. No commits, no
pushes, no merges; project 02 untouched.

## Part 1 — Wave 1C: RAG 01 documentation, story, and card

`projects/01-rag-agent/story.yaml`:
- `short_version` rewritten (276 chars, under the 280 cap): S3 hybrid
  retrieval at 0.946 recall@5, judge calibrated 30/30 blind, final
  120-question pass F1 0.909 / precision 0.952 / faithfulness 0.872 /
  1/120 unsupported.
- `roadmap`: 4 `shipped` + 1 `next` on the Data → Training → Evaluation →
  Production → Next arc (verb-first titles, details ≤ 90 chars).
- `training`: opens with the promoted S3 design (title-anchored chunks,
  dense + BM25 RRF k=60, rerank, per-article cap 2) and the final_v3 ladder
  result (0.9457 vs 0.9239 recall@5; multi-hop 0.8333 vs 0.7917); the
  65-question sweep is reframed as the prior tuning baseline; the code
  excerpt now shows the real fused `search` path.
- `evaluation`: judge_v2 validation added (30/30 owner blind sample, Wilson
  [0.8865, 1.0], clearing the 0.85 gate; the earlier ~44% miss rate stays as
  history); the finalized 120-question pass summarized (F1 0.9091, bounded
  agent loop, $2.04 cumulative).
- `results` and `conclusions`: finalized pass table added (F1/precision/
  recall/accuracy/faithfulness/taxonomy/slices/judge agreement/spend);
  "measured alternatives" now records the S3 promotion and the judge_v2
  supersession; limits restated as final-state debt (10/92 empty-answers,
  4 rail stops). Earlier 65/55/stress/B numbers are labeled prior baselines.

`README.md`, `docs/projects/01-rag-agent.md`, root `README.md` projects row,
and `docs/projects/index.md` row: updated with the S3 design, judge_v2
validation, the final_v3 results table, and the verbatim new `short_version`
(all four short-copy surfaces now match). `DESIGN.md`: 2026-11-23 entry
appended (S3 promotion, judge_v2, Phase E close-out).
`apps/showcase-web/src/lib/cardCopy.ts`: `CARD_DOES` / `CARD_ACHIEVES` /
`CARD_TAGS` for 01-rag-agent updated to the finalized numbers.
`storyShort.ts` and `staticRegistry.ts` regenerated.

## Part 2 — Wave 2: UI

- **Light-mode green alignment**: new semantic tokens in
  `tokens-base.css` — `--card-accent`, `--btn-accent-bg`, `--btn-accent-ink`.
  Light theme: card left borders and clickable accent buttons (global
  `button` incl. Send inquiry / Unlock, `.demo-banner-cta`) use `#0f766e`
  (`--accent-bright`) with `#ffffff` button text (AA). Dark theme unchanged
  (`#2dd4bf` + `#042f2e`). Wired into `pages.css` (button, `.contact-form`),
  `demos.css` (`.demo-banner-cta`, `.wb-notice`), `demos-workbench.css`
  (two accent left borders). Non-button accent fills (progress bars,
  sliders, scrollbar, roadmap dots) intentionally keep `--accent`.
- **Contact disclaimer** (`ChannelCards.tsx`): reduced to the crisp notice
  "Share your email or phone to unlock; requests are logged for ~30 days
  (request deletion)." — retention note and deletion mailto preserved;
  "This is not a security boundary" and the field enumeration removed.
- **Copy polish**: `Home.tsx` go-link casing/dash alignment; `About.tsx`
  lead-role bullet tightened. All factual claims and links intact.
- **Test contract updates** (copy changes broke two hard-coded assertions):
  `ChannelCards.test.tsx` (new disclaimer text + link name) and
  `ProjectsIndex.test.tsx` ("F1 0.909", new first strong
  "120-question sealed pass", new tag list).

## Part 3 — Gates (verbatim)

Repo (from repo root):
- `lint_story_language.py` → `13 stories — 0 errors, 1 warning`
  (warning: 01-rag-agent evaluation section 660 words vs the 550 soft
  budget; warning-level only, exit 0)
- `check_short_copy.py --check` → `short copy is single-sourced (39 surfaces across 13 stories)`
- `check_docs.py` → `check-docs: OK`
- `gen_story_short.py --check` → `story short map is current`
- `gen_static_registry.py --check` → `static registry is current`
- `check_headline_numbers.py` → `11 claims checked, 2 finding(s)` — both the
  pre-existing `02-demand-forecasting` `0.6211` drift (present on main,
  untouched per handoff). **Zero findings on 01-rag-agent, zero new
  findings anywhere.**

Web (`apps/showcase-web`):
- `npm test` → **56 files / 753 tests passed**
- `npm run lint` → clean
- `npm run build` → built

## Files (uncommitted; Claude reviews, validates, commits)

- `projects/01-rag-agent/{story.yaml, README.md, DESIGN.md}`
- `docs/projects/01-rag-agent.md`, `docs/projects/index.md`, root `README.md`
- `apps/showcase-web/src/lib/cardCopy.ts`, `storyShort.ts`, `staticRegistry.ts`
- `apps/showcase-web/src/styles/tokens-base.css`, `pages.css`, `demos.css`,
  `demos-workbench.css`
- `apps/showcase-web/src/components/ChannelCards.tsx`,
  `pages/Home.tsx`, `pages/About.tsx`
- `apps/showcase-web/src/__tests__/ChannelCards.test.tsx`,
  `__tests__/ProjectsIndex.test.tsx`

## Notes for the commit pass

1. The evaluation-section word warning (660 vs 550) is soft; a future edit
   can move the finalized-pass paragraph into `results` if the warning
   bothers the report.
2. `02-demand-forecasting` `0.6211` headline drift remains the owner's
   pre-existing item (project 02 untouched here).
