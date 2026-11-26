# Wave 8 round-3 executor closeout

Date: 2026-11-26  
Branch: `wave8-articles-truthfulness-2026-11-25`  
Baseline: `c05accd0`  
Scope: approved handoff `collaboration/designs/20261126-wave8-round3-article-fixes/03-implementation-handoff.md`, projects 02–13 only.

## Result

57 handoff items were addressed; the items not yet done are listed under "Open items" below. Each finding was checked against the cited working-tree surface and committed evidence before editing. No experiment, training job, benchmark, model refit, hosted call, or paid call was run. Projects 01 and 15 were left untouched. No commit, push, merge, stash, checkout, or other git mutation was performed.

Two settled decisions are preserved:

- **Project 02:** the catalog payload remains the historical `0.6161` blend with weights `0.60/0.10/0.30`; the current committed champion is `0.6211` with weights `0.95/0.00/0.05`. Regenerating the old catalog would require a prohibited model refit, so the disclosure fallback is used (owner sign-off pending). The failed guard and decision are recorded in `collaboration/designs/20261126-wave8-round3-article-fixes/OPEN_QUESTIONS.md`.
- **Project 08:** owner option (b) is implemented. The gitignored repeat file was not committed and `.gitignore` was not changed. Only one Limits sentence mentions the uncommitted co-tenant repeat; no numeric or causal claim depends on it.

## Open items

Added by the design lane (Opus, revision 3 of the fix list, 2026-11-26).

1. **Item 53 — verbless transitions (Kimi).** Fix 1 changed 39 "; next, the" splices to ". Next, the X (link)." Only `projects/03-anomaly-detection/story.yaml:51` is a full sentence. The other 38 still have no main verb and must be rewritten as full sentences (line = start of the sentence):
   - 02 `projects/02-demand-forecasting/story.yaml`: 86
   - 06 `projects/06-routing-optimization/story.yaml`: 55, 95, 126, 209, 242, 276
   - 07 `projects/07-open-data-mobility/story.yaml`: 91, 130, 154, 223, 259, 285
   - 08 `projects/08-inference-serving/story.yaml`: 93, 127, 155, 222, 250, 270
   - 09 `projects/09-agentic-workflows/story.yaml`: 66, 97, 133, 208, 257
   - 10 `projects/10-uplift-experimentation/story.yaml`: 73, 104, 134, 188, 215
   - 11 `projects/11-data-engineering/story.yaml`: 60, 91, 279
   - 12 `projects/12-tabular-ml-lifecycle/story.yaml`: 65, 101, 135, 214, 260, 296

   After the rewrite, re-run `lint_story_language.py`, `check_short_copy.py --check`, `gen_story_short.py --check` and `git diff --check`, and record exit codes.
2. **Project 02 fallback sign-off (owner).** Signed off by the owner on 2026-11-26: the historical `0.6161` blend stays in the demo, labelled as the earlier blend, with the `0.6211` champion beside it. No refit was run.

## Evidence map

Paths are repository-relative. Line numbers refer to the final working tree. Gate abbreviations: **F** figure regeneration/figure gates; **S** story-language/docs gates; **H** headline-number gate; **D** demo contract/web tests/browser; **I** diagram tests/web build/browser; **P** Python tests; **G** generator checks; **R** Ruff/mypy; **K** strict MkDocs build.

### Project 02 — demand forecasting

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 1 | FIXED | Regenerated ranking, per-level, pooling and sample-series figures. Ranking is `0.6211 / 0.6219 / 0.6225 / 0.6459`; per-level total is `0.3142809`; pooling shows `57.2%`; obsolete causal titles are absent. Sources: `projects/02-demand-forecasting/src/demand_forecasting/m5_full_figures.py`; outputs under `reports_m5_full/figures/`. | `projects/02-demand-forecasting/reports_m5_full/metrics.json` | F, H, P |
| 2 | fallback taken; owner signed off (2026-11-26) | Historical payload retained and disclosed in `story.yaml:173,241`, `README.md:108`, `DESIGN.md:773-774`, `demo.yaml:10-13`, and `ForecastWorkbench.tsx:31-35,307-311,352-363`. Payload was not hand-edited. | `reports_m5_full/demo_payload.json`; `reports_m5_full/metrics.json`; `OPEN_QUESTIONS.md` | D, H, P |
| 3 | FIXED | Selection diagram now gives `0.95/0.00/0.05` and says selection reads only the nine selection origins: `apps/showcase-web/src/diagrams/m5Pipeline.ts:43-70`. | `reports_m5_full/metrics.json`, `ensemble.members/weights`; `evaluation_metadata.json` | I, H |
| 4 | FIXED | Mid-volume series is smooth with no zero days (`story.yaml:79`); three item-grain levels (`:145`); under `0.001` and about `1.3×` (`:155,159`); weekly-reforecast recommendation removed. | `reports_m5_full/metrics.json`; committed demo catalog | S, H, P |

