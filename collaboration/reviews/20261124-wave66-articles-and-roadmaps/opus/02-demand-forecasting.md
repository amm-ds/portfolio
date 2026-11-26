# Review: 02-demand-forecasting story.yaml (Wave 6.6)

- Target: `projects/02-demand-forecasting/story.yaml` (Wave 6.6 content, committed in `18adc59d`; the working tree is clean, so the round diff is `git diff HEAD~1 -- projects/02-demand-forecasting/story.yaml`)
- Gold template: `projects/01-rag-agent/story.yaml`
- Evidence checked: `reports_m5_full/metrics.json`, `reports_m5_full/evaluation_metadata.json`, `reports_m5_full/erratic_challenger.json`, `README.md`, `DESIGN.md` (changelog 0.18.0), `src/demand_forecasting/m5_full.py`, `src/demand_forecasting/m5_track.py`
- Reviewer stance: read-only. No repository file other than this review was changed.

## What this round changed

The diff is mechanical. It renames `Business summary` to `In plain terms`, adds one "...; next, ... ([X →](#sec-x))" transition per section, makes roadmap titles imperative and drops their trailing periods, and tightens the background paragraph. It does not touch the factual errors in the body. One roadmap edit was a regression: the shipped card's detail went from "9 selection origins + 1 test", which is correct per `metrics.json`, to "origins split selection from scoring", which is vaguer. That removed the only place where the article had the origin count right.

## Grades

| # | Dimension | Grade |
|---|---|---|
| 1 | Structure and article logic | 7 |
| 2 | Engagement and human-like narrative | 6 |
| 3 | Language quality | 6 |
| 4 | Technical detail depth | 7 |
| 5 | Truthfulness | **4** |
| 6 | Roadmap cards | 7 |
| 7 | Consistency with gold template | 8 |
| | **Overall** | **6** |

### 1. Structure and article logic: 7

The order works: question, contract, data, EDA, candidates and screen, metric, ranking, conclusions. Every section now ends with a forward transition and an `In plain terms` card. Weaknesses:

- The Results section (L262–280) packs two separate challenger stories, routed spike capture and Huber, into one dense paragraph. "This arm is absent from the ranking figure" (L278–279) is ambiguous: the routed arm is also absent from the 8-candidate figure.
- Conclusions repeats the Results body almost word for word. The spike-capture bullet (L318–322) restates L269–274, and the quiet-day line appears at L117–118, L185–186, L258–259, L316–317 and L369, five times in all.
- The closing diagram sits after Limits (L380), but the section opens with "The closing diagram summarizes..." (L294) and refers to it before the reader reaches it.

### 2. Engagement and narrative: 6

The opening question is good, and the honest negative results (spike capture, Huber) are the most interesting material. The prose still anchors itself to artifacts too often: "Follow the diagram from...", "Read the diagram from left to right", "Apply the diagram's three stops", "Follow the selection diagram from left to right", "Follow the diagram from the 30,490 bottom forecasts". In Conclusions every bullet starts from the diagram: "The diagram's pooled ensemble...", "Its stability screen...", "Its scored-once windows...". This reads as template compliance rather than narrative. There is no concrete planner scenario, such as what a 0.62 vs 0.89 WRMSSE means for a store-department reorder.

### 3. Language quality: 6

- The transitions all follow one frame, "X; next, Y ([Z →])" (L23, L52, L88, L121, L190, L235, L282). The gold template varies its frames more.
- The `In plain terms` cards almost all open with "The <diagram/figure> ..." (L55, L92, L124, L193, L239, L286, L383). Several are just the headline numbers repeated, not a plain-language restatement.
- Some sentences are awkward: "Before the evaluation contract shown below, the input is the full Walmart M5 accuracy panel" (L61–62), and "Full scale prices those days into the hierarchy but does not fix them" (L259–260 and L370), which is jargon that also appears twice.
- "scored-once" appears more than 15 times. It also clashes with the article's own admission (L274–276) that the test window was read a second time.

### 4. Technical depth: 7

Strong points:
- WRMSSE is explained correctly, including the equal weight per level and the revenue weights within each level.
- The code excerpt shows that blending happens at forecast level before scoring, which experts will care about.
- The stability-screen definition is exact.
- The negative results include the bootstrap noise band.

