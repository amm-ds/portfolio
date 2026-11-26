# Grades pass 2 — closing the post-deploy gaps

Date: 2026-11-26 · Reviewer: Claude (review lane, implementation explicitly assigned for this pass) · Base: `acf6f9f7`.
Input: `collaboration/reviews/20261126-post-deploy-grades/00-grades.md`.

No git mutations, no training, refits, benchmarks, experiments, hosted or paid calls. No headline number changed. All edits are uncommitted in the working tree.

**Branch note for the orchestrator:** the working tree is on `main` at `acf6f9f7`, not on `wave8-articles-truthfulness-2026-11-25`. I did not switch branches (no checkout allowed). Create or switch the branch before committing.

## 1. Redeploy blocker (item 1)

Nothing to fix in the repo. Production still serves `c05accd0` (per the input report §0). After committing, redeploy and confirm `/health` sha = the new HEAD and 0 "champion" hits on the live 13 story. Until then, none of the copy fixes below are live on the app. The mkdocs site updates on push.

## 2. What changed

Paths are relative to the repo root. "Old → new" lists the load-bearing strings.

### Project 03 — `threshold_sweep` subtitle (item 2)
- `projects/03-anomaly-detection/src/anomaly_detection/evaluate.py:377`: `"flags hit real incidents"` → `"flags hit injected anomalies"`.
- Regenerated through `uv run python -m anomaly_detection.cli evaluate` (scores saved models; no training).
  - `reports/figures/threshold_sweep.json`: `data` byte-equal to the previous file; only `layout.title` changed. Subtitle now reads `ocsvm_tuned; dashed = fixed 2% operating point — 17/120 flags hit injected anomalies`.
  - The caption (`story.yaml:326-327`, "17 of 120 flags hit injected anomalies, 14.2% precision") now agrees.
  - The run also rewrote `metrics.json` (dropped the `_meta` stamp, reordered keys; values identical), `eda_signals_overview.json`, `telemetry_flags.json` and `report.html` (the committed report was older than the committed figures). All four were **restored** from the saved bytes. In `report.html`, only the one subtitle string was then replaced (1 occurrence).
- `projects/03-anomaly-detection/README.md:92`: `"…window semantics instead (owner decision,\n2026-11-18)."` → `"…window semantics instead."`
- `projects/03-anomaly-detection/story.yaml:22`: `"Next, the four rules that keep the test fair"` → `"Next, four rules keep the test fair"` (it now has a verb and stays under the 150-word first-section cap).

### Project 08 — `engine_panel` subtitle and the MLX 31B label (item 3)
- **Label chosen: "unrecorded quantization".** The committed evidence (`reports/metrics.json` cells `gemma4:31b` / `gemma4:31b-mlx`, `src/inference_serving/config.py`, `data/bench_run.json` model tags) records no MLX precision. `story.yaml:171` already said "No committed artifact establishes precision for the plain gemma4:31b". Nothing supports "4-bit".
- `src/inference_serving/figures.py:189`: `f"same gemma4:31b weights on {hw} at c=1 …"` → `f"same model family on {hw} at c=1 …"`. The docstring (`:159`) changed from "(gemma4:31b weights)" to "(gemma4:31b; quantization differs)".
- Regenerated through `uv run python -m inference_serving.cli report` (offline, from `data/bench_run.json`).
  - `reports/figures/engine_panel.json`: `data` byte-equal; only the title changed.
  - The run rewrote `metrics.json` (dropped `_meta`, reordered keys; cells identical) and `report.html` (random div ids). Both were **restored**. In `report.html`, only the subtitle string was then replaced (1 occurrence).
- `story.yaml:7` (`quality_quant` caption): `"The 4-bit, QAT-int4, and Q8_0 arms"` → `"The MLX, QAT-int4, and Q8_0 arms"`.
- `story.yaml:14` (`engine_panel` caption): `"MLX 4-bit reaches"` → `"MLX (unrecorded quantization) reaches"`.
- `story.yaml:260`: `"MLX 4-bit reaches 18.8 tok/s"` → `"MLX with unrecorded quantization reaches 18.8 tok/s"`.
- `story.yaml:296`: `"the MLX 4-bit build"` → `"the MLX build (unrecorded quantization)"`.
- `README.md:55`: `"on the same models;"` → `"on the same model family (MLX quantization unrecorded);"`.
- `DESIGN.md:61`: `"(Q8_0 vs 4-bit)"` → `"(Q8_0 vs unrecorded MLX quantization)"`.
- `docs/projects/08-inference-serving.md:21`: `"— both external audits' #1 recommendation."` removed.
- `docs/projects/08-inference-serving.md:51,59`: `"MLX 4-bit beats GGUF Q8_0"` → `"MLX (unrecorded quantization) beats GGUF Q8_0"`, in both the text and the alt text.
- `docs/assets/projects/08-inference-serving/engine_panel.png`: re-rendered with `render_png` from `scripts/export_readme_figures.py`. I checked it visually against the old PNG: same bars and layout, new subtitle only.
- Remaining uses of "4-bit" in 08 refer to the Q4_K_M MoE and are correct.

