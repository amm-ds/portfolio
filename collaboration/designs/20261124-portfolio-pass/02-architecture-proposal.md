# Architecture proposal: portfolio pass (grids, demo sizing, article pattern, roadmap)

Date: 2026-11-24
Designer: Claude Code
Status: draft, pending owner approval
Companion: `01-design-brief.md` (findings with file:line), `03-implementation-handoff.md` (steps), `OPEN_QUESTIONS.md`.
Supersedes, once approved: `collaboration/designs/20261124-wave65-ui-and-rag-article-polish/01-design-and-handoff.md` Tracks A–C. Track A's diagnosis is confirmed (see brief §4.1); its proposal to change `.wb-root` is kept as option 2.3-c below, gated on the owner's screenshot. Its roadmap cards are replaced by the verified set in §4.

Legend: **[V]** verified in this session; **[I]** inference.

## 1. Scope and layering

Three surfaces change, each with its own contract:

| Surface | Files | Contract it must keep |
|---|---|---|
| Card grids (projects and demos) | `apps/showcase-web/src/styles/cards-grids.css` | Two columns from 720 px; cards span the page width; no per-card height hacks |
| Demo workbench shell | `apps/showcase-web/src/styles/demos.css`, `demos-workbench.css` | Charts remain readable; no hollow stretched tiles |
| Article content and roadmap | `projects/01-rag-agent/story.yaml` (pilot) | Eight section ids in fixed order; `short_version` ≤280 chars; one `In plain terms` card per section, last; roadmap 3–4 shipped + 1–2 next/blocked, ≤5 total |

Nothing in the API, the registry, or the generated files changes. `short_version` is kept unchanged, so `gen_story_short.py` and the README/docs surfaces are not regenerated.

## 2. Card grids and demo sizing

### 2.1 Decision: remove the caps (recommended)

Remove `max-width: 72rem` and `margin-inline: auto` from `.demo-grid` (`cards-grids.css:10-11`), `.project-grid` (`:223-224`) and `.apps-grid` (`:256-257`, change `margin: 0 auto 2rem` back to `margin: 0 0 2rem`). Keep the `grid-template-columns` rules and the 720 px breakpoint.

Alternatives considered:
- **Raise the cap to match `.app-main--fluid`** (for example `max-width: 100%`). Equivalent to removing it; no benefit over removal.
- **Cap at a wider value such as 96rem for ultra-wide screens.** Keeps centered gutters at 2560 px. Rejected for now: the owner asked for full width, and the page header and tables already span the full width. Reopen if the owner's screenshot shows 2-column cards too wide (Q1).

Cost and risk: at 2560 px each of the two columns is about 1,200 px wide. That is the reason §2.3(b) exists.

### 2.2 Tests

- Add to `apps/showcase-web/src/__tests__/ProjectsIndex.test.tsx` (near line 302–325): assert that the rules for `.project-grid`, `.demo-grid` and `.apps-grid` contain no `max-width` and no `margin-inline: auto`. This pins the regression.
- Keep the existing 720 px and `repeat(2, minmax(0, 1fr))` assertions unchanged (`ProjectsIndex.test.tsx:319-325`, `:395-405`).
- Optional, owner-gated: a Playwright check at 1920 px that `.project-grid` width equals `.app-main` content width. The repo already ships `@playwright/test`-style tooling via `playwright` and `@axe-core/playwright` in `apps/showcase-web/package.json`; do not add a new dependency.

### 2.3 Demo card sizing: options, gated on the screenshot

- **(a) Same fix as §2.1.** Demo cards share `.demo-grid`. Always included.
- **(b) Text cap.** `.study-card__content { max-inline-size: 70ch; }` (`cards-grids.css:48-51`) limits text to about 70 characters while the card can be much wider. Options: keep it (readable line length, recommended default), or remove it only for `.demo-card` so the description fills the card. Decide after Q1.
- **(c) Workbench shell** (only if Q2 says the workbench is the subject):
  - `.wb-root` (`demos.css:293-316`): add `align-content: start;` and drop the viewport-height `min-height` in favour of `height: auto`, so tiles stop stretching.
  - `.wb-root` `max-width: 109rem; margin-inline: auto;` (`:313-314`): remove, to match the rest of the page.
  - `.wb-notice-strip` (`demos.css:441-445`): `grid-template-columns: repeat(auto-fit, minmax(280px, 1fr))` so a single notice spans the row.
  - Leave `demos-workbench.css` `clamp()` values unchanged unless the screenshot shows a problem there.

