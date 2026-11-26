# Review: 10-uplift-experimentation article (Wave 6.6)

- Target: `projects/10-uplift-experimentation/story.yaml` (516 lines)
- Gold template: `projects/01-rag-agent/story.yaml`
- Reviewer stance: senior ML writer and reviewer, read-only
- Note on the diff: `git diff -- projects/10-uplift-experimentation/story.yaml` is **empty**. The Wave 6.6 edits are already committed in `18adc59d` ("align projects 02-13 to 01 gold template"). This review covers `HEAD` and uses `git show 18adc59d` as the diff for this round.
- Evidence checked: `reports/metrics.json`, `reports/segment_summary.json`, `reports/figures/*.json`, `reports/report.html`, `reports/single_protocol/{metrics.json,report.md}`, `README.md`, `DESIGN.md`, `MODEL_CARD.md`, `src/uplift_experimentation/{models.py,cli.py,evaluate.py}`.

## What this round changed

- Renamed "Business summary" to "In plain terms" in all eight sections.
- Added a closing transition with an anchor link to sections 1–7.
- Changed roadmap titles to verb-first and removed trailing periods.
- Compressed the Background paragraph. The compression introduced one meaning error (see Fix 4).
- Removed "$0.30" from roadmap card 4 and "3,063 / 21,306" from card 1. Both details are now vaguer.

## Grades

| # | Dimension | Grade |
|---|---|---|
| 1 | Structure and article logic | 6 |
| 2 | Engagement and human-like narrative | 5 |
| 3 | Language quality | 5 |
| 4 | Technical detail depth | 8 |
| 5 | Truthfulness | 5 |
| 6 | Roadmap cards | 7 |
| 7 | Consistency with gold template style | 7 |
| | **Overall** | **6** |

### 1. Structure and article logic: 6

- Every section from Background to Results now ends with a transition and an anchor link. The chain is complete.
- Figures sit in the wrong sections. Training (L198–259) hosts the CUPED variance read and the full multi-arm planning money ($35.5k / $16.6k / $49.8k / ≈$0.31). CUPED is an experiment-read result and belongs with EDA or Results. Multi-arm planning is a policy result. As placed, the reader meets channel-planning dollars before the two-arm policy race has been explained. L201 ("The channel-planning figures below use these scores") admits the figures are only loosely tied to the section.
- Evaluation (L262) opens with the final verdict ("Use targeted sends when … Otherwise, mail everyone") before Results presents the evidence for it.
- Conclusions (L343–491) is about 150 lines long. It repeats almost every number from earlier sections (break-even, 2× hot, CUPED, $49.8k, 76.0/20.2/3.8) and adds the only places where the T−X comparison and the cost grid appear. Readers get duplication with little synthesis.
- The Results lead (L290–292) is a three-clause list that is mostly negative. Its plain-terms card (L336–338) then adds "multi-arm best-arm beating random", which the lead leaves out.

### 2. Engagement and narrative: 5

- The article lacks a human hook. The gold opens on a user-facing outcome. This one opens on a definition ("Uplift is the extra buying an email causes").
- The prose reads like a checklist of instructions: "Start with…", "Next, compare…", "Read the…", "Check whether…". Section 1 of the gold carries a story; this article carries a protocol.
- L59–61 is the strongest opener. L178–183 (visits versus purchases) is the most concrete passage and reads well.
- The seven transitions all use one template ("The X …; next, the Y ([Z →])"). By the fourth one this becomes mechanical (see Dimension 7).

### 3. Language quality: 5

- "Revenue minus send cost" appears **24 times**. It is fused into compounds such as "revenue-minus-send-cost-at-budget CI" (L29) and "raw revenue minus send cost" (L23, L34, L50, L275, L305). Define one short term once, such as "net value", and use it from then on.
- "Model-estimated" appears 6 times, and "spans zero" appears in nearly every section.
- L66–67: "the policy race, a recipient-selection rule". The appositive now defines the *race* as a rule. This round's compression broke the earlier "A policy is a recipient-selection rule."
- L275–276: "The best targeting share drops below everyone near $0.20". "Below everyone" does not parse. It should say below 100% coverage.
- L117–118: "The money metric judging uses 1,000 paired bootstraps". The noun stack is ungrammatical.
- L125: "judge each on revenue minus send cost, and an honest interval". The comma breaks the coordination.
- L60 is a 124-character source line produced by the edit. Not a rendering issue, but it is untidy against the wrapped lines around it.
- L417: "Its standard error … is 0.09". The unit (pp) is missing. README L39 gives "SE 0.09pp".
- L150–154: the definition of "log-transformed" is wedged between list items ("log-transformed spend history, a scale that compresses large values, plus recency…"). That makes a hard-to-read sentence.

### 4. Technical detail depth: 8

