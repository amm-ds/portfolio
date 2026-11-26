# Review: 12-tabular-ml-lifecycle story.yaml (Wave 6.6)

- Reviewer: Claude (Opus), read-only senior ML writer/reviewer pass
- Target: `projects/12-tabular-ml-lifecycle/story.yaml` (469 lines)
- Gold template: `projects/01-rag-agent/story.yaml`
- Evidence checked: `reports/metrics.json`, `reports/results.md`, `reports/evaluation_metadata.json`, `reports/figures/*.json` (decoded), `data/feature_selection.json`, `params.yaml`, `README.md`, `DESIGN.md`, `src/tabular_ml_lifecycle/{figures,features,stages,mlp}.py`
- Note on the diff: the working tree is clean for this file. The Wave 6.6 edits are already committed in `18adc59d`, so `git diff -- story.yaml` is empty. I reviewed the round with `git diff HEAD~1`. That round renamed "Business summary" to "In plain terms", added seven `next; ([X →])` transitions, and tightened the background prose. No numbers changed in this round, so every truthfulness finding below was already in the file before Wave 6.6.

## Grades

| # | Dimension | Grade |
|---|---|---|
| 1 | Structure and article logic | 7 |
| 2 | Engagement and human-like narrative | 6 |
| 3 | Language quality | 6 |
| 4 | Technical detail depth | 8 |
| 5 | Truthfulness | 5 |
| 6 | Roadmap cards | 6 |
| 7 | Consistency with gold template | 8 |
| | **Overall** | **6** |

## 1. Structure and article logic: 7

The order works: question → checks → data → EDA → training ladder → fixed measurement chain → ledger → conclusions. Each section ends with a transition and then an "In plain terms" card.

Problems:
- **Repeated content.** The candidate table appears twice: once rounded (L308-314) and once at two decimals (L364-370). The floor-gap sentence "57.8 … [52.5, 63.1] … [44.2, 71.8] … [38.8, 73.4]" appears in the headline, short_version, L248-250, L275, L286-289, L316-318, L333-336, L378-380 and the bootstrap caption, so about nine times. Results and Conclusions overlap heavily. The L320 transition even promises "the exact tables" again.
- **Weak link from EDA to metrics.** L131 says "These patterns set four judging rules". Only the MAPE floor follows from the EDA (the near-zero 4h counts). MAE-first and the naive floor are design choices, not EDA findings.
- **Non sequitur at L291-293.** It reads: "A dropout-off row reaches 32.1, about 2 rentals better. The pre-registered configuration … therefore stands." A better variant is not a reason to keep the shipped one. The real reason is the protocol: the configuration was fixed before scoring.
- **Champion contradiction.** L223 says "The ladder picks the champion", but L375-376 says "without a champion label".

## 2. Engagement and human-like narrative: 6

The opening question (L12) is concrete and good. After that the voice turns into a figure-reading manual: "Follow `…`", "Read `…` as a sequence", "In `…`, compare …", "look for …". Almost every paragraph also stops to define a term with "meaning …" (L127, L166, L292, L303). Defining terms helps a lay reader, but at this density the story disappears. The residual findings (L255-258) are the most interesting part of the article, yet they get three flat sentences and no "so what". For example, the article never says that the late-December error is the holiday week. The training section reads like a hyperparameter list.

## 3. Language quality: 6

- Every transition uses the formula "`X`; next, `Y` ([Z →])", seven times in a row (L29, L69, L106, L141, L223, L270, L320). The gold template varies its transitions and names the table or figure that comes next.
- Definitions pile up inside definitions. Examples: L180-182, "an 8-dimensional embedding turns the raw hour into eight learned numeric values beside standardized features, which are rescaled to comparable ranges"; and L59-61, where regularization → overfitting is defined twice in one bullet.
- L18-19 "last week's count at the same hour" is fine. L19-20 "a neural network for tables trained in PyTorch" is ambiguous: it could mean the tables were trained.
- L296 "statistical dead heat" next to L372 "tie", L425 "negligible" and L351 "effectively tied" means four names for the same thing.
- L237-238 "the served-model row — the one candidate validation selected to serve — with the same floor row" is hard to parse.

## 4. Technical detail depth: 8

Strengths: the paired hourly plus 24h/168h block bootstrap is stated correctly, including the scope note that it "does not measure selection variance". The validation tie interval is shown. The positional-lag convention is disclosed. The checkpoint/restore code excerpt is apt. The leakage drop of `casual`/`registered` is explained. Post-freeze diagnostics are labelled correctly.

