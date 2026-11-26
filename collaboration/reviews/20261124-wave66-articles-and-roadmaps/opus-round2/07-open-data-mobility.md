# Round-2 review: 07-open-data-mobility story.yaml

Reviewer: Claude (Opus). This is a read-only second-round pass by a senior ML writer and reviewer.
Target: `projects/07-open-data-mobility/story.yaml` at HEAD (last touched in `e69bba84`).
Gold template: `projects/01-rag-agent/story.yaml`.
Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/07-open-data-mobility.md`, written against `18adc59d`.

All line numbers below refer to the current HEAD file.

## What changed since round 1

`git diff 18adc59d e69bba84` shows 459 insertions and 491 deletions. Most of that churn is the YAML
being reflowed from `>-` blocks into single-quoted and plain scalars, plus inline code backticks.
The changes that matter:

- **Background (L39–54)** was rewritten in the gold shape: a bold headline, a pipeline diagram, a
  three-bullet "Follow the pipeline" list, and a link to the next section.
- **All eight "In plain terms" cards** now state an outcome instead of describing a figure.
- **The rest of the body is unchanged word for word.** That covers Objectives, Data, EDA,
  Training, Evaluation, Results, Conclusions, and the roadmap.

As a result, none of round 1's truthfulness findings was addressed.

Evidence I re-checked myself for this round:

- `reports/metrics.json`
- `reports/figures/{borough_mae, gbm_feature_importance, p90_calibration, green_transfer,
  hour_borough_heatmap, weather_elasticity, conformal_coverage, zone_demand_map, ...}.json`.
  Binary arrays were decoded, and the heatmap peaks were recomputed.
- `params.yaml`, `README.md`, `DESIGN.md`, `MODEL_CARD.md`, and `src/mobility/serving.py`

Two files are new to the evidence set or still missing from it:

- `reports/figures/green_transfer.json` is now committed.
- `reports/drift/*.json` is still not tracked (`git ls-files` shows no drift reports).

## Grades

| # | Dimension | R1 | R2 |
|---|---|---:|---:|
| 1 | Structure and article logic | 7 | 7 |
| 2 | Engagement and human-like narrative | 5 | 5 |
| 3 | Language quality | 5 | 5 |
| 4 | Technical depth | 8 | 8 |
| 5 | Truthfulness | 6 | 5 |
| 6 | Roadmap cards | 6 | 6 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | **6** | **6 / 10** |

**Lowest dimension: Truthfulness (5).** Engagement and Language are also at 5, but Truthfulness is
the one that blocks publication. Every contradicted claim from round 1 is still present. The new
plain-terms cards also add one wrong claim: they say 90.8% coverage holds "in busy zones".

---

## 1. Structure and article logic: 7

What improved:

- The Background now matches the gold opening: headline, diagram, three steps, and a link onward.
  The three bullets (L48–50) work well. Each one is a single stage with one number.

What is still wrong:

- **Templated transitions (unchanged).** These four lines share one frame and never name the
  chart they refer to:
  - L91 "The bars set the contract"
  - L154 "The figures frame the candidate comparison"
  - L259 "The figures qualify the band"
  - L285 "The figures bound the claims"
- **Ordering (unchanged).** The hour-borough heatmap (L267–271) still comes in Results. The reader
  sees borough error (L237–241) before borough demand scale.
- **Conclusions is still an inlined evaluation report (L293–446).** It repeats the serving rule,
  the no-borough figure, and the default-vs-tuned remark that Training and Evaluation already
  covered.
- **The Objectives headline (L59–60) is not a bolded question or imperative.** Gold uses one, for
  example "Set four targets before any tuning begins."

## 2. Engagement and human-like narrative: 5

What improved:

- The opening is tighter. One "We" appears (L133).
- The new plain-terms cards read like a person talking. One example is "Beat a dispatcher's
  simple 'same hour yesterday' rule by at least 20%" (L94).

What is still wrong:

- **Glossary chains remain** in the unchanged body:
  - L66 "A baseline is a simple reference method that the model must beat."
  - L68–71 "RAM is the computer's working memory, and GB means gigabytes. … meaning rented remote
    computers"
  - L102 "TLC is the New York City Taxi and Limousine Commission."
  - L107–108 a full expansion of the NOAA GHCN name
  - L177 "Tuning means searching over model settings."
  - L184–185 "a neural network, which learns patterns through layered numerical transformations"
  - L325 "Weights are the model's learned numerical parameters."
  - L402–403 "This contract is the fixed three-file bundle format used for serving."
  - L426 "Lazy processing delays work until results are needed."

  " means " still occurs 10 times.
- **The voice is still impersonal.** Openers like "The diagram…" and "The figures…" dominate.
  Gold 01 uses "we" to carry the narrative ("we locked down clear rules").
- **There is still no tension.** Two results could carry the story, but both are flattened:
  - Persistence beats every GBM in three sparse groups.
  - 2025-01 band coverage falls to 87.4%.

## 3. Language quality: 5

**Repetition at HEAD.** These counts come from `grep -o` and are effectively unchanged:

| Term | Count |
|---|---:|
| "84.7" | 10 |
| "90.8" | 8 |
| "28.3" | 6 |
| "4.676" | 6 |
| "no-borough" | 14 |
| "persistence" | 11 |
| "xGB" | 10 |
| "flat within noise" | 3 (L178–179, L308, L353) |

**Filler and awkward phrasing, all still present:**

- L166 "— the headline comparison is against persistence only" adds nothing.
- L352 "xGB improves relative test `MAE` by −4.1%" reads as a negative improvement.
- L254–255 "That +0.091-pickup width cost accompanies the coverage gain." repeats the numbers in
  the sentence before it.

**Mixed precision and format, now worse:**

- L3 short_version says "91% coverage". Everywhere else says 90.8%.
- L308 now writes coverage as a fraction (`0.9079`). Every other place uses a percentage.
- L41 and L50 use "28%", while the body uses "28.3%".

**Jargon:**

- "xGB" (×10) is still a nonstandard abbreviation for XGBoost.
- New "safety band" wording blurs what the band is:
  - L94 "honest 90% peak-demand safety band" misdescribes a p90 conditional quantile. It is not a
    peak-demand band.
  - L54, L262, L288, L451 use "safety band" in the same loose way.

## 4. Technical depth: 8

The strengths are unchanged:

- Embargoed expanding validation
- A single-shot holdout
- The real serving-rule code
- MASE with its ≈6.13 scale
- Predeclared paired bootstrap with day blocks and zone clusters
- Split conformal with its width cost
- The green transfer vs retrain contrast
- The RAM budget

All of round 1's expert-visible gaps remain:

- **Conformal offsets come from test data (L251, L421).** They are fit on the first half of the
  test window. L84 still says "Nothing learned on test data flows back into selection", and
  Limits never discloses this. The article also never says whether the served `p90` uses the raw
  quantile or the conformal-adjusted band.
- **Two drift months replay the test window.** 2024-11 and 2024-12 fall inside the Q4 test
  window. DESIGN L184–185 itself says they "verify wiring, not unseen drift". Key concept L35
  still says the check scores the model "on new data".
- **The 2025-01 coverage shortfall is not flagged (L392).** Coverage of 87.4% is reported as
  "In-window" with no under-cover flag. DESIGN L156 calls it "slight under-cover".
- **The decision that matters has no interval.** There is no CI for xGB vs `gbm_tuned`.
- **The exact-numbers table (L341–347) omits two runs** that the text relies on:
  - `gbm_lgbm_tuned` (4.582). The text cites its validation MAE and CI.
  - `temporal_net` (5.510 MAE, 54.5% MAPE). This untuned run is the overall MAPE winner.

## 5. Truthfulness: 5

### Contradicted by committed evidence

| Line(s) | Claim | Evidence | R1 status |
|---|---|---|---|
| L16, L240–241, L443 | "persistence still edges the default GBM in the Bronx" / "The Bronx is the one place where persistence still edges the default GBM" | `borough_mae.json`, naive vs `gbm_mean`: Bronx 0.483 vs 0.519, **EWR 0.147 vs 0.279**, **Staten Island 0.022 vs 0.196**. Persistence beats every GBM arm in all three groups. | STILL PRESENT |
| L328–330 | "Last week's hour matters most: lag_168 (`0.80`) tops lag_24 (`0.64`)" | `gbm_feature_importance.json` subtitle reads "dominant driver: lag_1". Decoded values: lag_1 3.311 > lag_168 2.576 > lag_24 2.477. README L96–97 agrees, and so does the article's own L371–372. | STILL PRESENT |
| L367 | "Unknown `93.8%`" | `p90_calibration.json`: 0.93747, labelled "93.7%". | STILL PRESENT |
| L391 | "ΔMAE versus naive `+34.6%`" | L336–337 defines ΔMAE as the change vs lag-24, where negative is better. README L149 calls it an "improvement". Under the article's own convention, the sign should be −34.6%. | STILL PRESENT |
| L173–174 | "Selection uses the best embargoed validation score among candidates that beat the baseline" | `serving.py`, quoted at L203–218, gates only on the HPO result plus the mean/p90 artifacts. It has no baseline check. | STILL PRESENT |
| L288, L451 (also L54, L262) | "covers 90.8% of actual demand **in busy zones**" / "keeps 90.8% safety-band coverage **in busy zones**" / "holds across busy zones" | 90.8% is the **city-wide overall** figure (`p90_calibration.json` OVERALL 0.9079). The busy-zone stratum is "dense" in `metrics.json` `conformal.before`: 89.6% before adjustment and 90.3% after. Brooklyn (88.6%) and Queens (89.6%) are below target. | **NEW** |
| L397 | Yellow-trained GBM wins "`MAPE` (`−19%`)" | README L109–110: yellow `gbm_tuned` 66.7% vs naive 81.8% is −18.5%, which rounds to −18%. README's "−19%" (L115) belongs to the **retrained** model, so the figure has been misattributed. | partly noted in R1 |

### Untraceable (no committed source)

| Line(s) | Claim | Count |
|---|---|---:|
| L373–375 | "A second summary ranks lag_168 at 0.80, lag_24 at 0.64, lag_1 at 0.55, and hour at 0.32" | 4 |
| L67 | "within about 2 percentage points of target". Not in README, DESIGN, or MODEL_CARD. | 1 |
| L386–389 | 2024-11 MAPE 65.45%, coverage 90.6%, 152,110 zone-hours. 2024-12 MAPE 65.59%, coverage 91.2%, 152,375 zone-hours. Only in untracked `reports/drift/*.json`; README shows "—" for coverage. | 6 |
| L398 | "`337,080` zone-hours". DESIGN L180 gives only "337k", and the committed `green_transfer.json` figure has no row count. | 1 |
| **Total** | | **12** |

**Precision beyond the source.** The values below agree with README and DESIGN at their published
precision, but the extra digits appear only in untracked drift JSON:

- 5.0592 / +8.19%
- 5.0458 / +7.90%
- 4.4420 / −5.01%
- 59.60%

Round to the published precision: 5.059, 5.046, 4.442, 59.6%, +8.2%, +7.9%, −5.0%.

### Docs-only (traceable to committed docs)

These are acceptable:

- 41.2M trips
- About 1.5 GB download
- ≈2 GB peak RAM
- 2,327,760 grid rows
- 30 and 10 trials
- MASE scale ≈6.13
- Green 197,160 / 534,240 zone-hours, RMSE 0.688 vs 1.100, MAPE 66.4% vs 81.8%
- 2025-01: 4.442, 59.6%, 87.4%

Three values come from `params.yaml`: validation MAEs 3.165204 / 3.173486 / 3.18172.

### Verified against committed reports

Run ladder, from `metrics.json`:

- The full table
- −28.3% and −31.2%
- −0.2% default vs tuned
- 4.05 → −4.1% for xGB vs `gbm_tuned`

Paired intervals:

- Both CI rows
- 2,000 resamples, seed 42, 265 zones, 7-day blocks

Conformal:

- 94.3 / 88.2 / 89.6 → 94.3 / 89.9 / 90.3
- Overall 90.7 → 91.5
- Height 7.032 → 7.124
- Offsets +0.09 / +0.18

p90 calibration:

- 90.8% overall
- Every borough except Unknown

Figures:

- Hour-borough heatmap, recomputed: Manhattan peak 103.67 at hour 18, Bronx max 0.732
- Busiest zone 213.9
- Weather ratios: 0.895 / 0.919 / 0.928 / 0.965 / 1.030 / 1.080
- Green MAE 0.296 / 0.212 / 0.1805
- Permutation importance 3.31 / 2.58 / 2.48 / 1.12

Minor:

- L25 and L281 group "N/A, Queens, and Staten Island at 0.89–0.93×". They omit Unknown (0.90),
  which is also in that range.
- L270 says the scale "spans two orders of magnitude". Staten Island's max is 0.017, so the real
  span is closer to four.

## 6. Roadmap cards: 6

The roadmap is unchanged since round 1.

What passes:

- Every title is verb-first.
- Every detail is ≤90 characters. The longest is L469 at 75.
- Status is plausible: 4 shipped, 1 next.
- Each shipped claim checks out against the repo:
  - Replay: the `dvc.yaml` pipeline exists.
  - Serving rule: `serving.py`.
  - Band: `conformal.py` and `p90_calibration.json`.
  - Per-service retrain: `reports/models/serving/green/`, `services.json`.
  - Drift: `drift.py` and `dvc.lock`.

What is still wrong:

- **Compound titles:** L462 "Calibrate the band; flag no-borough zones" and L465 "Retrain per
  service; keep drift in-window". Gold uses single-action titles.
- **Details carry no evidence:**
  - L460 "The test leader tested better; the holdout has no vote." repeats its title.
  - L463 "Coverage lands on target" is vague.

  Gold details carry one concrete committed fact. A traceable fix for L460: "XGBoost tested
  4.1% lower; validation still picks `gbm_tuned`" (`metrics.json` 4.05).
- **L457 does not match its title.** The detail describes the panel, not the one-command replay.
- **L466 overclaims.** "drift months stay in-window" is true for MAE only. 2025-01 coverage is
  87.4%.
- **L469 skips the gold "Gate:" phrasing** for its next-card prerequisite.

## 7. Consistency with gold template: 7

Now aligned with gold:

- Background structure
- One-sentence outcome plain-terms cards in all 8 sections
- The transition link format

Still diverging:

- Transitions say "the figures" instead of naming chart IDs. Gold names them, for example
  `retrieval_ladder` and `eda_corpus_composition`.
- Objectives has no gold-style target table. Gold 01 sets out Target, Threshold, and Final
  result; here, success bars are bullets with no outcome column.
- Conclusions is much longer than gold's and inlines a full evaluation report.

---

## Round-1 finding status

| # | Round-1 finding | Status | Current location |
|---|---|---|---|
| S1 | Templated "The figures …" transitions | STILL PRESENT | L91, L154, L259, L285 |
| S2 | Hour-borough heatmap placed after borough error | STILL PRESENT | L267–271 |
| S3 | Conclusions repeats Training and Evaluation | STILL PRESENT | L293–446 |
| S4 | Background plain-terms card restates the paragraph | PARTLY FIXED | L54: now an outcome, but adds an unsupported "holds across busy zones" |
| E1 | Glossary-style definitions | PARTLY FIXED | "Served means…" was cut; L66, L68–71, L177, L325, L402–403, L426 remain |
| E2 | Impersonal voice, no "we" | PARTLY FIXED | One "We" at L133 |
| E3 | No tension (Bronx, 2025-01 dip) | STILL PRESENT | L240–241, L390–392 |
| L1 | Repeated figures (84.7% ×9 and others) | STILL PRESENT | 84.7% now ×10 |
| L2 | Consecutive "In plain terms: The figures support" | FIXED | — |
| L3 | "headline comparison is against persistence only" filler | STILL PRESENT | L166–167 |
| L4 | "improves … by −4.1%" | STILL PRESENT | L352 |
| L5 | "flat within noise" with no interval | STILL PRESENT | L178–179, L308, L353 |
| L6 | "+0.091 width cost accompanies" repetition | STILL PRESENT | L254–255 |
| L7 | short_version "91%" vs 90.8% | STILL PRESENT | L3; new fraction `0.9079` at L308 |
| L8 | Nonstandard "xGB" | STILL PRESENT | ×10 |
| T1 | Conformal fit on test half not in Limits; served band unspecified | STILL PRESENT | L251, L421, L84, L431–446 |
| T2 | Drift months 2024-11/12 replay the test window; "new data" | STILL PRESENT | L35, L326 |
| T3 | 2025-01 coverage 87.4% not flagged | STILL PRESENT | L390–392 |
| T4 | No CI for xGB vs `gbm_tuned` | STILL PRESENT | L352 |
| T5 | Table omits `gbm_lgbm_tuned` and `temporal_net` | STILL PRESENT | L341–347 |
| TR1 | Bronx "the one place" (also EWR, Staten Island) | STILL PRESENT | L16, L240–241, L443 |
| TR2 | lag_168 (0.80) "matters most" contradicts lag_1 3.31 | STILL PRESENT | L328–330 |
| TR3 | Unknown 93.8% should be 93.7% | STILL PRESENT | L367 |
| TR4 | ΔMAE vs naive +34.6% has the wrong sign | STILL PRESENT | L391 |
| TR5 | "candidates that beat the baseline" contradicts the code | STILL PRESENT | L173–174 |
| TR6 | Untraceable second-summary importances | STILL PRESENT | L373–375 |
| TR7 | Untraceable "about 2 percentage points" | STILL PRESENT | L67 |
| TR8 | 2024-11/12 MAPE, coverage, zone-hours from untracked files only | STILL PRESENT | L386–389 |
| R1 | Compound roadmap titles | STILL PRESENT | L462, L465 |
| R2 | Roadmap details lack a committed number | STILL PRESENT | L460, L463 |
| R3 | Replay card detail doesn't match its title | STILL PRESENT | L457 |
| R4 | One card joins retrain and drift | STILL PRESENT | L465–466 |
| R5 | Next card lacks "Gate:" phrasing | STILL PRESENT | L469 |
| C1 | Plain-terms cards describe figures | FIXED | — |
| C2 | Transitions don't name chart IDs | STILL PRESENT | L91, L130, L154, L223, L259, L285 |
| C3 | Conclusions inlines the full report | STILL PRESENT | L293–446 |

**Totals:** 36 findings. 2 FIXED, 3 PARTLY FIXED, 31 STILL PRESENT.

---

## Top 5 remaining fixes, by severity

**1. Feature importance contradiction (L328–330 and L373–375).** Delete "Last week's hour matters
most: lag_168 (0.80) tops lag_24 (0.64)" and the "second summary" sentence. Neither has a committed
source, and both contradict `gbm_feature_importance.json` ("dominant driver: lag_1") and the
article's own L371–372. Replace with: "The last hour matters most: shuffling lag_1 adds 3.31 MAE,
ahead of lag_168 (2.58) and lag_24 (2.48)."

**2. Bronx-only claim (L16, L240–241, L443).** `borough_mae.json` shows persistence also beats
every GBM at EWR (0.147 vs 0.279) and Staten Island (0.022 vs 0.196). Rewrite as: "In the three
sparsest groups (Bronx, EWR, Staten Island), same-hour-yesterday still beats every GBM."

**3. Coverage claims (L288, L451, L54, L262, L367, L390–392).**
- 90.8% is the city-wide figure, not a busy-zone figure. Say "city-wide". If the busy-zone figure
  is wanted, it is dense 89.6% → 90.3% after conformal.
- Fix "Unknown 93.8%" to 93.7%.
- Flip "+34.6%" to "−34.6%" to match the L336–337 sign convention.
- Flag 2025-01 coverage of 87.4% as an under-cover, about 2.6 points below target. Do the same in
  roadmap L466.

**4. Serving-rule prose (L173–174).** The quoted `serving.py` contradicts "among candidates that
beat the baseline". Change it to "among candidates with complete mean and `p90` artifacts". Also
add one Limits bullet saying the conformal offsets are fit on the first test half, so the adjusted
band is test-derived. Either soften L84 or qualify it.

**5. Untraceable and over-precise drift and green numbers (L386–389, L35, L67, L398, L397).**
- Drop the 2024-11 and 2024-12 MAPE, coverage, and zone-hour figures, or commit the drift
  reports.
- Round the MAEs and deltas to README precision.
- Say that 2024-11 and 2024-12 replay test months and check wiring, so only 2025-01 is new data.
  Fix key concept L35 to match.
- Cite or soften "about 2 percentage points" (L67).
- Replace "337,080" with "about 337k" (L398).
- Correct the yellow-model MAPE delta to −18% (L397).

## Ready to publish?

**No.** The round-2 edit changed the framing (Background and the plain-terms cards) but left the
body untouched. Five claims contradicted by committed evidence remain (TR1–TR5), and the new cards
add a sixth (the "busy zones" coverage). Twelve numbers still have no committed source. Fixes 1–3
alone are about 20 lines of edits and would remove every outright contradiction.