### Project 10 — headline CI evidence (item 4)
- **Option chosen: state the source and gate it.** No number changed, and `metrics.json` was not edited.
  - Editing `metrics.json` would break the `_meta` lineage contract (`scripts/stamp_metrics_meta.py --check`).
  - The paired intervals already sit in committed `reports/report.html` ("T-learner vs baselines, with intervals").
- Root cause, recorded for later: `evaluate.py` writes the intervals to `metrics["_meta"]["ci"]`, and the provenance stamp (commit `0ebefee3`) replaced `_meta`. The same values are in history at `0c01c45d` (`_meta.ci.t_learner_vs_random.profit_at_budget_diff_ci = [717.58, 4766.66]`), which matches the article's [+$718, +$4,767].
- `scripts/check_headline_numbers.py` `_m10` now parses both paired T-learner-minus-baseline intervals from `report.html` and requires them on README and story: `+$718`, `+$4,767`, `−$13,125`, `−$5,808`. Label: `"delta vs random + two-arm size + paired baseline CIs (report.html)"`.
- `story.yaml:313`: `"Paired differences (the same resample across policies):"` now continues with "These two-arm intervals are persisted in `reports/report.html`; `reports/metrics.json` holds the point estimates."
- `README.md:100`: "(T-learner minus comparator)" → "(T-learner minus comparator; intervals from `reports/report.html`)".
- `README.md:186-190` and `docs/projects/10-uplift-experimentation.md:100-102` claimed `metrics.json` holds `_meta.cuped/power/ci/cost_sensitivity/deciles`. That was false (the committed `_meta` is the provenance stamp). Both now say what `metrics.json` and `report.html` actually hold.
- Tests: `scripts/tests/test_check_headline_numbers.py` gained `test_m10_reads_paired_baseline_intervals_from_committed_report` and `test_m10_claim_verifies_against_real_repo`.

### Project 15 — five diagrams (item 5)
- New hand-built spec `apps/showcase-web/src/diagrams/pricingPipeline.ts` (`15-pricing-pipeline`).
  - Nodes: Calibrate from M5 → Train with action masks / Lock tuned B1 → One sealed test → Negative verdict.
  - Every fact is a sentence or number from `story.yaml` or `reports/metrics.json`.
  - Registered in `src/diagrams/index.ts` and added to the placement and fact-evidence maps in `src/__tests__/diagramSpecs.test.ts`.
- New section specs `src/diagrams/auto/15-dynamic-pricing-rl-{1..4}.ts`, one per section, each drawing only what that section states:
  - objectives: P1, P2 and P3 gates leading to the verdict;
  - data: pinned files → calibration → item split, plus the elasticity prior → hashed specs;
  - training: env, mask, encoder, MaskablePPO, seeds and validation pick;
  - conclusions: result → reusable assets → development splits → fresh sealed protocol.
- These are hand-built because the story never had mermaid source. Each file says so, and `facts: []` follows the auto convention.
- `src/diagrams/auto/index.ts` was regenerated by `node scripts/mermaid-to-flow.mjs`. It converted 0 blocks, added the 4 new entries and synced 0 titles.
- All five fences are now registered and embedded. The fences were already in `story.yaml:9,27,43,70,126`.
- **New check (Python):** `scripts/check_diagram_fences.py`, with tests in `scripts/tests/test_check_diagram_fences.py`. It fails when a `projects/*/story.yaml` fence names an id that is not in `diagrams/index.ts` or `diagrams/auto/index.ts`. Run against HEAD's registry, it reports exactly the 5 missing 15 ids. It passes now: 71 fences, 77 specs, 0 unresolved.
- **New check (vitest):** `diagramSpecs.test.ts`, "registers every diagram id referenced by a project story", checks the same thing through the real `getDiagramSpec`.
- Not done (outside my allowed paths): adding `check_diagram_fences.py` to `.github/workflows/ci.yml`.

