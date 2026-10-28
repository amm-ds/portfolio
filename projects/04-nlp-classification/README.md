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

## Results (real runs, this machine — CPU ladder, full-data run on Apple MPS)

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
| 7 | `distilbert_full_120k` | **0.9460** | **0.9460** | full 120k fine-tune on Apple-Silicon MPS |

Macro-F1 ladder vs. the better naive floor (`random_uniform`): TF-IDF **+61.8
pp**, encoder_b **+64.5 pp**, bounded DistilBERT family **+64.9 pp**, full-data
DistilBERT **+69.3 pp**. DistilBERT beats
the TF-IDF baseline by **+3.1 pp** and its roberta-base challenger by **+0.4
pp** — inside test noise (±1.9 pp), so read the two encoders as tied at this
data scale. `naive_majority` looks deceptively good on accuracy (0.25 =
chance on a balanced test split) but collapses on macro-F1 (0.10) — exactly
why the portfolio scores runs with macro-F1, not accuracy.

### Serving economics (probe-hardware numbers, not the headline)

Measured, not estimated — this machine (Apple M4 Max, torch 2.14.1, CPU
with 12 torch threads), batch=1 end-to-end serving (tokenize + forward for
the transformers, vectorize + predict for sklearn), n=200 held-out test
rows per variant, p50 per prediction. These are single-machine probe
figures for a routing decision, not production benchmarks; other hardware
moves the milliseconds, not the ordering conclusions. Model size: artifact
bytes for the
sklearn pipeline, serialized `state_dict` for torch. Accuracy/F1 for the
first three rows are the committed 1000-row test-split numbers (no
re-evaluation); the int8 row's quality is measured on a 2000-row train
sample (fp32 on the same sample: macro-F1 0.9627 → int8 0.9637, Δ +0.0010 —
no drop). Cost is cloud-equivalent at a declared rate card ($1 / 1M input
tokens, $4 / 1M output tokens) with measured token counts (~51.5 input +
~3.5 output tokens per prediction; classification output ≈ the tokenized
class name). Full data: [`reports/latency_probe.json`](reports/latency_probe.json),
reproduce with `uv run python -m nlp_classification.latency_probe --n 200`.

| Variant | Size (MB) | p50 latency (ms) | Throughput (pred/s) | Cost ($/1k preds) | Accuracy | F1 macro |
|---|---|---|---|---|---|---|
| `tfidf_logreg` | 0.5 | 0.2 | 4477.8 | 0.0000 | 0.8720 | 0.8714 |
| `distilbert_tuned` fp32 (bounded) | 255.5 | 9.0 | 110.7 | 0.0656 | 0.9020 | 0.9021 |
| `distilbert_full_120k` fp32 | 255.5 | 8.7 | 112.5 | 0.0654 | 0.9460 | 0.9460 |
| `distilbert_full_120k` int8 (dynamic) | 132.3 | 13.2 | 77.6 | 0.0654 | 0.9635 | 0.9637 |

Read the table as a routing decision: TF-IDF is ~40x faster and free of
token-metered cost, at −7.4 pp macro-F1; the full DistilBERT buys that back
for ~$0.065 per 1k items at ~110 pred/s on a laptop CPU. Dynamic int8
(`torch.quantization.quantize_dynamic`, qnnpack on arm64) halves model size
with zero measured quality loss but is **slower** here (13.2 vs 8.7 ms
p50) — on Apple Silicon the int8 kernels lose to fp32 Accelerate at
batch=1, so quantization buys memory and transfer, not speed.

### Full-data path (GPU-track roadmap item — delivered on MPS)

`train-nn --full-data` runs the real scaling route: the full 120k AG News
train split (108k train / 12k val after the same stratified carve-out), gated
behind an accelerator. `--device auto|mps|cpu` picks the device (default
`auto`: CUDA → Apple MPS → CPU; the bounded showcase stays CPU-first). On
machines with no accelerator the full-data path errors with an honest
wall-clock estimate (~45–50 min/epoch on this CPU) unless `--force-cpu` /
`--device cpu` is passed; `--subset N` gives bounded evidence runs.

