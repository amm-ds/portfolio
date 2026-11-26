# Round-3 review: 09-agentic-workflows story.yaml

Reviewer: Claude Code (Opus), read-only. No repository file was edited apart
from this review.
Target: `projects/09-agentic-workflows/story.yaml`, **working tree** (454 lines;
uncommitted Wave 8 edits on `wave8-articles-truthfulness-2026-11-25`, HEAD
`c05accd0`). Gold template: `projects/01-rag-agent/story.yaml`.
Round 2: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/09-agentic-workflows.md`.
Line numbers below refer to the current working-tree file.

Evidence I re-checked myself (all tracked by git unless noted):
`reports/metrics.json` (per-task latencies, `agentic_suite`, `detail.tooling`,
`detail.heldout`), `data/run_records.json`, `data/heldout_records.json`,
`data/tasks.json`, `data/tasks_heldout.json`, `params.yaml`,
`reports/figures/{suite_summary,node_waterfall,cost_latency_bars}.json`,
`reports/kimi_comparison.json`, `README.md` (working tree),
`src/agentic_workflows/{report.py,workflow.py,hitl.py,tools.py,schemas.py,evals.py}`,
`tests/test_hitl.py`,
`collaboration/reviews/20261118-live-confirmation/{comparison.md,heldout_live_records.json}`,
and project 01's `DESIGN.md` / `reports/retrieval_tournament/results.json`
(3,589 chunks). `data/checkpoint.json` exists locally but is **gitignored**
(`.gitignore:15 data/`), so it does not count as committed evidence.

## Grades

| # | Dimension | R2 | R3 |
|---|---|---|---|
| 1 | Structure and article logic | 6 | 7 |
| 2 | Engagement and human-like narrative | 6 | 6 |
| 3 | Language quality | 6 | 6 |
| 4 | Technical depth | 7 | 7 |
| 5 | Truthfulness | 6 | 7 |
| 6 | Roadmap cards | 6 | 8 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | **6** | **7** |

Wave 8 fixed every finding round 2 ranked in its top five except the p95
framing, which it half-fixed and mislabelled. The remaining problems are one
cost misattribution in the opening paragraph, a checkpoint claim backed only
by a gitignored placeholder file, the new "nearest-rank" label, and the
long-standing prose issues.

### 1. Structure and article logic: 7

Improvements: the "three steps" count now matches the three bullets (26-30);
the Evaluation paragraph (247-251) now says the cost chart holds only the 15
tuning tasks; the Results section adds a paragraph (309-311) saying the live
rerun ran all 19 tasks on the hosted endpoint, so its 19/19 latency is not a
like-for-like fix; Conclusions (337-338) now agree with the live thread.

Remaining:

- Cost and latency are still restated in Background, Training, Evaluation,
  Results, and Conclusions. "$0.13" or "13 cents" appears 9 times (15, 21, 34,
  203, 211, 250, 293, 325, 424) and "18.2 s" 5 times.
- The provider caveat lives only in Results (309-311). The short_version (3),
  Background (21), and roadmap card 1 (442) still quote "19/19 budgets"
  without saying the live run was all-hosted.
- Line 248, "The separate held-out records show", points nowhere. Name the
  table at 303-307 or `data/heldout_records.json`.

### 2. Engagement and human-like narrative: 6

Unchanged since round 2. The `hitl.py` excerpt and the t15 trace are still the
most concrete passages, and the "In plain terms" cards read as real sentences.
Still weak:

- Seven "Follow ..." reading instructions (26, 62, 93, 124, 232, 389, 394).
- Inline glossary sentences still interrupt the prose: 43-44 (deterministic),
  53-54 (schema), 75 (corpus), 241-242 (open weights), 349-353 (AST, FAISS,
  MiniLM, PrefixedToolset).
- There is still no sentence on what a fabricated number or an unplanned
  tool call would cost a research-ops team. The gold opener earns attention
  with exactly this kind of stake ("a model can misread a source or stitch
  two facts into a false bridge").

### 3. Language quality: 6

Fixed: the broken code spans (`$0.00.`, `1,`430.9 s``), the inconsistent
`18/19` / 12/19 formatting, the "both bounded retries" phrasing, and the h19
"calculator-guard error" wording.

Still present or new:

- 197-199: the comma splice is unchanged ("the diagram identifies the measured
  work, the numbers come from recorded runs. Each has a limit:").
- 272-274: "The hosted tuning suite has ... Across 19 held-out tasks, it has
  `13/13` answers": "it" still refers to the tuning suite.
- Six of seven transitions are still verbless "X; next, the Y" fragments (32,
  66-67, 97-98, 133-134, 208-209, 257-258). Gold uses full sentences ("Next,
  we set the rules ...").
- New, 2: "15/15 fixed runs" calls tasks "runs". It was one run of 15 fixed
  tasks.
- New, 313: "without calling a single extra answer-task tool" is clumsy. Try
  "with no unplanned tool calls on answer tasks".
- New, 442: "Live checks" (plural) describes a single live run.
- `StepTrace` (21, 30) is still never explained for the reader.

### 4. Technical depth: 7

Strong as before: typed `WorkflowResult` statuses, the verified `hitl.py`
excerpt (every quoted line exists in `src/agentic_workflows/hitl.py`),
exact-set tool grading with precision and recall, grader definitions (395-400),
and the cost basis. The retry semantics are now correct. Gaps remain:

- What a Critique revision changes is still unstated (143-144, 154).
- What `StepBudget` counts is still unstated (397). The code counts
  `steps_taken` entries (`evals.py:478`). h17's 10 entries are plan, execute,
  draft, critique, revise, execute ×2, draft, critique, pass, which explains the
  only step miss in one clause.
- The p95 method is now named, but named wrongly (see Truthfulness).

### 5. Truthfulness: 7

Verified this round: 15/15 on all four tuning graders; median 18.227 s (8th of
15 sorted latencies); `p95_latency_s` 31.102 (t15) and t05 slowest at 31.581;
85,174 input and 11,541 output tokens; $0.1313 suite and $0.008756 per task at
$1/$4 per Mtok; 30/30 planned tuning calls, precision and recall 1.0; held-out
13/13 answers, 13/13 exact sets, 5/6 refusals, 18/19 steps, 12/19 latency; 22
answer-task calls plus 20 probe calls (h08 2, h10 3, h18 12, h19 3); hosted
h01-h10 at 8.996-40.881 s; 7/9 local tasks over 60 s; h17 at 1,430.923 s and
10 steps; legacy h19 with two Execute attempts (`retries` = 2 failed attempts
against `max_execute_retries: 1`, so one retry), status `ok`, and no
refusal marker; live h19 `status: refused` with "execute failed after 2
attempts: exponent too large"; live 13/13, 6/6, 19/19, all hosted
(`comparison.md` run command uses `kimi-for-coding`); t15 at 7,709/862 tokens,
two `search_documents` calls, then `2022 - 1903`, zero retries; 12 handbook
documents (`tools.py`); 3,589 chunks (project 01 DESIGN.md and
`results.json`); $0.25 and $2.00 caps; 8-step default; two hosted repeat
passes at 15/15 with one step miss each (README "Repeat stability").

Contradicted, mislabelled, or untraceable claims:

| Line(s) | Claim | Problem |
|---|---|---|
| 21 | "Held-out legacy runs hit `13/13` answers, ... `12/19` time caps at `~$0.13` of the `$2.00` cap" | **Misattributed number.** $0.13 is the 15-task *tuning* suite (`agentic_suite.est_cost_usd_per_task` × 15 = $0.1313). No committed file reports a held-out suite cost. The held-out records give about $0.084 for the 10 hosted tasks at the same rate card and $0 for the local tasks. Pre-existing; round 2 missed it. |
| 11, 292 | "Nearest-rank p95 latency is 31.1 s over 15 tasks" / "The nearest-rank `p95` is t15 at `31.1 s`" | **Mislabelled method (new in Wave 8).** Standard nearest-rank p95 is rank ⌈0.95·15⌉ = 15, which gives t05 at 31.581 s. `report.py:221-225` uses `sorted(d)[round(0.95·(n−1))]` = index 13, i.e. the "nearest" interpolation method, which gives t15 at 31.102 s. The number is right for the code, but the label is wrong. |
| 206, 373 | "A recorded run demonstrates pause, reject-with-feedback, and re-plan" / "`data/checkpoint.json` shows pause, reject-with-feedback, and re-plan" | **Untraceable to committed evidence.** `data/checkpoint.json` is gitignored. The local copy holds a scripted placeholder (plan steps "step 1/2/3", `expected_output: "x"`, findings `["f"]`, `status: awaiting_approval` while `steps_taken` already shows a rejection and execution). That is test-model output, not a recorded run. The only committed evidence is `tests/test_hitl.py::test_reject_replans_with_feedback` (scripted model). Pre-existing; round 2 missed it. |
| 34 | "cost about 13 cents for the whole test suite" | Framing. It follows the held-out numbers, so a reader takes "whole test suite" to include them. It is the 15-task practice suite. |
| 442 | "Live checks pass 6/6 refusals and 19/19 step and time budgets" (under "hard deadlines") | Framing. One all-hosted run with 0/19 deadline cancellations (`comparison.md`). It shows budgets were met but never exercised the deadline. The deadline evidence is the offline tests. |

Count: **0 numbers with no source at all**. There are **2 contradicted or
mislabelled numeric claims**: $0.13 for held-out (21), and the "nearest-rank"
p95 (11 and 292, counted once). There is **1 untraceable non-numeric claim**:
the recorded checkpoint run (206, 373). There are also 2 framing issues (34,
442).

### 6. Roadmap cards: 8

All five titles start with a verb. Every detail is ≤90 characters (the longest
is 66). The "52 captured calls" overclaim is gone. Card 4 now reads "52
answer-task calls match plans; 20 probe calls are refusal-graded", which
`heldout_records.json` and `detail.tooling` confirm. Card 2 now separates the
approval gate from the retry cap, and both match code (`max_execute_retries:
1`, `save_checkpoint`). The next card uses the gold "Gate: ..." form and names
latency caps and a provider matrix, which covers the provider-sensitive budget
round 2 asked for.

Residual: card 1 (442) supports "hard deadlines" with a single all-hosted run
in which no deadline fired, and says "checks" for one run. Suggested detail:
"Offline deadline tests pass; one hosted live run: 6/6 refusals, 19/19
budgets." (78 characters.)

### 7. Consistency with the gold template: 7

Matches: section order, the "In plain terms" closers, the shipped and next
card shapes, and the "Gate:" next card. Gaps:

- Transitions are verbless fragments in six places (see Language).
- `figure_captions` still comes before `sections`. Gold puts it after
  `roadmap` (gold lines 269-285).
- The short_version (2-4) is shorter but still packs two runs and an h19 note.
  The gold short_version is a single run of headline numbers.

## Round-2 finding status

| # | Round-2 finding | Status | Working-tree evidence |
|---|---|---|---|
| 1 | "live efficacy is unmeasured" contradicts the live run | FIXED | 337-338: "one live confirmation; repeated live efficacy remains unmeasured" |
| 2 | Evaluation paragraph attributes held-out misses to `cost_latency_bars` | FIXED | 247-251 say the chart is tuning-only |
| 3 | Repetition of cost, latency, and h19 | PARTLY FIXED | $0.13 ×9, 18.2 s ×5; h19 guard ×4 but now correctly worded |
| 4 | Background opens with a number dump | PARTLY FIXED | Unchanged; line 21 still packs eight figures into one sentence |
| 5 | Inline definitions interrupt the prose | PARTLY FIXED | Unchanged: 43-44, 53-54, 75, 241-242, 349-353 |
| 6 | "Follow ..." openers | STILL PRESENT | 7 instances (26, 62, 93, 124, 232, 389, 394) |
| 7 | No reason why a research-ops team should care | PARTLY FIXED | Pilot scope stated (21); cost of failure still absent |
| 8 | "reviews its work" clipped list | FIXED | — |
| 9 | "Held-out: 13/13 ..." fragment | FIXED | — |
| 10 | Comma splice 197-199 | STILL PRESENT | 197-199 |
| 11 | "it" refers to the tuning suite | STILL PRESENT | 272-274 |
| 12 | `StepTrace` never introduced | PARTLY FIXED | Bullets kept; `StepTrace` still undefined (21, 30) |
| 13 | h19 "calculator-guard error" reads as a live failure | FIXED | 4, 282, 408 say "refused after the calculator guard tripped" |
| 14 | "used both bounded retries" | FIXED | 278: "two Execute attempts (one retry)"; matches `workflow.py:280-287` |
| 15 | p95 "95% of tasks" and "p95 task t15" | PARTLY FIXED | "95% of tasks" removed and t05 disclosed (11, 292), but the new "nearest-rank" label is wrong |
| 16 | What a Critique revision changes is undefined | STILL PRESENT | 143-144, 154 |
| 17 | What `StepBudget` counts is undefined | STILL PRESENT | 397, 416-417 |
| 18 | "all 52 captured calls" (Conclusions) | FIXED | 323-324: 52 answer-task calls plus 20 probe calls |
| 19 | "all 52 captured calls" (roadmap) | FIXED | 451 |
| 20 | "$0.10-0.15 per suite" mixes bases | FIXED | — |
| 21 | Roadmap card 1 detail does not support the title | FIXED | 442 (minor residual: single run, deadline unexercised) |
| 22 | Card 2 merges retries and the checkpoint | FIXED | 444-445 |
| 23 | Next card lacks "Gate:" form; no latency card | FIXED | 453-454 name latency caps and a provider matrix |
| 24 | In plain terms cards are number lists | FIXED | — |
| 25 | Transitions are verbless fragments | STILL PRESENT | 32, 66-67, 97-98, 133-134, 208-209, 257-258 |
| 26 | README says live confirmation is "pending" (out of scope) | FIXED | README 29-31, 154 (working tree) |
| R2-a | "four steps" over three bullets | FIXED | 26 |
| R2-b | Legacy vs live provider mismatch undisclosed | FIXED | 307, 309-311 (not carried to 3, 21, 442) |
| R2-c | Broken code spans and number formatting | FIXED | 242, 268, 402, 416 |
| G-1 | `figure_captions` placed before `sections`, unlike gold | STILL PRESENT | 5-16 |
| G-2 | short_version packs two runs plus an h19 note | PARTLY FIXED | 2-4 shorter, same structure |

Totals: 17 FIXED, 7 PARTLY FIXED, **7 STILL PRESENT** (6, 10, 11, 16, 17, 25,
G-1).

## New errors introduced by Wave 8

1. **11, 292: "Nearest-rank p95".** The method label is wrong. True
   nearest-rank for n = 15 gives the maximum (t05, 31.581 s). The code uses the
   rounded-index method. Drop the label or say "p95 (rounded-index, n = 15)".
2. **442: card 1 detail.** "Live checks" is plural for one run, and 19/19 budgets
   from an all-hosted run with zero deadline firings is offered as evidence for
   "hard deadlines".
3. **2: "15/15 fixed runs".** This mislabels 15 fixed tasks in one run.
4. **313: "a single extra answer-task tool".** Clumsy compound phrasing.
5. **248: "The separate held-out records show"** gives no pointer to where the
   reader can see them.

None of the Wave 8 edits introduced a wrong count.

## Top 5 remaining fixes

1. **Line 21 (and 34): move $0.13 to the tuning clause.** Rewrite as
   "Legacy tuning passed 15/15 at ~$0.13 of the $2.00 cap; held-out legacy runs
   hit 13/13 answers, 5/6 refusals, 18/19 step caps, and 12/19 time caps." At
   34, write "about 13 cents for the 15-task practice suite".
2. **Lines 206 and 373: re-source the checkpoint claim.** `data/checkpoint.json`
   is gitignored and holds scripted placeholder data. Either write "A scripted
   test (`tests/test_hitl.py`) demonstrates pause, reject-with-feedback, and
   re-plan; no live checkpoint run is recorded", or have the owner commit a
   real recorded checkpoint.
3. **Lines 11 and 292: fix the p95 label.** For example: "p95 is 31.1 s (t15,
   rounded-index method over 15 tasks); the slowest task, t05, took 31.6 s."
4. **Lines 153-154, 397, 416-417, and 21: add the missing mechanics.** Say in
   one clause that `StepBudget` counts recorded graph steps (plan, execute,
   draft, critique, and revise entries) and that h17's critique revision
   added a second Execute pass, reaching 10. Say what a Critique revision sends
   back to Execute. Define `StepTrace` in one phrase at first use.
5. **Prose pass: 197-199, 272-274, 32/66/97/133/208/257, 442.** Fix the comma
   splice, replace "it" with "the held-out run", turn the six transitions into
   full "Next, we ..." sentences, and change card 1 to "Offline deadline tests
   pass; one hosted live run: 6/6 refusals, 19/19 budgets." Optionally move
   `figure_captions` after `roadmap` to match gold.

## Ready to publish?

**No, but it is close.** Wave 8 removed every contradicted count from round
2. Three truthfulness defects remain, all text-only fixes:

- The opening paragraph attributes the tuning-suite cost to the held-out runs
  (21).
- The checkpoint demonstration cites a gitignored placeholder file as a
  "recorded run" (206, 373).
- The new "nearest-rank" p95 label is wrong (11, 292).

Once fixes 1-3 land, the article clears the truthfulness bar. Fixes 4-5 lift
depth and prose but do not block publication.
