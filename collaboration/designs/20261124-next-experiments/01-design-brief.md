# Design brief: next two experiments (LLM fine-tuning lift, RL dynamic pricing)

Date: 2026-11-24
Designer: Claude Code
Owner: session owner
Status: draft (owner approval requested)
Related artifacts: `collaboration/reviews/20261124-orchestrator-review/00-review.md`,
`projects/04-nlp-classification/`, `projects/01-rag-agent/`,
`projects/02-demand-forecasting/data_m5/`, `projects/10-uplift-experimentation/`,
`docs/engineering/statistical-intervals.md`

Legend: **[V]** verified in this session (file read, command run, or page
fetched on 2026-11-24); **[I]** inference or estimate, to be measured by the
first gate of each experiment.

## Problem

The portfolio has 13 experiments. Two capability gaps are visible to a
reader who scans the topics (`projects/*/portfolio.yaml` `topic:` [V]):

1. **No open-weight LLM fine-tuning.** Project 04 fine-tunes encoders
   (DistilBERT, roberta-base) with a hand-written PyTorch loop [V]
   (`projects/04-nlp-classification/README.md`). No project adapts a
   decoder LLM (Gemma or Qwen), and no project measures fine-tune lift over
   the same model's zero-shot and few-shot behaviour.
2. **No reinforcement learning.** Projects 05, 06, 10 and 12 make decisions
   with thresholds, solvers, uplift policies and cost surfaces. None trains a
   sequential policy in an environment, and none has a constrained action
   space.

The owner asks for two article-grade experiments that close these gaps.
Both must hold to the repo's evidence bar: pre-registered thresholds,
intervals, sealed test data, and numbers traced to committed files.

## Context and evidence

### (a) Honest inventory: what exists, what is reusable, what is missing

