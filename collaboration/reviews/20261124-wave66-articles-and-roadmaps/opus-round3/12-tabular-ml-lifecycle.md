# Round-3 review: 12-tabular-ml-lifecycle story.yaml

- Reviewer: Claude (Opus), read-only senior ML writer/reviewer pass, round 3
- Target: `projects/12-tabular-ml-lifecycle/story.yaml`, **working tree** (471 lines; uncommitted Wave 8 edits on `wave8-articles-truthfulness-2026-11-25`, HEAD `c05accd0`)
- Gold template: `projects/01-rag-agent/story.yaml`
- Prior round: `opus-round2/12-tabular-ml-lifecycle.md` (reviewed `e69bba84`). Every finding was re-checked against the working-tree file.
- Evidence checked: `reports/metrics.json`, `reports/results.md`, `reports/evaluation_metadata.json`, `reports/figures/*.json` (Plotly `bdata` decoded), `data/feature_selection.json`, `params.yaml`, `README.md`, `DESIGN.md`, `src/tabular_ml_lifecycle/{features,figures,models,mlp}.py`. `reports/train_runs.json` and `reports/dq_report.md` are gitignored and were not used as evidence. The gitignored `data/hour.parquet`, the sha256-pinned UCI source, was used only to check two factual claims about missing hours. Those two claims also appear in committed docs.
- Known limitation, not scored: the project's report assembler expects legacy metadata that the current `metrics.json` lacks (Wave 8 closeout).
- Line numbers refer to the working-tree file.

## What Wave 8 changed

`git diff` on the story touches about 60 lines. Wave 8 also edits `README.md`, `DESIGN.md`, `results.md`, `report.py`, `figures.py`, `features.py`, `config.py`, and the subtitles of six figure JSON/HTML files. I compared HEAD and working-tree figure JSON: the `data` arrays are identical and only `layout.title` changed, so no number moved. The story edits fix almost every round-2 truthfulness defect: residual bias, the season labels, the holiday week, epochs, dropout "within noise", the champion wording, the run ids, runtime, the loss and learning curves, the MI ordering and pruning claims, and the untraceable 50/50, 150-cap and two-decimal values. The cost is in the prose. Several fixes were written as defensive review-response sentences ("no lower-`MI` rule is claimed", "rather than a prose-only fix", "no committed artifact proves…"). Those sentences now read as process notes, not as article text.

**Commit dependency:** the story captions now agree with the *working-tree* figure subtitles (for example `residual_vs_fitted` "+9.2 … under-forecast bias" and `residual_heatmap` "Red = over-forecast"). The HEAD figures still carry the old, contradicting subtitles. The story and the regenerated figures must land in the same commit.

## Grades

| # | Dimension | R1 | R2 | R3 |
|---|---|---|---|---|
| 1 | Structure and article logic | 7 | 6 | 6 |
| 2 | Engagement and human-like narrative | 6 | 6 | 6 |
| 3 | Language quality | 6 | 6 | 5 |
| 4 | Technical depth | 8 | 7 | 7 |
| 5 | Truthfulness | 5 | 4 | 7 |
| 6 | Roadmap cards | 6 | 5 | 8 |
| 7 | Consistency with gold template | 8 | 7 | 7 |
| | **Overall** | **6** | **5** | **6** |

## 1. Structure and article logic: 6

The arc is still sound: question → checks → data → EDA → ladder → measurement chain → ledger → conclusions. The Results bullet that used to be a non sequitur ("therefore stands") now gives the right reason, L280-281 "stands by protocol, not because it won the ablation".

Remaining:
- **Two candidate tables** (L296-302 rounded, L350-356 mixed one- and two-decimal). The L308 transition still promises "the exact tables" again. The gold template has one Exact-numbers table.
- **The floor-gap CI triple repeats about 8 times**: headline L2-4, short_version L12, L237-239, L276-277, L305-306, L320, L365-366, caption L469.
- **The atemp/temp pruning fact appears 6 times**: L120-121, L146-147, L152-153, L332-334, key concept L440-441, caption L454. Within the training section it is stated twice in seven lines (L146-147 and L152-153).
- **Weak EDA-to-rules link** at L123 ("These patterns set four judging rules"). Only the MAPE floor follows from the EDA.
- **Logic tension about the shipped ablation configuration (new).** L280 calls it "pre-registered". L377-378 and L398 say validation set "the shipped ablation configuration". Yet the validation argmin is dropout-off (32.1 vs 34.2), so validation did not choose it. The likely truth is "fixed in `params.yaml` before the ablation ran". The article should say that once and drop both "pre-registered" and "validation … shipped ablation configuration".
- **Conclusions order** is still Results summary → Taught → Exact numbers → Protocol → Limits. Gold is Taught → Limits → Exact numbers → Measured alternatives → Protocol, with no "Results summary".

