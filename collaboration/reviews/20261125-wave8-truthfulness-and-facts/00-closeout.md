# Wave 8 closeout — article truthfulness, facts, diagrams, and roadmaps

Date: 2026-11-26

Branch: `wave8-articles-truthfulness-2026-11-25`

Base: `main` @ `c05accd096ee2209bc7bb8362aa15bf3ec171fc5`

Scope: Opus round-2 reviews for projects `02`–`13`; projects `01-rag-agent` and `15-dynamic-pricing-rl` are excluded.

## Method and review locator convention

Every material claim was checked against committed reports, source, parameters, or diagram specifications before editing. Review labels below (`TR`, `T`, `S`, `E`, `L`, `D`, `R`, `G`, and numbered round-1 rows) are the identifiers used by each project's round-2 review; `R2 §5` denotes the review's truthfulness section and `R2 §6` its roadmap section. Findings that shared one artifact and one correction are grouped, with all applicable identifiers retained.

The `e69bba84` presentation contract was preserved: one hero diagram and three-step introduction, eight-section article structure where applicable, inline code tagging, compact tables, linked transitions, plain-English takeaway cards, and five roadmap cards. No model was retrained and no evaluation result was changed to fit prose.

## 02 — demand forecasting

Review: `opus-round2/02-demand-forecasting.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| Round-1 1–5, 26–27; R2 new 1 and 5: origin counts, runtime, candidate families, feature windows, and formatting | `reports_m5_full/metrics.json` (`origins`, `candidates`), `evaluation_metadata.json` (`split`, `runtime_seconds`), `src/m5_full.py`, `src/m5_track.py` feature docstring, `README.md` | Corrected the protocol to nine selection origins plus one test origin (ten total), removed the unsupported `46,509 s` and `12.9 h` claims, described five LightGBM fits among eight candidates, restored the actual lag/rolling/std/expanding feature sets, and removed the stale README origin count. |
| Round-1 6: pooled-versus-global comparison changed two variables | `metrics.json` / `evaluation_metadata.json` (`pooled_strategy: direct`) and the recursive global-fit implementation | Disclosed that pooled arms use direct multi-horizon fits while the global comparator is recursive; the article no longer attributes the whole difference to pooling alone. |
| Round-1 9, 13–14; R2 new 2, 3, and 6: blend membership, marginal advantage, and per-level claims | `metrics.json` (`ensemble.weights`, `test.*.per_level_wrmsse`, WAPE, bias, stability), routed-arm noise band | Reframed the `0.95 / 0.00 / 0.05` blend as two active models, stated the `0.0008` best-single gap as about `1.2×` the noise band, disclosed the single fit's WAPE/bias wins and four learned arms beating the blend at total level, and separated total's largest relative cut (`43.9%`) from item-store's largest absolute cut (`0.341`). Removed misleading stability bolding. |
| Round-1 7–8, 10–11, 15, 23: spike/Huber chronology, capped gate, partial Huber score, interval scope, and test rereads | `erratic_challenger.json`, `erratic_refinement` bootstrap fields, `DESIGN.md` wave 33/34 and capped-run gate records | Identified Huber as the later challenger, stated that the capped run was already rejected (`+0.0204`, about twice noise), limited the Huber loss to one of nine selection origins, narrowed the missing interval to the headline gap, and disclosed the adoption gate's second test read instead of claiming an absolute single read. |
| Round-1 12, 16–22, 24–25; R2 new 4; R2 §§6–7: stale diagrams, repetition, transitions, and roadmap | `apps/showcase-web/src/diagrams/auto/02-demand-forecasting-{2,3}.ts`, `m5Pipeline.ts`, committed origin/weight fields, `story.yaml`, `README.md` | Updated all three diagrams to nine selection origins and `0.95 / 0.00 / 0.05`; restored the origin count in the shipped card, replaced the historical Huber card with a forward gate, reduced repeated quiet-day/caveat language, varied transitions, and normalized number tagging. |

The requested concrete reorder-planning scenario was not invented: no committed artifact translates forecast error into a specific reorder decision. The article keeps the supported operational interpretation instead.

## 03 — anomaly detection

Review: `opus-round2/03-anomaly-detection.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| TR1–TR4, L3–L4, S4: false-alarm versus missed-incident wording, CI comparison, train-only zeros, page range, detector attribution, and cross-cell recall | `reports/nab_sweep.json`, `reports/nab_metrics.json`, sweep/tuning tables | Replaced “miss rate roughly halves” with the like-for-like outside-incident share `65.3% → 44.7%` (about `32%` lower) at `66 → 35` pages and equal `0.604` recall; stated that `[0.230, 0.811]` lies wholly above `[0.063, 0.105]`; counted train-only series as zero in range recall; used `20–33×`; and attached `1,609 → 80` to IsolationForest rolling+residual rather than the ensemble. |
| TR7, TR11 and R2 §5 comparator/gate rows: hardest-series wording, precision definition, tuning recall cost, comparator switch, HPO versus selection objective, and adoption rule | `reports/nab_tune.json`, `reports/ocsvm_hpo.json`, `reports/metrics.json`, `reports/champion_selection.json` | Replaced “hardest” with the observed missed-window description, defined range precision over labelled-window mass rather than “alerts outside windows,” disclosed IsolationForest tuning's recall costs, kept tuned IsolationForest as the validation/test comparator (`0.1330` / `0.1208`), distinguished HPO objective `0.126` from selection PR-AUC `0.1514`, and stated that adoption needs validation improvement plus one test evaluation—not guaranteed transfer. |
| R2 §6 / roadmap findings: nonexistent demo, wrong fusion failure, missing evidence, and non-gated next step | `apps/showcase-web/src/demos/`, `reports/nab_tune.json`, refinement/ablation artifacts | Removed the false shipped demo claim; the shipped ledger card now points to committed sweep/tuning/refinement records. Corrected fusion to fail coverage (`14/17` or `15/17`) while calibration fails precision, restored the `66 → 35` / `0.388 → 0.533` detail, and made VUS-PR a gated comparison against the 16-seed band on the same nine NAB series. |
| Figure and source labels: alert-budget subtitle and NAB “champion” ambiguity | `src/anomaly_detection/nab.py`, `reports/figures/nab_alert_budget.json`, `reports/figures/nab_timelines.json`, `story.yaml` | Corrected the alert-budget subtitle to NAB groups for IsolationForest only; changed the timeline source and committed JSON title to “NAB test windows vs IsolationForest alerts”; changed the Limits reference from “champion ensemble” to “rank ensemble.” Unrelated synthetic OCSVM champion terminology remains intact. |
| R2 §§1–4 and 7: interpretation and language | The same NAB/synthetic artifacts and current article renderer inputs | Clarified kNN/LOF interpretation, separated threshold-sweep `0.527` from fixed-budget aggregation, and polished transitions/plain-terms wording without changing the evaluation protocol or results. |

