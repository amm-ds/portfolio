# 04 · NLP Multi-class Classification with Transformers

**Status:** working showcase on the standard portfolio platform
(flagship projects are [01](../01-rag-agent/README.md) and [07](../07-open-data-mobility/README.md)).
**Domain:** Deep learning NLP · **Data:** AG News (real, HuggingFace `fancyzhx/ag_news`)

## Problem

Classify short news headlines + descriptions into four categories (World, Sports,
Business, Sci/Tech). The engineering question is not "can a transformer do this"
— it is **how much a fine-tuned DistilBERT actually buys you over a strong
classical baseline, on the same bounded data, trained with code you can read
line by line** on a laptop CPU.

## Design summary

Two approaches are trained on the **same seeded, stratified subsample** and
scored on the same bounded test split:

| Approach | Model | Trainable params | Why |
|---|---|---|---|
| Baseline | TF-IDF (word 1–2 grams, 8000 features) + LogisticRegression | ~32k | The honest bar any deep model must clear |
| Fine-tune | `distilbert-base-uncased` + fresh classification head, **hand-written PyTorch loop** | ~67M | The showcase: no `Trainer`, no callbacks |

The hand-written loop implements everything the frameworks usually hide:
AdamW, a **linear warmup + linear decay LR schedule written by hand**
(`lr_at_step`), per-epoch train/val loss and validation macro-F1, and early
stopping with patience 1 that restores the best `state_dict`.

**Bounded data contract:** full AG News is 120k train rows — far beyond a CPU
showcase. We download the real dataset once and draw a seeded
(`numpy.random.RandomState`), per-class stratified subsample:
**4000 train (3600 train / 400 val after a stratified carve-out) / 1000 test**.
That bound keeps the whole pipeline under ~15 minutes on CPU and is documented
in [`DESIGN.md`](DESIGN.md).

Data quality gates (`portfolio_core.dq`): zero empty texts, labels within
`[0, 3]` — checked per split, persisted to `data/dq_*.md`, enforced with
`raise_if_failed()`. The prepared snapshot carries a `DatasetContract`
(name, source, license, snapshot date, sha256, row count).

See [DESIGN.md](DESIGN.md) for requirements, options considered, and the
pipeline diagram.

## Results (real run, this machine, CPU only)

Bounded test split: **1000 rows**, perfectly stratified (250 per class),
seed 42. Every run below is scored on that identical, untouched split with the
platform's `classification_metrics` + weighted F1. Full numbers in
[`reports/metrics.json`](reports/metrics.json).

| # | Run | Accuracy | F1 macro | What it is |
|---|---|---|---|---|
| 1 | `naive_majority` | 0.2500 | 0.1000 | most frequent training class, always |
| 2 | `random_uniform` | 0.2540 | 0.2533 | seeded uniform chance floor |
| 3 | `baseline_tfidf_logreg` | 0.8720 | 0.8714 | TF-IDF (1–2g, 8k) + LogisticRegression |
| 4 | `encoder_b` | 0.8980 | 0.8982 | roberta-base, default hypers, 2 epochs |
| 5 | `distilbert` | **0.9020** | **0.9021** | DistilBERT, wave-2 default hypers |
| 6 | `distilbert_tuned` | **0.9020** | **0.9021** | selection winner (see below) |
| 7 | `distilbert_fulldata_20k` | **0.9270** | **0.9270** | full-data path evidence: 20k-row subset |

Macro-F1 ladder vs. the better naive floor (`random_uniform`): TF-IDF **+61.8
pp**, encoder_b **+64.5 pp**, DistilBERT family **+64.9 pp**. DistilBERT beats
the TF-IDF baseline by **+3.1 pp** and its roberta-base challenger by **+0.4
pp** — inside test noise (±1.9 pp), so read the two encoders as tied at this
data scale. `naive_majority` looks deceptively good on accuracy (0.25 =
chance on a balanced test split) but collapses on macro-F1 (0.10) — exactly
why the portfolio scores runs with macro-F1, not accuracy.

### Full-data path (GPU-track roadmap item)