### Project 03 — anomaly detection

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 20 | FIXED | Minute PR-AUC ranges are `0.566–0.577` and `0.515–0.574`: `projects/03-anomaly-detection/story.yaml:97`. | `projects/03-anomaly-detection/reports/metrics.json` | S, H |
| 21 | FIXED | Train-only series count as zero in range recall: `auto/03-anomaly-detection-2.ts:31,57`, `detectionPipeline.ts:16,69`, and `README.md:46-47`. | `reports/nab_metrics.json`; `reports/metrics.json` | I, S |
| 22 | FIXED | Hero is explicitly the IsolationForest headline path; conclusions diagram no longer calls a nonexistent deployed artifact. `story.yaml` Background; `auto/03-anomaly-detection-3.ts:6-75`. | `reports/champion_selection.json`; `reports/nab_sweep.json` | I, S |
| 23 | FIXED | Rebuttal asides and staccato fragments removed; openings and transitions rewritten as reader-facing prose throughout `story.yaml`. | Existing committed metrics; language-only edit | S |
| 24 | FIXED | Results summary folded into lessons; tuned OCSVM `17/120` and tuned IsolationForest `18/120` retained; threshold terminology and six-window/five-series scope corrected in `story.yaml` Training/Conclusions. | `reports/nab_tune.json`; `reports/nab_refinement.json`; `reports/nab_sweep.json` | S, H |
| 25 | FIXED | Shipped roadmap and adoption gate describe the recommended page stream, not an anomaly demo. `story.yaml` roadmap. | Repository demo inventory; `check_demo_contract.py` | S, D |

### Project 04 — NLP classification

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 5 | FIXED | Background uses the full-data transformer → `τ=0.6` → reviewed-rows cascade (`auto-04-nlp-classification-3`), matching `story.yaml:10-18`; obsolete routing hero expectation removed from `diagramSpecs.test.ts`. | `projects/04-nlp-classification/reports/fresh_holdout.json`; `llm_cascade.json` | I, H |
| 6 | FIXED | Lineage is seeded sample → validation/model selection; bounded test `1,000`; complement `6,600`; fresh holdout; scale ladder. `auto/04-nlp-classification-2.ts:19-75`; prose at `story.yaml:81-100`. | `reports/fresh_holdout.json`; `reports/scale_meta_*.json` | I, H |
| 7 | FIXED | Gate uses full-data raw softmax maximum; `T=0.927` is attributed to the bounded selected model (`story.yaml:160,213-214`); validation temperature/ECE distinction corrected (`:434-436`). | `reports/metrics.json`; `reports/fresh_holdout.json`; `reports/history_fulldata.json` | S, H |

Note: `apps/showcase-web/src/diagrams/routing.ts` (spec `04-routing`) is a registered test fixture (`diagrams/index.ts:12,21`; `__tests__/FlowDiagramImportFailure.test.tsx`) and is not embedded in any story. Its stale `0.9020` was corrected to the fresh-holdout `0.9061` (τ = 0.5) at `routing.ts:35,53`; the registration and tests were left unchanged.

### Project 05 — ML pipeline churn

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 8 | FIXED | One preprocessing DAG with numeric/categorical branches, including `internet_service`, joins at `ColumnTransformer`: `auto/05-ml-pipeline-churn-4.ts:37,49`; `story.yaml:245-249,313`. | `projects/05-ml-pipeline-churn/reports/metrics.json`; `SERVING.md` | I, S |
| 9 | FIXED | Measurement chain is OOF → 41-point grid → frozen `0.175` → holdout scored once → paired bootstrap; watch labels aligned: `auto/05-ml-pipeline-churn-3.ts:13-53`. | `reports/metrics.json`; `reports/sensitivity.json` | I, P |
| 10 | FIXED | Unsupported 25-trial claim removed; hero says `$601`; audit sentence deleted: `churnCycle.ts:33,69`, `README.md`, `story.yaml`. | `reports/metrics.json`; `params.yaml` | I, S, H |
| 11 | FIXED | `−434` is the observed point delta, not a bootstrap mean (`story.yaml:240-241,284-285`); recall and raw-policy cost-panel wording corrected (`:216,224`). | `reports/metrics.json` | S, H |
| 12 | FIXED | `7,043` total = `5,634` train + `1,409` holdout throughout `story.yaml:8,15,54,69,322,358` and README. | `reports/metrics.json`; `evaluation_metadata.json` where present | S, H |

