# Implementation handoff: next two experiments (14 LLM fine-tuning, 15 RL dynamic pricing)

Date: 2026-11-24
Designer: Claude Code
Executor: Kimi Code
Status: draft (owner approval requested). Kimi does not start until the
owner sets this to `approved` and answers the decisions marked **blocking**.
Source design: `collaboration/designs/20261124-next-experiments/01-design-brief.md`,
`02-architecture-proposal.md`

## Objective

Build two new reproducible experiments and their articles:

- **E2 / `projects/15-dynamic-pricing-rl/`**: a Gymnasium pricing
  environment calibrated on the committed M5 subset, a MaskablePPO policy
  with a custom history encoder, baselines B0-B3, a fluid upper bound, and
  a single sealed evaluation on 1,000 held-out episodes against
  pre-registered thresholds.
- **E1 / `projects/14-llm-finetuning/`**: LoRA fine-tunes of Qwen3.5-4B and
  Gemma-4-E4B (mlx-lm) for grounded-claim verification, scored against the
  same checkpoints zero-shot and few-shot, a classical baseline, and
  MiniCheck-Flan-T5-Large, on a sealed LLM-AggreFact sample (G1) and an
  owner-labelled portfolio set (G2), against pre-registered thresholds.

Every model call is local. No hosted LLM, no paid API, no cloud GPU unless
the owner approves O1. Run E2 first; E1 can start once its blocking
decisions are answered.

## Scope

### In scope

- New module `libs/portfolio-eval/src/portfolio_eval/intervals.py` + tests.
- New projects 14 and 15 (code, tests, params, dvc.yaml, reports, figures,
  README, DESIGN.md, story.yaml, portfolio.yaml).
- Registrations each new project needs (listed in step S-R).
- Two new data-registry cards for E1's datasets; a "Used by" line on the M5
  card.

### Out of scope

- Any edit to projects 01-13 source, data, reports, or copy. 01 and 02 data
  are read by path only.
- Fixing the orchestrator review's 01/02 copy blockers (separate wave).
- Demos, Hugging Face Hub uploads, cloud runs.
- Splitting existing files over 1,000 lines.
- Refactoring existing per-project bootstrap/Wilson code onto the new helper.

## Affected surfaces

- `libs/portfolio-eval/src/portfolio_eval/intervals.py` (new),
  `libs/portfolio-eval/tests/test_intervals.py` (new)
- `projects/14-llm-finetuning/**` (new), `projects/15-dynamic-pricing-rl/**` (new)
- root `pyproject.toml`: `[tool.importlinter]` `root_packages` and the
  independence contract `modules` (add `llm_finetuning`, `dynamic_pricing`);
  the shared-libs forbidden list (add both); `[[tool.mypy.overrides]]`
  (`strict = true` for `llm_finetuning.*` and `dynamic_pricing.*`)
- `.github/workflows/ci.yml` and `nightly.yml` project matrices (add two rows
  next to `13-model-serving`, `cov: "--cov=src"`)
- `apps/showcase-web/src/lib/cardCopy.ts` (`CARD_DOES`, `CARD_ACHIEVES`,
  `CARD_TAGS` entries for both)
