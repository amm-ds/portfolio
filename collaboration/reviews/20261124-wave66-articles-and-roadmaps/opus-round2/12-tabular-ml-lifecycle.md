# Round-2 review: 12-tabular-ml-lifecycle story.yaml

- Reviewer: Claude (Opus), read-only senior ML writer/reviewer pass, round 2
- Target: `projects/12-tabular-ml-lifecycle/story.yaml` at HEAD (464 lines; last changed in `e69bba84`)
- Gold template: `projects/01-rag-agent/story.yaml`
- Prior round: `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus/12-tabular-ml-lifecycle.md` (reviewed the `18adc59d` version)
- Evidence re-checked (committed only): `reports/metrics.json`, `reports/results.md`, `reports/evaluation_metadata.json`, `reports/figures/*.json` (Plotly `bdata` decoded), `data/feature_selection.json`, `params.yaml`, `README.md`, `DESIGN.md`, `src/tabular_ml_lifecycle/{features,figures,mlp}.py`. `reports/train_runs.json` and `reports/dq_report.md` exist locally but are gitignored (`reports/.gitignore`), so they do not count as committed evidence.
- Line numbers below refer to the current HEAD file.

## What changed between rounds

`git diff 18adc59d e69bba84 --word-diff` shows the round rewrote the background section (new question-style lead, a three-bullet "Follow the lifecycle" list), rewrote every "In plain terms" card in plainer language, and wrapped many numbers and acronyms in backticks. No number, claim, caption, or roadmap card that round 1 flagged was changed. Almost all round-1 findings therefore carry over, and the rewrite added three new problems (see §5, "New in this round").

## Grades

| # | Dimension | Round 1 | Round 2 |
|---|---|---|---|
| 1 | Structure and article logic | 7 | 6 |
| 2 | Engagement and human-like narrative | 6 | 6 |
| 3 | Language quality | 6 | 6 |
| 4 | Technical depth | 8 | 7 |
| 5 | Truthfulness | 5 | 4 |
| 6 | Roadmap cards | 6 | 5 |
| 7 | Consistency with gold template | 8 | 7 |
| | **Overall** | **6** | **5** |

The lower round-2 grades reflect findings round 1 missed (the feature-pruning claim, §5) and new contradictions introduced by the plain-terms rewrite, not a regression in already-correct text.

## 1. Structure and article logic: 6

The arc is still sound: question, checks, data, EDA, training ladder, measurement chain, ledger, conclusions. The new background (L16-30) is a clearer opening than the old one.

Problems that remain:
- **Duplication.** The candidate table appears twice: rounded at L292-298 and at two decimals at L345-351. The floor-gap triple "[52.5, 63.1] / [44.2, 71.8] / [38.8, 73.4]" appears in the headline (L2-4), short_version (L12), L235-237, L272-273, L301-302, L316, L360-361 and the `bootstrap_ci` caption (L463), eight times in all. The L304 transition still promises "the exact tables" again.
- **Weak EDA-to-metrics link.** L123 "These patterns set four judging rules". Only the MAPE floor follows from the EDA. MAE-first and the naive floor are design choices.
- **Non sequitur.** L275-277: "A dropout-off row reaches 32.1, about 2 rentals better. The pre-registered configuration … therefore stands." A better variant is not a reason to keep the shipped one. The reason is the protocol.
- **Champion contradiction.** L213 "The ladder picks the champion" versus L356-357 "without a champion label" and `metrics.json.validation_tie_interval.interpretation` ("not a proven champion").
- **Conclusions order differs from gold.** Gold runs What the experiment taught → Limits → Exact numbers → Measured alternatives → Protocol. Here it is Results summary → What the experiment taught → Exact numbers → Protocol → Limits, and the "Results summary" block (L311-321) repeats the Results section.

## 2. Engagement and human-like narrative: 6

The new background question (L16) and plain-terms cards read more naturally. The body is unchanged, though: it still reads as a figure-reading manual ("Read `…` as a sequence" L34, "Follow `…`" L73, L221, "In `…`, compare" L108, L233, "look for" L117, L274). The residual findings (L241-245) are still the most interesting part of the article and still get three flat sentences. The article never tells the reader that the large L242 over-forecast is the Christmas week. The training section still reads like a hyperparameter list.