### Project 06 — routing optimization

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 26 | FIXED | Vehicles-first control trims only `+3.73` to `+3.66`; fleet gap is framed as mainly a search limit: `projects/06-routing-optimization/story.yaml:50-52`; mirrored at `README.md:95-99`. | `projects/06-routing-optimization/reports/results.md`; `reports/metrics.json` | S, H |
| 27 | FIXED | Five negative gaps exclude three `−0.00%` rounding ties, C108/C109/C207: `story.yaml:154-158,348`. | `reports/results.md` per-instance table | S, H |
| 28 | FIXED / OPTIONAL POLISH | Short copy now says about `3.7` vehicles; repeated directions and conclusions were tightened without changing the evidence. | `reports/results.md` | S, G |

### Project 07 — open-data mobility

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 13 | FIXED | Tuned GBM is `0.2%` worse than default (`4.676` versus `4.667`), stated once in Exact numbers with no direct interval: `projects/07-open-data-mobility/story.yaml:354`. | `projects/07-open-data-mobility/reports/metrics.json` | S, H |
| 14 | FIXED | Background says JFK and LaGuardia, not JFK/EWR: `story.yaml:12`; airport discussion aligned. | `reports/figures/zone_demand_map.json` | S, H |
| 15 | FIXED | Daily Central Park weather broadcast to each hour: `story.yaml:48,133`. | GHCN-Daily provenance; `DESIGN.md` | S |
| 16 | FIXED | Shipped card is “Measure the upper band's coverage,” with raw city-wide and no-borough coverage: `story.yaml:465-468`. | `reports/metrics.json` | S, H |
| 17 | FIXED | Unsupported 20% target replaced by “beat the same-hour-yesterday baseline by a clear margin”: `story.yaml:65`. | `reports/metrics.json` | S |

### Project 08 — inference serving

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 0.2 / owner decision | FIXED — OPTION (b) | Removed committed-status wording, `5–35×`, Ollama `0.40.12`, and `2026-10-30`; retained one uncommitted-observation Limits sentence at `projects/08-inference-serving/story.yaml:375`. No repeat-file or `.gitignore` change. | `projects/08-inference-serving/reports/metrics.json`; `OPEN_QUESTIONS.md` | S, H |
| 18 | FIXED | Aggregate throughput is flat/slightly rising for gpt-oss and gemma4 MLX and falls about `26%` for qwen3.6; interpretation explicitly does not isolate bandwidth, batching, or another cause: `story.yaml:184-190`. | `reports/metrics.json`; committed `data/bench_run.json` | S, H |
| 19 | FIXED | Grid selects a throughput leader, not an overall champion (`story.yaml:222`); missing MLX tag and earlier switch-expert conversion failure are distinct (`:177-178,349-350`); qwen3:32b and gemma4:31b both use “not recorded” (`:326-327`). | `reports/metrics.json`; committed model registry | S, H |

### Project 09 — agentic workflows

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 29 | FIXED | `~$0.13` belongs to legacy tuning; held-out outcomes are separate: `projects/09-agentic-workflows/story.yaml:21,201-203`. | `projects/09-agentic-workflows/reports/metrics.json`; `kimi_comparison.json` | S, H |
| 30 | FIXED | Scripted `tests/test_hitl.py` demonstrates pause/reject/re-plan; no live checkpoint run is recorded: `story.yaml:206,373`. | `projects/09-agentic-workflows/tests/test_hitl.py` | S, P |
| 31 | FIXED | Rounded-index p95 is `31.1 s` (t15); slowest task t05 is `31.6 s`: `story.yaml:11,287-292`; nearest-rank wording removed. | `reports/metrics.json` | S, H |
| 32 | FIXED | StepBudget mechanics state that `steps_taken` entries are counted and the runner allows 8: `story.yaml:321-326,397` and related budget clauses. | `src/` runner and budget implementation; `reports/metrics.json` | S, P |