- `apps/showcase-web/src/pages/About.tsx:15,178` ("13 reproducible
  experiments", "thirteen case studies")
- `scripts/check_headline_numbers.py` (+ its test) and
  `scripts/export_readme_figures.py` (entries for 14 and 15)
- `README.md` project table rows; `docs/projects/14-llm-finetuning.md`,
  `docs/projects/15-dynamic-pricing-rl.md`, `docs/projects/index.md`
- `docs/data-registry/minicheck-c2d-d2c.md`, `docs/data-registry/llm-aggrefact.md`
  (new), `docs/data-registry/index.md`, `registry/README.md`,
  `docs/data-registry/m5-nixtla-mirror.md` ("Used by" line),
  `registry/minicheck-c2d-d2c.dvc` (via `dvc import-url --no-exec` if the HF
  file URL works without auth; otherwise card only and say so)
- Generated, by script only: `apps/showcase-web/src/lib/staticRegistry.ts`,
  `storyShort.ts`, route manifest, sitemap
- `uv.lock` (via `uv sync`)

## Shared conventions for both projects

- **Pins.** `gymnasium==1.4.0`, `stable-baselines3==2.9.2`,
  `sb3-contrib==2.9.2`, `mlx-lm==0.32.2` (Darwin-only extra). If any pin
  fails to resolve, stop and write `OPEN_QUESTIONS.md`. Do not add `peft`,
  `trl`, or `mlx-vlm` unless the E1-2 fallback triggers; then query PyPI JSON
  and pin the newest release that is at least 14 days old on that date.
- **CI safety.** MLX is an optional extra:
  `[project.optional-dependencies] mlx = ["mlx-lm==0.32.2; sys_platform == 'darwin'"]`.
  Import mlx lazily inside the functions that need it (house pattern). No
  test imports mlx; CI tests run on Linux with no model downloads.
- **Ledger.** `reports/experiment_log.json`, append-only list. Row fields:
  `ts` (UTC ISO), `step`, `change`, `split`, `config_sha256` (sha of the
  resolved params used), `set_sha256` (sha of the split id file), `n`,
  headline numbers for that step, `wall_clock_s`, `request_hosts` (list;
  must be `[]` except in approved download steps, where only
  `huggingface.co` / `cdn-lfs*.huggingface.co` may appear), `report_path`
  (repo-relative), `decision`. Write via one small `ledger.py` per project
  (projects may not import each other).
- **Sealed access log.** `reports/sealed_access.json`: every open of a
  sealed set appends `{ts, step, path (repo-relative), sha256, purpose}`.
  Purposes: `prepare` (E1 only: length and n-gram filtering, no labels
  inspected beyond class counts), `seal_read` (exactly one per sealed set).
  A second `seal_read` voids the run.
- **Pre-registration.** A `preregistration:` block in `params.yaml` holding
  the hypotheses, thresholds, comparators, seeds and metric definitions
  exactly as in `02-architecture-proposal.md`. Its sha256 is logged in the
  ledger, and the **owner commits it before the seal read** (owner gate).
  Nothing in that block changes afterwards.
- **Metrics.** `reports/metrics.json` in git, stamped with
  `uv run python scripts/stamp_metrics_meta.py` after each write. Large
  outputs (adapters, PPO checkpoints, raw dataset copies) are DVC outs.
  Committed files must not contain absolute home paths
  (`git grep -c "/Users/" -- projects/14-llm-finetuning projects/15-dynamic-pricing-rl`
  must print nothing).
- **Intervals.** Use `portfolio_eval.intervals`; 2,000 resamples, seed 42,
  wording from `docs/engineering/statistical-intervals.md`.
- **Copy.** `portfolio.yaml` and `story.yaml` are written in the article
  step only. Until then keep them out of the tree (the scaffolder creates
  them; move them to `projects/NN-*/.draft/` and add `.draft/` to the
  project `.gitignore`, or delete and recreate in the article step). A
  `planned` card is not hidden on the site.
- **Git.** Kimi never commits, pushes or merges. At each owner gate Kimi
  lists the files that are ready to commit. Commit messages are imperative
  with a body and carry no `Co-Authored-By` model trailer.

## Ordered implementation steps

Each step names inputs, outputs and a gate. Do not start a step until the
previous gate is green. Record every gate result in
`collaboration/designs/20261124-next-experiments/04-execution-notes.md`.

### S-0. Shared interval helper

- Inputs: `docs/engineering/statistical-intervals.md`;
  `projects/09-agentic-workflows/src/agentic_workflows/report.py:51`
  (`wilson_interval`, reference); `projects/01-rag-agent/src/rag_agent/reporting.py:173`.
- Do: add `portfolio_eval/intervals.py` with `wilson_interval(k, n, z)`,
  `paired_bootstrap(a, b, stat, n_resamples=2000, seed=42)` and
  `cluster_bootstrap(a, b, clusters, stat, n_resamples=2000, seed=42, strata=None)`
  returning `(point, lo, hi)`. numpy only. Strict-mypy clean.
- Outputs: module + `libs/portfolio-eval/tests/test_intervals.py`
  (k = n boundary gives upper 1.0; same seed gives same interval; identical
  inputs give a zero-width delta interval; cluster resampling keeps clusters
  intact; strata are preserved).
- Gate: `uv run ruff check libs && uv run mypy libs && uv run pytest libs/portfolio-eval -q`.

### E2. `projects/15-dynamic-pricing-rl/`

**E2-1. Scaffold.**
- Do: `uv run python scripts/new_project.py 15-dynamic-pricing-rl "Dynamic Pricing with RL"`.
  Move `portfolio.yaml`/`story.yaml` aside (conventions above). Dependencies:
  `gymnasium==1.4.0`, `stable-baselines3==2.9.2`, `sb3-contrib==2.9.2`,
  `scipy`, `numpy`, `polars`, `pyarrow`, `typer`, `plotly`, `portfolio-core`,
  `portfolio-eval`. Add `dynamic_pricing` to the import-linter lists.
  `uv sync --all-packages --dev`.
- Outputs: package skeleton, `params.yaml`, `dvc.yaml` stages
  `calibrate → baselines → train → evaluate_val → seal_read → figures`.
- Gate: `uv run ruff check . && uv run mypy libs projects apps && uv run lint-imports`
  (import-linter) all green; `uv run pytest projects/15-dynamic-pricing-rl -q` runs.

**E2-2. Calibrate from M5 (read-only).**
- Inputs: `projects/02-demand-forecasting/data_m5/subset_{Y,X,S}.parquet`.
- Do: `calibrate.py`. Pin the three files' sha256 in `params.yaml` (compute
  once and record; loader refuses drift). Window 2011-01-29 to 2016-04-24
  only. Per series: `base` = mean daily units over the last 52 weeks of the
  window; `dow` = 7 weekday shares (sum 7); `k` = NB dispersion by method of
  moments on daily residuals (floor 0.5, cap 100); `p_ref` = modal
  `sell_price` over the last 52 weeks. Split by `item_id` with seed 42:
  140 / 30 / 30 items.
