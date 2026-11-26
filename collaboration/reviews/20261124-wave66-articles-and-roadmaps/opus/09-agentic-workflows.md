# Review: 09-agentic-workflows story.yaml (Wave 6.6)

Reviewer: Claude Code (Opus), read-only.
Target: `projects/09-agentic-workflows/story.yaml` (530 lines).
Gold template: `projects/01-rag-agent/story.yaml`.

**Diff note:** the working tree is clean. `git diff -- projects/09-agentic-workflows/story.yaml`
is empty because the Wave 6.6 edits were committed in `18adc59d`. This review
grades the file as it is now and reads the round's changes from
`git show 18adc59d -- projects/09-agentic-workflows/story.yaml`.

Evidence checked: `reports/metrics.json` (`agentic_suite`, `detail.tooling`,
`detail.heldout`), `data/run_records.json`, `data/heldout_records.json`,
`params.yaml`, `src/agentic_workflows/{tools.py,schemas.py,evals.py}`,
`README.md`, `DESIGN.md`, `projects/01-rag-agent/DESIGN.md` (3,589 chunks), and
`collaboration/reviews/20261118-live-confirmation/{comparison.md,heldout_live_records.json}`.

## Grades

| # | Dimension | Grade |
|---|---|---|
| 1 | Structure and article logic | 6 |
| 2 | Engagement and human-like narrative | 5 |
| 3 | Language quality | 5 |
| 4 | Technical detail depth | 7 |
| 5 | Truthfulness | 7 |
| 6 | Roadmap cards | 7 |
| 7 | Consistency with gold template | 6 |
| | **Overall** | **6** |

### 1. Structure and article logic: 6

The section arc works: background, objectives, data, grading design,
executable graph, audit path, results, conclusions. Each section now ends with
a forward link. Three problems weaken it.

- **The live-confirmation thread contradicts itself.** Lines 41-42, 266-268,
  280-282, 357-359, and 478-481 say the 2026-11-19 live run confirmed the
  typed-refusal contract. Line 410 then says "live efficacy is unmeasured".
  Both cannot be true. The reader leaves the conclusions unsure which evidence
  counts.
- **The Evaluation chart paragraph describes data the chart does not hold.**
  Lines 318-324 send the reader to `cost_latency_bars`, which plots only the 15
  hosted tuning tasks (`reports/figures/cost_latency_bars.json` has no `h*`
  ids). Lines 321-322, "No hosted latency point crosses that line. The misses
  come from slow local generation", describe held-out misses that are not on
  that chart.
- **Too much repetition between sections.** "$0.13 of the $2.00 cap" appears
  in 8 places (lines 5, 27, 38, 54, 261, 280, 322, 370, 398). "18.2 s" appears
  6 times. The h19 live-grader parenthetical appears 6 times. Evaluation,
  Results, and Conclusions each restate the cost and latency numbers. The later
  sections add no new reading of them.

The background (lines 32-54) opens with a number dump before the reader knows
what the workflow does. The gold template opens with the problem and one
headline number.

### 2. Engagement and human-like narrative: 5

The strongest passages are concrete: the t15 trace (lines 441-445), the h19
story (lines 263-265, 354-357), and the `hitl.py` excerpt. Elsewhere the prose
reads like a glossary with numbers attached.

- Inline definitions interrupt almost every paragraph. Examples: "JSON is a
  text format for structured records" (line 124), "Deterministic code gives the
  same output for the same input" (line 63), "tokens, which are pieces of text
  processed by the model" (lines 126-127), and "Open weights are publicly
  available model parameters..." (lines 312-313). An expert reader does not need
  these. A general reader gets the same effect from the key-concepts list.
- Several reading instructions follow a fixed formula: "Follow the arrow...",
  "Follow the corpora...", "Follow a task...", "Follow the run...", "Follow the
  capture step", "Follow the grading step". That is six "Follow" openers.
- No section says why a research-ops team would care. For example: what does
  a fabricated number cost, and what does a reviewer gain from a checkpoint?

### 3. Language quality: 5

The Wave 6.6 compression introduced new defects.

- Line 34: "It plans, uses approved tools, reviews its work." The edit dropped
  "and", which leaves a clipped, telegraphic list.
- Line 37: "Held-out: 13/13 answers, 5/6 refusals, ..." This is a sentence
  fragment in the opening section.
- Lines 248-250: "The measurements below apply to the graph path above; the
  diagram identifies the measured work, the numbers come from recorded runs.
  Each has a limit:" This contains a comma splice and an unclear "Each".
