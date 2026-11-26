# Round-3 review: 02-demand-forecasting story.yaml

- Target: `projects/02-demand-forecasting/story.yaml`, **working tree** on branch `wave8-articles-truthfulness-2026-11-25` (HEAD `c05accd0` plus uncommitted Wave 8 edits). Line numbers refer to the working-tree file (244 lines).
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/02-demand-forecasting.md`. That review used the HEAD version, so its line numbers no longer apply. Every finding was re-checked against the working tree.
- Gold template: `projects/01-rag-agent/story.yaml`
- Evidence re-checked:
  - `reports_m5_full/metrics.json` (test, selection, ensemble, erratic_refinement)
  - `reports_m5_full/evaluation_metadata.json`, `reports_m5_full/erratic_challenger.json`, `reports_m5_full/catalog_meta.json`, `reports_m5_full/demo_payload.json`
  - `reports_m5_full/figures/*.json`, i.e. the four figures the article embeds
  - `reports_m5_full/report.html`
  - `README.md` (working tree), `DESIGN.md` 0.18.0 changelog, and the `src/demand_forecasting/m5_track.py` feature docstring
  - Diagram specs: `apps/showcase-web/src/diagrams/m5Pipeline.ts` and `auto/02-demand-forecasting-{1..5}.ts` (working tree)
  - The demo hero card in `apps/showcase-web/src/lib/staticRegistry.ts`
- Stance: read-only. No repository file other than this review was written.

## What changed in Wave 8

`git diff -- story.yaml` shows a real content rewrite this time, not a presentation pass:

- **Selection origins:** "two" changed to nine, and "3 cutoffs" to 10.
- **Runtime:** the invented 46,509 s and the 12.9 h figure were replaced by the committed 1,348,530.6 s of summed runtime.
- **Feature list:** corrected.
- **Direct vs recursive:** the confound is now disclosed (L97, L157, L177, L201, L219).
- **Effective blend:** it is described as a 95/5 blend of two active models.
- **Edge over best single:** the marginal 0.0008 edge is stated, along with the single fit's better WAPE and bias.
- **Per-level results:** relative and absolute gains are now separated, and the four arms that beat the blend at total level are disclosed.
- **Huber variant:** "earlier" changed to "later", and its claim is limited to 1 of 9 origins.
- **Capped run:** the gate rejection is stated.
- **Bootstrap interval:** the text now says no interval covers the headline, and the spike-capture CI is cited.
- **Objectives:** a target-vs-result table was added.
- **Roadmap:** cards were rewritten.

The diagram specs were fixed as well: 9 origins, weights 0.95/0.00/0.05, champion 0.6211. `README.md` L50 was also fixed.

The prose is now mostly truthful. The main remaining problem sits next to the prose: **all four embedded figures and the linked demo still render the superseded 0.6161 run.** That run used weights 0.60/0.10/0.30, two selection origins and a recursive catalog. The Wave 8 captions now describe numbers the figures do not show. Round 2 missed this.

## Grades

| # | Dimension | R2 | R3 |
|---|---|---|---|
| 1 | Structure and article logic | 7 | 8 |
| 2 | Engagement and human-like narrative | 6 | 6 |
| 3 | Language quality | 6 | 6 |
| 4 | Technical depth | 6 | 8 |
| 5 | Truthfulness | 3 | **5** |
| 6 | Roadmap cards | 6 | 8 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | 5 | **6** |

### 1. Structure and article logic: 8

The arc is clean. It runs from question to contract (now a real table), data with dated origins, EDA, candidates and screen, metric with relative and absolute gains, results with challengers, and conclusions.

The two challengers now get separate paragraphs (L161, L163). "Neither challenger appears in the main candidate ranking" (L163) removes the old ambiguity. The premature "closing diagram" reference is gone.

What remains:

- Conclusions ("What the experiment taught", L177–181) restates the Results bullets almost point for point: direct vs recursive, 95/5, the 0.0008 edge, WAPE and bias, spike capture, and Huber. The gold template's conclusions add new material, such as the retrieval and generation tables and the pass history. They do not re-list results.
- `auto-02-demand-forecasting-5` sits after Limits (L212) and recommends "Weekly reforecast · floors + scored-once windows". The prose never argues for weekly reforecasting any more, so the closing diagram makes a recommendation the text no longer supports.

### 2. Engagement and narrative: 6

- The opening question is strong. The new results lead, "The blend wins the headline by only `0.0008`…" (L155), is honest and arresting.
- The diagram-narration habit ("Follow / Read / Apply the diagram") is gone.
- The article still never translates 0.62 vs 0.89 WRMSSE into a planner's terms. One store-department reorder example would make the 30.4% concrete.
- The rewrite traded narrative for staccato. See section 3.

### 3. Language quality: 6

- **New: telegraphic, choppy sentences.** Many passages read as a list of 6–10-word sentences with no connective tissue:
  - L26: "The model must beat… The test must be repeatable. One lucky split is not enough."
  - L136–138: five consecutive one-clause sentences
  - L145: "Thus the blend does not win every aggregate comparison."
  - L126: "Its statistical solutions are direct. A rerun therefore produces the same bytes."
- **New: "direct" carries two meanings.** L97 defines "direct" as the one-model-per-horizon strategy. L126 then says "Its statistical solutions are direct", where it means closed-form, seed-free ETS fits (`evaluation_metadata.json` `determinism`). A reader who just learned the forecasting-strategy meaning will misread the sentence. Suggested wording: "AutoETS fits are closed-form and seed-free".
- **New: "the noise band" refers to two different bands in one paragraph (L161).** The capped run's +0.0204 is "about twice the noise band", meaning ±0.0106 on the capped run (`DESIGN.md` L767–768). The full run's +0.0025 is "3.9 times the paired bootstrap noise band", meaning 0.000644. L159 also reuses the 0.000644 band for the blend-vs-single comparison. Name each band.
- **Quiet-day repetition.** The 66.6% / 57.2% pair still appears with numbers at L38, L82–83, L128, L208 and L244. It appears without numbers at L3, L151, L180, L215 and L222. Down from 8+ but still heavy; keep the numbers once in EDA and once in Limits.
- Backtick use on numbers is now consistent in the body. That round-2 issue is fixed.

### 4. Technical depth: 8

The big round-2 gaps are closed:

- The direct-vs-recursive confound is disclosed in four places.
- The zero weight is acknowledged.
- The marginal edge is set against a noise band, and the single fit's WAPE and bias wins are reported.
- Relative and absolute per-level gains are separated, and the four learned arms that beat the blend at total level are disclosed (verified: dept 0.286, tweedie 0.296, store 0.298, lgbm 0.300 vs blend 0.314).
- The feature list is now essentially correct.

Remaining nits:

- L95 omits the lag-7 rolling means 7/28 (`m5_track.py` L23–25: "rolling mean 7/28 and std 7 at lag 7").
- L159 measures the ensemble-vs-single gap against the *routed arm's* bootstrap band. That band was computed for a different paired comparison. Say "for scale only" or bootstrap the gap itself.
- L128 and L203 state "1,348,530.6 seconds of summed compute" as the run's cost. About 565,000 s of that, roughly 42%, is the two spike-capture peak variants (`runtime_seconds_peak_variant_origin`), not the headline candidates. One clause would fix this.

### 5. Truthfulness: 5

**Prose: near-clean.** I re-derived every number in the `story.yaml` text from committed files:

- **Headline scores:** 0.6211, 0.6219, 0.6225, 0.6459, 0.6473, 0.6601, 0.7093, 0.8929. The reductions −30.4% / −30.3% / −26.1% / −20.6% also check out.
- **Exact-numbers table:**
  - WAPE 0.7623 / 0.7617 / 0.7626 / 0.7710 / 0.9159
  - Bias +0.0222 / +0.0177 / +0.0041 / −0.0063 / −0.0120
  - Stability 0.0538 / 0.0549 / 0.0347 / 0.0525 / 0.0577, the population std over 9 selection origins
- **Quiet days:** 66.6% / 57.2%.
- **Per-level and hierarchy:**
  - Total 0.314 vs 0.560, a 43.9% cut (0.2457 / 0.5600)
  - item_store absolute gap 0.341 (1.3830 − 1.0416). It is the largest gap; item is 0.282 and state_item 0.310.
  - 12 levels and 42,840 nodes
- **Panel and data:** 2,754 / 27,736 series (91%); 59.5%; 47,649,940 rows; 1,969 days; 2011-01-29..2016-06-19; 10 / 3 / 7; groups 10 / 30 / 7.
- **Origins:** 9 selection origins (2016-03-20..2016-05-15), 1 test origin (2016-05-22), 10 origins total, 7-day spacing, a minimum of 1,096 training days, seed 42.
- **Spike capture:** 0.6235, +0.0025, 3.9× (0.002488 / 0.000644 = 3.86), 0.8260 → 0.8247, CI [0.00178, 0.00307], capped run +0.0204.
- **Huber:** 0.8683 vs 0.7409 on origin 1 of 9.
- **Ensemble and runtime:** weights 0.95 / 0.00 / 0.05; 1,348,530.6 s.

**Rendered evidence: contradicted.** The article embeds four figures and links one demo. None of them reflects the 0.6211 champion.

| Line(s) | Claim in article | Rendered / committed evidence | Verdict |
|---|---|---|---|
| L168, caption L242 | Ranking: "convex ensemble leads at 0.6211, the best single pooled fit scores 0.6219" | `figures/m5_full_candidate_ranking.json` bars: ensemble **0.6161 (−31.0%)**, pool_store 0.6217, pool_dept 0.6313, **pool_storecat 0.6575**. Title: "leads at 0.6161… pooling wins at full scale" | **Contradicted by its own figure.** The bar order differs too: storecat ranks 5th in the figure but 2nd in `metrics.json` |
| L152, caption L243; text L145 | Per-level: total 43.9% cut; "Four learned single arms beat the blend at total level" | `m5_full_per_level_wrmsse.json`: blend total **0.350** (a 37.5% cut), not 0.314. The figure plots only blend, floor and pool_store, so the "four arms" claim is not visible. Figure title still says "the blend's edge is broadest at the aggregate levels the competition weights most" | **Contradicted.** The figure title also repeats the round-2 error the prose fixed |
| L133, caption L244; L128 | Pooling panel: blend zero-day accuracy 57.2%, bias +2.22% | `m5_full_pooling_panel.json`: blend zero-day 0.5734 (title says "57.3%"), blend bias 3.28%, pool_storecat bias 4.82% (`metrics.json`: 2.28%) | **Contradicted (stale data)** |
| L90, caption L241; L209 | Sample series show "the ensemble curve with its member envelope"; "the demo band is the per-day min/max envelope of blend members" | `catalog_meta.json`: ensemble weights **[0.6, 0.1, 0.3]**, `pooled_strategy: "recursive"`. `demo_payload.json` and `catalog_forecasts.parquet` derive from it | **Contradicted.** The curves and envelopes come from the superseded blend, not the 0.95/0.00/0.05 direct champion |
| L173 | "try the live demo" | `staticRegistry.ts` hero card: "**0.6161 vs 0.8929**", "−31.0%"; `demo_payload.json` `champion_wrmsse` 0.6161 | **Contradicted.** The linked demo shows a different headline |
| L79 | "The mid-volume series fluctuates around quiet days" | Third panel in `m5_full_sample_series.json` (HOUSEHOLD_1_110_TX_2, "smooth dense", ADI 1.10): **0 zero days** in 56 history and 28 actual days; mean about 12–15 units/day | **Contradicted.** This is pre-existing; round 2 missed it |
| L155, L159, L179 | Edge "only `0.0008`"; "about `1.2` times the… `0.000644` noise band" | Unrounded gap 0.6219173 − 0.6210518 = **0.000866** (rounds to 0.0009). 0.000866 / 0.000644 = **1.34** | **Imprecise.** It subtracts rounded values. Say "under 0.001, about 1.3×" |
| L145 | "At item level, learned candidates score between `1.04` and `1.15`" | The `item` level itself spans 1.108–1.150. The 1.04 low end is `item_store` | **Imprecise.** Say "at the three item-grain levels" |
| L241 | Sample series "at the test origin on 2016-05-22" | Figure title says "test origin 2016-05-23", the first forecast day | Minor inconsistency |
| Diagrams L11, L28, L52, L140, L212 | (rendered labels) | `m5Pipeline.ts`: "Final 28 days · scored once", "scored exactly once", edge "blend scored once". `auto-1`: "zero-day, scored once". `auto-2`: "Score once". `auto-4`: "scored once". `auto-5`: "scored-once windows" | **Inconsistent** with L31 and L161, which disclose that the gate reread the test window |
| L239 (roadmap `next`) | "Gate: beat 0.7409 on origin 1 with no zero-day accuracy loss" | `erratic_challenger.json` rule: "promote to the test origin only if the routed arm improves the selection pooled official WRMSSE without regressing zero-day accuracy" (all selection origins; Huber was stopped after the first) | **Understated gate.** A one-origin threshold also contradicts L26: "One lucky split is not enough" |

Count of untraceable or contradicted items:

- **Numbers in the `story.yaml` prose:** 0 untraceable. 2 are imprecise (0.0008 and 1.2×).
- **Article claims contradicted by rendered or linked evidence:** 6 (four figures, the demo, and the L79 mid-volume claim).

Truthfulness is graded 5, not 8. A reader sees a bar chart headed "0.6161" directly above the caption's "0.6211", so the gap between text and figures is a visible defect.

Secondary note: `reports_m5_full/report.html` is also entirely stale: 0.6161, "2 sel. origins", weights 0.60/0.10/0.30, and the wrong stability column. The article does not link it directly, since the L173 "full evaluation report" points at the site page, but the README presents it as the rebuildable report.

### 6. Roadmap cards: 8

- Titles are verb-first with no trailing periods. Detail lengths are 70 / 62 / 61 / 67 / 61 characters, all ≤90.
- The shipped claims check out:
  - Checksums: four SHA-256 values in `evaluation_metadata.json`
  - 9 + 1 origins
  - Best three of six, with weights 0.95 / 0.00 / 0.05
  - Test WRMSSE 0.6211
  - Spike-capture rejection: `adoption_gate.adopted: false`
- Card 1 restored the origin count. Card 3 no longer says "scored once" and discloses the second read.
- The `next` card is now a gate, as round 2 asked, but it understates the committed rule (see the table above). Suggested fix: "Gate: beat the champion's 9-origin screen with no zero-day accuracy loss."

### 7. Consistency with the gold template: 7

What matches the gold template:

- The background opener: question, pipeline diagram, "Follow the pipeline in three steps", bold-led bullets, "Next, we…", plain terms
- Plain-terms cards in lay language
- The roadmap form
- The new Objectives table

What still differs:

- The gold Objectives table has three columns, Target | Threshold | Final test result, with the result in bold (gold L38–44). This one has two columns and no thresholds.
- The gold template uses the "Next, we…" transition only in the background (gold L18). This article closes every one of seven sections with "Next, we…", which makes the frame monotone.
- The gold template uses tables in Data, EDA, Evaluation and Results. Here only Objectives and Conclusions have tables. A small EDA table (dense / intermittent / zero share) or an evaluation-check table would match the gold rhythm and cut prose.

## Round-2 finding status

| # | Round-2 finding | Status | Working-tree evidence |
|---|---|---|---|
| 1 | Selection-origin count "two" instead of nine | **FIXED** | L16, L31, L55, L103, L178, L200; diagrams auto-2, auto-3 and m5Pipeline now say 9 |
| 2 | "3 weekly cutoffs" instead of 10 | **FIXED** | L200 |
| 3 | "Runtime is 46,509 seconds" untraceable | **FIXED** | L128, L203 use 1,348,530.6 s (the share from peak variants is not stated; see §4) |
| 4 | "12.9 hours on one machine" | **FIXED** | Removed; README also changed to "extended" |
| 5 | Feature list conflates lags and rolling windows | **FIXED** (nit: lag-7 rolling means 7/28 omitted) | L95 |
| 6 | Direct vs recursive confound undisclosed | **FIXED** | L97, L157, L177, L201, L219 |
| 7 | "Earlier" Huber variant | **FIXED** | L163 "later" |
| 8 | Capped-window success framing hid gate rejection | **FIXED** (new ambiguity: two "noise bands") | L161 |
| 9 | "Broadest at aggregate levels" | **PARTLY FIXED** | Prose L145 and caption L243 are fixed. The rendered figure title still says "broadest at the aggregate levels the competition weights most" |
| 10 | Huber "full-panel performance measured" overstated | **FIXED** | L163 |
| 11 | "No bootstrap CIs exist" imprecise | **FIXED** | L207 |
| 12 | Misleading bold on 0.0549 | **FIXED** | L190 |
| 13 | "Three-member blend" / "three tree models" | **FIXED** | L17, L22, L132, L167, L178, L215 |
| 14 | Marginal 0.0008 edge undisclosed | **FIXED** (ratio 1.2× should be about 1.3×) | L155, L159, L179 |
| 15 | Two challengers in one paragraph; ambiguous "This arm" | **FIXED** | L161, L163 |
| 16 | Conclusions duplicates Results; quiet-day line repeated | **PARTLY FIXED** | The spike-capture copy is gone, but L177–181 still re-list Results. The quiet-day pair appears with numbers 5× and without numbers 5× |
| 17 | "The closing diagram" referenced before it appears | **FIXED** | Removed |
| 18 | Diagram-anchored narration | **FIXED** | No "Follow / Read / Apply the diagram" in the body |
| 19 | No concrete planner scenario | **STILL PRESENT** | — |
| 20 | Monotone transition frame | **PARTLY FIXED** | "X; next, Y" became "Next, we …" at the end of all 7 sections |
| 21 | Plain-terms cards | **FIXED** | The new cards are accurate (95/5, nine dates, relative vs absolute) |
| 22 | Awkward phrasing ("Before the evaluation contract…", "Full scale prices…") | **FIXED** | Phrases removed. New choppiness and the double meaning of "direct" are noted in §3 |
| 23 | "Scored-once" overused and clashes with the second read | **PARTLY FIXED** | 0 occurrences in `story.yaml`. Still present in 5 rendered diagrams (m5Pipeline, auto-1, auto-2, auto-4, auto-5) and in figure titles |
| 24 | Roadmap card 1 lost the 9 + 1 count | **FIXED** | L227 |
| 25 | Roadmap `next` described the past | **FIXED** (new issue: the gate is understated) | L239 |
| 26 | Objectives has no target-vs-result table | **PARTLY FIXED** | L33–38 add a 2-column table with no thresholds |
| 27 | README L50 stale "3 origins (2 selection + 1)" | **FIXED** | README L50 now reads "10 weekly rolling origins (9 selection + …)" |
| R2-new-4 | Rendered diagrams show 0.60/0.10/0.30 and 2 origins | **FIXED** | auto-3, m5Pipeline |
| R2-new-6 | Blend loses at total level to four single arms | **FIXED** | L145, L243 |

Totals for the 27 numbered round-2 findings: **20 FIXED, 6 PARTLY FIXED, 1 STILL PRESENT.**

## New errors introduced or exposed in Wave 8

1. **Captions now contradict their figures.** Pre-existing, missed in round 2, and made worse by Wave 8 captions. The Wave 8 captions (L242–244) state 0.6211-run facts: 43.9%, four arms beat the blend at total level, 57.2%. All four committed figure JSONs still hold the 0.6161 run:
   - The ranking figure shows ensemble 0.6161, pool_storecat 0.6575 and a different bar order.
   - The per-level figure shows total 0.350 and plots only three series, so "four arms" cannot be seen.
   - The pooling-panel figure shows 57.3% and bias 3.28%.
   - The figure titles also carry retracted claims: "broadest at the aggregate levels the competition weights most" and "pooling wins at full scale".
2. **The demo and sample-series curves come from the superseded blend** (`catalog_meta.json` weights [0.6, 0.1, 0.3], recursive). The live demo hero card shows "0.6161 vs 0.8929, −31.0%". L173 links that demo directly under the 0.6211 headline.
3. **L79 claims the mid-volume series "fluctuates around quiet days".** That series has zero zero-sale days in the plotted 84 days. Pre-existing and missed in round 2.
4. **L126 "Its statistical solutions are direct"** reuses "direct" in a different sense right after L97 defined it as the multi-horizon strategy (new wording).
5. **L161 uses "the noise band" for two different bands:** ±0.0106 on the capped run and 0.000644 on the full run (new wording).
6. **L155, L159: the "0.0008" edge and "about 1.2 times" are computed from rounded values.** The true values are 0.00087 and 1.34× (new).
7. **L239: the roadmap gate "beat 0.7409 on origin 1"** is narrower than the committed rule (improve the selection-pooled WRMSSE without regressing zero-day accuracy). It also clashes with L26, "One lucky split is not enough" (new).
8. **Choppy, telegraphic sentence style** in L26, L126 and L136–145 (new).

## Top 5 remaining fixes

1. **Regenerate the four embedded figures from the committed 0.6211 metrics.** Run `build-figures-m5-full` against the current `metrics.json`, then confirm:
   - The ranking figure shows 0.6211 / 0.6219 / 0.6225 / 0.6459 in the right order.
   - The per-level figure shows a total of 0.314. Consider adding the four arms that beat the blend at total, or drop "Four learned single arms…" from caption L243.
   - The pooling panel shows 57.2%.
   - Figure titles no longer say "broadest at aggregate levels" or "pooling wins".

   These figures back L168, L152, L133 and captions L242–244. Until they are regenerated, the article contradicts itself on its headline.
2. **Re-run the catalog and demo payload with the 0.95/0.00/0.05 direct champion,** or state the mismatch in the article. This affects the sample-series figure (L90, caption L241), the demo band claim (L209), and the demo link (L173), whose hero card shows 0.6161 / −31.0% in `staticRegistry.ts`. If the re-run is deferred, add one line at L173 and L241: "the demo and sample curves come from an earlier 0.6161 blend (0.60/0.10/0.30)". Without a re-run or that disclosure, the "Live" demo is not truthful.
3. **Fix L79 and the rounding at L155, L159 and L179.**
   - L79: the mid-volume series is smooth with no zero days. Say that it "sells every day with moderate swings", or pick a different contrast.
   - L155, L159, L179: use "under `0.001`" or "`0.0009`", and "about `1.3` times". At L159, say the routed arm's band is borrowed for scale only.
   - L145: "at the three item-grain levels".
4. **Align the rendered diagrams with the test-reuse disclosure, and drop the weekly-reforecast recommendation.**
   - `m5Pipeline.ts`: change "scored exactly once" and "blend scored once" to "champion's headline window".
   - `auto-1`, `auto-2`, `auto-4`: change "scored once" to "test window".
   - `auto-5`: change "Weekly reforecast · floors + scored-once windows" to something the prose supports. The prose has no weekly-reforecast argument.
   - Also fix L239 to "Gate: beat the champion's 9-origin screen with no zero-day accuracy loss."
5. **Language pass:**
   - Merge the staccato runs (L26, L136–138, L145) into connected sentences.
   - L126: replace "Its statistical solutions are direct" with "AutoETS fits are closed-form and seed-free".
   - L161: name both noise bands.
   - Cut the quiet-day numbers to two occurrences (EDA and Limits).
   - Thin the Conclusions bullets (L177–181) so they synthesize instead of repeating Results.
   - Optional: add a Threshold column to the Objectives table and one planner-scale example.

## Ready to publish?

**No.** The prose is now substantially truthful: every number in the `story.yaml` text traces to committed files, and Wave 8 closed 20 of 27 round-2 findings. But the article embeds four figures and links a demo that all render the superseded 0.6161 run (weights 0.60/0.10/0.30, 2 selection origins, recursive catalog). The ranking chart headed "0.6161" sits directly above a caption saying "0.6211". The per-level figure cannot show the 43.9% and "four arms" claims its caption makes. The demo hero card says −31.0%. Once the figures and demo payload are regenerated (or the mismatch is disclosed) and the L79 claim is fixed, the article is close to publishable.