| Piece | Where [V] | Reusable for | Limit |
|---|---|---|---|
| Story, manifest, demo registry schemas | `libs/portfolio-core/src/portfolio_core/{story,manifest,demo}.py` | both articles as-is | manifest `status` is `flagship\|working\|planned`; `planned` is not hidden on the site, so a skeleton story must not be committed early |
| Data-quality gates, IO, logging, synthetic helpers | `portfolio_core/{dq,io,logging,synthetic}.py` | both | none |
| LLM provider and spend ledger | `portfolio_core/llm.py` (`build_model`, `ollama_available`), `llm_budget.py` (`SpendLedger`, `RateCard`, `BudgetExceededError`) | E1 only if a hosted arm were added (it is not) | built for pydantic-ai chat calls, not for token-logprob scoring of a local MLX model |
| Classification and regression metrics | `libs/portfolio-eval/src/portfolio_eval/ml.py` (`classification_metrics`) | E1 | no balanced accuracy, no AUROC, no intervals |
| Run comparison and HTML report | `portfolio_eval/{metrics,report}.py` (`RunResult`, `compare_runs`, `ReportBuilder`) | both | none |
| Interval helpers | duplicated per project: `rag_agent/reporting.py:173 bootstrap_ci`, `02 m5_track.py:1153,1191 paired_bootstrap_*`, `09 agentic_workflows/report.py:51 wilson_interval`, `01 scripts/build_judge_calibration_report.py:81 kappa_bootstrap_ci` | conventions in `statistical-intervals.md` | **missing from the shared lib**; projects may not import each other (import-linter independence contract in the root `pyproject.toml`) |
| RAG judge, verifier, gate, phase meter, checkpointed runner | `projects/01-rag-agent/src/rag_agent/{judge,verify,gate,metering,runner}.py` | E1 as design pattern only (independence contract) | judge is a pydantic-ai rubric judge over a hosted or Ollama model; it cannot be fine-tuned |
| Measurement scripts and experiment ledger | `01 scripts/{measure_retrieval,run_e2e_eval,label_judge_calibration_v2}.py`; `reports/experiment_log.json` (337 append-only rows with `config_sha256`, `set_sha256`, `request_hosts`, `decision`) | the ledger row shape is the pattern for both experiments | the writer is in 01; copy the pattern, not the code |
| Sealed-set discipline | `01 scripts/build_final_v3.py` file-access log, `reports/final_v3_file_access.json`; the review's 5.2 shows final_v3 was read 4 times | both experiments seal their test sets the same way, and avoid the reuse failure | the log has absolute home paths (review P4); new logs must write repo-relative paths |
| Judge calibration claims with evidence text | `projects/01-rag-agent/data/judge_v2_claims.json` (147 items: 75 supported, 72 unsupported, each with `claim`, `chunk_id`, `chunk_text`, `kind`) [V]; `reports/judge_calibration_v2/owner_sample.json` (30 items, unlabelled) [V] | E1 owner-labelled golden set G2 | negatives are constructed mutations, not real generator errors (review 5.2); the real final_v3 checkpoint rows do not persist claim text (`runs/final_v3-432d6b705715/rows.jsonl` keys: `qhash, question, trace, hosts, spend_usd, ts`) [V] |
| Encoder fine-tuning ladder | `projects/04-nlp-classification` (TF-IDF baseline, DistilBERT, roberta-base, Optuna HPO, MPS full-data run, latency probe, LLM cascade, fresh holdout) | E1 baseline ladder shape, the "classical baseline first" rule, the latency probe idea | task (AG News topics) is solved at macro-F1 0.946 [V]; repeating it with an LLM adds little |
| Local serving benchmark incl. MLX runner | `projects/08-inference-serving` (Ollama, `gemma4:31b-mlx`, qwen3.6 MoE) [V] | proves MLX inference runs on this machine | serving only; no training |
| M5 dense subset with prices | `projects/02-demand-forecasting/data_m5/subset_{Y,X,S}.parquet` (600 series, 200 items x 3 stores, 2011-01-29 to 2016-06-19, `sell_price` with zero nulls), committed in git [V] | E2 simulator calibration (demand level, weekday profile, dispersion) | **price elasticity is not identifiable from it**: see the probe below |
| Paired bootstrap, policy value | `projects/10-uplift-experimentation` and `05` (paired row bootstrap, seed 42) | E2 evaluation convention | per-project code |
| Showcase demos | `projects/02/demo.yaml` (forecast-workbench), `projects/05/demo.yaml` (churn-sandbox), `scripts/check_demo_contract.py` [V] | a later pricing demo could reuse the static-payload contract | out of scope here |
| Generators and gates | `scripts/new_project.py`, `gen_static_registry.py`, `gen_story_short.py`, `gen_route_manifest.py`, `check_short_copy.py`, `check_headline_numbers.py`, `stamp_metrics_meta.py`, `lint_story_language.py`, `export_readme_figures.py` [V] | both | `check_headline_numbers.py` needs one extractor per new project |
| Local hardware and runtimes | Apple M4 Max, 128 GB unified memory (`sysctl`) [V]; Ollama models `qwen3:4b`, `qwen2.5:3b`, `gpt-oss:20b`, `qwen3.6:35b-a3b-q4_K_M` [V]; HF cache holds `lytang/MiniCheck-Flan-T5-Large`, `google/flan-t5-large`, `mlx-community/Qwen3.6-35B-A3B-4bit` [V]; uv env has torch 2.14.1, transformers 5.19.0, datasets 5.1.0, scikit-learn 1.9.1, scipy 1.18.1 [V] | both | `mlx`, `mlx-lm`, `gymnasium`, `stable-baselines3` are **not** installed [V]; CI runs on `ubuntu-latest` [V], so MLX must be an optional, Darwin-only extra |

**What is missing** (and this design adds): a decoder-LLM training path
(MLX LoRA), a label-token log-probability scorer, balanced accuracy with a
cluster bootstrap, a Gymnasium environment, an RL trainer, a bandit
baseline, a fluid upper bound, and one shared interval helper.

### Probe: M5 prices do not give causal elasticities [V]

Read-only local check on the committed dense subset (weekly units vs mean
weekly `sell_price`, rows with positive sales):

| estimator | FOODS | HOUSEHOLD | HOBBIES |
|---|---|---|---|
| per-series log-log slope, median (series with price sd > 0.02) | -0.62 (n=335) | +1.61 (n=45) | +0.77 (n=39) |
| two-way fixed effects (series, store x week), pooled slope | +0.595 (107,094 rows) | +2.419 (26,206 rows) | +1.198 (12,993 rows) |

Positive "elasticities" mean that M5 price changes are mostly regular
increases that move with demand growth, not experiments. Median price
ratio max/min per series is 1.17 and 410 of 600 series vary by more than
10% [V]. So M5 can calibrate **how much and when** people buy, but not
**how they react to price**. The elasticity must come from a stated
prior. This is the main reason the pricing environment is semi-synthetic.

### Other constraints that shape the design

