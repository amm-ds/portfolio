# Implementation handoff: UI layout regression (project cards and demo workbench)

Date: 2026-11-24
Designer: Claude Code
Executor: Kimi Code
Status: blocked (awaiting owner approval of Option A in `01-design-brief.md`)
Source design: `collaboration/designs/20261124-ui-layout-regression/01-design-brief.md`,
`02-architecture-proposal.md`

## Objective

Restore full-width card grids on `/projects` and make the demo workbench
(`/demos/forecast-workbench`, `/demos/churn-sandbox`) size its rows and tiles
to their content from 375px to 2,560px. CSS-only change plus CSS-text tests.

## Scope

### In scope

- `apps/showcase-web/src/styles/cards-grids.css`: `.demo-grid`,
  `.study-card__content`, `.project-grid`, `.apps-grid`.
- `apps/showcase-web/src/styles/demos.css`: `.wb-root` (line 293 block),
  `.wb-notice-strip` (line 441 block), `.wb-canvas-slot .figure-card`
  (line 472 block).
- `apps/showcase-web/src/__tests__/ProjectsIndex.test.tsx` (extend two tests).
- `apps/showcase-web/src/__tests__/ForecastWorkbench.test.tsx` (add one test).

### Out of scope

- Any TSX change (including `DemoWorkbench.tsx` canvas height logic).
- `.app-card__shot` (Wave 6 aspect-ratio rule stays; its test at
  `ProjectsIndex.test.tsx:758-764` stays as is).
- `.wb-secondary` height (`demos-workbench.css:301-307`) and the
  `@media (max-width: 900px)` rules.
- Column counts: `.project-grid` and `.demo-grid` stay 1 → 2 at 720px;
  `.apps-grid` stays 1 → 2 at 960px.

## Affected surfaces

- `/projects` (apps, experiments, live demos blocks), `/experiments` (same
  component).
- `/demos/forecast-workbench`, `/demos/churn-sandbox`.

## Ordered implementation steps

### 1. `cards-grids.css` — `.demo-grid` (lines 3-13)

Before:

```css
/* full-width grid, same shape as the experiment card grid below; capped so
   the two demo cards stay readable on very wide screens (proposal A) */
.demo-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--gap-card);
  margin-bottom: 1rem;
  margin-inline: auto;
  max-width: 72rem;
  align-items: stretch;
}
```

After:

```css
/* full-width grid, same shape as the experiment card grid below; width comes
   from the fluid page shell, never from the grid */
.demo-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--gap-card);
  margin-bottom: 1rem;
  align-items: stretch;
}
```

### 2. `cards-grids.css` — `.study-card__content` (lines 48-51)

Before:

```css
.study-card__content {
  padding: 1.1rem 1.25rem 1.25rem;
  max-inline-size: 70ch;
}
```

After:

```css
.study-card__content {
  padding: 1.1rem 1.25rem 1.25rem;
}
```

(The two `.study-cols` text columns already keep line length near 600px at
2,560px.)

### 3. `cards-grids.css` — `.project-grid` (lines 219-226)

Before:

```css
.project-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--gap-card);
  margin-inline: auto;
  max-width: 72rem;
  align-items: stretch;
}
```

After:

```css
.project-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--gap-card);
  align-items: stretch;
}
```

### 4. `cards-grids.css` — `.apps-grid` (lines 252-258)

Before:

```css
.apps-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--gap-card);
  margin: 0 auto 2rem;
  max-width: 72rem;
}
```

After:

```css
.apps-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--gap-card);
  margin: 0 0 2rem;
}
```

### 5. `demos.css` — `.wb-root` (lines 293-316)

Before (the last block of declarations):

```css
  gap: 0.5rem;
  height: auto;
  min-height: calc(100dvh - 58px - 1rem);
  /* cap the whole workbench on very wide screens so charts stay readable
     (proposal A: chart column tops out just under 1,400px at 2560px) */
  max-width: 109rem;
  margin-inline: auto;
  width: 100%;
}
```

After:

```css
  gap: 0.5rem;
  height: auto;
  min-height: calc(100dvh - 58px - 1rem);
  /* rows keep their content height; free viewport height stays below the
     last row instead of stretching the header, KPI and notice tiles */
  align-content: start;
}
```

Also replace the stale comment inside the same rule (lines 295-298):