## 2. Engagement and human-like narrative: 6

The residual paragraph (L243-254) is now the best writing in the article. It names the late-December holiday week, puts a number on the bias, and says what the bias means. The body still reads as a figure manual: "Read … as a sequence" L34, "Follow" L73/L223, "compare" L108/L112/L182/L235/L278/L317, "look for" L117/L278, "Read `mlp_loss_curves`" L180. The training section is still a hyperparameter list. The holiday-week finding stays in Evaluation and never becomes a lesson in "What the experiment taught".

## 3. Language quality: 5 (down from 6)

New in Wave 8. The truth fixes were written as review-response hedges and leak process language into the article:
- L147 "no lower-`MI` rule is claimed"
- L169-170 "no committed artifact proves all `50` completed inside that budget"
- L181 "the gap motivates the controls without claiming continual improvement"
- L189 "No ablation interval supports a within-noise claim." This is a double negative about a sentence that no longer exists.
- L334 "requires a fresh run rather than a prose-only fix". "Prose-only fix" is internal workflow vocabulary.
- L368-369 "Completion counts and epoch caps are not committed."

A reader who never saw the earlier draft cannot tell what these sentences push back against. State the fact positively, for example "The study budget is 50 trials or 240 s, whichever comes first", or cut the sentence.

Also new:
- L280 "about `2.1` rentals better and becomes a next-round candidate" needs a comma and a subject: "…better; it becomes…".
- L215 "The ladder selects the served model without a champion label; next, …" is awkward. "Validation selects the MLP; next, …" is enough.
- Many Wave 8 lines run 110-130 characters (L109, L146, L151, L180, L183, L188, L244, L252, L281, L369) while the surrounding text wraps at about 75. This is cosmetic in YAML, but it signals patching.

Carried over:
- Six of seven transitions still use the "X; next, Y ([Z →])" formula (L28, L65, L100, L133, L215, L261, L308).
- Nested definitions remain at L54-57 (regularization → overfitting) and L171-173 (embedding → standardized → rescaled).
- The tie still goes by five names: "validation-tied" (L2), "statistical dead heat" (L284), "effectively tied" (L336), "a tie" (L358), "negligible" (L412).
- L226-227 "the served-model row — the one candidate validation selected to serve — with the same floor row" is still hard to parse.
- Backtick use is still inconsistent (`83.2` at L17 but plain 83.2 at L236; "`95%` `CI`" split across two code spans).

## 4. Technical depth: 7

Strong points: the paired hourly, 24 h and 168 h bootstrap with its explicit scope (L228-230, L322-324), the validation tie interval (L358-362), the checkpoint/restore excerpt, the leakage drop, the honest learning-curve reading, and the quantified under-forecast bias.

Gaps:
- MLP architecture: hidden dims 64/32, lr 1e-3, batch 256, patience 10, max 150 epochs (`params.yaml` L22-32). These are still missing. L369 even says the epoch cap is "not committed" (see §5).
- The LightGBM search space is not stated.
- Permutation importance uses a ridge probe for a nonlinear winner, and the article does not flag this.
- The season-code quirk is mentioned (L110, L244) but never explained. In the data, UCI code 1 "spring" runs Dec 21–Mar 20 and code 4 "winter" runs Sep 23–Dec 20, so every label is one season early. One sentence would make the EDA and residual paragraphs self-explanatory. It would also reveal that the "winter" residual row (L245) is November to mid-December.
- Missing-hour handling is described with the wrong gap location and size (§5). That matters for the positional-lag discussion.

## 5. Truthfulness: 7 (up from 4)

### Verified against committed files

Every number in the article traces to a committed file:

