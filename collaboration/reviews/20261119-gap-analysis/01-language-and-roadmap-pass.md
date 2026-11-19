# Language, cohesion and roadmap pass (proposal)

Date: 2026-11-19
Reviewer: Claude Code
Scope: article language and engagement in `story.yaml` (section bodies, TL;DRs, figure captions), cohesion between sections, the link between text and each figure, and the roadmap cards.
Implementation: none changed. This file proposes the rules and shows rewrites for three projects. The owner approves the rules; then Kimi applies them.

## 1. What the roadmap is doing now

Measured across all 13 `story.yaml` files:
- **Every roadmap card has `status: delivered`.** Grep found no `planned`, `next`, `open` or `blocked` cards. The roadmap is a build history, not a roadmap.
- Card length averages 82–165 characters. Projects 03, 09 and 12 have the longest cards (03 up to 297 characters, 12 up to 210). Several cards hold four or five facts (metric, method, result and caveat in one sentence).
- Cards describe what was built ("Built the…", "Ran the…") rather than what it shows or what happens next.

A roadmap for a reader should answer three questions: what is shipped and what it shows, what is next and why, and what is blocked and on whom.

## 2. Roadmap card spec (proposal)

Each card has three fields:

- **state**: `shipped` | `next` | `blocked`
- **title**: 3–6 words, verb first, no metric.
- **detail**: one line, at most 90 characters, that carries one number or one decision.

Rules:
1. Shipped cards show the result that matters to the reader, not the file or step.
2. Next cards name the gate that would change the claim ("needs 3 seeds", "needs owner licence decision").
3. Blocked cards name the owner decision, not the technical blocker.
4. No caveat sentences in cards; put caveats in the body, next to the number.
5. Keep at most 5 cards per project (shipped 3–4, next or blocked 1–2).

Example: current 12 card 3 (210 chars) becomes:
- shipped: "Ladder selects the served MLP on validation" / "Tied with LightGBM; MAE 25.4 vs 83.2 for the floor."

## 3. Rewrites (current → proposed)

### 12 Tabular
Current (5 cards, all `delivered`, about 165 characters each):
1. "Built the reproducible pipeline: sha256-pinned UCI ingest, 26 DQ gates, time-based split…" → shipped: "Reproducible pipeline with 26 data-quality gates." / "Frozen time-based test window; sha256-pinned source."
2. "Engineered leakage-safe features…" → shipped: "Leakage-safe features under a written contract." / "Past-only lags; selection recorded in the feature contract."
3. "Ran the seeded ladder…" → shipped: "Served MLP ties LightGBM on validation." / "MAE 25.4 vs 83.2 for the seasonal-naive floor."
4. "Measured the served-model vs floor gap…" → shipped: "Gap to the floor holds under block resampling." / "Every 95% CI excludes zero (hourly and week-block)."
5. "Shipped overfitting-control artifacts…" → shipped: "Ablation scores labelled as post-freeze diagnostics." 

Add:
- next: "External TabPFN-2.5 challenger" / "Blocked on the Prior Labs licence decision; see research deltas."

### 03 Anomaly
Current card 7 is the longest (297 characters; it combines a negative result, a fusion number and a gate). Proposed:
- shipped: "A detector challenge with a published negative result." / "No fusion clears the precision gate; the committed detector stands."
- next: "Re-run the headline on TSB-AD with VUS-PR." / "Current benchmark for this task; no hosted calls needed."
- next: "Report run count and fit variance on the champion." / "Single fit per series today (Lyu 2026 disclosure)."

Card 6 (rank-average ensemble) becomes: shipped: "Rank-average ensemble halves paged load at equal recall." / "66 → 35 pages at recall 0.604, range-F1 0.533."

### 09 Agentic
Current card 7 (147 characters): "Added typed terminal outcomes, no-evidence stopping, and hard task deadlines with offline regressions; fresh live confirmation pending." Proposed:
- shipped: "Typed outcomes and hard deadlines in place." / "Offline regressions pass; live run done (13/13 answers)."
- next: "Multi-trial reliability run (k≥3)." / "Needs an owner-approved cap; current results are single runs."

