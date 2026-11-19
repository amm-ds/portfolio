# H9 report: heading slash spacing

Date: 2026-11-19
Spec: `collaboration/designs/20261119-ui-and-apps-fixes/01-h9-heading-slash-and-deploy.md`
(approved by owner via P2 plan feedback)

## Change

- `apps/showcase-web/src/styles/story.css:161` — `content: "/ ";` → `content: "/";`.
  Section headings now read "/01 Background" (no space after the slash; one space
  between number and title, from the existing `.sec-num` markup + JSX space and its
  `margin-right`). Both experiment stories and app articles share this single
  `.story-section h2::before` rule, so both article types match by construction
  (the app articles never had their own slash rule — `cards-grids.css:202` is the
  projects-index row label).
- `apps/showcase-web/src/__tests__/StorySection.test.tsx:275` — style-contract test
  updated to assert `content: "/";` (it encoded the earlier, wrong spec).

Not changed, per spec: `.section-subtitle` stays on `var(--muted)` (gray — verified
locally in both themes; the blue subtitle on production is the old build, owner
deploys after commit). No JSX, data, copy or number changes. Nothing regenerated.

## Acceptance checks

- Computed `::before` content is `"/"`: asserted by the updated style-contract test
  (`StorySection.test.tsx`, h2 title styling case) and visible in the screenshots.
- Heading reads "/01 Background" with one space between number and title:
  screenshots below (experiment article + app article, both widths, both themes).
- Subtitle computed colour is `--muted`: dark `#94a3b8`, light `#4e6276` — confirmed
  on `story.css` `.section-subtitle` rule (`color: var(--muted)`) and in the
  screenshots (gray in both themes on both article types).

## Gates (all run)

- `npm test` — 56 files passed, **752 tests passed**.
- `npm run lint` — clean.
- `npm run build` — success (12.79s).

## Screenshots

All under `collaboration/reviews/20261119-h9-report/screenshots/`:

- `375-01-rag-agent-dark.png`, `375-01-rag-agent-light.png`
- `375-agent-chat-dark.png`, `375-agent-chat-light.png`
- `1280-01-rag-agent-dark.png`, `1280-01-rag-agent-light.png`
- `1280-agent-chat-dark.png`, `1280-agent-chat-light.png`

## Owner action

Deploy the web app — production keeps the old style (space after slash, blue
subtitle) until the build ships. The subtitle wording question in the spec's
"Open question" stands: if the request was about the subtitle text rather than its
colour, that is a separate change.
