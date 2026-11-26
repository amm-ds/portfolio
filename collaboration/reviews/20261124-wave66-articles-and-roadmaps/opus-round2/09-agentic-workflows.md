# Round-2 review: 09-agentic-workflows story.yaml

Reviewer: Claude Code (Opus), read-only. No repository file was edited.
Target: `projects/09-agentic-workflows/story.yaml` at HEAD (451 lines; last
touched in `e69bba84`). Gold template: `projects/01-rag-agent/story.yaml`.
Round 1: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/09-agentic-workflows.md`
(graded the 530-line `18adc59d` version). Line numbers below refer to the
current 451-line file.

Evidence I re-checked myself: `reports/metrics.json` (per-task latencies,
`agentic_suite`, `detail.tooling`, `detail.heldout`), `data/run_records.json`,
`data/heldout_records.json`, `data/tasks.json`, `data/tasks_heldout.json`,
`params.yaml`, all four `reports/figures/*.json`, `README.md`, and the committed
`collaboration/reviews/20261118-live-confirmation/{comparison.md,heldout_live_records.json}`.

## Grades

| # | Dimension | R1 | R2 |
|---|---|---|---|
| 1 | Structure and article logic | 6 | 6 |
| 2 | Engagement and human-like narrative | 5 | 6 |
| 3 | Language quality | 5 | 6 |
| 4 | Technical depth | 7 | 7 |
| 5 | Truthfulness | 7 | 6 |
| 6 | Roadmap cards | 7 | 6 |
| 7 | Consistency with gold template | 6 | 7 |
| | **Overall** | **6** | **6** |

Truthfulness and roadmap drop by one point. The defects are the same ones as
in round 1, but this round added a live-rerun comparison row (line 309) and
"In plain terms" summaries that rely on those claims, so the errors now carry
more weight.

### 1. Structure and article logic: 6

The arc (background, objectives, data, EDA, training, evaluation, results,
conclusions) is sound, and the new Results table (lines 305-309) is a real
improvement. It sets legacy and live outcomes side by side. Problems:

- **The live thread still contradicts itself.** Lines 21, 204, 283, 309, 311,
  and 404 cite the 2026-11-19 live run. Line 335 still says "live efficacy is
  unmeasured".
- **The Evaluation chart paragraph still describes data the chart lacks.**
  Lines 247-251 send the reader to the cost-and-latency chart and say "No
  hosted latency point crosses that line. The misses come from slow local
  generation". `reports/figures/cost_latency_bars.json` holds only t01-t15.
  The chart has no held-out points and no misses.
- **Line 26 promises four steps and lists three bullets** (lines 28-30). This
  is a new defect: "Checkpoint & Execute" and "Critique & Trace" were merged.
- **The legacy and live comparison is not like-for-like, and the article does
  not say so.** Legacy held-out ran 10 tasks hosted and 9 local. Per
  `comparison.md`, the live rerun ran all 19 on hosted `kimi-for-coding`. The
  live 19/19 latency row (line 309) therefore reflects a provider change, not a
  fix. Line 311 should not imply otherwise.
- Repetition is reduced but still heavy. "$0.13" or "13 cents" appears 10
  times (lines 2, 15, 21, 34, 203, 211, 251, 295, 323, 421). Evaluation,
  Results, and Conclusions each restate cost and latency.

### 2. Engagement and human-like narrative: 6

The opening now states a use case: "fits supervised pilots, not unattended
runs" (line 21). The "In plain terms" cards are real sentences. The t15 trace
and the `hitl.py` excerpt remain the most concrete passages. Still weak:

- Seven "Follow ..." reading instructions (lines 26, 62, 93, 124, 232, 386,
  391).
- Inline glossary definitions interrupt the prose: "Deterministic code gives
  the same output..." (43-44), "A schema is..." (53-54), "A corpus is..."
  (75), "Open weights are..." (241-242), and the AST/FAISS/MiniLM/
  PrefixedToolset glossary (346-350). The key-concepts list already covers
  most of these.
- There is still no sentence on what a fabricated number or an unplanned call
  would cost a research-ops team.

### 3. Language quality: 6

Fixed: the clipped list ("reviews its work") and the opening fragment
("Held-out: 13/13 ...") are gone. Still present or new:

- Lines 197-199: the comma splice ("...identifies the measured work, the
  numbers come from recorded runs. Each has a limit:") is unchanged.
- Lines 272-275: in "The hosted tuning suite has ... Across 19 held-out tasks,
  it has `13/13` answers", "it" refers to the tuning suite.
- Six of seven transitions are still verbless "X; next, the Y (...)" fragments
  (lines 32, 66-67, 97-98, 133-134, 208-209, 259-260).
- Line 413: "up to 1,`430.9 s`" has a broken code span, so the comma renders
  outside it.
- Lines 242 and 399: "`$0.00.`" puts the full stop inside the code span.
- Line 270: "`18/19` and 12/19" formats the two values inconsistently.
- Lines 4, 284, and 405: "h19 a calculator-guard error" still reads as a live
  failure. The live record has `status: refused`.

### 4. Technical depth: 7

The typed `WorkflowResult` statuses, the checkpoint-resume code, exact-set
tool grading with precision and recall, the grader definitions (lines
391-397), and the cost basis are all strong. Gaps from round 1 remain:

- The p95 explanation is wrong for n = 15 (line 11). See Truthfulness.
- The article never says what a Critique revision changes (lines 143, 154).
- It never says what counts as a "step" for `StepBudget` (line 394). A reader
  cannot see why h17 reached 10 steps. `heldout_records.json` shows
  retries = 1 and critique_loops = 1 for h17, which would explain it in one
  clause.

### 5. Truthfulness: 6

Verified against committed files: 15/15 on all four tuning graders; median
18.227 s (the median of the 15 per-task latencies); p95 31.102 s
(`agentic_suite.p95_latency_s`); 85,174 input and 11,541 output tokens; $0.1313
per suite and $0.008756 per task at $1/$4 per Mtok (`params.yaml`); 30/30
planned tuning calls; held-out 13/13, 5/6, 18/19, and 12/19, with 22
answer-task calls; hosted h01-h10 at 8.996-40.881 s; 7/9 local tasks over 60 s;
h17 at 1,430.923 s and 10 steps; t15 at 7,709/862 tokens with two
`search_documents` calls and `2022 - 1903`; zero retries in the record run;
five task categories with 1-3 expected tools; $0.25 and $2.00 caps; two hosted
repeats at 15/15 with one step miss each (README 111-125); and live 13/13, 6/6,
19/19 (`comparison.md`, `heldout_live_records.json`).

Contradicted or misleading claims:

| Line(s) | Claim | Problem |
|---|---|---|
| 321 | "Across all 52 captured calls, none was unplanned." | **Contradicted.** `heldout_records.json` holds 42 held-out calls: 22 answer-task calls and 20 probe calls (h08 2, h10 3, h18 12, h19 3). The total is 72, not 52. The probes have no planned set. |
| 448 | "All 52 captured calls matched planned tool sets in both suites." | Same overclaim, repeated in the roadmap. |
| 335 | "live efficacy is unmeasured" | **Contradicted** by the 2026-11-19 live run that the article cites six times. |
| 11 | "p95 ... meaning 95% of tasks finished within this time, is 31.1 s" | 14/15 (93%) finished within 31.1 s. t05 took 31.581 s (`metrics.json task_t05`). |
| 294 | "Even the `p95` task, t15, finishes at 31.1 s." | This implies t15 is the slowest task. t05 is slower. |
| 280 | "used both bounded retries" | `max_execute_retries: 1`. Those were two attempts with one retry. The live error string reads "execute failed after 2 attempts". |
| 247-251 | "No hosted latency point crosses that line. The misses come from slow local generation" | This is attributed to `cost_latency_bars`, which holds only tuning tasks. The fact is true for held-out data, but the figure reference is wrong. |
| 4, 284, 405 | "h19: calculator-guard error" in the live context | The live h19 record has `status: refused`. The error text exists, but the phrasing reads as a failure. |
| 309, 311 | Live 19/19 latency "closed" the gap | Live ran all 19 tasks hosted. Legacy ran 9 on a local model. The comparison is not like-for-like, and the article does not disclose that. |

Count: **0 fully untraceable numbers**. There are **5 contradicted numeric
claims**: "52 captured calls" (×2, lines 321 and 448), "95% of tasks" (11),
"p95 task t15" (294), and "both bounded retries" (280). There are also 4
framing errors (335, 247-251, the h19 wording, and the 309/311 provider
mismatch).

Outside this file: README lines 27-30 and 150-154 still say live confirmation
is "pending", but committed `comparison.md` shows it ran. The README is stale.
This note is for the owner and is not in scope for this article.

### 6. Roadmap cards: 6

All five titles start with a verb, and every detail is ≤90 characters (the
longest is 66). Status problems:

- Line 438-439: the detail ("Offline regressions pass; the live run answers
  13 of 13.") does not support the title "Pin typed outcomes and hard
  deadlines". The evidence for the title is 6/6 refusals and 19/19 budgets.
- Line 441: "Bound retries behind a human checkpoint" merges two separate
  mechanisms. `max_execute_retries` is one, and the approval gate is another.
- Line 448: the "shipped" claim "All 52 captured calls matched planned tool
  sets" is contradicted by the repo.
- Line 451: the next card does not use the gold "Gate: ..." form. The
  provider-sensitive latency budget, the weakest legacy result at 12/19, still
  has no card.

### 7. Consistency with the gold template: 7

The "In plain terms" cards are now interpretive sentences, which matches gold
line 20. That is the main gain this round. Gaps remain:

- Gold transitions are full sentences ("Next, we set the rules each answer must
  clear ([Objectives →]...)"). Six of seven here are verbless fragments.
- The gold `short_version` is one readable line with headline numbers. The
  short_version here (lines 2-4) packs two runs and a parenthetical about h19.
- Gold places `figure_captions` after `roadmap`, while this file places them
  first. Either order works, but the gold order is the house style.

## Round-1 finding status

| # | Round-1 finding | Status | Current evidence |
|---|---|---|---|
| 1 | Live thread contradiction ("live efficacy is unmeasured") | STILL PRESENT | Line 335 |
| 2 | Evaluation paragraph attributes held-out misses to `cost_latency_bars` | STILL PRESENT | Lines 247-251 |
| 3 | Repetition of cost, latency, and h19 across sections | PARTLY FIXED | $0.13 ×10, 18.2 ×4, h19 guard ×4 |
| 4 | Background opens with a number dump | PARTLY FIXED | Line 21 adds the use case, but the numbers follow in one sentence |
| 5 | Inline definitions interrupt the prose | PARTLY FIXED | JSON and token definitions removed; 43, 53, 75, 241, 346-350 remain |
| 6 | Six "Follow ..." openers | STILL PRESENT | Now 7 |
| 7 | No reason given for why a research-ops team should care | PARTLY FIXED | Line 21 states the pilot scope; cost of failure still not stated |
| 8 | "reviews its work" clipped list | FIXED | Line 21 rewritten |
| 9 | "Held-out: 13/13 ..." fragment | FIXED | Line 21 is a full sentence |
| 10 | Comma splice "the diagram identifies ..., the numbers come ..." | STILL PRESENT | Lines 197-199 |
| 11 | "it" refers to the tuning suite | STILL PRESENT | Lines 273-275 |
| 12 | Semicolon chain; `StepTrace` never introduced | PARTLY FIXED | Now bullets; `StepTrace` still undefined (21, 30) |
| 13 | h19 "calculator-guard error" reads as a live failure | PARTLY FIXED | 6→4 mentions; still in live context at 4, 284, 405 |
| 14 | "used both bounded retries" | STILL PRESENT | Line 280 |
| 15 | p95 "95% of tasks" and "p95 task t15" | STILL PRESENT | Lines 11, 294 |
| 16 | Critique revision content undefined | STILL PRESENT | Lines 143, 154 |
| 17 | Step counting for `StepBudget` undefined | STILL PRESENT | Line 394 |
| 18 | "all 52 captured calls" (conclusions) | STILL PRESENT | Line 321 |
| 19 | "all 52 captured calls" (roadmap) | STILL PRESENT | Line 448 |
| 20 | "$0.10–0.15 per suite" mixes bases | FIXED | Removed |
| 21 | Roadmap card 1 detail does not support the title | STILL PRESENT | Line 439 |
| 22 | "Bound retries behind a human checkpoint" merges mechanisms | STILL PRESENT | Line 441 |
| 23 | Next card lacks "Gate:" form and a latency card | STILL PRESENT | Line 451 |
| 24 | In plain terms cards are number lists | FIXED | Lines 34, 69, 100, 136, 211, 262, 311, 421 |
| 25 | Transitions are verbless fragments | STILL PRESENT | 32, 66, 97, 133, 208, 259 |
| 26 | README says live confirmation is "pending" (out of scope) | STILL PRESENT | README 27-30, 150-154 |

Totals: 4 fixed, 6 partly fixed, 16 still present (15 in the story, plus the
out-of-scope README note).

New in round 2: the "four steps" list has three bullets (26-30); the
legacy-vs-live table does not disclose the provider change (309, 311); and
line 413 has a broken code span.

## Top 5 remaining fixes (by severity)

1. **Lines 321 and 448: correct "52 captured calls".** Write "all 52
   answer-task calls (30 tuning, 22 held-out) were planned; the 6 probes made
   20 further calls, graded on refusal rather than tool sets." As written, the
   claim is contradicted by `data/heldout_records.json`. It also appears in a
   "shipped" card.
2. **Line 335: remove "live efficacy is unmeasured".** Replace it with "one
   live run (2026-11-19) confirmed 6/6 refusals; repeat live runs are
   unmeasured." In the same pass, reword h19 at lines 4, 284, and 405 to "h19
   refused after the calculator guard tripped". At line 280, change "both
   bounded retries" to "both Execute attempts (one retry)".
3. **Lines 11 and 294: fix the p95 framing.** Drop "meaning 95% of tasks
   finished within this time" and "Even the p95 task, t15". Write "p95 31.1 s
   (nearest-rank, n = 15); slowest task t05 at 31.6 s."
4. **Lines 247-251 and 309-311: fix the latency evidence.** Point the held-out
   latency sentence at the held-out records or the Results table, not
   `cost_latency_bars`. Add one clause to the live row or line 283 saying that
   the live rerun ran all 19 tasks on the hosted endpoint, so 19/19 latency is
   not a like-for-like fix of the 7 local misses.
5. **Lines 438-451: repair the roadmap and prose.** Card 1 detail: "6/6 live
   refusals; 19/19 budgets; offline regressions pass." Card 2: split into
   "Gate consequential runs behind human approval" with the detail "Retries
   capped at one per Execute." The next card should read "Gate: owner-approved
   cap; results are single runs." Add a next card for a provider-aware latency
   budget. In the same pass, fix line 26 ("four steps" → "three steps"), the
   comma splice at 197-199, the "it" at 274, the code span at 413, and the
   verbless transitions.

## Ready to publish?

**No.** The article still contains five numeric claims contradicted by
committed files, one of them in a "shipped" roadmap card. It also still
contradicts itself on whether live efficacy was measured. All of these fixes
are text edits; none needs a new run.
