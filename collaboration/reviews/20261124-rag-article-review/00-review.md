# Review: RAG 01 article (story, README, docs page): language, logic, structure

Date: 2026-11-24
Reviewer: Claude Code (read-only; no implementation or copy files edited; no
hosted LLM or paid API calls)
Repo state: `main` @ `2a7d9b7a`
Scope: `projects/01-rag-agent/story.yaml` (the web article), with cross-checks
against `projects/01-rag-agent/README.md`, `docs/projects/01-rag-agent.md`,
`apps/showcase-web/src/lib/cardCopy.ts:45`, and the committed reports.
Status: draft, for owner decision. The article is **not** rewritten here.

Legend: **[V]** verified in this session (file read or command run);
**[I]** inference.

---

## 0. Summary

1. **The article reads as a lab notebook, not a case study.** Every section
   mixes three eras (65-question tuning, 55-question sealed set, 120-question
   final pass) and asks the reader to keep them apart. The final result
   appears in the Background as "Results" and is then re-explained four times.
2. **The structure the owner wants is mostly absent.** Three of eight sections
   have a diagram at the top; Evaluation and Results have zero bullets; no
   section closes with a table plus a link to the next step. Evaluation is
   685 words, over the 550-word lint budget [V]
   (`uv run python scripts/lint_story_language.py`: 1 warning).
3. **The Results section's metric table shows the wrong era.** Its
   `metrics_keys` read `reports/metrics.json`, which still holds the
   2026-11-16 tuning numbers (`rag_agent.faithfulness 0.6209`, recall@5 0.831)
   [V]. The prose beside it says 0.8717 and 0.9457.
4. **Five claims need a fix or a source** (section 3): the $2.0392 spend is in
   no committed report; "won every development split" is true only for
   all-articles@5, not recall@5; two different accuracy intervals and two
   false-abstention counts coexist; the fusion figure is described with two
   different sealed sets; and the generator, verifier and judge are the same
   model, which the article never says.
5. **Known open items, unchanged:** the owner has not hand-labelled the
   30-item judge sample (`owner_sample_validated.json:288`, `"validated_by":
   "claude-role-audit (pending human owner hand-label confirmation)"`) [V].
   The public faithfulness pair is **now fixed** in public copy: README:98,
   story:394 and docs:84 all show `[0.8092, 0.9304]`, matching
   `reports/final_v3_e2e/metrics.json` → `detail.final_v3.faithfulness.ci95`
   [V]. `git grep "0.7983"` outside `collaboration/` returns nothing [V]. The
   stale pair survives only in `collaboration/ITERATION_TRACKER.md:29`
   (internal).

---

## 1. Section-by-section table

Word counts, bullets and diagrams are from `story.yaml` at HEAD [V].

