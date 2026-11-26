# Round-2 review: 02-demand-forecasting story.yaml

- Target: `projects/02-demand-forecasting/story.yaml` at HEAD (last touched in `e69bba84`). Line numbers below refer to this version.
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/02-demand-forecasting.md`. That review covered `18adc59d`.
- Gold template: `projects/01-rag-agent/story.yaml`
- Evidence re-checked: `reports_m5_full/metrics.json`, `reports_m5_full/evaluation_metadata.json`, `reports_m5_full/erratic_challenger.json`, `README.md`, `DESIGN.md` (0.18.0 changelog), `src/demand_forecasting/m5_track.py` (module docstring), and the diagram sources that render inside this article: `apps/showcase-web/src/diagrams/m5Pipeline.ts` and `apps/showcase-web/src/diagrams/auto/02-demand-forecasting-{1..5}.ts`
- Stance: read-only. No repository file other than this review was written.

## What changed since round 1

`git diff 18adc59d HEAD -- story.yaml` shows edits to presentation only:

- The background section was rebuilt on the gold template's frame: "Follow the pipeline in three steps" followed by three bold-led bullets.
- Every `In plain terms` card was rewritten into lay language.
- Many numbers were wrapped in backticks.
- Long lines were reflowed.

None of the factual findings from round 1 were addressed. The rewrite also introduced new errors:

- L16 says "eight `LightGBM` candidates".
- Four plain-terms cards say "three tree models".
- L267 says "biggest gains at store and category totals".

## Grades

| # | Dimension | R1 | R2 |
|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 |
| 2 | Engagement and human-like narrative | 6 | 6 |
| 3 | Language quality | 6 | 6 |
| 4 | Technical depth | 7 | 6 |
| 5 | Truthfulness | 4 | **3** |
| 6 | Roadmap cards | 7 | 6 |
| 7 | Consistency with gold template | 8 | 7 |
| | **Overall** | 6 | **5** |

### 1. Structure and article logic: 7

The arc is sound: question, contract, data, EDA, candidates and screen, metric, results, then conclusions. The new background bullets follow the gold opener well. Three problems remain:

- Results (L243–261) still runs two challenger stories together, spike-capture routing and Huber, in one paragraph pair. "This arm is absent from the ranking figure" (L259–260) is still ambiguous, because the routed arm is also absent from that figure.
- Conclusions (L297–301) repeats the spike-capture paragraph from Results (L250–255) almost word for word.
- L273 opens Conclusions with "The closing diagram summarizes...". That diagram does not appear until L359, after Limits.

### 2. Engagement and narrative: 6

The new opening is sharper, and the plain-terms cards now read like a person talking. The body still leans on the diagrams instead of telling the story:

- "Read the diagram from left to right" (L34)
- "Apply the diagram's three stops" (L72)
- "Follow the selection diagram from left to right" (L140)
- "Follow the diagram from the `30,490` bottom forecasts" (L199)
- The Conclusions bullets open "The diagram's pooled ensemble…" and "Its stability screen…" (L288–292)

There is still no concrete planner example of what 0.62 vs 0.89 WRMSSE means for a single store-department reorder.

### 3. Language quality: 6

- Gains: the plain-terms cards are clear and no longer open with "The diagram…".
- Every transition after the background still uses the same frame, "X; next, Y ([Z →])" (L47, L81, L112, L179, L218, L263).
- Backticks are now applied inconsistently. Numbers are code-formatted in some places and plain in others, sometimes in the same sentence: `0.6219` / `0.6225` / 0.6459 (L231), `0.6473` and 0.7093 (L234), `66.6%` against the ensemble's 57.2% (L239–240 and L296), `0.95` + `0.00` + 0.05 (L320–321). The gold template is consistent.
- These phrases are still awkward:
  - "Before the evaluation contract shown below, the input is…" (L54–55)
  - "Full scale prices those days into the hierarchy but does not fix them" (L240–241)
  - "Full scale prices intermittency into the hierarchy but does not remove it" (L349), a near-repeat of the line above
- "scored-once" or "scored once" appears 16 times. That clashes with L255–257, which admits the test window was read twice, and with L76, "scores every candidate exactly once".
- The quiet-day sentence (floor `66.6%` vs blend `57.2%`) appears at L108–109, L175, L239–240, L296, L348, L374 and L407, plus in the short_version. That is eight occurrences.

### 4. Technical depth: 6

The strengths from round 1 still hold:

- WRMSSE is explained with equal weight per level and revenue weights within each level.
- The code excerpt shows the blend formed before scoring.
- The stability screen is defined exactly.
- The negative results carry the bootstrap noise band.

The grade drops for these reasons:

- **New error (L16):** "Train eight `LightGBM` candidates." Only 5 of the 8 candidates are LightGBM. The other three are `seasonal_naive`, `auto_ets` and `convex_ensemble` (`metrics.json` `candidates`).
- **Feature list still wrong (L124):** it says "7/14/21/28-day rolling means". The docstring in `m5_track.py` (L23–25) gives lags 1/7/14/21/28; rolling means 7/28/56/84 and stds 7/28 on lag 1; rolling mean 7/28 and std 7 on lag 7; an expanding mean; and calendar and exogenous inputs. The article has conflated the lags with the rolling windows.
- **Direct vs recursive is still undisclosed.** `pooled_strategy: "direct"` (`metrics.json`, `evaluation_metadata.json`) means the pooled arms fit h = 1..28 directly, while the global fit is recursive (L122–123, L334). So "pooling beats a global fit" (L231–233, L288–289) changes two variables at once.
- **The blend is effectively two models.** The weights are 0.95 / 0.00 / 0.05, so `lgbm_pool_store` contributes nothing. The text still says "three-member blend" (L290), and the new plain-terms cards repeat "three tree models" (L22, L182, L267, L362).
- **The ensemble's edge over the best single fit is not discussed.** The gap is 0.6211 vs 0.6219, or 0.0008, about 1.2× the routed-arm noise band of 0.000644. The single fit also wins on bottom WAPE (0.7617 vs 0.7623) and on bias (+0.0177 vs +0.0222). An expert reader will notice this.
- **New observation:** at the total level the blend (0.314) loses to four learned arms: `lgbm_pool_dept` 0.286, `lgbm_tweedie` 0.296, `lgbm_pool_store` 0.298 and `lgbm` 0.300 (`metrics.json` `test.*.per_level_wrmsse.total`). The article presents the aggregate levels as where the blend wins (L209–213, L267). It wins there only against the floor.

### 5. Truthfulness: 3

These claims trace to committed files:

- 0.6211, 0.6219, 0.6225, 0.6459, 0.6473, 0.6601, 0.7093, 0.8929
- −30.4%, −30.3%, −26.1%, −20.6%
- WAPE and bias table values
- Stability values 0.0538 / 0.0549 / 0.0347 / 0.0525 / 0.0577. These are population std over **9** origins.
- 66.6% / 57.2%
- 0.314 / 0.560, 1.04–1.15, 1.38–1.39
- 2,754 / 27,736 / 91%, 59.5%
- 47,649,940 rows, 1,969 days, 2011-01-29..2016-06-19
- 42,840 nodes, 12 levels
- Groups 10 / 30 / 7
- Weights 0.95 / 0.00 / 0.05
- 0.6235, +0.0025, 3.9× (0.002488 / 0.000644 = 3.86)
- 0.8247 / 0.8260
- 0.8683 / 0.7409 after origin 1
- Seed 42, 1,096 days, the 28-day horizon, 7-day spacing

Claims that are contradicted or untraceable:

| Line(s) | Claim | Evidence | Verdict |
|---|---|---|---|
| L36, L74–75, L85, L141, L291, L309, L323, L331, L345 | Selection uses "two earlier cutoff dates" / "2 selection origins" (2016-05-08, 2016-05-15) | `metrics.json` `origins.selection` lists 9 dates, 2016-03-20 … 2016-05-15. `evaluation_metadata.json` `split.n_selection = 9`. The two-origin split is the **capped** development run (`DESIGN.md` L763–764). | **Contradicted.** The article also says "nine" at L292 and L302, so it contradicts itself. |
| L331 | "Origins: 3 weekly cutoffs" | `split.n_origins = 10` | **Contradicted.** The stale source is still `README.md` L50. |
| L340–341 | "Runtime is `46,509` seconds" | This number is in no committed file. `evaluation_metadata.json` `runtime_seconds = 1348530.613`. | **Untraceable** |
| L177, L341 | "about 12.9 hours on one machine" | Only `README.md` L208/L226 say ~12.9 h. The metadata gives 1.35 M s, about 375 h of summed compute. A single `lgbm_pool_storecat` origin takes about 25,000 s. | **Contradicted by metadata** unless it is labelled as parallel wall-clock time with a source |
| L124 | "7/14/21/28-day rolling means" | `m5_track.py` L23–25 | **Contradicted** |
| L16 | "Train eight `LightGBM` candidates" | `metrics.json` `candidates`: 5 of the 8 are LightGBM | **Contradicted (new)** |
| L22, L182, L267, L362 | "three tree models" / "three pooled tree models" | Weight on `lgbm_pool_store` = 0.00 | **Misleading (new)** |
| L267 | "biggest gains at store and category totals" | Relative cut vs floor: total 43.9%, cat 41.3%, state 39.7%, store 35.8%, dept 34.9%. Absolute cut: item_store 0.341 is the largest; total 0.246 is the smallest. | **Contradicted (new).** Store is neither the largest relative nor the largest absolute cut. |
| L209–213, L402–403 | Margin "broadest at aggregate levels"; "widening bars toward the top show where the win comes from" | Absolute floor − blend gap: total 0.246, item_store 0.341. Each level carries equal weight, so the bottom levels contribute the most WRMSSE reduction. | **Contradicted in absolute terms.** It holds only as a relative gap. |
| L257–258 | "An **earlier** Huber variant" | `erratic_challenger.json` protocol `m5_full_v1-wave34-…`. Spike capture is wave 33 (`DESIGN.md` 0.18.0). | **Contradicted.** The Huber variant is the later experiment. |
| L246–248, L297–298 | Capped window: "the swap won its erratic quadrant against the floor" | `DESIGN.md` L765–768: on the capped window the gate was **already REJECTED** (+0.0204 WRMSSE ≈ 2× noise). Only the win-rate leg passed. | **Misleading.** It implies a capped-window success. |
| L259–261 | Huber "full-panel performance is measured and it loses" | `n_origins_scored: 1` (of 9 selection origins) | **Overstated** |
| L303, L346 | "no bootstrap confidence intervals exist" | `erratic_refinement.wrmsse_delta_bootstrap_routed_vs_champion.ci95` = [0.00178, 0.00307] | **Imprecise.** Should read: no interval on the headline gap. |
| L315 | Bold on `lgbm_pool_store` stability 0.0549 | `lgbm` has the lowest value, 0.0347 | **Misleading emphasis** |
| L76 | "scores every candidate exactly once" | L255–257: the adoption gate re-read the test window | **Internally inconsistent** |
| Rendered diagram `auto-02-demand-forecasting-3` (selection diagram, L137) | "convex_ensemble · weights 0.60/0.10/0.30" and "2 selection origins" | `metrics.json` `ensemble.weights` = [0.95, 0.0, 0.05]; 9 selection origins | **Contradicted (new finding; source `apps/showcase-web/src/diagrams/auto/02-demand-forecasting-3.ts`).** The prose at L144 and L320–321 correctly says 0.95/0.00/0.05, so the article contradicts its own figure. |
| Rendered diagrams `auto-02-demand-forecasting-2` (L69) and `02-m5-pipeline` (L11) | "Choose on past: origins 2016-05-08 + 2016-05-15"; "Stability screen · 2 selection origins" | 9 selection origins | **Contradicted** |

**Untraceable or contradicted numbers: 7.** They are:

1. 2 selection origins (instead of 9)
2. 3 cutoffs (instead of 10)
3. 46,509 s
4. 12.9 h
5. 7/14/21/28 rolling windows
6. "eight LightGBM"
7. Diagram weights 0.60/0.10/0.30

### 6. Roadmap cards: 6

- Titles are verb-first and have no trailing periods. All details are at most 90 characters; the longest is L392 at 75.
- Status claims check out against the repo:
  - 30,490 series checksum-pinned (`evaluation_metadata.json` `checksums_sha256`)
  - Screen of the best three of six
  - Test WRMSSE 0.6211
  - Spike-capture rejection (`adoption_gate.adopted: false`)
- Shipped card 1 (L380): "origins split selection from scoring" still drops the "9 selection origins + 1 test" count that round 1 asked to restore.
- Shipped card 3 (L386): "scored once on the held-out origin" contradicts the second read disclosed at L255–257.
- The `next` card (L392) still describes a past failure, not a next step. "lost its only selection origin" is wrong: the Huber arm was scored on the first of nine origins and then stopped. The gold template's `next` detail names a gate (gold L284). For example: "Gate: beat 0.7409 on origin 1 with no zero-day loss."

### 7. Consistency with the gold template: 7

What now matches the gold template:

- The background opener: question, pipeline diagram, "Follow the pipeline in three steps", bold-led bullets, "Next, …", plain terms
- Plain-terms cards in lay language
- The roadmap form

What still differs:

- Objectives has no target-vs-result table (gold L38–44). This article lists success criteria with no measured column.
- The gold transitions vary ("Next, we…", "…; next, we…"). This article repeats one frame.
- Backtick use on numbers is inconsistent; the gold template is consistent.
- The gold template's "Follow the pipeline" device appears once. This article repeats "Follow / Read / Apply the diagram" four more times.

## Round-1 finding status

| # | Round-1 finding | Status | Current location |
|---|---|---|---|
| 1 | Selection-origin count is "two" instead of nine | STILL PRESENT | L36, L74–75, L85, L141, L291, L309, L323, L331, L345 |
| 2 | "3 weekly cutoffs" instead of 10 origins | STILL PRESENT | L331 |
| 3 | "Runtime is 46,509 seconds" untraceable | STILL PRESENT | L340–341 |
| 4 | "about 12.9 hours on one machine" contradicts metadata | STILL PRESENT | L177, L341 |
| 5 | Feature list conflates lags with rolling windows | STILL PRESENT | L124 |
| 6 | Pooled direct vs global recursive confound undisclosed | STILL PRESENT | L122–135, L231–233, L334 |
| 7 | "An earlier Huber variant" (it is later, wave 34) | STILL PRESENT | L257–258 |
| 8 | Capped-window "won its erratic quadrant" hides gate rejection | STILL PRESENT | L246–248, L297–298 |
| 9 | "Broadest at aggregate levels" / "widening bars" is absolute-false | STILL PRESENT (worse: L267 adds "store and category totals") | L209–213, L267, L402–403 |
| 10 | Huber "full-panel performance is measured and it loses" overstated | STILL PRESENT | L259–261 |
| 11 | "No bootstrap confidence intervals exist" imprecise | STILL PRESENT | L303, L346 |
| 12 | Misleading bold on 0.0549 stability | STILL PRESENT | L315 |
| 13 | "Three-member blend" despite a 0.00 weight | STILL PRESENT (worse: "three tree models" in 4 cards) | L22, L182, L267, L290, L362 |
| 14 | Marginal 0.0008 edge over best single, which wins WAPE and bias, not stated | STILL PRESENT | L226–236, L314–315 |
| 15 | Two challengers in one paragraph; ambiguous "This arm" | STILL PRESENT | L243–261 |
| 16 | Conclusions duplicates Results; quiet-day line repeated 5+ times | STILL PRESENT (8 occurrences) | L297–301; L108, L175, L239, L296, L348, L374, L407 |
| 17 | "The closing diagram" referenced before it appears | STILL PRESENT | L273 vs L359 |
| 18 | Diagram-anchored narration ("Follow the diagram…") | PARTLY FIXED (background now uses the gold "Follow the pipeline" device; body unchanged) | L34, L72, L140, L199, L288–292 |
| 19 | No concrete planner scenario | STILL PRESENT | — |
| 20 | Monotone "X; next, Y" transition frame | PARTLY FIXED (background only) | L47, L81, L112, L179, L218, L263 |
| 21 | Plain-terms cards restate figures / open with "The diagram" | FIXED (but the rewrite introduced the errors in rows 9 and 13) | L22, L50, L85, L115, L182, L222, L267, L362 |
| 22 | Awkward phrasing ("Before the evaluation contract…", "Full scale prices…") | STILL PRESENT | L54–55, L240–241, L349 |
| 23 | "scored-once" overused and clashes with the second read | STILL PRESENT (16 uses) | passim; L76 |
| 24 | Roadmap card 1 lost the "9 selection origins + 1 test" count | STILL PRESENT | L380 |
| 25 | Roadmap `next` detail describes the past and says "its only selection origin" | STILL PRESENT | L392 |
| 26 | Objectives has no target-vs-result table | STILL PRESENT | L40–45 |
| 27 | `README.md` L50 is the stale source of "3 origins (2 selection + 1)" | STILL PRESENT | `README.md` L50 |

Totals: 24 STILL PRESENT, 2 PARTLY FIXED, 1 FIXED.

## New findings this round

1. L16: "eight `LightGBM` candidates". Only 5 of the 8 candidates are LightGBM.
2. L22, L182, L267, L362: "three tree models". One of the three carries weight 0.00.
3. L267: "biggest gains at store and category totals". Contradicted by the per-level numbers in section 5.
4. Rendered selection diagram `auto/02-demand-forecasting-3.ts`: weights 0.60/0.10/0.30 and "2 selection origins". Rendered diagrams `auto/02-demand-forecasting-2.ts` and `m5Pipeline.ts`: two selection origins. These files are outside `story.yaml`, but the article displays them, so the reader sees a figure that contradicts the text.
5. Inconsistent backtick formatting of numbers (L231, L234, L239–240, L296, L320–321).
6. At the total level the blend loses to four single learned arms. Not disclosed.

## Top 5 remaining fixes (by severity)

1. **Fix the selection-origin count everywhere, including the diagrams.** Change "two"/"2" to nine selection origins (2016-03-20 … 2016-05-15) + 1 test = 10 origins:
   - `story.yaml`: L36, L74–75, L85, L141, L291, L309, L323, L331 ("3 weekly cutoffs" → "10 weekly cutoffs"), L345
   - Diagram sources: `apps/showcase-web/src/diagrams/auto/02-demand-forecasting-2.ts`, `auto/02-demand-forecasting-3.ts`, `m5Pipeline.ts`
   - Restore the count in roadmap card 1 (L380).
   - Flag `README.md` L50 as the stale source.

   This is the protocol the whole article rests on, and the stability column is computed over nine origins.
2. **Fix the selection diagram's ensemble weights.** `auto/02-demand-forecasting-3.ts` shows 0.60/0.10/0.30; the committed weights are 0.95/0.00/0.05. While you are there, stop calling it a "three tree models" blend (L22, L182, L267, L290, L362) and say it is effectively a 95/5 blend of two pooled fits. Also fix L16, "eight LightGBM candidates", to "five LightGBM fits among eight candidates".
3. **Remove or source the runtime.** L340–341 "`46,509` seconds" is in no committed file. L177 and L341 "about 12.9 hours on one machine" conflict with `runtime_seconds: 1348530.613`. Either commit the wall-clock figure and say it is parallel wall time, or drop the claim.
4. **Correct the per-level and challenger narrative:**
   - L209–213, L267, L402–403: say the largest *relative* cut is at total (43.9%) while item_store has the largest absolute cut. Drop "store and category totals". Consider noting that at total level single arms beat the blend.
   - L257–258: change "earlier" to "later (wave 34)".
   - L246–248 / L297–298: say the capped run was already gate-rejected (+0.0204 ≈ 2× noise).
   - L259–261: say the Huber arm lost on 1 of 9 selection origins.
   - L392: rewrite the `next` card as a gate.
5. **Fix the feature list and disclose the strategy confound.** At L124, replace "7/14/21/28-day rolling means" with lags 1/7/14/21/28 plus rolling means 7/28/56/84, rolling stds, and an expanding mean. Add one sentence that the pooled arms use the direct strategy while the global fit is recursive, so "pooling beats global" (L231–233, L288–289) mixes two changes. Also state that the 0.0008 edge over the best single fit is about 1.2× the noise band, and that the single fit wins on WAPE and bias.

Secondary fixes:

- L303 / L346: write "no bootstrap interval on the headline gap".
- L315: remove the bold on 0.0549.
- Cut the quiet-day sentence down to two occurrences.
- Move the closing diagram or rephrase L273.
- Normalize backticks on numbers.
- Add an Objectives target-vs-result table (gold L38–44).

## Ready to publish?

**No.** The article states its core protocol wrong: 2 selection origins instead of 9, and 3 origins instead of 10. It contradicts itself ("nine" at L292 and L302). A rendered diagram shows ensemble weights (0.60/0.10/0.30) that disagree with the committed 0.95/0.00/0.05. It also carries an untraceable runtime. Round 2 changed presentation only, left all round-1 factual findings open, and added three new false or misleading claims (L16, L267, and "three tree models").