### Wording pass (item 6)
- `projects/01-rag-agent/story.yaml:154`: `"reconciled against passage text with the reviewer audit, hitting"` → `"re-checked against the cited passage text and corrected, hitting"`.
- `projects/01-rag-agent/README.md:77`: `"During the reviewer audit the owner also re-checked"` → `"The owner also re-checked"`.
- `projects/01-rag-agent/README.md:175`: `"closes the loop the audits asked for"` → `"tests the pipeline outside its tuning loop"`.
- `projects/03-anomaly-detection/README.md:92`: see §03.
- `projects/06-routing-optimization/story.yaml:403`: `"pin an owner-approved size"` → `"pin one instance size"`.
- `docs/projects/07-open-data-mobility.md:102`: `"productionized (wave 15):"` → `"productionized:"`.
- `docs/projects/08-inference-serving.md:21`: see §08.
- `docs/projects/09-agentic-workflows.md:238`: `"report after the audit-P1 split)"` → `"report)"`.
- `projects/12-tabular-ml-lifecycle/reports/metrics.json:38` is copy (the `validation_tie_interval.interpretation` value), not a key. `"per owner decision 8 … not a proven champion."` → `"per the stated protocol … not a proven winner."`.
  - **The orchestrator must restamp this single file after committing**, as done for 15 in `07be7998`. Otherwise `stamp_metrics_meta.py --check` flags it.
  - The generator string in `src/tabular_ml_lifecycle/stages.py:478-481` was changed to match.
- `projects/15-dynamic-pricing-rl/story.yaml:84`: `"The owner committed the frozen params, calibration, and splits before evaluation."` → `"The frozen params, calibration, and splits were committed before evaluation."`.
- `projects/15-dynamic-pricing-rl/story.yaml:117`: the splice `"; next, the limits…"` → `". Next come the limits…"`.
- **"Champion", project 12:**
  - `figures.py:390` axis: `"MAE(floor) - MAE(champion)"` → `"MAE(floor) - MAE(served MLP)"`. Regenerated through `figures.bootstrap_ci_figure` (see §3). JSON `data` byte-equal; only `xaxis3.title` changed.
  - `bootstrap_ci.html` restored, then the same string replaced.
  - `report.html`: the embedded axis string and protocol `"The champion-vs-floor MAE gap"` → `"The served-model-vs-floor MAE gap"`. The same protocol change was made in `results.md`, `evaluation_metadata.json` and the generator `stages.py:509`.
  - `docs/projects/12-tabular-ml-lifecycle.md:24,61,63`: "the champion is the validation leader" → "the served MLP is the validation leader (tied with LightGBM)"; "← champion" → "← served (validation tie)"; "Champion vs floor" → "Served MLP vs floor".
  - `docs/assets/projects/12-tabular-ml-lifecycle/bootstrap_ci.png`: re-rendered and checked visually.
  - Diagrams: `lifecyclePipeline.ts` ("Champion MLP…" → "Served MLP…; validation MAE 34.2, tied with LightGBM."; "Champion beats…" → "The served MLP beats…"; edge label "champion" → "served MLP"); `auto/12-tabular-ml-lifecycle-2.ts` ("champion pick" → "model pick"); `auto/12-tabular-ml-lifecycle-3.ts` ("MAE(champion)" → "MAE(served MLP)").
- **"Champion", project 13:**
  - `src/model_serving/report.py:147`: `"Champion re-derivation:"` → `"Served-MLP re-derivation:"`. Regenerated through `uv run python -m model_serving.cli report`.
  - `results.md:5` kept as generated.
  - The run also rewrote `metrics.json` (lineage), `report.html` and the `hardware` block of `evaluation_metadata.json` (`i386` → `arm`). These were **restored**. In `evaluation_metadata.json`, only the protocol string was then replaced (`report.html` had no occurrence).
  - The live page's diagrams also carried the label, and were fixed too: `servingPipeline.ts` "Re-derive champion" → "Re-derive served MLP"; `auto/13-model-serving-1.ts` "rebuild champion" → "rebuild served MLP".
- Left as is: "champion" in 02, 03 and 06 is the normal model-selection term in those projects and was out of scope. `champion` JSON keys in 12/13 metrics are keys.