| Section | What it says | Problem | Suggested change |
|---|---|---|---|
| background (146 w, 1 diagram, 0 bullets) | Hook question; system answers from 593 articles with citations; set B had 9 unsupported outcomes over a gate of 6; lists 0.831, 0.733, 0.633 baselines; final F1 0.909 | Opens with a failed gate from an old set before the reader knows what the system is. Uses internal names (`set B`, `final_v3`, `01-rag-pipeline`). Four numbers from four different sets in one paragraph. "Business summary" is the legacy marker | Open with the problem and the answer in two sentences, then the pipeline diagram, then 3 bullets (what it does / what was measured / what it does not prove). One headline number. Move baselines to Evaluation |
| objectives (269 w, 1 diagram, 3 bullets) | Answer with evidence or refuse; 0.6 support floor; repair loop; success = structured output, ≥0.60 article recall, ≤$0.01/query; local vs hosted model | Good bones. The diagram walk-through is long prose that repeats the diagram. The $0.01 target is never checked against the final pass anywhere in the article | Keep the diagram; turn the walk-through into 4 bullets; close with a **target vs result** table (recall, refusal, cost/query, latency) so the reader sees each target met or missed |
| data (245 w, 1 diagram, 5 bullets) | 5 topics, ≤120 articles each, 12,000-char cap, sha256 pins, data registry, 65 tuning + 55 sealed questions | Lists the 65/55 question sets but not the 120-question final set (68/24/28), which carries the headline. Defines "context" and "indexing" inline, which slows technical readers | Add a **question-sets table**: name, size, mix, role (tune / gate / final), times read. Keep definitions in the glossary link |
| eda (173 w, 0 diagram, 4 bullets, 1 figure) | 102–125 articles per topic; long-tailed lengths; dump order not topical; anchors checked | Fine content. No diagram (figure only). "Dump order is not topical" is opaque to non-technical readers | Add a one-line plain meaning; keep the figure as the section visual; close with a 3-row corpus stats table |
| training (565 w, 0 diagram, 2 bullets, 3 figures + code) | S3 retriever defined; S3 beats R0 0.9457 vs 0.9239; then the 65-question funnel, chunk sweep, model comparison; reranker MRR 0.718 → 0.808; code excerpt | Two eras interleaved: the promoted S3 first, then three figures of the *old* dense champion labelled "development history". Readers cannot tell which figures describe the shipped system. "FAISS … finds exact nearest matches" is defined after use. The closing paragraph jumps to 17/65 unsupported answers (an evaluation fact) | Split into **(a) the shipped retriever** (diagram of the S3 path, 4 bullets, the code excerpt, ladder figure, a 4-row R0→S3 table) and **(b) what the tuning sweep ruled out** (chunk size, embedding model, reranker) as a short bullet list with one table. Move the retrieval ladder here from Results |
| evaluation (685 w, 1 diagram, 0 bullets, 3 figures) | Three judges; judge audit 30/30; 65-question tuning results; latency; 55-question sealed results; stress set; fusion; then the final pass in one paragraph | Over budget. Eight prose paragraphs, zero bullets. The final pass, the one that matters, is the last paragraph. All three figures are tuning-era. The measurement protocol (what counts as correct, who judges) is spread across four paragraphs | Make this the **method** section only: diagram, then bullets for sets, judges, gates, cost meter, and contamination disclosure. Move every result to Results. Close with a **judge table**: judge, what it checks, model, calibration evidence, status |
| results (518 w, 0 diagram, 0 bullets, 3 figures) | Disclaimer first; then F1, accuracy, faithfulness; ladder; final outcome confusion; taxonomy; traces in chat; verify funnel; judge calibration miss rates | Opens with "These figures do not show broad-corpus readiness", a limit before the result. Seven prose paragraphs. The metrics table under it shows tuning numbers (section 0, item 3). Judge-calibration rates (0.4433, 0.3966) appear here with no link to the judge story | Open with the headline table (final pass), then 3 figures (final outcome, failure taxonomy, verify funnel) each with a 1-line reading. Bullets for what improved vs the tuning pass. Replace `metrics_keys` with keys that hold final numbers (needs a committed source, see 3.C7) |
| conclusions (1,148 w, 1 diagram, 19 bullets, 2 tables) | Results summary table; lessons; "Exact numbers" (tuning tables); "Current grounding-hardened results" (stress, B); measured alternatives; protocol; limits | Holds almost all tables in the article; the reader meets them last. Repeats the final pass a fourth time. Heading "Current grounding-hardened results" is not current (sets B/stress predate final_v3). Sets C and D are named in Protocol but their results are omitted (C: 10/30 correct, 20 empty; D: 17/30, 9 unsupported, `reports/metrics.json` → `detail.stress_c`, `detail.stress_d`) [V] | Keep: lessons (5 bullets), limits (4 bullets), next step. Move "Exact numbers" into one collapsed appendix table set with neutral headings ("Tuning pass, 65 questions", "Earlier stress sets") and include C and D or drop their mention |
| key_concepts | Six concept cards | Good. Card 6 mixes 17/65 and 1/120 (different sets, different denominators) | Keep; make card 6 qualitative ("verification bounds harm; it does not remove it") or cite one set |
| figure_captions | 11 captions | Five carry "Development history:" prefixes, which is right, but four of those five figures render in sections that also describe the final system | Captions are fine once figures move to the right sections; `fusion_arm_comparison` caption conflicts with prose (3.C5) |

---

## 2. Cross-surface consistency