Before:

```css
  /* the controls rail sits right of the chart; the main row absorbs free
     viewport height (minmax floor 400px) so big screens don't leave dead
     space below the workbench; content taller than the viewport overflows
     the 1fr row and scrolls the page */
```

After:

```css
  /* the controls rail sits right of the chart; every row is content-sized
     and content taller than the viewport scrolls the page */
```

### 6. `demos.css` — `.wb-notice-strip` (lines 439-445, the `display: grid` block, not the `grid-area` block at 326)

Before:

```css
/* notice strip: two dynamic tiles side by side under the KPI band */

.wb-notice-strip {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}
```

After:

```css
/* notice strip: one tile per notice under the KPI band; a single notice spans
   the strip and two notices stack on phones */

.wb-notice-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
  gap: 0.5rem;
}
```

### 7. `demos.css` — `.wb-canvas-slot .figure-card` (lines 471-484)

Before:

```css
/* the canvas figure card grows to fill the row; the chart svg fills the card */
.wb-canvas-slot .figure-card {
  /* definite clamped card: the measured viewBox cannot feed back into layout
     (an auto-height chain grew the row without bound), and the chart never
     resizes because the controls rail grew; the clamp caps the card on very
     wide screens (proposal A) while keeping a floor for small laptops */
  flex: none;
  height: 100%;
  min-height: clamp(400px, 48vh, 640px);
```

After:

```css
/* the canvas figure card grows to fill the row; the chart svg fills the card */
.wb-canvas-slot .figure-card {
  /* definite card: the measured viewBox cannot feed back into layout (an
     auto-height chain grew the row without bound); the 460px floor matches
     the slot's inline height floor in DemoWorkbench.tsx, so the card never
     outgrows its overflow-hidden slot */
  flex: none;
  height: 100%;
  min-height: 460px;
```

(Leave the remaining declarations of the rule unchanged.)

### 8. Tests — `src/__tests__/ProjectsIndex.test.tsx`

a. In `it("lays the demos out full width: one shared row on desktop, stacked on mobile")`
(line 394), append:

```ts
    // width comes from the fluid shell: no grid caps or centring (Wave 6 regression)
    for (const sel of ["demo-grid", "project-grid", "apps-grid"]) {
      const rule = stylesCss.match(new RegExp(`\\.${sel} \\{[\\s\\S]*?\\n\\}`))![0];
      expect(rule).not.toContain("max-width");
      expect(rule).not.toContain("margin-inline: auto");
      expect(rule).not.toContain("0 auto");
    }
```

b. In `it("uses full-width translucent title bands with a green terminal prompt")`
(line 148), after the existing `.study-card__content` padding assertion, add:

```ts
    expect(stylesCss.match(/\.study-card__content \{[\s\S]*?\n\}/)![0]).not.toContain(
      "max-inline-size",
    );
```

### 9. Tests — `src/__tests__/ForecastWorkbench.test.tsx`

Add `import { readStylesCss } from "./helpers/css";` and one test in the
existing top-level `describe`:

```ts
  it("keeps workbench rows at content height and full width on large screens", () => {
    const css = readStylesCss();
    const root = css.match(/\n\.wb-root \{[\s\S]*?\n\}/)![0];
    expect(root).toContain("align-content: start;");
    expect(root).not.toContain("max-width");
    expect(root).not.toContain("margin-inline: auto");
    const strip = css.match(/\.wb-notice-strip \{\n  display: grid;[\s\S]*?\n\}/)![0];
    expect(strip).toContain("repeat(auto-fit, minmax(min(100%, 18rem), 1fr))");
    const card = css.match(/\.wb-canvas-slot \.figure-card \{[\s\S]*?\n\}/)![0];
    expect(card).toContain("min-height: 460px;");
  });
```

The `\n\.wb-root \{` anchor matches the top-level rule in `demos.css`
(imported before `demos-workbench.css`, `src/styles.css:7-8`), not the indented
one inside `@media (max-width: 900px)`.

## Existing tests that read these rules (must stay green)

