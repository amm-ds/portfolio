# Grades pass 4: plan to bring every project to 9

Date: 2026-11-26 · Author: Claude (review/design lane) · Base: `main` at `acf6f9f7` plus the uncommitted pass-2 edits.
Inputs: `20261126-post-deploy-grades/00-grades.md` (original grades), `20261126-grades-pass-2/00-pass.md` (pass 2), `20261126-grades-pass-3-plan/00-plan.md` (pass 3 plan; this document supersedes its §1, §2 and §7 and reuses its P0–P3 item specs by reference).

This is a plan only. No repo file was edited except this one. No git mutation, experiment, training, refit, benchmark, hosted or paid call was run. Reads used: `story.yaml`/README/docs text, committed `metrics.json` and figure JSON titles, `git`-free greps.

## 0. The arithmetic, and what it implies

- Overall = mean of C/R/T/V, rounded to one decimal. **9.0 needs an axis sum of 36.** A sum of 35 is 8.75 → 8.8.
- Results is 9 almost everywhere. So 9.0 needs **C9 + T9 + V9**, or a 10 somewhere to offset an 8. This plan does not assume any new 10s.
- Consequence: a project with a hard T8 ceiling (08 on one host, 12 with its headline kept) **cannot honestly reach 9.0**. Its ceiling is 8.8. §5 states this and the article wording.

## 1. New facts found in this pass (they change the plan)

1. **A stale number on a first-contact page.** `docs/projects/index.md:14` (02 "Pinned:") says "ensemble official WRMSSE **0.6161**". The scored blend is 0.6211. 0.6161 is the earlier demo blend. This is a truth-in-copy defect, not style.
2. **Two different "0.527" numbers in 03.** `nab_metrics.json` has `overall.pr_auc = 0.5271` and `pa_k_2_precision_interval.point = 0.5274` (macro range precision at the 2% budget, k = 2). The background (`story.yaml:8`) uses 0.527 as PR-AUC. The conclusions (`:167`) use 0.527 as "threshold-sweep precision" with the CI [0.230, 0.811]. A reader will think they are one number.
3. **Same point, two opposite interval verdicts in 10.** The T-learner score 12.03 has CI [0.77, 24.39], which excludes zero (two-arm table, `story.yaml:325`, seed 1041). The same 12.03, shown as "Mens per-arm AUUC", has CI [−0.47, 24.21], which spans zero (`:243`, multi-arm seed 2041). The article never says these are the same score under two resampling protocols.
4. **07's served model has no committed interval.** `paired_intervals` covers only `gbm_lgbm_tuned` and `gbm_xgb_tuned` against naive. The served `gbm_tuned` (4.676 vs 6.517, −28.25%) has none. The story admits this (`:376-378`). The p90 coverage 0.908 sits in `_meta`, which the stamp overwrote (`evaluate.py:920-933`). That is why it survives only in figure JSON. 07 has the same `_meta` clobber as 10.
5. **06 says both 5 and 8 for one count.** "Beats published references on 5 of 56" (`story.yaml:279,385,367`) excludes three −0.00% rounding ties. The `gap_pct` title (`figures.py:47`) and `docs/projects/06-routing-optimization.md:57` ("eight") include them. Also, "beats" is wrong under the vehicles-first convention, because every one of those plans uses more trucks.
6. **Root README overclaims reproducibility.** `README.md:8-9` says "Every number in the showcase re-runs from a clean clone." That is false for:
   - 01/04/09: they need a model endpoint and are not bit-reproducible;
   - 08/13: they need the same hardware class;
   - 02: its full run took 1,348,530.6 s, about 375 CPU-hours.
   The Stack table (`README.md:17-28`) is also stale. For example, `pytorch` is listed for "02, 04, 07" but not 12/13, and LightGBM, DuckDB, ONNX Runtime and SB3 are missing.
7. **"Champion" is still on first-contact surfaces:**
   - `README.md:36` (alt text "champion alerts");
   - `README.md:56` and `docs/projects/index.md:25` (13 data cell "Champion MLP re-derived");
   - `docs/projects/index.md:24` (12 Pinned "champion tabular MLP");
   - 03 figure titles `telemetry_flags` ("Champion flags") and `range_pr` ("champion vs a 16-seed random band").
8. **Overclaims in docs openings:**
   - `docs/projects/08-inference-serving.md:23` says "the numbers describe real traffic, not a lab proxy". It is a fixed 8-prompt synthetic task.
   - `docs/projects/07-open-data-mobility.md:13` says "90.8%-calibrated p90 staffing band", but no-borough zones reach only 84.7%.
   - `docs/projects/10-uplift-experimentation.md:16` says the "ranking established by paired-bootstrap CIs". The story says the response-vs-T ranking is *not* established.
9. **The axe failure has a single likely cause.** `apps/showcase-web/src/lib/markdown.tsx:217` wraps every markdown table in `<div className="table-scroll">`, which is `overflow-x: auto` in `styles/tokens-base.css:423-426`. The div has no `tabIndex`/`role`/label. Code blocks already have them (`markdown.tsx:303-309`). `DataTable.tsx:10` and `FigureCard.tsx:308` use the same unlabeled wrapper. The 09 page and the document-intelligence article are the routes in `scripts/axe_check.mjs:30-41` whose tables overflow at mobile width.
10. **Committed data already supports a 02 stability statement.** `selection.*.official_wrmsse_per_origin` shows the blend beat the seasonal-naive floor at **all 9 selection origins, by 23.6% to 41.6%**. Those origins chose the members and weights, so this is not an independent test, but it is a stated, honest spread.

## 2. Score table: now → projected

`C/R/T/V → overall`. "Now" is after pass 2 plus the pass-3 Phase 0 items. "Projected" assumes every item in this plan for that project lands as described.