### Project 10 — uplift experimentation

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 33 | FIXED | `T-learner − random` row renders with `[+$718, +$4,767]`: `projects/10-uplift-experimentation/story.yaml:311`. Browser confirmed the table row. | `projects/10-uplift-experimentation/reports/metrics.json` | S, H, I |
| 34 | FIXED | All cost copies distinguish analytic top-25% break-even `≈$0.30`, first sub-100% grid share at `$0.20` (`90%`), and 25% share at `$0.50`: `story.yaml:14-15,47,208-210,285,315-319,418,431`. | `reports/metrics.json`; `reports/demo_payload.json` | S, H |
| 35 | FIXED | Mens `+0.68 pp`, Womens `+0.31 pp`, Womens `66.5` incremental conversions `[33.1,104.7]`, and `0.57%` control are stated with the need for intervals: `story.yaml:118-121`. | `reports/segment_summary.json`; `reports/metrics.json` | S, H |
| 36 | FIXED | Unsupported T−X CI `[−$323,$4,343]` removed; stale-claim search is empty. | `reports/metrics.json` | S, H |
| 37 | CLOSED — OPTIONAL | Money wording and repeated tables were reduced; CUPED remains explicitly labelled as a measured null result. Revenue-only metrics are not called net profit. Two multi-arm planning figures moved to Training, leaving three Results figures. | `reports/metrics.json`; final `story.yaml` structure | S, I |

### Project 11 — data engineering

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 38 | FIXED | Three reader-facing audit-voice sentences removed; remaining prose states results directly throughout `projects/11-data-engineering/story.yaml`. | Existing committed benchmark artifacts | S |
| 39 | FIXED | SQLite copy consistently says loading is not timed separately and its share is unknown; no unsupported dominance claim: `story.yaml:184-185,352,387`. | `projects/11-data-engineering/reports/metrics.json` | S, H |
| 40 | FIXED | Short copy leads with the parity catch; Background's “Match check first” step mentions the `1,658` dropped trips: `story.yaml:3,16`. | `reports/metrics.json` | S, G |
| 41 | FIXED / OPTIONAL POLISH | “Row count” wording, `39 of 39`, and bigger-than-RAM gate aligned: `story.yaml:106,355,396,408`. | `reports/metrics.json`; README | S, H |

### Project 12 — tabular ML lifecycle

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 42 | FIXED | `165` missing hours, early-2011 concentration, and 36-hour 2012-10-29/30 validation gap; positional lags can drift up to 36 hours for about a week: `story.yaml:89-90,374-375,398-399`; `README.md:46-49`; `DESIGN.md:27`; `data/feature_selection.json:3`. | Committed UCI data contract; `reports/evaluation_metadata.json`; `data/feature_selection.json` | S, H, P |
| 43 | FIXED | Review-process hedges replaced by protocol facts; epoch cap `150` and uncommitted per-variant counts disclosed (`story.yaml:176,359`); ablation configuration described as fixed in `params.yaml` beforehand (`:279,369,392`). | `projects/12-tabular-ml-lifecycle/params.yaml`; `reports/train_runs.json` | S, P |
| 44 | FIXED | UCI season codes run one season early (`story.yaml:111`); high-demand under-forecast `+28.6` and holiday over-forecast added to lessons (`:252,331`); roadmap gate includes validation MAE and late-December residuals. | `reports/metrics.json`; `reports/figures/residual_vs_fitted.json`; `residual_heatmap.json` | S, H, F |
| 45 | FIXED | “No global bias” removed; mean residual is explicitly `+9.2` overall (`story.yaml:459`). | `reports/metrics.json` | S, H |
| 46 | FIXED | Conclusions retain one exact-number table in gold order; Results points to the committed record instead of repeating it: exact-number table at `story.yaml:354` (Conclusions, after Taught :303 and Limits :334); Results pointer at `:292-293`. | `reports/metrics.json`; `reports/results.md` | S |

### Project 13 — model serving