- Strong points: the cross-fitting code excerpt, the paired-bootstrap logic, the DR/IPW observed-versus-planning separation, the analytic break-even, the honest CI tables, and the scoping of the X-learner's weakness to strong overlap and near-constant propensity (L328–331).
- The article does not explain why two intervals exist for the same Mens/T-learner score of 12.03: [0.77, 24.39] (L350, seed 1041 two-arm bootstrap) and [−0.47, 24.21] (L351, seed 2041 per-arm bootstrap). The committed `reports/single_protocol/report.md` gives a third: [−0.0135, 24.18]. An expert will read this as a lower bound that is sensitive to the bootstrap seed. The honest statement is that the T-learner's Qini is borderline, not that it is "12.03 [0.77, 24.39]" in one place and "not established" in another.
- "Predicted magnitudes run about 2× hot" (L19, L271, L370, L437, L475) holds only at the top decile: predicted 0.0250 versus measured 0.0111 (`metrics.json` `multi_arm.per_arm.mens.deciles`). Across all deciles the mean prediction (≈0.0069) matches the measured mean (≈0.0068). The bottom decile is predicted *negative* (−0.0083) but measured at +0.0033. The accurate description is "the predicted spread is about 2× too wide", not "magnitudes are 2× hot". That difference matters for the planning dollars, which sum predictions.
- The article does not mention the hand-rolled causal forest in `reports/single_protocol/` (Qini −3.53 [−16.2, 9.70]). Leaving it out is defensible, but it is a fourth learner an expert would want to hear about.

### 5. Truthfulness: 5

Verified against committed files (no issue): 42,613 / 64,000 / arm sizes (`segment_summary.json`); visit 18.3/15.1/10.6%; conversion 1.25/0.88/0.57%; mean spend ~$241–243; +$2,812, $6,838, $4,026, $16,103 and the response/X rows (`metrics.json`); Qini table, paired CIs, −$9,265 [−$13,125, −$5,808], 3,063 per arm, SE 0.09pp, CUPED 0.08/0.52/0.12/0.95% (`README.md`, `cuped_variance.json`, `report.html`); cost grid $16,103 / $12,268 / $8,065 [$8,007] / $4,230 [$3,745] / $1,618 [−$4,777] with 100/90/25% shares (`cost_sensitivity.json`, `report.html`); break-even 0.2999 (`demo_payload.json`); multi-arm $35,514 / $29,487 / $16,563 / $49,819, 0.308, 76.0/20.2/3.8%, all DR/IPW numbers and CIs, per-arm AUUC and incremental CIs (`metrics.json` `multi_arm`); seeds 1041/2041/3041 (DESIGN `seed+999/1999/2999`) and 1042 (`cli.py` `seed + 1000`); ~61 of ~145 (README L77).

**Untraceable (1)**

| Line | Claim | Status |
|---|---|---|
| L395 | "T-learner − X-learner, rev. minus send cost @25% \| [−$323, $4,343]" | Not found in `metrics.json`, `README.md`, `report.html`, `DESIGN.md`, or `demo_payload.json`. |

Evidence-chain gap (not counted as untraceable): README L181–184 says `reports/metrics.json` carries `_meta.ci`, `_meta.cost_sensitivity`, `_meta.cuped`, `_meta.power`, and `_meta.cuped_multivariate`. The committed `_meta` holds only provenance keys. The two-arm Qini CIs, paired differences, cost grid, CUPED, and power numbers can therefore be traced only to the README prose, `report.html`, and figure JSON, not to a metrics file. This is a project-artifact issue, but the article's numbers depend on it.

**Contradicted or misleading (6)**

| Line | Claim | Evidence |
|---|---|---|
| L13, L182, L187, L194 | "conversion rises materially only for Mens"; "Only the Mens email clearly increased conversion"; "a converting email with a non-converting one"; "The Womens email moved visits only" | Womens conversion is 0.884% versus 0.573% (+0.31pp, z≈3.8). The article's own L428–429 gives Womens incremental conversions 66.5 [33.10, 104.69], which excludes zero. The Womens email *did* raise purchases, by less than Mens. |
| L363–365 | "The T-learner loses the Qini race to the response model but wins on revenue minus send cost" | L300 and L393 say the response − T Qini CI [−8.18, 9.52] spans zero ("ranking not established"). "Loses" is an overclaim. "Is nominally lower on Qini" is accurate. |
| L347–349 | "On 64,000 randomized customers …, the T-learner ranking beat random … by +$2,812" | The +$2,812 result is on the 42,613-row two-arm frame (`metrics.json` `t_learner`; README L35). The short version (L3) states this correctly. |
| L276–277 | "Above ≈$0.30, the top-25% list wins outright" | At $0.30 the best share is 90% ($4,230). The top-25% policy is about $3,749, barely above mail-everyone ($3,745). Top-25% becomes the best share only at the $0.50 grid point. "Beats mail-everyone above ≈$0.30" is accurate; "wins outright" is not. The same imprecision appears in key concept L500. |
| L183, L441 | "rare purchases, near a 0.9% baseline"; "~0.9% base conversion" | The no-email baseline is 0.57% (L13, L180). 0.9% is the pooled three-arm mean, which includes treated customers. README L41 says "~1% base rate". |
| L50, L252, L436 | "Unconstrained mail-everyone-Mens leads … at $49.8k until sends cost ≈$0.31" | It leads *best-arm at the 25% budget*. Unconstrained best-arm is model-estimated at $66,253 (`multi_arm.policies.best_arm.profit_full`). The comparator should be named. |