## 3. Language quality: 6

- Six of seven transitions still use the "X; next, Y ([Z →])" formula (L65, L100, L133, L213, L257, L304). The gold transitions name the table or chart the reader is about to see and vary the sentence shape.
- Nested definitions remain: L170-172 ("an 8-dimensional embedding turns the raw hour into eight learned numeric values beside standardized features, which are rescaled to comparable ranges"); L55-57 defines regularization through overfitting and then defines overfitting.
- One concept, four names: "statistical dead heat" (L280), "effectively tied" (L332), "a tie" (L353), "negligible" (L406).
- L224-225 "the served-model row — the one candidate validation selected to serve — with the same floor row" is still hard to parse.
- New: backticks are applied inconsistently. `83.2` is code-formatted at L17 but 83.2 is plain at L234. `MAE` is code-formatted in most places but plain in L187, L277, L343, L364. "`95%` `CI`" (L235, L272, L301) splits one phrase across two code spans. Pick one convention.
- Fixed: the round-1 ambiguity "a neural network for tables trained in PyTorch" is gone.

## 4. Technical depth: 7

Still strong: the paired hourly plus 24h/168h block bootstrap, the scope note that it "does not measure selection variance" (L228, L319-320), the validation tie interval, the positional-lag disclosure, the checkpoint/restore excerpt, and the leakage drop of `casual`/`registered`.

Gaps that remain: the MLP architecture is not stated (hidden dims 64/32, lr 1e-3, batch 256, max 150 epochs, patience 10, Huber δ 1.0, all in `params.yaml` L22-32). The LightGBM search space is not stated. The ablation has no interval, yet the text makes "within noise" claims about it. Permutation importance uses a ridge probe for a nonlinear winner, and this is not flagged.

New: the feature-selection description is wrong about which member of the correlated pair the rule keeps (see §5). This is a technical error in the article and a bug in the code.

## 5. Truthfulness: 4

Traced correctly: 83.2/25.4 (metrics.json 83.199/25.432), gain 57.8 (57.77 is the metrics.json difference), the three CIs (README, DESIGN, results.md), the five-row table at one decimal (README L64-70), tie interval −0.18 [−1.71, +1.21] (metrics.json), test MAE gap 0.06 and RMSE 39.3 vs 40.2, MI 0.89/0.76/0.71 (feature_selection.json), r 0.987 (pruned_pairs r = 0.9873) and r 0.99 (correlation_heatmap 0.9877), 15 of 16 features, 14,523/1,344 rows, 165 missing hours, 2% DQ budget, 26 DQ checks (README L28, DESIGN L42), peaks at 08h and 17h, the 4h minimum, residual maxima 58.8 / 50.5 / 39.1-40.2, 32.13 ablation argmin (ablation_dotplot.json). Round 1 listed "best validation MAE 34.397" as untraceable; it is in `learning_curves.json` (LightGBM at fraction 1.0 = 34.3968), so that item is withdrawn.

### Contradicted by committed files (carried over from round 1, all unfixed)