| # | Now (post pass 2) | Main cap | Projected | Confidence |
|---|---|---|---|---|
| 01 | 8/9/8/8 → 8.3 | C jargon; T single judge family; V titles | 9/9/9/9 → **9.0** | Medium. T9 depends on cross-family agreement. If κ is low, R drops to 8 → 8.8 |
| 02 | 8/9/8/7 → 8.0 | V stale-blend figure; T no CI, demo not regenerable | 9/9/9/9 → **9.0** with refit E9. **8.8** without (C9/R9/T8/V9) | Medium-low. The refit cost is an estimate |
| 03 | 8/9/8/8 → 8.3 | T no official NAB score; C 0.527 collision; V champion titles | 9/9/9/9 → **9.0** | Medium. NAB adapter effort |
| 04 | 7/9/8/8 → 8.0 | C glossary asides; T no paired cascade CI | 9/9/9/9 → **9.0** | Medium-high |
| 05 | 8/9/8/8 → 8.3 | T one split, CI excludes selection; V titles | 9/9/9/9 → **9.0** | Medium |
| 06 | 9/9/9/8 → 8.8 | V titles and the 5-vs-8 count | 9/9/9/9 → **9.0** | High |
| 07 | 9/9/8/8 → 8.5 | T no CI on served model; coverage not in metrics | 9/9/9/9 → **9.0** | Medium. Needs the curated test frame on disk |
| 08 | 8/9/6/8 → 7.8 | T saturated quality, no quant-matched pair, one host | 9/9/8/9 → **8.8** on one host. 9.0 only with a second host | Medium |
| 09 | 8/9/8/8 → 8.3 | C "legacy" jargon; T single runs | 9/9/9/9 → **9.0** | Medium. If repeats fail, the copy changes; T9 still holds |
| 10 | 8/9/8/7 → 8.0 | V `qini_per_arm`; T CIs in HTML only; C 12.03 two-interval confusion | 9/9/9/9 → **9.0** | High |
| 11 | 9/9/9/8 → 8.8 | V two non-finding titles | 9/9/9/9 → **9.0** | High |
| 12 | 8/9/7/8 → 8.0 | T known pruning and lag defects in the committed run | **8.8** if the headline is kept (option A). **9.0** if replaced (option B) | Medium |
| 13 | 8/9/9/8 → 8.5 | C stale "Champion MLP" cell, non-finding leads; V titles | 9/9/9/9 → **9.0** | High |
| 15 | 9/10/9/8 → 9.0 | V browser check of the diagrams | 9/10/9/9 → **9.3** | High |

Portfolio end state:
- 12 of 14 at 9.0 or more.
- 08 at 8.8 (single host).
- 12 at 8.8 (option A) or 9.0 (option B).
- With a second host and option B, all 14 reach 9.0.

## 3. Phase order

1. **Phase A, blockers (no compute).**
   - Commit pass 2, restamp, axe fix, CI green, redeploy, fence gate.
   - Spec: pass-3 P0.1/P0.2. The axe fix spec is refined in §3.1.
2. **Phase B, Contents (no compute).** §4, Contents block per project, plus the root README and docs index (§4.0).
3. **Phase C, Visualizations (no compute).**
   - Generator title edits.
   - Data byte-equal rebuilds, or a targeted JSON title patch where a full rebuild would rerun models.
   - The 10 axes gate and the 02 move-or-drop decision.
   - Spec in §4; mechanics in §3.2.
4. **Phase D, experiments.**
   - D0: move analysis out of `_meta` (pass-3 P1.0, now including 07). This is a prerequisite for D1.
   - D1: CPU minutes (E1–E5).
   - D2: hosted, $5 cap (E6–E8).
   - D3: long, hardware or headline-moving (E9–E12).
   - Each experiment ends with a copy patch to the sentences listed under its project.

Phase B is written against today's evidence. Where an experiment later adds a CI or a score, the project's "after E-n" line names the exact sentences to update. Phase B must not pre-announce results.

### 3.1 Phase A refinement: axe fix
- `apps/showcase-web/src/lib/markdown.tsx:217`: give the wrapper `role="region"`, `tabIndex={0}` and `aria-label={\`Table: ${header.map(stripMd).join(", ").slice(0, 80)}\`}`. Mirror the code-block pattern at `:303-309`.
- `components/DataTable.tsx:10`: add an `ariaLabel` prop (required) and the same three attributes.
- `components/FigureCard.tsx:308`: add `aria-label={\`Data table for ${name}\`}` and the same attributes.
- Add a vitest case asserting that every `.table-scroll` has `tabindex="0"` and an accessible name.
- Then run `node scripts/axe_check.mjs` locally at mobile width, dark and light. The target is 0 `scrollable-region-focusable` findings.
- Release-artifact check: fixed by the restamp of 02 and 09 in P0.1 (both errors are `_meta is not an object`).
- Cost: none. App code, so owner-assigned.

### 3.2 Phase C mechanics (the same for every retitle)
- The title text lives in the generator. Change the string there; the generator stays the source of truth.
- Rebuild without rerunning models in one of two ways:
  - (a) call the figure function on committed data, as pass 2 did for 12 `bootstrap_ci` and pass 3 for 10 `qini_per_arm`;
  - (b) where the function needs model objects not on disk, patch only `layout.title` in the committed JSON and add a test asserting that the generator's title string equals the committed title.
- In both cases, `data` must stay byte-equal. Check it with a JSON diff that excludes `layout`.
- Re-render a docs PNG only where `docs/projects/*.md` embeds that figure (`scripts/export_readme_figures.py:render_png`). Check it visually.
- Titles state the finding in ≤ 90 characters. Caveats go in the subtitle. Every number must already be in the figure data or `metrics.json`. Where this plan gives a template (`<x>`), read `x` from the figure JSON. Do not take it from this plan.
- Gates: `check_figure_axes`, `check_figure_budget`, `gen_static_registry --check`, `check_headline_numbers`, `mkdocs build --strict`.

## 4. Per project

Line numbers are at the working tree on 2026-11-26. "Why" codes:
- **CL**: clarity;
- **PL**: plain language;
- **LIM**: stated limit;
- **BL**: baseline;
- **NEG**: negative result;
- **PROC**: review-process wording;
- **TRU**: factual error or overclaim.

### 4.0 Root README and docs index (the first contact for every project)

| Passage | Now | Should say | Why |
|---|---|---|---|
| `README.md:8-9` | "Every number in the showcase re-runs from a clean clone." | "Every headline number is read from a committed artifact and checked in CI. Most pipelines re-run from a clean clone; the LLM projects (01, 04, 09) need a model endpoint, 08 and 13 need comparable hardware, and 02's full run takes about 375 CPU-hours." | TRU, LIM |
| `README.md:17-28` Stack "Where" column | stale | Add 12/13 to `pytorch`, 10/12/13 to `scikit-learn`, 09 to `pydantic-ai`, 11 to `polars`. Add rows: `lightgbm` (02, 05, 07, 12), `duckdb` (11), `onnxruntime` + Docker (13), `stable-baselines3` (15). Check against each `pyproject.toml`. | TRU |
| `README.md:34` | "S3 hybrid wins the sealed tournament" · "897 alerts vs labelled windows" | "Hybrid retrieval lifts recall@5 from 0.924 to 0.946" · "Six of nine NAB series: 897 of 1,609 alerts vs labelled windows" | CL, BL |
| `README.md:36` alt text | "champion alerts" | "IsolationForest alerts" | PROC |
| `README.md:56`, `docs/projects/index.md:25` (13 Data cell) | "Champion MLP re-derived…" | "Project 12's served MLP, re-derived from its committed recipe (UCI Bike Sharing hourly)" | PROC |
| `docs/projects/index.md:13` 01 Pinned | "…judge sample audit 30/30 owner-labelled" | "…the judge agreed with all 30 hand-labelled checks" | PROC, PL |
| `docs/projects/index.md:14` 02 Pinned | "ensemble official WRMSSE 0.6161 vs 0.8929" | "ensemble official WRMSSE 0.6211 vs 0.8929" | **TRU** |
| `docs/projects/index.md:15` 03 Pinned | "…OCSVM's marginal adoption fails to transfer — the measured limit of 6-window validation" | "…tuning a second detector did not hold up on six validation windows, so the default stays" | PL |
| `docs/projects/index.md:21` 09 Pinned | "…the local-provider wave meters $0.00 but breaks…" | "…a local-model run costs $0.00 but misses the 60 s deadline on 7/9 tasks" | PROC, PL |
| `docs/projects/index.md:24` 12 Pinned | "champion tabular MLP" | "served tabular MLP (validation-tied with LightGBM)" | PROC |
| Short-version cells for 01, 03, 09 | see the projects | generated from `short_version`; `check_short_copy.py` enforces it | |

