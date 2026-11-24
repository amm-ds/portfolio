# Architecture proposal: next two experiments

Date: 2026-11-24
Designer: Claude Code
Status: draft (owner approval requested)
Source design brief: `collaboration/designs/20261124-next-experiments/01-design-brief.md`

Legend: **[V]** verified in this session; **[I]** inference or estimate.

## Decision

Two new uv workspace projects, each self-contained under the independence
contract, sharing one new interval helper in `portfolio_eval`:

- `projects/14-llm-finetuning/` (package `llm_finetuning`): grounded-claim
  verification. LoRA fine-tunes of Qwen3.5-4B and Gemma-4-E4B with mlx-lm,
  scored by label-token log-probability against zero-shot, few-shot, a
  classical baseline, and MiniCheck-Flan-T5-Large.
- `projects/15-dynamic-pricing-rl/` (package `dynamic_pricing`): a Gymnasium
  single-product pricing environment calibrated on the committed M5 subset,
  a MaskablePPO policy with a custom history encoder, three non-RL baselines,
  and a fluid upper bound.

Both use the same evidence spine that 01 built: pre-registration committed
before the sealed read, an append-only ledger, a sealed-set access log, and
`_meta`-stamped metrics.

## System shape

### Shared spine (both projects)

```text
params.yaml (incl. preregistration block)
   │  sha256 logged in reports/experiment_log.json BEFORE any sealed read
   ▼
prepare  →  data/ (DVC)  +  data/splits.json (ids + sha256, git)
   ▼
train    →  reports/models/ (DVC)  +  ledger row
   ▼
evaluate (dev/val only, many reads allowed)  →  reports/dev_metrics.json
   ▼
seal-read (once)  →  reports/metrics.json (git, _meta stamped)
                  →  reports/sealed_access.json (repo-relative paths)
   ▼
figures  →  reports/figures/*.json (git)  →  story.yaml / README / docs
```

`portfolio_eval/intervals.py` (new, strict mypy, no first-party imports):

- `wilson_interval(k, n, z=1.959964) -> tuple[float, float]`
- `paired_bootstrap(a, b, stat, n_resamples=2000, seed=42) -> (point, lo, hi)`
  over aligned rows.
