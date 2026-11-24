# Deep review: RAG 01 article (story, README, DESIGN, docs page, figures)

Date: 2026-11-24
Reviewer: Claude Code (designer/reviewer lane). Read-only: no article, story,
README, tracker or implementation file edited; no git mutation; no hosted LLM
or paid API call. Local reads and `uv run python scripts/lint_story_language.py`
only.
Repo state: `main` @ `8833358c` (clean at session start).
Supersedes nothing. It re-checks `collaboration/reviews/20261124-rag-article-review/00-review.md`
(written at `2a7d9b7a`, four commits earlier) and goes deeper on truth,
technical precision and figures.

Legend: **[V]** verified this session by reading the file or running a
command. **[I]** inference. File references are `path:line` at `8833358c`.

---

## 0. Which surface is "the article"

| Surface | Role per `docs/engineering/repo-conventions.md` | Reviewed as |
|---|---|---|
| `projects/01-rag-agent/story.yaml` (267 lines) | "the case study"; rendered as the web article by `StorySection.tsx` with diagrams from `apps/showcase-web/src/diagrams/` and figures from `reports/figures/*.json` | **Main article** |
| `projects/01-rag-agent/README.md` (321 lines) | operational and evidence snapshot | Secondary, cohesion and truth |
| `docs/projects/01-rag-agent.md` (216 lines) | mkdocs project page; the story's last link points here (`story.yaml:231`) | Secondary, cohesion and figures |
| `projects/01-rag-agent/DESIGN.md` (414 lines) | history and alternatives | Secondary, cohesion only |
| `apps/showcase-web/src/lib/cardCopy.ts:13-14,44-45` | `/projects` card | Spot check |
| Diagrams `diagrams/ragPipeline.ts`, `diagrams/auto/01-rag-agent-{1..4}.ts` | embedded in story sections | Text-versus-image |

Story lint: `lint-story-language: 13 stories — 0 errors, 0 warnings` [V].

### What changed since the earlier review (claims re-verified)

| Earlier claim | State now |
|---|---|
| Results `metrics_keys` render tuning numbers (C7) | **Resolved.** No `metrics_keys` in `story.yaml` [V]. |
| "$2.0392" spend in story/README/docs (C1) | **Resolved in public copy**: story, README:102 and docs:88 now use `$1.014` / `$1.458`. **Still in `DESIGN.md:413`** and untraceable: no committed report contains 2.0392; `experiment_log.json` carries a per-step `cumulative_usd_est` that reaches only 0.094784 for judge labelling [V]. |
| "won every development split" (C2) | **Mostly resolved** (`story.yaml:92` now says all-articles@5 led; recall@5 did not win everywhere). New over-claim at `story.yaml:90` (section 3, T6). |
| "1 unsupported claim in 120" unit (C4) | **Fixed in story and card** ("1 of 120 answers", `story.yaml:163`, `cardCopy.ts:45`). **Still wrong** in `README.md:15-16`, `docs/projects/01-rag-agent.md:13-14`, `DESIGN.md:412`; ambiguous "1/120 unsupported" in `short_version` (`story.yaml:2`). |
| Faithfulness pair (C8/known issue) | **Correct everywhere public**: `[0.8092, 0.9304]` at `story.yaml:161,170`, `README.md:98`, `docs:84`, matching `reports/final_v3_e2e/metrics.json` → `detail.final_v3.faithfulness.ci95` [V]. Stale `[0.7983, 0.9155]` survives only in `collaboration/` history files [V]. |
| Self-judging undisclosed (C8) | **Now disclosed** at `story.yaml:143,192` and `:186`. |
| final_v3 called "sealed" (C9) | **Partly fixed**: disclosure added (`story.yaml:143,191`), but contradicted at `story.yaml:156` and `:235` (section 3, T1). |
| Owner hand-label pending (C10) | **Disclosed correctly** at `story.yaml:141,147,192,252`. Still not done: `owner_sample_validated.json` → `validated_by: "claude-role-audit (pending human owner hand-label confirmation)"` [V]. |
| Final latency missing (C12) | **Resolved** (`story.yaml:40,164`). |

---

## 1. Verdict in one paragraph

The story is a well-instrumented, mostly traceable case study: every headline
number in Results (`story.yaml:155-173`) matches `reports/final_v3_e2e/` to
four decimals [V]. It falls short in three ways. First, four sentences state
things the code or reports contradict: the final set is called "never used
during retrieval tuning" (`:156`), the 0.6 floor is described as a per-claim
score (`:30`, `:236`), the earlier judge's 44% miss rate uses the wrong
denominator (`:140`), and 33 skipped verifications are called "short
answers" (`:142`). Second, the pictures lag the system: four of the five
diagrams predate S3 and final_v3, and all three Evaluation figures are
tuning-era charts the Evaluation text never mentions. Third, the prose is
uniform bold-label bullets with a justification clause, which reads as
generated. **Overall 3 / 5.**

---

## 2. Scores

| # | Dimension | Score |
|---|---|:---:|
| 1 | Components | 4 |
| 2 | Engagement | 3 |
| 3 | Language | 3 |
| 4 | Article logic | 2 |
| 5 | Text versus images | 2 |
| 6 | Cohesion across surfaces | 2 |
| 7 | Truthfulness against code and results | 3 |
| 8 | Human-like narrative | 2 |
| 9 | Technical details | 3 |
| 10 | Overall quality | 3 |