- Outputs: `data/calibration.json` (600 rows, git), `data/splits.json`
  (series ids per split + sha256, git), ledger row.
- Gate: tests prove (a) no `item_id` in two splits, (b) no date
  ≥ 2016-04-25 used, (c) sha mismatch raises, (d) `dow` sums to 7.
  Kimi prints the distribution of `base`, `k`, `p_ref` in the notes.

**E2-3. Environment.**
- Do: `env.py` with `PricingEnv(gymnasium.Env)` exactly as specified in
  `02-architecture-proposal.md` (T = 91, 7-step ladder, NB demand by inverse
  CDF from a per-episode uniform stream, ρ ∈ {0.7, 1.0, 1.3}, reward and
  salvage definitions, observation layout, `action_masks()` for C1-C3,
  `strict` flag, `info["violations"]`). `EpisodeSpec(series_id, epsilon, rho,
  seed)` is the only way to make an episode; `reset(options={"spec": ...})`.
  Elasticity prior from `params.yaml` (O8).
- Outputs: env module; `tests/test_env.py`.
- Gate: tests prove (a) same spec → identical trajectory, (b) two different
  policies on the same spec see the same uniforms (CRN), (c) masks forbid a
  two-step jump and any change within 7 days, (d) strict mode raises on an
  invalid action and default mode holds price and counts it, (e) sales never
  exceed inventory, (f) C4 holds across the band, (g)
  `gymnasium.utils.env_checker.check_env` passes in default mode.
  Benchmark `DummyVecEnv(8)` vs `SubprocVecEnv(8)` over 10k steps, record
  both steps/s in the ledger, and select the faster wrapper for E2-7.

**E2-4. Upper bound and baselines.**
- Do: `bound.py` (fluid LP with known ε via `scipy.optimize.linprog`;
  variables = share of each day at each price; demand ≤ I0; returns expected
  normalised profit). `baselines.py`: B0, B1, B2, B3 per the proposal. B3 uses
  a conjugate normal update on ε with the training prior, samples once per
  day, solves the same LP for the remaining horizon and inventory, and plays
  the best action allowed by the mask.
- Outputs: modules + tests.
- Gate: tests prove (a) on a zero-noise instance, the bound ≥ the profit of
  every baseline, (b) B3's posterior mean moves toward the true ε over an
  episode with a fixed seed, (c) every baseline returns only masked-valid
  actions (0 violations over 50 random specs).

**E2-5. Tune baselines on train, choose the best non-RL baseline on val.**
- Do: B1 grid over the 7 multipliers on 2,000 train episodes; B2 grid
  x, y ∈ {5, 10, 15, 20}% on 2,000 train episodes. Then evaluate B0-B3 on the
  300 val episodes.
- Outputs: `reports/baselines_val.json` (git), ledger rows; the name of the
  best non-RL baseline on val is written to `params.yaml: comparator`.