- `cluster_bootstrap(a, b, clusters, stat, n_resamples=2000, seed=42)`:
  resample clusters (documents, or episodes' series) with replacement.

### E1: 14-llm-finetuning

```text
lytang/C2D-and-D2C-MiniCheck (MIT, 14,395 rows: claim, doc, label)
   └─ group split by sha256(doc): train 90% / dev 10%
lytang/LLM-AggreFact test (gated, CC BY-ND 4.0, eval-only)
   └─ G1: stratified sample, 200 rows per source dataset (all if fewer),
          doc ≤ 1,800 tokens (Qwen tokenizer), 13-gram leakage filter vs train docs
projects/01-rag-agent/data/judge_v2_claims.json (147 claims + chunk_text)
   └─ G2: owner relabels all 147 blind (model labels hidden)

arms (same prompt template, same scorer):
  classical      logistic regression on lexical-support features (train split)
  specialist     MiniCheck-Flan-T5-Large, threshold 0.5 (no tuning)
  {qwen,gemma} × zero-shot     instruct checkpoint, no exemplars
  {qwen,gemma} × few-shot-4    4 fixed balanced exemplars from train (seed 42)
  {qwen,gemma} × lora          mlx-lm LoRA on train, checkpoint chosen on dev

scorer: one forward pass over the chat-formatted prompt with the assistant
turn opened; p(supported) = softmax over the two label tokens' logits;
predict supported iff p ≥ 0.5 (pre-registered fixed threshold; a dev-tuned
threshold is reported as secondary)
```

Definitions that matter:

- **"Base model"** = the off-the-shelf instruction-tuned checkpoint
  (`Qwen/Qwen3.5-4B`, `google/gemma-4-E4B-it`). The LoRA arm starts from the
  same weights, so the lift isolates the fine-tune.
- **Prompt** (fixed, committed in `params.yaml`): system line "You verify
  whether a claim is fully supported by a document. Answer with one word:
  Yes or No."; user turn "Document:\n{doc}\n\nClaim: {claim}"; label tokens
  " Yes"/" No" (Kimi verifies each tokenizer maps them to single tokens and
  records the ids; if not, use "1"/"0"). Thinking/reasoning modes off via the
  chat template.
- **Training format**: mlx-lm chat JSONL with the assistant answer "Yes" or
  "No"; prompt tokens masked from the loss (`--mask-prompt`).
- **Classical baseline** features: content-word coverage of the claim in the
  doc, number and year match share, capitalised-entity match share, best
  sentence-level token overlap, claim length, doc length. scikit-learn
  `LogisticRegression` (already in the workspace).

Metrics: balanced accuracy (BAcc, the LLM-AggreFact convention per the
MiniCheck paper) primary; F1 of the "unsupported" class, AUROC of
p(supported), Brier score and Expected Calibration Error (ECE, 10 bins)
of p(supported), and per-source-dataset BAcc secondary. G2 also reports
sensitivity and specificity with Wilson intervals.

Intervals: G1 deltas use `cluster_bootstrap` with clusters = document hash
(AggreFact has several claims per document), stratified by source dataset,
2,000 resamples, seed 42. G2 deltas use `paired_bootstrap` over items.

Pre-registered hypotheses (written to `params.yaml: preregistration` and
logged before the G1 read):

| id | statement | pass rule |
|---|---|---|
| H1 (primary, per family) | LoRA beats the better of the same checkpoint's zero-shot and few-shot arms on G1 | BAcc delta ≥ +5.0 pp **and** 95% CI lower bound > +2.0 pp |
| H2 (guardrail, per family) | LoRA does not degrade on the portfolio distribution | G2 BAcc delta vs the same comparator has 95% CI lower bound > −5.0 pp |
| H3 (context, no gate) | LoRA vs classical and vs MiniCheck-Flan-T5-Large on G1 | reported with CI, no pass rule |

"Meaningful lift" = H1 and H2 both pass. Which comparator is "the better of
zero-shot and few-shot" is decided on the **dev** split, not on G1.

Power note [I]: with n≈2,200 rows in ~1,000 document clusters, the CI
half-width on a paired BAcc delta is about 2-3 pp, so a true lift of about
5 pp or more is detectable at this threshold; a smaller true lift is
reported as "not established".

Leakage rules:

1. Train/dev split grouped by document hash; no document in both.
2. G1 rows whose document shares any 13-gram (lower-cased, whitespace
   tokens) with any training document are dropped before sampling; the
   count is recorded.
3. Few-shot exemplars come from train only, fixed by seed, identical for
   every G1/G2 row.
4. No G1 or G2 row is ever used for training, checkpoint choice, threshold
   choice, or prompt edits. AggreFact dev is not used at all (licence says
   evaluation only; selection is kept on C2D/D2C dev to stay clear of that
   line).
5. G2 claims come from 01's tuning-65/dev_v1 chunks, not final_v3 (the
   builder never reads final_v3, `build_judge_calibration_v2.py` docstring
   [V]).
6. Stated limit: base models may have seen public AggreFact sources during
   pre-training. This affects every LLM arm alike; the article says so.

Compute plan (estimates [I], replaced by measured numbers at gate E1-2):