## 04 — NLP classification

Review: `opus-round2/04-nlp-classification.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| Round-1 18–19; R2 §5 cascade rows: incorrect upper bound, conflated review count, and plain-terms accuracy overclaim | `reports/llm_cascade.json`, `reports/metrics.json`, paired interval fields | Reported split-specific macro-F1 deltas (`+0.0001` validation, `+0.0030` bounded test, `+0.0010` fresh) and their respective `6` / `16` / `22` reviews. Removed “at most `+0.001`,” detached `44` total reviews from one delta, and framed the cascade as inconclusive where CIs cross zero rather than as a clear accuracy lift. |
| Round-1 20–23, 26–29; R2 §6: HPO/seed conflation, fresh-split scope, full-fit size, and false roadmap cards | `reports/hpo_study.json`, `hpo_seeds.json`, `selection.json`, `fresh_holdout.json`, `params.yaml`, `DESIGN.md` | Separated the 12-trial study from three six-trial seed reruns, identified the fresh draw as coming from the test partition's other `6,600` rows, corrected full-data training to `108k` fit plus `12k` validation, removed the undefined fixed-compute claim, and rewrote both roadmap cards: validation selected HPO, while full-data training uses default settings; the cascade uses raw-softmax selective review of `22/1,000` fresh rows, not calibrated review of a quarter. |
| Round-1 13–17, 24–25; router and serving findings | `src/model.py`, `calibration.py`, `fresh_holdout.json` router cells, `reports/metrics.json` | Named raw max-softmax as the review gate and stated that temperature `T=0.927` is not applied to it; named `kimi-for-coding`, documented the validation tie-break, showed the complete router ladder including τ=`0.6` / `0.9082`, distinguished bounded `110.7` from full-data `112.5` items/s, and replaced the edited code excerpt with the source's actual assignment/log sequence. |
| Round-1 1–12, 30–32 and Tier-3 findings: repetition, definitions, precision, device/scale wording, and transitions | `metrics.json`, `hpo_*`, `fresh_holdout.json`, `results.md`, figure source | Defined HPO at first use, identified the four scale rungs as `3.6k/10.8k/36k/108k`, separated the `0.0002` test and `0.0105` fresh device gaps, expressed the HPO margin as about `1.7` seed SDs with a zero-crossing CI, added calibration ECE `0.0360 → 0.0227`, removed orphan quantization, identified the 20k run as a separate pre-ladder `18k/2k` diagnostic, corrected the stale HPO caption, reduced repeated cascade caveats, and made transitions substantive. |

## 05 — churn ML pipeline

Review: `opus-round2/05-ml-pipeline-churn.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| T5 and new training-size finding: `7,043` versus `5,634`; stale CI diagrams | `reports/operating_policy.json` (`n_train`), `reports/metrics.json`, `reports/sensitivity.json`, `apps/showcase-web/src/diagrams/churnCycle.ts`, `auto/05-ml-pipeline-churn-3.ts` | Limited training to `5,634` rows within the `7,043`-customer panel and synchronized both diagrams to the committed FN=5 interval `−508` to `−353`. |
| T2–T4: wrong feature ranking, nonexistent figure panels, and wrong figure count | `reports/permutation_importance.json`, `reports/figures/eda_churn_profile.json`, `story.yaml` figure list, `README.md` | Corrected importance to tenure `0.213`, contract `0.174`, internet service `0.088`, monthly charges `0.033`; stopped attributing senior/fiber facts to panels that do not exist; and changed “all three figures” to both figures. |
| T1, T6–T7: unsupported `−90 [−159, −26]`, CV cost/search claims, and synthetic-era F1-first story | `reports/metrics.json`, `sensitivity.json`, `data/model_selection.json` (`n_trials: 0`, `best_score: NaN`), `DESIGN.md` | Removed the unsupported interval, CV cost, 25-trial/median-pruning claim, and misattributed F1-first narrative rather than manufacturing new result artifacts. |
| T8 and new serving-scope finding: model width and “automatic quality checks” | `reports/models/serving/meta.json` (`feature_names`, `n_features: 4`), `src/model.py`, `src/serving.py`, `reports/dq_report.md` | **Evidence-backed exception:** the review suggested six features, but the committed serving contract has **four**. The article now distinguishes 21 raw source columns from four served model features. Serving prose describes actual capping/imputation preprocessing; training-only DQ gates are no longer presented as serving-time rejection checks. |
| T9–T11, D1–D4: FN=3 omission, tested-price scope, incentive terminology, calibration details | `reports/sensitivity.json`, `operating_policy.json`, `metrics.json`, `params.yaml` | Added the FN=3 improvement `518 → 514`, limited claims to tested prices `3`, `5`, and `8`, replaced undefined voucher language, explained ROC-AUC `0.8387 → 0.8317` through tied calibrated scores, disclosed the raw base learner's 80% training share, added 10-bin ECE, the 41-point / `0.025` grid, and the close raw/calibrated OOF costs `$2,440` / `$2,425`. |
| S1–S5, E1–E4, L1–L7, R1–R5, G1–G2: repetition, formatting, and roadmap | Current `story.yaml`, `README.md`, `DESIGN.md`, committed policy/CI records | Reduced Results/Limits duplication, made dollar and negative-cost conventions consistent, repaired wrapping/fences/link spacing, restored concrete roadmap evidence and a forward gate, and retained the required article structure without repeating metric dumps. |

