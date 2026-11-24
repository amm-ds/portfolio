# Architecture proposal: UI layout regression

Date: 2026-11-24
Designer: Claude Code
Status: draft
Source design brief: `collaboration/designs/20261124-ui-layout-regression/01-design-brief.md`

## Decision

Width belongs to the page shell, not to individual grids. `.app-main--fluid`
already sets the content width for every route (`tokens-base.css:240-248`).
The grids and the workbench inherit that width and do not cap or centre
themselves. Vertical size belongs to content: the workbench grid packs its
rows at the top instead of stretching them to fill the viewport.

## System shape

```text
.app-main--fluid (full width, 1.25rem side padding)
├── /projects
│   ├── .apps-grid     1 col → 2 cols @960px     (no cap)
│   ├── .project-grid  1 col → 2 cols @720px     (no cap)
│   └── .demo-grid     1 col → 2 cols @720px     (no cap)
│        └── .study-card__content                (no 70ch cap; .study-cols splits text)
└── /demos/*
    └── .wb-root  grid, 6 auto rows, align-content: start (no cap)
         ├── .wb-notice-strip  auto-fit columns, min(100%, 18rem)
         └── .wb-canvas-slot   inline height max(460, rail) → .figure-card min-height 460px
```

## Contracts and data ownership

- Public schemas or APIs: none.
- Internal types: none.
- Data and artifact ownership: CSS lives in `apps/showcase-web/src/styles/`;
  CSS-text tests read the concatenated manifest through
  `src/__tests__/helpers/css.ts` (`readStylesCss`).
- Generated files: none.

## Computed widths after the fix

Content width = viewport − 40px (side padding), scrollbar ignored; card gap
20px (`--gap-card: 1.25rem`, `tokens-base.css:19`).

| viewport | project / demo card (after) | Wave 6 card (now) | forecast chart column (after) |
|---|---:|---:|---:|
| 375 | 335 (1 col) | 335 | 335 (1 col, stacked) |
| 768 | 354 | 354 | 728 (1 col; ≤900px media) |
| 1,280 | 610 | 566, centred | 892 |
| 1,440 | 690 | 566, centred | 1,052 |
| 1,920 | 930 | 566, centred | 1,532 |
| 2,560 | 1,250 | 566, centred | 2,172 |

Chart column = content − 340px rail − 8px gap (`demos.css:300`, `:307`).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep the caps, left-aligned | Not full width; the owner asked for the pre-Wave-6 look |
| 3 columns at ≥1,800px | Reverses an owner decision and a locked test |
| Remove `min-height` from `.wb-root` instead of `align-content: start` | Also works, but the comment and tests treat the viewport-high workbench as intended; `align-content: start` keeps that and only stops row stretching |
| Container queries for the workbench | More moving parts; nothing here needs them |

## Failure modes and limits

| Failure or limit | Detection | Behavior |
|---|---|---|
| Very wide chart at 2,560px (about 4.7:1 at the 460px floor) | Screenshot at 2,560 | Acceptable for now; follow-up O2 |
| Empty space below the workbench on very tall screens | Screenshot at 2,560×1,440 | Free space now sits below the last row, not inside the cards |

## Migration and rollout

1. Edit the CSS rules in the handoff.
2. Extend two existing tests and add one.
3. Run the web gates, then capture screenshots at the listed widths.

## Observability and verification

- Tests: CSS-text assertions in `ProjectsIndex.test.tsx` and
  `ForecastWorkbench.test.tsx`.
- Manual or browser verification: screenshots at 375, 768, 1,280, 1,440,
  1,920 and 2,560px on `/projects`, `/demos/forecast-workbench`,
  `/demos/churn-sandbox`.

## Rollback

- Safe rollback point: `2a7d9b7a`.
- Data or state that rollback does not undo: none.

## References

- `collaboration/reviews/20261124-orchestrator-review/00-review.md` §4.3
- `collaboration/reviews/20261124-wave6/00-closeout.md`