**The full run** (this machine, Apple Silicon MPS, torch 2.14.1, batch 32 —
verified by an up-front memory probe at 256 MiB allocated — seed 42, 2
epochs, val macro-F1 0.9433 → **0.9464**): **0.9460 test macro-F1** on the
untouched 1000-row split, **+4.4 pp over the 3.6k-row models**. Honest
measured wall-clock: **27.5 min for epoch 1 (1651 s), 18.0 min for epoch 2
(1079 s)** — the training loop totalled ~46 min, the whole command ~47 min
end-to-end — versus the ~50 s / 3.6k-row CPU epoch this path is gated on
(full 120k ≈ 45–50 min/epoch on CPU, ~1.5–2 h for 2 epochs). Epoch 1 ran
while other jobs shared this machine; steady state is ~18 min/epoch, and
epoch-to-epoch variance tracks machine load, not GPU thermal drift. MPS
quirks documented: the libomp-dependent classical stack (lightgbm, xgboost)
and torch MPS coexist in one process here (the workspace libomp repair
holds), MPS has no OOM recovery so the batch is probed with a synthetic
forward+backward before training, and single-process tokenization of the
120k split is CPU-bound (~10 s — batched HF tokenizer, not a bottleneck).

**Why two epochs?** Because the third and fourth are measured to buy nothing.
A probe re-ran the full fine-tune with the budget raised to 4 epochs and
early stopping disabled (`uv run python -m nlp_classification.epochs_probe`,
same hypers, seed 42, ~13 min/epoch with the machine quieter than during the
headline run): val macro-F1 goes 0.9407 → 0.9474 → **0.9477** → 0.9471 —
epochs 3-4 add **+0.0003 / −0.0003** over epoch 2, inside run-to-run noise,
while val loss rises again (0.1566 → 0.1609 → 0.1774) and train loss keeps
falling (0.1425 → 0.0959 → 0.0634): textbook overfitting onset, ~27 extra
minutes for no quality. (Probe epochs 1-2 don't bit-match the shipped run —
the LR schedule depends on the total step count.) Both histories come from
the **full 120k data**, not the bounded subsample: `reports/history_fulldata.json`
is the shipped headline run (2 epochs, early stopping enabled, val macro-F1
0.9433 → 0.9464); `reports/history_probe4.json` is this 4-epoch probe of the
same full-data fine-tune. Read the probe as "extra epochs overfit", not as
a better headline — its peak 0.9477 vs the shipped 0.9464 is the validation
split under a different LR schedule, inside run-to-run noise. Figure:
`reports/figures/epochs_probe.*`.

Scaling story (all on the same untouched 1000-row test split, seed 42):

| Train rows | Run | Test macro-F1 | Δ vs 3.6k |
|---|---|---|---|
| 3.6k | `distilbert` / `distilbert_tuned` | 0.9021 | — |
| 18k | `distilbert_fulldata_20k` (evidence) | 0.9270 | +2.5 pp |
| 108k | `distilbert_full_120k` | **0.9460** | +4.4 pp |

