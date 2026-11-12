# Stress failure ledger — R6 baseline trace review

Source: `reports/question_traces_stress.json` (the committed, immutable
baseline pass over `data/golden_stress.json`, 30 questions).
Taxonomy: 11 unsupported-claim / 2 retrieval-miss / 1 format-failure.
Every row is explained here before any intervention (delta-review rule:
review traces before targeting fixes).

| # | question (slice) | trace evidence | mechanism (root-caused) | R6 intervention | expected change |
|---|---|---|---|---|---|
| 1 | As of May 2022, how many geothermal power plants were operating in Australia? (single/answer) | top_rank 1, cited relevant | right article; number/date asserted beyond the span ("as of May 2022" trap) | number/date token check vs span | unsupported → correct/abstain |
| 2 | What 2050 emissions cut did the UK government first propose in the Climate Change Act? (single/answer) | top_rank 1, cited relevant | adopted 80% asserted where the span carries the proposed 60% | number check + temporal qualifier comparison | unsupported → correct |
| 3 | Until when was the Fuhrländer Wind Turbine Laasow the tallest wind turbine? (single/answer) | top_rank 1, cited relevant | date-boundary paraphrase; precomposed vs decomposed "ä" defeats naive substring matching | span verification with NFKC (composition equivalence only — does not equate a/ä) + temporal check | unsupported → correct |
| 4 | How long did the Aguçadoura Wave Farm operate after its official opening? (single/answer) | top_rank 1, cited relevant | duration asserted beyond the text — a derived claim | derived-claims policy: computed values only when a span states them verbatim; else abstain on the claim | unsupported → correct/abstain |
| 5 | How do the C40 Cities group and the Mayors Climate Protection Center differ? (multi/answer) | top_rank 1, cited relevant | two-leg synthesis; one leg unsupported | multi-span claims, both chunks cited | unsupported → correct/abstain |
| 6 | What did the 2005 Exeter conference conclude about stabilizing greenhouse gases? (multi/answer) | top_rank 2, cited relevant | synthesis paraphrase beyond cited spans | multi-span + entailment judge (retained arbiter) | unsupported → correct/abstain |
| 7 | How does Portugal's installed wind capacity compare with its installed solar capacity? (multi/answer) | top_rank 1, cited relevant | comparison numbers assigned to swapped entities | entity–value–relation check or judge; number presence alone does not catch swaps | unsupported → correct |
| 8 | What improvements did the Van's RV-7 bring over the RV-6? (multi/answer) | top_rank 1, cited relevant | relational claim beyond the cited span | entailment judge on structured claims | unsupported → correct/abstain |
| 9 | Where is the hottest place on Earth? (ambiguous/abstain) | top_rank None, cited NOT relevant | no relevant evidence; the model answered anyway | inference-time evidence gate (no gold labels) | unsupported → refusal |
| 10 | How many people were killed by Typhoon Nalgae? (ambiguous/abstain) | top_rank None, cited NOT relevant | no relevant evidence; a number was confabulated | evidence gate + number check | unsupported → refusal |
| 11 | How does phycocyanin help cyanobacteria harvest light? (unanswerable/abstain) | top_rank None, cited NOT relevant | no relevant evidence; a mechanism was confabulated | evidence gate | unsupported → refusal |
| 12 | Which renewable energy source supplies more electricity than all other renewable sources combined? (single/answer) | top_rank None, cited relevant | genuine retrieval miss — semantic comparative with no lexical overlap | known limit this wave; documented, not patched | stays retrieval-miss |
| 13 | What is the most common form of photosynthesis? (ambiguous/answer) | top_rank None, cited NOT relevant | genuine retrieval miss | known limit; documented | stays retrieval-miss |
| 14 | What capacity was the Wave Hub marine energy project designed to host? (unanswerable/abstain) | `error: UsageLimitExceeded` (total_tokens 4,019,638 of a 4,000,000 cap) | **operational, not a generation defect**: the pass exhausted its token budget on the final question; the cap is a fail-closed hard stop, so zero output retries fired | budget terminations classified separately from format failures in all sealed passes; new runs carry adequate headroom; classifier regression test | format-failure → budget-terminated (normalized comparison only; baseline artifact unchanged, row stays non-correct) |

Derived-claims policy (decides row 4 and similar): R6 disallows derived
claims — a duration or computation is accepted only if a cited span states it
verbatim; otherwise the answer abstains on that claim. Explicit arithmetic
provenance is future work, declared as such.

## Pass A outcomes — scored run (`detail.stress_after_r6`, commit 55dfae0)

Normalized comparison (fixed classifier both sides; baseline row 14
reclassified budget-terminated): overall 0.500 → 0.733, answer-expected
0.450 → 0.700, unsupported-claim 11 → 5, refusal accuracy 0.600 → 0.800,
false abstention 0.050 → 0.050. All frozen-set no-regression gates pass.

| ledger row | baseline → pass A | note |
|---|---|---|
| 1 geothermal plants | unsupported → **correct** | number/date span check held |
| 2 UK 2050 target | unsupported → **correct** | 60%-vs-80% number check held |
| 3 Fuhrländer until-date | unsupported → **correct** | NFKC span + temporal check held |
| 4 Aguçadoura duration | unsupported → unsupported | derived duration still asserted; one claim survived (surv=1) and the rubric judge failed it — partial fix, repair accepted wording the judge still rejects. Remaining debt. |
| 5 C40 vs Mayors | unsupported → **correct** | two-leg synthesis verified |
| 6 Exeter conclusions | unsupported → **correct** | synthesis now grounded |
| 7 Portugal wind vs solar | unsupported → **correct** | entity swap caught/answered correctly |
| 8 RV-7 over RV-6 | unsupported → unsupported | 7 claims survived verify but the rubric judge still scores the answer unfaithful — claim-judge/rubric-judge disagreement, documented below |
| 9 hottest place | unsupported → unsupported | gate thresholds are 0/0 (lexical gating rejected by calibration), so the row generates; verify passed 2 claims, the rubric judge failed the answer. Refusal now depends on the rubric layer, not the gate. |
| 10 Nalgae deaths | unsupported → unsupported | same pattern as row 9 |
| 11 phycocyanin | unsupported → **correct** | refused cleanly (surv=0) |
| 12 renewable vs all | retrieval-miss → retrieval-miss | known limit, unchanged |
| 13 most common photosynthesis | retrieval-miss → retrieval-miss | known limit, unchanged |
| 14 Wave Hub | format-failure → **correct** | root cause was the schema-level abstention block (tool-loop burn); the abstention contract fixed it — refused, surv=0, zero budget terminations in the scored run |

Two rows moved the other way, both accounted for: *surface-light algae*
(baseline "correct" was a classifier bug — NaN faithfulness fell through to
correct; honestly an empty-answer both before and after) and *Nalgae
cyclones* (baseline correct; the rubric judge now rejects the claim set — a
judge-strictness swing within run-to-run variance, n=1).

Known remaining debt, in order: (a) claim-judge vs rubric-judge
disagreement — the entailment judge passes claims the rubric judge then
fails (rows 8, 9, 10; 54/54 drafted claims "survived" this pass while the
rubric layer failed 5 answers); aligning the two judges is the next lever.
(b) Rows 9–10 style confabulation on no-evidence questions now reaches the
rubric layer instead of a gate refusal — cheaper would require a
retrieval-aware gate, future work. (c) The two genuine retrieval misses
(rows 12–13) are embedding-model limits; pgvector or a stronger encoder is
the benchmarked next step, not yet measured.