- Data and split: 17,379 rows; 14,523/1,344 split (`feature_selection.json` n_train + 2×1,344 + 168 = 17,379); 26 DQ checks (README); 165 missing hours, ~1%, 2% gate (DESIGN).
- EDA: 08h and 17-18h peaks, spring lowest at 264, winter 486 vs summer 519, minimum at 4h (`rentals_by_hour_season.json`); r 0.99 / 0.987 (heatmap 0.9877, `pruned_pairs` 0.9873).
- Feature selection: MI 0.89/0.76/0.71; atemp 0.1645 > temp 0.1578; permutation order lag1 > lag168 > lag24 versus MI lag1 > lag24 > lag168; 15 of 16 features.
- Training: validation 88.7/68.9/39.5/34.4/34.2 (README table; 34.397 in `learning_curves.json`; 34.217 in `mlp_loss_curves.json`); 50 trials, 240 s, MedianPruner (`params.yaml`, `models.py` L130); embed 8, dropout 0.2, weight decay 1e-4 (`params.yaml`); 57 epochs, best epoch 47, train plateau about 20-21 (`mlp_loss_curves.json`).
- Learning curves: LightGBM 35.62 → 34.40; MLP non-monotone.
- Ablation: dropout-off −2.09 / −2.09; every early-stopping-off row worse by +1.1/+0.5/+3.6/+2.6; argmin 32.13 with test 25.0 (`ablation_dotplot.json`, `results.md`).
- Test metrics: 83.2/25.4, gain 57.77, test MAE gap 0.06, RMSE 39.3 vs 40.2 (`metrics.json`); CIs [52.49, 63.07], [44.21, 71.83], [38.82, 73.41] (DESIGN; `bootstrap_ci.json` percentiles reproduce them); tie −0.18 [−1.71, +1.21] (`metrics.json`).
- Residuals: maxima −58.8 (spring, 17h), +50.5 (winter, 8h), +39.1/+40.2 (w1/w2, 8h); +9.2 mean, +2.8 median, +28.6 for fitted 300-600 (`residual_vs_fitted.json`, 1,344 points).
- Run metadata: 44.4 s / 13.3 s, 16 CPUs, torch 1 thread (`evaluation_metadata.json`); determinism settings (`models.py` L28-30, L58; `mlp.py` L118-145).

**Untraceable numbers: 0.** All six round-2 untraceable items were fixed by removal or by rounding to the committed values.

### Contradicted or wrong claims (4)

| Line | Claim | Evidence |
|---|---|---|
| L89-90 (also L382) | "165 hours are missing in the January 2011 outage pattern" | Only **56** of the 165 missing hours are in January 2011. The largest other gap is **36 consecutive hours, 2012-10-29 01:00 to 2012-10-30 12:00** (Hurricane Sandy), plus 73 scattered hours. 40 missing hours fall inside the validation/test span. The story repeats committed DESIGN L27, README L47 and `feature_selection.json.leakage_policy`, so this is a docs-wide error and not a Wave 8 regression. It is still false. Fix: "165 hours are missing, mostly early 2011 plus a 36-hour gap in late October 2012". |
| L405-406 | "Around the 165 missing hours, 'same hour last week' drifts by an hour of wall-clock time" | Positional lags drift by the number of missing rows in the window. For about a week after the Oct-2012 gap, `lag_168` (and the seasonal-naive floor) reads a value about **36 hours** off, and `lag_24` is shifted for a day and a half. That gap sits inside the **validation** window (validation starts 2012-09-09 08:00; test starts 2012-11-05 20:00). It therefore affects validation MAE for the floor and every lag model. Validation also spans about 8 weeks + 1.5 days, not exactly 8 weeks. |
| L368-369 | "Completion counts and epoch caps are not committed." | The epoch cap **is** committed: `params.yaml` `max_epochs: 150`. Only per-run epochs for the ablation variants are uncommitted. Fix: "The epoch cap is 150; per-variant epoch counts are not committed." Better still, state the configuration positively and drop the sentence. |
| L280 (with L377-378, L398) | "The pre-registered configuration" | No pre-registration artifact exists. The same article says validation set the shipped ablation configuration, but the validation argmin is a different row. Replace with "the configuration fixed in `params.yaml` before the ablation". |

### Minor or imprecise

- L244-245 "over-forecast by up to `59` rentals at `7–8h` and `17h`". The 59 is at 17h only; 7-8h are −20.6/−24.8. Suggest "up to 59 at 17h and about 20-25 at 7-8h".
- L245 "Winter morning peaks": the UCI "winter" code in the test window is November to Dec 20. Name the dates once.
- Headline L2-4: the CI has no stated subject ("hourly 95% bootstrap CI 52.5-63.1"). It is the CI of the *gain*, not of the 25.4 MAE. Write "gain 57.8, hourly 95% CI 52.5-63.1".

### Evidence-side issues (not story errors; for the implementation handoff)

