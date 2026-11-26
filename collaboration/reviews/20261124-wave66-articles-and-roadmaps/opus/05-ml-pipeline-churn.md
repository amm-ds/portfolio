# Review: 05-ml-pipeline-churn story.yaml (Wave 6.6)

Reviewer: Claude (Opus), read-only senior ML writer/reviewer pass
Target: `projects/05-ml-pipeline-churn/story.yaml` (422 lines)
Gold template: `projects/01-rag-agent/story.yaml`
Date: 2026-11-25

Note on the diff: `git diff -- projects/05-ml-pipeline-churn/story.yaml` is empty;
the working tree is clean. The Wave 6.6 edits are already committed in
`18adc59d` ("align projects 02-13 to 01 gold template"). This review uses
`git show 18adc59d -- projects/05-ml-pipeline-churn/story.yaml` as the round
diff. That round renamed "Business summary" to "In plain terms", added six
closing transitions, tightened two background paragraphs, and rewrote roadmap
titles from past tense to imperative.

Evidence checked: `reports/metrics.json`, `reports/sensitivity.json`,
`reports/dq_report.md`, `reports/figures/{eda_churn_profile,permutation_importance,fairness_slices,bootstrap_ci}.json`,
`data/{operating_policy,model_selection,model_meta,dataset_contract}.json`,
`params.yaml`, `README.md`, `DESIGN.md`, `src/churn_pipeline/{evaluate,hpo}.py`,
`data-registry/telco-churn.md`, the diagram specs in
`apps/showcase-web/src/diagrams/{churnCycle.ts,auto/05-ml-pipeline-churn-*.ts}`,
and a recomputation of the EDA numbers from `data/churn.parquet` and
`data/holdout.parquet`.

## Grades

| # | Dimension | Grade |
|---|---|---|
| 1 | Structure and article logic | 7 |
| 2 | Engagement and human-like narrative | 5 |
| 3 | Language quality | 5 |
| 4 | Technical detail depth | 8 |
| 5 | Truthfulness | 6 |
| 6 | Roadmap cards | 6 |
| 7 | Consistency with gold template | 7 |
| | **Overall** | **6.3 / 10** |

Lowest dimensions: engagement (5) and language (5).

## 1. Structure and article logic (7)

The section order works: priced list, cost objective, data lineage, EDA,
training and threshold, frozen evaluation, fairness limits, then tables. Each
section has a bold lead sentence and an "In plain terms" close. The frozen-policy
idea (select on training OOF, persist, then score the holdout once) is carried
consistently through background, objectives, training, evaluation, and protocol.

Problems:

- Several transitions do not describe what comes next.
  - L23 "Next, the cost-model diagram that sets the gates". The objectives
    diagram (`auto/05-ml-pipeline-churn-1.ts`) shows a cost model, a grid, an
    argmin, and two outputs. It sets no gates. "Gates" in this article means
    data-quality gates (L69) and rollout gates (L236). The word now covers three
    different things.
  - L53 "Three tests for success need one real panel and one twin". This is a
    non sequitur. The success tests do not need a synthetic twin. The twin is
    CI evidence only (L84-88).
  - L91 "the churn-profile figure that sets the judging rules". The figure shows
    churn by contract, charges, and tenure. The judging rules are listed in
    the text, not in the figure.
- Headline numbers repeat too often. "601 versus 1,035" appears at L3, L11-12,
  L163, L204, L255, L284, L322, and L389. "−508 to −353" appears six times. The
  Conclusions "Results summary" (L282-296) restates the training section almost
  line for line. The repeats make the second half feel like a loop.
- Results (L243-277) mixes two jobs. Its opening reads the fairness figure. Its
  bullet list is a generic limits list, and Conclusions "Limits" (L376-387)
  repeats it.

## 2. Engagement and human-like narrative (5)

The concrete material is good: vouchers, missed churners, a contact list, and a
bill. The narrative voice is not. The gold article opens with a question and
gives a short reason why the problem matters (gold L5-7). This article opens
with three glossary sentences in a row (L7-10).

Patterns that read as machine-written:

- Inline "X, or Y," glosses stacked in a row: "A grid, or list, of 41
  thresholds" (L47), "one 9,999 outlier, or extreme, charge" (L85-86), "the
  pipeline, or full processing sequence" (L95), "Rollout, or real release"
  (L229). L262-264 chains three of them in one sentence: "drift, meaning change
  over time, seasonality, meaning repeating time patterns, or causation,
  meaning ...".
- Repeated imperative figure-reading lines: "Compare the contract bars" (L101),
  "Start with the flat line" (L142), "Compare the logistic policies" (L145),
  "Read permutation importance from top to bottom" (L169), "Read the
  fairness-slices figure one customer group at a time" (L245), "Follow the
  measurement chain" (L214), "Follow both source branches" (L69). Every section
  instructs the reader. None of them tells a story.
- Terms are defined more than once. OOF is defined at L155-156 and again at
  L215-216. Calibration error is defined at L116-117 and ECE at L159-161. The
  repeats show that the sections were written in isolation.

## 3. Language quality (5)

- L18 "Accuracy, the share correct" is clipped to the point of awkwardness. The
  pre-round text ("the share of correct predictions") was better.
- L8-9 "a model, a learned rule estimating churn; serving uses it to choose
  contacts" uses a semicolon splice that the round introduced. It reads worse
  than the earlier two sentences.
- L138-140 has a broken line wrap: "Training and serving\n use this same\n
  pipeline". It is harmless in rendering, but it shows careless editing.
- L148-150 "An F1-first search chose a different model family. The figure's
  cost-based winner therefore depends on the objective, not accuracy alone."
  The "therefore" does not follow, and the business-cost figure does not show
  any F1 search.
- L289-291 "The pipeline diagram separates the raw and isotonic model paths.
  That comparison gives the ECE improvement". A diagram does not produce a
  metric.
- L296: the link row sits inside the paragraph with no blank line before it, so
  it renders as part of the paragraph.