Default if the owner does not answer Q1/Q2 before implementation starts: implement §2.1 and §2.2 only; report demo sizing as still open.

## 3. Article pattern (pilot: RAG 01)

### 3.1 Current state [V]

- Sections and ids: `story.yaml` lines 4–515, eight ids in the fixed order.
- Introductions already embed diagrams: `background` → `01-rag-pipeline` (`story.yaml:12`); `objectives` → `auto-01-rag-agent-1` (`:33`).
- Lint baseline: 0 errors, 1 warning, `evaluation` at 685 words against the soft 550 budget (`scripts/lint_story_language.py:64`). Run 2026-11-24.
- Opus review (read-only, 2026-11-24) on the current prose: background opens with insider shorthand before the result; training packs FAISS, BM25, RRF k=60, cross-encoder and per-article cap into one paragraph; evaluation is an eight-paragraph run of numbers and walks four runs (65q, 55q, 30q, final) before the final result; results and evaluation use "empty-answer" where the committed `f1_summary.json` calls the same rows `false_abstention`.
- Legacy-run numbers presented as current: the 65q, 55q, 30q stress, set B 0.633 and stress 0.733 results (`story.yaml:18-22`, `:233-251`, `:259-266`, `:456-468`). The table at `:456` is titled "Current grounding-hardened results" although it is superseded. This conflicts with `repo-conventions.md` "Present last results only."

### 3.2 Section pattern (per section, in this order)

1. **Opening.** One bold hook sentence, then 2–3 plain-English sentences that state the question or choice. Then the section's diagram block (existing ids; do not invent new ones).
2. **Contents.** 3–5 bullets, each one mechanism or trade-off in plain language, with the technical term named once and defined in the same bullet (for example "reciprocal rank fusion (RRF), which merges two ranked lists by position").
3. **Evidence.** The section's `metrics_keys` table or `FigureCard`s. Prose introduces the table in one sentence; it does not repeat its numbers.
4. **Bridge.** One sentence that links to the next section (a link to the next step).
5. **Closing.** `**In plain terms:**` as the last paragraph (renders as the takeaway card, `StorySection.tsx:8-9`).

Rules:
- Numbers in prose: round for people (95%, not 0.9460); keep full precision in tables. Every number must be traceable (see §5).
- Development history (65q, 55q, 30q, set B, stress runs) moves to `conclusions` under `## Exact numbers` (already collapsed) or to `DESIGN.md`. It does not appear in the visible prose of `results`.
- The final sealed pass is the only result shown as current.
- Use the public label "unnecessary refusals" for `false_abstention` rows, and say so once.
- No repository paths inside prose (Opus flagged `story.yaml:136`).

### 3.3 Lint constraints (from the Opus review, verified against `lint_story_language.py`)

- Opening-section raw word count: `background` is 159 raw words against a hard limit of 150 (`lint_story_language.py:63`). The lint passes only because diagram and code text are excluded. Adding bullets to `background` can make it an ERROR. **Rule: the opening section of RAG 01 must be rewritten to ≤140 raw words including bullets.** Verify with the lint before finishing.
- Exactly one `In plain terms` card per section, and it must be last. A bridge sentence goes before the marker, not after (`lint_story_language.py:475-495`).
- Do not add, rename or reorder section ids. Use headings inside a section, not new sections.
- Keep `metrics_keys` in `evaluation` (`story.yaml:286-294`) and `results` (`:356-361`) if their tables stay; moving numbers into `conclusions` is safe for the budgets (`lint_story_language.py:72`, `:598`).

### 3.4 Word targets (soft)

- `evaluation`: 685 → ≤550 (clears the warning).
- `results`: 518 → ≤400.
- `training`: 565 → ≤500 (will also clear its word budget).
- `conclusions` is exempt from budgets; it absorbs the judge calibration paragraph (`story.yaml:345-349`) and the exact numbers.

These targets replace the wave 6.5 draft's ranges (320–360), which were not checked against the lint's hard limits.

## 4. Roadmap

### 4.1 Current [V]