`train-nn --full-data` implements the real scaling route: it loads the full
120k AG News train split (or a `--subset N` seeded stratified slice), gates on
GPU availability — on CPU it errors with an honest wall-clock estimate
(measured ~50 s / 3.6k-row epoch → full 120k ≈ 45–50 min/epoch, ~1.5–2 h for
2 epochs) unless `--force-cpu` is passed. **Evidence run** (same flag
machinery, bounded): `train-nn --full-data --subset 20000 --force-cpu` —
18k train / 2k val, 2 epochs, ~22 min on CPU — reached **val F1 0.9189** and
**0.9270 test macro-F1**, +2.5 pp over the 3.6k-row models. Scaling to 18k
rows already approaches published full-corpus numbers; the remaining step to
120k is compute, not engineering.

### HPO — and the honest part

Optuna searched the hand-written loop's hypers (seeded TPE sampler, median
pruning between epochs, 12 trials; lr log 1e-5…5e-5, warmup 0…0.2, weight
decay 0…0.1, epochs 2…4; batch fixed at 32). Validation macro-F1 improved
from **0.8880** (defaults) to **0.8953** (best trial: lr 3.82e-5, warmup
0.042, wd 0.018, 2 epochs; 2/12 trials pruned). The tuned model reproduces
its trial's validation score bit-for-bit when retrained (`reports/hpo_study.json`).

But validation gains did not transfer: on the untouched test split the
HPO-retrained model scored **0.9011** macro-F1 vs the wave-2 artifact's
**0.9021**. Per the project's honesty rule, the reported `distilbert_tuned`
run is therefore the **wave-2 artifact** (decision persisted in
[`reports/selection.json`](reports/selection.json), margin +0.0010 — i.e.
noise). Lesson: at 1k test rows, a +0.7 pp validation improvement is inside
sampling noise; HPO here is a *process* demonstration, not a guaranteed win.

**Seed variance — is the HPO gain even real?** The `hpo-seeds` stage re-ran
the study under 3 fixed sampler seeds (6 trials each, epochs 2–3 budget):
best val macro-F1 0.8953 (seed 42), 0.8852 (seed 43), 0.8926 (seed 44) —
**mean 0.8910 ± 0.0042**. Against 0.8880 for defaults, the mean HPO gain is
~+0.3 pp, i.e. **smaller than the seed standard deviation**: at 400 validation
rows, run-to-run HPO variance exceeds the effect being chased. (Seed 42's best
matches the 12-trial study bit-for-bit — same RNG stream, determinism
re-confirmed.) Full data in `reports/hpo_seeds.json` and
`metrics.json → _meta.hpo_seeds`.

**Calibration.** Temperature scaling fitted on the 400-row validation split
(T = 0.843 — the fine-tuned model is mildly *under*-confident) cuts test ECE
from **0.0467 to 0.0133** (−71 % relative). Predictions are unchanged (argmax
is temperature-invariant), so calibration is a free reliability upgrade for any
confidence-thresholded routing; numbers in `metrics.json → _meta.calibration`.

Hand-written loop history for the default run (validation macro-F1 drives
early stopping):

| Epoch | Train loss | Val loss | Val F1 macro | LR |
|---|---|---|---|---|
| 1 | 0.6933 | 0.3590 | **0.8880** | →2e-5 ramp |
| 2 | 0.2840 | 0.3525 | 0.8823 | decay → 0 |

Early stopping fired after epoch 2 (patience 1); best epoch-1 weights were
restored and saved to `reports/models/distilbert.pt`.

**Error analysis.** The dominant confusion of the selected model is
**Business → Sci/Tech (24 of 250 Business rows)**, e.g. *"Amazon Snaps Up
China's Largest Web Retailer…"* and *"PeopleSoft customers reassured…"* —
stories about technology companies that are legitimately business news. Full
table in [`reports/error_analysis.md`](reports/error_analysis.md); per-class
comparison vs the TF-IDF baseline in `reports/figures/per_class_f1_comparison.*`.

**Why fine-tuning beats bag-of-words here.** TF-IDF + logistic regression sees
each headline as an unordered weighted word bag: it captures which *words*
predict a topic, but not word order, negation, or how words compose. DistilBERT's
pre-trained attention layers already encode syntax and topical semantics;
fine-tuning only re-points that representation at the four classes, so ~3.6k
labeled rows are enough to learn discriminations an 8k-feature sparse vector
cannot express.

