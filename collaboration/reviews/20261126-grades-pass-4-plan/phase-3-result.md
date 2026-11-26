# Grade pass 4, Phase 3 (figures): result

Branch: `wave8-articles-truthfulness-2026-11-25`. Commit: see below (single
Phase C commit). Scope: §4 figure rows + §3.2 mechanics for projects 01–11
and 13 (12 deferred until E4 per the brief).

## Mechanics used

- Titles state a finding in ≤ 90 chars; caveats moved to subtitles.
- Every title number verified against the figure's own trace data or the
  committed `metrics.json` before writing; spec/template numbers that did not
  match the data were replaced with data-verified values (deviations below).
- Hand-patched JSONs: only `layout.title` (plus the two authorized axis fixes
  and the two authorized data changes). Structural equality of `data` vs HEAD
  verified for all 52 touched figure JSONs; the only data diffs are the
  authorized ones (03 telemetry downsampling + trace renames, 03 range_pr
  trace rename, 06 gap_pct tie threshold in the generator).
- Serialization matches plotly's compact `write_json` format (no indent, no
  trailing newline, raw UTF-8). 10/11/13 were patched surgically on raw bytes
  after catching that a full `json.dumps` rewrite rewrites small-float
  notation; other projects verified structurally equal.
- Generator strings synced for every patched figure; dynamic (computed)
  titles preferred where the generator has the inputs. Guarded fallbacks keep
  tiny-fixture tests green (06, 02).
- One committed-title consistency test added per touched project
  (01, 03, 04, 05, 06, 07, 08, 09, 10, 11, 13).

## Per-project figures

- **01**: chunk_size_sweep ("All chunk sizes tie on recall@5 (0.831);
  200-token chunks lead MRR@5 (0.808)" — corrected from the plan's "best
  recall@5" framing after the data showed a three-way recall tie),
  model_comparison (tie + MRR edge), failure_taxonomy (10 empty vs 1
  unsupported), eda_corpus_composition (Aviation 125 of 593),
  retrieval_ladder (S3 0.924→0.946; axes fixed to the bars-pin-zero [0, 1.1]
  convention after the gate flagged yaxis2 — an earlier truncated-range patch
  was reverted because it clipped Wilson whiskers).
- **02**: m5_full_sample_series dropped (superseded 0.6161 blend; E9 restores
  a regenerated version in Iter 3). pooling_panel retitled dynamically
  ("The floor wins on zero-sales days (66.6% vs 57.2%)…", guarded fallback).
  EDA prose rewritten to stop narrating the deleted figure; README figure
  list updated. Known temporary lint warning: eda section has no visual
  until E9.
- **03**: telemetry_flags downsampled 519→226 KiB (min-max bucket=5, spikes
  preserved; markers untouched) and retitled "Served-model flags …: 17 of
  120 hit injected anomalies" (17/120 recomputed from traces);
  range_pr retitled with the detector name (IsolationForest, verified above
  the band at every recall level, min margin +0.498); nab_score_distribution
  overlap title (medians −0.069 vs −0.186, heavy overlap); pr_curves title
  computed dynamically (ocsvm_tuned AP 0.136 vs 1.89% floor). Unreferenced
  score_distribution.{json,html} deleted; static registry regenerated.
- **04**: six figures retitled. Deviation: training_curve — the spec's
  "extra probe epochs do not improve it" was false (probe peaks 0.9477 >
  0.9464); title now states the +0.0013 probe edge.
- **05**: five figures retitled; fairness_slices gained the spec subtitle
  ("raw model at t = 0.225, not the served policy"). Deviation:
  permutation_importance — a single feature is 42% (not "most"), so the
  title names the top-2 pair (76%).
- **06**: gap_pct tie threshold (−0.005%) applied in the generator
  (figures.py:31): 8 → 5 undercuts, ties C108/C109/C207 excluded; title and
  subtitle updated. Deviations: solver_profile "all 56" → 52 of 56
  (alns_fleet takes 4); family_gap spec text was muddled (C families have
  the highest mean gap, not the easiest) — title uses the figure's own
  family means (worst 6.50% C2); pareto "ALNS" → "The ALNS arms" (alns and
  alns_fleet both sit near 4% at ~1 s); eda_instance_map "minutes" →
  "units" (Solomon times are abstract units).
- **07**: hour_borough_heatmap appears in exactly one story section, so it
  was retitled (not dropped): "Manhattan peaks at 103.7 pickups/zone-hour at
  18:00; the Bronx tops out at 0.73". Deviation: weather_elasticity — the
  spec's "outside Manhattan" was false (Brooklyn/Bronx/EWR above dry); the
  title names Manhattan, Queens and Staten Island (−3% to −11%).
  conformal_coverage subtitle now carries the second-half caveat.
- **08**: three figures retitled (4-bit MoE leads at every concurrency;
  p95 0.81 s → 7.80 s; MLX 2.9× Q8_0 llama.cpp with the quantization caveat
  kept in the subtitle). No discrepancies.
- **09**: four figures retitled; "(legacy recorded run)" dropped from titles
  (run date stays in subtitles). No discrepancies.
- **10**: five figures retitled; qini_per_arm axes-gate fix (layout only:
  xaxis range now contains every CI whisker at 3.87× span). Deviation:
  cuped_variance covers conversion/visits, not "spend" — title uses the
  plotted outcomes (0.08% / 0.52%).
- **11**: three figures retitled (×19.2 / ×14.9 / ~29× slower; slopes 0.73,
  0.63; sqlite 1,520 MB peak). No discrepancies.
- **13**: four figures retitled; hardware/cost caveats moved from titles to
  subtitles. "at most 4%" holds at displayed precision (max deviation
  4.03% at c=4).

## Gates

- `check_figure_axes.py`: 0 warnings (was 2 at phase start).
- `check_figure_budget.py`: 0 over the warn line (was 1: telemetry_flags).
- `gen_static_registry.py --check`: current.
- `check_headline_numbers.py`: 16 claims, 0 findings.
- `lint_story_language.py`: 0 errors, 1 warning (02 eda no-visual; expected
  until E9 restores the sample-series figure).
- `check_short_copy.py --check`, `gen_story_short.py --check`: current.
- `check_docs.py`: OK. `check_demo_contract.py`: OK.
- Project suites: 01 186, 02 208, 03 112, 04 86, 05 64, 06 176, 07 67,
  08 18, 09 100, 10 70, 11 47, 13 36 — all passed.
- Web: 768 tests passed (56 files).
- Docs PNGs re-rendered via `scripts/export_readme_figures.py`; changed
  figures visually checked.

## Not done (per brief)

- 12 figures: deferred until E4.
- "After E-n" figure additions (04 cascade CI whiskers, 05 per-split strip):
  Phase D.
- No git push, no deploy.