- `README.md` L99-101 says the residual maps show where the model "under-forecasts (rush-hour peaks and bad weather)". `residual_heatmap.json` shows late-December rush hours and most w3 (light-rain) evening hours **over**-forecast. Only winter/clear-weather mornings are under-forecast.
- `features.py` L151-152 docstring and L174-175 FIXME (new in Wave 8) say the code "drops the first member". L180 `drop, keep = (a, b) if mi_scores[a] >= mi_scores[b] else (b, a)` drops the **higher-MI** member, which here happens to be the second element (atemp). The new comment misdescribes the bug it flags.
- `DESIGN.md` L27, README L47 and `feature_selection.json` carry the "January 2011 outages" attribution.

## 6. Roadmap cards: 8 (up from 5)

| Card | Verb-first | Detail chars | Status vs repo | Note |
|---|---|---|---|---|
| Build the leakage-safe training pipeline | yes | 65 | shipped ✓ (README Delivered, DQ gates, sha256 in params) | fine |
| Serve the validation-tied MLP | yes | 56 | shipped ✓ | fixed (no "champion"; concrete 25.4 vs 83.2) |
| Bound the floor gap with block bootstraps | yes | 58 | shipped ✓ (`bootstrap_ci.json`, DESIGN) | fixed (includes day block) |
| Label ablation scores as post-freeze diagnostics | yes | 61 | shipped ✓ (`results.md`, DESIGN) | fine |
| Correct pruning and test holiday features | yes | 71 | next ✓ (features.py FIXME, README Deferred) | Concrete now. Two actions in one title. The gate "no regression in floor gap" is weak for a feature change: it should be "validation MAE ≤ 34.2 and late-December residual reduced". The under-forecast bias (+9.2) and the dropout-off candidate surfaced by the article have no card. Gold also has only one "next" card, so this is optional. |

## 7. Consistency with gold template: 7

Matches gold: question lead, a three-bullet "Follow the …" list, a plain-terms card closing every section, a section link before each, backticked figure ids, a code excerpt with a source link, and a gate-style "next" card.

Differs:
- Formulaic transitions, where gold names the next artefact and varies the sentence shape.
- Two results tables.
- Conclusions order and the extra "Results summary".
- Plain-terms cards for objectives (L68) and data (L103) still carry no result number. Every gold card carries one (for example 593, 1/120, 30/30).

## Round-2 finding status

| # | Round-2 finding | Status | Working-tree lines |
|---|---|---|---|
| 1 | Candidate table duplicated; CI triple repeated | STILL PRESENT | L296-302, L350-356; triple about 8× |
| 2 | "These patterns set four judging rules": weak EDA link | STILL PRESENT | L123 |
| 3 | "therefore stands" non sequitur | FIXED | L280-281 ("by protocol"), but see the new "pre-registered" issue |
| 4 | "picks the champion" vs "no champion label" | FIXED | L215, L362, roadmap L422 |
| 5 | Figure-reading-manual voice | STILL PRESENT | L34, L73, L108, L117, L180, L223, L235, L278, L317 |
| 6 | Residual findings flat; holiday week not named | PARTLY FIXED | named at L244, quantified bias L252-254, Limits L410-411; never reaches "What the experiment taught"; season quirk unexplained |
| 7 | Formulaic "X; next, Y" transitions | STILL PRESENT | L28, L65, L100, L133, L215, L261, L308 |
| 8 | Nested definitions | STILL PRESENT | L54-57, L171-173 |
| 9 | "neural network for tables trained in PyTorch" | FIXED (since R2) | — |
| 10 | Several names for the tie | STILL PRESENT | L2, L284, L336, L358, L412 |
| 11 | "served-model row — … —" hard to parse | STILL PRESENT | L226-227 |
| 12 | MLP architecture / LightGBM search space missing | STILL PRESENT | L171-178 (hidden dims, lr, batch, patience, cap absent) |
| 13 | Ablation lacks uncertainty; ridge probe not flagged | PARTLY FIXED | L189 acknowledges no interval; ridge-for-nonlinear still unflagged (L149-151) |
| 14 | "No global bias" (mean residual +9.2) | FIXED | L252-254, caption L465, Limits L410 |
| 15 | "Spring rush hours" = holiday week | FIXED | L244 |
| 16 | "Winter is flatter and lower" | FIXED | L109-110, caption L448 |
| 17 | "among 47 epochs" | FIXED | L177-178 |
| 18 | "Dropout … within noise" | FIXED | L188-189, L338-340 |
| 19 | "run ids in metrics.json" | FIXED | L294 |
| 20 | 44.3 s / 14.7 s | FIXED | L392 |
| 21 | Heatmap figure subtitle contradicts caption | FIXED (working tree only; HEAD figure still wrong; commit together) | `residual_heatmap.json` title |
| 22 | "Training loss keeps falling" | FIXED | L180-181, caption L455 |
| 23 | "Both flatten near the full set" | FIXED | L183-184, caption L457 |
| 24 | "agrees with the MI ranking" | FIXED | L151-152, L331-332 |
| 25 | "50/50 trials within 240 s" | FIXED (now over-hedged, see §3) | L167-170, L367-369 |
| 26 | "34.397" untraceable | WITHDRAWN in R2 | L368 |
| 27 | "150-epoch cap" untraceable | FIXED, but replaced by the false "epoch caps are not committed" | L369 |
| 28 | "laptop" | FIXED | L392 |
| 29 | Roadmap "champion" card | FIXED | L422-423 |
| 30 | "Hold" card weak, omits day block | FIXED | L425-426 |
| 31 | Generic "next" card | PARTLY FIXED | L430-432 concrete; weak gate; bias/dropout unrepresented |
| 32 | Plain-terms cards without a number | STILL PRESENT | L68, L103 |