| Item | Status | Final correction and changed surface | Committed evidence | Check |
|---|---|---|---|---|
| 47 | FIXED | Native/ONNX p50 gaps are at most `4.0%`: `projects/13-model-serving/story.yaml:189,213,285`. | `projects/13-model-serving/data/bench_run.json`; `reports/metrics.json` | S, H, F |
| 48 | FIXED | Ratio range corrected to `0.96–1.04`: `story.yaml:392-393`; slope figure regenerated. | `data/bench_run.json`; `reports/figures/backend_comparison_slope.json` | S, F |
| 49 | FIXED | CPU claims say “likely contend” / “likely saturated” (`story.yaml:177,207,389`); queueing and computation are not separated (`:185,391`). | `data/bench_run.json`; host-sharing limitation in `reports/evaluation_metadata.json` | S, F |
| 50 | FIXED | c64 native/ONNX p50 is `65.4/63.1 ms` (`story.yaml:178,207`); image roadmap says measure base/venv/model layers and infer framework weight from a slim build (`:382`). | `data/bench_run.json`; `reports/docker_run.json` | S, H |
| 51 | FIXED | Batch header remains p50 (`story.yaml:298`; `src/model_serving/figures.py:93-140`); duplicate image/cost retelling removed from Conclusions. | `data/bench_run.json`; `reports/metrics.json` | S, F, P |

### Cross-cutting and regeneration

| Item | Status | Final correction and changed surface | Evidence | Check |
|---|---|---|---|---|
| 52 | FIXED | Reader-facing review-process and audit-voice language removed across all twelve stories. | Final `projects/02`–`13/story.yaml` | S |
| 53 | FIXED | The 39 “X; next, the” splices are rewritten as full sentences in projects 02, 03 and 06–12 (38 edits, Wave 8 iteration pass; project 15 out of scope). Gates re-run after the rewrite; see `collaboration/reviews/20261126-wave8-iteration-final-review/00-final-review.md`. | Final story sections; grep `Next, the` | S |
| 54 | FIXED | Sentence-breaking inline definitions folded into glossary/key-concept prose. | Final story sections | S |
| 55 | FIXED | Plain-terms cards remain everyday one-sentence takeaways rather than metric dumps. | Final story sections | S, browser |
| 56 | FIXED | Affected figures/reports and all registry/copy/route surfaces regenerated through project or repository generators, including `projects/02-demand-forecasting/reports_m5_full/figures/m5_full_sample_series.json` and `.html`, regenerated on 2026-11-26 with `build-figures-m5-full` after the title-date fix (2016-05-23 → 2016-05-22). Figure checks `check_figure_axes`, `check_figure_budget` and `check_docs` exit 0. See `collaboration/reviews/20261126-wave8-iteration-final-review/00-final-review.md`. | Commands and outputs below | F, G |
| 57 | FIXED | Every changed numeric claim was rechecked against the committed artifact named above; stale-claim searches for projects 02, 08, 12 and 13 returned no prohibited surviving claims. | This map; committed reports; final greps | H, S, P, D |

## Regenerated surfaces

Commands used only committed artifacts:

```bash
cd projects/02-demand-forecasting
uv run python -m demand_forecasting.cli build-figures-m5-full
uv run python -m demand_forecasting.cli build-report-m5-full

cd ../13-model-serving
uv run python -m model_serving.cli report

cd ../..
uv run python scripts/gen_static_registry.py
uv run python scripts/gen_story_short.py
uv run python scripts/gen_route_manifest.py
```

Project 03's `hpo_importance` figure was rebuilt through `hpo_importance_figure(get_config(), "ocsvm")` from the committed `ocsvm_hpo.json`; the generic champion label in `range_pr.py` was deliberately not changed because that would require an experiment rerun. Project 12's existing regenerated report/figure outputs were retained and checked; round 3 changed its prose and committed feature metadata, not experiment measurements.

The project 13 assembler initially rewrote unrelated host/provenance metadata. Those unrelated fields were restored to their committed values; `git diff --quiet -- projects/13-model-serving/reports/metrics.json projects/13-model-serving/reports/evaluation_metadata.json` passes. Measured values were unchanged. Only the intended figure/report wording changes remain.

All three repository generators also pass their subsequent `--check` forms.

## Browser verification

Verified with the local Vite/React app and a freshly launched API for the current demo manifest. The pre-existing API process on port 8000 was not stopped or modified. Temporary verification servers were stopped afterward.

