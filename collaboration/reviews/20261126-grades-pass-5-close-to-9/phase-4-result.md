# Phase 4 result — project 12 option B promoted, LightGBM served in 13

Date: 2026-11-26. Executor: Kimi Code (subagent). Scope: phase 4 of
`04-revised-execution-plan.md` as approved in `05-phase-4-approval.md`.
No hosted calls. No git mutations beyond the phase's own commits (no push).

## Commits (branch wave8-articles-truthfulness-2026-11-25)

| hash | message |
|---|---|
| `405d579c` | fix(13-model-serving): move report analysis block out of _meta |
| `a46cf5f3` | feat(12-tabular-ml-lifecycle): promote v2 recipe (timestamp lags, keep-higher-MI pruning); v1 kept under previous_runs.v1 |
| `96b25cbb` | feat(13-model-serving): regenerate from 12's v2 recipe, serve LightGBM (native + ONNX) |
| `34f59274` | feat(12,13): promote v2, serve LightGBM — copy, headline gate re-key, derived copy |
| `4e20a2b4` | style(13-model-serving): wrap long assert in test_figures (ruff E501) |

Step-1 commit is code-only (no committed artifact touched). Steps 2, 3, 4 are
the approval's three commits; the style commit is a one-line lint fix that
belonged in step 3.

## Gates — exit codes (final sweep, this working tree)

| gate | exit | notes |
|---|---|---|
| lint_story_language.py | 0 | 0 errors; 3 advisory Flesch warnings (12 training 44.7, 13 data 44.4, 13 eda 43.3; floor 45) |
| check_short_copy.py --check | 0 | 42 surfaces single-sourced |
| gen_story_short.py --check | 0 | current |
| gen_static_registry.py --check | 0 | current |
| gen_route_manifest.py --check | 0 | 28 routes |
| check_headline_numbers.py | 0 | 23 claims, 0 findings |
| check_docs.py | 0 | |
| check_demo_contract.py | 0 | |
| check_figure_axes.py | 0 | 1 over-wide-window warning on 04's llm_cascade_comparison.json (pre-existing, not this phase) |
| check_figure_budget.py | 0 | |
| check_diagram_fences.py | 0 | |
| git diff --check | 0 | |
| mkdocs build --strict | 0 | 14 project pages built |
| 12: ruff check / format / mypy / pytest | 0 / 0 / 0 / 0 | 44 passed |
| 13: ruff check / format / mypy / pytest | 0 / 0 / 0 / 0 | 36 passed |
| scripts/tests | 0 | 32 passed (`-o addopts=""`; root addopts force a libs coverage gate) |
| libs/portfolio-core pytest | 0 | 131 passed |

## 13 reproduction / parity gates (quoted from reports/train_run.json)

- Reproduction: expected 23.76360139335002, derived 23.76360139335002,
  **abs_diff 0.0** (tolerance 0.05) — **PASS**. 12's v2 LightGBM re-derived
  bit-for-bit in 15.3 s (seeded 50-trial HPO + final fit).
- Parity: max-abs **2.646e-4 rentals** on 512 seeded probe rows, limit
  6.791e-3 (tolerance 1e-4 + float32 rel term 1e-5, opset 15) — **PASS**.
  The exported TreeEnsemble is float32; the deviation is kernel-order noise
  at ~4e-7 relative, exactly the case the relative term exists for.
- 12's own v2 pipeline reproduced the E4 variant numbers bit-for-bit (all
  five candidates, `metrics.json` vs `sensitivity_pruning_lags.json`
  variant block, max abs diff 0.0).

## Numbers that changed, and why (all inside 12/13)

**12 `reports/metrics.json`** (v1 → v2, `previous_runs.v1` keeps every v1 block):
- served model: MLP (25.4316) → LightGBM (**23.7636**); champion key `mlp` → `lightgbm_hpo`.
- per-model test MAE: floor 83.20→72.98, ridge 51.09→48.68, RF 26.32→26.13,
  LightGBM 25.37→23.76, MLP 25.43→27.16 (RMSE/MAPE regenerated likewise).
- floor gain: 57.77 [52.49, 63.07] → **49.21 [44.43, 53.99]**; day/week
  sensitivity intervals regenerated ([37.37, 61.16], [33.00, 63.84]).
- validation tie interval: −0.18 [−1.71, +1.21] (tie) → **+3.19 [+1.79, +4.54]**
  (LightGBM wins validation, no tie).
- `data/feature_selection.json`: v2 selection (keeps `atemp`, drops `temp`)
  + `nan_lag_policy` block (250 train / 43 val rows dropped, 28 test cells
  median-imputed).
- figures: all model figures regenerated from v2; the 3 EDA figures'
  data JSONs were byte-identical (their tracked .html restored to avoid
  div-id churn). `sensitivity_pruning_lags.json` untouched (E4 record).
- `_meta`: carried over from v1 verbatim — **stale until the central
  restamp** (params/uv-lock hashes predate v2); restamp is the plan's
  central step, not run here.