- Lines 349-351: "The hosted tuning suite has ... Across 19 held-out tasks, it
  has 13/13 answers". Here "it" grammatically refers to the tuning suite. The
  held-out set is also mixed-provider, not hosted.
- Line 47: "Plan records steps and tools; consequential runs pause for review;
  Critique audits tool use; StepTrace records transitions." Four clauses are
  chained with semicolons, and `StepTrace` is never introduced.
- Lines 6 and 42: "(h19: calculator-guard error)" and "h19 a calculator-guard
  error" read as if h19 failed in the live run. It did not. The live h19 record
  has `status: refused`, and the refusal was triggered by the calculator guard.
- Lines 355-356: "used both bounded retries". `params.yaml` sets
  `max_execute_retries: 1`, so there were two attempts, not two retries. README
  line 94 says "both bounded-retry Execute visits".

### 4. Technical detail depth: 7

The technical content is good for an expert reader. It covers the typed
`WorkflowResult` statuses, the checkpoint resume excerpt, exact-set tool
grading with call precision and tool recall, the grader definitions, the cost
basis, and the split between provider and latency. Gaps:

- The p95 definition is wrong for n = 15 (lines 17-18 and 258-259). It says
  "95% of tasks finished within this time, is 31.1 s". Only 14/15 (93%)
  finished within 31.1 s, because t05 took 31.581 s (`metrics.json`
  `task_t05.latency_s`). Line 369, "Even the p95 task, t15, finishes at 31.1 s",
  implies t15 is the slowest task. It is not.
- Lines 194-195 say "Critique revises through Execute, never Plan", but the
  article never says what a Critique revision changes: arguments, the tool, or
  the answer.
- The `StepBudget` grader counts `steps_taken` entries (`evals.py:478`). The
  article does not explain what counts as a step. A reader cannot tell why h17
  reached 10 steps.

### 5. Truthfulness: 7

Most numbers trace to committed files. Verified: 15/15 on all four tuning
graders; median 18.227 s and p95 31.102 s; 85,174 input and 11,541 output
tokens; $0.1313 suite and $0.008756 per task at $1/$4 per Mtok; 30/30 planned
calls with precision and recall of 1.0; held-out 13/13, 5/6, 18/19, 12/19;
22 answer-task calls; hosted h01-h10 at 8.996-40.881 s; 7/9 local tasks over
60 s; h17 at 1,430.923 s and 10 steps; t15 at 7,709/862 tokens with zero
retries and `2022 - 1903` = 119; 12 handbook docs (`tools.py` `HANDBOOK`);
3,589 chunks (`01-rag-agent/DESIGN.md:239`); `max_steps=8`; the $0.25 and $2.00
caps; two repeat passes with one step miss each (README lines 111-125); and live
13/13, 6/6, 19/19 (`comparison.md`).

Untraceable or contradicted claims:

| Line(s) | Claim | Problem |
|---|---|---|
| 396 | "Across all 52 captured calls, none was unplanned." | **Contradicted.** 52 = 30 tuning + 22 held-out *answer-task* calls. The held-out probes made another 20 captured calls (h08: 2, h10: 3, h18: 12, h19: 3; `data/heldout_records.json`). That makes 72 captured calls in total, and probes have no planned set to match. |
| 521 | "All 52 captured calls matched planned tool sets in both suites." | Same overclaim, repeated in the roadmap. |
| 410 | "live efficacy is unmeasured" | **Contradicted** by the 2026-11-19 live run that the same article cites 5 times (6/6 refusals; `comparison.md`). |
| 497 | "about $0.10–0.15 per suite" | **Mixed bases, and the range is incomplete.** The record run is $0.131 on the metrics basis. Repeats were $0.148/$0.144 on the metrics basis and $0.10/$0.09 on the ledger basis (README lines 116-118). The $0.09 value falls outside the stated range, and the rest of the article says ~$0.13. |
| 17-18, 259 | "95% of tasks finished within this time" (31.1 s) | Only 14/15 (93%) finished within 31.1 s. t05 took 31.6 s. |
| 369 | "Even the p95 task, t15, finishes at 31.1 s." | This implies t15 is the slowest task. t05 (31.581 s) is slower. |
| 321-322 | "No hosted latency point crosses that line. The misses come from slow local generation" | This is attributed to the `cost_latency_bars` chart, which contains only the 15 tuning tasks and no misses. The fact is true for held-out, but the chart reference is wrong. |
| 6, 42, 268, 281, 359, 480 | "h19 a calculator-guard error" | This reads as a live failure. The live record is `status: refused`. It needs rewording, not new numbers. |