Hand-written "Pinned:" lines are not gated. Add them to `check_headline_numbers.py` claims for 02 (0.6211) at least. Cost: none.

### 01 RAG agent: 8/9/8/8 → 8.3. Cap: C (insider tags, "owner" wording, one confusing bullet); T (single model family); V (three non-finding titles, ladder y-window)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `story.yaml:2` (`short_version`, and the 4 surfaces through `check_short_copy`) | "Cited question answering over 593 Wikipedia articles. Hybrid search finds a correct passage in the top five 94.6% of the time (recall@5 0.946). Final 120-question test: F1 0.9091, precision 0.952, one unsupported answer. The judge agreed with all 30 hand-labelled checks." (≤ 280 chars. Keeps the gated `0.9091` and `0.946`.) | PL, PROC |
| `README.md:44` "Stack:" text | Drop `final_v3`, `judge_v2`, "S3", "owner-labelled". Write: "pydantic-ai agent, hybrid FAISS+BM25 retrieval with reranking, per-claim verification, per-phase cost metering" | PL |
| `story.yaml:16` (background Outcome bullet) | "**Outcome (`n = 120`):** `104` answered or refused correctly (`F1 0.9091`); `1` kept an unsupported claim. One model family wrote, checked and graded the answers, and the set was read four times, so treat this as an upper bound." | CL, LIM |
| `story.yaml:177` (over-caution bullet) | "**Most misses were silence, not false claims:** 14 of 16 misses came from saying too little (10 empty answers to answerable questions and 4 refusals forced by the tool budget); 1 was a search miss and 1 an unsupported claim." Recount from `f1_summary.json` before writing. | CL |
| `story.yaml:154,157,161,209,281` | "owner" → "the author" or "hand-labelled"; "blind owner audit" → "blind hand check" | PROC |
| `story.yaml:209` (Limits) | Add the end-to-end comparator: "Against dense-only retrieval (R0) the hybrid lifts recall@5 0.924 → 0.946 on the same set; no end-to-end F1 for R0 is committed, so the F1 gain from hybrid search is not measured." | BL, LIM |
| `docs/projects/01-rag-agent.md:21-24` | Drop "Per ADR-0004 (amended)" from prose; keep it as a link at the end of the paragraph | PL |
| `docs/projects/01-rag-agent.md:190-198` | Replace with: "The author hand-labelled 30 judged claims without seeing the judge's labels; the judge agreed on all 30 (Wilson 95% [0.887, 1.0]). Set C failed because the verifier crashed, not because of answer quality." Move the "2026-11-23 SOTA ladder superseded…" history to `DESIGN.md` (repo rule: present last results only). | PROC, PL |

**Results.**
- The headline F1 0.9091 already has Wilson intervals on accuracy and faithfulness.
- The missing baseline is an end-to-end R0 F1. Do not run it: `final_v3` is consumed. State the limit (above).
- After E8, add one sentence to Results and Limits (`:208-209`): "A second judge from a different model family scores F1 `<x>` on the same answers (agreement κ `<k>`)."
- The headline stays 0.9091 either way.

**Technologies.** E8, the cross-family re-grade of the committed `final_v3` answers. About $0.94–1.88 plus $0.15 calibration, cap $2.50 (spec: pass-3 P2.3). That is the smallest step to T9.

**Visualizations** (`src/rag_agent/figures.py`, rebuilt from committed `reports/metrics.json` and traces):

| Figure | Generator line | New title |
|---|---|---|
| `chunk_size_sweep` | `figures.py:149` | "200-token chunks give the best recall@5 (0.831) on 65 tuning questions". Fix the subtitle: "65 golden" → "65 tuning". |
| `model_comparison` | `figures.py:202` | "`<best encoder>` leads recall@5 on 65 tuning questions; lexical floor 0.677". Fix the subtitle: "golden" → "tuning". |
| `failure_taxonomy` | `figures.py:360` | "Misses are mostly silence: 10 empty answers vs 1 unsupported claim (n = 120)" |
| `eda_corpus_composition` | `figures.py:310` | "`<top topic>` holds the most articles; long pages capped at 12k characters" |
| `retrieval_ladder` | its builder | Set the y-range to data span ± 10% (axes gate 15.1× and 4.5×). Title: "Hybrid retrieval (S3) lifts recall@5 from 0.924 (R0) to 0.946 on the final set" |

Docs PNG: `docs/assets/readme/rag-retrieval-ladder.png` (re-render).

**Projection.** 9/9/9/9 → 9.0. Confidence medium: if the second judge disagrees (κ < 0.6), R → 8 and overall → 8.8, and the article must say so.

### 02 Demand forecasting: 8/9/8/7 → 8.0. Cap: V (figure shows a superseded blend); T (no headline CI, demo not regenerable); C (stale Pinned number, 100-word caption)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `docs/projects/index.md:14` | 0.6161 → 0.6211 (see §4.0) | **TRU** |
| `story.yaml:241` (`m5_full_sample_series` caption, 102 words) | ≤ 40 words: "Three catalog series at the test origin. The curve is the earlier demo blend (0.6161, weights 0.60/0.10/0.30), not the scored 0.6211 blend; the two differ in selection origins (2 vs 9)." If the figure is dropped (P0.5 option B), delete the caption. | CL |
| `story.yaml:173` (Results summary, last sentence) and `README.md:108` | "the current 0.6211 champion" → "the scored 0.6211 blend" | PL |
| `story.yaml:159` (spike-capture paragraph, 5 sentences) | 3 sentences: "A spike-capture variant for erratic series was rejected twice: on development (+0.0204 WRMSSE) and on the test window (+0.0025, CI [0.0018, 0.0031], about 4× the noise band). That test-window check was a second use of the window; the headline model did not change." | CL, NEG |
| `story.yaml:182` (Limits, first bullet) | Append: "On the nine earlier origins used to select it, the blend beat the floor every time, by 24% to 42%; those origins are not independent tests." (From `selection.*.official_wrmsse_per_origin`. Gate it.) | LIM, BL |