| Claim or constraint | Evidence path | Why it matters |
|---|---|---|
| Projects may not import each other | root `pyproject.toml` `[tool.importlinter]` independence contract; 09 -> 01 is the only documented exception | E1 reads 01's claim file by path (data, not code); E2 reads 02's parquet by path |
| final_v3 is consumed | review 5.2, D2 | E1 must not use final_v3 questions or traces as test data |
| Owner labels are not done | review C1, 5.3 | any "owner-labelled" wording waits for the owner's actual labels |
| Every number traces to a committed file | `docs/engineering/repo-conventions.md` "Truth in copy" | metrics JSON in git, large outputs in DVC |
| Interval vocabulary | `docs/engineering/statistical-intervals.md` | "95% CI" with method named; "spans zero / excludes zero", never "significant" |
| No hosted LLM or paid API calls | owner request | every model call in both experiments is local; ledger `request_hosts` must stay empty outside download steps |

## Goals and non-goals

Goals:

- **E1 (fine-tuning).** Fine-tune Qwen3.5-4B and Gemma-4-E4B (LoRA, MLX on
  the MacBook) as grounded-claim verifiers (claim + evidence -> supported /
  unsupported). Measure lift over the same checkpoint's zero-shot and
  few-shot behaviour, over a classical baseline, and against a published
  specialist (MiniCheck-Flan-T5-Large), on a sealed public golden set and
  an owner-labelled portfolio set, with paired cluster-bootstrap CIs and a
  pre-registered lift threshold.
- **E2 (dynamic pricing).** Train a masked-action PPO policy with a custom
  history encoder in a Gymnasium pricing environment calibrated on the
  committed M5 subset. Beat the best non-RL baseline (fixed price, markdown
  rule, inventory-aware Thompson sampling) on 1,000 sealed held-out
  simulated episodes, with common random numbers, a paired bootstrap CI and
  zero constraint violations.
- Both ship as new projects with full stories, after their numbers exist.

Non-goals:

- Replacing 01's production judge with the fine-tuned model (a later design
  can use E1's result).
- Any hosted model call, cloud GPU, or paid API (unless the owner approves a
  cloud cap, decision O1).
- Publishing adapters or policies to the Hugging Face Hub.
- A live web demo for either project (a later design; the demo contract
  already exists).
- Claims about real-world revenue. E2's numbers are about the simulator.
- Reference-price effects, competitor prices, multi-product substitution in
  E2 (named as limits).

## Constraints

- Repository conventions and gates: smallest complete change; one project
  per experiment; `ruff`, `ruff format --check`, `mypy libs projects apps`,
  `pytest --cov` per project, all content checks; `stamp_metrics_meta.py` on
  each metrics write; generated registries rebuilt by script only; no
  `Co-Authored-By` model trailers; agents never commit, push or merge.
- Compatibility: CI is Linux. MLX and mlx-lm go in an optional
  `[mlx]` extra with a `sys_platform == 'darwin'` marker and lazy imports;
  every CI test runs without them. torch is already in the workspace.
- Privacy, security, cost: $0 hosted spend. Model and dataset downloads need
  owner approval (sizes in the handoff). LLM-AggreFact is gated and
  CC BY-ND 4.0, evaluation-only: the owner accepts its terms personally, and
  its rows are never committed or used for training or selection. Written
  logs use repo-relative paths.
- Performance: each experiment's full run fits in about one working day of
  local compute [I], confirmed by a measured smoke gate before the full run.

## Options

### E1 task choice

| Option | Strength | Cost or risk | Best when |
|---|---|---|---|
| **A. Grounded-claim verification** (binary: is the claim supported by the evidence?) train on MiniCheck C2D/D2C (MIT, 14.4k rows), test on LLM-AggreFact (11 datasets) + owner-labelled portfolio claims | Connects to the portfolio's largest open weakness (self-judging in 01, review 5.2); published specialist baseline exists; real distribution shift between train and test | AggreFact is gated and eval-only; long documents need a length cap; owner labelling ~2.5 h | the owner wants a non-toy result that feeds back into 01 |
| B. Banking77 intent classification (CC BY 4.0, 10,003 train / 3,080 test, 77 classes) | Clean licence, simple pipeline, large lift almost certain | Another short-text topic classifier next to 04; "lift" is predictable; no owner-labelling need | E1 must avoid gated data |
| C. Reuse AG News | Zero new data | Duplicates 04; DistilBERT already reaches 0.946 | never |

### E1 training path