Gaps an expert reader would notice:
- The feature list is wrong (see the Truthfulness section).
- The pooled arms run the `direct` strategy (`pooled_strategy: "direct"`, h = 1..28 separate fits), while the global fit is recursive. The article never says this, so the pooled-vs-global comparison mixes two variables: pooling and direct-vs-recursive.
- The blend has a 0.00 weight on `lgbm_pool_store` (L154, L254, L341). It is effectively a 95/5 two-model blend, yet it is called a "three-member blend" (L312) and "three pooled fits" (L193).
- Ensemble vs best single is 0.6211 vs 0.6219, a 0.0008 gap. That is about 1.3 times the routed-arm noise band of 0.00064. The single model is also better on bottom WAPE (0.7617 vs 0.7623) and on bias (+0.0177 vs +0.0222). The prose never says the ensemble's edge over the best single fit is marginal.

### 5. Truthfulness: 4

The headline numbers all trace: 0.6211, 0.6219, 0.6225, 0.6459, 0.6473, 0.6601, 0.7093, 0.8929, −30.4%, WAPE, bias, stability values, 66.6% / 57.2%, 0.314 / 0.560, 1.04–1.15 / 1.38–1.39, 2,754 / 27,736, 59.5%, 47,649,940 rows, the date range, 42,840 nodes, the 10 / 30 / 7 groups, weights 0.95 / 0.00 / 0.05, 0.6235, +0.0025, 3.9× (0.002488 / 0.000644), 0.8247 / 0.8260, 0.8683 / 0.7409, seed 42, 1,096 days, and the 28-day horizon.

The protocol description contradicts the committed metrics:

| Line(s) | Claim | Evidence | Verdict |
|---|---|---|---|
| L40–41, L80–82, L94, L194, L311–312, L330, L344, L366 | Selection uses "two earlier cutoff dates" / "2 selection origins" (2016-05-08, 2016-05-15) | `metrics.json` `origins.selection` and `evaluation_metadata.json` `split.n_selection = 9` (2016-03-20 … 2016-05-15). The stability column values (e.g. 0.0538) are population std over **9** per-origin scores | **Contradicted**. The article also says "nine origins" at L313 and L323, so it contradicts itself |
| L352 | "Origins: 3 weekly cutoffs" | `split.n_origins = 10` | **Contradicted**. Inherited from stale `README.md` L50 |
| L361 | "Runtime is 46,509 seconds" | Not found in any committed file. `evaluation_metadata.json` `runtime_seconds = 1348530.613` | **Untraceable / contradicted** |
| L187–188, L362 | "about 12.9 hours on one machine" | Only `README.md` L208/L226 say ~12.9 h. Metadata gives 1.35 M s, and the per-candidate sums (e.g. `lgbm_pool_storecat` 257,355 s) exceed 12.9 h | **Contradicted by metadata**. Reconcile or label it as wall-clock with parallelism |
| L135–136 | "7/14/21/28-day rolling means" | `m5_track._mlforecast_for`: **lags** 1/7/14/21/28; rolling means 7/28/56/84 on lag 1 (+ 7/28 on lag 7), rolling stds, expanding mean | **Contradicted** (lags conflated with rolling windows) |
| L277 | "An **earlier** Huber variant" | `erratic_challenger.json` protocol `m5_full_v1-wave34-…`; spike capture is wave 33 (`DESIGN.md` 0.18.0) | **Contradicted**. The Huber variant is the later experiment |
| L264–267 | Capped window: "the swap won its erratic quadrant against the floor" | `DESIGN.md` L762–767: on the capped window the routed win rate rose vs the **champion** (0.8449 vs 0.8395), but the gate was **already REJECTED** there (+0.0204 WRMSSE ≈ 2× noise) | **Misleading**. It implies a capped-window success that the full run then reversed |
| L226–230, L288 | Margin "broadest at aggregate levels"; "widening bars toward the top show where the win comes from" | Absolute floor − blend gap: total 0.246, store 0.257, item 0.282, item_store **0.341**. With equal weight per level, the bottom levels contribute the most WRMSSE reduction | **Contradicted in absolute terms**. True only as a relative (percentage) gap; say "relative" |
| L278–279 | Huber arm's "full-panel performance is measured and it loses" | Scored on 1 of 9 selection origins only (`n_origins_scored: 1`) | **Overstated** |
| L324 | "no bootstrap confidence intervals exist" | A paired bootstrap CI exists for the routed-vs-champion delta (`ci95` [0.00178, 0.00307]) | **Imprecise**. Should read "no bootstrap interval on the headline gap" |
| L335 (table) | Bold on `lgbm_pool_store` stability 0.0549 | `lgbm` has the lowest stability, 0.0347 | **Misleading emphasis** (also in `README.md` L96) |

