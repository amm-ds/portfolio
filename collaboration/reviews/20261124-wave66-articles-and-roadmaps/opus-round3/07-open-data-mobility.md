# Round-3 review: 07-open-data-mobility story.yaml

Reviewer: Claude (Opus). This is a read-only third-round pass by a senior ML writer and reviewer.
Target: `projects/07-open-data-mobility/story.yaml` in the **working tree** on branch
`wave8-articles-truthfulness-2026-11-25` (HEAD `c05accd0`, uncommitted Wave 8 edits).
Gold template: `projects/01-rag-agent/story.yaml`.
Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/07-open-data-mobility.md`.

All line numbers refer to the working-tree file (474 lines).

## What Wave 8 changed

`git diff` on the file shows a targeted truthfulness pass. The body structure is untouched.

- short_version now says 90.8% instead of 91%.
- Bronx-only claims were rewritten as "Bronx, EWR, and Staten Island" (L16, L240–241, L448).
- Weather ranges now include Unknown (L25, L281). The exact list adds Unknown 0.90× and Brooklyn 1.01× (L381–383).
- The drift key concept and the "taught" bullet now say 2024-11/12 are replays and flag 2025-01 coverage at 87.4% (L35–36, L326–328, L388–394).
- The serving-rule prose now matches `serving.py`: no baseline-win gate (L173–175).
- "flat within noise" is gone. It was replaced by "no direct interval is committed" disclosures (L307–308, L354–357).
- The feature-importance contradiction (lag_168 0.80) and the "second summary" were removed (L329–331, L374–378).
- Unknown coverage is now 93.7% (L371). ΔMAE versus naive is now −34.6% (L393).
- The exact table now includes `gbm_lgbm_tuned` and `temporal_net` (L346, L348).
- 2024-11/12 MAPE, coverage, and zone-hours were dropped. Precision was rounded to README (L388–391).
- Green MAPE delta is now −18%, and 337,080 is now "about 337k" (L399–400).
- New Limits bullet: the served band is the raw quantile, and conformal offsets are test-derived (L441–443).
- All "safety band" / "busy zones" wording is gone from the plain-terms cards.
- The roadmap was rewritten. Titles are single-action, details carry one number each, and the next card uses "Gate:".

## Evidence re-checked this round

- `reports/metrics.json`: every run, every delta, paired intervals, and the conformal block.
- `reports/figures/*.json`, with binary arrays decoded:
  - `borough_mae`, `p90_calibration`, `weather_elasticity`, `gbm_feature_importance`
  - `green_transfer`, `conformal_coverage`, `hour_borough_heatmap`, `zone_demand_map`
  - `zone_hour_heatmap`, `actual_vs_pred_top5`, `p90_band`, `gbm_vs_nn`
- `README.md`, `DESIGN.md`, `MODEL_CARD.md`, `SERVING.md`, `params.yaml`
- `src/mobility/serving.py` and `.github/workflows/drift-observatory.yml`
- `reports/drift/` exists on disk but is not tracked in git. The 2024-11/12/2025-01 numbers the article now uses all appear in committed README L143–149 and DESIGN L150–156 and L183–185, so they are traceable.

## Grades

| # | Dimension | R1 | R2 | R3 |
|---|---|---:|---:|---:|
| 1 | Structure and article logic | 7 | 7 | 7 |
| 2 | Engagement and human-like narrative | 5 | 5 | 5 |
| 3 | Language quality | 5 | 5 | 5 |
| 4 | Technical depth | 8 | 8 | 8 |
| 5 | Truthfulness | 6 | 5 | 7 |
| 6 | Roadmap cards | 6 | 6 | 7 |
| 7 | Consistency with gold template | 7 | 7 | 7 |
| | **Overall** | **6** | **6** | **6.5 / 10** |

**Lowest dimensions: Engagement and Language (5 each).** Truthfulness rose from 5 to 7, because
every round-2 contradiction was fixed. It does not go higher for two reasons:

- Wave 8 introduced one new sign error, in two places.
- Three contradictions that existed before Wave 8 were missed in round 2 and are still present.

---

## 1. Structure and article logic: 7

No structural change this round.

What works:

- The Background opening matches gold.
- The Training → Evaluation → Results flow is clear.
- The new Limits bullet (L441–443) closes the logic gap between the conformal evaluation and what is actually served.

What is still wrong:

- **Templated, figure-less transitions:**
  - L91 "The bars set the contract"
  - L130 "The panel sets the evidence base"
  - L154 "The figures frame the candidate comparison"
  - L259 "The figures qualify the band"
  - L285 "The figures bound the claims"
- **Ordering.** The hour-borough heatmap (L267–271) still comes in Results, after borough error (L237–241). Demand scale should come before error by borough.
- **Conclusions (L293–451) is still an inlined report and has grown.**
  - It now carries the full 7-row table, the CI table, and coverage, importance, weather, drift, and green paragraphs.
  - The serving rule appears three times: L172–181, L317–319, L351–357.
  - The "no direct interval is committed" disclosure for default versus tuned appears twice in near-identical words (L307–308 and L355–357).
- **The Objectives headline (L59–60) is a long declarative sentence.** It is not a short gold-style imperative.

## 2. Engagement and human-like narrative: 5

Unchanged.

What works:

- The plain-terms cards read naturally.
- The tension material now exists in the text:
  - Persistence wins in the three sparsest groups (L240–241).
  - 2025-01 coverage is 2.6 points short (L394).

What is still wrong:

- The tension material is listed, not told. Neither result is framed as a surprise or a decision point.
- **Glossary chains remain.** " means " still occurs 10 times. Examples:
  - L66 "A baseline is a simple reference method…"
  - L68–71 RAM/GB/cloud definitions
  - L102 TLC expansion
  - L107–108 NOAA GHCN expansion
  - L178–179 "Tuning means searching over model settings."
  - L184–185 neural-network definition
  - L325 "Weights are the model's learned numerical parameters."
  - L404–405 three-file contract definition
  - L428 "Lazy processing delays work until results are needed."
- **The voice is impersonal.** There is one "We" (L133) and no other first-person narration. Gold 01 uses "we" throughout.

## 3. Language quality: 5

**Repetition is unchanged or worse.** Counts in the working tree:

| Term | Count |
|---|---:|
| "90.8" | 11 (up from 8) |
| "84.7" | 10 |
| "xGB" | 11 |
| "no-borough" | 11 |
| "persistence" | 10 |
| "28.3" | 6 |
| "4.676" | 6 |

**Filler still present:**

- L166–167 "— the headline comparison is against persistence only".
- L254–255 "That +0.091-pickup width cost accompanies the coverage gain." It restates the previous sentence.
- L307–308 and L355–357 repeat the same disclosure. The second one says "either", which shows it was pasted.

**Format and precision:**

- L309 still writes coverage as a fraction (`0.9079`). Everywhere else uses 90.8%.
- L41 and L50 use 28%; the body uses 28.3%.

**Jargon:** "xGB" is still a nonstandard abbreviation (×11). Write "XGBoost". The roadmap card at L465 already does.

**Formatting:** L240 and L448 are unwrapped long lines in an otherwise hard-wrapped block. This is cosmetic only.

## 4. Technical depth: 8

Improvements this round:

- The full 7-run table.
- An explicit statement that the served band is the raw quantile and the conformal adjustment is test-derived (L441–443).
- Honest "no committed interval" disclosures for xGB versus `gbm_tuned` and for tuned versus default.
- Drift replay months are now separated from unseen months.

Remaining gaps:

- **No interval for the decision-relevant comparisons.** xGB versus `gbm_tuned` and tuned versus default still have no CI. The gap is now disclosed rather than hidden.
- **Small inconsistency on green retraining.** Key concept L33–34 and Conclusions L296 say the recipe is refit "on two months". That is the Jan–Feb control experiment. The production `gbm_green_served` bundle (L402–403) is fit on all 534,240 curated green zone-hours (Jan–Mar, DESIGN L160). The article should say which one is the operating rule.

## 5. Truthfulness: 7

### Contradicted by committed evidence

| Line(s) | Claim | Evidence | Origin |
|---|---|---|---|
| L307–308, L355–357 | "The tuned GBM's relative test `MAE` change versus the default is `−0.2%`" | `metrics.json`: `gbm_tuned` MAE 4.6763 vs `gbm_mean` 4.6670. Tuned is **+0.2% worse**. `deltas.gbm_tuned.mae_reduction_pct_vs_gbm_mean = −0.2` is a negative *reduction*. Under the article's own convention (L336–337, "negative is better"), "change … is −0.2%" reads as an improvement. The sign is wrong. | **NEW in Wave 8.** Round 2 wording was sign-neutral ("sit 0.2% apart"). |
| L11–12 | zone_demand_map caption: "Demand concentrates in Manhattan and at **JFK/EWR**" | `zone_demand_map.json`, decoded: EWR (zone 1) averages **0.077** pickups/hour, among the darkest zones. JFK (132) is 211.2 and LaGuardia (138) is 143.4. The bright airports are JFK and LaGuardia. The `hour_borough_heatmap` also has EWR peaking at 0.20. | Present before Wave 8; missed in round 2. |
| L48, L133 | "hourly weather" / "hourly Central Park weather" | The source is NOAA **GHCN-Daily** (the article's own L104–108). DESIGN L49 says "weather joined on date". MODEL_CARD L21 says daily PRCP/SNOW/TMAX/TMIN. Daily values are broadcast to hours; they are not hourly observations. | Present before Wave 8; missed in round 2. |
| L466–468 (roadmap) | `shipped`: "Calibrate the demand upper band" — "Dense-zone coverage rises from 89.6% to 90.3% after adjustment." | The article's own L441–443 says the serving bundle stores the raw quantile p90, and conformal offsets are an evaluation adjustment fit on test data. `serving.py` never imports `conformal`. Only the evaluation is shipped, not a calibrated served band. | Card rewritten in Wave 8; the overclaim is now sharper. |

### Imprecise (minor)

- **L270–271 "about four orders of magnitude".** The decoded `hour_borough_heatmap` runs from Staten Island's minimum 0.0019 to Manhattan's 103.67. That ratio is about 5.4×10⁴, so log₁₀ ≈ 4.7. "Nearly five orders" is more accurate. Round 2's suggested "closer to four" was also too low.
- **L35, L297, L429–431, "monthly drift check" / "scheduled observatory".** `drift-observatory.yml` runs weekly (Thursdays) and scores the newest published month. "Monthly" describes the data cadence, not the check cadence. This is acceptable but loose.
- **L72 and roadmap L461–462, "Replay the full study with one command".** README L32 gives `uv run dvc repro`. DESIGN L169–175 notes that the `serving` stage cannot be `dvc repro`'d and that drift needs `--single-item`. The detail ("rebuilds the … zone-hour panel") is accurate. The title slightly overclaims "the full study".

### Untraceable (no committed source)

| Line | Claim | Note |
|---|---|---|
| L65 | "Cut error by at least `20%` against the same-hour-yesterday baseline" | No committed README, DESIGN, or MODEL_CARD line sets a 20% accuracy target. DESIGN L39's "20% ceiling" is a DQ gate, not this target. It is either a retrofitted objective or needs a source. |

**Untraceable count: 1** (down from 12).

### Verified this round

**Run table (L343–349).** All 7 rows match `metrics.json` to 3 dp or 1 dp:

- −28.3%, −28.4%, −29.7%, −31.2%, −15.5%, −20.5%
- xGB 4.05 → "4.1% lower" (L354, L465)
- Validation MAEs 3.165 / 3.173 / 3.182 (`params.yaml`)

**Paired intervals (L365–366):** both rows, plus 2,000 resamples, seed 42, 7-day blocks, and 265 zones.

**Conformal:**

- Coverage before: 94.3 / 88.2 / 89.6
- Coverage after: 94.3 / 89.9 / 90.3
- Overall 90.7 → 91.5
- Band height 7.032 → 7.124 (+0.091)
- Offsets +0.09 / +0.18

**p90 calibration:** all nine values (L369–371), including Unknown 93.7%.

**Borough MAE:** persistence beats `gbm_mean`, `gbm_tuned`, `gbm_xgb_tuned`, and `gbm_lgbm_tuned` in each of Bronx (0.483), EWR (0.147), and Staten Island (0.022).

**Weather ratios:** all eight values (0.895, 0.900, 0.919, 0.928, 0.965, 1.009, 1.030, 1.080).

**Feature importance:** lag_1 3.311, lag_168 2.576, lag_24 2.477, hour 1.12.

**Heatmap and map values:**

- Manhattan peak 103.67 at 18:00
- Bronx maximum 0.732
- Busiest zone 213.9 (zone 237)
- 263 mapped zones
- The zone-hour heatmap shows the top 30 zones for the week starting Monday 2024-10-07
- The top-5 and p90-band figures cover 14 days (336 hours)

**Green transfer:**

- Yellow-trained vs persistence: 0.296 vs 0.212
- RMSE 0.908 vs 1.100 → −17%
- MAPE 66.7 vs 81.8 → −18%
- Retrained: 0.180 / 0.688 / 66.4%
- 197,160 / about 337k / 534,240 zone-hours

**Drift:**

- 5.059 (+8.2%) and 5.046 (+7.9%)
- 2025-01: 4.442 (−5.0%), 59.6%, ΔMAE −34.6% ("improvement" in README L149), coverage 87.4%
- 2.6 points below target

**Infrastructure:** 41.2M, 584,855, 2,327,760, ~1.5 GB, ≈2 GB peak (DESIGN L17–19), 8 GB, 30/10 trials, MASE scale ≈6.13.

**Derived:** 1.8 fewer pickups (6.517 − 4.676 = 1.84).

**Code excerpt (L204–218):** matches `serving.py` L70–83 verbatim. Only the logger line is omitted.

## 6. Roadmap cards: 7

What passes:

- All titles are verb-first and single-action.
- All details are ≤90 characters. The longest is 67 (L474).
- Every detail carries one committed number.
- The next card uses the gold "Gate:" phrasing.
- Shipped claims verified:
  - Replay panel: `dvc.yaml`.
  - Serving rule: `serving.py`.
  - Per-service retrain: `reports/models/serving/green/`, `services.json`. 0.212 → 0.180 is in README L108–111.

What is wrong:

- **L466–468 "Calibrate the demand upper band" is marked `shipped`,** but the served band is the raw quantile (the article's own L441–443). Two honest fixes:
  - Retitle it "Measure the upper band's coverage", with detail "Raw p90 covers 90.8% city-wide; N/A zones 84.7%."
  - Or keep the title and downgrade the status to `next`, with a Gate for shipping out-of-sample conformal offsets.
- **L461–462 "Replay the study with one command"** slightly overclaims. See the imprecise items in section 5.
- **The drift observatory has no card,** although it is real (the workflow plus three scored months). This is optional. It would be a strong shipped card if worded around MAE only, for example "Score each new TLC month; 2025-01 MAE −5.0%, coverage 87.4%."

## 7. Consistency with gold template: 7

Aligned with gold:

- Background shape
- Plain-terms cards
- Transition link format
- Roadmap style, now close to gold

Still diverging:

- Section bodies lack gold's bold one-line headlines (data, eda, training, evaluation, results).
- Transitions do not name chart IDs.
- Objectives has no Target / Threshold / Final result table. Gold 01 L38–44 uses one, and here it would neatly hold 20% → 28.3%, 90% → 90.8%, and 8 GB → ≈2 GB.
- Conclusions is still far longer than gold's.

---

## Round-2 finding status

| # | Round-2 finding | R3 status | Evidence / location |
|---|---|---|---|
| S1 | Templated "The figures …" transitions | STILL PRESENT | L91, L130, L154, L259, L285 |
| S2 | Hour-borough heatmap after borough error | STILL PRESENT | L267–271 vs L237–241 |
| S3 | Conclusions repeats Training and Evaluation | STILL PRESENT | L293–451; it grew this round |
| S4 | Background card "holds across busy zones" | FIXED | L54 |
| E1 | Glossary-style definitions | PARTLY FIXED (no change this round) | " means " ×10; L66, L68–71, L178, L325, L404, L428 |
| E2 | Impersonal voice | PARTLY FIXED (no change this round) | One "We", at L133 |
| E3 | No tension (sparse boroughs, 2025-01 dip) | PARTLY FIXED | Facts now stated (L240–241, L394), not narrated |
| L1 | Repeated figures | STILL PRESENT | 90.8 ×11, 84.7 ×10 |
| L2 | Consecutive figure-describing cards | FIXED | — |
| L3 | "headline comparison is against persistence only" | STILL PRESENT | L166–167 |
| L4 | "improves … by −4.1%" | FIXED | L354 "4.1% lower" |
| L5 | "flat within noise" without an interval | FIXED | Replaced with a disclosure, but see the new sign error |
| L6 | "+0.091 width cost accompanies" | STILL PRESENT | L254–255 |
| L7 | short_version 91% / fraction 0.9079 | PARTLY FIXED | L3 fixed; L309 still 0.9079 |
| L8 | Nonstandard "xGB" | STILL PRESENT | ×11 |
| T1 | Conformal on test half undisclosed; served band unspecified | FIXED | L441–443 |
| T2 | Replay drift months called "new data" | FIXED | L35–36, L326–327 |
| T3 | 2025-01 coverage 87.4% not flagged | FIXED | L327–328, L394 |
| T4 | No CI for xGB vs `gbm_tuned` | PARTLY FIXED | Disclosed (L355), still no interval |
| T5 | Table omits two runs | FIXED | L346, L348 |
| TR1 | Bronx-only persistence claim | FIXED | L16, L240–241, L448 |
| TR2 | lag_168 "matters most" | FIXED | L329–331 |
| TR3 | Unknown 93.8% | FIXED | L371 shows 93.7% |
| TR4 | ΔMAE +34.6% sign | FIXED | L393 |
| TR5 | "candidates that beat the baseline" | FIXED | L173–175 |
| TR6 | Untraceable second-summary importances | FIXED | Removed |
| TR7 | Untraceable "about 2 percentage points" | FIXED | Removed (L67) |
| TR8 | 2024-11/12 untracked MAPE, coverage, rows | FIXED | L388–391, "no committed coverage record" |
| R1 | Compound roadmap titles | FIXED | L464, L467, L470 |
| R2 | Details lack a committed number | FIXED | All details |
| R3 | Replay detail does not match its title | PARTLY FIXED | Detail is about the panel; title claims the full study |
| R4 | One card joins retrain and drift | FIXED | Split; drift card dropped |
| R5 | Next card lacks "Gate:" | FIXED | L474 |
| C1 | Plain-terms cards describe figures | FIXED | — |
| C2 | Transitions do not name chart IDs | STILL PRESENT | L91, L130, L154, L223, L259, L285 |
| C3 | Conclusions inlines the full report | STILL PRESENT | L293–451 |

**Totals:** 36 findings. 21 FIXED, 6 PARTLY FIXED, 9 STILL PRESENT.

Round 2 also had truthfulness items outside the numbered table. All of these are now fixed:

- "busy zones" coverage
- −19% → −18%
- 337,080 → about 337k
- Over-precise drift digits
- Unknown missing from the weather range

The "two orders of magnitude" item is PARTLY FIXED: it now says "about four", and the true span is about 4.7.

## New errors introduced by Wave 8

1. **Sign error, tuned vs default (L307–308, L355–357).** The new sentence "relative test `MAE` change versus the default is `−0.2%`" reverses the direction. Tuned MAE is 0.2% *higher* than default (4.676 vs 4.667). Under the article's negative-is-better convention, readers will take it as a small gain.
2. **Roadmap overclaim (L466–468).** The rewritten "Calibrate the demand upper band" card is `shipped` and cites the conformal-adjusted dense coverage. The same Wave 8 edit added a Limits bullet (L441–443) saying the served band is the raw, unadjusted quantile. The article now contradicts itself.
3. **Duplicated disclosure (L307–308 and L355–357).** The same sentence was pasted twice, which adds to the repetition problem.

## Top 5 remaining fixes, by severity

1. **Fix the tuned-vs-default sign (L307–308, L355–357).** Use: "The tuned GBM is `0.2%` worse on test `MAE` than the default (4.676 vs 4.667); no interval for this pair is committed." Keep it once, in Exact numbers, and delete the L307–308 copy.
2. **Correct the airport claim (L11–12).** Change "JFK/EWR" to "JFK and LaGuardia". EWR averages 0.077 pickups/hour in `zone_demand_map.json`. L145 ("the two airports") is then correct.
3. **Replace "hourly weather" (L48, L133).** Say "daily Central Park weather" or "daily weather broadcast to each hour", to match GHCN-Daily (L104–108, DESIGN L49).
4. **Make the calibrate card honest (L466–468).** Either re-scope it to what shipped ("Measure the upper band's coverage" / "Raw p90 covers 90.8% city-wide; N/A zones 84.7%.") or move it to `next` with "Gate: fit conformal offsets out of sample before serving them." Also consider trimming L72 and the L461 title to "Rebuild the panel with one command".
5. **Source or soften the 20% target (L65), and clean up language.**
   - Add the target to DESIGN Requirements, or reword it as "Beat the same-hour-yesterday baseline by a clear margin."
   - Change "about four" to "nearly five orders of magnitude" (L270).
   - Replace "xGB" with "XGBoost" (×11).
   - Drop L166–167 and L254–255.
   - Change `0.9079` to 90.8% (L309).

## Ready to publish?

**No, but close.** Every contradiction from round 2 is fixed, and untraceable numbers fell from
12 to 1. Four contradicted claims remain:

- one new sign error (tuned vs default, written twice)
- the "JFK/EWR" caption
- "hourly" weather
- the roadmap card that says calibration shipped while the article's own Limits says it did not

These need about 8 lines of edits. After them, the article is publishable on truthfulness grounds.
Engagement and Language (5) and the oversized Conclusions remain quality debts, not blockers.