| Surface | State | Issue |
|---|---|---|
| `README.md:83-102` | Final table matches `f1_summary.json` and `metrics.json` [V] | `whole-wave meter $2.0392` untraceable (3.C1) |
| `docs/projects/01-rag-agent.md:73-143` | Heading "Key results (selected `kimi-for-coding`)" leads with tuning-era numbers; final table at :84-88 | Heading names a provider choice, not the result; "Current grounding-hardened configuration" (:179) is not current |
| `cardCopy.ts:45` | "1 of 120 unsupported claims", "audited 30/30 by a reviewer agent (owner hand-label pending)" | "1 of 120 unsupported claims" reads as claims; it is answers (3.C4) |
| `story.yaml:2` short_version | "Judge sample: reviewer-agent audit 30/30; owner hand-label pending." | Truthful, but spends a third of the 280 chars on an internal audit state. Suggest dropping it from short copy once the owner labels or decides |

---

## 3. Factual claims that need a source or a fix

| # | Claim (where) | Committed evidence | Verdict | Fix |
|---|---|---|---|---|
| C1 | "Cumulative cloud-equivalent spend is $2.04" / "$2.0392" (`story.yaml:279,397`; `README.md:102`; `docs/projects/01-rag-agent.md:88`; `DESIGN.md:413`) | No file under `projects/01-rag-agent/reports/` contains `2.0392` [V]. The final pass meter is `$1.457917` (`final_v3_e2e/metrics.json` → `detail.final_v3.meter.total.spend_usd`, budget `$2.40`) [V]. Judge-calibration labelling logged `cumulative_usd_est 0.094784` (`experiment_log.json`, last judge row) [V] | **Untraceable** | Either commit a wave ledger that sums to 2.0392, or report the final pass at $1.46 |
| C2 | "won every development split" / "won the tournament on every frozen split" (`story.yaml:318-319,413-414`) | recall@5 ties at 1.0 on `dev_40`, `dev_v1`, `heldout_55` and **S1 beats S3** on `dev_65` (1.0 vs 0.9818). S3 leads on **all-articles@5** on every split: 0.906 / 0.891 / 0.9375 / 0.976 vs R0 0.719 / 0.745 / 0.875 / 0.952 (`reports/retrieval_sweeps/*`, `reports/retrieval_baseline/*` → `metrics`) [V] | **Wrong metric named** | "S3 led on all-articles@5 (every chunk of a relevant article in the top 5) on every development split; recall@5 was at or near the ceiling there" |
| C3 | Two accuracy intervals for 0.8667 | Wilson `[0.7944, 0.9162]` (`f1_summary.json`) and `correct_share_ci95 [0.8, 0.925]` (`final_v3_e2e/metrics.json` → `taxonomy`) [V] | **Ambiguous** | Use the Wilson pair everywhere and name the method once (`docs/engineering/statistical-intervals.md`) |
| C4 | "1 unsupported claim in 120" (`story.yaml:2,284,375,511`; `cardCopy.ts:45`) | `taxonomy.counts.unsupported-claim: 1` counts **answers**, not claims. At claim level, 2 of 150 judged claims were unsupported plus 16 mechanical failures (`verify.n_judged 150`, `n_judge_supported 148`, `n_mechanical_fail 16`) [V] | **Unit error** | "1 of 120 answers kept an unsupported claim" |
| C5 | Fusion arm comparison: prose says RRF "trailed sealed raw-layer recall@5 0.952 to 0.976" (`story.yaml:477-478`); caption says "0.533 (RRF) to 0.600 (dense)" (`story.yaml:550`) | 0.9524/0.9762 is `reports/sealed_retrieval.json` (42 answerable of 55); 0.533/0.600 is `reports/fusion.json` → `sealed` (15 questions), which the figure plots [V] | **Two sets, one figure** | Name one set per sentence; the caption must describe what the figure plots (15 questions) |
| C6 | "10 empty-answers" / "10/92 empty-answers" (`story.yaml:276,308,500,538`) | `f1_summary.json` → `errors.false_abstention: 10` and `taxonomy.counts.empty-answer: 10`, but `abstention.false_abstention_rate 0.1196` = 11/92 (`final_v3_e2e/metrics.json`) [V]. FN is 12 | **Two counts** | State one definition: "10 answerable questions got an empty answer; 11 of 92 answerable questions (12%) were not answered, counting the retrieval miss" |
| C7 | Results and Evaluation metric tables (`story.yaml:286-294,356-361` `metrics_keys`) | Keys resolve to `reports/metrics.json` top level: `rag_agent.faithfulness 0.6209`, `retrieval_chunks_200.recall@5 0.8308`, `_meta.created_at 2026-11-16` [V] | **Stale numbers rendered next to final prose** | Either point the Results table at final numbers (needs a committed headline source, owner decision D5 in the orchestrator review) or drop `metrics_keys` from Results and keep them in an appendix labelled "tuning pass" |
| C8 | Faithfulness 0.8717 presented as the answer-quality score | Generator, verifier and judge are all `kimi-for-coding` (`final_v3_e2e/metrics.json` → `meter.phases.{agent,verify,judge}`, `ops.backend env:kimi-for-coding`) [V]. Computed on 92 answerable rows (`rag.n_questions 92`) [V] | **Undisclosed self-judging** | One line: "scored by the same model family that wrote the answers; a cross-judge check is pending" and give n = 92 |
| C9 | final_v3 called "sealed" for the F1 headline (`story.yaml:300,374,387`) | README:88-93 discloses that final_v3 was read for the R0 baseline, the S3 promotion gate, held-out validation and the E2E pass [V] | **Misleading label** | Call it "the final 120-question test set"; put the contamination disclosure next to the first headline, not in Conclusions |
| C10 | Judge audit "30 of 30, Wilson 95% [0.8865, 1.0]" (`story.yaml:224-227,396,483-485`) | `owner_sample_validated.json`: 30 matches, Wilson `[0.886487, 1.0]`, `validated_by: claude-role-audit (pending human owner hand-label confirmation)`; each item stores `kimi_label` beside `validated_label` [V] | **Accurate wording now; not blind** | Keep "reviewer agent"; drop any "blind" wording (tracker:13, :24 still say blind). Replace once the owner labels |
| C11 | Objective "≤ $0.01 a query" (`story.yaml:50,62`) | Final pass: agent + verify = $0.781 + $0.233 = $1.014 / 120 = **$0.0084**; with judging, $1.458 / 120 = **$0.0121** (`meter.phases`) [V] | **Result missing** | Report both; the answer path meets the cap, evaluation cost does not count against it |
| C12 | Latency: article cites p50 25.9 s / p95 108.8 s, 24.4 / 126.8 s, 23.0 / 532 s (all earlier passes) | Final pass p50 **16.5 s**, p95 **40.5 s** (`final_v3_e2e/metrics.json` → `ops`) [V] | **Final number missing** | Add the final latency to the headline table |
| C13 | "Earlier calibrated judges accepted about 44% of unsupported claims" | `judge_calibration_report.json` → `false_acceptance_rate_all_claims 0.44329896907216493` (86/194) [V] | Traceable | none |
| C14 | "local judge … kappa 0.5464; hosted … 0.3966 [0.3269, 0.4707], kappa 0.6052" (`story.yaml:347-349`) | Not re-verified in this review; `judge_calibration_report.json` also holds `0.3563` and `0.4368` unsupported-only rates in other blocks [V] | **Unverified** | Kimi must cite the exact JSON path for each number before reuse |
| C15 | S3 0.9457 vs R0 0.9239; multi-hop 0.8333 vs 0.7917 | `retrieval_sweeps/s3_structure_hybrid_diverse__final_v3.json` (0.94565), `retrieval_baseline/final_v3.json` (0.92391) [V] | Traceable | Define recall@5 here as retrieval-only on 92 answerable questions; the E2E file reports a different recall@5 (0.7583 over 120 rows, `detail.final_v3.retrieval`) [V] |
| C16 | Set B 19/30 = 0.633, 9 unsupported; frozen re-run 22/30 = 0.733, 5 unsupported | `reports/metrics.json` → `detail.stress_b`, `detail.stress_after_r6` [V] | Traceable | none |
| C17 | "uncited_relevant" | `f1_summary.json` → `errors.uncited_relevant: 8` [V] | **Omitted** | Mention once in the failure table (8 answers cited no relevant article) |