| item | estimate |
|---|---|
| train tokens per epoch | 14.4k rows × ~500 tokens ≈ 7M |
| LoRA throughput, 4B-class bf16 on M4 Max | ~1.5-3k tokens/s → ~40-80 min per epoch |
| training budget | ≤ 2 epochs per family, rank 16, all attention + MLP projections, lr 1e-4, batch 8 (grad accumulation allowed), max seq 2,048 |
| G1 scoring per arm | ~2,200 × ~1,000 prompt tokens; prefill-only ≈ 10-25 min |
| arms | 6 LLM arms + classical + MiniCheck ≈ 3-4 h scoring |
| total | ≈ 1 working day, $0 hosted, electricity only |
| memory | E4B is 8B parameters with embeddings (bf16 ≈ 16 GB); fits 128 GB with LoRA [V for RAM, I for footprint] |

### E2: 15-dynamic-pricing-rl

```text
projects/02-demand-forecasting/data_m5/subset_{Y,X,S}.parquet  (read by path, sha256-pinned)
   └─ calibration window: 2011-01-29 .. 2016-04-24 (excludes 02's 2016-05-23..06-19 test window)
   └─ per series: base daily mean (last 52 weeks), weekday profile (7 shares),
      NB dispersion k (method of moments), reference price p_ref (modal last-52w price)
   └─ split by item_id: 140 / 30 / 30 items → 420 train / 90 val / 90 test series

elasticity prior (stated assumption, owner decision O8):
   ε ~ Normal(-2.5, 0.8) truncated to [-5.0, -0.8]
   anchored on Bijmolt, van Heerde & Pieters (2005) meta-analysis mean -2.62
   stress priors for robustness only: mean -1.5 and mean -3.5 (same sd)

PricingEnv(gymnasium.Env)
   episode: T = 91 days, one decision per day
   action: Discrete(7) → price multiplier m ∈ {0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30} × p_ref
   demand: λ_t = base · dow[t mod 7] · m_t^ε ; sales_t = min(NB(λ_t, k), inventory_t)
           NB draws by inverse CDF from a pre-drawn uniform stream per episode
           (common random numbers: every policy sees the same uniforms)
   inventory: I0 = horizon demand at p_ref / ρ, ρ ∈ {0.7, 1.0, 1.3} per episode; no replenishment
   reward_t = (p_t − c) · sales_t / R_ref ; terminal adds salvage s · leftover / R_ref
              c = 0.60 · p_ref, s = 0.30 · p_ref, R_ref = expected revenue at p_ref over T
   observation (float32 Box): t/T, inventory/I0, days since last change / 7, current multiplier,
              last 14 days of (multiplier, sales / λ_ref_t) , next-7-day λ_ref profile / base,
              ρ is NOT observed, ε is NOT observed
   constraints (action mask, `action_masks()`):
     C1 price band 0.70-1.30 × p_ref (by action space)
     C2 at most one ladder step change per decision
     C3 at least 7 days between changes
     C4 price ≥ c · 1.05 (holds for the whole band with c = 0.60 · p_ref; asserted in a test)
   env counts any invalid action it receives (strict mode raises; default mode holds price
   and increments info["violations"])
```

Policies:

| id | policy | tuned on |
|---|---|---|
| B0 | fixed price at p_ref | none |
| B1 | single best static multiplier (one value for all episodes, since ρ and ε are unobserved) | train episodes |
| B2 | sell-through markdown rule: compare cumulative sales with the linear plan I0 · t/T; behind by > x% → one step down, ahead by > y% → one step up, respecting C2/C3 | grid over x, y on train |
| B3 | inventory-aware Thompson sampling (Ferreira, Simchi-Levi & Wang 2018, TS-fixed idea): Bayesian linear regression of log((sales+0.5)/λ_ref) on log m with the training prior on ε; each day sample ε, solve the fluid LP for the remaining horizon and inventory over allowed actions, play today's best allowed action | prior from train calibration |
| RL | MaskablePPO with a custom `BaseFeaturesExtractor`: a 1-D conv over the 14-day history plus an MLP over the scalar context, concatenated (separate pi/vf heads) | train episodes; 3 training seeds; model chosen on val |
| UB | fluid (deterministic) upper bound with known ε: LP over time-price mixtures with Σ demand ≤ I0 (Gallego & van Ryzin style), `scipy.optimize.linprog` | none (ceiling, not a competitor) |