- Gate: numbers recorded; the comparator is fixed before E2-6.

**E2-6. Pre-registration (owner gate).**
- Do: write the `preregistration:` block (P1, P2, P3, thresholds, comparator
  from E2-5, test spec seeds, metric definitions, resamples, seed). Generate
  the 1,000 test specs and 2 × 500 stress specs into `data/splits.json`
  (seed streams 2, 3, 4); never run a policy on them. Log the block's sha256.
- Gate: **owner reviews and commits** `params.yaml`, `data/splits.json`,
  code and tests so far. Kimi waits.

**E2-7. Train PPO.**
- Do: `train.py`. `MaskablePPO` with `policy_kwargs = {features_extractor_class:
  HistoryEncoder, features_extractor_kwargs: {history_len: 14}, net_arch:
  {pi: [64, 64], vf: [64, 64]}}`, where `HistoryEncoder(BaseFeaturesExtractor)`
  runs a 1-D conv (2 layers, 16 channels, kernel 3) over the 14 × 2 history
  and an MLP over the scalars, then concatenates. 8 vectorised envs on train
  specs, 3,000,000 steps, seeds 0, 1, 2; PPO defaults otherwise (record all
  hyperparameters). Evaluate each seed on the 300 val episodes with
  `sb3_contrib.common.maskable.evaluation.evaluate_policy`-equivalent code
  that **passes `action_masks`**. Choose the seed with the best val mean.
- Outputs: checkpoints under `reports/models/` (DVC), `reports/train_curves.json`
  (git, downsampled), `reports/ppo_val.json` (git), ledger rows.
- Gate: val results for all 3 seeds recorded; violations 0 on val; if the
  measured wall-clock projects past 24 h, reduce to 2,000,000 steps and
  record why before training.

**E2-8. Sealed read (once).**
- Do: `evaluate.py seal-read`: run B0-B3, the chosen PPO, and the bound on
  the 1,000 test specs, then the stress specs, in one invocation. Write
  per-episode normalised profit and violations to `reports/test_episodes.json`
  (git if ≤ ~2 MB, else DVC), and to `reports/metrics.json`: per policy mean
  normalised profit, mean raw gross profit (ex-salvage), % of bound (overall
  and per ρ), violations; P1 difference with
  paired bootstrap CI (episodes as rows); relative lift; P1/P2 verdicts;
  stress results (no gate). Append `seal_read` to `sealed_access.json`.
  Stamp `_meta`.
- Gate: exactly one `seal_read` per sealed set in `sealed_access.json`;
  verdicts computed by code from the pre-registered block (no manual
  edits); `git grep -c "/Users/" -- projects/15-dynamic-pricing-rl` empty.

**E2-9. Figures and article.**
- Do: `figures.py` → `reports/figures/*.json` (≤ 3 per section):
  `profit_vs_baselines` (means + CIs), `price_traces` (3 test episodes chosen
  by fixed seed, not by outcome), `bound_share_by_rho`, plus EDA
  `calibration_overview`. Then README (What it is / Why / Quickstart /
  Results / Limits / Reproduce / Common errors), DESIGN.md (alternatives and
  changelog), `story.yaml` (eight sections; `short_version` ≤ 280 chars;
  5-card `roadmap` on the `Data -> Training -> Evaluation -> Production -> Next`
  lifecycle arc, 4 `shipped` + 1 `next`, verb-first title 3–6 words, detail
  ≤ 90 chars; `data` links the M5 data card; Limits state: simulator results
  only, elasticity is an assumption from Bijmolt et al. 2005, no reference-price
  or substitution effects), `portfolio.yaml` (topic per O5). Then step S-R.
- Gate: the full gate list below; every number in copy appears in
  `reports/metrics.json` or another committed report.

### E1. `projects/14-llm-finetuning/`

**E1-0. Owner prerequisites (owner, not Kimi).**
- O2: accept the LLM-AggreFact terms on Hugging Face personally and log in
  locally (`huggingface-cli login`); Kimi never accepts terms.
- O9: approve the downloads listed under "Downloads".
- O3: start G2 labelling (E1-3 produces the sheet).