**1. Components: 4.** Problem (`story.yaml:6-7`), targets set before tuning
(`:22-40`), data and question sets (`:46-63`), corpus checks (`:69-81`),
method (`:87-126`), measurement protocol (`:132-149`), results (`:155-173`),
limits (`:189-193`) and next step (`:231`, roadmap `:253-255`) are all there.
Two parts are missing. The data section never says how the 120 final
questions were made: a local model drafted them from single corpus chunks
(`scripts/build_final_v3.py:1-16`), each single-hop row has exactly one gold
chunk and each multi-hop row two [V], and the 28 unanswerable rows are
off-topic (Charon's orbit, Gaudí, Hokusai pigments) rather than near-miss
questions inside the five topics (`data/golden_final_v3.json`) [V]. That
shapes every retrieval and refusal number. Also the stress set C result
(`:218`, "10/30 (20 empty)") is listed without the cause recorded in
`README.md:220-222` and `DESIGN.md:302-304` (a verifier crash, 27 verifier
failures in `metrics.json` → `detail.stress_c.claim_accounting`) [V].

**2. Engagement: 3.** The opening question (`:6`) is good and the second
sentence gives a concrete failure ("invent a link between two quoted lines",
`:7`). The arc problem → guardrails → data → retriever → measurement →
outcome → lessons is sound. It loses force because the payoff is spent in the
first screen (`:14`) and then restated in Objectives (`:35-40`), Results
(`:155-173`), the Conclusions summary (`:181`), and the closing card (`:231`).
That is five tellings of F1 0.9091. There is no worked example: the reader
never sees one real question go through search, draft, check and repair,
though `reports/final_v3_e2e/question_traces_heldout.json` holds 120 of them
with `claim_states`. There is no tension either: nothing says what went
wrong before the fix. `README.md:184-203` holds the schema defect that
"burned up to ~33M tokens" on unanswerable rows, the best story in the
project, and the article does not tell it.

**3. Language: 3.** Sentences average 17-27 words per section; Conclusions
averages 26.7 and has three sentences over 35 words [V, word count with
tables and code removed]. Em dashes: 2 in story (good), 13 in README.
Overused words: "every" ×20, "never" ×8, "honest/honestly" ×5, ", not " ×8 in
story [V]. Internal ids reach the reader without a gloss: `S1/S2/S3`, `R0`,
`final_v3`, `judge_v2`, `dev_65`, `kimi-for-coding`, `MRR@5`, `all-articles@5`,
`Wilson 95%` (`:88-94,141-143,161`). F1 is never defined. Non-technical readers
get good plain lines ("The generator can only cite what search delivers",
`:31`) but then hit "cross-encoder re-scores the fused pool" with no plain
meaning (`:92`). Filler: "precisely because the cut is hard" (`:74`),
"Direct verification caught what summary averages would have smoothed over"
(`:75`), "the honest headline" (`:92`).

**4. Article logic: 2.** Three logic breaks matter.
(a) Results claims the final set was "never used during retrieval tuning"
(`:156`) two sections after Evaluation says it was read for the S3 gate
(`:143`), and Conclusions repeats the gate read (`:191`).
(b) Objectives defines the retrieval target as "a relevant article in the top
5" (`:31`), but the number reported against it, 0.9457 (`:37`), is chunk-exact
hit@5 on final_v3 (`reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json`
→ `gold_modes: ["chunk_exact"]`). On the dev splits the same name is
article-level (`scripts/measure_retrieval.py:479-496`) [V]. One name, two
metrics, and the ladder figure plots both on one axis.
(c) "Promotion protocol: each stage had to win on the next set in line …
then the sealed final set" (`:93`) describes a clean sequence, but S1 and S2
never ran on final_v3 (`story.yaml:263`) and the gate that promoted S3 was
final_v3 itself (`README.md:89-92`). So the "next set in line" was the
reporting set. F1 appears in Background (`:14`) before any definition.
The Evaluation section's three figures (`:152`) do not belong to its text.

**5. Text versus images: 2.** See section 4 for the full table. Of the 5
diagrams, 4 are dated 2026-11-16, before the S3 promotion (2026-11-23) and the
final_v3 pass (`63a27768`, 2026-11-23). They show the old pipeline ("Top 15 →
top 3", no BM25, no RRF, no per-article cap) and the old sets ("65 tuning, 55
sealed", "Sealed 55-question set · scored once") [V]. Of the 11 story figures,
4 come from the final artifacts (`retrieval_ladder`, `final_outcome`,
`failure_taxonomy`, `verify_funnel`, all committed in `214cc041`); 6 are
tuning-era; `eda_corpus_composition` is still valid. The retrieval ladder
uses one colour for R0 and S3 in both panels, so the reader cannot see the
promotion it is meant to show.

**6. Cohesion: 2.** The four surfaces tell two different stories.
`README.md:14-16` says the final set was scored "once" and calls it "sealed".
Its disclosure at `:89-92` says it was read four times. `docs/projects/01-rag-agent.md:12`
says recall@5 0.946 "on the sealed set". `docs:68-71` still describes the
evaluation as "65 graded questions". `docs:73` heads the results "Key results
(selected `kimi-for-coding`)". `docs:179` keeps "Current grounding-hardened
configuration" for a superseded stack. `DESIGN.md:20-43` architecture has no
BM25, RRF, cap or verify loop; `DESIGN.md:64` says the reranker scores "5 ×
top_k" while S3 runs `rerank_multiplier: 6` (`params.yaml:68`).
`DESIGN.md:215-216` points to README sections "§Wave 14/16" that no longer
exist. `DESIGN.md:395` puts an unversioned 2026-11-23 entry after 0.1.0.
README Limits (`:285-290`) still cite the tuning pass (17 unsupported) and
the 55-question pass as current. The "44% of unsupported claims" error
(section 3, T3) appears at `story.yaml:140`, `README.md:77-78` and
`docs:173-174`.

**7. Truthfulness: 3.** About 70 numbers traced (section 3). All final-pass
numbers trace exactly. The known issues:
- *Owner hand-labelling*: not done; disclosed correctly at all four story
  points. One gap: the reviewer was a Claude agent that saw the judge's label
  beside each claim (`owner_sample_validated.json` → items carry `kimi_label`,
  `kimi_reason`) [V], so "independent" (`:141`) should say "a reviewer agent
  from another model family that could see the judge's labels". The 147
  calibration labels themselves were written by `kimi-for-coding`
  (`experiment_log.json` rows with `step: judge-calibration-v2`, `model:
  kimi-for-coding`, `decision: labelled`) [V]. The article does not say so.
- *Faithfulness pair*: correct (above). Unstated: "faithfulness" here is the
  `kimi-for-coding` rubric judge's 0-1 score averaged over 92 answerable rows
  with a bootstrap CI (`src/rag_agent/evaluate.py:764,1212-1214`), not RAGAS
  (`meter.phases.ragas.calls: 0`) [V]. The judge table row "RAGAS suite |
  Faithfulness" (`:149`) invites the wrong reading.
- *final_v3 read several times*: disclosed at `:143,191`, contradicted at
  `:156` and in the key concept at `:235` ("scored once to prevent tuning
  overfit"). The ladder and outcome figures still say "sealed" in their titles.
- *Same model for generator, verifier, judge*: disclosed (`:143,186,192`) and
  true (`meter.phases.{agent,verify,judge}`, `ops.backend env:kimi-for-coding`)
  [V]. Not disclosed: the correctness verdict behind F1 and accuracy is also
  that judge's call (`scripts/run_e2e_eval.py:104`).
- *Spend*: story `$1.014` / `$1.458` / `$0.0084` / `$0.0121` trace exactly.
  `DESIGN.md:413` `$2.0392` is UNTRACED.

**8. Human-like narrative: 2.** 38 of 44 bullets open with a bold label, and
most of those follow one template:
`**Label (metric):** claim. Reason clause, so consequence.` [V, count]. Repeated
sentence frames: "each step exists because a measured failure forced it"
(`:88`) and "every rule exists because an earlier measurement exposed the hole
it now closes" (`:133`); "X, not Y" eight times; "fails loudly / loudest"
(`:23,56`); every section opens with a bold aphorism and closes with an
"In plain terms" line that restates the opener. Judgement does show in places:
the Wright Flyer example (`:90`), "a cited assistant fails loudest when it
sounds confident and is wrong" (`:23`). But "A wrong-but-plausible answer is
gone" (`:163`) overclaims in the same bullet that reports one. A person
with judgement would also say what surprised them. The data has two
surprises: the reranker added nothing to recall, only rank (`metrics.json` →
`detail.hpo.rerank_ablation`, recall@5 0.831 both ways), and precision is held
down by budget stops, not wrong answers.

**9. Technical details: 3.** Reproducible: chunk size and overlap (200/40),
RRF k=60, pool 50, per-article cap 2 with backfill, serving top 3 versus
measuring top 5, context token means, rails 12/16/200k, repair cap 2, code
excerpt that matches `src/rag_agent/index.py` [V]. Imprecise or wrong:
- "split at paragraph and heading boundaries" (`:90`): the corpus has no
  heading markers ("verified across all 593 articles", `src/rag_agent/chunking.py:11-12`).
  R0 and S1 split identically (same `_pack`, same 3,589 chunk ids and bodies)
  [V, compared `data/index/chunks_200` with `tourn_R0_size_minilm`]. "Structure"
  is the title prefix only.
- "a cross-encoder re-scores the fused pool" (`:92`): it re-scores the top
  `top_k × rerank_multiplier` of the fused list, 18 at serving and 30 at
  measurement, not the 50-pool (`index.py:99,108`; sweep `method` field) [V].
- The MRR 0.718 → 0.808 and "975 … narrowed to 195" (`:92`) are the R0-era
  rerank ablation on 65 tuning questions (`metrics.json` →
  `detail.hpo.rerank_ablation`), placed under the S3 bullet.
- The 0.6 floor (`:30,139,147,162,228,236`) is the share of an answer's
  claims that survive. Each claim gets a yes/no entailment verdict
  (`verify.py:61-66,618-622`). "Mean support 0.9739" is the mean of that
  share per answer (`n_answers_verified 116`), not a claim support score.
- recall@5 is a hit rate: 1 if any gold chunk is in the top 5
  (`measure_retrieval.py:513,560-564`). Never defined in the article.
- F1 is never defined. Per `run_e2e_eval.py:101-118`: TP = answerable row
  answered, judged correct and citing a relevant article. FP = unanswerable
  row not correctly refused. All 4 FPs are budget stops with no answer
  (traces: `verdict: budget-terminated`, `abstained: false`) [V], so
  "precision 0.9524" does not mean "4 wrong answers given".
- Two interval methods (Wilson for accuracy, bootstrap for faithfulness) are
  not named as such (`:161,170`).
- Newer models were tried and not reported: Qwen3-Embedding-0.6B and
  Qwen3-Reranker-0.6B on `dev_v1` (`reports/retrieval_sweeps/embed_qwen3__dev_v1.json`,
  `rerank_qwen__dev_v1.json`). Every arm scored recall@5 1.0 on n = 16, so the
  split could not tell them apart [V]. The article's choice of 2021-era
  MiniLM models needs that sentence.

**10. Overall: 3.** The evidence trail is stronger than the article: one can
re-derive every final number. The article's job is to make that trail
legible and not overstate it. Today it overstates in four places, shows a
pipeline that no longer exists, and buries its best material.
**Three biggest improvements**, in order:
1. **One honest test-set paragraph, placed before the first headline.** Fix
   `:156` and `:235`. Say how final_v3 was built and read (section 7.3 text).
   Retitle "sealed" figures.
2. **Redraw the four stale diagrams and fix the ladder colours.** Move the
   three tuning-era Evaluation figures to a "what tuning ruled out" block.
3. **Define the four measures once (recall@5, F1/precision, faithfulness,
   0.6 floor) and tell one traced question end to end.** That replaces
   repetition with substance and fixes the technical misstatements.

---

## 3. Number trace (story.yaml unless marked)

TRACED = exact match after rounding for people. PARTIAL = trace exists but
scope, unit or definition differs. UNTRACED = no committed source found.
`E2E` = `reports/final_v3_e2e/metrics.json` → `detail.final_v3`; `F1S` =
`reports/final_v3_e2e/f1_summary.json`; `S3F` =
`reports/retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json`; `R0F` =
`reports/retrieval_baseline/final_v3.json`; `M` = `reports/metrics.json`.

### 3.1 Material problems (fix before anything else)

| # | Line | Claim | Evidence | Verdict |
|---|---|---|---|---|
| T1 | `:156` | "sealed final split, never used during retrieval tuning or guardrail fitting" | S3 promotion confirmed on final_v3 (`README.md:89-92`, `story.yaml:143,191`, `params.yaml` comment "won the dev_65/heldout_55/final_v3 ladder") | **FALSE**: contradicts own disclosure |
| T2 | `:235` | key concept "scored once to prevent tuning overfit" | as T1 | **FALSE** for final_v3 |
| T3 | `:140` | "first verifier accepted 44% of unsupported claims (kappa 0.546 local, 0.605 hosted)" | `judge_calibration_report.json` → `judges[0]` (local `qwen2.5:3b`): rate 0.4433 = 86/**194 all claims**, "the committed FA rate uses all 194 claims as denominator"; among 97 unsupported that is 86/97 ≈ 0.89. Hosted `judges[1].pooled`: unsupported-only 0.3966 (69/174), kappa 0.6052 | **WRONG DENOMINATOR** and two judges merged into "the first verifier". Same error `README.md:77-78`, `docs:173-174` |
| T4 | `:142` | "skipped 33 short answers" | `E2E.verify.n_verify_skipped 33`; `verify.py:102` "agent already abstained: nothing to verify" | **WRONG REASON**: 33 refusals, not short answers |
| T5 | `:30,236` | "Each drafted claim is scored against its cited passage"; "Each claim needs support of 0.6 or better" | `verify.py:61-66` (boolean verdict), `:618-622` (fraction of surviving claims < 0.6 → abstain) | **WRONG MECHANISM** |
| T6 | `:90` | "Structure-aware chunking alone lifted development recall@5 to 1.000 on every development split" | R0 already 1.000 on `dev_v1`, `dev_40`; lift only on `dev_65` 0.9636 → 1.0 (and `heldout_55` 0.9762 → 1.0, not a dev split); S1 = title prefix only | **PARTIAL / over-claim** |
| T7 | `:163` | "A wrong-but-plausible answer is gone" | `E2E.taxonomy.counts.unsupported-claim 1` | **Over-claim**: one remains |
| T8 | `:161` | "20/24 multi-hop (+4.2 percentage points retrieval lift from S3)" | 0.8333 − 0.7917 = 0.0416 from S3F/R0F retrieval slices | **PARTIAL**: a retrieval delta attached to an answer count |
| T9 | `:218` | "set C 10/30 (20 empty)" | `M.detail.stress_c`: 27 verifier failures, 37/39 mechanical fails; README:220-222 "verifier crash … failure diagnostic" | **Context omitted**: reads as a model result |
| T10 | `DESIGN.md:413` | "$2.0392 of the $3.00 cap" | none | **UNTRACED** |

### 3.2 Final pass and retrieval

| Line | Number | Source | Verdict |
|---|---|---|---|
| `:2` | 0.946 recall@5 | S3F `recall_at_5 0.94565` | TRACED (chunk-exact hit@5, see 2.4b) |
| `:2,14,166-168,181` | F1 0.9091, P 0.9524, R 0.8696 | F1S | TRACED |
| `:2,156,170` | faithfulness 0.8717 [0.8092, 0.9304], n = 92 | `E2E.faithfulness`, `E2E.rag.n_questions 92` | TRACED (rubric judge, bootstrap) |
| `:14,155,172` | 104 correct / 10 / 4 / 1 / 1 | `E2E.taxonomy.counts` | TRACED |
| `:161,169,181` | 86.7%, Wilson [0.7944, 0.9162] | `F1S.overall_accuracy_wilson95` (the other pair `correct_share_ci95 [0.8, 0.925]` is unused, good) | TRACED |
| `:161` | 80/4/24/12 | F1S | TRACED |
| `:161` | 60/68, 20/24, 24/28 | `final_outcome` figure JSON; F1S totals | TRACED |
| `:161` | refusal 0.8571; cite-when-expected 90.2% | `E2E.abstention` | TRACED |
| `:161` | 88.6% gold chunks; 93.5% relevant articles | S3F `gold_chunk_coverage_at_5 0.8859`, `article_coverage_at_5 0.9348` | TRACED (undefined terms) |
| `:37,92,171,222` | 0.9239 → 0.9457; multi-hop 0.7917 → 0.8333 | R0F, S3F | TRACED |
| `:222` | all-articles@5 0.8804 | S3F | TRACED; no R0 value exists on final_v3 (R0F lacks the field) |
| `:92` | all-articles@5 "led on every split" | S3 vs R0: dev_v1 0.938/0.875, dev_40 0.906/0.719, dev_65 0.891/0.745, heldout_55 0.976/0.952 [V] | TRACED for dev + heldout only |
| `:93` | 443 / 748 context tokens | S3F `mean_context_tokens_top3/top5` | TRACED |
| `:91` | k = 60, pool 50; cap 2 | `params.yaml:65-66`, S3F config | TRACED |
| `:92` | MRR@5 0.718 → 0.808 | `M.detail.hpo.rerank_ablation.off/on` | PARTIAL (R0 tuning-era, placed under S3) |
| `:92` | 975 → 195 | `story.yaml:258` caption, 65×15 and 65×3 | PARTIAL (derived; R0 multiplier 5) |
| `:94` | 0.831 tie 200/400/800 | `M.detail.retrieval.{200,400,800}.recall@5` | TRACED |
| `:94` | MiniLM 0.808 vs BGE 0.805 MRR | `M.detail.hpo.models` | TRACED |
| `:94` | "MiniLM (80 MB)" | none | UNTRACED |
| `:94,223` | RRF 0.533 vs dense 0.600, n = 15 | `reports/fusion.json` → `sealed` | TRACED |
| `:138` | random 0.031, word-match 0.677 | `M.detail.retrieval.200` | TRACED |

### 3.3 Verify loop, cost, rails, judges

| Line | Number | Source | Verdict |
|---|---|---|---|
| `:162,181` | 166 / 16 / 150 / 148 / 15 / 11 / 7 / 159 | `E2E.verify` | TRACED |
| `:162` | 95.8% retention | `claim_retention_rate 0.9578` | TRACED |
| `:162,181` | mean support 0.9739 | `mean_support_fraction` | PARTIAL (per-answer surviving share) |
| `:163` | 2 of 150 claims unsupported | 150 − 148 | TRACED (derived) |
| `:163` | 11/92 missed; 8 cited no key page | `false_abstention_rate 0.1196`; `F1S.errors.uncited_relevant 8` | TRACED |
| `:163` | 17/65 in tuning | `README.md:113`, `M` tuning taxonomy | TRACED, different set |
| `:142` | 2 verify abstentions; 0 mechanical false rejections | `E2E.verify` | TRACED |
| `:142` | 12 / 16 / 200k rails | `src/rag_agent/config.py:201-203` | TRACED |
| `:164` | 6.2 s, 31% | `mean_verify_latency_s 6.242`, `verify_latency_share_of_answer 0.3107` | TRACED |
| `:164,181` | $1.014 = $0.781 + $0.233; $0.0084/q | `meter.phases.agent/verify.spend_usd` | TRACED (sum 1.013633) |
| `:164` | 74% cached | 724,736 / 983,908 = 0.737 | TRACED (derived) |
| `:164` | $1.458; $0.0121/q | `meter.total.spend_usd 1.457917` | TRACED |
| `:40,164` | p50 16.5 s, p95 40.5 s | `E2E.ops` | TRACED |
| `:141` | 147 claims, 72 one-detail negatives | `judge_calibration_v2/raw/` holds 147 files [V]; 72 only in `DESIGN.md:403-404` | PARTIAL (72 not found in a report) |
| `:141` | 30 sampled, 11 / 19, 30/30, [0.8865, 1.0], gate 0.85 | `owner_sample_validated.json` | TRACED |
| `:149` | RAGAS v0.3.1 | `E2E` top-level `ragas_version`; tuning pass only | TRACED |
| `:212-216` | tuning RAGAS / rubric table, p50/p95, $0.000906 | `README.md:111-124` and `M` | TRACED (earlier review verified; spot-checked 0.6209) |
| `:217` | 44/9/1/1, 0.80 [0.69, 0.89], 12/13, $1.95, 24.4 s / 126.8 s | `M.detail.heldout` via README:139-153 | TRACED |
| `:218` | stress 16/30, 22/30, 19/30, 17/30 | `M.detail.stress*` | TRACED (C context, T9) |
| `:229` | $1/$4 per Mtok, 30% cached | `meter.cost_basis` | TRACED |
| `:72,80` | 102-125 per topic, 593 | `data/raw/corpus.jsonl` counts 125/124/122/120/102 [V] | TRACED |
| `:75` | "Several expected flagship titles were missing on the first scan" | none found | UNTRACED (narrative; cite or cut) |

---

## 4. Figures and diagrams

Final-result commits: S3 sweep 2026-11-23, E2E pass `63a27768` 2026-11-23,
final figures `214cc041` 2026-11-24 [V, `git log -1`].

| Asset | Where shown | Date | Stale? | Carries the text's point? | Action |
|---|---|---|---|---|---|
| `diagrams/ragPipeline.ts` (`01-rag-pipeline`) | Background `:9` | 11-16 | **Yes**: "Top 15 → top 3", FAISS only, no BM25/RRF/cap | No: the text says "CPU search", the picture shows the retired retriever | **Redraw** with dense + BM25 → RRF → rerank top 18 → cap 2 → top 3 |
| `auto/01-rag-agent-1.ts` | Objectives `:25` | 11-16 | Partly: "All claims at 0.6 support floor?" | Misstates the floor (T5) | **Edit** node: "≥ 60% of claims survive?" |
| `auto/01-rag-agent-2.ts` | Data `:49` | 11-16 | **Yes**: "65 tuning, 55 sealed"; no final_v3 | Contradicts the table under it (`:59-63`) | **Edit** last node: "65 tuning · 55 gate · 120 final" |
| `auto/01-rag-agent-3.ts` | Evaluation `:135` | 11-16 | **Yes**: "Tuning pass, 65 questions", "Sealed set, scored once" | Contradicts the disclosure | **Redraw** for the final protocol |
| `auto/01-rag-agent-4.ts` | Results `:158` | 11-16 | **Yes**: title "Conclusions & lessons", "Sealed 55-question set · scored once", "Rubric + RAGAS judges" (RAGAS made 0 calls) | No | **Redraw** as the verify loop with final counts, or drop for `verify_funnel` |
| `eda_corpus_composition` | EDA | 10-19 | No (corpus unchanged) | Yes. Caption says "word-length distribution" and "12,000-character cap" (`:257`): units clash | Fix caption units |
| `retrieval_ladder` (PNG + JSON) | Training; docs:99; root README | 11-24 | No | **Partly**. R0 and S3 share one colour in each panel; the right panel uses a different palette with no legend; value labels overlap ("1.0001.0001.000"); four of five left-panel groups sit at the 1.0 ceiling with n = 16-55; final_v3 right panel has S3 only | **Regenerate**: fixed colour per arm across panels, one legend, drop the saturated recall panel or show it as a table, label metric definitions (article-level vs chunk-exact) |
| `chunk_size_sweep` | Training; docs:116 | PNG 10-19, JSON 11-11 | Tuning-era, labelled as history in story caption | Yes for the story. **docs:116 alt text** "Chunk size, not model size, sets retrieval recall" contradicts the figure (all sizes tie at 0.831) | Keep in a "ruled out" block; fix docs alt text |
| `model_comparison` | Training | 10-19 | Tuning-era | Yes (tie) | Move to "ruled out" or drop (a table row says it) |
| `latency_histogram` | **Evaluation** | 11-08 | **Yes**: tuning p50 25.9 s; final is 16.5 s | No: Evaluation text never mentions latency | Remove from Evaluation; regenerate from final traces only if latency matters |
| `kimi_generation_comparison` | **Evaluation** | 11-08 | Tuning-era provider pick | No | Remove (appendix at most) |
| `fusion_arm_comparison` | **Evaluation** | 11-11 | Tuning-era, reranking off | No; text mentions it only in Training/Conclusions | Remove or move to "ruled out" |
| `final_outcome` | Results | 11-24 | No | Yes, but title "Final **sealed** pass"; subtitle truncated at the right edge; FP bar labelled "answered" although all 4 are budget stops with no answer | **Regenerate**: drop "sealed", wrap subtitle, label FP "budget stop (no answer)", show slices as stacked correct/incorrect |
| `failure_taxonomy` | Results; docs:103 | 11-24 | No | **Weakly**: no value labels, so the 1 unsupported and 1 miss bars are near-invisible; subtitle says "sealed pass" | **Regenerate** as a horizontal bar with counts, log-free, "correct" shown as a number not a bar |
| `verify_funnel` | Results; docs:105 | 11-24 | No | Mostly. Not a funnel ("accepted" 159 is taller than "judge-supported" 148); "mean support" label (T5) | Regenerate as a flow: 166 → 16 mech fail + 150 judged → 148 + 2 → repair 18 → 11 kept / 7 dropped → 159 |
| `retrieval_funnel` | Conclusions | 11-18 | Tuning-era R0 | Not referenced in Conclusions text | Remove |

Summary: regenerate 4 (`retrieval_ladder`, `final_outcome`,
`failure_taxonomy`, `verify_funnel`); redraw or edit 5 diagrams; move or remove 6
tuning-era figures; fix 2 captions.

---

## 5. Cross-surface contradictions (names, numbers, dates)

| # | Topic | Surfaces in conflict | Fix direction |
|---|---|---|---|
| X1 | final_v3 status | "sealed … once" `README.md:14-15`, `docs:12,75`, `DESIGN.md:400,410`, `story.yaml:156,235`, figure titles vs "consumed" `README.md:89-92`, `story.yaml:143,191` | One term: "final test set (read four times; consumed)" |
| X2 | Unsupported unit | "claim in 120" README:15-16, docs:13-14, DESIGN:412 vs "answers" story:163, card:45 | "answers" everywhere |
| X3 | 44% judge miss | story:140, README:77-78, docs:173-174 | Fix denominator (T3) |
| X4 | Pipeline | DESIGN §2 and §3.2 (no BM25/RRF/cap, 5×k) vs README:60-67, docs:29-53 (current) | Update DESIGN §2 or label it "v0.1 architecture" |
| X5 | Evaluation set described | docs:68-71 (65 questions) vs story:59-63 (65/55/120) | docs follows story |
| X6 | Headline heading | docs:73 "Key results (selected kimi-for-coding)" | "Final 120-question results" |
| X7 | "Current" configuration | docs:179, README:184-211 ("current champion") vs S3 + Phase E | Mark as earlier stack |
| X8 | Limits | README:285-290 (tuning + 55-question failures) vs story:189-193 | README Limits mirror story Limits |
| X9 | Spend | DESIGN:413 $2.0392 vs README:102 $1.458 | Drop or source |
| X10 | Reproduce | README:26-42 never shows how to re-run the headline (`scripts/measure_retrieval.py`, `scripts/run_e2e_eval.py --summarize`, `scripts/build_final_figures.py`); docs:97 shows only the last | Add three commands; `--summarize` is $0 |
| X11 | DESIGN changelog order | 2026-11-23 entry after 0.1.0 (`DESIGN.md:395`) | Version it (1.3.0) and place first |
| X12 | Model naming | "kimi-for-coding" (provider route) vs "kimi-k2.8-preview reference card" (`meter.cost_basis`) | Name the endpoint once, say the rate card is a proxy |

---

## 6. Section-by-section notes on story.yaml (only what sections 2-5 do not cover)

- **background** (`:5-19`): good hook. Bullet 2 "single-family judging" is
  jargon on screen one. Use "the same model wrote and graded the answers".
- **objectives** (`:21-43`): the target table is the strongest element in the
  article. Add the row the reader most wants: "Unsupported answers: target
  none stated → 1 / 120". The "Why not a bigger model" bullet (`:33`) asserts
  "Larger models still extrapolate" with no evidence. Cut it, or point to
  the provider comparison.
- **data** (`:45-66`): "Reads: Multiple / Consumed / >1 (consumed)" (`:61-63`)
  is vague. Give counts: final_v3 read 4 times (R0 baseline, S3 gate, held-out
  validation, E2E).
- **eda** (`:68-84`): fine, a little padded (`:74-75`).
- **training** (`:86-129`): the best technical section. Split the S3 bullet
  (`:92`) in two (rerank, cap). Move the R0-era MRR and funnel numbers to
  "ruled out".
- **evaluation** (`:131-152`): the judge table (`:145-149`) is good. Add a
  "what correct means" row (rubric judge, same model). Remove the figures.
- **results** (`:154-176`): the first paragraph contains T1. Bullet 3 holds
  the most important finding (over-caution: 10 empty answers + 4 budget stops
  = 14 of 16 failures). It deserves to lead.
- **conclusions** (`:178-232`): "Exact numbers" (`:195-218`) is an appendix
  inside the lessons. "What the experiment taught" has 3 bullets, and 2 repeat
  Results. Lesson candidates the data supports but the text lacks: the
  reranker improved rank, not recall; budget rails turned 4 refusals into
  failures; the representable-refusal schema fix.

---

## 7. Proposed target structure

Constraints kept: eight fixed ids and order (`repo-conventions.md`, story
contract), ≤ 3 figures per section, "In plain terms" card last, `#sec-<id>`
anchors. Pattern: **opening line → visual → 3-5 bullets → closing table or
figure → plain-terms card ending in a link to the next section.**

### 7.1 Section plan

| # | id | Opening line type | Visual | Bullets (content) | Closing table / visual + next link |
|---|---|---|---|---|---|
| 1 | background | **Question + stakes**: "When every answer carries a citation, what can still go wrong?" then one concrete failure | Redrawn `01-rag-pipeline` (S3 path + verify loop) | What it does (593 articles, cite or refuse) · who it is for · one headline with n · the honest caveat in plain words (same model graded; test set read four times) | 3-row "at a glance" table (corpus, final test, headline) → `[Next: what we promised up front](#sec-objectives)` |
| 2 | objectives | **Promise**: "Four targets, fixed before any tuning." | `auto-1` with the floor node fixed | Refuse outside the corpus · ≥ 60% claims survive or abstain, ≤ 2 repairs per answer · retrieval hit rate ≥ 0.60 (defined) · ≤ $0.01 per answer path · local or hosted model | **Target vs result** table, adding an "unsupported answers" row → `[Next: the corpus and the questions](#sec-data)` |
| 3 | data | **Constraint as a choice**: "A small, pinned corpus makes every claim checkable." | `auto-2` with the 65/55/120 node | Five topics and caps · sha256 pins · **how the 120 final questions were made** (local model, one gold chunk single-hop, two multi-hop, off-topic unanswerables) · how often each set was read | **Question-sets table** with exact read counts → `[Next: what the corpus looks like](#sec-eda)` |
| 4 | eda | **Finding first**: "Topics are even; page lengths are not." | `eda_corpus_composition` | Topic range 102-125 · cap shapes the tail · anchors checked against the slice | Corpus stats table → `[Next: building the retriever](#sec-training)` |
| 5 | training | **Claim + number**: "Better ranking, not a bigger model, lifted retrieval from 0.924 to 0.946." | `retrieval_ladder` (regenerated) | Title prefix (S1, and what it is not) · dense + BM25 via RRF · rerank top 18 · per-article cap · **what tuning ruled out** in one bullet (chunk size, embedding model, Qwen3 arms at the n = 16 ceiling, reranker = rank not recall) | R0/S1/S2/S3 table on all-articles@5 and recall@5 with metric definitions; code excerpt stays → `[Next: how results earn trust](#sec-evaluation)` |
| 6 | evaluation | **Rule**: "A result counts only if a person can check it." | Redrawn `auto-3` (final protocol) | Definitions: hit@5, correct (judge), F1 cells, faithfulness · floors · verify loop mechanics · rails · **test-set and judge disclosure** (section 7.3) | **Judge table** with a "who checks the checker" column → `[Next: the final run](#sec-results)` |
| 7 | results | **Outcome**: "104 of 120 handled correctly; 1 answer kept an unsupported claim." | `final_outcome` (regenerated) | Headline with n and intervals · **failures are now over-caution** (10 empty + 4 budget stops = 14 of 16) · claim accounting · one traced question walk-through · cost and latency | Headline table + `failure_taxonomy` + `verify_funnel` (regenerated) → `[Next: what this does and does not prove](#sec-conclusions)` |
| 8 | conclusions | **Judgement**: "Auditable on this slice; not ready to run unattended." | none (or roadmap strip) | 3-4 lessons the data supports (section 6) · 3 limits · next step: final_v4, cross-family judge, owner labels, cut empty answers | Collapsed appendix: tuning pass, 55-question gate, stress A-D **with C's crash note** → `[Full evaluation page](…/projects/01-rag-agent/)` |

### 7.2 Figures to regenerate or redraw (owner decision O3)

1. `retrieval_ladder`: colours, legend, definitions (required).
2. `final_outcome`: title, subtitle wrap, FP label (required).
3. `failure_taxonomy`: value labels, title (required).
4. `verify_funnel`: flow layout, label "share of claims kept" (recommended).
5. Diagrams `01-rag-pipeline`, `auto-2`, `auto-3`, `auto-4` (required);
   `auto-1` one node (required).
6. Remove from the story: `latency_histogram`, `kimi_generation_comparison`,
   `fusion_arm_comparison`, `retrieval_funnel`. Optional: `model_comparison`.

### 7.3 Proposed final_v3 disclosure text (owner decision O4)

Place in Evaluation as its own bullet, and as one clause in Background.

> **How clean is the final test?** Not fully. A local model drafted the 120
> questions from corpus passages, and the drafting step could not open any
> tuning file (`reports/final_v3_file_access.json`). We then read results on
> this set four times: the old retriever's baseline, the check that promoted
> the new retriever, a held-out validation, and the end-to-end run reported
> here. Because the retriever was chosen partly on this set, these numbers
> are optimistic by an amount we cannot measure. The next quality claim will
> come from a new set, scored once.

Background clause: "…on a 120-question test set that was also used to pick
the retriever, so treat the numbers as an upper estimate."

Judge clause for the same bullet:

> The same model (`kimi-for-coding`) wrote the answers, checked each claim,
> and graded correctness. A reviewer agent from another model family agreed
> with the judge on 30 of 30 sampled claims, but it could see the judge's
> labels, and the owner's own blind labelling is still pending.

---

## 8. Expand and tighten

### 8.1 Expand (too thin)

| # | Where | What is missing | Model rewrite (one or two sentences) |
|---|---|---|---|
| E1 | data `:57-63` | How the final questions were made | "A local model wrote each final question from one corpus passage (two for multi-hop), and that passage is the gold answer. The 28 unanswerable questions ask about things outside all five topics, such as Pluto's moon Charon, so they test refusal of clearly foreign questions, not near misses." |
| E2 | evaluation `:139` | What "correct", F1 and precision mean | "A row counts as a true positive when the assistant answers, cites a relevant article, and the judge marks the answer correct. All four false positives were unanswerable questions that hit the tool budget before refusing, not wrong answers." |
| E3 | evaluation `:138` / training `:90` | recall@5 definition | "Recall@5 here is a hit rate: a question scores 1 if any gold passage is in the top five results. On the final set gold means the exact passage; on the development sets any passage of the right article counts." |
| E4 | results `:163` | A worked example | "Take 'Which company acquired LM Wind Power in April 2017?'. Search puts the LM Wind Power passage first, the draft cites it, the verifier accepts its single claim, and the answer ships as 'GE Renewable Energy' with one citation." (Pick a real row from `question_traces_heldout.json` and quote its trace; do not use this example unless the trace matches.) |
| E5 | results `:163` | Over-caution as the lead finding | "Fourteen of the 16 misses were the system saying too little: 10 empty answers to answerable questions and 4 refusals cut off by the tool budget. Only one answer said something the sources did not support." |
| E6 | training `:94` | Newer models tried | "Qwen3 embedding and reranker models scored the same as MiniLM on the 16-question development set, where every arm hit the ceiling, so the smaller model stayed." |
| E7 | conclusions `:183-187` | A lesson with tension | "The most expensive bug was in the schema, not the model: before the fix, a correct refusal was invalid output, so the agent searched until the token cap. Making 'no answer' a valid answer fixed six of six unanswerable rows in the stress set." (verify against `README.md:199-203` before use) |
| E8 | stress C `:218` | Cause | "Set C scored 10 of 30 because the verifier crashed on an empty batch and every answer became a refusal; it measures that bug, not the model." |

### 8.2 Tighten (too verbose or repeated)

| # | Where | Current | Model rewrite |
|---|---|---|---|
| G1 | objectives `:28` | "Open-web chatbots answer everything fluently; that is the failure mode a citation-first product cannot afford, so 'I cannot find this in the corpus' is a first-class output." | "'I cannot find this in the corpus' is a valid answer here." |
| G2 | eda `:74` | "That tail is a property of the cap, not of the web: some flagship articles simply run longer. Prompt budgets stay predictable precisely because the cut is hard." | "The tail stops at the 12,000-character cap, which keeps prompts a predictable size." |
| G3 | eda `:75` | "…so no score rests on an article that was never indexed. Direct verification caught what summary averages would have smoothed over." | "We checked every anchor title and test question against the indexed slice." |
| G4 | training `:92` | "…and `all-articles@5` led on every split (the honest headline; raw recall@5 did not win everywhere)." | "S3's clearest gain is on all-articles@5, which needs every relevant article in the top five: it led R0 on all four development splits." |
| G5 | evaluation `:133` | "…and every rule exists because an earlier measurement exposed the hole it now closes." | Cut; `:88` already makes the point. |
| G6 | results `:164` | Cost bullet, 70 words | "The answer path cost $0.0084 per question, under the $0.01 cap; judging for evaluation raised it to $0.0121. Median answer time was 16.5 s." |
| G7 | conclusions `:181` | 80-word summary repeating Results | Delete; Results already has the table. |
| G8 | `README.md:184-240` | Five dense paragraphs of R6-R8.1 history | Move to DESIGN changelog; README keeps one table row per earlier set. |
| G9 | all "In plain terms" cards | Restate the opener | Make each card say what the section means for a user, plus the next link. Example for training: "Search now finds the right passage for 95 of 100 answerable questions on CPU alone. [Next: how we checked the answers →](#sec-evaluation)" |

---

## 9. Style guide for project articles (reusable)

1. **One number, one definition, one place.** Define a metric at first use in
   plain words (what counts as 1) and name its n and split. Never reuse a
   metric name for a different definition across splits.
2. **Say what the test set has seen.** Before the first headline, state how
   the evaluation set was built and how many times it was read. "Sealed" and
   "held-out" only for sets read once.
3. **Lead with the finding, then the mechanism, then the caveat.** No section
   opens with a limit; no caveat waits until Conclusions if it changes how to
   read a number.
4. **Picture must match the shipped system.** Every diagram and figure in a
   section describes the configuration that section talks about. History
   figures go in a labelled "what we ruled out" block or the appendix. A
   figure must make its point readable without the caption (distinct colours
   per arm, value labels on small bars).
5. **Show one real example.** Each case study traces one real input through
   the system, quoted from a committed trace.
6. **Vary the sentence shape.** At most half the bullets in a section use the
   `**Label:** claim, reason` form. Avoid repeated frames ("X, not Y", "exists
   because"). Cut "every", "never", "honest" unless literally true and
   needed.
7. **Internal ids stay internal.** Use names like `S3`, `final_v3`, `judge_v2`
   only inside tables or after a plain gloss ("the promoted retriever (S3)").
8. **Each number is told once in prose.** Headline in Background, full table
   in Results; other sections link to it instead of repeating it.

---

## 10. Owner decisions

| # | Decision | Recommendation |
|---|---|---|
| O1 | Approve the target structure (section 7.1) | Approve; pilot on 01, then roll to 02-13 |
| O2 | Approve the style guide (section 9) | Approve; rules 1, 2 and 4 could later become checks in `scripts/lint_story_language.py` (banned "sealed" near a consumed set id; figure-date check) |
| O3 | Which figures to regenerate | Required: `retrieval_ladder`, `final_outcome`, `failure_taxonomy`; diagrams `01-rag-pipeline`, `auto-1` (node), `auto-2`, `auto-3`, `auto-4`. Recommended: `verify_funnel`. Remove four tuning-era figures from the story (section 7.2) |
| O4 | Accept the final_v3 and judge disclosure text (section 7.3) | Accept, or edit wording; it replaces `:156` and the key concept at `:235` |
| O5 | Fix the four material misstatements T1-T5 in story, README and docs before any restructuring | Yes; these are truth fixes, not style |
| O6 | `DESIGN.md:413` $2.0392 | Drop, or commit a ledger that sums to it |
| O7 | Owner hand-label of the 30-claim sample | Still pending; the article wording is acceptable until then |

Kimi handoff: not written here. After O1-O5, the next step is a
`03-implementation-handoff.md` under `collaboration/designs/` covering the
truth fixes (T1-T10, X1-X12), the figure work (O3) and the restructure (7.1)
as three separately gated tasks.