**Results.**
- The headline −30.4% has no interval. The committed artifacts cannot produce one: there are no per-node test forecasts.
- Committed data supports only the 9-origin spread above. Add it, and gate the 23.6/41.6 values.
- A real interval needs E9. That refit yields node-level test forecasts for the blend, so the same paired node-bootstrap as `erratic_refinement` (2,000 draws) gives a CI for blend minus floor.
- It does **not** change the headline: the point must reproduce 0.62105 to 1e-6 before any curve or CI is used.

**Technologies.** E9 (pass-3 P3.2, extended): refit `lgbm_pool_storecat` and `lgbm_pool_dept` at origin 2016-05-22. Estimated ≈ 9.4 CPU-hours summed; M5 raw data must be on disk. Outputs:
- (a) the demo payload and sample series from the scored blend;
- (b) `reports_m5_full/headline_interval.json` (node bootstrap of blend − floor).

Without E9, T stays 8.

**Visualizations.**
- Phase C: P0.5, move or drop `m5_full_sample_series`. Drop is recommended if E9 is not approved.
- Retitle `m5_full_pooling_panel` (`m5_full_figures.py`): "The floor wins on zero-sales days (66.6% vs 57.2%); the blend over-forecasts slightly (bias +0.022)".
- `m5_full_candidate_ranking` and `per_level_wrmsse` already state findings.
- After E9, restore the sample series with the title "The scored blend tracks weekly shape on dense series and stays near zero on intermittent ones". Check this against the refit data before using it.
- Replace the hard-coded takeaway strings with reads from `ensemble.weights`.

**Projection.**
- With E9: 9/9/9/9 → 9.0.
- Without E9: 9/9/8/9 → 8.8. V9 holds without the figure if the other three titles state findings.
- Confidence medium-low.

### 03 Anomaly detection: 8/9/8/8 → 8.3. Cap: T (no official NAB score); C (0.527 collision, dense short version); V (champion titles, 519 KiB figure)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `story.yaml:2-4` (`short_version`) | "On 9 NAB series, IsolationForest touches 16 of 17 incidents but fires 1,609 alerts. Merging bursts and capping one page per series per day cuts that to 80 pages. Averaging three detectors halves 66 pages to 35 at the same recall (0.604). No official NAB score yet." (≤ 280; gate tokens `1,609` and `0.604` kept.) | PL |
| `story.yaml:167` (conclusions bullet) | "**Keep precision in the decision.** Averaged per series, range precision at the 2% budget (point-adjusted, k = 2) is 0.527, 95% CI [0.230, 0.811] over 9 series. This is a different metric from the minute-level PR-AUC (also 0.527 by coincidence). The interval sits above the no-skill band [0.063, 0.105] but is wide." Keep the NAB sentence until E5 lands. | CL |
| `story.yaml:8-9` (background) | "minute-level `PR-AUC` (`0.527`)" — add "(not to be confused with the per-series range precision in Conclusions)" or spell it out once | CL |
| `story.yaml:100` | "the synthetic champion" → "the best synthetic detector" | PL |
| `docs/projects/03-anomaly-detection.md:43,56` | "current champion" → "recommended detector" | PROC |
| `docs/projects/index.md:15`, `README.md:34,36` | see §4.0 | PL |

**Results.**
- The ensemble's 66 → 35 pages and range precision 0.347 → 0.553 have no interval.
- Strengthen from committed artifacts if per-series rows for both cells exist in `reports/` (check `nab_metrics.json`/`ablation` files). If they do, compute a 9-series paired bootstrap of the range-precision delta, report-only, as `reports/ensemble_vs_if_interval.json`.
- If they don't, include it in E5's rescore run (same CPU minutes).
- No headline number changes.

**Technologies.** E5 (pass-3 P1.3): vendor the MIT NAB scorer and score the 9 series under three profiles. After E5, replace "NAB score not reported" in `short_version`, `story.yaml:167` and `README.md:46` with "NAB standard-profile score `<s>` (null 0, perfect 100)".

**Visualizations** (`src/anomaly_detection/evaluate.py`):

| Figure | Line | New title / fix |
|---|---|---|
| `telemetry_flags` | `:282` | "Served-model flags on the test window: `<k>` of `<n>` hit injected anomalies". Downsample the plotted traces to bring the file under the 300 KiB budget (now 519 KiB). |
| `range_pr` | its builder | Replace "champion" with the detector name. Title: "`<detector>` stays above the 16-seed random band at every budget" (check it against the data) |
| `nab_score_distribution` | its builder | "In-window minutes score higher than the rest, but the distributions overlap" (check it against the data) |
| `pr_curves` | `:213` | "`<best>` has the highest AP (`<ap>`) against a 1.89% prevalence floor" |

- Delete the unreferenced `reports/figures/score_distribution.json`.
- Rebuild through `cli evaluate` (it scores saved models, no training), then restore the other files as in pass 2.

**Projection.** 9/9/9/9 → 9.0. Confidence medium (NAB adapter effort; the score may be low, which is still T9).

### 04 NLP + cascade: 7/9/8/8 → 8.0. Cap: C (glossary asides, non-finding lead); T (no paired cascade CI)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `story.yaml:261-262` | Delete "A confusion matrix compares actual topics with predicted topics." (it is in the glossary) | PL |
| `story.yaml:265-266` | Delete "Per-class F1 measures each topic separately." | PL |
| `story.yaml:268-270` | Delete the three CPU/MPS/GPU definition sentences. Keep "Same-rows CPU and Apple-GPU (MPS) twins sit 0.0002 apart…" | PL |
| `story.yaml:327` | Delete "Data leakage means…". Keep the rule sentence. | PL |
| `story.yaml:408, 451, 462` | Same treatment: cut the "X means Y" sentences where the term is in `key_concepts` or the glossary | PL |
| `story.yaml:255-257` (results lead) | "**The transformer's remaining errors are mostly Business read as Sci/Tech (25 of 250); LLM review of the uncertain 2% does not measurably fix them.**" | CL |
| `story.yaml:2-3` (`short_version`) | Keep. It is already honest. | — |
| After E6: `story.yaml:17`, `docs/projects/04-nlp-classification.md:9-13`, `README.md:47` | "without per-row decisions, that small gain has no paired interval" → "the paired 95% interval for the gain is [`<lo>`, `<hi>`] (McNemar p = `<p>`), so the gain is not distinguishable from zero" (or, if it excludes zero, say so) | NEG, LIM |

**Results.** The headline 0.9529 → 0.9539 needs the paired CI. That needs E6 (hosted, ≈ $0.024). Publish the replication beside the committed number. The committed 0.95393 stays.

**Technologies.** E6 (pass-3 P2.1) → T9.

**Visualizations** (`src/nlp_classification/evaluate.py`):

