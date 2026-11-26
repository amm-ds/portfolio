# Wave 8 pre-push review — HEAD `ebb889cf` plus working-tree edits

**Verdict: APPROVE WITH NOTES.** No HOLD blocker. Every cheap gate exits 0. The headline numbers spot-checked in 02–13 match committed artifacts. The uncommitted edits are copy-only or string-only, and they close the two cross-project items from `20261126-wave8-final-report/00-report.md:42-46` and the `03:115` splice. Six notes follow: residual labels and wording to fix in a follow-up pass. None of them is a false number.

Date: 2026-11-26 · Reviewer: Claude (review lane) · Branch `wave8-articles-truthfulness-2026-11-25`.
Scope: read-only. No project, app or docs file was edited, there were no git mutations, and no training, refit, benchmark, hosted call, or long pytest/npm suite was run. This file is the only file written.

---

## 1. Change set

| Check | Result | Status |
|---|---|---|
| `git status --short` | 12 modified tracked files, 1 untracked dir (`collaboration/reviews/20261126-wave8-final-report/`, files `00-report.md`, `01-orchestrator-push-message.md`) | verified |
| `git diff --stat ebb889cf` | 12 files, +30/−30: `staticRegistry.ts`, `docs/projects/13-model-serving.md`, `02/README.md`, `02/story.yaml`, `03/story.yaml`, `13/{DESIGN.md,README.md,portfolio.yaml,reports/report.html,reports/results.md,src/model_serving/report.py,story.yaml}` | verified |
| Projects 01 and 15 untouched | `git diff --stat ebb889cf` and `git diff --stat main...HEAD` over `projects/01*`, `projects/15*` and `docs/projects/01*`/`15*` are both empty | verified |
| `bench_run_repeat.json` | Exists only at `projects/08-inference-serving/data/bench_run_repeat.json`. Not tracked (`git ls-files` no match), not staged (`git diff --cached` empty), ignored by `.gitignore:15` (`data/`) | verified |
| Stash | `git stash list` empty | verified |
| Untracked files | Only the collaboration review folder above. This review folder is added by this pass. | verified |
| Branch vs main | `git log main..HEAD` = `ebb889cf` only | verified |

## 2. Code

| # | Item | Evidence | Status |
|---|---|---|---|
| C1 | `13/src/model_serving/report.py` edits are string-only (`REPORT_TITLE` at :26, section heading at :248, results.md heading at :310). `py_compile`, `ruff check` and `ruff format --check` all exit 0. | diff vs `ebb889cf` | verified |
| C2 | `13/reports/report.html:4,28,29` and `results.md:1,7` match the new generator strings exactly. The report was not re-run, so the agreement is by inspection only. | diff | verified (by inspection) |
| C3 | **Residual label:** `report.py:147` still builds the protocol string "Champion re-derivation: …". It surfaces in `13/reports/results.md:5` and `13/reports/evaluation_metadata.json:2`. Internal keys (`metrics.json:33` `"champion"`, `config.champion_expected_test_mae`, `cli.py:18,31` help text) are developer-facing and acceptable. | grep | verified — **note N1** |
| C4 | `staticRegistry.ts:260` regenerated line ("Served MLP …") matches `13/portfolio.yaml:13`. `gen_static_registry.py --check` exits 0. | gate | verified |
| C5 | `02/src/demand_forecasting/m5_full_figures.py` (in `ebb889cf`): `origin = cat_meta["origin"]` resolves to `2016-05-22` in `reports_m5_full/catalog_meta.json`. Ruff and format are clean. The takeaway strings hard-code "0.6161 (weights 0.60/0.10/0.30)" and "under 0.001", so they are not read from the payload or metrics. Drift risk only. | diff `main...HEAD` | verified — **note N5** |
| C6 | `ForecastWorkbench.tsx` (in `ebb889cf`) labels the hero, KPI tiles and evidence block "earlier blend" and puts "current champion 0.6211" beside them (`:31-35`). Its fallback manifest matches `staticRegistry.ts:676-681`. Tests were changed in the same commit and were not re-run here; the recorded npm test exit is 0 (`20261126-wave8-commit-handoff/00-commit-handoff.md`). | diff | verified (tests: recorded only) |
| C7 | Leftover debugging: no `console.log`, `debugger`, `breakpoint()`, `print(` or `.only(` added under `apps/showcase-web/src`, `projects/*/src` or `projects/*/tests` on the branch. One added `FIXME` at `12/src/tabular_ml_lifecycle/features.py:175` is a deliberate compatibility note: it keeps the committed behaviour and matches the docstring at `:152-153`. It is not leftover debugging. | `git diff main...HEAD` grep | verified |