Untraceable or contradicted **numbers**: 5. They are the selection-origin count (2 vs 9), the origin count (3 vs 10), 46,509 s, 12.9 h, and the 7/14/21/28 rolling windows.

### 6. Roadmap cards: 7

- Titles are verb-first, imperative, and have no periods. All details are 90 characters or fewer.
- Shipped card 1: "origins split selection from scoring" is vaguer than the pre-round "9 selection origins + 1 test", which was correct. Restore the count.
- The `next` card's title, "Find erratic gains beyond routing", names a goal, but its detail ("Huber challenger lost its only selection origin and never reached test") describes a past failure, not the next step. "its only selection origin" is also wrong: it was scored on the first of nine, then stopped. The gold template's `next` detail names a gate. Here it should name the next lever, for example "Gate: beat 0.7409 on origin 1 without zero-day loss; try …".

### 7. Consistency with gold template: 8

The `In plain terms` cards, link-arrow transitions, and roadmap form all match the template. Differences:
- The gold template puts transitions as "Next, we …". Here they come after a semicolon in one repeated frame.
- The gold template's plain-terms cards describe what was gained or what users get. Several cards here only restate figures.
- The gold template has an up-front target table in Objectives. 02 lists success criteria with no measured-result column, which would help.

## Top 5 fixes (by severity)

1. **Selection-origin count is wrong throughout**: `story.yaml` L40–41 "two earlier cutoff dates", L80–82, L94 "two past origins", L194 "at two past origins", L311–312 "two selection origins", L330 / L344 "the 2 selection origins", L352 "3 weekly cutoffs", L366 "only 2 selection origins". The committed protocol has 9 selection origins (2016-03-20 … 2016-05-15) + 1 test = 10. The stability numbers in the table are computed over 9. Fix every instance and restore "9 selection origins + 1 test" in roadmap card 1 (L399). Also flag `README.md` L50 as the stale source.
2. **Runtime is untraceable or contradicted**: L361 "Runtime is 46,509 seconds" appears in no committed file, and L188 / L362 "about 12.9 hours on one machine" conflicts with `evaluation_metadata.json` `runtime_seconds: 1348530.613`. Either cite a committed wall-clock figure and say what it measures, or drop the runtime claim.
3. **Feature list is wrong**: L135–136 "7/14/21/28-day rolling means" should read lags 1/7/14/21/28 plus rolling means over 7/28/56/84 days, rolling stds, and an expanding mean. Add that the pooled arms use the direct strategy (`pooled_strategy: direct`) while the global fit is recursive, because that confounds the "pooling beats global" reading at L250–252 and L309–310.
4. **"Gain at aggregate levels" is misstated**: L226 "The blend's margin is broadest at aggregate levels", L229–230 "The widening bars toward the top show where the win comes from", and L288 "the gain concentrated at aggregate levels". The absolute gap is largest at `item_store` (0.341 vs 0.246 at total), and every level carries equal weight. Reword to "largest *relative* cut at aggregate levels; the bottom levels still contribute most of the absolute WRMSSE reduction."
5. **Challenger narrative is inaccurate**: L277 "An earlier Huber variant" should be "A later (wave 34) Huber variant". L265–267 "the swap won its erratic quadrant against the floor" hides that the capped run was already gate-rejected (+0.0204 WRMSSE ≈ 2× noise; `DESIGN.md` L762–767). L278–279 "its full-panel performance is measured and it loses" should say it lost on 1 of 9 selection origins. Also split the two challengers into separate short paragraphs, name which arm "This arm" means, and fix the roadmap `next` detail (L411) "lost its only selection origin".

Secondary: call the blend what it effectively is, 95/5 over two fits, at L193 and L312. State that the edge over the best single fit (0.0008) is about 1.3× the measured noise band and that the single fit wins on WAPE and bias. Fix the misleading bold at L336. Change L324 to "no bootstrap interval on the headline gap". Cut the repeated quiet-day sentence down to two occurrences.