### Project 09 — live evidence (item 7)
- New folder `projects/09-agentic-workflows/reports/live_confirmation_20261119/`.
  - Byte-identical copies of `collaboration/reviews/20261118-live-confirmation/heldout_live_records.json` (sha256 `b1561ec6…d3b3`) and `live-grading/metrics.json` → `live_grading_metrics.json` (sha256 `d3a6fbed…c793`).
  - A short `README.md` gives provenance and counts (13/13, 6/6, 19/19, 19/19), each read from the copied grading file. No new numbers.
  - The run logs were not copied.
- `story.yaml:204`: link moved from `collaboration/reviews/…/comparison.md` to `tree/main/projects/09-agentic-workflows/reports/live_confirmation_20261119`.
- `README.md:29-31`: now links the folder.

### Conclusion order (item 8)
- Target order (project 01): What the experiment taught → Limits → Exact numbers → (Measured alternatives) → Protocol.
- 02, 04, 05, 06, 07, 08, 09, 10, 11 and 13: the `## Limits` block was moved, unchanged, from after Protocol to just before `## Exact numbers`.
  - Any diagram fence or action paragraph inside the block moved with it.
  - `**In plain terms:**` stays last.
  - `## Results summary` stays first, because 01 has no such section.
- 05 has no "Taught" section. 06 and 08 use "What the results/evidence shows" as their taught section.
- Web rendering is unchanged: `StorySection.splitConclusionsTechnical` already lifts a trailing Limits into the visible narrative. Either order renders as summary + taught + limits visible, with exact + protocol collapsed.
- 03 and 12 were already in 01 order.
- 15 had only Limits. It now has What the experiment taught → Limits → Exact numbers → Protocol. Every number is quoted from `story.yaml` / `reports/metrics.json`: 0.5120/0.5217/0.5291, −0.009696 [−0.011437, −0.007998], −1.86%, 96.76/98.60%, 97.36/96.90/95.74%, stress 0.5450/0.5649/0.5356 and 0.4817/0.4837/0.4753, 0 violations, splits 140/30/30 and 267/57/58, seeds and steps, 2,000 resamples with seed 42.
- Not aligned: `scripts/new_project.py` still writes Limits after Protocol. The docs pages (`docs/projects/*.md`) are hand-authored with their own layouts, and were not restructured.

### Keep-at-level checks (item 9) and extra fixes
- 11 `story.yaml:123`: the pointer said the next figure was in Evaluation. It now points to Training, where `speedup_overview` actually is.
- 04: the headline gate now covers 04. `_m04` reads fresh macro-F1 0.9529 → 0.9539 and $0.023671 from `reports/llm_cascade.json`. `KNOWN_DRIFT` is now empty, and its test was updated. The gate now checks 14 claims with 0 findings.
- 06, 11, 13: no regressions. All their gates pass. 13's copy and diagrams no longer say "champion".

## 3. Regenerated files and metadata restoration

| File | Generator | Metadata/lineage restored? |
|---|---|---|
| 03 `reports/figures/threshold_sweep.json` | `anomaly_detection.cli evaluate` | n/a. Data byte-equal, title only |
| 03 `reports/metrics.json`, `figures/eda_signals_overview.json`, `figures/telemetry_flags.json` | (same run, unintended) | **Restored** to committed bytes |
| 03 `reports/report.html` | (same run) | **Restored**, then 1 subtitle string replaced |
| 08 `reports/figures/engine_panel.json` | `inference_serving.cli report` | n/a. Data byte-equal, title only |
| 08 `reports/metrics.json` | (same run) | **Restored** (`_meta` stamp kept) |
| 08 `reports/report.html` | (same run) | **Restored**, then 1 subtitle string replaced |
| 12 `reports/figures/bootstrap_ci.json` | `figures.bootstrap_ci_figure` called with the committed deltas and CI bounds decoded from the committed JSON (the evaluate stage would retrain ablation variants, and the MLP weights are not on disk) | n/a. Data byte-equal, axis title only |
| 12 `reports/figures/bootstrap_ci.html` | (same call) | **Restored**, then 1 axis string replaced (avoids a random div-id diff) |
| 12 `reports/report.html`, `results.md`, `evaluation_metadata.json`, `metrics.json` | targeted string edits. The report generator was not used: it reads `metrics._meta.champion/ci`, which the provenance stamp replaced, so it would print `?`/`nan` | no other bytes touched; `metrics.json` needs a post-commit restamp |
| 13 `reports/results.md` | `model_serving.cli report` | kept as generated (only line 5 differs) |
| 13 `reports/metrics.json`, `report.html`, `evaluation_metadata.json` | (same run) | **Restored**. The hardware block was reverted and the protocol string patched |
| `docs/assets/.../08-inference-serving/engine_panel.png`, `.../12-tabular-ml-lifecycle/bootstrap_ci.png` | `scripts/export_readme_figures.py:render_png` | n/a. Re-renders of unchanged figures are not byte-identical on this host (kaleido/font), so only these two were replaced. Checked visually |
| `apps/showcase-web/src/diagrams/auto/index.ts` | `node scripts/mermaid-to-flow.mjs` | n/a (+4 entries only) |