| Line | Claim | Evidence |
|---|---|---|
| L249-250; caption L458-459 | "The points remain centered on zero, so the figure shows no global bias to correct"; "without global bias" | `residual_vs_fitted.json`: mean residual (actual − fitted) is **+9.2** over 1,344 points (median +2.8); **+28.6** for fitted 300-600. The model under-forecasts on average. The figure's own subtitle repeats the error (figure-side). |
| L242 | "Spring rush hours (7-8h, `17h`) are over-forecast by up to 59" | Test window is the final 8 weeks of 2012 (Nov-Dec). `residual_heatmap.json` has only "spring" and "winter" rows with data. "Spring" is UCI season code 1 (`figures.py` uses `SEASON_LABELS`), which in this window covers only about Dec 21-31, the holiday week. |
| L109; caption L441-442 | "Winter is flatter and lower"; "winter peaks are lower" | `rentals_by_hour_season.json`: the lowest panel is **"spring"** (peak 264); "winter" peaks at 486, close to summer's 519. Same UCI label quirk; the prose contradicts the figure as labelled. The figure subtitle has the same error. |
| L176-177 | "keeps the best checkpoint among 47 epochs" | `mlp_loss_curves.json`: **57** epochs ran; best epoch 47. |
| L187; L334-335 | "Dropout and weight decay sit within noise"; "smaller dropout and weight-decay differences" | `results.md` ablation: dropout-off improves validation MAE by **2.1** in both early-stopping-on pairs (34.2→32.1, 34.3→32.2). Early-stopping-off costs +1.0, +0.5, +3.6, +2.6 across the four pairs. Dropout is not "within noise", and no interval exists to support the phrase. Weight decay alone (≤0.1) really is negligible. |
| L290 | "run ids in `reports/metrics.json`" | `metrics.json` has no run ids, only `_meta.git_sha`. |
| L387 | "train stage `44.3 s` plus evaluate `14.7 s`" | `evaluation_metadata.json`: `train_s` 44.377 (44.4), `evaluate_s` **13.306**. |
| L213; roadmap L416 | "The ladder picks the champion"; "Serve the validation-tied MLP champion" | L356-357 and `metrics.json` say no champion label. |
| Caption L455-456 vs figure | Caption: "Red means over-forecast" | Caption matches the RdBu scale (zmid 0, negative = red). The committed figure subtitle says "Red = the model under-forecasts there". Figure-side bug; README L101-102 repeats it. |

### New in this round (missed in round 1 or introduced by `e69bba84`)

| Line | Claim | Evidence |
|---|---|---|
| L146-147; caption L447-448; key concept L434-435 | "Grey stems mark fields pruned as the lower-MI member of a correlated pair" | `feature_selection.json`: `atemp` MI **0.1645** > `temp` MI **0.1578**, yet `atemp` was dropped. In `src/tabular_ml_lifecycle/features.py` L180, `drop, keep = (a, b) if mi_scores[a] >= mi_scores[b] else (b, a)` drops the **higher**-MI member. That is the opposite of the docstring (L151) and comment (L173). The `mi_lollipop` subtitle (`figures.py` L250) repeats the false rule. This is a code bug plus a false article claim. The practical effect is small (r = 0.987), but the article presents the rule as a strength ("resolved … by rule", L329-330). |
| L26 | "confirmed by block intervals" | The article's own Limits (L397-399), `evaluation_metadata.json.limits` and `results.md` say block bootstraps are "sensitivity analyses … not independent confirmations". |
| L216 | "learning curves show diminishing returns from more rows and confirm early stopping helps" | Learning curves (`learning_curves.json`) say nothing about early stopping; that evidence is the ablation. LightGBM is also still falling at the top (35.6→34.4 from 0.8→1.0). |

### Overstated (partly supported), unchanged

- L179-180 and caption L449-450, "Training loss keeps falling while validation stalls". Train MAE drops 45.7→~21 by epoch 25 and then plateaus at about 20-21.
- L182-183 and caption L451-452, "Both flatten near the full set … not row count, is the immediate ceiling". LightGBM is still descending (35.6→34.4). The MLP is non-monotone (37.6, 36.4, 37.7, 34.8, 35.3).
- L151 and L327-328, "It agrees with the MI ranking". The set agrees, but the order differs: permutation gives lag1 > lag168 > lag24, MI gives lag1 > lag24 > lag168.

### Untraceable numbers (not in any committed file): 6

1. L167 and L361-362, "`50/50` trials within `240 s`". README says "50 trials" and params gives the 240 s budget. No committed file records that all 50 completed inside the budget.
2. L363-364, "every early-stopping-off row runs to the 150-epoch cap". Only in gitignored `train_runs.json` (`epochs_run`).
3. L347, validation MAE "88.65". Only in gitignored `train_runs.json`; committed files give 88.7.
4. L348, "68.87". Same: committed files give 68.9.
5. L349, "39.50". Same: committed files give 39.5.
6. L365, "`24.96` post-freeze test diagnostic". Committed `results.md` gives 25.0.

Non-numeric: L388 "laptop". `evaluation_metadata.json` records macOS arm64 with 16 CPUs, not a form factor.