Evaluation sets (all drawn before training, ids + seeds committed in
`data/splits.json`):

- train: unlimited episodes from train series, seed stream 0.
- val: 300 episodes (val series × seeds from stream 1); used for PPO seed
  choice, B2 grid, and the "best non-RL baseline" choice.
- **test (sealed)**: 1,000 episodes (test series × seeds from stream 2),
  balanced over ρ. Read once.
- stress (reported, no gate): 500 episodes each under the two shifted priors,
  read once after the test read.

Pre-registered hypotheses:

| id | statement | pass rule |
|---|---|---|
| P1 (primary) | RL beats the best non-RL baseline (chosen on val among B0-B3) on mean normalised episode profit | relative lift ≥ +1.0% **and** paired bootstrap (episodes, 2,000 resamples, seed 42) 95% CI of the profit difference excludes zero on the positive side |
| P2 (hard) | constraints hold | violations = 0 for every policy on every test episode, with masks passed at evaluation |
| P3 (context, no gate) | share of fluid upper bound, per ρ bucket and per stress prior | reported |

Honest prior expectation [I]: B3 is close to optimal for a one-parameter
demand curve, so P1 may fail. That is an acceptable, publishable result;
the threshold does not move.

Compute plan [I]: vectorised env (8 `DummyVecEnv` or `SubprocVecEnv` copies —
choose whichever scores higher steps/s in E2-3), 3M PPO steps per
seed, about 1-2k steps/s on CPU → about 30-60 min per seed, 3 seeds ≈ 2-3 h.
B3 solves one small LP per day per episode: 1,000 × 91 ≈ 91k LPs, about
10-30 min. $0.

Both `raw_gross_profit` (ex-salvage) and `mean_normalised_profit` (with
terminal salvage `s * leftover`) are recorded per policy in `metrics.json`
so terminal-salvage reliance is transparent.

## Contracts and data ownership

- Public schemas or APIs: none new. Story and manifest follow
  `portfolio_core.story` / `manifest`.
- Internal types: frozen dataclasses for `SeriesCalibration`, `EpisodeSpec`,
  `ArmResult` (E2) and `ClaimRow`, `ArmScores` (E1); parsed at the data
  boundary, trusted inside.
- Data and artifact ownership:
  - 14 owns its splits, adapters (DVC), scores per row (git if ≤ ~1 MB as
    gzip-free JSON of ids + probabilities; DVC otherwise), metrics (git).
    AggreFact text is never written to git; only row ids, source dataset
    names, document hashes and scores.
  - 15 owns its calibration table (git, small), splits (git), PPO checkpoints
    (DVC), per-episode results (git), metrics (git).
  - 01 and 02 data files are read by path with a sha256 check, never written.
- Generated files: `staticRegistry.ts`, `storyShort.ts`, route manifest,
  sitemap, README figures via their scripts only.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Put E1 inside 01 as a new judge | 01's `evaluate.py` is already 2,435 lines; mixes a finished article with a new experiment; final_v3 is consumed |