## 06 — routing optimization

Review: `opus-round2/06-routing-optimization.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| Round-1 14–15 and new RC202 finding: undercut count and best value | `reports/metrics.json` per-instance ALNS and `alns_fleet` gaps | Corrected the count to five substantive ALNS reference wins, six including `alns_fleet`; labelled C108/C109/C207 (`−0.0004%`, `−0.0004%`, `−0.0006%`) as rounding ties; and reported RC202 separately as `−3.8478%` ALNS and `−5.7898%` fleet. |
| Round-1 4, 16 and new unit finding: reversed fleet logic and `0.07%` distance | `metrics.json` family vehicle/gap summaries, `README.md` reference-objective convention | Explained that fleet-first references minimize vehicles before distance while ALNS minimizes distance; naive solvers can win with fewer, not more, vehicles. Recast `0.07` as percentage points of mean gap, not percent distance. |
| Round-1 18: C101 geography and windows | `reports/figures/eda_instance_map.json` coordinates/window widths | Replaced “one tight cluster” with several groups spread around the depot and stated that every window is narrow (`37–89` within a `1,236` horizon). |
| Round-1 17 and new two-minute claim: runtime scope | `metrics.json` runtime summaries, `README.md` benchmark/HPO/full-stage records | Labelled `130 s` and `13 min` as summed evaluation runtimes excluding tuning where applicable, removed the contradictory whole-search-under-two-minutes claim, and aligned full-stage wording with the committed README. |
| Round-1 19–21: bootstrap contradiction, supplement semantics, and rounding | `metrics.json` (`intervals.mean_gap_pct`), `best_known_supplement.csv`, tuning summaries | Kept per-instance spread distinct from, but no longer contradictory to, the instance bootstrap CI; changed “42 omitted cases” to 42 restored references; and corrected 2-opt HPO improvement from `0.12` to `0.13` points. |
| Round-1 12–13, 22–24; R2 §§6–7: tuning detail, lag explanation, roadmap, and prose | `metrics.json` (`tuning.alns_best`), `params.yaml`, `README.md` C2/C203 analysis | Added segment `100`, reaction `0.5`, uniform initialization, destroy size `10`, and `120` iterations; explained under-diversification on wide horizons and tight-chain resistance; renamed the CP-SAT card away from “tie as goal,” corrected its evidence, and added an explicit next-card gate while reducing formulaic prose. |

## 07 — open-data mobility

Review: `opus-round2/07-open-data-mobility.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| TR1–TR5 and new busy-zone claim: sparse groups, importance, Unknown coverage, delta sign, serving gate, and coverage scope | `reports/figures/borough_mae.json`, `gbm_feature_importance.json`, `p90_calibration.json`, `reports/metrics.json`, `src/mobility/serving.py` | Expanded Bronx-only persistence wins to Bronx, EWR, and Staten Island; made lag_1 dominant (`3.31`, ahead of `2.58` / `2.48`); corrected Unknown to `93.7%` and January ΔMAE to `−34.6%`; removed the nonexistent baseline-win selection gate; and scoped raw `90.8%` coverage to city-wide zone-hours, distinct from dense `89.6% → 90.3%` after adjustment. |
| TR6–TR8 and all 12 untraceable values: second importance summary, tolerance prose, replay-month details, and green row count | Committed `README.md`, `DESIGN.md`, `MODEL_CARD.md`, `reports/green_transfer.json`, and available drift records | Deleted the unsupported second importance ranking and untracked November/December MAPE, coverage, and row counts; removed the ungrounded two-point claim; used about `337k` green training rows; rounded replay/unseen values to committed precision (`5.059`, `5.046`, `4.442`, `59.6%`, `+8.2%`, `+7.9%`, `−5.0%`); and corrected yellow-model MAPE improvement to `−18%`. |
| T1–T4: conformal scope, replay versus unseen drift, January under-coverage, and absent direct CI | `metrics.json` (`conformal`, `paired_intervals`), `README.md` drift table | Stated that offsets are fit on the first test half and are not the raw served quantile; labelled November/December as wiring replays and January 2025 as the only unseen month; flagged January coverage `87.4%`; and retained xGB's `4.1%` lower test MAE versus `gbm_tuned` without implying a committed direct interval. |
| L4–L5 and table omissions: misleading signed wording, “flat within noise,” and missing runs | `metrics.json` run keys and `deltas` | Replaced “improves by −4.1%” with direct lower-error wording; removed “flat within noise” for default/tuned GBM and explicitly noted the absent direct interval; added `gbm_lgbm_tuned` (`4.582`, `14.794`, `59.9%`, `0.747`, `−29.7%`) and `temporal_net` (`5.510`, `19.686`, `54.5%`, `0.899`, `−15.5%`) to the exact table. |
| R2 minor factual findings: heatmap span and omitted weather group | `reports/figures/hour_borough_heatmap.json`, `weather_elasticity.json` | Changed the full heatmap span from two to about four orders of magnitude and added Unknown (`0.90×`) to the `0.89–0.93×` weather group in Results, exact records, and caption. |
| R1–R5, C1–C3, S/E/L language findings: roadmap and plain-terms integrity | `story.yaml`, committed panel/conformal/drift artifacts | Split compound roadmap actions, restored concrete evidence, separated retraining from drift, limited in-window language to MAE, added a gated next step, and removed busy-zone/raw-band overclaims from plain-terms cards. Simplified the serving-selection prose after the factual edits to retain zero language warnings. |