Gaps for an expert reader: the MLP architecture is missing (hidden dims 64/32, lr 1e-3, batch 256, patience 10, Huber δ=1.0, all in `params.yaml`). So is the LightGBM search space. The ablation carries no uncertainty, yet the text makes "within noise" claims about it (see §5). Permutation importance uses ridge as the probe, which is a weak probe for a nonlinear winner, and the article does not flag this.

## 5. Truthfulness: 5

All headline numbers trace correctly: 83.2/25.4, 57.8, the three CIs, the validation and test table, the tie interval −0.18 [−1.71, +1.21], MI 0.89/0.76/0.71, r 0.987, 15 of 16 features, 14,523/1,344 rows, 165 missing hours, peaks at 08h and 17-18h, the 4h minimum, and residual extremes 59/51/~40. The problems are in the interpretive claims and a few operational numbers.

### Contradicted by committed files

| Line | Claim | Evidence |
|---|---|---|
| L262-263 | "The points remain centered on zero, so the figure shows no global bias to correct." | `residual_vs_fitted.json`: mean residual (actual − fitted) is **+9.2 rentals/hour** over 1,344 points, about 36% of the 25.4 MAE. For fitted 300-600 it is +28.6. The model under-forecasts on average. The same error repeats in caption L467, "without global bias". |
| L255 | "Spring rush hours (7-8h, 17h) are over-forecast by up to 59" | The test window is 2012-11-05 to 2012-12-31. `residual_heatmap.json` has data only for "spring" and "winter". The "spring" cells are UCI season code 1, which in this window covers only about Dec 21-31 (262 rows, the holiday week). Calling them "spring rush hours" misleads the reader. |
| L117-118 | "Winter is flatter and lower" | In `rentals_by_hour_season.json` the lowest, flattest panel is **"spring"** (peak 264). "Winter" peaks at 486, close to summer's 519. This is the same UCI season-label quirk, and the prose contradicts the figure as it is labelled. |
| L186-187 | "keeps the best checkpoint among 47 epochs" | `mlp_loss_curves.json`: **57 epochs ran**, best epoch 47 (47 + patience 10). The claim should be "best of 57, at epoch 47". |
| L197; L353-354 | "Dropout and weight decay sit within noise"; "smaller dropout and weight-decay differences" | `results.md` ablation: turning dropout off improves validation MAE by **2.1** in both early-stopping-on pairs (34.2→32.1, 34.3→32.2). Turning early stopping off costs only **+1.0** on the shipped row. No interval exists on the ablation, so "within noise" is unsupported for dropout. Weight decay alone (≤0.1) really is negligible. |
| L306 | "run ids in `reports/metrics.json`" | `metrics.json` has no run ids, only `_meta.git_sha`. `train_runs.json` is gitignored and not committed. |
| L406 | "train stage 44.3 s plus evaluate 14.7 s" | `evaluation_metadata.json`: `train_s` 44.377 (rounds to 44.4), `evaluate_s` **13.306**. |
| L223; L440 | "The ladder picks the champion"; roadmap "Serve the validation-tied MLP champion" | L375-376 and `metrics.json.validation_tie_interval.interpretation` say "not a proven champion" and "without a champion label". |
| L466 caption vs figure | Caption: "Red means over-forecast" | The caption agrees with the RdBu colorscale (negative residual = red). But the committed figure's own subtitle (`residual_heatmap.json` layout.title) says "Red = the model under-forecasts there … bad-weather bias". The reader sees a figure that contradicts its caption. This is a figure-side bug. `README.md` L101-102, "under-forecasts (rush-hour peaks …)", has the same confusion. |

### Overstated (partly supported)

- L189-190 "Training loss keeps falling while validation stalls". Train MAE falls 45.7→~21 by epoch 25 and then plateaus around 20-21, so it does not keep falling.
- L192 and caption L464, "Both flatten near the full set". LightGBM is still descending at the top (35.6→34.4 from 0.8→1.0). The MLP curve is non-monotone (37.6, 36.4, 37.7, 34.8, 35.3). The conclusion that "row count is not the ceiling" holds for the MLP but is weak for LightGBM.
- L160-161 "It agrees with the MI ranking". The three lags agree as a set, but the order differs (permutation: lag1 > lag168 > lag24; MI: lag1 > lag24 > lag168). Also, `feature_selection.json` stores `permutation_val_mae_increase` with a flipped sign (lag_1h = −64.9 means an increase). The contract field is mislabelled, though the article itself is not affected.
- L263, residual spread: "spread widens as fitted values rise" is supported (std 19.7 → 34.7 → 56.8 → 89.3).

### Untraceable numbers (not in committed files): 3