| Figure | New title |
|---|---|
| `llm_cascade_comparison` | "Reviewing 22 uncertain items moves fresh macro-F1 0.9529 → 0.9539: no measurable change" |
| `confusion_matrix_selected` | "Business read as Sci/Tech is the largest error (25 of 250)" |
| `per_class_f1_comparison` | "The transformer beats TF-IDF on every topic; Business and Sci/Tech stay lowest" (check against data) |
| `hpo_history` | "12 trials; best validation macro-F1 0.8953, not separated from seed noise" |
| `eda_class_balance` | "Four topics, equal class sizes; most items under `<n>` words" |
| `training_curve` | "Validation macro-F1 peaks at 0.9464; extra probe epochs do not improve it" (check against data) |

After E6, add the paired CI as an error bar on `llm_cascade_comparison`, from `llm_cascade_paired_ci.json`.

**Projection.** 9/9/9/9 → 9.0. Confidence medium-high.

### 05 Churn: 8/9/8/8 → 8.3. Cap: T (one split; the CI excludes threshold-selection uncertainty; contact-everyone is the only baseline); C (results lead is about fairness, not the headline); V (titles)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `story.yaml:215-219` (results lead) | Lead with the decision: "**On the 1,409-customer holdout the served policy costs $601 against $1,035 for contacting everyone (CI −$508 to −$353); the raw model's slices show a contract-length blind spot to check before rollout.**" Then the current fairness text. | CL |
| `story.yaml:227-228` | "The source has 21 columns, while the fitted pipeline uses 4 model features." Explain which 4 and why (selection step), or say "after feature selection keeps `<names>`". Read the names from `reports/models/serving/meta.json`. | CL |
| `story.yaml:240-247` (Results summary) | Add a second baseline in one sentence: "Contacting nobody would cost $`<5 × churners>` on the same holdout." Arithmetic from committed holdout counts; gate it. | BL |
| Limits (`:256-258`) | After E3: "Across `<n>` repeated splits with the threshold re-selected each time, the saving ranges `<lo>`–`<hi>`; the headline keeps the committed split." | LIM |

**Results.**
- Contact-nobody cost is pure arithmetic on committed counts. Do it in Phase B.
- A rule baseline ("contact month-to-month customers only") needs the holdout frame. That is CPU seconds, inside E3.

**Technologies.** E3 (new): repeated stratified splits (20 seeds) running the frozen pipeline config. Each split re-selects the threshold from its own 3-fold OOF predictions, so selection uncertainty is included. Write `reports/repeated_splits.json` (cost delta per split, with median and 2.5/97.5 percentiles) and price the month-to-month rule on each split. This is the step to T9.

**Visualizations** (`src/churn_pipeline/evaluate.py`):

| Figure | New title |
|---|---|
| `permutation_importance` | "`<top feature>` carries most of the holdout F1" (add the missing finding subtitle) |
| `fairness_slices` | "Raw model misses all 9 two-year-contract churners; gender slices are level" (subtitle: "raw model at t = 0.225, not the served policy") |
| `calibration_curve` | "Isotonic calibration cuts ECE from 0.028 to 0.016" |
| `precision_recall_curve` | "`<best>` ranks churners best (AP `<ap>`) against the 26.5% base rate" |
| `bootstrap_ci` | Keep, or "The saving excludes zero: −$508 to −$353 over 2,000 resamples" |

After E3, add a strip of 20 per-split deltas beside `bootstrap_ci`, or drop it into that figure.

**Projection.** 9/9/9/9 → 9.0. Confidence medium.

### 06 Routing: 9/9/9/8 → 8.8. Cap: V (non-finding titles; 5-vs-8 count)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `story.yaml:249-253` (results lead) | "**ALNS averages 4.23% above best-known distance but always needs more trucks (+3.73); the gap reaches 19.48% on C203.**" | CL |
| `story.yaml:279`, `:385` ("beats published references on 5 of 56 days") | "finds a shorter route than the published reference on 5 of 56 days, always with more trucks" | TRU |
| `story.yaml:17` (background Outcome bullet, "beating published references on 5 of 56 days") | same wording | TRU |
| `docs/projects/06-routing-optimization.md:57` ("undercuts eight") | "undercuts five published distances (three more are −0.00% rounding ties), always with more vehicles" | TRU |

**Results.** No change. The CI [3.22, 5.28] is committed.

**Technologies.** None.

**Visualizations** (`src/routing_optimization/figures.py`, rebuilt from committed `metrics.json`):

| Figure | New title |
|---|---|
| `gap_pct` | Count with a −0.005% threshold so ties are excluded (`figures.py:47`): "ALNS has the tightest gap distribution; 5 runs undercut best-known distance" (check against data) |
| `solver_profile` | "ALNS gives the shortest routes of the solver ladder on all 56 instances" (check against data) |
| `family_gap` | "Clustered families are easy and wide-window families hard: gap up to 19.48% (C203), +`<n>` vehicles everywhere" (check against data) |
| `pareto_gap_runtime` | "ALNS is the only solver near a 4% gap at about 1 s" |
| `eda_instance_map` | "C101: window widths vary `<a>`–`<b>` minutes across 100 customers" |

**Projection.** 9/9/9/9 → 9.0. Confidence high.

### 07 Mobility: 9/9/8/8 → 8.5. Cap: T (no CI on the served model; coverage only in figure JSON); V (duplicated heatmap, coverage-subset confusion)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `docs/projects/07-open-data-mobility.md:13` | "with a 90.8%-calibrated p90 staffing band" → "with a p90 staffing band that covered 90.8% of test zone-hours (84.7% in zones without a borough)" | TRU |
| `story.yaml:267-271` (results lead) | "**Demand spans four orders of magnitude across borough-hours, and the p90 band holds its 90% target city-wide but not in no-borough zones.**" Then cut the axis-reading sentences. | CL |
| `story.yaml:376-378` | After E2: replace "no direct interval … is committed" with the served-model CI (and the xGB-vs-served CI) | LIM → BL |

**Results.**
- Headline −28.25% has no CI today.
- E2 adds day-block and zone-cluster CIs for `gbm_tuned − naive_lag24`, using the existing `paired_mae_intervals` machinery (`evaluate.py:153`). It also persists `p90_coverage` outside `_meta`.
- The headline point does not change (stop rule below).

**Technologies.** E2 → T9.

**Visualizations** (`src/mobility/evaluate.py`):

| Figure | Fix / title |
|---|---|
| `hour_borough_heatmap` | Its own subtitle says "identical data to eda_trips_profile". Drop it from Results, or replace it with `borough_mae`. Title if kept: "Manhattan peaks at 103.7 pickups/zone-hour at 18:00; the Bronx tops out at 0.73" |
| `borough_mae` | "Persistence beats the GBM in the Bronx (0.48 vs 0.52 MAE)" |
| `conformal_coverage` | "Conformal adjustment lifts second-half coverage 90.7% → 91.5% for +0.09 pickups of band height". Subtitle: "second half only; the 90.8% headline is the full window" |
| `weather_elasticity` | "Rainy hours average 3–11% fewer pickups outside Manhattan (not adjusted for hour of week)" (check against data) |
| `gbm_vs_nn` | "The tuned GBM leads the run ladder; every learned model beats persistence (MASE < 1)" (check against data) |