Saved previous bytes: `/private/tmp/claude-501/-Users-alejandro-work-portfolio/48d46ef9-c310-450a-accb-449e4a02945b/scratchpad/backup/` (03, 08, 12, 13 reports; 08, 12 docs assets).

## 4. Before/after grades

Same four axes and evidence rules as the input report. Overall is the mean of the four axes, rounded to one decimal. For the after column I read the edited copy, figures, specs and gates on disk. I did not look at the live app, and I did not inspect the new 15 diagrams in a real browser (they were checked by the jsdom render smoke test only).

| # | Project | Before C/R/T/V → overall | After C/R/T/V → overall | Change |
|---|---|---|---|---|
| 01 | RAG agent | 8/9/8/8 → 8.3 | 8/9/8/8 → 8.3 | review phrases removed; "owner-labelled" is in short_version (root README is outside my edit scope); ladder y-window and "65 golden questions" titles unchanged |
| 02 | Demand forecasting | 8/9/8/7 → 8.0 | 8/9/8/7 → 8.0 | order aligned; sample-series figure still shows the earlier blend |
| 03 | Anomaly detection | 7/9/8/6 → 7.5 | 8/9/8/8 → 8.3 | subtitle fixed; process phrase and verbless intro fixed; "Champion flags" title and the 519 KiB file remain |
| 04 | NLP + cascade | 7/9/8/8 → 8.0 | 7/9/8/8 → 8.0 | order aligned; headline now gated; glossary asides remain; cascade CI still missing |
| 05 | Churn | 8/9/8/8 → 8.3 | 8/9/8/8 → 8.3 | order aligned only |
| 06 | Routing | 8/9/9/8 → 8.5 | 9/9/9/8 → 8.8 | process word removed |
| 07 | Mobility | 8/9/8/8 → 8.3 | 9/9/8/8 → 8.5 | "wave 15" removed, order aligned |
| 08 | Inference serving | 6/9/6/6 → 6.8 | 8/9/6/8 → 7.8 | one quantization label, backed by evidence; audit voice gone; subtitle fixed and regenerated; Technologies needs experiments |
| 09 | Agentic workflows | 7/8/8/8 → 7.8 | 8/9/8/8 → 8.3 | live evidence now committed in the project; audit phrase gone; short-version jargon remains (root README) |
| 10 | Uplift | 7/7/7/7 → 7.0 | 8/9/8/7 → 8.0 | CI source stated and gated; false artifact lists fixed; `qini_per_arm` window unchanged |
| 11 | DataFrame engines | 9/9/9/8 → 8.8 | 9/9/9/8 → 8.8 | navigation fixed |
| 12 | Tabular lifecycle | 7/9/7/7 → 7.5 | 8/9/7/8 → 8.0 | "champion" gone from docs, report, axis and diagrams; owner phrase gone; Technologies needs a retrain |
| 13 | Model serving | 7/9/9/8 → 8.3 | 8/9/9/8 → 8.5 | `results.md`, metadata and diagrams cleaned; the live app stays stale until redeploy |
| 15 | Dynamic pricing RL | 8/10/9/5 → 8.0 | 9/10/9/8 → **9.0** | 5 diagrams registered and embedded, plus a fence gate; Exact/Protocol blocks added; process voice and splice fixed. Visualizations held at 8 until the diagrams are checked in a browser |

Target (overall ≥ 9.0, no axis < 8): met by **15 only**.
- Axes still below 8: 02 V7, 04 C7, 08 T6, 10 V7, 12 T7.
- Every other project sits at 8.0–8.8.

## 5. NOT REACHABLE WITHOUT EXPERIMENTS

