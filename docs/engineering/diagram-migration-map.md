# Mermaid diagram audit — migration map (66 diagrams, 13 stories)

Audit date: 2026-11-05. Method: every ```mermaid block in `projects/*/story.yaml`
(66 blocks, all block-scalar encoded) rendered with the site's own pipeline
(headless Chromium + `mermaid/dist/mermaid.min.js` + `MERMAID_THEME` from
`apps/showcase-web/src/components/mermaid-theme.ts` — the same input
`apps/showcase-web/scripts/render-diagrams.mjs` and the runtime fallback use).
Renders inspected
as PNG at natural size in `/tmp/diagram-audit/png/`.

Readability basis: pre-rendered SVGs scale to the story prose column
(`.story-layout` grid: 200px rail + fluid column ≈ 1000–1180px on desktop,
collapsing narrower), so natural width ≫ column shrinks the 20px theme font.
Diagrams wider than ~1900px render under ~11px effective; wider than ~2300px
under ~9px. Defect classes checked: clipped/cramped labels, extreme aspect
strips, awkward TB poles, dead space, wrong glyphs.

Library column: mermaid-forever = static mermaid stays; react-flow =
interactive React Flow treatment would add material value.

## Verdict counts

- FIXED (source edited, SVG regenerated, defect verified gone): 9
- REPLACE-CANDIDATE (left as-is, flagged for the React Flow pilot): 3
- KEEP (no change): 54

## Per-diagram verdicts

### 01-rag-agent (5)

| section | verdict | reason |
|---|---|---|
| background | FIXED — mermaid-forever | 2327×301 one-row chain shrank to ~6.5px text; rebuilt as two stacked LR subgraph rows (921×726), funnel kept as "top 15 passages, then top 3"; prose "from the left" → "from the top". |
| objectives | FIXED (minor) — mermaid-forever | 1821×455 decision flow is borderline-acceptable at column width; edge label "no - outside the corpus" → "no: outside the corpus". |
| data | KEEP — mermaid-forever | 975×271, clean lineage chain at natural size. |
| evaluation | KEEP — mermaid-forever | 1061×331 reads fine; tall thin "Sealed set" node is cosmetic only. |
| conclusions | FIXED (minor) — mermaid-forever | 1863×572 verify/repair loop reads acceptably; SP diamond wording trimmed to "0.6 support floor vs cited chunk?". Also a react-flow candidate if phase 2 wants the loop interactive. |

### 02-demand-forecasting (6)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 1153×280 six-node chain, legible; unbalanced wrapping cosmetic. |
| objectives | FIXED — mermaid-forever | Non-branching "Stability screen" step was drawn as a huge decision diamond (glyph error, 1715×417); now a box — 1467×310. |
| data | KEEP — mermaid-forever | 589×280 three-stage contract, natural size. |
| training | KEEP — mermaid-forever | 1299×250 ensemble screen chain, legible. |
| evaluation | KEEP — mermaid-forever | 949×280 WRMSSE pipeline, fine. |
| conclusions | KEEP — mermaid-forever | 787×310; single-"yes" diamond is a deliberate scope gate. |

### 03-anomaly-detection (4)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 1311×345 detector pipeline, legible. |
| objectives | KEEP — mermaid-forever | 1441×211 flat strip, but ~13px at column width; relayout experiments (TB stack) read worse — reverted. |
| data | KEEP — mermaid-forever | 1478×296 NAB window split, legible. |
| conclusions | FIXED (minor) — mermaid-forever | 1935-wide adoption chain kept LR (TB became a 1798px pole); node wording trimmed ("clear +0.05 and transfer"). |

### 04-nlp-classification (5)

| section | verdict | reason |
|---|---|---|
| background | REPLACE-CANDIDATE — react-flow | Keyword/transformer routing topology; a static 1308px cascade reads okay, but live split shares + threshold interactivity would add real value. |
| objectives | KEEP — mermaid-forever | 1393×331 ladder; 11-line judge node is awkward but legible. |
| data | KEEP — mermaid-forever | 977×344 biased-sample split, clear. |
| evaluation | KEEP — mermaid-forever | 1312×464 router cascade + high-value side flow; tall "Full-data model" node cosmetic. |
| conclusions | KEEP — mermaid-forever | 1141×220 five-node summary chain, fine. |

### 05-ml-pipeline-churn (5)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 1594×517 cycle+holdout; TB relayout became a 1598px pole — reverted. |
| objectives | KEEP — mermaid-forever | 1141×160 cost-model chain, fine. |
| data | KEEP — mermaid-forever | 757×344 split diagram, fine. |
| evaluation | KEEP — mermaid-forever | 1046×337 holdout evidence; tall resample node cosmetic. |
| conclusions | FIXED — mermaid-forever | 10-node pipeline as a 1611×224 strip (~8px text); rebuilt as vertical two-track TB (493×694) with the same 10 stages. |

### 06-routing-optimization (5)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 1059×301 problem→plan flow, fine. |
| objectives | KEEP — mermaid-forever | 1100×345 contract→validator→scoring, fine. |
| data | KEEP — mermaid-forever | 769×423 registry merge, fine. |
| evaluation | KEEP — mermaid-forever | 839×451 criteria→ships; "~1 s" wrap cosmetic. Solver×instance matrix would suit a table/heatmap, but the diagram itself is healthy. |
| conclusions | KEEP — mermaid-forever | 1479×241 solver ladder; single-row progression is the meaning. |

### 07-open-data-mobility (4)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 1290×495 sources→panel→forecast, legible. |
| objectives | KEEP — mermaid-forever | 1208×495 train/test split, legible. |
| data | KEEP — mermaid-forever | 769×374 panel build, fine. |
| conclusions | KEEP — mermaid-forever | 1250×558 zone-class router, legible. |

### 08-inference-serving (5)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 1616×318 serving pipeline ≈14px at column; TB stack became ~1000px tall — left as-is. |
| objectives | KEEP — mermaid-forever | 769×310 cell-metrics chain, fine. |
| data | KEEP — mermaid-forever | 1461×599 prompt→envelope→scoring; dead space inside the envelope subgraph is cosmetic (mermaid ignores `direction` once a subgraph links to an outside node). |
| training | KEEP — mermaid-forever | 745×344 rung ladder, fine. |
| conclusions | KEEP — mermaid-forever | 1187×375 evidence regen, fine. |

### 09-agentic-workflows (7)

| section | verdict | reason |
|---|---|---|
| background | REPLACE-CANDIDATE — react-flow | THE agent graph: park/resume self-loop, repair-cap loop, critique revise loop — 2205×544 (~9px text) with crossing loop labels. Step-through interactivity is the real fix; static relayout can't tame it. |
| objectives | FIXED — mermaid-forever | 1887×241 flat strip (aspect 7.8, ~10px text); task/checks subgraphs stacked TB (902×600), inner LR kept. |
| data | KEEP — mermaid-forever | 1205×271 corpora→grading, fine. |
| eda | FIXED — mermaid-forever | 1996×582 three sources feeding the graders (~10px text); stacked TB (1131×1072), inner LR kept. |
| training | REPLACE-CANDIDATE — react-flow | Human-checkpoint loop (1878×392) — approve/reject/park cycle plus repair cap; same interactive case as background, plus a clipped "retries exhausted" label at the bottom edge. |
| evaluation | KEEP — mermaid-forever | 878×494 record→graders, fine. |
| conclusions | KEEP — mermaid-forever | 638×400 I→G→O chain, fine. |

### 10-uplift-experimentation (4)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 1087×314 send-decision flow, fine. |
| objectives | KEEP — mermaid-forever | 1637×331 anchor→scores→judging; borderline width but ~13px at column — acceptable. |
| data | KEEP — mermaid-forever | 1153×335 frames→roles, fine. |
| conclusions | KEEP — mermaid-forever | 1106×344 decision mirror of background, fine. |

### 11-data-engineering (6)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 1065×583 dataset×engines fan-out, legible. |
| objectives | KEEP — mermaid-forever | 527×659 gate→measures, natural size. |
| data | KEEP — mermaid-forever | 601×637 projection fan-out, fine. |
| eda | KEEP — mermaid-forever | 360×479 two EDA pairs, fine. |
| evaluation | KEEP — mermaid-forever | 744×839 cell→gate, natural size; "1e-5" wrap cosmetic. |
| conclusions | FIXED — mermaid-forever | 10-task suite as a 1920×100 strip (aspect 19, ~40px tall at column); rebuilt as three LR subgraph rows — reads/transforms/writes (744×561). |

### 12-tabular-ml-lifecycle (4)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 921×271 six-stage pipeline, fine. |
| objectives | KEEP — mermaid-forever | 741×676 two gates→slices, natural size. |
| data | KEEP — mermaid-forever | 769×498 split fan-out, fine. |
| evaluation | KEEP — mermaid-forever | 927×262 test-window chain, fine. |

### 13-model-serving (6)

| section | verdict | reason |
|---|---|---|
| background | KEEP — mermaid-forever | 937×250 re-derive→ship chain, fine. |
| objectives | KEEP — mermaid-forever | 745×250 four-gate chain, fine. |
| data | KEEP — mermaid-forever | 838×301 feature contract, fine. |
| eda | KEEP — mermaid-forever | 552×374 parity gate, fine. |
| training | KEEP — mermaid-forever | 1018×344 backend-flag router, legible — small enough that interactivity adds little. |
| conclusions | KEEP — mermaid-forever | 744×190 numbers chain, fine. |

## SVG regeneration evidence

- At the audit, `node apps/showcase-web/scripts/render-diagrams.mjs` was run
  twice; the second run was all-unchanged, proving deterministic output.
- 9 SVGs were written for the 9 edited sources, and 15 missing current-hash
  SVGs for 11/12/13 were backfilled. The old hashes recorded here were valid
  at that audit date; later story edits changed the expected set again.
- **Cleanup follow-up (2026-11-07):** the renderer now resolves Playwright
  from `apps/showcase-web`'s declared development dependencies, reports stale
  hashes, and prunes them only with the explicit `--prune` flag. A fresh run
  found 57 current diagrams and removed exactly seven orphan SVGs:
  `0fc7cba7…`, `195dccbe…`, `35f825ee…`, `63a63610…`, `e45e591c…`,
  `f2b5eae2…`, and `f9f83318…`. No active diagram or app media was deleted.

## Renderer limitation worth encoding (lesson)

Mermaid ignores `direction LR` inside a subgraph when any of its nodes link
to a node outside the subgraph (also triggered by chains like
`SCORE --> OUT`). Audited TB relayouts that depended on inner directions
silently became vertical poles (up to 1931px tall). The two-row wins
(01 background, 09 objectives/eda, 11 conclusions) work because their
subgraphs connect subgraph-to-subgraph only.

## Phase 2 outcome — React Flow pilot (2026-11-05)

Shipped: `@xyflow/react` v12 viewer behind a new ` ```diagram <spec-id> ` fence
(lazy chunk, ~209 kB, main bundle unchanged). Pilots live on 09-agentic-workflows
(agent loop with budgets in the inspector) and 04-nlp-classification (routing
topology with τ, escalation rate, fresh macro-F1). Mermaid keeps its lane for
docs-style flows; Plotly keeps all data figures.

Follow-up candidates from the pilot: 02's routing architecture, 11's benchmark
harness flow, 13's serving topology (React Flow); deployment-architecture pages
(D2, only if a Go build step is ever accepted); 03's sensor graphs (Cytoscape,
when a network-analysis story exists). Polish item: auto-height canvases for
single-rank topologies.