Remedy for items 2-6: either commit `train_runs.json` (the README already cites it as the "Full record", results.md L36) or round to the committed one-decimal values.

## 6. Roadmap cards: 5

| Card | Verb-first | Detail ≤90 | Status vs repo | Issue |
|---|---|---|---|---|
| Build the leakage-safe training pipeline | yes | yes (64) | shipped: true (README Delivered) | fine |
| Serve the validation-tied MLP champion | yes | yes (58) | shipped, but "champion" contradicts L356-357 and metrics.json | "a fraction of the floor's 83.2" is vague; say "25.4 vs 83.2 test MAE". Retitle "Serve the validation-tied MLP". |
| Hold the floor gap under resampling | yes (weak verb) | yes (51) | shipped: true | Omits the day block. Suggest "Bound the floor gap with block bootstraps" / "Hourly, day and week 95% CIs all exclude zero." |
| Label ablation scores as post-freeze diagnostics | yes | yes (61) | shipped: true | fine |
| Test challengers under the frozen-window protocol | yes | yes (61) | next | Generic. README "Deferred" (L166-168) lists concrete next steps the cards drop: calendar-event features (the holiday-week residual), refit on train+validation before serving, a transfer check, probabilistic forecasts. No "later" card. |

New since round 1: no roadmap card is false, but the article's own findings (+9.2 under-forecast bias, holiday-week miss, MI-pruning bug) each suggest a concrete next card that is missing.

## 7. Consistency with gold template: 7

Matches gold: an "In plain terms" card closes every section, there is a `([Section →](#sec-…))` link before each, figures are cited by backticked id, and there is a code excerpt with a source link.

Differs:
- Transitions use a fixed formula. The gold versions name the artefact that comes next.
- Two results tables where gold keeps one exact-numbers table.
- The Conclusions sub-section order differs from gold, and this file has an extra "Results summary" heading that gold does not.
- The plain-terms cards for objectives (L68) and data (L103) still carry no quantified takeaway. Gold cards each carry one result number.

## Round-1 finding status

| # | Round-1 finding | Status | Current lines |
|---|---|---|---|
| 1 | Candidate table duplicated; CI triple repeated ~9x | STILL PRESENT | L292-298, L345-351; 8 repeats of the triple |
| 2 | "These patterns set four judging rules": weak EDA link | STILL PRESENT | L123 |
| 3 | "therefore stands" non sequitur | STILL PRESENT | L275-277 |
| 4 | "picks the champion" vs "without a champion label" | STILL PRESENT | L213, L356-357 |
| 5 | Figure-reading-manual voice | PARTLY FIXED | background rewritten (L16-30); body unchanged (L34, L73, L108, L117, L221, L233, L274) |
| 6 | Residual findings flat; holiday week not named | STILL PRESENT | L241-245 |
| 7 | Formulaic "X; next, Y" transitions | STILL PRESENT | L65, L100, L133, L213, L257, L304 |
| 8 | Nested definitions | STILL PRESENT | L170-172, L55-57 |
| 9 | "neural network for tables trained in PyTorch" ambiguous | FIXED | removed in background rewrite |
| 10 | Four names for the tie | STILL PRESENT | L280, L332, L353, L406 |
| 11 | "served-model row — … —" hard to parse | STILL PRESENT | L224-225 |
| 12 | MLP architecture / LightGBM search space missing | STILL PRESENT | L170-177 |
| 13 | Ablation lacks uncertainty; ridge probe not flagged | STILL PRESENT | L149-151, L185-188 |
| 14 | "No global bias" (mean residual +9.2) | STILL PRESENT | L249-250, L458-459 |
| 15 | "Spring rush hours" = holiday week | STILL PRESENT | L242 |
| 16 | "Winter is flatter and lower" contradicts figure | STILL PRESENT | L109, L441-442 |
| 17 | "among 47 epochs" (57 ran) | STILL PRESENT | L176-177 |
| 18 | "Dropout … within noise" | STILL PRESENT | L187, L334-335 |
| 19 | "run ids in reports/metrics.json" | STILL PRESENT | L290 |
| 20 | 44.3 s / 14.7 s (actual 44.4 / 13.3) | STILL PRESENT | L387 |
| 21 | Heatmap figure subtitle contradicts caption (figure-side) | STILL PRESENT | caption L455-456; `residual_heatmap.json` title |
| 22 | "Training loss keeps falling" overstated | STILL PRESENT | L179-180, L449-450 |
| 23 | "Both flatten near the full set" overstated | STILL PRESENT | L182-183, L451-452 |
| 24 | "agrees with the MI ranking" (order differs) | STILL PRESENT | L151, L327-328 |
| 25 | "50/50 trials within 240 s" untraceable | STILL PRESENT | L167, L361-362 |
| 26 | "34.397" untraceable | WITHDRAWN (traceable in `learning_curves.json`) | L362-363 |
| 27 | "150-epoch cap" untraceable | STILL PRESENT | L363-364 |
| 28 | "laptop" not recorded | STILL PRESENT | L388 |
| 29 | Roadmap "champion" card, vague detail | STILL PRESENT | L415-417 |
| 30 | "Hold" card weak, omits day block | STILL PRESENT | L418-420 |
| 31 | Generic "next" card; README deferrals missing | STILL PRESENT | L424-426 |
| 32 | Plain-terms cards without a number (objectives, data) | STILL PRESENT | L68, L103 (reworded, still unquantified) |