**Projection.** 9/9/9/9 → 9.0. Confidence medium (E2 needs the curated test frame; if absent it is a DVC pull or the 1.5 GB pinned download).

### 08 Inference serving: 8/9/6/8 → 7.8. Cap: T (saturated quality check, no quant-matched pair, one host)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `story.yaml:57` ("A 4-bit MoE … wins at 0.81 s p95") | "is fastest at 0.81 s p95 … ; quality was not compared beyond a saturated format check" | TRU, LIM |
| `story.yaml:230` ("is the serving choice") | "is the fastest setup measured; choosing it for serving assumes its answers are good enough, which this run does not test" | LIM |
| `docs/projects/08-inference-serving.md:23` | Delete ", so the numbers describe real traffic, not a lab proxy". Write: "on a fixed 8-prompt structured-output task" | TRU |
| `docs/projects/08-inference-serving.md:12-15` | "Headline: the 4-bit MoE arm serves locally…" → "Headline: on this laptop the 4-bit MoE is the fastest setup…" | TRU |
| Limits (story conclusions) and `README.md:58` | Add: "Cost lines here assume 100 W; project 13 assumes 65 W for a lighter CPU load on the same class of laptop. Neither is measured." Put the mirror sentence in 13. | CL, LIM |
| After E10: `quality_quant` caption, `story.yaml:7,14,260,296`, `README.md:55` | Replace "unrecorded quantization" with the recorded value (pass-3 P0.6). Add the quality score per arm. | |

**Results.** No change until E10. The speed cells stay as committed.

**Technologies.**
- E10 (pass-3 P3.1 a+b): a harder exact-match quality eval and a quantization-matched cross-runner pair. Hours of local inference. This reaches T8.
- E11 (second host) is the only path to T9.

**Visualizations** (`src/inference_serving/figures.py`):

| Figure | Line | New title |
|---|---|---|
| `toks_per_s` | `:103` | "The 4-bit MoE leads throughput at every concurrency level" (check against data) |
| `latency_concurrency` | its builder | "MoE p95 rises near-linearly from 0.81 s (1 request) to 7.80 s (8 requests)" |
| `engine_panel` | `:176` | "The MLX build delivers 2.9× the tokens/s of Q8_0 llama.cpp; quantization differs" |
| `quality_quant` | keep | After E10, replace it with the real quality figure: "`<arm>` scores `<x>`% exact match; speed ranking `<holds / flips>`" |

**Projection.** 9/9/8/9 → **8.8** (single host). 9.0 needs E11. Confidence medium. §5 has the honest statement.

### 09 Agentic workflows: 8/9/8/8 → 8.3. Cap: C ("legacy", "live-grader", "h19" jargon); T (single runs)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `story.yaml:2-4` (`short_version`) | "Plan-act-review workflow with typed outcomes and deadlines. Recorded runs: 15/15 fixed tasks, 13/13 unseen answers, 5/6 correct refusals. A live re-run with hosted models: 13/13 answers, 6/6 refusals, all 19 tasks within budget." (gate tokens `15/15`, `13/13`) | PL |
| `story.yaml:20-21` (background lead) | "**The workflow passed all 15 practice tasks; on 19 unseen tasks it answered all 13 answerable ones but missed one refusal and seven deadlines.**" Spell out "12/19 time caps" as "7 of 19 unseen tasks ran past the 60 s deadline on the local model". | PL, NEG |
| "legacy" (11 occurrences: `:126,204,265,272,277,306,309,320,335,420` and `README.md:27,60,89`) | "the first recorded run (before the typed-refusal fix)" on first use, then "the recorded run" | PROC, PL |
| `docs/projects/09-agentic-workflows.md:7-17` | Generated blockquote plus the hand-written "Headline:" paragraph. Apply the same wording; drop "on every grader" (say "on all four checks: answer, tool set, step budget, deadline") | PL |
| `README.md:52` "Stack:" | Drop "budget-capped offline graders" → "deterministic graders (no AI judge)" | PL |
| After E7: `story.yaml:351`, Limits | "Both runs are single" → "Five repeated live runs: pass^5 = `<k>`/19; p50/p95 `<a>`/`<b>` s" | LIM |

**Results.** The live 13/13 and 6/6 are now in-project (pass 2). E7 adds repeat consistency. The committed live folder stays.

**Technologies.** E7 (pass-3 P2.2) → T9.

**Visualizations** (`src/agentic_workflows/figures.py`, from committed records):

| Figure | New title |
|---|---|
| `suite_summary` | "Every answer task passes; 1 of 6 refusal probes failed in the first recorded run" |
| `cost_latency_bars` | "All 15 practice tasks finish under the 60 s deadline at about $0.13 per suite" (check against data) |
| `node_waterfall` | "Execute dominates task time; the slowest single visit is t15 Execute at 23 s" |
| `tool_usage_matrix` | "Every tool call was in the plan: zero out-of-set calls" |

Drop "(legacy recorded run)" from titles and keep the run date in subtitles. After E7, add `live_repeats` (per-task pass count out of 5): "`<k>` of 19 tasks pass all five live runs".

**Projection.** 9/9/9/9 → 9.0. Confidence medium.

### 10 Uplift: 8/9/8/7 → 8.0 (8/9/8/8 after pass-3 P0.4). Cap: V; T (CIs only in HTML); C (12.03 with two intervals)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `story.yaml:241-243` (per-arm AUUC paragraph) | Add: "Mens's 12.03 is the same score as the T-learner's Qini in the two-arm table. Its interval differs because this figure resamples all three arms together (seed 2041) while the table resamples only Mens vs control (seed 1041): [0.77, 24.39] there excludes zero, [−0.47, 24.21] here does not. Read the ranking as weak either way." | CL |
| `story.yaml:226-233` (Qini reading paragraph) | Cut the axis-reading tutorial to 2 sentences; the definition is in `key_concepts` (`:414`) | PL |
| `docs/projects/10-uplift-experimentation.md:16` | "with the revenue-minus-send-cost ranking established by paired-bootstrap CIs" → "the gain over random is established by a paired bootstrap; the ranking against a plain response model is not" | TRU |
| `docs/projects/10-uplift-experimentation.md:12` | "A campaign owner" → "A marketer" | PL |
| After E1: `story.yaml:313`, `README.md:100` | "intervals from `reports/report.html`" → "intervals in `reports/metrics.json` (`analysis.ci`)" | |

**Results.** E1 persists the CIs; they must match `0c01c45d` to 1e-6. No headline change.

**Technologies.** E1 (pass-3 P1.1) → T9.

