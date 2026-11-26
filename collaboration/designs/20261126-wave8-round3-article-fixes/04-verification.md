# Round-3 pre-edit verification

Every item was checked against the current working tree before its edit. Line numbers refer to the pre-edit files; the closeout records final locations.

| Item | Status | Current-tree evidence |
|---|---|---|
| 1 | VERIFIED | `reports_m5_full/figures/*.json` still contain the earlier M5 scores and titles; `metrics.json` carries the `0.6211` champion. |
| 2 | VERIFIED | `demo_payload.json` and `catalog_meta.json` carry the earlier blend; `demo.yaml`, `ForecastWorkbench.tsx` and generated registry show `0.6161`. Offline payload generation failed its catalog/ensemble integrity guard, so the disclosure fallback applies. |
| 3 | VERIFIED | Selection weights are already `0.95/0.00/0.05`, but `m5Pipeline.ts` and auto diagrams still say the test was scored only once despite the disclosed challenger reread. |
| 4 | VERIFIED | Story lines 79, 145, 155, 159, 179 and the next-card gate retain the reviewed wording; `auto-02-demand-forecasting-5.ts` recommends weekly reforecasting. |
| 5 | VERIFIED | Background embeds `04-routing` while its bullets describe the full-data cascade in `auto-04-nlp-classification-3.ts`. |
| 6 | VERIFIED | `auto-04-nlp-classification-2.ts` routes the shared test set into “Model selection · biased by design” and omits the scale-ladder branch. |
| 7 | VERIFIED | Story lines 157–160, 213–214 and 433–434 do not scope temperature `T=0.927` to the bounded selected model. |
| 8 | VERIFIED | Story lines 245–247, 310–312 and 346–348 describe raw/calibrated branches rather than the preprocessing DAG; the categorical node omits `internet_service`. |
| 9 | VERIFIED | `auto-05-ml-pipeline-churn-3.ts` orders holdout scoring before threshold selection. |
| 10 | VERIFIED | `churnCycle.ts` and README retain the unsupported 25-trial claim; the hero says “601 cost units”; story lines 132–133 contain audit wording. |
| 11 | VERIFIED | Story lines 217, 225, 241 and 284 retain the reviewed fairness and bootstrap labels. |
| 12 | ALREADY FIXED | Current story consistently uses `7,043` total customers and `5,634` training rows; no conflicting training-size statement was found. |
| 13 | VERIFIED | Story lines 307–308 and 355–357 call the tuned-versus-default change `−0.2%` even though `4.676` is worse than `4.667`. |
| 14 | VERIFIED | The map caption says “JFK/EWR” and EDA says “two airports”; `zone_demand_map.json` identifies JFK and LaGuardia as the high-demand airports. |
| 15 | VERIFIED | Background and Data plain-terms cards call the GHCN-Daily input hourly weather. |
| 16 | VERIFIED | The shipped “Calibrate the demand upper band” card advertises test-half adjustment instead of the shipped raw-band coverage measurement. |
| 17 | VERIFIED | The `20%` target is asserted in Objectives without a committed DESIGN requirement. |
| 18 | VERIFIED | Story lines 183–187 use “flat-to-declining”; the repeat-file claims are present and owner option (b) is settled. |
| 19 | VERIFIED | Story lines 219, 330 and 352–354 retain the throughput-champion, causal conversion and inconsistent quantization wording. |
| 20 | VERIFIED | `nab_sweep.json` gives ensemble minute PR-AUC `0.566–0.577` and singles `0.515–0.574`; story line 95 uses the wrong lower bound. |
| 21 | VERIFIED | Both anomaly diagrams and README say the three train-only series are excluded; committed protocol counts them as zero. |
| 22 | VERIFIED | The hero omits rank averaging although the adjacent bullets describe it; `auto-03-anomaly-detection-3.ts` says “deployed artifact”. |
| 23 | VERIFIED | Story lines 62–64, 74, 98, 125, 139, 141 and 143 retain staccato or reviewer-rebuttal wording. |
| 24 | VERIFIED | Conclusions still has a separate Results summary; lines 91, 224, 232 and 249–250 retain the reviewed labels and protocol wording. |
| 25 | ALREADY FIXED | The roadmap advertises committed ledgers, not an anomaly demo; no anomaly demo exists under `apps/showcase-web/src/demos/`. |
| 26 | VERIFIED | Story lines 50–52 and README over-attribute the fleet gap to objective convention despite `alns_fleet` moving only `+3.73` to `+3.66`. |
| 27 | VERIFIED | The five-undercut count omits the three `−0.00%` rounding ties named in `reports/results.md`. |
| 28 | VERIFIED | Fixed ALNS parameters are presented as HPO choices; Conclusions repeats earlier results, transitions are formulaic, and Background rounds `3.73` to roughly four. |
| 29 | VERIFIED | Story lines 21 and 34 attach the `~$0.13` tuning-suite cost to held-out runs. |
| 30 | VERIFIED | Story lines 206 and 373 present gitignored placeholder checkpoint data as a recorded run; committed `tests/test_hitl.py` is the valid evidence. |
| 31 | VERIFIED | Story lines 11 and 292 call the rounded-index percentile “nearest-rank”; `report.py` uses the rounded-index method. |
| 32 | VERIFIED | `StepBudget`, critique revision and `StepTrace` mechanics are absent from the cited passages. |
| 33 | VERIFIED | Story line 325 has four extra leading spaces on the T-learner−random row carrying `[+$718, +$4,767]`. |
| 34 | VERIFIED | Background, Evaluation, Conclusions, key concepts and the roadmap describe the cost threshold inconsistently. |
| 35 | VERIFIED | Story lines 118–121 repeat the Mens effect and contain the garbled interval sentence. |
| 36 | ALREADY FIXED | No T−X CI `[−$323, $4,343]` remains in the current story. |
| 37 | VERIFIED | The revenue-minus-send-cost phrase and policy tables are still duplicated; CUPED remains in Training. |
| 38 | VERIFIED | Story lines 102–107, 236–237 and 305 contain reader-facing audit/repository wording. |
| 39 | VERIFIED | The story says conversion is not timed separately but subsequently attributes sqlite cost to import/conversion as fact. |
| 40 | VERIFIED | Short and Background copy omit the `1,658`-trip parity catch. |
| 41 | VERIFIED | Line 263 says file size instead of row count; line 396 says “All 39/39”; the cold-cache gate is not aligned with the bigger-than-RAM deferred track. |
| 42 | VERIFIED | Story, README, DESIGN and `feature_selection.json` retain the January-only attribution and one-hour lag claim; committed review evidence identifies the 36-hour October 2012 validation gap. |
| 43 | VERIFIED | The cited story lines retain process hedges; `params.yaml` commits `max_epochs: 150`; no pre-registration artifact exists. |
| 44 | VERIFIED | The season-code shift, residual lesson and validation-MAE-plus-residual roadmap gate are absent or imprecise. |
| 45 | ALREADY FIXED | No surviving “no global bias” claim was found; the story reports mean residual `+9.2`. |
| 46 | VERIFIED | Candidate tables and conclusions are duplicated and Conclusions is not in gold order. |
| 47 | VERIFIED | Story lines 189, 213 and 285 say at most `3.6%`; `metrics.json` and the slope figure give a c4 p50 ratio of `0.960`. |
| 48 | VERIFIED | The slope caption says `0.97–1.04` instead of `0.96–1.04`. |
| 49 | VERIFIED | CPU contention is asserted at lines 177, 207, 345 and 391, and the batch caption says queue-dominated despite the measurement caveat. |
| 50 | VERIFIED | Line 207 generalizes ONNX-only `63 ms`; the image key concept claims unmeasured torch/CUDA component measurements. |
| 51 | VERIFIED | The batch table is correctly headed `p50`; image and cost are retold in Conclusions and need trimming. |
| 52 | VERIFIED | The review-specific process sentences documented in items 23, 38 and 43 remain. |
| 53 | VERIFIED | Formulaic verbless transitions remain in projects 06, 09, 10, 11 and 12. |
| 54 | VERIFIED | Inline definitions that interrupt sentences remain, including projects 06, 09 and 12. |
| 55 | VERIFIED | Most plain-terms cards are single-sentence takeaways; projects 09 and 13 still contain number-list-style cards targeted by their reviews. |
| 56 | VERIFIED | Regeneration is required for M5 figures, generated registry/copy/routes, and any other generated surface affected by these edits. Auto diagram TS files have no remaining Mermaid source fence and are maintained source artifacts after one-time conversion. |
| 57 | VERIFIED | The final closeout must map each changed claim to its committed evidence and final gate. |