## 3. Contents (articles 02–13)

| # | Check | Result | Status |
|---|---|---|---|
| T1 | "champion" in 13 reader copy | None left in `13/story.yaml`, `13/README.md`, `13/portfolio.yaml`, `docs/projects/13-model-serving.md`, or the `report.html` title and headings. Only `results.md:5` remains (N1). | verified |
| T2 | "champion" elsewhere | 02 uses it for the validation-selected 0.6211 blend, and 03 for the synthetic OCSVM / budgeted ensemble. Both are correct uses. 06:209 is generic. **12 is mixed:** `12/README.md:93-98` and `12/story.yaml:369-371` say "without a champion label", but `docs/projects/12-tabular-ml-lifecycle.md:24,61,63`, `12/reports/report.html:29` (body "Champion: tabular MLP") and the `bootstrap_ci` figure axis "MAE(champion)" still use it. These labels already exist on `main` (3 hits there), so this push does not introduce them. Now that 13 is clean, they are more visible. | verified — **note N2** |
| T3 | "; next," run-ons in 02–13 story/README/docs/portfolio/storyShort/registry | 0 hits. The `03/story.yaml:115` splice is fixed in the working tree. | verified |
| T4 | "real incidents" | `03/story.yaml:24,59,88,139`. Each refers to labelled NAB incident windows, against synthetic spikes. Acceptable; optionally change to "labelled incidents". | verified (style only) |
| T5 | "0.6161" | Every occurrence is labelled as the earlier blend: `02/story.yaml:173,241`, `02/README.md:108`, `ForecastWorkbench.tsx:33`, `staticRegistry.ts:680` (label "earlier blend · official WRMSSE"). None presents it as the committed champion. | verified |
| T6 | Audit / review-process voice | `docs/projects/08-inference-serving.md:21` "both external audits' #1 recommendation" and `docs/projects/09-agentic-workflows.md:238` "after the audit-P1 split". Both already exist on `main`. No "round-N", "reviewer finding" or "Opus/Kimi review" language appears in 02–13 article copy. `kimi-for-coding` in 04/09 names a model, not a review process. | verified — **note N3** |
| T7 | New 02 disclosure sentence | `02/README.md:108` and `02/story.yaml:241` add the same 50-word sentence giving the reason (2 vs 9 selection origins). The facts are verified (see R-02). The caption is now 102 words. "both were scored once on the same test origin" is true per run, but two runs (plus the challenger gate, disclosed at `02/story.yaml:223`) have read that window. "each run scored it once" would be more exact. | verified — **note N4** |

## 4. Results spot-check (committed files)

All of the following were verified by direct value match (rounding as printed).