---

## 4. Proposed outline for the rewritten article

Pattern per section (owner's guideline): **intro (2–3 sentences) → diagram →
3–6 bullets → table or figure → one-line "In plain terms" card that ends with
the link to the next section**. The renderer treats the last summary marker
and everything after it as the card (`scripts/lint_story_language.py:470-492`,
`StorySection.tsx:9-32`), so the next-step link goes inside the card as its
last line, e.g. `[Next: the data →](#sec-data)`. Section anchors are
`#sec-<id>` (`StorySection.tsx:122`). The eight section ids stay fixed
(`repo-conventions.md`, story contract). Target 250–400 words per section;
Conclusions ≤ 500 plus a collapsed appendix.

| # | Section id | Working heading (bold lead) | Diagram | Bullets cover | Closing table / visual | Next link |
|---|---|---|---|---|---|---|
| 1 | background | "A cited answer, or an honest refusal" | `01-rag-pipeline` (existing) | what it does; who it is for; the one headline (F1 0.909 on 120 questions); what it does not prove | 3-row "at a glance" table: corpus, final test set, headline | → objectives |
| 2 | objectives | "Four targets, set before tuning" | `auto-01-rag-agent-1` (decision flow, existing) | refuse outside the corpus; 0.6 support floor; ≤2 repairs; cost cap; local or hosted model | **Target vs result** table: article recall ≥0.60 → 0.946; refusal → 24/28; cost ≤$0.01 → $0.0084 answer path; latency → p50 16.5 s | → data |
| 3 | data | "A small, pinned corpus makes every claim checkable" | `auto-01-rag-agent-2` (lineage, existing) | five topics; 12,000-char cap; sha256 pins; registry link | **Question sets** table: tuning 65 / earlier gate 55 / final 120 (68/24/28) / stress sets; role; times read | → eda |
| 4 | eda | "Balanced topics, long-tailed lengths" | figure `eda_corpus_composition` as the visual | per-topic range; length cap; anchor checks | 3-row corpus stats table | → training |
| 5 | training | "Better ranking, not a bigger model" | **new**: S3 retrieval path (chunk → dense + BM25 → RRF → rerank → per-article cap) | each stage in one bullet with why; what the tuning sweep ruled out (chunk size, embedding size, reranker effect) | figure `retrieval_ladder`; table R0 / S1 / S2 / S3 on all-articles@5 and recall@5 per split; the code excerpt stays | → evaluation |
| 6 | evaluation | "How a result earns trust" | `auto-01-rag-agent-3` (measurement, existing) | floors; three judges and what each checks; support floor; cost meter; contamination and self-judging disclosure | **Judge table**: judge, checks, model, calibration evidence, status (owner label pending) | → results |
| 7 | results | "104 of 120 correct, 1 unsupported answer" | `auto-01-rag-agent-4` (retrieval → answer → outcome, existing; move from Conclusions) | headline numbers with units and n; improvement vs tuning pass; where failures sit (empty answers, rail stops) | figures `final_outcome`, `failure_taxonomy`, `verify_funnel`; **headline table** (F1/P/R, accuracy Wilson, faithfulness n=92, latency, cost) | → conclusions |
| 8 | conclusions | "Auditable, not unattended-ready" | none new (optional: a small roadmap strip) | 4–5 lessons; 3–4 limits; the next step (new sealed set, cut empty answers, cross-judge, owner labels) | collapsed appendix: tuning pass, earlier gate set, stress sets A–D (all four or none), measured alternatives | → project roadmap or repo link |

Development-history figures (`retrieval_funnel`, `chunk_size_sweep`,
`model_comparison`, `latency_histogram`, `kimi_generation_comparison`,
`fusion_arm_comparison`) move to the Training "ruled out" bullets or the
appendix. At most 3 figures per section (story contract).

---

## 5. Wording problems and suggested replacements

| # | Location | Current | Problem | Suggested |
|---|---|---|---|---|
| W1 | background:9-10 | "Independent set B has 9 unsupported-claim outcomes, over the gate of 6." | Opens on an old negative result with an internal name | "On the final 120-question test, 104 answers were correct and 1 kept an unsupported claim." |
| W2 | background:15-16 | "In `01-rag-pipeline`, follow CPU retrieval…" | Diagram id shown to readers | "The diagram follows one question from search to a checked answer." |
| W3 | all sections | "**Business summary:**" | Legacy marker; the renderer prefers "In plain terms" | "**In plain terms:**" |
| W4 | background:18 | "These were the prior baselines:" | History before the reader knows the result | Move to Evaluation appendix |
| W5 | many | "final_v3", "judge_v2", "S3", "R0", "dev_65" | Internal ids | First use: "the final 120-question test set (final_v3)"; afterwards "the final set". "S3" only inside the Training table |
| W6 | evaluation:210-211 | "Auditable means every claim points to a passage a person can read. A reviewer is still necessary." | Good line; buried under method | Keep as the Evaluation lead |
| W7 | evaluation:220 | "a screen, not proof" (repeated from background:9) | Repetition | Say it once, in Evaluation |
| W8 | results:297 | "These figures do not show broad-corpus readiness." | Limit as the opening line of Results | Open with the result; move the limit to Conclusions |
| W9 | results:304 | "The finalized pass supersedes these tuning figures." | Admits the section shows the wrong figures | Remove once figures move |
| W10 | conclusions:456 | "Current grounding-hardened results:" | "Current" is wrong and time-bound | "Earlier stress sets (before the final pass):" |
| W11 | many | "finalized", "prior", "earlier", "current", "now" | Time-relative words age badly | Name the set: "on the tuning set", "on the final test set" |
| W12 | story:2,284,375; cardCopy:45 | "1 unsupported claim in 120" / "1 of 120 unsupported claims" | Unit (3.C4) | "1 of 120 answers kept an unsupported claim" |
| W13 | training:137 | "FAISS is a library that finds exact nearest matches between embeddings." | Defined two sentences after use | Define at first use or link the glossary |
| W14 | objectives:46-47 | "Bad output fails loudly after a few retries." | Vague | "Malformed output is rejected after at most two retries." (check the retry count in `agent.py` before using) |
| W15 | evaluation:259-266 | "`evaluate --stress`, $1.93, `detail.stress`" | CLI and JSON paths in reader prose | Keep paths in README; article says "a 30-question stress set" |
| W16 | conclusions:510-514 | "S3 hybrid retrieval, a validated judge, and a bounded agent loop…" | "validated judge" overstates (owner label pending, self-judging) | "S3 hybrid retrieval, an audited judge and a bounded agent loop…" |
| W17 | results:334-337 | "Hosted answers cost real money." | Informal, off-topic | Drop or move to Limits |
| W18 | eda:113 | "Dump order is not topical." | Opaque | "The Wikipedia export is not sorted by topic, so a simple quota would fill topics with side pages." |
| W19 | general | em dashes in story (`—` at background:8 and elsewhere) | House rule: avoid em-dash clause joining | Split sentences |

---

## 6. Other project articles (quick structural profile)

From `story.yaml` at HEAD [V]; words / bullets / diagrams per section.

| Pattern | Projects | Note |
|---|---|---|
| Evaluation or Results with **0 bullets** | 01, 03, 05 (eval), 07, 08, 10, 11 (eval), 12 (eval), 13 (eval) | Same "prose wall" problem as 01 |
| Training > 500 words | 01 (565), 03 (555), 05 (507), 06 (631), 09 (586), 12 (537) | Candidates for the split used in 01 §5 |
| Conclusions > 1,100 words | 01 (1,148), 03 (1,470), 04 (1,363), 07 (1,293), 10 (1,191) | Appendix tables belong in a collapsed block |
| No closing table in any main section except Conclusions | all 13 (only 12-results has one) | The owner's "close with a table" rule is new for every project |
| Diagram coverage | background/objectives/data have diagrams almost everywhere; eda/training/results rarely | Results sections have no diagram in any project |

Recommendation: approve the 01 outline first as the pilot, then apply the same
pattern project by project, one handoff each.

---

## 7. Owner decisions

| # | Decision |
|---|---|
| A1 | Approve the section outline in §4 (or amend headings/diagrams). |
| A2 | Spend figure: commit a wave ledger for $2.0392, or switch copy to the final-pass $1.46. |
| A3 | Results metric table: point `metrics_keys` at final numbers (needs a committed headline source; ties to orchestrator D5) or drop them from Results. |
| A4 | Stress sets C and D: report them in the appendix, or drop the mention. |
| A5 | Hand-label the 30-item judge sample now, or keep the reviewer-agent wording until a cross-judge check exists. |
| A6 | Pilot on 01 only, then roll out to 02–13. |