**E1-1. Scaffold.**
- Do: `uv run python scripts/new_project.py 14-llm-finetuning "LLM Fine-tuning Lift"`;
  move `portfolio.yaml`/`story.yaml` aside. Dependencies: `datasets`,
  `transformers` (already in the workspace), `scikit-learn`, `numpy`,
  `typer`, `plotly`, `portfolio-core`, `portfolio-eval`; optional
  `[mlx]` extra as above. MiniCheck scoring uses `transformers` +
  `torch` directly with the cached `lytang/MiniCheck-Flan-T5-Large`
  (no `minicheck` package). Add `llm_finetuning` to import-linter lists.
- Gate: as E2-1.

**E1-2. Smoke gate (approved download step).**
- Do: download `Qwen/Qwen3.5-4B` and `google/gemma-4-E4B-it` (confirm each
  model card says Apache-2.0 and record the revision sha), and
  `lytang/C2D-and-D2C-MiniCheck`. For each family: load with `mlx_lm`,
  verify " Yes"/" No" are single tokens (else "1"/"0"; record ids), run 10
  LoRA steps on 64 train rows, score 20 train rows with the logprob scorer,
  measure train tokens/s and prefill tokens/s and peak memory.
- Outputs: `reports/smoke.json` (git), ledger rows with `request_hosts`.
- Gate: per family, (a) loads and trains in mlx-lm, or (`gemma-4-E4B-it`
  only) in `mlx-vlm` (`mlx_vlm.lora`), or the PEFT-on-MPS fallback works, or
  the family is dropped and recorded; (b) projected total
  E1 wall-clock ≤ 24 h, else apply the reductions in the proposal's failure
  table and record them before E1-6.

**E1-3. Data preparation.**
- Do: `data.py`.
  - C2D/D2C: group split by `sha256(doc)`, 90/10, seed 42 →
    `data/train.jsonl`, `data/dev.jsonl` (DVC) + ids/hashes in
    `data/splits.json` (git).
  - G1: load AggreFact **test** (log `prepare` in `sealed_access.json`).
    Drop rows whose doc exceeds 1,800 Qwen tokens; drop rows sharing any
    13-gram with any train doc; stratified sample 200 per source dataset
    (all if fewer), seed 42. Write only `{row_index, dataset, doc_sha256,
    label}` to `data/g1_ids.json` (git). Never write AggreFact text to git.
    Record counts dropped by each filter and the class balance per source.
    Do not run any model on G1.
  - G2: from `projects/01-rag-agent/data/judge_v2_claims.json` (sha256
    pinned) write `data/g2_label_sheet.csv` with `item_id, claim, chunk_text,
    owner_label` (empty), shuffled by seed 42, **no `kind` column**. The
    owner fills `owner_label` ∈ {supported, unsupported, unsure}. Kimi then
    writes `data/g2_owner_labels.json` with `labelled_by: "owner"`, the
    sheet's sha256, and the date. `unsure` items are excluded and counted.
    Kimi reports agreement between owner labels and `kind` (construction
    labels) as a data-quality note, and agreement on the 30 items of
    `reports/judge_calibration_v2/owner_sample.json` as a by-product (O3).
- Gate: tests prove group-split disjointness, the 13-gram filter on a toy
  pair, that `g1_ids.json` holds no text field, and that the G2 sheet has no
  label-revealing column.

**E1-4. Dev arms and comparator choice.**
- Do: `classical.py` (features in the proposal; `LogisticRegression`,
  `C` chosen by 5-fold CV on train); `score.py` (logprob scorer; batch by
  length; temperature irrelevant, single forward pass); few-shot exemplar
  selection (4 balanced train rows, seed 42, docs ≤ 300 tokens). Score
  classical, MiniCheck, and zero-shot and few-shot for each family on
  **dev**. Write `params.yaml: comparator.{qwen,gemma}` = the better of
  zero-shot / few-shot on dev BAcc.
- Outputs: `reports/dev_metrics.json` (git), ledger rows.
- Gate: comparators fixed; dev numbers recorded.

**E1-5. Pre-registration (owner gate).**
- Do: write the `preregistration:` block (H1, H2, H3, thresholds, comparators
  from E1-4, fixed threshold 0.5, metrics, bootstrap settings, G1/G2 id-file
  sha256s). Log its sha256.
- Gate: **owner reviews and commits**. Kimi waits.