| Put E1 inside 04 | Different task and model family; 04's story is complete |
| Banking77 for E1 | Fallback only (see brief); weaker portfolio story |
| Fine-tune a 9B model | ~2x training time for a demonstration that 4B-class already makes; optional rung if O4 allows |
| Real pricing dataset (Dominick's, dunnhumby, UCI Online Retail II) | licences are research-only or terms-bound; observational prices still confound elasticity, as the M5 probe shows; UCI Online Retail II mixes wholesale invoices |
| Estimate elasticity from M5 with fixed effects | probe gives positive slopes [V]; would produce a simulator where raising prices raises demand |
| Continuous price action (SAC/TD3) | masking is impossible for Box actions in sb3-contrib; constraints would become soft penalties |
| RLlib, CleanRL, custom PPO | see brief |
| A separate `intervals` lib package | one module inside existing `portfolio_eval` is enough |

## Failure modes and limits

| Failure or limit | Detection | Behavior |
|---|---|---|
| mlx-lm cannot load or train a family | gate E1-2 smoke (10 LoRA steps + 20 scored rows) | try PEFT on MPS; if that also fails, drop the family, record in ledger and story |
| Label words are multi-token | tokenizer check in E1-2 | switch to "1"/"0", record |
| Projected run > 24 h | E1-2 / E2-3 measured throughput | reduce to 1 epoch or max seq 1,536 (E1); 2M steps (E2); recorded before training |
| AggreFact terms not accepted | O2 | fallback task B (Banking77), same protocol |
| Sealed set read twice | access log has 2 entries | run void; new seeds/sample; ledger explains |
| PPO evaluated without masks | test + `violations` counter | P2 fails loudly; never silently clipped |
| Reward hacking via end-of-season dump | salvage < cost; per-episode price traces in figures | visible in traces |
| Simulator validity | n/a | article states: results hold for the simulator; elasticity is an assumption |

## Migration and rollout

1. Add `portfolio_eval/intervals.py` + tests (additive).
2. E2 project end-to-end through its sealed read, then its article.
3. E1 project end-to-end through its sealed read, then its article.
4. Registrations (cards, CI matrix, import-linter, headline guard, docs,
   README rows, About page count) land with each article, not before.

## Observability and verification

- Logs, metrics: ledger rows per run (`config_sha256`, `set_sha256`,
  `request_hosts`, wall-clock, peak memory where available, decision);
  `_meta` stamps.
- Tests: unit tests for splits, leakage filter, scorer, features, env
  dynamics, masks, CRN, LP bound, baselines, intervals; all offline, no mlx.
- Manual: owner reads the per-arm table and three example price traces
  before the article step.

## Rollback

- Safe rollback point: before step 1 of each experiment; each project is a
  new directory.
- Not undone by rollback: owner labelling time; downloaded models in the
  local HF cache (delete manually if unwanted).

## References

### Online sources (fetched or searched 2026-11-24)

Verified directly (page or PyPI JSON fetched):

| item | source | what was verified |
|---|---|---|
| mlx-lm 0.32.2 | https://pypi.org/pypi/mlx-lm/0.32.2/json | uploaded 2026-10-16; MIT; requires `mlx>=0.32.2` on Darwin, `transformers>=5.7.0`; `train` extra |
| mlx 0.32.4 | https://pypi.org/pypi/mlx/json | latest version and MIT; upload date not visible |
| Gymnasium 1.4.0 | https://pypi.org/pypi/gymnasium/json | uploaded 2026-10-05; MIT; Python ≥ 3.10 |
| Stable-Baselines3 2.9.2 | https://pypi.org/pypi/stable-baselines3/2.9.2/json | uploaded 2026-10-26; MIT; needs gymnasium < 2.0, torch ≥ 2.8 |
| sb3-contrib 2.9.2 | https://pypi.org/pypi/sb3-contrib/json | version and MIT; upload date not visible |
| MaskablePPO | https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html | Discrete actions only; `action_masks()`; use maskable `evaluate_policy`; `check_env` ignores masks |
| SB3 custom policies | https://stable-baselines3.readthedocs.io/en/master/guide/custom_policy.html | `policy_kwargs`, custom `BaseFeaturesExtractor`, `ActorCriticPolicy` subclass |
| peft 0.22.0 | https://pypi.org/pypi/peft/json | uploaded 2026-11-19 (too new for the 14-day rule today); Apache-2.0 |
| trl 1.18.2 | https://pypi.org/pypi/trl/json | version and Apache-2.0; upload date not visible |
| CleanRL | https://github.com/vwxyzjn/cleanrl | "not meant to be imported"; MIT |
| Gemma 4 | https://huggingface.co/google/gemma-4-E2B ; https://ai.google.dev/gemma/docs/core/model_card_4 ; https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/ | Apache 2.0; sizes E2B (2.3B effective, 5.1B with embeddings), E4B (4.5B / 8B), 12B, 26B A4B, 31B |
| MiniCheck | https://github.com/Liyan06/MiniCheck ; https://huggingface.co/lytang/MiniCheck-Flan-T5-Large ; paper https://arxiv.org/abs/2404.10774 | repo Apache-2.0; Flan-T5-L model MIT; input (document, claim) → {0,1} |
| C2D/D2C training data | https://huggingface.co/datasets/lytang/C2D-and-D2C-MiniCheck | MIT; 14,395 rows (c2d 7.08k, d2c 7.32k); columns claim, doc, label |
| LLM-AggreFact | https://huggingface.co/datasets/lytang/LLM-AggreFact ; leaderboard https://llm-aggrefact.github.io/ | CC BY-ND 4.0; gated; evaluation only, "should not be used in pretraining or fine-tuning"; dev 30,420 / test 29,320 rows; 11 sources listed; leaderboard averages MiniCheck-Flan-T5-L 75.0, Bespoke-MiniCheck-7B 77.4 (no date shown) |
| Banking77 (fallback) | https://huggingface.co/datasets/PolyAI/banking77 | CC BY 4.0; 10,003 / 3,080 rows; 77 classes |

Searched, secondary sources only (not verified at the primary page):

| item | source | note |
|---|---|---|
| Qwen3.5 small models (0.8B, 2B, 4B, 9B; Apache 2.0; released 2026-03-02) | https://huggingface.co/Qwen/Qwen3.5-0.8B ; https://huggingface.co/collections/Qwen/qwen35 ; https://artificialanalysis.ai/es/articles/qwen3-5-small-models | licence seen on the 0.8B card metadata; Kimi confirms the 4B card licence before download |
| Qwen3.6 (27B dense, 35B-A3B MoE; no small sizes found) | https://huggingface.co/unsloth/Qwen3.6-27B-GGUF ; https://lmstudio.ai/models/qwen3.6 | why E1 uses Qwen3.5 for the 4B class |
| mlx-lm support for `qwen3_5` and Gemma 4 | https://github.com/ml-explore/mlx-lm/issues/1136 ; https://discuss.huggingface.co/t/gemma4-e4b-adaptors-fuse-after-training-how/176429 | qwen3_5 loads in mlx-lm ≥ 0.31.3 per a user report; Gemma-4-E4B LoRA reported via `mlx_vlm.lora`; **unverified**, hence the smoke gate. `mlx_lm/LORA.md` returned HTTP 503 when fetched |
| RAGTruth licence | https://arxiv.org/abs/2401.00396 ; https://huggingface.co/datasets/flowaicom/RAGTruth_test | original repo licence unconfirmed; not used directly (it reaches E1 only as one AggreFact source) |
| Price-elasticity prior | Bijmolt, van Heerde & Pieters (2005), JMR 42(2):141-156, https://repository.tilburguniversity.edu/items/813834f9-4626-45f8-ad0a-2920a545e089 | mean elasticity −2.62 over 1,851 elasticities from 81 studies (abstract as indexed) |
| Thompson sampling with inventory | Ferreira, Simchi-Levi & Wang (2018), Operations Research 66(6):1586-1602, https://dspace.mit.edu/handle/1721.1/125757 | B3 design |
| RLlib | not fetched | rejected on dependency weight, version not verified |

### Repo

- `docs/engineering/statistical-intervals.md`, `repo-conventions.md`,
  `code-quality-guidelines.md`
- `collaboration/reviews/20261124-orchestrator-review/00-review.md` (5.2,
  5.3, 5.5 V3)
- Projects 01, 02, 04, 08, 10
