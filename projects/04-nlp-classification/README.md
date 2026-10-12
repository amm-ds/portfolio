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
seed 42. Every run below is scored on that identical split with the platform's
`classification_metrics` + weighted F1. Numbers in
[`reports/metrics.json`](reports/metrics.json).

| Run | Accuracy | F1 macro | F1 weighted |
|---|---|---|---|
| `naive_majority` | 0.2500 | 0.1000 | 0.1000 |
| `random_uniform` | 0.2540 | 0.2533 | 0.2533 |
| `baseline_tfidf_logreg` | 0.8720 | 0.8714 | 0.8714 |
| `distilbert_finetuned` | **0.9020** | **0.9021** | **0.9021** |

Macro-F1 deltas vs. the better naive floor (`random_uniform`): TF-IDF baseline
**+61.8 pp**, DistilBERT **+64.9 pp**; DistilBERT beats the TF-IDF baseline by
**+3.1 pp**. `naive_majority` looks deceptively good on accuracy (0.25 = chance
on a balanced test split) but collapses on macro-F1 (0.10) — exactly why the
portfolio scores runs with macro-F1, not accuracy.

Hand-written loop history (validation macro-F1 drives early stopping):

| Epoch | Train loss | Val loss | Val F1 macro | LR |
|---|---|---|---|---|
| 1 | 0.6933 | 0.3590 | **0.8880** | →2e-5 ramp |
| 2 | 0.2840 | 0.3525 | 0.8823 | decay → 0 |

Early stopping fired after epoch 2 (patience 1); best epoch-1 weights were
restored and saved to `reports/models/distilbert.pt`. Numbers in
[`reports/metrics.json`](reports/metrics.json).

**Takeaway:** on only 3600 training documents, fine-tuned DistilBERT beats the
strong TF-IDF + logistic-regression baseline by **+3.1 points macro-F1**
(0.9021 vs 0.8714), and both trained models tower ~62–65 points over the naive
floors. The classical baseline remains remarkably competitive — that trade-off
conversation is exactly what a client should hear.

**Why fine-tuning beats bag-of-words here.** TF-IDF + logistic regression sees
each headline as an unordered weighted word bag: it captures which *words*
predict a topic, but not word order, negation, or how words compose ("Apple
recalls laptops" vs "Apple pie recalls childhood"). DistilBERT's pre-trained
attention layers already encode syntax and topical semantics; fine-tuning only
re-points that representation at the four classes, so ~3.6k labeled rows are
enough to learn discriminations a 8k-feature sparse vector cannot express. The
confusion matrix shows the residual errors are mostly the genuinely ambiguous
Sci/Tech ↔ Business boundary.

**Honest limits.** These numbers come from a deliberately bounded showcase:
4k train / 1k test stratified subsample, 2 epochs, max_length 128, single
seed, CPU budget (~3.5 min of training). Expect the TF-IDF baseline to keep
gaining with data up to a ceiling in the low-90s, while the transformer has
substantial headroom left — with the full 120k rows and a GPU, published
full-data DistilBERT results reach ~0.93–0.94 macro-F1, so the +3.1 pp gap at
4k rows understates the asymptotic gap. Treat this project as the
cheap, reproducible lower bound of the scaling curve, not the ceiling.

Figures (interactive HTML + showcase-API JSON in `reports/figures/`):

- `eda_class_balance.{html,json}` — class distribution across splits + train text-length histogram
- `confusion_matrix_distilbert.{html,json}` — fine-tuned model, counts
- `per_class_f1_distilbert.{html,json}` — per-class F1 bars
- `training_curve.{html,json}` — train/val loss + val macro-F1 per epoch

Human-readable report: [`reports/report.html`](reports/report.html).

## Reproduce

```bash
# from the repository root, one stage at a time
uv run python -m nlp_classification.cli prepare        # ~6s (downloads AG News once)
uv run python -m nlp_classification.cli train-baseline # ~1s
uv run python -m nlp_classification.cli train-nn       # ~3.5 min on CPU
uv run python -m nlp_classification.cli evaluate       # ~10s

# or everything at once
uv run python -m nlp_classification.cli all            # ~4 min total

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

Planned deepening, in priority order:

- **Optuna HPO** (declared in `portfolio.yaml` techniques): search LR, warmup
  ratio, and TF-IDF `min_df`/`max_features` with cross-validation, tracked as
  first-class runs in the platform's `RunResult` comparison.
- **Real-data track:** scale the bound from 4k → full 120k rows behind a GPU
  flag, keeping the bounded CPU track as the default reproducible path.
- **Error analysis slice:** per-class confidence calibration and a
  misclassified-examples table fed into the report.