- **02:** 8 sections, 4 figures, 2 tables; historical `0.6161` and current `0.6211` disclosures render; no raw Markdown fences or Vite error overlay.
- **04:** 8 sections; background cascade and 9-node seeded/validation/bounded-test/complement/fresh-holdout lineage render correctly.
- **05:** 8 sections and 5 tables; measurement diagram renders OOF → 41-point grid → frozen `0.175` → holdout once → bootstrap; no holdout-leak ordering.
- **07:** 8 sections, 9 figures, 3 tables; JFK/LaGuardia, daily weather, tuned/default sign, and shipped coverage card render correctly.
- **03, 06, 08, 09, 10, 11, 12, 13:** each rendered all 8 sections with its corrected claims; no raw fences or Vite overlay. Project 10 rendered the headline CI row and exactly 3 Results figures; project 13 rendered `4.0%`, `0.96–1.04`, `65.4/63.1 ms`, and the p50 header.
- **Forecast Workbench:** historical payload label and weights, `0.6161` versus `0.8929`, and current champion evidence `0.6211 (−30.4%)` render. Clicking `7d` selects it, deselects `28d`, and updates the KPI to `WAPE @ 7d`; no error overlay.

This was a rendered-content and interaction check. No claim about console history is made because console-history injection was unavailable.

## Final gates

| Command | Result |
|---|---|
| `uv run python scripts/lint_story_language.py` | PASS — 14 stories, 0 errors, 0 warnings |
| `uv run python scripts/check_headline_numbers.py` | PASS — 13 claims, 0 findings |
| `uv run python scripts/check_short_copy.py --check` | PASS — 42 surfaces across 14 stories |
| `uv run python scripts/check_docs.py` | PASS |
| `uv run python scripts/check_demo_contract.py` | PASS — demo contracts and current static registry |
| `uv run python scripts/check_figure_budget.py` | PASS — one existing 519 KiB warning |
| `uv run python scripts/check_figure_axes.py` | PASS — three existing over-wide-window warnings |
| All three generators, plain and `--check` | PASS — registry current, short map current, 28 routes current |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS — 978 files already formatted |
| `uv run mypy libs projects apps` | PASS — 266 source files, no issues |
| `uv run mkdocs build --strict` | PASS |
| `cd apps/showcase-web && npm test` | PASS — 56 test files, 754 tests |
| `npm run lint` | PASS |
| `npm run build` | PASS — TypeScript and Vite production build |
| `uv run pytest -q` | PASS — exit 0, 100% completed, 97.14% coverage |
| `git diff --check` | PASS |

The three initially failing tests were stale guards, not evidence regressions. They now retain metric checks while allowing the intentional prose/figure changes: project 02 no longer requires redundant AutoETS/intermittent percentages in README and checks the historical-blend disclosure; project 10 checks horizontal forest-plot `y`, numeric `x`, and `error_x`. The three targeted tests pass, followed by the green full suite.

Non-fatal existing warnings remain: React `act(...)` test warnings, Vite chunk-size warnings, one figure-size warning, three over-wide-axis warnings, and upstream Python deprecation/user warnings. MkDocs also prints its upstream Material warning and the existing non-nav page list; strict build succeeds.

## Repository state

- Branch: `wave8-articles-truthfulness-2026-11-25`; HEAD remains `c05accd0`.
- `git diff --stat c05accd0`: 94 tracked files changed, 1,372 insertions, 1,641 deletions. This includes the pre-existing uncommitted Wave 8 working tree plus these round-3 corrections.
- `git diff --check`: PASS.
- `git diff --exit-code c05accd0 -- projects/01-rag-agent projects/15-dynamic-pricing-rl`: PASS; scoped status is empty.
- Existing untracked collaboration/design/review directories remain untracked, alongside the two new closeout surfaces. No unrelated files were cleaned up or reverted.
- Working tree remains uncommitted for owner and Claude review. No commit was created.

## Fix-pass gates (2026-11-26, fix list `20261126-wave8-round3-closeout-fixes`)

Cheap: gen_static_registry --check exit=0; gen_story_short --check exit=0;
gen_route_manifest --check exit=0; lint_story_language exit=0 (0 errors, 0
warnings); check_headline_numbers exit=0; check_short_copy --check exit=0;
check_docs exit=0; check_demo_contract exit=0; ruff check exit=0; ruff format
--check exit=0; git diff --check exit=0.

Full: pytest --cov exit=0 (1482 passed, coverage 97.14%); mypy libs projects
apps exit=0 (266 files); mkdocs build --strict exit=0; npm test exit=0 (754
passed); npm run lint exit=0; npm run build exit=0.

Fix details and the change table: `20261126-wave8-round3-closeout-fixes/01-kimi-report.md`.