| Project / axis | Gap | Experiment needed | Cost |
|---|---|---|---|
| 01 T (8) | One model family drafts, verifies and grades | Second-family judge over a fresh sealed `final_v4`; `final_v3` is consumed | Hosted calls: about $1 per 120-question pass at $0.0084/query, plus judge tokens; a new question set to author |
| 02 V (7) | `m5_full_sample_series` shows the superseded blend | Recompute recursive predictions for the final 0.6211 blend on the sample series | Refit-class compute; the committed runtime metadata records 1,348,530.6 s of summed compute for the full run |
| 03 T (8) | No official NAB score | Vendor the NAB scorer with its application profiles, then rescore | CPU minutes plus a new dependency; publishes new numbers |
| 04 T/R | No paired CI for the cascade gain | Re-run the cascade, persisting per-row decisions | Hosted LLM: 44 reviews, ~$0.024 estimated; new numbers |
| 08 T (6) | Quality is a saturated smoke check; one host; no quantization-matched cross-runner pair | A harder quality eval per arm, a second machine, and an MLX build with a recorded quantization matched to a GGUF | Hours of local inference per host (electricity only) plus access to other hardware |
| 09 T (8) | Single runs of 19 tasks | Repeated live held-out runs (for example 5×) | Hosted: ~$0.094 per 19-task run, so ~$0.5 for 5 |
| 10 V (7), T | `qini_per_arm` x-window 4.4× data span; `evaluate` writes intervals under `_meta`, where the stamp clobbers them | Fix the generator (write `ci` top-level), re-run `cli evaluate` (deterministic 1,000-rep bootstrap) and restamp | CPU minutes; rewrites committed `metrics.json`, `report.html` and figures, so it was not done here |
| 12 T (7) | Pruning drops `atemp` (higher MI); positional lags across the 36 h gap | Fix the rule and use date-aware lags, then retrain and re-evaluate | CPU ~1 minute (train 44.4 s + evaluate 13.3 s recorded); new headline numbers |
| 13 | none in-repo | Redeploy only | — |

Reachable without experiments, but not done in this pass:
- 01: figure-title wording ("65 golden questions") through its generator.
- 01/09: short-version jargon. This needs root `README.md`, outside my allowed edit paths, plus `check_short_copy`.
- 02: the ~100-word caption.
- 03: the "Champion flags" title.
- 04: the glossary asides.
- Adding the fence gate to CI (`.github/`, outside my allowed paths).

## 6. Exit codes

| Command | Exit | Note |
|---|---|---|
| `uv run ruff check .` | 0 | |
| `uv run ruff format --check .` | 0 | 992 files formatted |
| `uv run mypy libs projects apps` | 0 | no issues in 266 files |
| `scripts/lint_story_language.py` | 0 | 14 stories, 0 errors, 0 warnings |
| `scripts/check_short_copy.py --check` | 0 | 42 surfaces |
| `scripts/gen_static_registry.py --check` | 0 | |
| `scripts/gen_story_short.py --check` | 0 | |
| `scripts/gen_route_manifest.py --check` | 0 | 28 routes |
| `scripts/check_headline_numbers.py` | 0 | 14 claims, 0 findings (was 13, with 04 uncovered) |
| `scripts/check_docs.py` | 0 | |
| `scripts/check_demo_contract.py` | 0 | |
| `uv run mkdocs build --strict` | 0 | |
| `git diff --check` | 0 | |
| `scripts/check_diagram_fences.py` (new) | 0 | 71 fences, 77 specs, 0 unresolved; returns 1 against HEAD's registry (5 ids) |
| `npm test` (showcase-web) | 0 | 56 files, 767 tests |
| `npm run lint` | 0 | |
| `npm run build` | 0 | chunk-size warning only |
| pytest: `scripts/tests`, projects 03, 08, 09, 10, 12, 13, 15, `libs/portfolio-core`, `apps/showcase-api` | 0 each | run with `--no-cov` (the per-suite coverage floor applies to the full run) |
| `scripts/stamp_metrics_meta.py --check` (extra) | fails | **Already failing at HEAD** for 01, 02, 09 and 11, which I did not touch. 12 now joins until it is restamped after commit |
| `scripts/check_figure_axes.py` / `check_figure_budget.py` (extra) | 0 / 0 | same 3 axis warnings and 1 budget warning as before |

## 7. Readiness

**READY WITH LISTED GAPS.**
- Commit from the intended branch.
- Restamp `projects/12-tabular-ml-lifecycle/reports/metrics.json` (single file) after the commit.
- Redeploy and verify `/health`.
- Only 15 reaches the 9.0 target. The remaining gaps are listed in §5 (experiments) and in the "reachable, not done" list.