**Visualizations** (`src/uplift_experimentation/{evaluate,eda}.py`):

| Figure | Line | New title |
|---|---|---|
| `qini_per_arm` | `evaluate.py:943` | "Neither arm's AUUC interval excludes zero" (pass-3 P0.4, plus the axes-gate fix) |
| `uplift_by_decile` | `evaluate.py:764` | "Predicted uplift tracks the observed contrast in the top deciles only" (check against data) |
| `cuped_variance` | `evaluate.py:892` | "CUPED cuts outcome variance by `<x>`% for spend, `<y>`% for visits" |
| `eda_segment_profile` | `eda.py:56` | "Three balanced arms of about 21k; Mens mail lifts visits most" (check against data) |
| `profit_frontier_multi_arm` | its builder | Shorten: "Best-arm targeting at 25% budget: model-estimated value, not observed" |

**Projection.** 9/9/9/9 → 9.0. Confidence high.

### 11 DataFrame engines: 9/9/9/8 → 8.8. Cap: V

**Contents.** `story.yaml:269-272` (results lead) → "**Polars wins 9 of 10 tasks, DuckDB wins one, and sqlite is slowest on 9; pandas uses the most memory on compute tasks.**" Cut the three "the X shows Y" sentences. Why: CL.

**Results, Technologies.** None.

**Visualizations** (`src/data_engineering/figures.py`):
- `speedup_overview` (`:165`): "Polars (×19.2) and DuckDB (×14.9) beat pandas; sqlite is about 29× slower".
- `scalability_lines` (`:233`): "Polars and DuckDB grow sub-linearly with rows (slopes 0.73, 0.63); pandas grows linearly".
- `memory_lollipop`: "sqlite peaks highest (to 1,520 MB) because it holds frame and database together".

**Projection.** 9/9/9/9 → 9.0. Confidence high.

### 12 Tabular lifecycle: 8/9/7/8 → 8.0. Cap: T (the committed run keeps the pruning and lag defects)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `story.yaml:7-8` (`limits`) | Add the pruning defect beside the lag one: "the correlation-pruning rule drops `atemp`, the higher-information member of the `temp`/`atemp` pair" | LIM |
| `story.yaml:24` ("pick the winner before touching test") | "pick the model on validation before touching test; the MLP and LightGBM tie there (34.2 vs 34.4)" | CL, TRU |
| `story.yaml:267-271` (results lead) | "**The served MLP cuts error from 83.2 to 25.4 rentals/hour, but it does not beat LightGBM, which is 0.06 lower on test.**" | CL, NEG |
| `docs/projects/index.md:24` | see §4.0 | PROC |
| After E4 (option A): Results and Limits, `README.md`, docs page | "A corrected variant (keeps `atemp`, joins lags by timestamp) scores MAE `<x>` [CI `<lo>`–`<hi>` vs committed]. The headline keeps the committed run; project 13 serves the committed model." | LIM, NEG |

**Results.** No headline change under option A. E4 adds a disclosed sensitivity arm.

**Technologies.**
- Option A, E4 (pass-3 P1.2): T7 → 8. Cost: about 1 CPU minute.
- Option B, E12: replace the headline → T9. The headline moves (§5, E12).

**Visualizations.** The titles already state findings. Add one figure, `sensitivity_pruning_lags` (`src/tabular_ml_lifecycle/figures.py`, from `reports/sensitivity_pruning_lags.json`): "Fixing pruning and lag alignment moves MLP test MAE by `<Δ>` (CI `<lo>`–`<hi>`)". This lifts V to 9.

**Projection.**
- Option A: 9/9/8/9 → **8.8**.
- Option B: 9/9/9/9 → 9.0.
- Confidence medium.

### 13 Model serving: 8/9/9/8 → 8.5. Cap: C (stale "Champion" cell, non-finding leads, a glossary aside); V (long caveat titles)

**Contents.**

| File:lines | Change to | Why |
|---|---|---|
| `README.md:56`, `docs/projects/index.md:25` | see §4.0 | PROC |
| `story.yaml:261-263` (results lead) | "**Both backends answer in 1.6 ms at the median, the service saturates near 950 requests/s, and the ONNX-only image is 22× smaller (291 MB vs 6.5 GB).**" | CL |
| `story.yaml:219-220` | Delete "RSS, or resident set size, is the memory held by a running process." (in the glossary) | PL |
| `story.yaml:307` (Limits, cost) | Add: "Project 08 assumes 100 W for LLM load on the same class of laptop; neither wattage is measured." | CL, LIM |

**Results, Technologies.** None. Under option B for 12, 13 must be re-derived (E12).

**Visualizations** (`src/model_serving/figures.py`):

| Figure | New title |
|---|---|
| `latency_concurrency_lines` | "p95 stays under 6 ms to 4 concurrent requests, then climbs sharply past 16" |
| `batch_throughput_curve` | "Batches of 128 rows reach about 56k rows/s on both backends" |
| `backend_comparison_slope` | "ONNX and native p50 differ by at most 4% at every concurrency level" |
| `footprint_cost_bars` | "Torch and unused CUDA make up most of the 6.5 GB image; ONNX-only is 291 MB" |

Move the current caveat text into the subtitles.

**Projection.** 9/9/9/9 → 9.0. Confidence high.

### 15 Dynamic pricing RL: 9/10/9/8 → 9.0
- Contents and Results: none.
- Visualizations: a browser check of the 5 diagrams on the redeployed page (pass-3 P0.6). V → 9.
- **Projection:** 9/10/9/9 → 9.3. Confidence high.

## 5. Projects that cannot honestly reach 9 on one axis

- **08, Technologies, single host.** T8 is the ceiling without a second machine, so overall is 8.8.
  - Article wording (Limits, and docs opening): "All measurements come from one laptop. They rank setups on this machine only; cross-host behaviour is untested, so re-run the harness on the target hardware before choosing."
  - Do not round 8.8 up or soften the single-host limit.
- **12, Technologies, if the headline is kept (option A).** The committed run carries two known defects, so T8 and overall 8.8.
  - Article wording: "The headline keeps the committed run because project 13 serves and reproduces it. A corrected variant scores `<x>`; the difference is `<Δ>` [CI]." If Δ's CI excludes zero, add: "The committed headline carries a known defect worth `<Δ>` MAE."
- **02, Technologies, if E9 is declined.** T8 and overall 8.8.
  - Article wording, as now: "The headline has no interval; across the nine selection origins (not independent) the blend beat the floor by 24–42%."
- **01, Results, conditional.** If the second judge disagrees, R drops to 8, overall 8.8, and Limits must say: "A second judge from another model family agrees on `<x>`% of verdicts; the 0.9091 F1 depends on the judge."

## 6. Experiments

Rules for all of them:
- New results go **beside** committed ones, in new dated files.
- No committed `metrics.json` value changes, except by the additive `analysis` key or under E12.
- Restamp in its own commit afterwards.
- "Tolerance" is the stop rule: if a committed headline value moves more than this when re-derived, stop, commit nothing, and report.