| Project | Claim (article) | Committed evidence |
|---|---|---|
| 02 | 0.6211 vs floor 0.8929, −30.4% | `reports_m5_full/metrics.json:608` (0.62105), `:454` (0.89290); (0.62105−0.89290)/0.89290 = −30.45% |
| 02 | weights 0.95/0.00/0.05, 9 selection origins | `metrics.json:155-158`; `evaluation_metadata.json:36` `n_selection: 9` |
| 02 | bias +0.0222, WAPE 0.7623, zero-day 57.2% vs 66.6% | `metrics.json:625,624,626`; floor `:472` |
| 02 | best single 0.6219 | `metrics.json:520` (0.62192) |
| 02 demo | 0.6161, 0.60/0.10/0.30, −31.0%, 2 selection origins, origin 2016-05-22 | `demo_payload.json:10` (0.61608), `:259` weights, `convex_ensemble_vs_naive.rel` −0.3100, `:20244-20245` `n_origins 3` / `n_selection 2`, `origins[0].origin` 2016-05-22 |
| 02 | 0.6211 consistent across surfaces | `story.yaml` ×12, `README.md` ×6, `demo.yaml`, `docs/projects/02` ×2, `cardCopy.ts`, `storyShort.ts`, `staticRegistry.ts`, `m5Pipeline.ts`, `ForecastWorkbench.tsx` ×3. No other rounding of 0.62105 appears. |
| 03 | 1,609 raw alerts; range-PR 0.804 | `reports/nab_metrics.json:748,750` |
| 03 | 66 → 35 pages, recall 0.604, range-F1 0.533 | `reports/nab_sweep.json` `grid.ensemble+rolling…budgeted` (`:1095` range_f1), `grid.isolation_forest+rolling…budgeted.alerts_fired` 66 |
| 03 | selection PR-AUC 0.1514; test AP 0.136 | `reports/champion_selection.json:31`; `reports/metrics.json` `ocsvm_tuned.pr_auc` |
| 04 | macro-F1 0.953 → 0.954; $0.023671 | `reports/llm_cascade.json:18,19,43` |
| 05 | $601 vs $1,035; CI −$508…−$353; threshold 0.175 | `reports/metrics.json:46,29`; `reports/demo_payload.json:22`, `:10` |
| 06 | 4.2% gap, +3.7 vehicles, ~1 s | `reports/metrics.json:3934,3937,3936` (4.2322, 3.73, 1.15 s) |
| 07 | 4.68 vs 6.52 MAE, −28.3% | `reports/metrics.json:88,100,43` |
| 07 | 90.8% p90 coverage | `reports/report.html` ("90.8% of realised zone-hours") and `reports/figures/p90_calibration.json`. It is **not** in `metrics.json`: `conformal.before.coverage_overall` 0.9069 there is the second-half subset. Consistent, but only the report/figure carry the number. |
| 08 | p95 0.81 s, p50 0.63 s, 760 requests, 0 failures | `reports/metrics.json:22,21`; 19 cells × 40 = 760, Σ`n_failures` = 0 |
| 09 | 15/15 suite, 19 held-out tasks, 13 answers | `reports/metrics.json:136,1070,1071` |
| 10 | +$2,812 (+70%), CI [+$718, +$4,767] | `reports/metrics.json:318`, `:294` (2812/4026 = 69.9%); CI in `reports/report.html:36` only |
| 11 | Polars 19×, DuckDB 15×, sqlite ~29× slower, 1,658 trips | `reports/metrics.json:737,729,741` (0.035 → 28.6×), `:2245` |
| 12 | 25.4 vs 83.2 MAE; tie −0.18 | `reports/metrics.json:17,32,42` |
| 12 | +57.8, CI 52.5–63.1, week 38.8–73.4 | `reports/results.md:17` (not stored as metrics.json fields) |
| 13 | 25.4316 reproduced; parity 7.15e-07; 6.5 GB; $0.000012/1k; p50 1.6 ms; knee ~950 (932.5/969.9); ~56k rows/s | `reports/metrics.json:38,210,187` (6466 MB), `:162`; `report.html:31-32` tables |

`check_headline_numbers.py` independently checks 13 claims with 0 findings.

## 5. Article structure

