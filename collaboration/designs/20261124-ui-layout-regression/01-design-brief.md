# Design brief: UI layout regression (project cards and demo workbench)

Date: 2026-11-24
Designer: Claude Code
Owner: session owner
Status: draft
Related artifacts:
`apps/showcase-web/src/styles/cards-grids.css`,
`apps/showcase-web/src/styles/demos.css`,
commit `214cc041` (Wave 6, "fix wide viewports"),
`collaboration/reviews/20261124-orchestrator-review/00-review.md` §4.3,
`collaboration/designs/20261124-wave65-ui-and-rag-article-polish/01-design-and-handoff.md` §1
(earlier diagnosis, superseded by this brief for Track A).

## Problem

Two visible regressions arrived with Wave 6 (`214cc041`):

1. **`/projects` cards are centred, not full width.** The apps, experiments and
   live-demo grids now stop at 72rem (1,152px) and centre in the fluid page.
   Section titles, intros and the page index still span the full width, so on
   any screen wider than about 1,190px the cards sit in a narrower centred
   column with empty gutters. Before Wave 6 the grids filled the content width.
2. **The demo workbench pages (`/demos/forecast-workbench`,
   `/demos/churn-sandbox`) still size their cards badly on large screens.**
   The header, "more information" drawer, KPI band and notice strip grow into
   tall, mostly empty boxes on tall viewports. Wave 6 also centred the whole
   workbench in a 109rem (1,744px) column and raised the chart card's floor
   above the slot height that the component sets, which can clip the chart's
   footer.

I did **not** see the owner's screenshot. This analysis comes from the CSS,
the components, and the Wave 6 diff. The only `/demos/*` routes are the two
workbenches (`App.tsx:166-180`), so I read "the demos page" as those routes and
the "live demos" grid on `/projects` as part of item 1. If the owner meant only
the live-demos grid on `/projects`, item 1 still covers it.

## Context and evidence

| Claim or constraint | Evidence path | Why it matters |
|---|---|---|
| Wave 6 added `margin-inline: auto; max-width: 72rem;` to `.demo-grid` and `.project-grid`, and `margin: 0 auto 2rem; max-width: 72rem;` to `.apps-grid` | `git show 214cc041 -- apps/showcase-web/src/styles/cards-grids.css`; now `cards-grids.css:10-11`, `:223-224`, `:255-257` | Root cause of the centred cards |
| Wave 6 added `max-inline-size: 70ch` to `.study-card__content` | `cards-grids.css:50` | With the grid cap removed, this leaves a dead strip on the right of every wide card |
| The page shell has no width cap | `tokens-base.css:240-248` (`.app-main--fluid { max-width: none; … }`) | Headings span the full width; the capped grids do not |
| `.wb-root` is a 6-row `auto` grid with `min-height: calc(100dvh - 58px - 1rem)` and no `align-content` | `demos.css:293-316` | Grid's default `align-content: normal` stretches `auto` rows to fill the min-height, so header, drawer, KPI band and notice strip grow on tall screens. This predates Wave 6 (`7a408cee`) |
| Wave 6 added `max-width: 109rem; margin-inline: auto; width: 100%` to `.wb-root` | `demos.css:313-315` | Centres the workbench in a strip on 2,560px screens; inconsistent with the fluid shell |
| Wave 6 changed the chart card floor from `460px` to `clamp(400px, 48vh, 640px)` | `demos.css:479` | The slot's height is set inline to `Math.max(460, railH)` (`DemoWorkbench.tsx:134,177`) and the slot has `overflow: hidden` (`demos.css:463-469`). When `48vh` exceeds the slot height, the card is taller than its slot and the bottom (the readout band) is clipped. [inferred from code, verify in browser] |
| The notice strip is always two equal columns | `demos.css:441-445` | The forecast workbench renders one notice (`ForecastWorkbench.tsx:321`), leaving the right half empty; at 375px the churn sandbox squeezes two notices into ~160px columns |
| No test locks the Wave 6 caps | `grep -n "72rem\|109rem\|max-inline-size\|clamp(400px" src/__tests__` returns nothing | Removing them breaks no existing assertion |