`projects/01-rag-agent/story.yaml:523-538`: four `shipped` and one `next`. The web renders `shipped` only (`RoadmapBlock.tsx:14-16`), so the `next` card is authored state, not visible. Problems: titles start with a noun in one case, details carry several numbers each (`:526`, `:535`), and titles and details use internal ids (`S3`, `final_v3`, `judge_v2`, `12/16/200k`).

Rules (`repo-conventions.md`): 3–4 shipped plus 1–2 next/blocked, ≤5 total; title 3–6 words, verb-first, no metric; detail one line ≤90 chars with one number or one decision; `next` names the gate; `blocked` names the owner decision. The generator (`scripts/gen_static_registry.py:80-100`) rejects over-long details.

### 4.2 Proposed cards (neutral, high-level; Opus-reviewed, figures checked)

```yaml
roadmap:
- status: shipped
  title: "Pin a bounded Wikipedia corpus"
  detail: "593 articles over five topics, checksum-pinned with source and license."
- status: shipped
  title: "Promote hybrid retrieval with reranking"
  detail: "Finds the right source for 95% of sealed test questions on CPU only."
- status: shipped
  title: "Audit the answer-checking judge"
  detail: "Reviewer audit matched the judge on 30 of 30 sampled claims; owner check pending."
- status: shipped
  title: "Bound and verify every answer"
  detail: "Final sealed pass kept 1 unsupported claim in 120 questions."
- status: next
  title: "Reduce unnecessary refusals"
  detail: "Gate: a fresh sealed set; today 10 of 92 answerable questions return empty."
```

Checks:
- Titles 4–6 words, verb-first, no metric. Details ≤90 chars (lengths 60–81 per Opus).
- "95%" is 0.9457 rounded (`reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json`). Rounding is allowed for people (`repo-conventions.md` Terminology).
- "10 of 92" must be re-traced from the committed false-abstention count before implementation (Opus cites `f1_summary.json:17` as `false_abstention`). **Open:** confirm the number's source file and key.
- Opus noted the wave 6.5 draft's details carry no number and no decision in some cards (see its Track C). The set above puts one fact per detail, which satisfies the rule.
- Owner must confirm the wording (Q3) before implementation.

### 4.3 Other projects

Not in this pass. The wave 6.5 draft proposed rolling the style out to 02–13. That is Q4.

## 5. Truth in copy

Each number in the rewritten RAG 01 copy must appear in a committed file. The trace table is in `01-design-brief.md` §4.4. Opus found these items to fix or disclose before shipping:

- `$2.0392` cumulative spend (`story.yaml:279`, `:397`) appears only in `DESIGN.md:413` and `README.md:102`, not in a JSON. The final pass's own spend is `1.457917` (`reports/final_v3_e2e/metrics.json`, `detail.final_v3.meter.ledger_spend_usd`). **Rule:** present the final pass spend, or cite the cumulative from `DESIGN.md` as history, not as current.
- `judge_v2 (147 claims)` (`story.yaml:526`) is a file count, not a committed key. **Rule:** cite the claim count from the owner-sample file or drop it from roadmap copy.
- Rounding-only differences (0.8865 vs 0.886487; 0.3966 vs 0.39655; $9.74 vs 9.738003) are acceptable under the round-for-people rule; keep full precision in tables.
- The final pass's refusal accuracy (0.857), false-abstention rate (0.120) and latency (p50 16.5 s, p95 40.5 s) are committed in `final_v3_e2e/metrics.json` and are missing from the story. **Proposal:** show them in `results` as the current numbers, and move the old latency pair (25.888 s / 108.836 s, `story.yaml:233`) to conclusions.
- `metrics.json` headline gap (brief §4.4): the final_v3 headline numbers are in other committed files. Q5 decides whether to promote them.

## 6. Alternatives rejected

- **Rewrite all 13 stories at once.** Rejected: the pattern is unverified with the owner; a single pilot is cheaper to reverse.
- **New section ids for intro or takeaway.** Rejected: the eight-id contract is read by position (`lint_story_language.py:223-297`).
- **Keep caps and tune numbers.** Rejected: the caps are the regression.

## 7. Risks

- Owner-screenshot dependency for demo sizing (Q1, Q2). Mitigation: §2.3 default.
- Lint hard limit on the opening section (§3.3). Mitigation: rule and lint run in handoff.
- Removing the 72rem cap makes 2-column cards very wide at 2560 px. Mitigation: Q1 screenshot; §2.3(b) text cap.