## 08 — inference serving

Review: `opus-round2/08-inference-serving.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| Round-1 23–25: unsupported `10–30×`, causal/build isolation, and committed-status wording | `data/bench_run.json`, committed `data/bench_run_repeat.json`, `reports/metrics.json`, documented Ollama versions | Derived and labelled an approximate `5–35×` p95 slowdown range from the two committed raw runs; disclosed Ollama `0.40.4` versus `0.40.12` and co-tenant load; removed claims that memory bandwidth was proven or a build regression excluded; and said the repeat is committed but outside the aggregate path. |
| Round-1 21–22 and new dense/quality claims: architecture and quantization | `params.yaml` model tags, `README.md`, `DESIGN.md`, `reports/metrics.json`; the review's cited gpt-oss model-card reference | Removed unsupported qwen3:32b full-precision and plain gemma4:31b 4-bit labels. Corrected gpt-oss:20b from dense to MoE and kept quantization explicit only where the model tag/committed record supports it. |
| New plain-terms findings and round-1 26: throughput versus answer time, saturated quality, and reasoning | `metrics.json` latency/tok-s cells, `quality_quant.json`, `params.yaml` (`reasoning_effort`) | Distinguished about `7×` output tok/s from about `6×` p95 answer time, replaced “equal accuracy” with a tie on a saturated schema/keyword check, and recorded reasoning `none` for qwen3.6 but `low` for gpt-oss. |
| Round-1 2, 15–20; table/pointer/detail omissions | `reports/metrics.json`, `params.yaml`, benchmark protocol documentation | Removed the nonexistent Details pointer, called the table selected cells rather than all 19, stated the `128`-token cap and p99=max at `n=40`, added gpt-oss context, described flat throughput as consistent with serialized decoding without claiming an isolated cause, and drew out same-runner QAT-int4 versus Q8_0 (`9.83` versus `6.43` tok/s, about `53%`). |
| License and cost-formula findings | `README.md` model-pull instructions, cost constants and electricity calculation | Stated that prompts are local but downloaded models retain their own licenses. Corrected the electricity formula to divide power-rate cost by throughput in tok/s rather than multiply. |
| Round-1 1, 3–14, 27–32; R2 §§6–7: roadmap and language | Current renderer inputs, `story.yaml`, committed grid/quality records | Restored concrete controls and numerical roadmap details, separated engine/quantization next work, and reduced repetition and broken code spans. **Refutation:** the indented diagram fence is accepted by the actual site renderer; it was normalized for consistency, not treated as evidence of a broken site. |

## 09 — agentic workflows

Review: `opus-round2/09-agentic-workflows.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| Round-1 18–19 and R2 §5: “52 captured calls” | `data/heldout_records.json`, tuning records | Split the ledger into 52 answer-task calls (`30` tuning + `22` held-out), all checked against planned tool sets, plus `20` probe calls graded on refusal rather than planned sets. Corrected both Conclusions and the shipped roadmap card. |
| Round-1 14–15: retry count and p95 interpretation | `params.yaml` (`max_execute_retries: 1`), `data/heldout_records.json`, `reports/metrics.json` task latencies | Changed “both bounded retries” to two Execute attempts with one retry; labelled p95 as nearest-rank over `n=15`, identified t15 at `31.1 s` as the p95 order statistic and t05 at `31.6 s` as slowest, and removed the false “95% finished within” interpretation. |
| Round-1 1, 13 and live-comparison rows: live efficacy and h19 | `collaboration/reviews/20261118-live-confirmation/comparison.md`, `data/heldout_live_records.json` | Replaced “live efficacy is unmeasured” with one live confirmation and an explicit lack of repeated-live evidence; described h19 as a refusal after the calculator guard tripped, not a fabricated numeric answer or unqualified failure. |
| Round-1 2 and provider-mismatch finding: chart attribution and hosted/local comparison | `data/heldout_records.json`, figure data for `cost_latency_bars`, live comparison | Attributed local latency misses to held-out records rather than the tuning-only chart and disclosed that the live rerun ran all 19 tasks hosted, so its `19/19` latency result is not a like-for-like repair of the legacy local misses. |
| Round-1 16–17, 21–26 and new presentation findings: revisions, step counting, roadmap, stale README, and prose | `heldout_records.json` retry/critique fields, workflow implementation, `README.md` | Explained Critique revisions and StepBudget counting, aligned roadmap details with `6/6` refusals and `19/19` budgets, separated retry caps from human approval, added a provider-aware gated next study, corrected the three-step intro/code spans/transitions, and updated stale live-confirmation README wording. |