| Option | Strength | Cost or risk | Best when |
|---|---|---|---|
| **mlx-lm LoRA (0.32.2)** | Native Apple Silicon, LoRA/QLoRA/DoRA, prompt masking, fuse; MIT | Gemma 4 support in `mlx_lm.lora` is unconfirmed (community reports train Gemma-4-E4B with `mlx_vlm.lora`) | default; smoke gate decides per family |
| PEFT + TRL on torch MPS | Most documented path; torch already present | slower on MPS [I]; peft 0.22.0 (2026-11-19) is newer than the 14-day rule | fallback when mlx-lm cannot load a family |
| Cloud GPU (rented A100/H100) | Fast | Paid; owner said MacBook-first | only if O1 sets a cap and the smoke gate projects > 24 h locally |

### E2 framework

| Option | Strength | Cost or risk | Best when |
|---|---|---|---|
| **Gymnasium 1.4.0 env + Stable-Baselines3 2.9.2 + sb3-contrib MaskablePPO** | Maintained, MIT, torch-based (already in workspace), action masking enforces constraints by construction, custom features extractor = custom policy | two new deps; `check_env` ignores masks | default |
| CleanRL | Readable single-file PPO | "not meant to be imported": we would vendor and maintain a file | teaching material, not a project dependency |
| RLlib (Ray) | Distributed scale | heavy dependency tree for a CPU-sized problem; not verified | multi-node training |
| Hand-written policy gradient | Matches 04's "hand-written loop" ethos | reinvents PPO clipping, GAE, masking; more code to review | never here |

## Recommendation

- **E1 = option A**, new project **`projects/14-llm-finetuning/`**: LoRA
  fine-tune of `Qwen/Qwen3.5-4B` and `google/gemma-4-E4B-it` with mlx-lm,
  scored by label-token log-probability. Fallback task B if the owner
  declines AggreFact's terms.
- **E2** = new project **`projects/15-dynamic-pricing-rl/`**: Gymnasium env
  calibrated on the committed M5 subset, elasticity from a published prior,
  MaskablePPO with a custom history encoder, baselines up to inventory-aware
  Thompson sampling, fluid upper bound as the ceiling.
- **Shared:** add one small `portfolio_eval/intervals.py`
  (`wilson_interval`, `paired_bootstrap`, `cluster_bootstrap`) so the two new
  projects do not add a fifth and sixth copy. Existing projects keep their
  copies (no churn).
- **Order:** E2 first (fully offline, no labelling or gated data), E1 while
  the owner labels G2 and accepts AggreFact's terms. Both can run in
  parallel if the owner prefers.

What this deliberately does not solve: whether the fine-tuned verifier should
replace 01's judge; real-revenue validity of the pricing policy; the 01 copy
blockers C1/C2 from the review (separate wave).

## Acceptance criteria

- [ ] E1: `reports/metrics.json` holds balanced accuracy (BAcc) for every
      arm on G1 (sealed AggreFact sample) and G2 (owner-labelled portfolio
      claims), with paired cluster-bootstrap 95% CIs for every pre-registered
      delta, and a `preregistration` block whose sha256 was logged before
      the sealed read.
- [ ] E1: the pre-registered verdict (pass or fail) is printed as computed,
      for each family, with no post-hoc threshold change.
- [ ] E2: `reports/metrics.json` holds mean episode profit, % of the fluid
      upper bound, and constraint violation counts for every policy on the
      1,000 sealed test episodes, the paired bootstrap CI of RL minus the
      best non-RL baseline, and the pre-registered verdict.
- [ ] E2: zero constraint violations for every reported policy, asserted in
      tests and in the metrics file.
- [ ] Both: sealed test sets read once, proven by an access log with
      repo-relative paths; ledger rows for every run; `request_hosts` empty
      outside approved download steps.
- [ ] Both: stories, READMEs, docs pages, card copy and registries added only
      after metrics are committed; all gates green.

## Rollback and failure behavior

- Failure modes: a family cannot be trained locally (smoke gate fails ->
  fallback path or drop the family, recorded); fine-tune gives no lift (the
  article reports the failure; this is a valid result); PPO does not beat
  Thompson sampling (likewise reported; no threshold change); sealed set
  touched twice (run is void, a new seed set is drawn and the ledger says
  why).
- Observability: append-only `reports/experiment_log.json` per project,
  access logs for sealed sets, `_meta` stamps on metrics.
- Rollback path: each experiment is a new directory plus registrations;
  removing the directory and its registration lines restores the prior
  state. The shared `intervals.py` addition is additive.

## Open questions

Owner decisions O1 to O11 are listed in `03-implementation-handoff.md`,
section "Owner decisions". None blocks reading this design.
