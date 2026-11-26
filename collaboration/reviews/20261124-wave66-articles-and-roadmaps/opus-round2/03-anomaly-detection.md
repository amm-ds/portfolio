# Review round 2: 03-anomaly-detection story.yaml

- Reviewer: Claude (Opus), senior ML writer/reviewer, read-only
- Target: `projects/03-anomaly-detection/story.yaml` at HEAD (last touched in `e69bba84`; the working tree matches HEAD). Line numbers below refer to this version, which has 446 lines. The round-1 version had about 540.
- Gold template: `projects/01-rag-agent/story.yaml`
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/03-anomaly-detection.md`
- Evidence re-checked: `reports/nab_metrics.json`, `nab_sweep.json`, `nab_tune.json` (`selection.families`, `vs_default_sweep_budgeted`), `nab_refinement.json`, `metrics.json`, `champion_selection.json`, `detect.json`, `residual_probe.json`, `nsl_probe.json`, `data/models_tuned/ocsvm_hpo.json`, `reports/figures/*.json` (titles, annotations, traces), `params.yaml`, `README.md`, `DESIGN.md`, `apps/showcase-web/src/demos/`, `apps/showcase-api/src/showcase_api/route_manifest.json`

## Grades

| # | Dimension | Round 1 | Round 2 |
|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 |
| 2 | Engagement and human-like narrative | 5 | 6 |
| 3 | Language quality | 5 | 6 |
| 4 | Technical depth | 8 | 8 |
| 5 | Truthfulness | 6 | 5 |
| 6 | Roadmap cards | 6 | 5 |
| 7 | Consistency with gold template | 7 | 7 |
| | **Overall** | **6** | **6** |

The lowest dimensions are Truthfulness (5) and Roadmap (5). The e69bba84 pass tightened the prose and the plain-terms cards. It left in place almost every factual defect that round 1 reported, including the false "shipped" demo card. Round 1 scored Truthfulness 6 on the assumption that these defects would be fixed. They survived a revision pass, so this round scores it lower.

## Round-1 finding status

| ID | Round-1 finding | Status | Current evidence |
|---|---|---|---|
| S1 | "Champion" means three different detectors | **STILL PRESENT** | It means IsolationForest at L139, L145, L279, L283 (range-PR 0.804 comes from `nab_metrics.json`, which is IF). It means the ensemble at L255, L361-362, and L398. It means synthetic `ocsvm_tuned` at L330 and L425. The `nab_timelines` figure title still says "champion alerts" for IF alerts. |
| S2 | Evaluation, Results, and Conclusions repeat the same argument | **STILL PRESENT** | 66 → 35 appears at L3, L18, L22, L103, L122, L152, L177, L201, L385. 2,546 appears at L169, L212, L314. 14/17 appears at L171, L214, L252. Results L205-215 restates Evaluation L166-172. |
| S3 | L8 cited "the three train-only ones" before introducing them | **FIXED** | L9 no longer mentions them. They are first introduced at L64. |
| S4 | Results compares across cells (ensemble rolling vs IF rolling+residual, "Recall is higher") | **STILL PRESENT** | L234-237 is unchanged: "35 pages … versus 80 pages … Recall is higher at 0.604 versus 0.562." This breaks the like-for-like rule the article states itself at L152 and in README L95-99. |
| E1 | Number stacking, no concrete on-call moment | **STILL PRESENT** | L102-105 packs about 30 numbers into 4 bullets. There is still no worked example of a single incident or page. |
| L1 | Telegraphic fragments | **PARTLY FIXED** | L18 is now full sentences. L105 ("`NSL-KDD` stays a `56.9%` rate check") and short_version L2-4 ("One fit per series; no-skill = 16 seeded baselines.") are still fragments. |
| L2 | L8 unwrapped bold lead runs into a dense clause | **FIXED** | The bold question now sits on its own line (L8). |
| L3 | 1,609 → 80 reads as an ensemble result | **STILL PRESENT** (moved) | L16-17 describes the ensemble flow ("Average their ranks on rolling features"), then "Cap pages … (`1,609` -> `80` pages)". Those counts belong to IF rolling+residual. The ensemble rolling cell is 1,157 → 35 and the ensemble rolling+residual cell is 1,003 → 45 (`nab_sweep.json`). L103 also attaches "(1,609 -> 80 pages …)" to "Every cell" without naming the cell. |
| L4 | "Range precision is measured over alerts outside windows" reads as backwards | **STILL PRESENT** | L338. README L82 defines it correctly: "alerts inside windows ÷ all alerts". |
| L5 | Repetition counts | **STILL PRESENT** | "1,609" appears 10 times (11 in round 1). "66" appears 11 times. |
| L6 | "face budget" / "face value" never defined | **STILL PRESENT** | L169, L212, L249. |
| T1 | 0.527 (range-PR precision at 2%) vs 0.512 (`precision@budget`) not reconciled | **STILL PRESENT** | L309 defines `precision@budget` but does not say why it differs from L143/L256/L288's 0.527 (`nab_metrics.pa_k_2` macro vs `nab_refinement.precision_at_budget`). |
| T2 | IF "transfer" omits its recall cost | **STILL PRESENT** | L104 and L228/L242 report 66 → 33 and 80 → 46 pages but not the recall drop: 0.604 → 0.500 and 0.562 → 0.479 (`nab_tune.json → vs_default_sweep_budgeted`, `delta_range_recall` −0.104 / −0.083). |
| T3 | k-NN distance does not support "tight cluster" | **PARTLY FIXED** | L78 adds "can look locally normal to `LOF`". The "so" still derives this from a *larger* k-distance (20.5 vs 9.5), which signals sparseness. The real argument, uniform within-blob spacing that gives LOF ≈ 1, is in DESIGN.md L75-77 and is not in the article. |
| TR1 | "Pages still miss incidents about half the time, but that miss rate roughly halves" | **STILL PRESENT** | L200-201, verbatim. Range precision 0.347 → 0.553 means the outside-incident share falls from 0.653 to 0.447, about −32%, not half. These are also false alarms, not missed incidents: recall is unchanged at 0.604. |
| TR2 | "The interval spans the no-skill band's upper edge" | **STILL PRESENT** | L259. The CI [0.230, 0.811] lies entirely above the matching no-skill precision band [0.063, 0.105] (`nab_metrics.json → no_skill.pa_k_precision`). |
| TR3 | Train-only series "leave the evaluation rather than count as misses" vs counted as zero | **STILL PRESENT** | L64 contradicts L339-340 and the artifacts (`aggregation`: "non-evaluable contribute 0"). The arithmetic confirms the zeros count: 8.75 / 12 = 0.729. |
| TR4 | "twenty- to thirty-fold" vs the measured 20.1-33.1× | **PARTLY FIXED** | L103 is now "`20–33×`" (correct). L150 and L239 still say "twenty- to thirty-fold". |
| TR5 | Tune-surface caption implied only IF clears the 0.05 margin | **FIXED** | L445 now reads "clears the 0.05 margin and transfers to test". That is accurate because OCSVM clears but does not transfer. It is still easy to misread; see the new finding on key_concepts L415. |
| TR6 | "sub-0.1 gains are noise" undermined the +0.081 IF adoption | **FIXED** | It is replaced by the specific "`+0.010` across `6` validation windows is noise" (L230). |
| TR7 | "`nyc_taxi` panel keeps the hardest series visible" | **STILL PRESENT** | L188. ambient_temperature is worse on raw range-F1 (0.005 vs 0.107), PR-AUC (0.233 vs 0.462), and range-PR area (0.026 vs 0.635). nyc_taxi is only the series with a missed window. |
| TR8 | Roadmap "showcase demo replays committed alerts" (shipped) | **STILL PRESENT** | L397-399. `apps/showcase-web/src/demos/` contains only `churn-sandbox`, `forecast-workbench`, `workbench`, `charts`. The only 03 entry in `route_manifest.json` (L25) is the project page path. No anomaly demo exists. |
| TR9 | "TSB-AD VUS-PR is the modern reference score" has no source | **STILL PRESENT** | L402. No citation in README or DESIGN. |
| TR11 | Tuned OCSVM "best validation PR-AUC 0.126" vs "validation PR-AUC 0.151" | **STILL PRESENT** | L423 (0.126 is `ocsvm_hpo.json best_value`, the HPO objective) vs L105/L425 (0.1514 is `champion_selection.json`). Two "validation PR-AUC" values for one model, with no explanation. |
| R1 | Card 2 detail dropped its numbers and repeats the title | **STILL PRESENT** | L393: "Like-for-like paged load halves at equal recall." |
| R2 | Card 3 says "No fusion clears the precision gate" | **STILL PRESENT** | L396. The fusions *pass* precision (0.650, 0.637 > 0.512) and fail **coverage** (14/17, 15/17). Only calibration fails precision (`nab_refinement.json → adoption.reasons`). |
| R4 | Card 5 is a claim, not an exit gate | **STILL PRESENT** | L402. The gold card format is "Gate: …". |
| G1 | Plain-terms cards ran to several sentences; filler "Every reported result is reproducible" | **FIXED** | All 8 cards are one sentence, and the filler is gone. |
| G2 | Transitions name the next idea but not the next artifact | **PARTLY FIXED** | L70-71, L89-91, and L120 now name figures. L20, L174-175, and L217-219 still do not. |

Tally: 29 distinct round-1 findings. **20 still present, 4 partly fixed, 5 fixed.** Round-1 items TR10, TR12, and R3 duplicate T1, T3, and TR8 and are counted once.

## 1. Structure and article logic: 7

The section order is sound, every section opens with a bold claim, and the transitions follow the gold `([X →](#sec-x))` pattern. The three-step flow at L14-18 is a good addition. Remaining problems:
- S1 (detector identity) is the main obstacle for an expert reader. At L139-146 "the champion's range-PR area 0.804" is IF. Ten lines later (L151-153) the subject is the ensemble, with no signal to the reader that the detector has changed.
- Results (L198-215) is mostly a second pass over Evaluation. The "panels do not show production readiness" paragraph repeats calibration, fusion, NSL-KDD, and adaptive results that appear twice elsewhere.
- L102 claims "Rank blending wins the sweep" but backs it with minute PR-AUC ranges (0.515-0.577 vs 0.515-0.574), and on that metric the ensemble's edge is 0.003. The win is in budgeted range-F1 and pages. The bullet's evidence does not support its heading.

## 2. Engagement and human-like narrative: 6

Better than round 1. The opening question, the three-step flow, and the one-sentence plain-terms cards make the article easier to scan. The nyc_taxi paragraph (L188-191) is the only concrete case. The training bullets (L102-105) and the Conclusions summary (L228-230, single lines of 469 and 548 characters) are still walls of decimals. One worked example would do more than any rewording, for instance "on machine_temperature, budgeting cut 538 alerts to N pages and still caught both failures".

## 3. Language quality: 6

- Fixed: the L12 fragment and the run-on lead.
- Remaining: the backwards precision definition (L338), the undefined "face budget" (L169, L212, L249), and fragments at L105 and in short_version.
- New: line wrapping is now mixed. Some paragraphs are hard-wrapped at about 75 characters (L126-172, L181-219), while others are single 250-550-character lines (L37, L64, L68, L78, L102-105, L228, L230). The gold uses unwrapped lines throughout. Pick one style.
- New: L98 "at a fixed `2%` cap" uses "cap" for the score threshold, while the rest of the article uses "cap" for the 24 h page limit.
- New: L122 "Swapping one single detector for another barely helps". Single-family budgeted range-F1 spans 0.200-0.388, a 1.9× spread, so the statement holds only for minute PR-AUC. L177 "at a small recall cost" describes a 0.167 absolute (23% relative) recall loss.

## 4. Technical depth: 8

The same strengths as round 1: past-only splits, frozen quantile, explicit recall denominator, 16-seed band, series bootstrap, adoption gate, rank-fusion code, and an honest negative ablation. The gaps from round 1 (T1, T2, T3) are all still open. T2 matters most, because the article's closing trade-off is "on-call capacity versus recall" (L154) and it then reports the IF tuning without the recall it costs.

## 5. Truthfulness: 5

Re-verified as correct against the artifacts: 16/17, 1,609, 0.527, 0.157, 0.729 → 0.562, 80, all five sweep-table rows, 0.515-0.577 / 0.515-0.574, 0.688-0.750, 1,003-3,586, 20-33× (L103), recall cost 0.125-0.25, the per-group table, 0.804 / 0.228 [0.081, 0.401], 0.680/0.632/0.527/0.234, recall 0.944, 0.082 [0.063, 0.105], 0.885 [0.806, 0.962], bootstrap [0.230, 0.811] (2,000, seed 42), ≈6× (0.527/0.082 = 6.4), 66 → 33 / 0.433, 80 → 46 / 0.382, OCSVM −0.043/+0.033, +0.010, 6 windows across 5 series, ablation table, 0.1514/0.1330, 0.1355/0.1239/0.0194, 0.9158/0.9171, 0.9999/0.9960, k-dist 20.46/9.54, NSL-KDD 0.8877/0.8979/56.9%, 5,983 rows / 1.89%, 20,000 / 2%, 2,880 minutes, 897 alerts (58+36+179+538+42+44), nyc_taxi 3/4, 0.750, 0.462, 179, adaptive 120/18/102 and 113/17/96, 0.150/0.159 and 0.150/0.150, 17/120 = 14.2%, 31/120 chunks (README L152, DESIGN L203, `adaptive_drift_events` 31), gamma 99.3% / 0.01313, HPO best 0.1259, 30 TPE trials, 2.4× / ~40-minute / 0.049 (DESIGN L121-122), Lyu 2026 (README L71), owner decision 2026-11-18 (README L93), grids 0.5-8% / 6-72 h, 24 runs per point.

**Untraceable numbers: 0.** Every decimal resolves to a committed file.

Contradicted or unsupported claims:

| Line | Claim | Finding |
|---|---|---|
| L200-201 | "Pages still miss incidents about half the time, but that miss rate roughly halves" | **Contradicted** (round 1 TR1). The outside-incident share falls 0.653 → 0.447 (−32%), and these are false alarms, not misses. |
| L259 | "The interval spans the no-skill band's upper edge" | **Contradicted** (TR2). [0.230, 0.811] lies wholly above [0.063, 0.105]. |
| L64 vs L339-340 | Train-only series "leave the evaluation rather than count as misses" | **Internal contradiction** (TR3). The artifacts count them as 0 in range recall. |
| L150, L239 | "twenty- to thirty-fold fewer pages" | **Contradicted range** (TR4). The measured range is 20.1-33.1×, and L103 already says 20-33×. |
| L17 | "(`1,609` -> `80` pages)" inside the ensemble flow | **Misattributed** (L3). These are IF rolling+residual counts. |
| L234-237 | "Recall is higher at 0.604 versus 0.562" | **Cross-cell comparison** (S4). The like-for-like IF rolling recall is also 0.604. |
| L188 | "the hardest series" | **Unsupported** (TR7). |
| L338 | "Range precision is measured over alerts outside windows" | **Misleading definition** (L4). |
| L415 (new) | key_concepts: "adoption needs +0.05 and one transferring test evaluation" | **Contradicted.** The gate is +0.05 on validation plus exactly one test evaluation. Transfer is not a condition: OCSVM is `adopted: true` in `nab_tune.json → selection.families.ocsvm` and then fails on test (−0.043 on rolling). |
| L105 (new, minor) | "tuned `OCSVM` leads val `PR-AUC` (`0.1514` vs `0.1330`) and test `PR-AUC` (`0.1355` vs `0.1239` untuned `IsolationForest`…)" | **Comparator switch.** 0.1330 is *tuned* IF on validation. On test the article compares against *untuned* IF (0.1239), although tuned IF is 0.1208 (`metrics.json`). The claim holds either way, but the comparator should stay the same. |
| L423 vs L425 | Validation PR-AUC 0.126 vs 0.151 for tuned OCSVM | **Unreconciled** (TR11). 0.126 is the HPO objective (`ocsvm_hpo.json best_value`), and 0.151 is champion selection. Label them differently. |
| L397-399 | "The showcase demo replays committed alerts" (shipped) | **Untraceable / false** (TR8). No anomaly demo exists in `apps/showcase-web/src/demos/`. |
| L402 | "TSB-AD VUS-PR is the modern reference score for this task" | **Untraceable in-repo** (TR9). It is a plausible external claim but needs a citation or softer wording. |

Artifact note (not a story defect): the `nab_alert_budget` figure subtitle says "one curve per detector family", but its traces are NAB groups for IF only. The story caption (L441) is correct. The figure's own subtitle should be fixed at the source.

## 6. Roadmap cards: 5

| Card | Verb-first | Detail length | Status matches reality | Note |
|---|---|---|---|---|
| Lock the event-aware evaluation contract | yes | 62 | yes | Good. |
| Halve paged load with rank averaging | yes | 48 | yes | The detail repeats the title. Restore the numbers: "Rolling cell: 66 → 35 pages at recall 0.604; range-F1 0.388 → 0.533." (70 chars) |
| Publish the detector-challenge negative result | yes | 70 | yes | "No fusion clears the precision gate" is wrong: fusion fails coverage. Use "Fusion fails coverage (14/17); calibration fails precision; detector stands." (77 chars) |
| Ship the champion behind frozen thresholds | yes | 72 | **no** | No demo exists. Set the status to `next` with "Gate: showcase demo replays committed ensemble alerts at (2%, 24 h)." Otherwise delete the card. |
| Re-run the headline on TSB-AD VUS-PR | yes | 59 | yes | Not a gate. Use "Gate: VUS-PR vs 16-seed band on the same nine NAB series." |

None of the four round-1 roadmap findings were addressed.

## 7. Consistency with gold template: 7

- Fixed: all plain-terms cards are now one sentence with a concrete number, matching the gold.
- Section ids, figure lists, the `key_concepts` and `figure_captions` blocks, and the transition pattern all match.
- Differences: the gold places a small table in Objectives, Data, and EDA (targets, question sets, corpus stats), but 03 has no table before Conclusions. A short "control → value" table in Objectives (70% split, 2% budget, 16 seeds, 24 h cap) would match the gold and replace prose. The gold's Conclusions opens with "What the experiment taught", while 03 opens with a "Results summary" that restates numbers already given. The line-wrapping style is mixed (see section 3). Gold roadmap details use "Gate: …" for `next` cards, and 03 does not.

## Top 5 remaining fixes (by severity)

1. **L397-399: remove or downgrade the false "shipped" demo card.** No anomaly demo exists under `apps/showcase-web/src/demos/`. Set the status to `next` with a gate, or delete the card. While editing the roadmap, fix L396 (fusion fails *coverage*, not precision) and L402 (make it a "Gate: …" detail).
2. **L200-201: replace the false "halves" sentence.** Suggested: "About 45% of ensemble pages still land outside incidents, down from 65% for IsolationForest on the same rolling cell, while pages fall 66 → 35 at equal recall."
3. **L259: fix the contradicted CI claim.** Suggested: "The interval sits wholly above the no-skill precision band [0.063, 0.105] but is wide across nine series, so read it as an alert-budget dial, not proof of unattended paging."
4. **L64 (with L415): resolve the denominator contradiction and the adoption-gate misstatement.** At L64, write "have every label inside the training span, so they touch no test window and count as zero in range recall". At L415, write "adoption needs +0.05 on validation and exactly one test evaluation; transfer is then checked, not assumed".
5. **L17, L139-145, L234-237, L150/L239: name the detector and stay like-for-like.** At L17, write "IsolationForest on rolling+residual features: `1,609` → `80` pages". At L139/L145, write "IsolationForest's range-PR area". Rewrite L234-237 as "ensemble 35 pages / range-F1 0.533 vs IsolationForest 66 / 0.388 on the same rolling cell, both at recall 0.604". Change "twenty- to thirty-fold" to "20-33×". Lower-severity items that should go in the same pass: L338 (precision definition), L104/L228 (state the IF tuning recall cost, 0.604 → 0.500 and 0.562 → 0.479), and L188 ("the only series with a missed window").

## Ready to publish?

**No.** The article still contains three factually contradicted claims (L200-201, L259, L64), a roadmap card that marks a non-existent demo as shipped (L397-399), and an incorrect description of the adoption gate (L415). All but the last were reported in round 1 and survived the e69bba84 revision. Every number traces, so the fixes are wording changes, not re-runs. One focused pass on the five items above should be enough to publish.