**Honest limits.** Deliberately bounded showcase: 4k train / 1k test stratified
subsample, ≤4 epochs, max_length 128, CPU budget. The HPO studies (12-trial
main + 3×6 seed variance) are small-budget demonstrations — at 400 validation
rows, hyperparameter rankings and seed-to-seed variance carry more noise than
the gains being chased, as both the val→test regression and the seed study
show. What is *not* noise: the 20k-row evidence run (+2.5 pp test macro-F1
over 3.6k) shows data scaling works as published, and the TF-IDF baseline will
plateau in the low 90s while encoders keep gaining toward ~0.93–0.94 at full
data. Treat the bounded numbers as the cheap, reproducible lower bound of the
scaling curve, not the ceiling.

Figures (interactive HTML + showcase-API JSON in `reports/figures/`):

- `eda_class_balance.{html,json}` — class distribution across splits + train text-length histogram
- `hpo_history.{html,json}` — per-trial validation macro-F1 + best-so-far
- `hpo_importance.{html,json}` — fANOVA parameter importance over the study
- `training_curve.{html,json}` — train/val loss + val macro-F1 per epoch
- `confusion_matrix_selected.{html,json}` — selected model, counts
- `per_class_f1_comparison.{html,json}` — selected model vs TF-IDF baseline, per class

Human-readable report: [`reports/report.html`](reports/report.html).

## Reproduce

```bash
# from the repository root, one stage at a time
uv run python -m nlp_classification.cli prepare          # ~6s (downloads AG News once)
uv run python -m nlp_classification.cli train-baseline   # ~1s
uv run python -m nlp_classification.cli train-nn         # ~3 min on CPU
uv run python -m nlp_classification.cli hpo              # 12-trial study, median pruning
uv run python -m nlp_classification.cli hpo-seeds          # 3-seed variance study (~1 h CPU)
uv run python -m nlp_classification.cli train-tuned      # retrains with HPO best params
uv run python -m nlp_classification.cli train-encoder-b  # roberta-base candidate
uv run python -m nlp_classification.cli evaluate         # seven-run ladder + selection + calibration

# full-data path (GPU-gated; bounded evidence run on CPU):
uv run python -m nlp_classification.cli train-nn --full-data --subset 20000 --force-cpu

# or everything at once
uv run python -m nlp_classification.cli all

# or via DVC
dvc repro projects/04-nlp-classification
```

Tests run fully offline (synthetic in-memory fixtures, mocked loader/tokenizer):

```bash
uv run pytest projects/04-nlp-classification -q
```

## What this demonstrates for a client

- **Honest benchmarking culture:** every deep-learning claim is anchored to a
  tuned classical baseline on identical, quality-gated data.
- **Deep learning without black boxes:** the training loop, LR schedule, and
  early-stopping logic are hand-written and unit-tested (loss decreases on
  random data; schedule warmup/decay endpoints asserted exactly).
- **Bounded, reproducible data contracts:** real data, stratified subsampling,
  sha256-pinned snapshot metadata, DQ gates that halt the pipeline loudly.
- **CPU-first engineering:** the full pipeline fits in a coffee break, so
  experiments stay cheap and reviewable before anyone rents a GPU.
- **Production-shaped reporting:** platform-standard metrics JSON, themed
  plotly figures, and an HTML report a stakeholder can open anywhere.

## Roadmap

Final forward intent — everything below is ready to execute against the
existing pipeline:

- **Full-dataset fine-tune** on the 120k AG News corpus via the proven
  `train-nn --full-data` path (GPU-gated; the 20k evidence run already
  demonstrates +2.5 pp test macro-F1).
- **Cost-sensitive routing** on top of the calibrated probabilities
  (temperature scaling already cuts ECE by 71 %; per-class thresholds for
  imbalanced production mixes remain to be tuned).
- **Multi-label extension** for hybrid Business/Sci-Tech articles — the
  dominant observed error mode — deferred deliberately: it is a different
  problem contract (multi-hot labels, different metrics), not a tuning knob.