1. L177 / L381: "50/50 trials within 240 s". The budget is in `params.yaml` and README says "50 trials", but no committed file records that 50 trials completed within the budget.
2. L382: "best validation MAE 34.397". Not in any committed file. Only the rounded 34.4/34.40 appears in README and the table.
3. L383: "every early-stopping-off row runs to the 150-epoch cap". The cap is in params, but per-run epoch counts live only in the uncommitted `train_runs.json`.

(Minor, non-numeric: L407 says "laptop". `evaluation_metadata.json` shows macOS arm64 with 16 CPUs, so the form factor is not recorded.)

## 6. Roadmap cards: 6

| Card | Title verb-first | Detail ≤90 | Issue |
|---|---|---|---|
| Build the leakage-safe training pipeline | yes | yes (67) | fine |
| Serve the validation-tied MLP champion | yes | yes (60) | "champion" contradicts L375-376. "a fraction of the floor's 83.2" is vague; state 25.4 vs 83.2. |
| Hold the floor gap under resampling | yes ("Hold" is weak) | yes (51) | Omits the day-block interval. Better: "Bound the floor gap with block bootstraps". |
| Label ablation scores as post-freeze diagnostics | yes | yes (62) | fine |
| Test challengers under the frozen-window protocol | yes | yes (63) | Generic. The article's own evidence points at concrete next steps that README "Deferred" already lists and the cards drop: calendar/holiday features (the late-December residual), refit on train+validation before serving, and a transfer check. |

The statuses are sensible. There is one "next" card and no "later" card, so the README deferrals are invisible in the roadmap.

## 7. Consistency with gold template: 8

It matches the gold template: an "In plain terms" card closes every section, there is a `([Section →](#sec-…))` link before it, figures are cited by backticked id, and there is a code excerpt with a source link. It differs in three ways:
- The gold transitions name the artefact the reader is about to see ("The headline table and three charts below … ([Conclusions →])"). Here they use the fixed "`X`; next, `Y`" formula.
- Gold "In plain terms" cards carry one quantified takeaway each. Here, L72-74 and L109-111 are restatements with no number.
- Gold keeps one results table. This file keeps two.

## Top 5 fixes (by severity)

1. **Retract the "no global bias" claim.** Lines: `story.yaml` L262-263, "The points remain centered on zero, so the figure shows no global bias to correct", and caption L467, "without global bias". The committed residuals average **+9.2** (actual − fitted), and +28.6 for fitted 300-600, so the model systematically under-forecasts. Suggested wording: "the served model under-forecasts by about 9 rentals/hour on average, mostly in high-demand hours". Add a roadmap or limits line for bias correction or a train+validation refit.
2. **Fix the season labels in EDA and residual prose.** Lines: L117-118, "Winter is flatter and lower" (the figure shows "spring", peak 264, as the lowest), and L255, "Spring rush hours … over-forecast by up to 59". The test window is Nov 5-Dec 31. UCI season code 1 there covers only about Dec 21-31, so the −59 at 17h is a holiday-week over-forecast, not spring. State the UCI season-code quirk once and rename the slice, e.g. "late-December (holiday-week) rush hours". The figure's "Red = under-forecasts" subtitle (`reports/figures/residual_heatmap.json`, generated in `src/.../figures.py`) contradicts caption L466 and should be fixed in the figure code. That is an implementation handoff, not a story edit.
3. **Rewrite the ablation interpretation.** Lines: L197, "Dropout and weight decay sit within noise"; L291-293, "about 2 rentals better. The pre-registered configuration … therefore stands"; L353-354, "smaller dropout and weight-decay differences". The data shows dropout-off is better by 2.1 in both early-stopping-on pairs, which is larger than the +1.0 early-stopping effect on the shipped row. Say instead that the configuration stands **by protocol** (it was fixed before scoring), that dropout-off is a candidate for the next frozen-window round, and that weight decay is negligible. Also drop "therefore".
4. **Correct the operational numbers and pointers.** L186-187 "among 47 epochs" → "57 epochs ran; the best checkpoint is epoch 47". L406 "train stage 44.3 s plus evaluate 14.7 s" → 44.4 s / 13.3 s per `evaluation_metadata.json`. L306 "run ids in `reports/metrics.json`" → point to `_meta.git_sha` or remove. For L381-383 ("50/50", "34.397", "150-epoch cap"), either commit the evidence (`train_runs.json`) or cut the claims back to what README and params support.
5. **Remove the "champion" contradiction and the duplication.** L223, "The ladder picks the champion", and roadmap L440, "Serve the validation-tied MLP champion", conflict with L375-376, "without a champion label". Use "served MLP". Then keep one results table (drop L308-314 or L364-370), state the floor-gap CI triple once in Evaluation and once in Conclusions, and vary the seven "`X`; next, `Y`" transitions so they name the figure or table that comes next, as the gold template does.