| ID | Project | What | Hardware | Cost | Duration | Changes | Stop rule (tolerance) |
|---|---|---|---|---|---|---|---|
| D0 | 01/02/04/05/07/10/12 | Move analysis out of `_meta` (pass-3 P1.0, plus 07 `p90_coverage`) | laptop | tests only | 1 day eng. | Code; no artifacts until re-run | Any test failure |
| E1 | 10 | `cli evaluate`, deterministic 1,000-rep bootstrap, seed 1041 | laptop CPU | ~0 | CPU minutes | `analysis.ci` in `metrics.json`; gate reads it | Any point metric ≠ committed (1e-9); CI ≠ `0c01c45d` (1e-6) |
| E2 | 07 | Add `(gbm_tuned, naive_lag24)` and `(gbm_xgb_tuned, gbm_tuned)` to `PAIRED_INTERVAL_COMPARISONS`; re-run evaluate from the saved `reports/models/*.joblib` (present locally) | laptop CPU, ≤ 1.5 GB data if the curated frame is absent | ~0 (download only) | 10–20 CPU min | Served-model CI; coverage persisted | MAE 4.6763/6.5175 differ > 1e-6, or coverage 0.90795 differs > 1e-5 |
| E3 | 05 | 20 repeated stratified splits, OOF threshold re-selected per split; month-to-month rule priced | laptop CPU | ~0 | 5–15 CPU min | New `repeated_splits.json` | First reproduce the committed split: $601 / $1,035 to ±$0.5, threshold 0.175 exactly; else stop |
| E4 | 12 | Sensitivity arm (pass-3 P1.2) | laptop CPU | ~0 | ~1 CPU min (44.4 s + 13.3 s recorded) | New JSON + one figure | Reproduction of 25.4316 fails (1e-4) |
| E5 | 03 | Vendor the NAB scorer, score 3 profiles (pass-3 P1.3) | laptop CPU | ~0 | CPU minutes + ~1 day eng. | New public NAB score; `uv.lock` → restamp all | 1,609 / 0.527 / [0.230, 0.811] change at all; null ≠ 0 or perfect ≠ 100 |
| E6 | 04 | Cascade re-run with per-row rows; paired CI + McNemar (pass-3 P2.1) | laptop CPU + hosted LLM | ≈ $0.024, cap $0.10 | ~15 min | Replication beside 0.95393 | Meter > $0.036; replicated F1 differs from 0.95393 by > 0.003: publish as replication, do not replace |
| E7 | 09 | 5× live held-out suite (pass-3 P2.2) | hosted | $0.47–0.83, cap $1.00 | ~40 min | pass^5, p50/p95 across runs | Meter > $1.50; committed `live_confirmation_20261119/` untouched |
| E8 | 01 | Cross-family judge on committed `final_v3` answers (pass-3 P2.3) | hosted | $1.1–2.0, cap $2.50 (re-check prices on the day) | 30–60 min | Agreement κ, F1 under judge 2 | Calibration < 25/30 on the hand labels: report, do not grade; never replace 0.9091 |
| E9 | 02 | Refit 2 members at 2016-05-22; node bootstrap blend − floor (pass-3 P3.2, extended) | laptop CPU, M5 raw on disk | electricity only | ≈ 9.4 CPU-h (rough) | Demo from scored blend; headline CI | Member WRMSSE ≠ 0.62252 / 0.64586 or blend ≠ 0.62105 (1e-6) |
| E10 | 08 | Exact-match quality eval per arm + quant-matched pair (pass-3 P3.1 a,b) | the same 128 GB laptop | ≈ $0.2 electricity (100 W × ~6 h × $0.30/kWh) | ~4–8 h inference | Quality axis; possibly the serving verdict | Re-measure one committed speed cell first; if tok/s drifts > 10%, stop (host state changed) |
| E11 | 08 | Same harness on a second machine of another class | other hardware | access | hours | T9 | n/a (new cells only) |
| E12 | 12 → 13 | Option B: retrain the corrected pipeline as v2; re-derive 13 (reproduction target, ONNX parity, images, load bench) | laptop | electricity | ~1 CPU min + ~2 h for 13 | **Every 12 and 13 headline number** | Only after E4; v2 must pass 13's parity gate (1e-4) |

**E12 honest option (headline-moving).**
- Keep the committed run as "v1 (2026-11, known pruning and lag defects): MLP 25.4316, LightGBM 25.3732" in the Exact-numbers table and in `metrics.json` under `previous_runs.v1`.
- Publish v2 as the headline with one sentence: "v2 fixes two disclosed defects; v1 remains for comparison and moved by `<Δ>`."
- 13's copy changes from "reproduces 25.4316" to "reproduces v2's `<x>`".
- The headline gate and 13's reproduction gate are re-keyed in the same commit.

Hosted budget across E6–E8: **$5.00 cap**, estimated $1.6–2.9.

## 7. Owner decisions needed

1. Branch for the commit, and restamp scope (5 files or all 17). Carried from pass 3.
2. Approval to edit app code for the axe fix (§3.1).
3. Approval of the rewritten `short_version`s for 01, 03 and 09, and of `README.md:8-9`.
4. 02: drop or move the sample-series figure now; run E9 (about 9.4 CPU-h) or accept 8.8.
5. 12: option A (keep the headline, 8.8) or option B (E12, 9.0; every 12/13 number moves).
6. 08: accept 8.8 on one host, or provide a second machine (E11).
7. The $5 hosted cap, the judge model for E8, and "beside, never replace" for E6–E8.
8. 03: publish the NAB score whatever it is.
9. Approve the new CPU experiments E2 (07) and E3 (05), which are not in pass 3.

## 8. Exit criteria

- **Phase A.** As pass-3 §8 P0, plus 0 axe findings on all 12 routes at both viewports.
- **Phase B.** These exit 0:
  - `check_short_copy --check`, `gen_story_short --check`, `gen_static_registry --check`;
  - `check_headline_numbers` (with the new 02 Pinned and 9-origin claims);
  - `lint_story_language`, `check_docs`, `mkdocs build --strict`.
  - `grep -niE "champion|owner|legacy|wave [0-9]|audit-P"` over `README.md`, `docs/projects/*.md` and `projects/*/story.yaml` returns only accepted domain uses (02/03/06 model selection; 05 "data owner").
- **Phase C.**
  - Every story figure title states a finding (re-run the title extraction used for this plan).
  - `check_figure_axes`: 2 or fewer warnings, 0 after the 01 ladder fix.
  - `check_figure_budget`: 0 warnings.
  - Each touched figure's `data` is byte-equal.
- **Phase D.**
  - Each new artifact is dated, reconciles to its summary, and is gated.
  - Meters are within cap.
  - Every stop rule was checked and logged in the commit message body.
