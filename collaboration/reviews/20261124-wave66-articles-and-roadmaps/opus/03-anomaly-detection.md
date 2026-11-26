# Review: 03-anomaly-detection story.yaml (Wave 6.6)

- Reviewer: Claude (Opus), senior ML writer/reviewer, read-only
- Target: `projects/03-anomaly-detection/story.yaml` (working tree == HEAD `18adc59d`; the Wave 6.6 edits are already committed, so `git diff` is empty and the round's diff was read with `git show HEAD -- projects/03-anomaly-detection/story.yaml`)
- Gold template: `projects/01-rag-agent/story.yaml`
- Evidence checked: `reports/nab_metrics.json`, `nab_sweep.json`, `nab_tune.json`, `nab_refinement.json`, `metrics.json`, `champion_selection.json`, `detect.json`, `residual_probe.json`, `nsl_probe.json`, `reports/figures/*.json` (titles/annotations), `params.yaml`, `README.md`, `DESIGN.md`, `apps/showcase-web/src/demos/`

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
| | **Overall** | **6** |

Lowest dimensions: Engagement (5) and Language (5). Language is the binding one, because the Wave 6.6 compression made several sentences telegraphic.

## 1. Structure and article logic: 7

What works: every section now ends with a `next, … ([X →](#sec-x))` transition in the 01 format, and each section opens with a bold claim. The section order (problem, controls, sources, EDA, sweep, evaluation, panels, tables) is sound.

Problems:
- **The subject keeps changing.** The article moves between three "champions" without saying so: the NAB IsolationForest headline (L6-10, L238 "champion's range-PR area of 0.804", which is the IF value from `nab_metrics.json`), the rank-average ensemble (L12 "The champion rank-average ensemble"), and the synthetic `ocsvm_tuned` champion (L207, `champion_selection.json`). The `nab_timelines` figure title also says "champion alerts" for IF alerts. An expert reader cannot tell which detector a number belongs to without checking the source.
- **Evaluation, Results, and Conclusions repeat the same argument.** The 66 → 35 like-for-like comparison appears at L26, L186, L219, L250, L277, L303, L341, L352 and L503. The 2,546-alert calibration failure appears at L267, L314, and L366. The 14/17 fusion failure appears at L269, L316, L369, and in the table. Results (L307-317) restates Evaluation (L264-270) almost word for word.
- **The background no longer sets up the denominator.** The diff removed "Three of twelve series have train-only labels", but L8 still refers to "the three train-only ones" before they are introduced (they first appear at L85).
- **Results breaks the like-for-like rule from Evaluation.** L278-279 warns "Do not compare the ensemble's 35 directly with the other cell's 1,609 raw alerts". L351-354 then compares the ensemble rolling cell (35 pages, recall 0.604) with headline IF rolling+residual (80 pages, recall 0.562) and calls the recall "higher".

## 2. Engagement and human-like narrative: 5

The opening question (L6-7) is good. After it, the text reads as a run of measurements with little narrative. Nearly every paragraph stacks three to six decimals. The reader is never told about one concrete on-call moment, for example "on nyc_taxi, the 24 h cap suppressed the page that would have caught the Nov-2014 window". Finding 3 (L189-202) packs 12 numbers into 14 lines. The EDA section (L114-129) is the most readable part, because it tells the reader where to look.

## 3. Language quality: 5

- Telegraphic fragments from the compression pass: L161-162 "`telemetry_flags` separately tracks synthetic CPU+latency spikes; not NAB evidence." and L12 "The champion rank-average ensemble on rolling features leaves 35 budgeted pages, range-F1 0.533, range precision 0.553".
- L8 is an unwrapped 98-character line, and its bold lead sentence runs straight into a dense clause about the recall denominator.
- L20-21 "cuts 1,609 raw alerts to 80 on the rolling+residual cell without claiming transfer". The diff dropped "IsolationForest", so the sentence now seems to describe the ensemble from the paragraph above. The ensemble rolling+residual cell is 1,003 → 45, not 1,609 → 80.
- L455 "Range precision is measured over alerts outside windows". This copies the artifact's `event_rule` string, but read as a definition it is backwards: precision is the share of alerts *inside* windows.
- Repetition: "1,609" appears 11 times, and the halving claim ("halves"/"66 to 35"/"66 → 35") appears 7 times.
- Jargon is mostly defined (ROC-AUC, IQR, OCSVM, k-NN). "face budget" / "2% face value" (L267, L314, L367) is never defined.

## 4. Technical detail depth: 8

This is the strongest dimension. Readers get past-only splits, a frozen train-anchored quantile, an explicit range-recall denominator, a 16-seed no-skill band, a series-level bootstrap CI, the adoption-gate margin, the neighbour-mean argument for OCSVM's fragile peak, and the rank-fusion code. Gaps an expert would notice:
- The text never says that the range-PR "precision at 2%" (0.527, macro over series, L241/L405) and the ablation's `precision@budget` (0.512, L430) are different estimators of the same idea.
- The IF "transfer" claim (L193-195) omits the recall cost. Budgeted recall falls 0.604 → 0.500 and 0.562 → 0.479 (`nab_tune.json → vs_default_sweep_budgeted`). That matters for the article's own "on-call capacity versus recall" framing.
- The k-NN statistic (L118-120) does not support "tight cluster" as written; see Truthfulness.

## 5. Truthfulness: 6

Most figures trace exactly. Verified examples: 16/17, 1,609, 0.527, 0.157, 0.729 → 0.562, 80, the five sweep rows, 0.515-0.577 / 0.515-0.574, 0.688-0.750, 1,003-3,586, recall cost 0.125-0.250, the per-group table, 0.804 / 0.228 [0.081, 0.401], 0.680/0.632/0.527/0.234, 0.944, 0.082 [0.063, 0.105], 0.885 [0.806, 0.962], bootstrap [0.230, 0.811], tune gains +0.081/+0.042/+0.056/+0.010, neighbour mean 0.168 vs 0.206, OCSVM test deltas −0.043/+0.033, 66 → 33 / 80 → 46, 0.433/0.382, ablation table, synthetic 0.9158/0.1239/0.9171/0.1355/0.5091/0.0194, residual 0.9999/0.9960, NSL-KDD 0.8877/0.8979/56.9%, 2,791 rows / 2.15%, 5,983 rows / 1.89%, gamma 99% / 0.0131 (DESIGN 0.013) / 0.126, 897 alerts, 17/120 flags, 31/120 chunks (DESIGN L203, README L152), detect.json 120/18/102 and 113/17/96, 20,000 rows / 2%, 30 TPE trials, 2.4× / 0.049 (DESIGN L51, L121), Lyu 2026 (README L71).

Contradicted or untraceable claims:

| Line | Claim | Finding |
|---|---|---|
| L302-303 | "Pages still miss incidents about half the time, but that miss rate roughly halves" | **Contradicted.** Range precision 0.347 → 0.553 means the share of pages outside incidents falls from 0.653 to 0.447, a reduction of about 32%, not half. The quantity is also false alarms, not "miss[ed] incidents"; recall is unchanged at 0.604. |
| L376 | "The interval spans the no-skill band's upper edge" | **Contradicted.** The CI [0.230, 0.811] lies wholly above the matching no-skill precision band [0.063, 0.105] (`nab_metrics.json → no_skill.pa_k_precision`). It only overlaps the range-PR *area* band [0.081, 0.401], which is a different metric. |
| L86-87 vs L8, L456 | Three train-only series "leave the evaluation rather than count as misses" | **Internally contradicted.** L8 and L456 (and `aggregation` in the artifacts) say range recall counts those three series as zero. |
| L248, L356 | "twenty- to thirty-fold fewer pages" | **Contradicted range.** The measured raw/budgeted ratios are 20.1-33.1× (ensemble+rolling 1,157/35 = 33.1). L183 correctly says "thirty-three-fold". |
| L542 (caption) | "Only IsolationForest's (0.5%, 24 h) adoption clears the 0.05 margin" | **Contradicted.** OCSVM also clears it (+0.056, `adopted: true` in `nab_tune.json`); it fails on test. Accurate wording: "Only IsolationForest's adoption both clears the margin and transfers." |
| L200 | "sub-0.1 gains are noise" | **Self-undermining.** The adoption gate is +0.05 (L466), and the endorsed IF adoption rests on a +0.081 gain. Either IF's adoption is noise too, or the threshold is wrong. |
| L290 | "The `nyc_taxi` panel keeps the hardest series visible" | **Unsupported.** It is the only series that misses a window, but ambient_temperature is worse on raw range-F1 (0.005), pointwise PR-AUC (0.233 vs nyc_taxi's 0.462), and range-PR area (0.026 vs 0.635). Write "the only series with a missed window". |
| L519 (roadmap) | "The showcase demo replays committed alerts; the threshold never moves." | **Untraceable.** `apps/showcase-web/src/demos/` has only `churn-sandbox`, `forecast-workbench`, and `workbench`, with no anomaly demo, and no showcase-api route serves 03 alerts. The only "detect" artifact (`detect.json`) is synthetic `isolation_forest_tuned`, not the ensemble the card calls the champion. |
| L522 (roadmap) | "TSB-AD VUS-PR is the modern reference score for this task." | **Untraceable in-repo** (external claim, no citation in README/DESIGN). Plausible (TSB-AD, NeurIPS 2024 D&B, recommends VUS-PR), but it needs a source link or softer wording. |
| L373 vs L430 | "headline 2%-budget precision is 0.527" vs `precision@budget` 0.512 | Both trace (`pa_k_2` macro range precision vs `precision_at_budget`), but the article gives two different numbers for the same label and does not explain the difference. |
| L534 vs L535 | Tuned OCSVM "best validation PR-AUC 0.126" vs "validation PR-AUC 0.151" | Both trace (HPO trial history vs `champion_selection.json`), but the two "validation" values are not reconciled. |
| L118-120 | "The tight cluster explains a later failure: its mean distance to the 20 nearest neighbours (k-NN) is ≈20.5, versus ≈9.5 for normal rows" | Numbers trace (`residual_probe.json`), but the inference does not follow: a *larger* k-distance signals sparser neighbourhoods, which is the opposite of "tight". DESIGN.md's argument needs within-blob spacing (uniform density → LOF ≈ 1), and the article omits it. |

Count: **0 untraceable numbers.** Every decimal resolves to a committed file. There are **4 contradicted numeric claims** (L303, L376, L248/L356, L542), **1 internal contradiction** (L86 vs L8/L456), and **2 untraceable non-numeric claims** (L519, L522).

## 6. Roadmap cards: 6

| Card | Title verb-first | Detail ≤90 | Status sensible | Note |
|---|---|---|---|---|
| Lock the event-aware evaluation contract | yes | 62 | yes | Good. |
| Halve paged load with rank averaging | yes | 48 | yes | The detail repeats the title and loses the numbers the old detail had ("66 to 35 pages at recall 0.604; range-F1 0.533"). Regression. |
| Publish the detector-challenge negative result | yes | 70 | yes | "No fusion clears the precision gate" is inaccurate: the fusions pass the precision gate and fail **coverage** (14/17, 15/17). Calibration fails precision. |
| Ship the champion behind frozen thresholds | yes | 72 | **no** | No anomaly demo exists (see L519). It should be removed or set to `next`. |
| Re-run the headline on TSB-AD VUS-PR | yes | 59 | yes | The detail is a claim, not an exit gate. The 01 gold card uses "Gate: …". |

## 7. Consistency with gold template: 7

- "In plain terms" cards are present in all 8 sections, and transitions use the 01 `next, … ([X →](#sec-x))` pattern. This part is good.
- Gold plain-terms cards are one sentence with one concrete number. Several here are 2-3 sentences (L275-279 has three, including a caveat), and L504-505 ends with a filler claim: "Every reported result is reproducible."
- Gold transitions name the figure or table the reader is about to see. Here L23-24 and L214-215 name the next idea but no artifact.
- Conclusions has no forward transition. That is acceptable, and the gold does the same.

## Top 5 fixes (by severity)

1. **`story.yaml` L302-303: fix a false quantitative claim.** Replace "Pages still miss incidents about half the time, but that miss rate roughly halves" with an accurate figure, e.g. "About 45% of ensemble pages still fall outside incidents, down from 65% for IsolationForest, while pages fall 66 → 35 at equal recall."
2. **`story.yaml` L376: fix the contradicted CI claim.** "The interval spans the no-skill band's upper edge" is false against the precision no-skill band [0.063, 0.105]. Say the interval sits above the no-skill precision band but is wide (0.23-0.81) across nine series, so it supports a budget dial, not unattended paging.
3. **`story.yaml` L519 (roadmap card 4): remove or downgrade an unsupported shipped claim.** "The showcase demo replays committed alerts" has no backing artifact in `apps/showcase-web/src/demos/`. Set the status to `next` with a gate, or delete the card. Also fix card 3's "No fusion clears the precision gate" (L516) to "No candidate clears the coverage-and-precision gate".
4. **`story.yaml` L86-87 vs L8/L456: resolve the denominator contradiction, and restore the setup the diff removed.** Change "they leave the evaluation rather than count as misses" to "they leave windows-touched but count as zero in range recall". Reintroduce "Three of twelve series have train-only labels" before L8's "the three train-only ones".
5. **`story.yaml` L12, L238, L20-21, L351-354: disambiguate "champion" and stop cross-cell comparisons.** Name the detector every time: "IsolationForest's range-PR area of 0.804" at L238, and "on the IsolationForest rolling+residual cell" at L21. Rewrite L351-354 to compare like-for-like (ensemble 35 vs IF 66 on rolling, both at recall 0.604) instead of 35 vs 80 with "Recall is higher". Also fix "twenty- to thirty-fold" at L248/L356 to "twenty- to thirty-three-fold" and the L542 caption's "Only IsolationForest's … adoption clears the 0.05 margin".
