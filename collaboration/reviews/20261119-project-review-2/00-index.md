# Per-project quality review, second pass (01–13)

Date: 2026-11-19
Reviewer: Claude Code
Scope: article copy (`story.yaml`, `README.md`, short copy in `storyShort.ts`), results wording against committed metrics, and performance claims. Figure layout was covered by the UI pass (H1–H8).
Implementation: none changed. Findings only. Fixes go to a handoff for the owner to approve.

## How this pass was done (and what it did not cover)

1. **Mechanical audit** of all 13 projects: pipe-table counts, figure references, stale words (`profit`, `significant`, `champion`, `proves`, `lifts`), and verify markers. Results below.
2. **Short copy read** for all 13 projects (`apps/showcase-web/src/lib/storyShort.ts`), checked against the committed metrics where a number is quoted.
3. **Targeted checks** of the claims that look most likely to be wrong: 06, 08, 10, 12.

Not covered: a line-by-line read of every README and story body. The stale-word hits in 01, 03, 12 and 13 have not been read in context. Treat the per-project rows below as a triage list, not a clearance.

## Triage table

| # | Project | Mechanical | Short copy | Findings (see sections) |
|---|---|---|---|---|
| 01 | RAG agent | 17 story / 51 README pipe rows; 13 stale-word hits (not read in context) | matches stress numbers | C7 |
| 02 | M5 | 7 / 13 table rows; 3 stale-word hits | matches 0.6161 / 0.8929 / −31.0% | none; the figure path is `reports_m5_full/figures` (checked, present) |
| 03 | NAB anomaly | 27 / 34 rows; 23 stale-word hits, mostly "champion" as a defined term | matches 16/17, 1,609, 80, 35, 0.604, 0.533 | C4 |
| 04 | NLP | 30 / 57 rows; 3 hits | matches 0.953 → 0.954, 22 of 1,000, $0.023671 | C8 (reword "no measurable change" as a fixed phrase) |
| 05 | Churn | 23 / 20 rows; 3 hits | matches 601 vs 1,035, CI −508 to −353 | minor: use a true minus sign in copy |
| 06 | VRPTW | 15 / 36 rows; 6 hits | "hand-written search", 4.2%, 3.7 vehicles | C3 |
| 07 | Mobility | 11 / 44 rows; 2 hits | matches 28.3%, 4.68 vs 6.52, 91% | none |
| 08 | Serving | 20 / 11 rows; 1 hit | $0.12 per 1M output tokens: derivation checks (67.7 tok/s, 100 W, $0.30/kWh gives about $0.123) | minor: short copy says "electricity only"; README says "hypothetical cloud rate card" in one place. Pick one basis |
| 09 | Agentic | 12 / 40 rows; 0 hits | live 6/6 refusals stated without the h19 caveat | C6 |
| 10 | Uplift | 19 / 28 rows; 6 hits | +$2,812 (+70%) matches README table (T-learner $6,838 vs random $4,026) | C2 |
| 11 | Data eng | 20 / 23 rows; 1 hit | matches 19x and 15x | none |
| 12 | Tabular | 15 / 23 rows; 7 hits (not read in context) | short copy omits the LightGBM validation tie | C1 |
| 13 | Serving | 10 / 9 rows; 15 hits (not read in context) | matches 25.4316, 7.2e-07, 1.6 ms, 950 req/s | C8 |

## Cross-cutting findings

**C1. Short copy drops the validation tie for project 12.** The headline in `story.yaml` says "validation-tied with LightGBM"; the short copy says "the validation-selected PyTorch MLP". Decision 8 says call MLP and LightGBM a tie and remove the champion label. The short copy must say the same, because it is what cards and social preview show. *Fix:* add "validation-tied with LightGBM" to the short copy and re-run `gen_story_short.py`.

**C2. The +$2,812 figure has no metric name in the short copy.** The 10 short copy says "beat random targeting by +$2,812 (+70%)". That figure is revenue minus send cost, per the owner's wording rule. The README table is correct, but the card is not. Also check the README table header for any leftover "profit" column name. *Fix:* name the metric in the short copy, and confirm the +70% basis (2,812 / 4,026 = 69.9%) is stated in the README.

**C3. Project 06 short copy says "a hand-written search".** The story describes the method as tuned adaptive large-neighbourhood search (ALNS), with the CP-SAT solver ALNS-hinted. "Hand-written" is vague and hides the method. *Fix:* "an adaptive large-neighbourhood search (ALNS)". The 4.2% and 3.7-vehicle figures match the story (4.23%, 3.73).

**C4. Project 03 wording: "proves" and the word "champion".** The story says "It proves no transfer to other datasets or production." A limit should say "does not show". "Champion" is defined in the README (rank-average ensemble frozen on validation PR-AUC), but it appears about 23 times, and several cards use it without the definition. *Fix:* replace "proves" with "does not show"; add a one-line definition beside the first use in each card.

**C5. Project 13 and 01 stale-word hits are unread.** Each has 13–15 hits. These need a read in context before anyone decides whether they are a problem.

**C6. Project 09 short copy omits the h19 caveat.** The short copy says "Live 2026-11-19: 13/13 answers, 6/6 refusals, 19/19 budgets". Kimi's comparison note explains that h19 was the calculator guard error, and the earlier review already flagged that the refusal message is raw exception text. A card that states "6/6 refusals" without that context overstates the graceful-refusal contract. *Fix:* keep the numbers and add "h19 is a guard error refusal" to the card and README.

**C7. Project 01 stale-word hits are unread.** See C5.

**C8. "No measurable change" and "no bootstrap interval" phrasing.** Projects 04 and 02 use these phrases. They are the correct wording, but they are repeated in several places with slightly different surrounding copy. *Fix:* use one sentence per project and link to the interval-methods doc (`docs/engineering/statistical-intervals.md`).

## What this pass did not find

- No headline number in the 11 claims checked by `check_headline_numbers.py` disagrees with its committed metrics. Projects 01 and 04 are not covered by that check (known-drift list), and I did not verify their short-copy numbers against their metrics files in this pass. That is a gap, not a clearance.
- No broken figure references in the story files for projects 01–13 (the one apparent gap was my script looking in the wrong folder for 02).

## Proposed handoff (for owner approval)

One copy-only handoff, `P1`:
- C1, C2, C3, C6: short copy and card wording for 12, 10, 06, 09. Re-run `gen_story_short.py` and `check_short_copy.py --check`.
- C4: replace "proves" in 03 and add definitions. Regenerate short copy if it changes.
- C5, C7: read the unread stale-word hits in 01 and 13; change only what is wrong.
- Gates: `lint_story_language.py`, `check_docs.py`, `check_short_copy.py --check`, `gen_story_short.py --check`, `check_headline_numbers.py`, and the web tests if `storyShort.ts` changes.
- No number changes. No git mutations. No hosted calls.

Also for owner decision: whether the 08 cost basis should be "electricity only" or "hypothetical cloud rate card" (C-minor, project 08).