## Goals and non-goals

Goals:

- Restore full-width apps, experiment and live-demo grids on `/projects`.
- Keep workbench rows at their content height on any viewport, with the
  workbench filling the page width.
- Size the notice strip to the number of notices and stack it on phones.
- Lock the fixed rules with CSS-text tests so the regression cannot return
  silently.

Non-goals:

- No change to the 2-column project grid (owner decision; the test
  `ProjectsIndex.test.tsx:315-325` forbids `repeat(3` in `.project-grid`).
- No TSX change. The canvas height logic in `DemoWorkbench.tsx:123-134` stays.
- No new breakpoints, no container queries, no redesign of card content.

## Constraints

- Repository conventions and gates: `docs/engineering/code-quality-guidelines.md`
  (smallest complete change). Web gates: `npm test && npm run lint && npm run build`.
- Compatibility: mobile layout at 375px must not change for the project grids.
- No hosted calls; no API needed (the projects page falls back to the static
  registry).

## Options

| Option | Strength | Cost or risk | Best when |
|---|---|---|---|
| A. Revert the Wave 6 grid caps and the 70ch cap; fix the workbench rows with `align-content: start`; remove the workbench cap; restore the 460px chart floor; make the notice strip auto-fit | Smallest change; restores the pre-Wave-6 look the owner asked for; fixes the stretched rows at the cause | At 2,560px each project/demo card is about 1,250px wide (two ~600px text columns), and the forecast chart is about 2,170px wide by 460–600px tall | The owner wants full-width cards (stated) |
| B. A, plus a 3-column `.demo-grid`/`.project-grid` at `min-width: 1800px` | Cards stay about 830px wide at 2,560px | Reverses the 2-column owner decision; breaks `ProjectsIndex.test.tsx:321`; 2 demo cards would leave an empty third track | Owner reverses the 2-column rule |
| C. Keep the caps but left-align them (`margin-inline: 0`) | Readable card width | Still not full width; leaves a large empty right side at 2,560px | Owner prefers bounded cards over full width |

## Recommendation

Option A. It removes the cause of both regressions and adds nothing new
except one `align-content` line and one auto-fit rule. It deliberately does not
solve the very wide forecast chart at 2,560px (about 4.7:1 at the 460px floor).
If the owner wants a taller chart on wide screens, the right place is the
height logic in `DemoWorkbench.tsx:134`, as a separate change.

## Acceptance criteria

- [ ] At 1,280, 1,440, 1,920 and 2,560px the `/projects` apps, experiment and
      live-demo grids share the left and right edges of the section titles
      (no centred gutter).
- [ ] At 375px, project and demo cards are one column and the page has no
      horizontal scroll.
- [ ] On `/demos/forecast-workbench` and `/demos/churn-sandbox` at 2,560×1,440
      and 1,920×1,080, the header, drawer summary, KPI tiles and notice strip
      are at their content height (no empty vertical space inside them), and
      the workbench spans the content width.
- [ ] The chart card's readout band is fully visible at 1,920×1,080 and
      2,560×1,440.
- [ ] The forecast notice spans the full strip; at 375px the two churn notices
      stack.
- [ ] `npm test && npm run lint && npm run build` pass, with the new CSS-text
      assertions in the handoff.

## Rollback and failure behavior

- Failure modes: CSS only; a wrong rule shows as layout, not as an error.
- Observability: the CSS-text tests and screenshots at the listed widths.
- Rollback path: revert the two CSS files and the two test files to `2a7d9b7a`.

## Open questions

- O1. Is Option A (full width, 2 columns) approved, or does the owner want B
  or C for the live-demo cards only?
- O2. Is a taller forecast chart on 2,560px screens wanted as a follow-up
  (TSX change in `DemoWorkbench.tsx`)?