Count: **0 fully untraceable numbers**. **3 numbers are contradicted or
misstated**: "all 52 captured calls" (×2), "$0.10–0.15", and p95 "95% of tasks".
Two more framing errors are listed above (line 410 and the chart scope).

Note outside this file: README lines 27-30 and 152-153 still say a live
confirmation is "pending". The story cites the committed live run, so the README
is the stale document. Flag this for the owner. Do not change it under this
article review.

### 6. Roadmap cards: 7

All titles now start with a verb, and every detail is ≤90 characters. The
longest is 66 characters (line 515).

- Line 512: the detail "Offline regressions pass; the live run answers 13 of
  13." does not support the title "Pin typed outcomes and hard deadlines". The
  evidence for typed outcomes and deadlines is 6/6 refusals and 19/19 budgets,
  not answer preservation.
- Line 514: "Bound retries behind a human checkpoint" joins two separate
  mechanisms. Retries are capped by `max_execute_retries`, and the checkpoint is
  a separate approval gate. Retries do not sit behind the checkpoint.
- Line 521: this card repeats the "all 52 captured calls" overclaim.
- Line 524: the next card is sensible and honest. The gold template uses
  "Gate: ..." for next-step details, so this could become "Gate: owner-approved
  cap; published results are single runs." Consider a second next card for the
  provider-sensitive latency budget. It is the largest measured weakness (12/19)
  and has no roadmap item.

### 7. Consistency with gold template: 6

- **The In plain terms cards are number lists, not plain-language takeaways.**
  Gold example (01, line 19): "The assistant answers from checked passages or
  refuses honestly, holding unsupported answers to 1 in 120..." Here, line 53
  says "Legacy results: 15/15 fixed tasks, 13/13 held-out answers, 5/6 refusals,
  and about $0.13..." Lines 97-99, 140-142, and 381-383 follow the same "Label:
  list" pattern and mostly restate the bold lede.
- **The transitions are verbless fragments.** Gold uses full sentences with
  the link at the end: "Next, we set the rules each answer must clear
  ([Objectives →](#sec-objectives))." Here, line 50 reads "Next, the loop's
  testable targets ([Objectives →](#sec-objectives))." Lines 94, 137, 181, 275,
  330, and 378 use the same "X; next, the Y" fragment.
- The heading set in Conclusions (Results summary, What the experiment taught,
  Exact numbers, Protocol, Limits) is richer than the gold template. That is
  acceptable, but it amplifies the repetition noted above.

## Top 5 fixes (by severity)

1. **`story.yaml:396` and `story.yaml:521`: correct "all 52 captured calls".**
   Write "all 52 answer-task calls were planned (30 tuning, 22 held-out)". You
   may add that should-fail probes made 20 more calls and that probes are
   graded on refusal, not tool sets. As written, the claim is contradicted by
   `data/heldout_records.json`.
2. **`story.yaml:409-410`: remove "live efficacy is unmeasured".** Replace it
   with "one live run (2026-11-19) confirmed 6/6 refusals; repeat live runs
   remain unmeasured". This resolves the contradiction with lines 42, 266, 281,
   358, and 479.
3. **`story.yaml:6, 42, 267-268, 281-282, 358-359, 480`: reword "h19 a
   calculator-guard error".** Use "h19 refused after the calculator guard
   tripped". Say it once in full, in Training or Limits, and drop it from
   short_version, Background, and the In plain terms cards. As written, it
   reads as a live failure and repeats six times.
4. **`story.yaml:17-18, 259, 369`: fix the p95 framing.** Remove "meaning 95%
   of tasks finished within this time" and "Even the p95 task, t15". With
   n = 15, say "p95 31.1 s (nearest-rank); slowest task t05 at 31.6 s".
   Also reconcile `story.yaml:497` "$0.10–0.15 per suite" with the ~$0.13 used
   everywhere else, or state both bases.
5. **`story.yaml:318-324` and the In plain terms cards (lines 53, 97, 140, 184,
   278, 333, 381, 496): bring them to the gold standard.** Point the held-out
   latency sentence at the held-out data, not `cost_latency_bars`. Rewrite each
   In plain terms card as one interpretive sentence, as in 01 line 19. Convert
   the "X; next, the Y (…)" transitions into full sentences. In the same pass,
   repair the Wave 6.6 regressions at line 34 ("reviews its work"), line 37
   (fragment), lines 248-250 (comma splice), and line 350 ("it" refers to the
   tuning suite).