## 10 — uplift experimentation

Review: `opus-round2/10-uplift-experimentation.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| Round-1 21: Womens/Mens conversion contradiction | `reports/segment_summary.json`, `metrics.json` (`multi_arm.per_arm`) | Stated that both emails raised purchases: Womens `+0.31 pp` with incremental conversions `66.5 [33.10, 104.69]`, Mens `+0.68 pp`; removed “only Mens” and “non-converting email” wording. |
| Round-1 23–26: frame, control rate, grid winner, and planning comparator | `metrics.json` two-arm frame, `segment_summary.json`, `cost_sensitivity.json`, `multi_arm.best_arm_break_even`, `policies.best_arm.profit_full` | Attributed `+$2,812` to the `42,613`-row two-arm frame, corrected control conversion to `0.57%`, replaced the above-`$0.30` outright-win claim with the observed grid ordering and best-share change by `$0.50`, and identified `$49.8k` mail-everyone-Mens as beating best-arm at a 25% budget—not unconstrained best-arm `$66.3k`. |
| Round-1 13 and new net-profit wording: metric identity | `metrics.json`, `DESIGN.md` revenue/cost definitions | Standardized the metric as revenue minus send cost, explicitly excluding COGS and contact fatigue; removed “real net profit” / “net profit” from prose, tables, and plain-terms cards. |
| Round-1 17, 20, 22: duplicate Qini intervals, untraceable T−X row, and nominal ordering | `metrics.json` Qini coefficients and both bootstrap protocols | Removed the unsupported `[−$323, $4,343]` row; explained that the same Mens Qini score `12.0252` has seed-1041 and seed-2041 intervals with lower bounds `+0.77` and `−0.47`; and labelled T-learner versus response-model ordering nominal where ranking is unestablished. |
| Round-1 18 and new sign-flip finding: prediction spread and planning versus observation | `multi_arm.per_arm.mens.deciles`, `multi_arm.ci.pairs`, observed DR policy values | Replaced “2× hot” with an about-twice-too-wide predicted spread and disclosed the best-arm-minus-single-arm reversal: `+$6,027` model-estimated planning value versus `−$2,902` observed DR. |
| Round-1 11, 14–16, 27–32; R2 §§6–7: units, formatting, roadmap, and repetition | `report.html`, `metrics.json`, `cost_sensitivity.json`, current `story.yaml` | Added missing percentage-point units, moved punctuation outside code spans, restored numerical power and break-even roadmap details, changed the next card to a prospective randomized holdout with a gate, and reduced duplicate policy/result presentation. |

## 11 — data engineering

Review: `opus-round2/11-data-engineering.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| Round-1 16–20, 31 and new rush-hour claim: unsourced real-data EDA and EWR-specific ulp story | `reports/metrics.json` groupby/filter results, `src/synthetic.py`, `DESIGN.md`, `apps/showcase-web/src/diagrams/auto/11-data-engineering-3.ts` | Removed unsupported 4 a.m./evening/weekday patterns, `$16` and `$200` fare claims, negative-fare attribution, and rush-hour wording. Replaced them with committed facts: 35 pickup dates, about `95,600` trips/day, and `168,468` rows passing the fare/distance filter. Regenerated the conclusion diagram and generalized the ulp warning instead of tying it to EWR. |
| Round-1 13–15 and SHA-scope finding: parser, task, schema, and hashing descriptions | `src/engines.py`, `src/fetch.py`, `DESIGN.md` task/schema definitions | Limited PyArrow to parquet and described pandas' CSV parser separately; changed “sort distinct values” to top-ten pickup zones by fare with tiebreaks; removed “object-heavy” groupby wording; and limited the SHA-256 claim to the raw download rather than derived CSV/partitions. |
| Round-1 21, 25: sqlite best cell and conversion timing | `reports/results.md`, `reports/metrics.json` | Corrected sqlite's fastest cell to filter at `1.947 s` and described `1.9–5.9 s` as total load-plus-query task time, not separately timed conversion. |
| Round-1 23–24: memory ratios and caption | `reports/results.md` memory cells | Replaced a blanket `2–3×` claim with measured task-dependent ratios/ranges, including exceptions, and corrected the caption to Polars `200–529 MB` and DuckDB `178–633 MB`. |
| Round-1 1–12, 22, 26–30; R2 §§6–7: roadmap and language | `reports/evaluation_metadata.json`, slope tables, parity records, current `story.yaml` | Restored `39/39` and scaling-slope evidence, clarified the roadmap titles and ten-million-row gate, preserved the already-fixed cold-read wording, and polished transitions/repetition while retaining the benchmark tables. |