## 4. Language rules for the article bodies

1. **Lead each section with the finding, then the method.** The TL;DR does this already; the body should not restate it in a different order.
2. **One term, one definition.** "Champion" (03) and "served model" (12) should each be defined once per project, then used the same way in every section and card.
3. **Name the metric the number belongs to.** "+$2,812" becomes "+$2,812 revenue minus send cost" the first time it appears in a section (10).
4. **Replace "proves" and "shows conclusively" with "does not show" or "measured".** Limits should read as limits.
5. **Sentence length:** cut sentences longer than about 35 words that carry two numbers. Split them so each number sits next to its interval.
6. **Caveats next to the number**, not in a later paragraph. For example, the h19 note belongs beside the 6/6 refusals (09).

## 5. Cohesion between sections

Problems found in the first read:
- **Repeated headline numbers in every section.** Projects 03, 09 and 10 repeat the headline in the TL;DR, the body and the card. Keep the number in the TL;DR and the body; the card links back.
- **Figure captions and body text describe the same figure in different words.** For 03, `nab_tune_surface` is described as four panels in one place and a 2×2 grid in another after H6. Update captions when the layout changes.
- **Section order differs between apps and experiments.** The apps articles use 01 Background to 08 Specs; experiment stories use other headings. This is acceptable, but the same section should have the same name (for example "Results" and "Limits") across projects.
- **Limits sections are inconsistent.** Some have a limits list, some put limits in a paragraph. Use one format.

## 6. Figure relation

For each figure, the section that introduces it should say what to look for in one sentence, and the caption should say what is plotted and the scale. Current gaps:
- Several figures are introduced by a number but not by a question (02 M5 series, 06 Pareto).
- Captions state the metric but not the test set (03 threshold sweep; check the rest in the next read, since this pass sampled only a few captions).
- The H6 layout change means some body text describes "a row of four panels". Check each mention.

## 7. Engagement

- Each section has a TL;DR. Keep it. It works as an entry point.
- Open each project with the question the reader would ask, in one sentence, before the method. 01 and 07 do this; 02, 03 and 12 open with the method.
- End each project with what to do with the result (a decision, a threshold to re-check), not with a list of caveats.

## 8. Handoff P2 (APPROVED by owner 2026-11-19)

Status: P2 EXECUTED by Kimi Code 2026-11-19 (report:
`collaboration/reviews/20261119-p2-report/00-report.md`). P1 (copy-only fixes in the second-pass review) is not covered by this approval; P1 items that overlap the language rules are included below only where they touch the same sentences. Do not cite PyVRP numbers in any card or body (routing conflict unresolved).

**Owner addendum 2026-11-19 (supersedes the rendering intent in §1–§2):** the
web roadmap block renders `shipped` cards only — finalized steps visible to
visitors. `next`/`blocked` cards stay in the schema and stories (they remain
the authored statement of forward work and owner decisions) but are not
rendered. Second fix the same day: section headings render a single space
between the number and the title (the `.sec-num` margin was removed; the JSX
space is the separator).

1. Apply the roadmap card spec (section 2) to all 13 projects. Each project: 3–4 shipped cards, 1–2 next or blocked cards, no card over 90 characters.
2. Apply the language rules (section 4) to the eight projects with the longest copy first: 03, 09, 10, 12, 13, 02, 06, 01.
3. Fix the cohesion and figure-relation items in section 5 and 6 for 03, 09, 10 and 12, the projects with the most repetition.
4. Gates: `lint_story_language.py`, `check_docs.py`, `check_short_copy.py --check`, `gen_story_short.py --check`, `check_headline_numbers.py`, and the web tests and build (roadmap cards are rendered in the web app).
5. No number changes. Any change to a headline number stops the item and returns to review.
6. No git mutations. No hosted calls.
