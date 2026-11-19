# H9: heading slash spacing, and why production still shows the old style

Date: 2026-11-19
Designer: Claude Code
Executor: Kimi Code (owner runs it)
Status: DRAFT for owner approval.

## What the owner saw

On the experiment article (`/projects/01-rag-agent`), the section heading still reads with a space after the slash, and the subtitle is blue. Owner's wording: "/01 Background", with the space between "/" and "01" removed.

## Findings

1. **Production is not the current tree.** On `alejandromerida.dev/projects/01-rag-agent` the computed subtitle colour is `rgb(56, 189, 248)`, which is the `--secondary` token (blue). In the local CSS, `.section-subtitle` uses `--muted` (`#94a3b8` dark, `#4e6276` light), which is gray. So the subtitle fix from H3 is local only and has not been deployed. The production heading text also has no space between the number and the title, which matches the old build. Owner deploys.

2. **My earlier spec was wrong, and the local heading still breaks the requested form.** `apps/showcase-web/src/styles/story.css` line 161 sets `.story-section h2::before { content: "/ "; }`. The trailing space in `"/ "` puts a space between the slash and the number, so the local result is "/ 01 Background". The owner asked for "/01 Background". H2 added spacing between the number and the title, which is correct. It did not remove the space after the slash, because I had described the target as "01 Background" without the slash. That description was mine, not the owner's.

3. **The app articles use a different slash rule.** `styles/cards-grids.css:202` sets `content: "/"` (no space). Check that the apps headings render "/01 Background" after the fix, so both article types match.

## Change (H9)

- `apps/showcase-web/src/styles/story.css` line 161: change `content: "/ ";` to `content: "/";`.
- Keep the `.sec-num` span and the JSX `{" "}` after it, so the number and the title stay separated.
- Keep `.section-subtitle` on `var(--muted)`. Do not change its colour.
- Regenerate nothing. No data, copy or number changes.

## Acceptance checks

- Local `npm run dev` or the test harness: computed `::before` content is `"/"`; the heading text reads "/01 Background" with one space between the number and the title.
- Subtitle computed colour equals the `--muted` value in both themes (dark `#94a3b8`, light `#4e6276`).
- Screenshots at 375 px and 1280 px for `/projects/01-rag-agent` and `/apps/agent-chat`, both themes, saved under `collaboration/reviews/20261119-h9-report/screenshots/`.
- Gates: `cd apps/showcase-web && npm test && npm run lint && npm run build`.

## Owner action after H9 is committed

Deploy the web app. Until then, production will keep showing the old style, whatever the local tree shows.

## Open question for the owner

The subtitle text "why this exists and the headline numbers" comes from `apps/showcase-web/src/lib/sectionMeta.ts`. If the question was about that wording rather than its colour, tell me which subtitle you want, and I will write it into a separate change.