| Check | Result | Status |
|---|---|---|
| All eight sections (background → conclusions) | Present in 02–13 | verified |
| "In plain terms" card in every section | Present in all 96 sections. It is the last line of every conclusions section. | verified |
| Baseline named | 02 seasonal naive, 03 random/no-skill band, 04 baseline transformer, 05 contact-everyone, 06 best-known/NN, 07 persistence, 08 dense 32B, 09 legacy suite, 10 random targeting, 11 pandas, 12 seasonal naive, 13 native vs ONNX + exp-12 MAE | verified |
| Limits | `## Limits` in every conclusions section; top-level `limits:` in 12 and 13 | verified |
| Negative results | Per `20261126-wave8-final-report/00-report.md:36`; re-grepped (rejected / spans zero / tie / no measurable) in each story | verified |
| Conclusions order | Only 03 and 12 follow 01's order (Taught → Limits → Exact → Protocol). 02, 04–11 and 13 use Results summary → Taught/Shows → Exact → Protocol → Limits. The order is consistent *within* that group of ten. But the `ebb889cf` commit message says "conclusion order aligned to project 01", which is true for 2 of 12. | verified — **note N6** |

## 6. Gates (this HEAD + working-tree edits)

| Command | Exit | Output |
|---|---|---|
| `uv run python scripts/lint_story_language.py` | 0 | 14 stories, 0 errors, 0 warnings |
| `uv run python scripts/check_short_copy.py --check` | 0 | 42 surfaces single-sourced |
| `uv run python scripts/gen_static_registry.py --check` | 0 | current |
| `uv run python scripts/gen_story_short.py --check` | 0 | current |
| `uv run python scripts/check_headline_numbers.py` | 0 | 13 claims, 0 findings |
| `uv run python scripts/check_docs.py` | 0 | OK |
| `git diff --check` (working tree) | 0 | clean |
| `git diff --check main...HEAD` (extra) | 2 | trailing spaces at `collaboration/reviews/20261124-wave66-articles-and-roadmaps/opus-round3/closeout-kimi.md:3-5`. These are Markdown hard breaks in an internal review file. Cosmetic. |
| `uv run mkdocs build --strict` | 0 | built in 0.40 s; `git status` unchanged afterwards |
| ruff check / format / py_compile on changed Python | 0 / 0 / 0 | — |

The full pytest and npm suites were not re-run (instruction). The recorded results are exit 0 at `ebb889cf`. The working-tree edits touch only one `.py` file, and only string literals in it. No test asserts the changed 13 strings: `grep` found no test reference to "champion MLP" or "Champion re-derivation".

---

## Notes (non-blocking, for the next small pass)

- **N1** — `13/src/model_serving/report.py:147` still says "Champion re-derivation:". It reaches `13/reports/results.md:5` and `13/reports/evaluation_metadata.json:2`. Change it to "Served-model re-derivation:" and regenerate the report offline. *verified*
- **N2** — Project 12 still uses the champion label in `docs/projects/12-tabular-ml-lifecycle.md:24,61,63`, `12/reports/report.html:29` (body "Champion: …") and the `bootstrap_ci` axis title (`12/reports/figures/bootstrap_ci.json`). This contradicts `12/README.md:93-98`. It already exists on `main`. *verified*
- **N3** — Review-process voice in published docs: `docs/projects/08-inference-serving.md:21` and `docs/projects/09-agentic-workflows.md:238`. Both already exist on `main`. *verified*
- **N4** — `02/story.yaml:241` caption is 102 words and repeats `02/README.md:108`. Tighten it, and say "each run scored it once". *verified*
- **N5** — `02/src/demand_forecasting/m5_full_figures.py` hard-codes 0.6161 / 0.60/0.10/0.30 / "under 0.001" in the takeaway strings. Read them from `demo_payload.json` / `metrics.json` instead. *verified*
- **N6** — The `ebb889cf` message overstates the conclusions alignment (2 of 12). Correct this in the push or PR description; do not amend. *verified*

## HOLD blockers

None.