Totals: 32 findings. 1 fixed, 1 partly fixed, 1 withdrawn as a round-1 false positive, **29 still present**.

## Top 5 remaining fixes (by severity)

1. **Retract "no global bias".** At L249-250 and caption L458-459, replace with: "the served model under-forecasts by about 9 rentals/hour on average (+28.6 for fitted 300-600), so high-demand hours carry both larger and biased misses." Add a Limits bullet, and add a roadmap card for a train+validation refit or bias check. The `residual_vs_fitted` subtitle in `figures.py` needs the same fix (implementation handoff).
2. **Fix the MI-pruning claim and hand off the code bug.** L146-147, L447-448 and L434-435 claim the lower-MI member is pruned. `atemp` (MI 0.1645) was dropped over `temp` (0.1578) because `features.py` L180 drops the higher-MI member, against its own docstring (L151) and comment (L173). Story interim: "the pruning rule dropped `atemp` and kept `temp`" with no MI-direction claim. Implementation: fix the comparison (or the docstring), re-run, and re-verify that no headline number moves. This is a Kimi handoff, not a story edit.
3. **Fix season labels and name the holiday week.** L109 ("Winter is flatter and lower"), caption L441-442 and L242 ("Spring rush hours … over-forecast by up to 59"). State the UCI season-code quirk once. Rename the L242 slice to "late-December (holiday-week) rush hours" and give the "so what": calendar-event features, already in README Deferred. Fix the figure subtitles ("Red = under-forecasts", "winter is flatter") in `figures.py` via handoff.
4. **Rewrite the ablation reading and remove the new overclaims.** L187 "within noise", L275-277 "therefore stands", L334-335 "smaller dropout … differences", L216 "learning curves … confirm early stopping helps", and L26 "confirmed by block intervals". The configuration stands **by protocol**. Dropout-off is better by about 2.1 on validation and is a next-round candidate. Early stopping is the only control that hurts in every off-row. Block intervals are sensitivity, not confirmation.
5. **Correct the operational numbers, then de-duplicate.** L176-177 → "57 epochs ran; best checkpoint at epoch 47". L387 → `44.4 s` / `13.3 s`. L290 → drop "run ids" or point to `_meta.git_sha`. L347-349 and L365 → use committed values (88.7/68.9/39.5, 25.0) or commit `train_runs.json`. L361-364 → same for "50/50" and "150-epoch cap". L213 and L416 → drop "champion". Then keep one results table and state the CI triple once in Evaluation and once in Conclusions.

## Ready to publish?

**No.** None of the round-1 truthfulness defects were fixed, including the false "no global bias" claim and the mislabelled season slices. This round also exposed a feature-selection claim that the committed data contradicts, rooted in a code bug in `features.py`, and the plain-terms rewrite added two new overclaims (L26, L216). The headline numbers are correct, but the interpretive layer that a senior reader would check is not.
