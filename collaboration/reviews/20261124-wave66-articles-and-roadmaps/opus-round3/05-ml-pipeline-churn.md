# Round-3 review: 05-ml-pipeline-churn story.yaml

Reviewer: Claude (Opus), read-only senior ML writer/reviewer pass, round 3
Target: `projects/05-ml-pipeline-churn/story.yaml`, **working tree** (394 lines, uncommitted Wave 8 edits on `wave8-articles-truthfulness-2026-11-25`, HEAD `c05accd0`)
Gold template: `projects/01-rag-agent/story.yaml`
Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/05-ml-pipeline-churn.md`
Date: 2026-11-26

All line numbers refer to the working-tree file. Every round-2 finding was
re-checked against that file and the evidence, not taken from the round-2 text.

## Evidence checked this round

- `reports/metrics.json`, `reports/sensitivity.json`, `reports/dq_report.md`
- `data/operating_policy.json`, `data/model_selection.json`, `data/dataset_contract.json`, `params.yaml`
- `data/churn.parquet`, `data/holdout.parquet`: shape and columns read; churn rate, mean charges and tenure, and senior and fiber churn recomputed
- `reports/figures/{bootstrap_ci,permutation_importance,fairness_slices,eda_churn_profile,calibration_curve}.json`: binary arrays decoded, panel titles and traces read
- `data/selected_model*.pkl` loaded with the repo `.venv` to test the isotonic-ties claim. The model gives 1,238 unique holdout scores raw and 283 calibrated, so the claim holds.
- `src/churn_pipeline/{evaluate.py,model.py}`: bootstrap `point` definition, feature schema
- `README.md`, `DESIGN.md` (working tree, with their Wave 8 diffs)
- `apps/showcase-web/src/diagrams/churnCycle.ts` and `auto/05-ml-pipeline-churn-{1,2,3,4}.ts` (working tree; `churnCycle.ts` and `-3.ts` were edited in Wave 8)
- `docs/data-registry/telco-churn.md` (21 columns)

## What Wave 8 changed

- Background L15 now says 5,634 training rows. Dollar units are used throughout the prose, and "bootstrap saving" became "cost delta".
- The stale CI −485/−343 was replaced with −508/−353 in `churnCycle.ts` L70 and `auto/05-ml-pipeline-churn-3.ts` L31.
- The EDA section dropped the non-existent senior and fiber panels and now says "both figures".
- Training dropped the F1-first and Optuna 25-trial claims. It now states the 80/20 base-learner carve-out, 10-bin ECE, the FN=3 calibration gain, and the correct permutation-importance order with values.
- Conclusions dropped the untraceable −90 [−159, −26] and the CV cost 2,416, and added the isotonic-ties explanation and raw versus calibrated OOF cost (2,440 vs 2,425).
- Results was rewritten as a claim plus two short paragraphs.
- The link row and the diagram fence were fixed.
- Roadmap details were made concrete, and the last card became `next` with a named gate.
- README and DESIGN were brought into line on the logistic interval, the search claims, the FN=3 gain, and the importance order.

## Grades

| # | Dimension | R1 | R2 | R3 |
|---|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 | 7 |
| 2 | Engagement and human-like narrative | 5 | 6 | 6 |
| 3 | Language quality | 5 | 5 | 6 |
| 4 | Technical depth | 8 | 8 | 9 |
| 5 | Truthfulness | 6 | 5 | 6 |
| 6 | Roadmap cards | 6 | 6 | 8 |
| 7 | Consistency with gold template | 7 | 7 | 7 |
| | **Overall** | 6.3 | 6.3 | **7.0 / 10** |

Lowest dimensions: engagement (6), language (6), and truthfulness (6).

Every number in the article now traces to a committed artifact. Truthfulness
stays at 6 for a different reason: the prose tells the reader what three
diagrams show, and in each case the diagram shows something else.

## 1. Structure and article logic (7)

The arc is sound: problem, cost objective, data and gates, EDA, training,
evaluation, fairness, then exact tables, protocol, and limits. Results is now
short and no longer copies the Limits list.

Remaining problems:

- **L19.** "the cost-model diagram that sets the gates". The objectives diagram (`auto/...-1.ts`) has six nodes: cost model, candidates, grid, argmin, served policy, and stability vs FN price. None of them is a gate. "Gates" still carries three meanings in this article: data-quality gates, success tests, and rollout gates.
- **L81.** "use the churn-profile figure to set the judging rules". The rules (L96-104) are prose. The figure sets nothing.
- **L245-247, L311-312.** Both lines refer the reader to "the pipeline diagram" for things it does not contain. See truthfulness items C1 and C2.
- **Headline repetition is still heavy.**
  - "$601 vs $1,035" or "42%" appears at L3, L17, L21, L141, L180, L212, L240, L277, L283, L352, L360, and captions L384/L388.
  - The interval [−508, −353] appears at L3, L17, L242, L285, L296, L363, and caption L394.
  - Both diagrams print the interval as well.
  - Three copies in the background alone (L3, L17, L21) is one too many.
- **L193-195 and L332-334 against L286-287.** The article says twice that a second paired bootstrap compares the policy with logistic-at-0.5, then says the result is not retained. A reader is left asking why the comparison is mentioned at all. Either persist it or drop the comparator from L193-195 and L332-334.

## 2. Engagement and human-like narrative (6)

The opener and the plain-terms cards work. Transitions now have a subject and
a verb ("We next…"). The body still reads as assembled:

- **Inline "X, or Y," glosses remain:**
  - L40 "A grid, or list, of 41 thresholds"
  - L61 "null, or missing-value, rates"
  - L76 "outlier, or extreme, charge"
  - L186-187 "a CRM, or customer relationship management, system"
  - L203 "Rollout, or real release"
  - L72 "probabilities, scores from 0 to 1,"
  The worst chain (drift / seasonality / causation) is gone.
- **Imperative figure-reading openers remain:** L60 "Follow both source branches", L88 "Compare the contract bars", L123 "Start with the flat line", L126 "Compare the logistic policies", L148 "Read permutation importance from top to bottom", L190 "Follow the measurement chain". Results (L216) now opens with a claim, which is better.
- **New, L132-133.** "The selection artifact records its settings. It has no valid trial count or search score, so this article makes no claim about them." This is an audit note to the maintainer, not narrative. Readers do not need to know that a JSON field is NaN. Say "The selected settings are listed in the record table" and move the caveat to L306, where it already appears.
- **Some terms are still defined more than once.** "Calibration error" is defined at L102-104 and ECE again at L138-140. Holdout is defined at L31-32 and the idea recurs at L70.

## 3. Language quality (6)

Improved since round 2:

- The broken wrap is fixed.
- The F1-first non sequitur is gone.
- The link row renders as its own paragraph.
- The fence is correctly indented.
- Units are dollars in the prose.

Remaining:

- **L245-247.** "The pipeline diagram separates the raw and isotonic model paths. That comparison gives the ECE improvement…" A diagram cannot produce a metric, and this diagram does not show those paths (see C1).
- **Unit drift:**
  - L26 "costs `1,870`" has no `$`, though L8 just priced errors in dollars.
  - Captions L384, L388, and L394 are unitless.
  - The hero diagram (`churnCycle.ts` L69) says "601 cost units".
- **L241, L284.** "The mean bootstrap cost delta is `−$434`" (see N1).
- **Source line lengths.** L132, L134, L138, and L217 run far past the file's wrap width. This does not affect rendering, but the diff noise suggests a hand-merge.
- **L203-204.** "Rollout, or real release, therefore needs a time-stamped feed". The "therefore" does not follow from "this snapshot has no time axis" alone. Make it explicit: "so a time-ordered test needs…".

## 4. Technical depth (9)

All four round-2 depth gaps are addressed:

- AUC drop from isotonic ties, L279-281. Verified: 1,238 unique holdout scores fall to 283 after calibration.
- 80/20 base-learner and calibrator carve-out, L134-136 and L322-323.
- Grid spacing of 0.025 and the small OOF cost gap of 2,440 vs 2,425, L191 and L325-326.
- 10-bin ECE, L138 and L330.

The priced-confusion-matrix objective, OOF freezing, sensitivity re-freezing,
and raw-versus-served fairness separation remain the article's strength.

One small gap remains. The OOF gap of 15 on 5,634 rows is called "small", but
the article does not say whether neighbouring thresholds (0.150, 0.200) cost
nearly the same, that is, whether 0.175 sits on a flat basin. One sentence from
`training_predictions.npz` would settle it.

## 5. Truthfulness (6)

### Numbers verified

| Claim | Lines | Source | Result |
|---|---|---|---|
| 7,043 rows, 21 columns, sha256 pin | L8, L55-56 | `dataset_contract.json`, `docs/data-registry/telco-churn.md` L10 | match |
| $1 / $5 costs | L8, L262-263 | `params.yaml` fp_cost, fn_cost | match |
| 5,634 / 1,409, 80/20, seed 42, calib 20% | L15, L69-70, L321-323 | `operating_policy.json` n_train; `params.yaml` calib_frac 0.2, seed 42 | match |
| 26.5% churn, 374 churners | L55, L124, L264 | parquet mean 0.2654; 0.2654 × 1409 = 374 | match |
| 73.5% contact-nobody accuracy, $1,870 | L26, L125 | 1 − 0.2654; 374 × 5 | derived, correct |
| null rate 0.000, ranges, binary churn | L117-118 | `reports/dq_report.md` | match |
| 42.7% / 2.8% contract churn | L89, L380 | `eda_churn_profile.json` (0.4271, 0.0283) | match |
| $74 vs $61, 18 vs 38 months | L90-91 | parquet group means (74.44 / 61.27; 17.98 / 37.57) | match |
| EDA figure has contract, charges, and tenure panels only | L89-90 | figure annotations | match |
| 691 / 655 / 644 / 601 / 1,035; ROC-AUC and F1 table | L127-141, L271-277 | `metrics.json` | match |
| thresholds 0.450 / 0.225 / 0.175; OOF costs 2,440 / 2,425 | L128, L141, L307, L325 | `operating_policy.json` | match |
| 41-point grid 0.00-1.00, step 0.025 | L40, L191, L265 | `params.yaml` threshold_grid | match |
| ECE 0.028 → 0.016, 10 bins | L138-140 | `metrics.json`; `params.yaml` calibration_bins 10; figure subtitle | match |
| XGBoost params; no trial count or score | L306 | `model_selection.json` (`n_trials: 0`, `best_score: NaN`) | match |
| AUC drop explained by isotonic ties | L279-281 | checked by reloading the persisted models (1,238 → 283 unique scores) | supported |
| FN 3/5/8: thresholds, costs, CIs; calibration gain at all three | L142-147, L293-297 | `sensitivity.json` | match |
| permutation importance 0.213 / 0.174 / 0.088 / 0.033, 5 repeats | L149-151, L389-390 | decoded `permutation_importance.json` | match |
| fairness recalls; 27 of 36; 9 of 9 | L217-224, L308 | `fairness_slices.json` (one-year recall 0.25; two-year cost 45 = 9 × 5) | match |
| 4 model features of 21 source columns | L227, L349 | `model.py` telco schema: tenure, charges, contract, internet_service | match (round-2's "6 features" fix was wrong; 4 is correct, as gender and senior are slice-only columns) |
| −41.9%, CI [−508, −353], n = 2,000 | many | `sensitivity.json` fn5, `bootstrap_ci.json` subtitle | match |
| synthetic 8.8% churn, 9,999 outlier | L76, L336 | README L19, L43, L76 | match (prose source) |

**Untraceable-number count: 0.** Both round-2 untraceable numbers were removed.

### Contradicted or misattributed claims

**C1. L245-247 and L346-348: contradicted by the diagram (pre-existing, not caught in round 2).**
- L245 says "The pipeline diagram separates the raw and isotonic model paths."
- L346 says "The pipeline diagram keeps raw and calibrated serving separate."
- `auto/05-ml-pipeline-churn-4.ts` is a preprocessing DAG: raw CRM row → OutlierCapper → MissingValueIndicator → impute + scale, with a contract → one-hot branch, both joining at ColumnTransformer → classifier → predict_proba.
- The diagram has no isotonic node and no raw/calibrated split.

**C2. L311-312: contradicted (pre-existing).** "Follow the raw and calibrated branches to keep the search, synthetic, and fairness records attached to the right path." The same diagram has none of those branches or records.

**C3. L190-192 against diagram `auto/05-ml-pipeline-churn-3.ts`: contradicted (pre-existing).**
- The text says to "Follow the measurement chain from left to right. Three-fold OOF predictions price a 41-point cutoff grid…".
- The diagram's leftmost node is "frozen holdout · 1,409 rows · score every candidate", which flows into "41-point threshold grid" and then "cost-optimal threshold".
- Read left to right, the diagram shows the threshold being chosen on the holdout. That is the exact leak the article rules out.
- The watch-item node reads "same-holdout optimism, served-policy fairness". L200 instead describes the first watch item as row-resampling noise.
- Wave 8 edited this file's CI label but left the stale flow in place.

**C4. L10 hero diagram against L132-133 and L306: newly exposed by Wave 8.**
- `churnCycle.ts` L33 still prints "Cost-aware Optuna HPO (25 trials × 4 arms) selected XGBoost on the real track."
- The article now correctly says the selection artifact has no valid trial count.
- README L47-48 also still says "~25 trials, median pruning".
- The first diagram a reader sees therefore asserts a claim that the article body disowns.

**C5. L217: contradicted (pre-existing).** "Each bar shows recall at its OOF-frozen 0.225 threshold." The fairness figure plots recall, precision, and F1 bars per slice, plus a separate slice business-cost panel.

**C6. L225: contradicted (pre-existing).** "recall alone cannot verify a budget result." This overlooks that the same figure shows per-slice cost.

**N1. L241 and L284: mislabelled (NEW in Wave 8).**
- The article says "The mean bootstrap cost delta is `−$434`". In `sensitivity.json` and `bootstrap_ci.json`, −434 is the `point` field.
- `evaluate.py` L240 computes that field as the observed holdout delta (601 − 1,035), not as a bootstrap mean.
- The mean of the binned bootstrap distribution is about −433, so the number is right but the label is wrong.
- Round 2's wording, "bootstrap point", was correct. Use "observed cost delta".

**N2. L19 and L29: misattributed (pre-existing, minor).** "The diagram also sets three tests for success." The objectives diagram shows a pipeline of six nodes, not three tests.

Contradicted: 6 (C1-C6). Mislabelled or misattributed: 2 (N1, N2). Untraceable: 0.

## 6. Roadmap cards (8)

| Title | Detail chars | Status vs repo | Issue |
|---|---|---|---|
| Pin one reproducible panel and twin | 76 | shipped: ok (`dataset_contract.json` sha256, synthetic track) | The detail talks about split sizes, not pinning. Mention the sha256 pin instead. |
| Choose the cutoff from OOF cost | 72 | shipped: ok (`operating_policy.json` 0.175; `metrics.json` 601) | "OOF" is jargon in the title. Try "Choose the cutoff from training-side cost". |
| Bound savings with bootstraps | 68 | shipped: ok (`sensitivity.json` n_boot 2000, [−508, −353]) | none |
| Re-freeze the cutoff as prices move | 65 | shipped: ok (`sensitivity.json` 0.25 / 0.175 / 0.15) | none |
| Gate rollout on owner data | 78 | next | It depends on a feed the data owner has not provided (L344-345). Round 2 had it as `blocked`, which matches better. `next` is defensible only if requesting the feed is the next action. |

All titles are verb-first. All details are 90 characters or fewer. All four
`shipped` claims are backed by committed artifacts.

## 7. Consistency with gold template (7)

What matches gold:

- Bold lead claims.
- A diagram followed by a "Follow the … in three steps" list in the background.
- "We next…" transitions that are full sentences. Gold has "Next, we set…".
- One-line plain-terms cards.
- Backticked numbers in most sections.
- Four `shipped` roadmap cards and one `next` card with a "Gate:" detail.

Gaps:

- **L19** is still a verbless fragment ("Next, the cost-model diagram that sets the gates"), while every other transition now has a subject and a verb.
- **Objectives has no target-vs-result table.** Gold's objectives section has one (gold L36-44). This article's three success tests (L31-34) would fit that table naturally: one cost model and one holdout; the CI excludes zero; the cutoff is re-frozen at FN 3/5/8.
- **The gold sections open with motivation prose** (gold data section: "Indexing all of Wikipedia turns verification into…"). This article opens most sections by pointing at a figure.
- **The opener is an imperative claim, not gold's question.** That is acceptable.

## Round-2 finding status

| # | Round-2 finding | R3 status | Current line(s) / note |
|---|---|---|---|
| S1 | "cost-model diagram that sets the gates" | STILL PRESENT | L19 |
| S2 | "Three tests… need one real panel and one twin" | FIXED | L46-47 rewritten |
| S3 | "churn-profile figure that sets the judging rules" | STILL PRESENT | L81 |
| S4 | Headline numbers repeated many times | STILL PRESENT | L3, L17, L21, L180, L212, L240, L283, L352 + captions |
| S5 | Results duplicates Conclusions Limits | PARTLY FIXED | Results trimmed; raw-vs-served (L222-224 vs L346-348) and 21/4 columns (L227 vs L349) still repeat |
| E1 | Glossary opener | FIXED | — |
| E2 | Stacked "X, or Y," glosses | PARTLY FIXED | drift chain gone; L40, L61, L76, L186, L203 remain |
| E3 | Imperative figure-reading openers | PARTLY FIXED | Results fixed; L60, L88, L123, L126, L148, L190 remain |
| E4 | Terms defined twice | PARTLY FIXED | OOF now once (L133); calibration error L102-104 vs ECE L138-140 remain |
| L1 | "Accuracy, the share correct" | FIXED | — |
| L2 | Semicolon splice | FIXED | — |
| L3 | Broken line wrap | FIXED | L119-121 |
| L4 | F1-first "therefore" | FIXED | removed |
| L5 | "diagram… gives the ECE improvement" | STILL PRESENT | L245-247 (and now known to be factually wrong, C1) |
| L6 | Link row inside paragraph | FIXED | L253 |
| L7 | Over-indented fence | FIXED | L314 |
| D1 | AUC drop unexplained | FIXED | L279-281 (verified) |
| D2 | 80% base-learner carve-out | FIXED | L134-136, L322-323 |
| D3 | Grid granularity vs close OOF costs | PARTLY FIXED | spacing and 2,440/2,425 stated; flatness of the cost basin near 0.175 not addressed |
| D4 | ECE bin count | FIXED | L138, L330 |
| T1 | −90 [−159, −26] untraceable | FIXED | removed with disclosure L286-287 |
| T2 | Permutation ranking wrong | FIXED | L149-151, L389-390 |
| T3 | Senior/fiber panels | FIXED | L89-90 |
| T4 | "all three figures" | FIXED | L94 |
| T5 | Stale −485/−343 in diagrams | FIXED | `churnCycle.ts` L70, `auto/...-3.ts` L31 |
| T6 | CV cost 2,416 / 25-trial search | PARTLY FIXED | gone from article; still asserted by hero diagram `churnCycle.ts` L33 (C4) and README L47-48 |
| T7 | F1-first misattributed | FIXED | removed |
| T8 | "21 columns" overstates pipeline | FIXED | L227, L349 say 4 model features (correct; round-2 suggested 6, which was wrong) |
| T9 | FN=3 calibration gain omitted | FIXED | L145-147 |
| T10 | "between 3 and 8" | FIXED | L34 |
| T11 | "voucher" undefined | FIXED | removed |
| R1 | Card 2 detail mismatched | FIXED | L360 |
| R2 | "Price… by bootstraps" | FIXED | L362 |
| R3 | Vague details | FIXED | L363, L366 |
| R4 | Jargon in cards | PARTLY FIXED | "DQ" gone; "OOF" in L359 title, "CI" in L363 |
| R5 | No `next` card | FIXED | L367-369 |
| G1 | Verbless transition fragments | PARTLY FIXED | all but L19 rewritten |
| G2 | Opener differs from gold question | PARTLY FIXED | unchanged; acceptable |
| N1 (R2 new) | L15 "7,043 pinned customers" | FIXED | L15 says 5,634 |
| N2 (R2 new) | "after automatic quality checks" | FIXED | L212 |
| N3 (R2 new) | Unit inconsistency | PARTLY FIXED | prose in dollars; L26, captions L384/L388/L394, and `churnCycle.ts` L69 ("cost units") are not |
| N4 (R2 lang) | "bootstrap saving −508 to −353" | FIXED | "cost delta" |
| N5 (R2 lang) | "saves nothing" | FIXED | L26 "still costs 1,870" |

Totals across 43 tracked items: **29 FIXED, 10 PARTLY FIXED, 4 STILL PRESENT** (S1, S3, S4, L5).

## New errors introduced by Wave 8

1. **L241, L284.** −434 is labelled "mean bootstrap cost delta". It is the observed point delta (`evaluate.py` L240). Round 2's "bootstrap point" was correct.
2. **L10 against L132-133.** Wave 8 removed the 25-trial claim from the prose but not from the hero diagram (`churnCycle.ts` L33), so the two now contradict each other on screen. The diagram file was edited in this wave, for the CI only.
3. **L132-133.** A maintainer-facing audit sentence ("It has no valid trial count or search score, so this article makes no claim about them") now sits in the narrative.
4. **L26.** "`1,870`" lacks the `$` that the rewritten L8 and L17 introduce. This is minor unit drift.
5. **Source formatting.** L132, L134, L138, and L217 are unwrapped long lines from a hand-merge. This is cosmetic.

Pre-existing errors newly identified this round: C1, C2, C3, C5, C6 (diagram and figure descriptions that do not match the committed specs and figure JSON).

## Top 5 remaining fixes

1. **Make the pipeline-diagram references true (L245-247, L311-312, L346-348).** Either:
   - add raw and isotonic branches to `auto/05-ml-pipeline-churn-4.ts`, or
   - reword all three passages to describe what the diagram shows: one preprocessing DAG, numeric and categorical branches joining at a ColumnTransformer.

   Take the ECE and cost comparison from the table, not "the diagram". Also add `internet_service` to the diagram's categorical branch.
2. **Fix the measurement-chain diagram (`auto/05-ml-pipeline-churn-3.ts`) or the L190-200 text.** The diagram now shows threshold selection after "frozen holdout · score every candidate", which depicts the leak the article denies. Reorder it to: OOF predictions → 41-point grid → frozen 0.175 → holdout scored once → bootstrap. Retitle the watch items to match L200 and L206.
3. **Remove the 25-trial claim from the hero diagram (`churnCycle.ts` L33)** and from README L47-48, to match L132-133 and L306. In the same diagram, change "601 cost units" (L69) to "$601". Then delete the audit sentence at L132-133.
4. **Correct the bootstrap and fairness labels.**
   - L241 and L284: "mean bootstrap cost delta" → "observed cost delta".
   - L217: "Each bar shows recall" → "The recall bars show…" (the figure also plots precision, F1, and slice cost).
   - L225: acknowledge that the figure's cost panel exists. Its slice costs are raw-policy costs, not the served bill.
5. **Finish the leftover structure items.**
   - L19: make it a sentence and drop "sets the gates".
   - L81: drop "to set the judging rules".
   - Trim one of the three background headline copies (L3, L17, L21).
   - Either drop logistic-at-0.5 from L193-195 and L332-334 or persist its interval.
   - Change L26 "`1,870`" to "`$1,870`".

Next tier: thin the remaining "X, or Y," glosses (L40, L61, L76, L186, L203),
replace two or three imperative openers with claims, add an objectives
target-vs-result table to match gold, and reconsider `next` versus `blocked` on
the last roadmap card.

## Ready to publish?

**No.** Wave 8 did the hard part. Every number now traces to a committed
artifact, the two untraceable figures are gone, and the depth gaps are closed.
The article still tells readers what three diagrams show, and each time the
diagram shows something else:

- The pipeline diagram has no raw/isotonic branches (C1, C2).
- The measurement-chain diagram depicts holdout-side threshold selection, the leak the article rules out (C3).
- The hero diagram still claims a 25-trial search that the article disowns (C4).

For an article whose argument is holdout discipline and truthful lineage, these
have to be fixed before publishing. All of them are small edits: three diagram
specs plus about six prose lines.