| Test file:line | Test name | What it locks |
|---|---|---|
| `ProjectsIndex.test.tsx:148` | uses full-width translucent title bands with a green terminal prompt | `.study-card__content` padding |
| `ProjectsIndex.test.tsx:315` | ships a 1-column grid on mobile and 2 columns from 720px up | `.project-grid` `1fr`, no `repeat(3`, `align-items: stretch` |
| `ProjectsIndex.test.tsx:394` | lays the demos out full width: one shared row on desktop, stacked on mobile | `.demo-grid` base rule and 720px 2-column rule |
| `ProjectsIndex.test.tsx:742` | renders all app template cards with screenshots and external links | `.app-card__shot` (unchanged) |
| `ProjectsIndex.test.tsx:875` | splits the card body into two equal white text columns… | `.study-cols` (unchanged) |
| `ProjectsIndex.test.tsx:1043` | left-aligns the tags row exactly with the card's outer padding — no indent | `.demo-grid` gap |
| `AppShell.test.tsx:172` | pads the page content one token above the footer | `.app-main--fluid` padding (unchanged) |
| `ChurnSandbox.test.tsx:270` | renders two capitalized notice tiles that both react to the FN slider | DOM only: two `.wb-notice` in `.wb-notice-strip` |
| `DemoWorkbench.test.tsx:153` (in `src/demos/workbench/`) | renders the notice as a slim strip directly under the KPI band | DOM only |

None of them asserts `72rem`, `109rem`, `70ch` or `clamp(400px…`, so steps 1-7
should not break them. If any does fail, stop and write `OPEN_QUESTIONS.md`.

## Commands and gates

```bash
cd apps/showcase-web
# arm64 node check (AGENTS.md): node -p process.arch should print arm64
npx vitest run src/__tests__/ProjectsIndex.test.tsx src/__tests__/ForecastWorkbench.test.tsx src/__tests__/ChurnSandbox.test.tsx src/demos/workbench/DemoWorkbench.test.tsx
npm test && npm run lint && npm run build
```

Browser check (no API needed for `/projects`; the workbenches need the API or
their committed payload fallback, as in Wave 6):

```bash
npm run dev   # port 4321; API on :8000 for /demos payloads
```

## Generated artifacts

None. Do not touch `staticRegistry.ts`, `storyShort.ts` or the route manifest.

## Acceptance criteria

- [ ] `git diff --stat` touches only the four files in scope.
- [ ] `grep -n "72rem\|109rem\|max-inline-size: 70ch\|clamp(400px, 48vh" apps/showcase-web/src/styles/*.css` returns nothing.
- [ ] `/projects` at 1,280, 1,440, 1,920 and 2,560px: the left edge of the first
      card and the right edge of the last card in each grid line up with the
      section title's left edge and the page's right padding (±1px).
- [ ] `/projects` at 375 and 768px: same layout as before Wave 6 (1 column at
      375; 2 columns at 768 for experiments and demos, 1 for apps); no
      horizontal scroll (`document.documentElement.scrollWidth === innerWidth`).
- [ ] `/demos/forecast-workbench` and `/demos/churn-sandbox` at 1,920×1,080
      and 2,560×1,440: `.wb-header`, `.wb-kpi` and `.wb-notice` heights equal
      their content heights (no stretched empty space); the `.wb-root` width
      equals the content width; the chart's `.figure-card-band` is fully
      inside `.wb-canvas-slot` (its `getBoundingClientRect().bottom` ≤ the
      slot's).
- [ ] Forecast workbench: the single notice spans the full strip width.
      Churn sandbox at 375px: the two notices stack.
- [ ] `npm test && npm run lint && npm run build` pass.

## Verification evidence required

- Tests run and results: test counts before and after (one new test, two
  extended tests).
- Build or typecheck results: `npm run lint`, `npm run build` output tails.
- Browser or runtime verification: screenshots at 375, 768, 1,280, 1,440,
  1,920 and 2,560px wide for `/projects`, `/demos/forecast-workbench`,
  `/demos/churn-sandbox`, saved under `artifacts/` (not committed), plus the
  measured values for the acceptance checks above.
- Artifact paths inspected: the four edited files.

## Risks and open questions

- Very wide forecast chart at 2,560px (about 2,170 × 460–600px). Accepted
  here; a taller chart needs a TSX change (brief O2).
- On very tall screens the free height now sits below the secondary band
  instead of inside the tiles. This is the intended trade.
- The owner screenshot was not available to the designer. If the owner's
  screenshot shows a different symptom, stop and record it in
  `OPEN_QUESTIONS.md` before editing.