Imprecise but traceable: "2× hot" (see Dimension 4), and "12.03 [0.77, 24.39]" presented without noting the seed sensitivity (L350).

### 6. Roadmap cards: 7

- All titles are verb-first. All details are ≤90 characters (longest: 66). Statuses are sensible: four shipped, one next.
- Card 1 detail, "arm sizes cover the power need", is vaguer than the previous "power needs 3,063 per arm, 21,306 available". This round traded the evidence for padding.
- Card 4 detail, "overtakes mail-everyone above the break-even cost", is circular. Restore "≈$0.30 per email".
- Card 5, "Decide the next live-campaign test", is weak. "Decide" is not a deliverable. Better: "Run a prospective randomized holdout".
- Card 3 detail is accurate and well bounded.

### 7. Consistency with the gold template: 7

- "In plain terms" cards appear in all eight sections and match the gold's position and bold label.
- The transitions match the gold's link format `([Section →](#sec-x))`. The gold varies the sentence ("next, we trace how…", "Below, `retrieval_ladder` charts…; next, we examine…") and ties the transition to the next section's content. This article repeats one template seven times ("The figures set the trust level; next, …", "The claims are bounded; next, …").
- The gold's plain-terms cards each carry one headline number. Several of this article's cards are number-free ("Cross-fitting protects every score. CUPED barely reduced variance."). The Data card is a near-copy of the Data lead.
- The gold names figures in backticks (`retrieval_ladder`). This article uses prose names ("the segment-profile figure"). That is acceptable, but it differs from the gold.

## Top 5 fixes (by severity)

1. **Correct the Womens-conversion contradiction.** `story.yaml` L13 "conversion rises materially only for Mens", L182 "Only the Mens email clearly increased conversion", L187 "a converting email with a non-converting one", L194 "The Womens email moved visits only". Replace with: both emails raised purchases, Mens by +0.68pp and Womens by +0.31pp (incremental 66.5 [33.1, 104.7]). Pooling would average a strong effect with a weak one.
2. **Remove the "loses the Qini race" overclaim.** L364 "The T-learner loses the Qini race to the response model". Replace with "is nominally lower on Qini (13.01 vs 12.03; paired CI spans zero) but wins on net value at the 25% budget." This keeps the lesson and matches L300/L393.
3. **Fix the frame size and the cost-sweep wording.** L347–348 "On 64,000 randomized customers": change to 42,613 (two-arm frame). L276 "the top-25% list wins outright": change to "the top-25% list beats mail-everyone; the best share falls to 25% by $0.50". Apply the same correction to L500. While there, fix the baseline at L183 and L441 "0.9% baseline" to 0.57% control, and name the comparator at L50 and L252 ("leads best-arm at the 25% budget").
4. **Repair the language damaged this round and cut the 24 repetitions.** L66–67 "the policy race, a recipient-selection rule": restore "A policy is a recipient-selection rule." L275 "drops below everyone": change to "drops below 100% coverage". Define "net value (revenue minus send cost)" once in Objectives L108 and use "net value" afterwards. That removes clumps such as L29 "revenue-minus-send-cost-at-budget CI". Also fix L117 "The money metric judging uses" and the L417 missing "pp".
5. **Source or drop the untraceable number, and reconcile the duplicate Qini CIs.** L395 "T-learner − X-learner … [−$323, $4,343]" has no committed source. Ask the implementer to commit `_meta.ci` into `reports/metrics.json` (README L181 already promises it), or delete the row. At L350–352, state that the same 12.03 score has a lower bound between −0.47 and +0.77 depending on the bootstrap, so the Qini above zero is borderline. Also restate "2× hot" (L19, L271, L370) as "the predicted spread is about 2× too wide at the top decile".

Second-tier (structure, not truth): move the CUPED and multi-arm planning paragraphs (L238–252) out of Training into EDA and Results. Restore "≈$0.30" in roadmap card 4 (L513) and "3,063 per arm" in card 1 (L504). Vary the seven "…; next, the …" transitions so each previews the next section's content, as the gold does.
