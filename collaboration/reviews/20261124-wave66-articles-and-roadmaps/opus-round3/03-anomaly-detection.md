# Review round 3: 03-anomaly-detection story.yaml

- Reviewer: Claude (Opus), senior ML writer/reviewer, read-only
- Target: `projects/03-anomaly-detection/story.yaml`, **working tree** on `wave8-articles-truthfulness-2026-11-25` (HEAD `c05accd0`, uncommitted Wave 8 edits: 82 insertions, 187 deletions in the story; it now has 341 lines). Line numbers below refer to the working-tree file.
- Also changed in this round (working tree): `src/anomaly_detection/nab.py` (two figure subtitles) and the regenerated `reports/figures/nab_timelines.json` / `nab_alert_budget.json`.
- Gold template: `projects/01-rag-agent/story.yaml`
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round2/03-anomaly-detection.md` (reviewed HEAD `e69bba84`; every finding was re-checked against the working tree, not carried over)
- Evidence re-checked: `reports/nab_metrics.json` (`overall`, `series`, `no_skill`, `pa_k_2_precision_interval`, `event_rule`), `nab_sweep.json` (all 8 cells × raw/deduped/budgeted), `nab_tune.json` (`protocol`, `validation_evidence`, `selection.families`, `vs_default_sweep_budgeted`), `nab_refinement.json` (`protocol`, `adoption.reasons`, candidates), `metrics.json`, `champion_selection.json`, `detect.json`, `residual_probe.json`, `nsl_probe.json`, `data/models_tuned/*_hpo.json`, `reports/figures/*.json` (titles, subtitles, traces), `README.md`, `DESIGN.md`, `src/anomaly_detection/nab_sweep.py` (code excerpt), `apps/showcase-web/src/diagrams/detectionPipeline.ts`, `diagrams/auto/03-anomaly-detection-{1,2,3}.ts`, `apps/showcase-web/src/demos/`, `apps/showcase-api/src/showcase_api/route_manifest.json`

## Grades

| # | Dimension | R1 | R2 | R3 |
|---|---|---|---|---|
| 1 | Structure and article logic | 7 | 7 | 7 |
| 2 | Engagement and human-like narrative | 5 | 6 | 6 |
| 3 | Language quality | 5 | 6 | 6 |
| 4 | Technical depth | 8 | 8 | 8 |
| 5 | Truthfulness | 6 | 5 | 7 |
| 6 | Roadmap cards | 6 | 5 | 8 |
| 7 | Consistency with gold template | 7 | 7 | 7 |
| | **Overall** | **6** | **6** | **7** |

Wave 8 is a real truthfulness pass. All five blocking items from round 2 are fixed in the story text: the false "halves" sentence, the CI claim, the denominator contradiction, the adoption-gate wording, and the false "shipped" demo card. The IsolationForest tuning recall cost is now stated three times, and "champion" now means only the synthetic `ocsvm_tuned` in the prose. The lowest dimensions are now the prose dimensions (engagement and language, 6). Truthfulness is held at 7 by one new numeric error (L95) and by embedded diagrams that still contradict the corrected text.

## Round-2 finding status (re-verified on the working tree)

| ID | Round-2 finding | Status | Evidence (working-tree lines) |
|---|---|---|---|
| S1 | "Champion" means three different detectors | **PARTLY FIXED** | In the prose, "champion" now means only the synthetic `ocsvm_tuned` (L37, L98, L230-231, L308, L318, L320). The IsolationForest range-PR table is relabelled (L183, L187). The `range_pr` figure itself still says "champion vs a 16-seed random band", and its trace is "champion (mean over series)" (`reports/figures/range_pr.json`), so the reader sees IsolationForest called "champion" right next to L123. |
| S2 | Evaluation/Results/Conclusions repeat the same argument | **STILL PRESENT** | 66 → 35 appears at L3, L18, L22, L95, L115, L125, L133, L143, L149, L162, L294 and in L286 ("35 pages"). "Results summary" (L154-158) and "What the experiment taught" (L160-167) restate each other. |
| S3 | Cited train-only series before introducing them | FIXED | (was already fixed) |
| S4 | Cross-cell comparison in Conclusions | **FIXED** | L162 compares the rolling ensemble with rolling IsolationForest (35 vs 66, 0.533 vs 0.388, both 0.604). |
| E1 | Number stacking; no concrete on-call moment | **STILL PRESENT** | L95-98 are still four bullets of 427-480 characters each, carrying about 35 numbers. There is still no worked single-incident or single-series example. |
| L1 | Telegraphic fragments | **PARTLY FIXED** | L98 "stays a 56.9% rate check" is now a sentence. short_version L2-4 still reads "One fit per series; no-skill = 16 seeded baselines. … NAB score not reported." Wave 8 also adds a new staccato style (see new errors N3). |
| L2 | Run-on lead | FIXED | (was already fixed) |
| L3 | 1,609 → 80 read as an ensemble result | **FIXED** | L17 now says "For `IsolationForest` with rolling+residual features, that takes `1,609` raw alerts to `80` pages". L96 and key concept L305 do the same. |
| L4 | Backwards range-precision definition | **FIXED** in story | L239 reads "divides alerts inside windows by all alerts". The artifact string `nab_metrics.json → event_rule` still says "range precision over alerts outside windows" (source fix, not a story defect). |
| L5 | Repetition counts | **STILL PRESENT** | "1,609" appears 9 times, "66" 14 times, "35" 15 times, "0.604" 13 times. |
| L6 | "face budget" undefined | **FIXED** | It is now "nominal `2%` budget" (L129). |
| T1 | 0.527 vs 0.512 not reconciled | **FIXED** | L210 explains the two artifacts and aggregations. |
| T2 | IF tuning omits recall cost | **FIXED** | L97, L164, L206: 0.604 → 0.500 and 0.562 → 0.479. These match `vs_default_sweep_budgeted` (Δrecall −0.104 / −0.083). |
| T3 | k-NN distance vs "tight cluster" | **FIXED** | L74 now says the gap "indicates sparseness, not a tight cluster" and attributes the LOF failure to even spacing (DESIGN L75-77). |
| TR1 | "miss rate roughly halves" | **FIXED** | L143: 65.3% → 44.7%, about −32% relative, "fewer false alarms, not a halving of missed incidents". The arithmetic checks: (0.653 − 0.447)/0.653 = 0.315. |
| TR2 | CI "spans the no-skill upper edge" | **FIXED** | L167 "lies wholly above the no-skill band [0.063, 0.105]". |
| TR3 | Train-only series excluded vs counted as zero | **PARTLY FIXED** | The story is now consistent: L62, L70, L240-241, L309 all say they count as zero, matching `nab_tune.protocol.aggregation`, `nab_refinement.protocol.aggregation`, and the arithmetic 8.75/12 = 0.729. **But the diagram embedded at L59 (`auto-03-anomaly-detection-2.ts`) still labels that branch "Excluded, not misses" (edge "3 all-train"), and `detectionPipeline.ts` (embedded at L11) still says "3 all-train series are excluded, not scored as misses."** README L46-47 says "excluded from aggregates". The page now contradicts itself between diagram and prose. |
| TR4 | "twenty- to thirty-fold" | **FIXED** | It is `20–33×` everywhere (L96, L125, L133, L163). The measured range is 20.1-33.1×. |
| TR5 | Tune-surface caption | FIXED | (still accurate, L340) |
| TR6 | "sub-0.1 gains are noise" | FIXED | (still accurate, L158) |
| TR7 | nyc_taxi "the hardest series" | **FIXED** | L139 "the only displayed series with a missed window". This is verified: the six panels are 24ae8d, 8c0756, nyc_taxi, machine_temperature, occupancy_t4013, speed_7578, and only nyc_taxi has `events_missed` 1. |
| TR8 | False "shipped" demo card | **FIXED** | The card is replaced by "Publish the exact alert ledger" (L298-300). `nab_sweep.json`, `nab_tune.json`, and `nab_refinement.json` are all tracked in git, so "shipped" is true. |
| TR9 | Unsourced "TSB-AD VUS-PR is the modern reference" | **FIXED** | The claim is removed. The card is now a gate (L301-303). |
| TR11 | HPO 0.126 vs selection 0.151 | **FIXED** in story | L98 and L318 label 0.126 as the HPO objective, distinct from selection PR-AUC. The `hpo_importance` figure subtitle still reads "best val PR-AUC 0.126" (artifact note). |
| R1 | Card 2 detail repeats title | **FIXED** | L294 restores the numbers (69 chars). |
| R2 | Card 3 "fails precision gate" | **FIXED** | L297 "Fusion fails coverage at 14/17 or 15/17; calibration fails precision." This matches `adoption.reasons`. |
| R4 | Card 5 not a gate | **FIXED** | L303 "Gate: compare VUS-PR with the 16-seed band…". |
| G1 | Plain-terms length/filler | FIXED | (all still one or two sentences) |
| G2 | Transitions do not name the next artifact | **PARTLY FIXED** | L68, L84, L113, L131 name figures or cells. L20 and L147 still name only the next idea. |
| R2-new | key_concepts "transferring test evaluation" gate | **FIXED** | L311 "adoption needs +0.05 on validation and exactly one test evaluation, with transfer checked rather than assumed". |
| R2-new | L105 comparator switch (untuned vs tuned IF) | **FIXED** | L98 now compares against tuned IF on both splits (0.1330 val, 0.1208 test, `metrics.json`). |
| R2-new | "cap" used for the score threshold | **STILL PRESENT** | L91 "at a fixed `2%` cap". Elsewhere "cap" is the 24 h page limit (L17, L163, L209). |
| R2-new | Mixed line wrapping | **STILL PRESENT** | L26-30, L42-50, L171-185, L208-209, L219-281 are hard-wrapped. L74 (590 chars), L95-98, L123-125, L156-158, L167 are single long lines. |
| R2-new | "Swapping one detector barely helps" | **FIXED** | Removed. |
| R2-new | "at a small recall cost" | **FIXED** | It now states 0.13-0.25 (L125, L133, L163). |
| R2-new | "Rank blending wins the sweep" heading unsupported by minute PR-AUC | **PARTLY FIXED** | The heading at L95 is now correct ("wins on budgeted event scoring, not minute ranking"). The rewrite introduced a wrong range in the same bullet (N1). |
| R2-new | `nab_alert_budget` subtitle said "per detector family" | **FIXED** | `nab.py` L632 and the regenerated JSON now say "IsolationForest only: one curve per NAB group". |

**Tally: 37 findings (29 from round 1 carried into round 2, plus 8 new in round 2). 27 fixed, 5 partly fixed (S1, L1, TR3, G2, PR-AUC heading), 5 still present (S2, E1, L5, "cap", line wrapping).**

## New errors introduced by Wave 8

| ID | Line | Problem | Evidence |
|---|---|---|---|
| N1 | L95 | **Contradicted number.** The line says "Minute `PR-AUC` spans `0.515–0.577` for the ensemble". The ensemble's two cells are **0.566** (rolling_residual) and **0.577** (rolling). 0.515 is `ocsvm+rolling_residual`. Round 2's text correctly said 0.515-0.577 was the range "across all 8 cells". | `nab_sweep.json → grid.ensemble+*.overall.pr_auc` |
| N2 | L59/L62, L11/L70 | **Prose now contradicts its own diagrams.** The corrected text says the train-only series "adds zero … None disappears from the denominator". The diagram directly above it says "Excluded, not misses", and the hero diagram's NAB node says "excluded, not scored as misses". The same hero node also says "overlap-weighted range recall 0.729", but L40 and L238 define a window as caught by any single alert. (These diagrams predate Wave 8. The contradiction is new because the prose changed and the diagrams did not.) | `apps/showcase-web/src/diagrams/auto/03-anomaly-detection-2.ts` n4; `diagrams/detectionPipeline.ts` nab and scoring facts |
| N3 | L62, L63, L64, L74 | **Staccato regression.** Long sentences were broken into chains of 4-8 word sentences: "The channels are `cpu`, `mem`, and `latency_ms`. Two days contain `2,880` minutes. … Memory keeps its usual path." and "They touch no test window. Each adds zero … None disappears from the denominator." These read as machine-chunked, not human. | — |
| N4 | L98, L125, L139, L141, L143 | **Reviewer-rebuttal voice leaks into the article.** "it is not the selection metric", "reported in Training rather than hidden by the page reduction", "It is not generally the hardest series by every metric, so the claim stays limited to that visible miss", "This is fewer false alarms, not a halving of missed incidents". Each answers a review comment, not a reader question. A reader who never saw the wrong claim is left puzzled. | — |
| N5 | L74 | **Dangling reference.** "The later `LOF` failure has a different cause". The prose never reports a LOF failure. The evidence (synthetic LOF PR-AUC 0.019 = random 0.019, `metrics.json`) appears only through the Results metrics panel. | `metrics.json → lof` |
| N6 | L145 | "Neither figure establishes production readiness" is followed by reasons (adaptive thresholds, NSL-KDD, synthetic data) that come from neither of the two Results figures. | — |
| N7 | L167 | "not reported because application profiles require the official scorer" inverts README L90-91 ("it requires the official scorer with application profiles"). Not false, but garbled. | README L90-91 |

## 1. Structure and article logic: 7

The section order, the bold claims, and the `([X →](#sec-x))` transitions follow the gold. Evaluation is now properly split by figure (pr_curves → range_pr → page layer → adaptive_stream → alternatives), and L123 explicitly separates the IsolationForest sweep from the ensemble. That was the main structural fix the expert reader needed. Remaining problems:
- Results (L136-150) is now very thin: one timeline paragraph, one nyc_taxi caveat, one sentence on the budget figure, then the ensemble precision paragraph that repeats Evaluation L125. The section's real job, reading the panels, is three sentences.
- Conclusions opens with "Results summary" (L154-158), which restates Background and Training, before "What the experiment taught". The gold opens Conclusions with "What the experiment taught", then Limits, Exact numbers, Measured alternatives, Protocol. In 03, Limits sits after Protocol.
- The hero diagram (L11, `detectionPipeline.ts`) draws an IsolationForest-only, rolling-features pipeline. The three-step flow right under it (L16-18) describes rank-averaging three detectors. The reader is told to "follow the flow" that the diagram does not draw.
- `auto-03-anomaly-detection-3` (L283) ends in "Tune operating point · train-only, clear +0.05 → Budgeted page stream · deployed artifact". The article recommends the *untuned* ensemble default (L158, L286), and nothing is deployed.

## 2. Engagement and human-like narrative: 6

The opening question, the plain-terms cards, and the clearer "Tuning trades recall for fewer pages" bullet help. Two things hold the score at 6. First, there is still no concrete moment: no "on `machine_temperature`, 538 raw alerts became N pages and still caught both failures" (the per-series numbers exist in `nab_metrics.json → series`). Second, Wave 8 swapped dense sentences for staccato chains (N3) and defensive asides (N4). Neither reads like a person explaining a result.

## 3. Language quality: 6

- Fixed: the backwards precision definition, "face budget", the fragment at old L105, and "small recall cost".
- Still present: "cap" for the score threshold (L91), mixed hard-wrapping, short_version fragments (L2-4), and heavy repetition (L5).
- New: the N3 staccato, the N4 rebuttal voice, and N7.
- Minor: L224 "17 of 120 flags hit real incidents" is on the *synthetic* stream; write "injected anomalies". L232 "Roughly 30 … trials": it is exactly 30 (`*_hpo.json n_trials`). L123 "across evaluable windows": the 0.944 is a macro mean over the nine evaluable *series*. L39 "proves whether ranking beats chance" overclaims; write "tests whether".

## 4. Technical depth: 8

The same strengths as before (past-only splits, frozen quantile, explicit 12-series denominator, 16-seed band, series bootstrap, adoption gates, rank-fusion code that matches `nab_sweep.py` L108-134, an honest negative ablation). T1, T2, and T3 are now closed. That is a substantive improvement, especially T2, because the trade-off is now stated where it is decided. Two gaps keep the score from 9:
- **OCSVM tuning cost (L97).** The article does not say that OCSVM's adopted tuning buys its page reduction (87/91 → 35) with large recall losses (−0.229 / −0.125, `vs_default_sweep_budgeted`). That is the strongest single example of the article's own "tuning trades recall" thesis.
- **Unnamed model behind two "120 flags" numbers.** `threshold_sweep` (17/120, `ocsvm_tuned`) and `adaptive_stream` (18/120, `isolation_forest_tuned`, `detect.json`) both report 120 flags at 2%. L224 and L325-330 never say they are different models.

## 5. Truthfulness: 7

Re-verified as correct against committed artifacts:
- 16/17, 1,609, 0.527, 0.157, 0.729 → 0.562, 80, 0.315, 0.306, 0.107
- All five sweep-table rows; 66/35/45/122 pages; 0.553 vs 0.347; 65.3% / 44.7% / about 32%
- 20-33× (20.1-33.1); recall cost 0.13-0.25 (0.125-0.250 across the 8 cells); range-F1 rises in every cell
- Per-group table (realTraffic 188 = 44+76+42+26, realKnownCause 1,289 = 508+538+179+64, AWS 132 = 58+8+30+36; windows 5/9/3)
- 0.804 / 0.228 [0.081, 0.401]; 0.680/0.632/0.527/0.234; recall 0.944; 0.082 [0.063, 0.105]; 0.885 [0.806, 0.962]; CI [0.230, 0.811], 2,000, seed 42
- Tuning: 66 → 33 / 0.433 / 0.500 and 80 → 46 / 0.382 / 0.479; OCSVM −0.043 / +0.033; ensemble +0.0095 ≈ +0.010; 6 windows / 5 series; 0.5-8%, 6-72 h, 24 runs; +0.05; 4 families
- Ablation table and all adoption reasons; 2,546
- Synthetic: 0.1514 / 0.1330, 0.1355 / 0.1208 / 0.0194, 0.9158 / 0.1239, 0.9171, 0.5091, 0.9999 / 0.9960, k-dist 20.46 / 9.54, 5,983 rows, 1.89%, 20,000, 2,880
- NSL-KDD 0.8877 / 0.8979 / 56.9%; gamma 99.3% / 0.01313; HPO 0.1259; adaptive 120/18/102, 113/17/96, 0.150/0.159 vs 0.150/0.150, 0 of 5 chunks, 31/120
- nyc_taxi 3/4, 0.750, 0.462, 179; 897 = 58+36+179+538+42+44; the three train-only series (53ea38, 1ef3de, TravelTime_387) each have one validation window in `nab_tune.validation_evidence`, which confirms "labels only in training"

**Untraceable numbers: 0.**

Contradicted or unsupported claims:

| Line | Claim | Finding |
|---|---|---|
| L95 | "Minute `PR-AUC` spans `0.515–0.577` for the ensemble" | **Contradicted** (N1). The ensemble range is 0.566-0.577. |
| L11 + L59 (diagrams in the article) | "3 all-train series are excluded, not scored as misses" / "Excluded, not misses" | **Contradicts** L62, L70, L240-241, L309 and the artifacts' `aggregation` (non-evaluable contribute 0). |
| L11 (diagram) | "overlap-weighted range recall 0.729" | **Contradicts** the event rule at L40/L238 (≥1 alert inside). |
| L283 (diagram) | "Budgeted page stream · deployed artifact" | **Unsupported.** No demo or deployment exists (`apps/showcase-web/src/demos/` has no anomaly entry, and the route manifest has only the project page). |
| L123 + `range_pr` figure | Prose says IsolationForest; the figure title and trace say "champion" | **Label conflict** (S1 residue). |
| L224 vs L327-329 | 17/120 vs 18/120 flags at 2% with no model named | **Ambiguous.** These are different models (`ocsvm_tuned` vs `isolation_forest_tuned`). |
| L249-250 | Adoption "needs … six validation windows across five series" | **Misframed.** That is the validation evidence size (`validation_evidence`), not an adoption condition (`protocol.min_gain_to_adopt`, `test_evaluations_per_family`). |

Source-side notes (not story defects; fix them in the same pass so the evidence chain agrees): README L46-47 "excluded from aggregates"; `nab_metrics.json → event_rule` "range precision over alerts outside windows"; DESIGN k-NN table (18.9 / 8.5) vs `residual_probe.json` (20.46 / 9.54); `hpo_importance` subtitle "best val PR-AUC 0.126".

## 6. Roadmap cards: 8

| Card | Verb-first | Detail chars | Status matches reality | Note |
|---|---|---|---|---|
| Lock the event-aware evaluation contract | yes | 66 | yes | Good. |
| Halve paged load with rank averaging | yes | 69 | yes | Numbers match `nab_sweep.json`. |
| Publish the detector-challenge negative result | yes | 69 | yes | Matches `adoption.reasons`. |
| Publish the exact alert ledger | yes | 69 | yes | All three artifacts are tracked. "Ledger" is vague. Consider "Commit sweep, tuning, and refinement artifacts". |
| Evaluate TSB-AD VUS-PR | yes | 71 | yes (`next`) | Neither "TSB-AD" nor "VUS-PR" is expanded anywhere in the article, and the gate has no pass criterion. Suggested: "Gate: VUS-PR beats the 16-seed band's p97.5 on the same nine NAB series." (75 chars) |

All four round-2 roadmap findings are resolved, and there are no false "shipped" claims.

## 7. Consistency with gold template: 7

- Match: section ids, bold-claim openers, plain-terms cards, code excerpt with source link, `key_concepts`, `figure_captions`, and "Gate:" on the `next` card.
- Differences: there is still no small table in Objectives, Data, or EDA (the gold has one in each). A four-row "control → value" table in Objectives (70% split, top-2% threshold, 16 seeds, 24 h cap) would replace L37-40. Conclusions order differs from the gold (see section 1). Line wrapping is mixed, while the gold uses unwrapped lines throughout.

## Top 5 remaining fixes

1. **L95: correct the ensemble PR-AUC range.** Write "Minute `PR-AUC` is `0.566–0.577` for the ensemble and `0.515–0.574` for single models, a negligible edge." (N1, the only contradicted number in the prose.)
2. **Diagrams embedded at L11 and L59: align with the corrected denominator and event rule.** In `auto/03-anomaly-detection-2.ts`, change n4 to "Count as zero in recall" (edge "3 train-only"). In `detectionPipeline.ts`, change the nab fact to "3 train-only series count as zero in range recall" and the scoring fact to "range recall 0.729 (window caught by ≥1 alert)". Fix README L46-47 the same way. (TR3/N2)
3. **L11-18 and L283: make the diagrams match the recommendation.** Either add a "rank-average IF/LOF/OCSVM" node to the hero diagram, or say under it that it shows the IsolationForest headline path and the ensemble swaps the scoring node. In `auto-…-3`, replace "deployed artifact" with "recommended page stream", and show the ensemble default kept because the +0.010 gain is under the +0.05 margin.
4. **L62-64, L74, L98, L125, L139, L141, L143: remove rebuttal asides and rejoin staccato sentences.** Example for L74: "Each injected anomaly spikes `cpu` and `latency_ms` together while `mem` keeps its daily path. Anomalies sit about twice as far from their 20 nearest neighbours as normal rows (`≈20.5` vs `≈9.5`), so they are sparse, not clustered. `LOF` still fails (synthetic `PR-AUC` `0.019`, equal to random) because spacing inside each blob is even, so local density looks normal." Delete L139's second sentence, L125's last sentence, and L143's last sentence.
5. **Cut repetition and name the models.** Fold "Results summary" (L154-158) into "What the experiment taught" and reorder Conclusions to the gold order, so 66 → 35 drops from about 12 mentions to 5 or fewer. At L224 and in the `threshold_sweep`/`adaptive_stream` captions, name `ocsvm_tuned` (17/120) vs tuned `IsolationForest` (18/120), and write "injected anomalies", not "real incidents". In the same pass: change L91 "cap" to "threshold", L232 "Roughly 30" to "30", and L249-250 to "validated on six windows across five series", and add OCSVM's recall cost at L97.

## Ready to publish?

**No, but close.** The story text is now substantially truthful: every number traces, and all round-2 blocking claims are fixed. Two things still block publication. One prose number is wrong (L95: the ensemble PR-AUC lower bound is 0.566, not 0.515). And two diagrams rendered inside the article contradict the corrected denominator and event rule sitting next to them (L11, L59). Both are small source edits with no re-runs needed. With fixes 1 and 2 applied the article is publishable. Fixes 3-5 are quality improvements.