Totals: 32 findings. **19 fixed, 3 partly fixed, 9 still present, 1 withdrawn.**

## New errors introduced by Wave 8

1. **L368-369 "epoch caps are not committed".** False: `params.yaml` `max_epochs: 150`.
2. **L280 "pre-registered configuration".** There is no pre-registration record, and the phrase contradicts L377-378 and L398 (validation-set configuration).
3. **Process-language leakage.** L147, L169-170, L181, L189, L334, L369 (§3).
4. **L280 grammar** ("about 2.1 rentals better and becomes…").
5. **Redundancy.** The atemp/temp fact appears twice within L146-153 and six times in total.
6. **Implementation-side.** The `features.py` FIXME and docstring misdescribe the pruning bug ("drops the first member" instead of "drops the higher-MI member").

Missed in rounds 1-2 and still present: the "January 2011 outage pattern" attribution (L89) and the "drifts by an hour" lag claim (L405-406). The 36-hour Oct-2012 gap sits inside validation.

## Top 5 remaining fixes

1. **Correct the missing-hours facts (L89-90, L382, L405-406).** Say "165 missing hours, mostly early 2011 plus a 36-hour gap on 2012-10-29/30 inside the validation window". Replace "drifts by an hour" with "drifts by up to 36 hours for about a week after the October 2012 gap, which affects validation lags and the floor". Hand the same correction to DESIGN L27, README L47 and `feature_selection.json.leakage_policy` via the implementation handoff.
2. **Strip the review-response hedges and fix the two new false or unsupported claims.** L147, L169-170, L181, L189, L334 and L368-369 should state facts positively. Change L369 to "epoch cap 150 (`params.yaml`); per-variant epoch counts are not committed". Change L280 from "pre-registered" to "fixed in `params.yaml` before the ablation", and align L377-378 and L398 with that.
3. **De-duplicate.** Keep one exact-numbers table (two-decimal, in Conclusions) and replace the Results table (L296-302) with a one-line pointer. State the CI triple once in Evaluation and once in Conclusions. State the atemp/temp fact once in Training and once in Limits or Taught. Reorder Conclusions to gold (Taught → Limits → Exact numbers → Protocol) and drop "Results summary".
4. **Explain the season-code shift once and lift the residual finding into the lessons.** Add one sentence at L110: "UCI codes run one season early: 'spring' is Dec 21–Mar 20, 'winter' is Sep 23–Dec 20". Make L244-245 precise ("up to 59 at 17h; 20-25 at 7-8h"). Add a "What the experiment taught" bullet: the model under-forecasts high-demand hours by +28.6 and over-forecasts the holiday week, which motivates calendar-event features. Tighten the roadmap gate to validation MAE plus the late-December residual.
5. **Language pass.** Vary the seven transitions (name the next artefact, as gold does). Use one name for the tie. Unnest L54-57 and L171-173. Rewrite L226-227. Fix L280 grammar. Add a result number to the L68 and L103 plain-terms cards. Add the MLP shape (64→32, lr 1e-3, batch 256, patience 10) in one line at L171.

## Ready to publish?

**No, but close.** Wave 8 fixed the substantive round-2 truth defects, and every number now traces to committed evidence. Four claims are still wrong or unsupported: the January-2011 attribution of the missing hours, the "drifts by an hour" lag claim (the real drift reaches 36 hours inside validation), "epoch caps are not committed", and "pre-registered". The Wave 8 patches also left review-process language in the article. Publication also depends on committing the regenerated figure subtitles together with the story. One focused editorial pass on fixes 1-2, plus the de-duplication in fix 3, should make it publishable.