## 12 — tabular ML lifecycle

Review: `opus-round2/12-tabular-ml-lifecycle.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| Round-1 14–15, 21: residual bias, holiday slice, and heatmap sign | `reports/metrics.json`, `reports/figures/residual_vs_fitted.json`, `residual_heatmap.json`, `src/tabular_ml_lifecycle/figures.py` | Replaced “no global bias” with mean residual `+9.2` overall and `+28.6` for fitted `300–600` (`actual − fitted`, hence under-forecast); named the late-December holiday window; and made red=over-forecast / blue=under-forecast consistent in source, captions, and regenerated figures. |
| Round-1 16–17, 20, 28: seasons, epoch count, timings, and hardware form factor | `rentals_by_hour_season.json`, `mlp_loss_curves.json`, `reports/evaluation_metadata.json` | Corrected the labelled panels to spring lowest and winter near summer, explained the UCI season-code quirk, changed training to 57 epochs with best epoch 47, corrected timings to `44.4 s` / `13.3 s`, and removed the unrecorded “laptop” form-factor claim. |
| Round-1 18–20, 25, 27 and new confirmation overclaims: ablations, run IDs, precision, and evidence roles | `reports/results.md`, `reports/metrics.json`, `evaluation_metadata.json`, `ablation_dotplot.json`, `learning_curves.json` | Removed “within noise” for dropout and reported the `2.1` validation-MAE dropout-off changes without inferential overclaim; kept early-stopping evidence in the ablation rather than learning curves; called block intervals sensitivity analyses; pointed to `_meta.git_sha` rather than nonexistent run IDs; removed unsupported `50/50` and all-at-cap claims; and restored committed precision `88.7`, `68.9`, `39.5`, and `25.0`. |
| New MI-pruning finding and round-1 12–13: correlated-pair rule and interpretation | `reports/feature_selection.json`, `src/tabular_ml_lifecycle/features.py`, `params.yaml` | Documented actual behavior: `atemp` was dropped despite MI `0.1645 > 0.1578` for `temp`. Corrected the config/docstring/comment/figure language to stop claiming lower-MI pruning. **No pruning logic, selected feature set, model, or score was changed**, because changing the comparison would require a fresh experiment and refreshed artifacts. Added the missing architecture/search context and qualified the ridge permutation probe and ablation uncertainty. |
| Round-1 22–24 and `34.397`: learning-curve and importance-order claims | `learning_curves.json`, `feature_selection.json`, permutation-importance records | Removed claims that both learners flatten or that row count is the immediate ceiling, separated the training-loss plateau from continued validation behavior, and stated that MI and permutation agree on the set but not the lag ordering. **Review exception withdrawn:** LightGBM validation `34.397` is traceable to `learning_curves.json` at fraction 1.0 (`34.3968`), so it was retained. |
| Round-1 1–11, 29–32; R2 §§6–7: champion label, roadmap, figures, and language | `metrics.json`, current report/article/figure sources | Removed the unsupported champion designation, restored `25.4` versus `83.2` and block-bootstrap roadmap evidence, added concrete deferred work, reduced duplicate tables/CI repetition, and regenerated six figure JSON/HTML pairs: `rentals_by_hour_season`, `mi_lollipop`, `mlp_loss_curves`, `learning_curves`, `residual_heatmap`, and `residual_vs_fitted`. |

### Project 12 report-builder limitation

`build_report()` cannot currently rebuild the checked-in report from the provenance-stamped `reports/metrics.json`: its `_meta` no longer contains the legacy report-only champion/CI/ablation fields expected by the assembler. A direct assembly attempt produced `None`/`nan`; that output was discarded. The committed `report.html` and `results.md` were restored from `HEAD`, then only verified display text and the “Champion” label were replaced. `src/tabular_ml_lifecycle/report.py` now uses truthful validation-selected wording, but the pre-existing metadata incompatibility remains a deliberate follow-up rather than being hidden by fabricated fields or a model rerun.

## 13 — model serving

Review: `opus-round2/13-model-serving.md`.

| Findings | Committed evidence checked | Resolution |
|---|---|---|
| Round-1 11–12, 14 and new bike-unit claim: tolerance and output spaces | `reports/metrics.json` (`parity`), `src/artifacts.py` tolerance implementation, project 12 dataset metadata | Added the exact tolerance formula, replaced “three orders” with about `140×`, and distinguished max-abs `7.152557e-07` in standardized space from `0.000123667` on the rentals scale. Removed “less than one-millionth of a bike” and stated that parity is against the native model. |
| Round-1 15: batch p50 column held means | `reports/metrics.json` ONNX batch latency fields | Replaced the means with actual ONNX batch p50 values `65.1`, `48.5`, `51.0`, and `65.3 ms` for batch sizes `1`, `8`, `32`, and `128`. |
| Round-1 17–21 and single-backend c64 finding: unscoped ties and mixed-backend numbers | `reports/metrics.json` native/ONNX concurrency and batch cells | Limited tie/within-noise/≤`3.6%` statements to concurrency cells; disclosed batch spreads (`+15.4%` at b8, `+11.2%` at b32 ONNX; `+12.5%` native at b1); used `1.6 ms` single-request p50; separated native/ONNX p95 (`2.0/1.9 ms`), concurrency-4 throughput (`932.5/970`), and c64 p95 (`0.249/0.210 s`). |
| Round-1 22: inferred environment composition | `Dockerfile.slim`, `reports/docker_slim.json`, committed image-size fields | Marked torch/CUDA composition as an inference from the full-versus-slim venv delta (`6,192 MB` versus `149 MB`), not a per-package measurement. |
| Semantic MAE wording and frame-hash finding | `reports/metrics.json`, `reports/train_run.json` (`frame_sha256`), `projects/12-tabular-ml-lifecycle/data/dataset_contract.json` (`checksum_sha256`) | Replaced “accuracy” with MAE/error terminology. **Review exception resolved on re-check:** the frame hash `42adb7aa…` matches project 12's committed dataset contract, so the identical-frame statement was retained. |
| Round-1 1–10, 13, 23–25; R2 §§6–7: roadmap and language | Current `story.yaml`, `README.md`, committed parity/image/latency records | Restored numerical parity and slim-image roadmap details, added an explicit paired-rerun gate, qualified the c16 throughput sag as a contention observation rather than a proven cause, and reduced glossary/repetition issues while preserving the required article structure. |

## Cross-surface synchronization

Regenerated the static registry, story short-copy map, and route manifest. Synchronized changed summaries across the root README, docs project index, and individual docs pages. Shortened over-limit project 09 and 13 summaries and synchronized copied text for projects 05 and 07. All temporary codemods were removed.

No commit, push, or merge was performed. Final gate and workspace-audit results follow below.

## Final verification

All commands below were rerun after the last article, figure, source, and generated-surface edits.

| Gate | Final result |
|---|---|
| `gen_static_registry.py` then `--check` | Wrote and verified 14 projects / 2 demos; static registry is current. |
| `gen_story_short.py` then `--check` | Wrote and verified 14 stories / 0 missing `short_version`; story short map is current. |
| `gen_route_manifest.py` then `--check` | Wrote and verified 28 routes; route manifest is current. |
| `lint_story_language.py` | **14 stories, 0 errors, 0 warnings.** |
| `check_headline_numbers.py` | **13 claims checked, 0 findings; OK, no unknown drift.** |
| `check_short_copy.py --check` | **42 surfaces across 14 stories; single-sourced.** |
| `check_docs.py` | **OK.** |
| `check_demo_contract.py` | **OK** for both demos and the static registry snapshot. |
| `ruff check .` | **All checks passed.** |
| `ruff format --check .` | **963 files already formatted.** |
| `mypy libs projects apps` | **Success: no issues found in 266 source files.** |
| `mkdocs build --strict` | **Passed; documentation built in 0.48 s.** Existing nav-information messages and the Material for MkDocs 2.0 announcement are non-fatal. |
| `showcase-web`: `npm test` | **56 test files and 754 tests passed.** |
| `showcase-web`: `npm run lint` | **Passed.** |
| `showcase-web`: `npm run build` | **TypeScript and Vite production build passed.** Existing chunk-size warnings are non-fatal. |

The web test run also retains existing React `act(...)` warnings and intentional ErrorBoundary test logs; neither caused a failure.

## Workspace audit and stop state

- `git diff --check`: passed with no output.
- `git diff --name-only -- projects/01-rag-agent projects/15-dynamic-pricing-rl`: empty; both excluded projects are untouched.
- `HEAD`, `main`, and `merge-base(HEAD, main)` all resolve to `c05accd096ee2209bc7bb8362aa15bf3ec171fc5`; no Wave 8 commit exists.
- No `_wave8_*.py` helper files remain.
- Existing untracked design/review inputs are preserved alongside the new closeout.
- Stop state: uncommitted working tree on `wave8-articles-truthfulness-2026-11-25`, with no push or merge, ready for owner and Claude verification.