**E1-6. LoRA training.**
- Do: `train.py` calling `mlx_lm` LoRA (prompt-masked chat JSONL; rank 16;
  attention + MLP projections; lr 1e-4; batch 8 via accumulation if needed;
  max seq 2,048; ≤ 2 epochs; eval on dev every ~500 steps; keep the
  best-dev-BAcc adapter). Same for the second family. Record all
  hyperparameters, loss curves, wall-clock, peak memory.
- Outputs: adapters in `reports/models/` (DVC), `reports/train_curves.json`
  (git), ledger rows.
- Gate: dev BAcc of the chosen adapter recorded; no G1/G2 access in
  `sealed_access.json` since E1-3.

**E1-7. Sealed read (once).**
- Precondition: `data/g2_owner_labels.json` exists with
  `labelled_by: "owner"`. If not, stop; do not substitute model or agent
  labels.
- Do: `evaluate.py seal-read` scores all arms (classical, MiniCheck,
  {qwen, gemma} × {zero-shot, few-shot, lora}) on G1 and G2 in one
  invocation. Write per-row probabilities to `reports/scores_g1.json` and
  `reports/scores_g2.json` (ids + probabilities only), and to
  `reports/metrics.json`: per arm BAcc, F1-unsupported, AUROC, Brier score
  and 10-bin ECE, per-source BAcc (G1), sensitivity/specificity with Wilson
  CIs (G2); H1 and H2 deltas
  with cluster/paired bootstrap CIs; H3 deltas; verdicts computed from the
  pre-registered block; dev-tuned-threshold results as secondary. Append
  `seal_read`. Stamp `_meta`.
- Gate: one `seal_read` per sealed set; verdicts by code; no AggreFact text
  in git (`git grep -n "\"doc\"" -- projects/14-llm-finetuning/reports` is
  empty); no absolute paths.

**E1-8. Figures and article.**
- Do: figures (`lift_by_arm` with CIs, `per_source_bacc` heatmap,
  `g2_sens_spec`, EDA `dataset_composition`); README, DESIGN.md, story.yaml
  (eight sections; `short_version` ≤ 280 chars; 5-card `roadmap` on the
  `Data -> Training -> Evaluation -> Production -> Next` lifecycle arc, 4
  `shipped` + 1 `next`, verb-first title 3–6 words, detail ≤ 90 chars;
  Limits state: G1 is a length-capped stratified sample, not the
  leaderboard protocol; G2 negatives are constructed mutations; possible
  pre-training exposure; base = instruct checkpoint), portfolio.yaml (topic
  per O5). Data cards for C2D/D2C (MIT) and LLM-AggreFact (CC BY-ND 4.0,
  gated, eval-only; we commit ids only). Then step S-R.
- Gate: full gate list; no wording says "owner-validated" about anything
  but G2, and only after G2 exists.

### S-R. Registrations (once per project, in its article step)

1. Restore `portfolio.yaml` and `story.yaml` into the project.
2. `cardCopy.ts`: `CARD_DOES`, `CARD_ACHIEVES`, `CARD_TAGS` entries.
3. `About.tsx:15,178`: update the experiment count words to the new total.
4. `README.md` project table row; `docs/projects/NN-*.md`; link it from
   `docs/projects/index.md`.
5. CI matrices in `ci.yml` and `nightly.yml`.
6. `scripts/check_headline_numbers.py`: one extractor (E2: P1 relative
   lift and the RL mean; E1: H1 delta per family) + a test row.
7. `scripts/export_readme_figures.py`: hero and docs figures for the project.
8. Regenerate: `uv run python scripts/gen_static_registry.py`,
   `uv run python scripts/gen_story_short.py`,
   `uv run python scripts/gen_route_manifest.py`, then
   `uv run python scripts/export_readme_figures.py` for the new figures.
9. Restart the API locally to confirm the new project is enumerated.

## Commands and gates

Run the narrowest first, then the broad set.