- L353: the diagram fence is indented 12 spaces, 6 deeper than the block. The
  custom parser (`markdown.tsx` `FENCE_RE = /^\s*```/`) tolerates it, but in
  CommonMark it would be an indented code block. Project 08 L347 has the same
  issue.

## 4. Technical detail depth (8)

This is the article's strength. An expert reader gets the following:

- the priced confusion-matrix objective, with a faithful `evaluate.py` excerpt
  (checked against `src/churn_pipeline/evaluate.py` L32-53)
- three-fold OOF threshold freezing with persisted `operating_policy.json`
- isotonic calibration on a train-side 20% carve-out
- paired bootstrap against two comparators
- FN-cost sensitivity with re-frozen thresholds
- explicit separation of raw-model fairness from the served policy
- XGBoost hyperparameters

Gaps an expert will notice:

- The article does not explain why calibration lowers ROC-AUC (0.8387 to
  0.8317, L319-320). Isotonic step ties reduce ranking resolution, and a reader
  will ask about it.
- The article does not say that the calibrated model's fitted base learner sees
  only 80% of training rows. That is a real cost of the train-side carve-out.
- The 41-point grid has 0.025 steps. Whether 0.175 against 0.150 or 0.200 is a
  meaningful difference is unaddressed. The OOF training costs (2,440 raw,
  2,425 calibrated) are close.
- L117 mentions calibration error, but not the 10-bin ECE (`calibration_bins:
  10`).

## 5. Truthfulness (6)

The core headline numbers all trace to committed files:

| Claim | Source |
|---|---|
| 601 / 1,035 / −41.9% | `metrics.json` |
| −434 [−508, −353] | `sensitivity.json` fn5 |
| thresholds 0.175 / 0.225 / 0.450 | `operating_policy.json` |
| 691 / 655 / 644 | `metrics.json` |
| ECE 0.028 → 0.016 | `metrics.json` |
| FN 3/5/8 table | `sensitivity.json` |
| fairness recalls 0.834/0.829/0.898/0.808/0.918/0.250/0.000 | `fairness_slices.json` |
| 27 of 36 one-year misses, 9 of 9 two-year misses | consistent with slice costs 168 and 45 |
| hyperparameters | `params.yaml` |
| calibrated OOF cost 2,425 | `operating_policy.json` |
| 7,043 rows, sha256 | `dataset_contract.json` |
| 1,409 holdout rows, 374 churners | `holdout.parquet` |
| 26.5% churn | recomputed |
| 42.7% / 2.8% / 41.7% / 41.9% / $74 vs $61 / 18 vs 38 months | recomputed from `churn.parquet` |
| 21 columns | `data-registry/telco-churn.md` |

The −90 [−159, −26] figure traces to README L96 only. No JSON file in the
project holds it. It is listed as untraceable item 1 below.

Contradicted or untraceable claims:

1. **L325-326 (also DESIGN L169)**: "−90 with 95% CI [−159, −26]". This number
   appears only in README/DESIGN prose. `metrics.json` and `sensitivity.json`
   do not contain it. It is an untraceable number.
2. **L170-172 and caption L420**: "Contract, tenure, and charges rank highest"
   and "Contract, tenure, and monthly charges carry the main signal". This is
   contradicted by `permutation_importance.json`: tenure 0.213, contract 0.174,
   internet_service 0.088, monthly_charges 0.033. Internet service outranks
   charges by about 2.7×. README L117-118 carries the same error.
3. **L102-103**: "The other panels show 41.7% churn for senior citizens and
   41.9% for fiber-optic users." The numbers are correct when recomputed, but
   the churn-profile figure has only three panels: contract, monthly charges,
   and tenure. No figure panel shows senior or fiber churn. The text tells the
   reader to look for panels that do not exist.
4. **L107**: "Use all three figures under the same judging rules". The EDA
   section has two figures (`eda_churn_profile`, `precision_recall_curve`,
   L130). This is a miscount.
5. **L20 and L222 against diagram assets**: the text says the interval is −508
   to −353. The decision diagram's bill box (`churnCycle.ts` L70) and the
   evaluation diagram (`auto/05-ml-pipeline-churn-3.ts` L31) both print "CI
   −485 to −343". Those are stale numbers from an earlier run (DESIGN L145).
   L20 tells the reader the diagram's interval sits right under a box that
   shows a different one. Readers will see the contradiction.
6. **L345**: "CV cost 2,416". This traces only to README L79 prose.
   `data/model_selection.json` records `best_score: NaN`, `n_trials: 0`. The
   committed selection artifact does not carry the search result. The number is
   untraceable to any metrics file, and the 25-trial search is not evidenced by
   a committed artifact.
7. **L148**: "An F1-first search chose a different model family". This traces
   only to a DESIGN L84-87 Wave 7 log entry about the synthetic-era run (an
   F1-selected HistGB). It is presented as part of the current telco story.
   This is misattributed context.
8. **L268 and L386**: "It covers one operator and 21 columns" and "The pipeline
   covers one operator and 21 columns". The raw source has 21 columns, but the
   pipeline consumes 6 features plus the target (`churn.parquet` shape
   7043×7). SERVING.md requires 4. Saying the pipeline "covers 21 columns"
   overstates the feature set and hides a real limit.
9. **L167-168**: "Calibration helps at five, 644 → 601, and at eight, 725 →
   718." This is selectively true. `sensitivity.json` fn3 also shows a gain
   (518 → 514). Listing only five and eight suggests calibration does not help
   at three.
10. **L41**: "Re-run the choice when a missed churner costs between 3 and 8."
    Only three points (3, 5, 8) were tested. "Between" implies a continuous
    sweep.
11. **L18, L305**: "one retention voucher". No project file defines a voucher.
    The project only says "$1 per contact" (README L93). This is minor framing,
    but it is not evidence.

Count: 2 untraceable numbers (−90 [−159, −26]; CV cost 2,416), plus 4 claims
contradicted by committed artifacts (items 2-5), plus 5 misleading or
overstated claims (items 7-11).

## 6. Roadmap cards (6)

| Title | Verb-first | Detail length | Status |
|---|---|---|---|
| Pin one reproducible panel and twin | yes | 70 | shipped, sensible |
| Choose the cutoff from OOF cost | yes | 67 | shipped; the detail describes HPO and calibration, not the cutoff, so it does not match the title |
| Price the served policy by bootstraps | yes | 76 | shipped; wrong verb, since a bootstrap bounds the saving and does not price it |
| Re-freeze the cutoff as prices move | yes | 71 | shipped |
| Gate rollout on owner data | yes | 61 | blocked, sensible |

All details are 90 characters or fewer. Issues:

- This round made two details vaguer. "2,000 paired resamples ... the 95% CI
  excludes zero" became "Paired bootstrap resamples ... the interval excludes
  zero". "Threshold moves 0.250 to 0.150 as missed-churner price goes 3 to 8"
  became "The cutoff tracks the missed-churner price across the sensitivity
  grid". The old details were concrete and within budget, so this is a
  regression.
- The details use jargon in public cards: "DQ gates", "OOF", "CI twin".
- The gold template ends with a `next` card that names its gate (gold L279-281).
  This roadmap has no forward-looking `next` item. The only open card is
  blocked.

## 7. Consistency with gold template (7)

All seven sections end with "**In plain terms:**". Six closing transitions use
the `([Section →](#sec-x))` link format, which matches gold. Differences:

- Gold transitions are full sentences with a verb ("Next, we set the rules each
  answer must clear"). This article uses verbless fragments: "Next, the
  cost-model diagram that sets the gates" (L23), and "X; next, the Y (link)"
  throughout (L53, L90, L123, L199, L235, L271). The pattern is rigid.
- Gold opens with a question hook. This article opens with a definition.
- Gold places transitions before tables and figures that they introduce. Here
  they are fine as section closers.

## Top 5 fixes (ordered by severity)

1. **Stale CI in diagrams contradicts the text.** The text at
   `story.yaml` L20 and L222 says −508 to −353. `apps/showcase-web/src/diagrams/churnCycle.ts`
   L70 and `auto/05-ml-pipeline-churn-3.ts` L31 both say "CI −485 to −343".
   Regenerate or edit both diagram labels to −508 to −353 (point −434). This is
   outside story.yaml, but the article points readers straight at the box.
2. **Wrong permutation-importance ranking.** `story.yaml` L170-172 says
   "Contract, tenure, and charges rank highest". Caption L420 says "Contract,
   tenure, and monthly charges carry the main signal". Change both to "Tenure
   and contract dominate; internet service is third; monthly charges add
   little" (values 0.213 / 0.174 / 0.088 / 0.033). Fix README L117-118 too.
3. **EDA text points at panels and figures that do not exist.** L102-103
   reads "The other panels show 41.7% churn for senior citizens and 41.9% for
   fiber-optic users". Reword as text-only facts ("Outside the figure, seniors
   churn at 41.7% and fiber users at 41.9%"), or add the panels. L107 says
   "Use all three figures"; change it to "both figures".
4. **The "21 columns" scope overstates the model.** L268 and L386 say "covers
   one operator and 21 columns". State that the source has 21 columns and the
   pipeline uses 6 features (tenure, charges, contract, internet service,
   gender, senior). Make the limit say so: "transfer and richer features are
   unmeasured".
5. **Untraceable or misattributed claims and selective calibration framing.**
   Delete L148-150 "An F1-first search chose a different model family. The
   figure's cost-based winner therefore depends on the objective" (old
   synthetic-era result, non sequitur). For L345 "CV cost 2,416", either
   persist the search result in `data/model_selection.json` (currently
   `n_trials: 0`, `best_score: NaN`) or drop the number. For L325-326 "−90
   with 95% CI [−159, −26]", persist that bootstrap in `metrics.json`. At
   L167-168, add FN=3 ("518 → 514") so calibration's gain is reported at all
   three prices.

Secondary (not in top 5):

- Restore concrete roadmap details (L402, L405).
- Rewrite the transition fragments at L23 and L53 as sentences, and stop using
  "gates" for the objectives diagram.
- Thin the gloss chains at L262-264 and L47.
- Cut the Conclusions "Results summary" repetition at L282-296.