The dominant confusion pair is **stable across the whole curve**:
Business → Sci/Tech, 24/250 at 3.6k → 15/250 at 20k → 14/250 at 120k — the
same hybrid technology-business headlines (e.g. *"Amazon Snaps Up China's
Largest Web Retailer…"*) still trip the model, just nearly half as often.
That residual is a labeling-ambiguity floor, not a data-scale problem — the
multi-label extension in the roadmap is the honest answer.

Classifier serving economics — size, latency, throughput, and token cost —
are measured in the [Serving economics](#serving-economics) table above;
LLM-serving stacks (llama.cpp vs MLX on Apple Silicon) are benchmarked in
[08 · LLM Inference & Serving](../08-inference-serving/README.md).

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
**Business → Sci/Tech (24 of 250 Business rows)**; the full-data model shows
the **same pair (14 of 250)** — e.g. *"Amazon Snaps Up China's Largest Web
Retailer…"* and *"PeopleSoft customers reassured…"* — stories about
technology companies that are legitimately business news. The pair is stable
across the scaling curve (24 → 15 → 14 of 250); only its frequency shrinks
with data. Full table in [`reports/error_analysis.md`](reports/error_analysis.md);
per-class comparison vs the TF-IDF baseline in
`reports/figures/per_class_f1_comparison.*`.

**Misclassified examples** — selected model (`distilbert_tuned`, wave-2
artifact per `reports/selection.json`) on the untouched 1,000-row bounded
test split; reproduced by running the committed artifact on the committed
test split — the reproduced predictions bit-match `reports/metrics.json`
(accuracy 0.9020, macro-F1 0.9020969724519001). Full list with all 8
examples and per-pair confusion counts:
[`reports/misclassification_examples.json`](reports/misclassification_examples.json).

| text snippet | true | predicted |
|---|---|---|
| "Amazon Snaps Up China's Largest Web Retailer (NewsFactor) NewsFactor - Amazon.com (Nasdaq: AMZN) has said it will buy Joyo.com Limited --…" | Business | Sci/Tech |
| "India's Tata makes powerful debut Shares in Indian software services giant Tata Consultancy close 16 higher on their market debut, raisi…" | World | Business |
| "Dell Exits Low-End China Consumer PC Market HONG KONG (Reuters) - Dell Inc. &lt;DELL.O&gt;, the world's largest PC maker, said on Monda…" | Sci/Tech | Business |
| "Future Doctors, Crossing Borders Students at the Mount Sinai School of Medicine learn that diet and culture shape health in East Harlem." | World | Sci/Tech |
| "U.S. Misses Cut in Olympic 100 Free ATHENS, Greece - Top American sprinters Jason Lezak and Ian Crocker missed the cut in the Olympic 100…" | World | Sports |
| "103 arrests for Internet fraud, related crimes since June: US (AFP) AFP - US authorities arrested at least 103 suspects and filed 117 cri…" | Sci/Tech | World |

**Why fine-tuning beats bag-of-words here.** TF-IDF + logistic regression sees
each headline as an unordered weighted word bag: it captures which *words*
predict a topic, but not word order, negation, or how words compose. DistilBERT's
pre-trained attention layers already encode syntax and topical semantics;
fine-tuning only re-points that representation at the four classes, so ~3.6k
labeled rows are enough to learn discriminations an 8k-feature sparse vector
cannot express.

**Honest limits.** Deliberately bounded showcase at the core: 4k train / 1k
test stratified subsample for the bounded ladder, ≤4 epochs, max_length 128.
The HPO studies (12-trial main + 3×6 seed variance) are small-budget
demonstrations — at 400 validation rows, hyperparameter rankings and
seed-to-seed variance carry more noise than the gains being chased, as both
the val→test regression and the seed study show. What is *not* noise: the
scaling curve (0.9021 → 0.9270 → 0.9460 test macro-F1 at 3.6k / 18k / 108k
train rows) and the calibration result (−71 % ECE). The full-data fine-tune
was trained on Apple Silicon MPS — a second-class citizen compared to CUDA
(see the quirks above), and its measured ~18 min/epoch steady-state
wall-clock is machine-specific.
Treat the bounded numbers as the cheap, reproducible lower bound of the
scaling curve — the full run confirms the published ~0.93–0.95 headroom is
real and reachable on a laptop GPU.

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

# full-data path (accelerator-gated; auto = CUDA → MPS → CPU):
uv run python -m nlp_classification.cli train-nn --full-data            # full 120k on MPS (~47 min measured)
uv run python -m nlp_classification.cli evaluate                        # seven-run ladder + selection + calibration

# bounded evidence run on CPU:
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

- **Full-dataset fine-tune — delivered:** the 120k AG News corpus trained
  through `train-nn --full-data` on Apple Silicon MPS (see above): 0.9460
  test macro-F1, +4.4 pp over the bounded models, ~18 min/epoch steady-state
  on MPS (27.5 min for epoch 1 under shared machine load; ~46 min training
  loop, ~47 min for the whole command).
- **Cost-sensitive routing** on top of the calibrated probabilities
  (temperature scaling already cuts ECE by 71 %; per-class thresholds for
  imbalanced production mixes remain to be tuned).
- **Multi-label extension** for hybrid Business/Sci-Tech articles — the
  dominant observed error mode — deferred deliberately: it is a different
  problem contract (multi-hot labels, different metrics), not a tuning knob.