```bash
# environment
uv sync --all-packages --dev
uv sync --all-packages --dev --extra mlx      # macOS only, E1 training/scoring

# narrow (per step)
uv run ruff check projects/15-dynamic-pricing-rl libs/portfolio-eval
uv run mypy libs projects/15-dynamic-pricing-rl
(cd projects/15-dynamic-pricing-rl && uv run pytest --cov=src -q)
(cd projects/14-llm-finetuning && uv run pytest --cov=src -q)
uv run lint-imports

# pipelines (from each project directory)
(cd projects/15-dynamic-pricing-rl && uv run dvc repro)
(cd projects/14-llm-finetuning && uv run dvc repro)

# broad (article step)
uv run ruff check . && uv run ruff format --check . && uv run mypy libs projects apps
HF_HUB_OFFLINE=1 uv run pytest -q
uv run python scripts/stamp_metrics_meta.py --help   # then stamp each new metrics.json
uv run python scripts/lint_story_language.py
uv run python scripts/check_docs.py
uv run python scripts/check_short_copy.py --check
uv run python scripts/check_demo_contract.py
uv run python scripts/check_headline_numbers.py
uv run python scripts/gen_static_registry.py --check
uv run python scripts/gen_story_short.py --check
uv run python scripts/gen_route_manifest.py --check
uv run mkdocs build --strict
(cd apps/showcase-web && npm test && npm run lint && npm run build)

# targeted
git grep -c "/Users/" -- projects/14-llm-finetuning projects/15-dynamic-pricing-rl   # expect no output
python3 -c "import json;a=json.load(open('projects/15-dynamic-pricing-rl/reports/sealed_access.json'));print([e['purpose'] for e in a])"
python3 -c "import json;a=json.load(open('projects/14-llm-finetuning/reports/sealed_access.json'));print([e['purpose'] for e in a])"
```

If `lint-imports` is not the import-linter entry point in this workspace,
use whatever `scripts/lint_ci.py` runs and say so in the notes.

## Generated artifacts

Regenerate through scripts or pipelines only:

- `reports/metrics.json`, `reports/figures/*.json` per project (`dvc repro`),
  then `_meta` via `scripts/stamp_metrics_meta.py`
- `apps/showcase-web/src/lib/staticRegistry.ts` (`gen_static_registry.py`)
- `apps/showcase-web/src/lib/storyShort.ts` (`gen_story_short.py`)
- route manifest and sitemap (`gen_route_manifest.py`, `gen_sitemap.py` if
  the route set changes)
- README/docs PNGs (`export_readme_figures.py`)
- `uv.lock` (`uv sync`)

## Downloads (owner approval O9; none happen before approval)

| item | source | approx. size | licence |
|---|---|---|---|
| `Qwen/Qwen3.5-4B` | huggingface.co | ~9 GB bf16 [I] | Apache-2.0 (confirm on card) |
| `google/gemma-4-E4B-it` | huggingface.co | ~16 GB bf16 [I] (8B with embeddings) | Apache-2.0 [V] |
| `lytang/C2D-and-D2C-MiniCheck` | huggingface.co | < 50 MB [I] | MIT [V] |
| `lytang/LLM-AggreFact` (test split) | huggingface.co, gated | < 200 MB [I] | CC BY-ND 4.0, eval-only [V] |
| `lytang/MiniCheck-Flan-T5-Large` | already in local HF cache [V] | 0 | MIT [V] |
| Python packages (gymnasium, SB3, sb3-contrib, mlx, mlx-lm) | pypi.org | < 1 GB | MIT |
| Optional rung (O4): `Qwen/Qwen3.5-2B`, `google/gemma-4-E2B-it` | huggingface.co | ~4 GB, ~10 GB [I] | Apache-2.0 |

## Acceptance criteria

- [ ] S-0 helper merged with tests; strict mypy clean.
- [ ] E2: `reports/metrics.json` has every policy's mean normalised profit,
      % of bound (overall and per ρ), violations (all 0), the P1 paired
      bootstrap CI, the relative lift, and P1/P2 verdicts computed by code.
- [ ] E2: `sealed_access.json` shows one `seal_read` for test and one per
      stress set; `preregistration` sha in the ledger predates them; the
      owner's commit of `params.yaml` predates them.
- [ ] E1: `reports/metrics.json` has every arm on G1 and G2, H1/H2 deltas
      with CIs and verdicts per family, H3 context deltas; dev-tuned
      threshold numbers labelled secondary.
- [ ] E1: `g2_owner_labels.json` says `labelled_by: "owner"`; no AggreFact
      text in git; `sealed_access.json` shows `prepare` then one
      `seal_read` per set.
- [ ] Both: ledgers complete; `request_hosts` empty outside E1-2 and E1-3
      download steps; no absolute paths; all CI tests pass without mlx and
      without downloads.
- [ ] Both: articles follow the story contract; every number traces to a
      committed file; `check_headline_numbers.py` covers both projects.
- [ ] All gates in "Commands and gates" green.

## Verification evidence required