**13 (full regeneration)**: champion `lightgbm` 23.7636 (was MLP 25.4316);
reproduction/parity blocks above; bench regenerated (native c1 p50 1.97 ms,
c4 knee 1,012 req/s, b128 28.2k rows/s; ONNX c1 p50 2.36 ms, b128 40.9k
rows/s; RSS 213/113 MB; 0 errors in 4,320 requests/backend); docker full
image **1,060 MB** (was 6,466 MB — torch removed from 13's deps), slim
**292 MB** (3.62×), both smokes passed; cost $1.16e-05 native / $1.71e-05
ONNX per 1k (declared 65 W, $0.30/kWh). `previous_runs.v1` keeps the v1
champion/reproduction/parity/serving-headline blocks; `_meta` carried
(stale until central restamp). Deps: −torch, +lightgbm/optuna/onnxmltools
(uv.lock; central restamp covers the lock-hash drift repo-wide).

**Headline gate (`scripts/check_headline_numbers.py`)**: `_m12` re-keyed to
served LightGBM MAE (23.8) + floor gain (49.2) + v1 reference (25.43);
`_m12_sensitivity` **retired** (the E4 arm graduated to the main line; its
numbers live in the v1→v2 record the new `_m12` pins); `_m13` re-keyed to
2.0 ms. `scripts/tests/test_check_headline_numbers.py` pins no 12/13 values
(verified — no edit needed). 13's reproduction constants updated in
`config.py`/`params.yaml`/`test_config.py` (23.7636 target, 27.161 cited
comparison).

**Copy**: 12 + 13 story.yaml/README/docs pages rewritten to the v2 truth
(served LightGBM; "v2 fixes two disclosed defects; v1 remains for
comparison; the corrected MLP is worse (27.16 vs 25.43), the corrected
LightGBM is better (23.76 vs 25.37)"; 13 names LightGBM as served, no
"champion" in reader-facing copy, "reproduces 25.4316" → "reproduces
23.7636"). Root README + docs index 12/13 rows updated (staged via
HEAD+my-hunks only — the uncommitted 09 docs-handoff hunks in those files
were left unstaged). `storyShort.ts` regenerated (12/13 lines staged;
the 09 line stays uncommitted for the docs-handoff commit).
`staticRegistry.ts` left uncommitted: its working-tree diff is purely E9's
in-flight 02 reflections; HEAD already carries 12's `sensitivity_pruning_lags`
figure (my stories changed no figure lists).

## Stop conditions — status

- ONNX parity or reproduction gate fails: **NO** — both passed (above).
- Committed number changes beyond the v1→v2 change in 12 and 13: **NONE** —
  `git diff --name-only c53069eb..HEAD` outside 12/13 is only `uv.lock`
  (13's dep change), `scripts/check_headline_numbers.py` (the re-key this
  phase owns), `storyShort.ts` (12/13 lines), root `README.md` +
  `docs/projects/index.md` (12/13 rows). No other project's files touched.
- Hardware/data outside this plan: **NONE** — Docker daemon present
  (linux/aarch64), pinned UCI fetch, zero hosted calls.

## Grades before/after (plan's axes: Contents/Results/Technologies/Visualizations)

- **12**: before 8/9/7/8 (8.0, cap T — committed run carried the pruning and
  lag defects). After option B: the defects are fixed in the committed run
  (T 7→9), the copy states the v1→v2 story plainly with v1 preserved (C 8→9),
  and the sensitivity figure plus regenerated v2 figures state findings
  (V 8→9). Projection per the pass-4 plan: **9/9/9/9 → 9.0**.
- **13**: before 8/9/9/8 (8.5, cap C — stale "Champion" cell, MLP-centric
  copy). After re-derivation from v2 with LightGBM served: reader copy names
  LightGBM and drops "champion" (C 8→9), figures regenerated with
  finding-stating data-driven titles (V 8→9). Projection per the pass-4
  plan: **9/9/9/9 → 9.0**.

## Follow-ups for the orchestrator (not this phase)

1. **Central restamp**: 12's and 13's `metrics.json` `_meta` blocks are the
   v1 stamps (stale params/uv-lock hashes by design); `stamp_metrics_meta
   --check` fails until the central restamp runs. uv.lock changed (13 deps),
   so every project's `uv_lock_sha256` stamp drifts — the plan's central
   restamp covers all 17.
2. **12 `dvc.lock` is stale (v1)**: repo-wide `dvc repro` is blocked by the
   in-flight 01 `dvc.yaml` output-overlap (2b's work; graph build fails
   before any stage runs), and `dvc commit` refuses the SCM-tracked figure
   outs. Refresh with `dvc repro` once 01 lands. The v2 artifacts themselves
   are committed and reproducible via the CLI stage commands.
3. **Docs-handoff commit (Phase 7)**: the working tree still holds the 09
   docs-handoff hunks (root README, docs index, 09 story, storyShort.ts 09
   line) and E9's 02 files — untouched by this phase. The two docs-handoff
   hunks that were in 12's README/story at phase start were superseded by
   the approved v2 copy in commit `34f59274`.
4. **Advisory Flesch warnings** (12 training 44.7, 13 data 44.4, 13 eda
   43.3 vs floor 45) — warnings only, gate exits 0; tighten prose in a
   future copy pass if desired.