- Tests run and results: per-project `pytest --cov` output with coverage %;
  `libs/portfolio-eval` tests.
- Build or typecheck results: ruff, ruff format, mypy, import-linter, web
  `npm test/lint/build`, `mkdocs build --strict`.
- Runtime verification: smoke and throughput numbers (E1-2, E2-3), wall-clock
  per step, peak memory for E1 training; the API lists projects 14 and 15
  after restart; `/projects` renders both cards.
- Artifact paths inspected: each `metrics.json`, `sealed_access.json`,
  `experiment_log.json`, `params.yaml: preregistration`, and the three E2
  price-trace figures.

## Owner decisions

| id | decision | recommendation | blocking for |
|---|---|---|---|
| O1 | Budget | $0 hosted, $0 cloud; local electricity only. If the E1 smoke gate projects > 24 h, reduce scope rather than rent a GPU. If you want a cloud fallback, set a hard cap (for example $25) and name the provider; prices were not verified in this design | E1-6 only if the smoke gate fails |
| O2 | Dataset licences | Accept: C2D/D2C (MIT) for training; LLM-AggreFact (CC BY-ND 4.0, gated, evaluation only) for G1, with ids-only commits; M5 derived parameters under the competition's research terms; Bijmolt et al. as the cited prior. If you decline AggreFact, E1 falls back to Banking77 (CC BY 4.0) with the same protocol | **E1-3** |
| O3 | Is the 30-item judge_v2 hand-labelling a prerequisite? | Not for E2, and not for E1's primary endpoint (G1). It is subsumed: G2 asks you to label all 147 judge_v2 claims blind (about 2.5 h at ~1 min each [I]), which includes the 30 `owner_sample.json` items, so it also closes review decision D1 for 01. Do the 30 first as a pilot to time yourself. G2 labels are required before E1-7 | **E1-7** |
| O4 | Acceptable open model sizes | Primary: Qwen3.5-4B and Gemma-4-E4B (both Apache-2.0). Optional smaller rung: Qwen3.5-2B and Gemma-4-E2B (adds a size-lift curve, ~+40% compute [I]). Not recommended for fine-tuning: ≥ 9B (time) | **E1-2** |
| O5 | Where pricing sits in the portfolio | `projects/15-dynamic-pricing-rl`, topic "Decision Science" beside 10 (uplift), not a new topic for one project. Alternative: "Optimization" beside 06. For E1: topic "NLP & Transformers" beside 04 | E2-9, E1-8 |
| O6 | Project numbers and order | 14 = fine-tuning, 15 = pricing; build 15 first (no external blockers) | E2-1 |
| O7 | Pre-registered thresholds | E1: H1 ≥ +5.0 pp BAcc with CI lower bound > +2.0 pp; H2 lower bound > −5.0 pp. E2: P1 ≥ +1.0% relative profit with CI excluding zero; P2 zero violations | **E1-5, E2-6** |
| O8 | Elasticity prior | Normal(−2.5, 0.8) truncated to [−5.0, −0.8], anchored on the −2.62 meta-analysis mean; stress priors at −1.5 and −3.5 | **E2-3** |
| O9 | Downloads | approve the table above | **E1-2** |
| O10 | Shared `portfolio_eval/intervals.py` | yes (two new callers; existing projects untouched) | S-0 |
| O11 | Publish adapters or policies | no (DVC-local only) | none |

## Risks and open questions

- mlx-lm support for Gemma 4 and Qwen3.5 training is unconfirmed (secondary
  sources only); E1-2 decides, with PEFT-on-MPS as fallback.
- PPO may not beat inventory-aware Thompson sampling. The article then
  reports a failed P1; thresholds do not move.
- The pricing result is about a semi-synthetic simulator; the elasticity is
  an assumption. Copy must say so in the Limits section and the card.
- G2 negatives are constructed mutations (review 5.2). G2 measures the
  portfolio distribution's claim style, not real generator errors.
- AggreFact's eval-only clause: we use it only to score. If the owner reads
  the clause more strictly (for example, no ids in git), commit the sampling
  seed and filter code only, and regenerate ids locally.
- `planned` status is not hidden on the site, so skeleton stories must not
  be committed before results exist.
- If import-linter or any generator fails because a project directory lacks
  `portfolio.yaml` during the build phase, stop and record it in
  `OPEN_QUESTIONS.md` rather than committing a placeholder card.
