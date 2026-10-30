# 04 · NLP Classification with Transformers

**Domain:** Deep learning NLP · **Data:** AG News (real, HuggingFace `fancyzhx/ag_news`) ·
**Status:** Working showcase

> News sorter for AG News' four topics: a language model trained on all 120k
> articles scores 95% macro-F1 on a fresh holdout, vs 88% for a keyword model
> 40x faster and free; routing doubtful items to it keeps that quality while
> 3 of 4 items ride at keyword cost. License unknown.
>
> Newsrooms, aggregators, and compliance teams routing a continuous stream of
> headlines need topic triage that keyword rules break on at the first
> unfamiliar wording. A full-data DistilBERT fine-tune on a laptop GPU
> reaches **0.9460 test macro-F1**, ~7.5 pp above the strong TF-IDF baseline.
>
> [Case study source and interactive figures on GitHub →](https://github.com/amm-ds/portfolio/tree/main/projects/04-nlp-classification)

Fine-tuned transformers vs. a TF-IDF + LogisticRegression baseline on news
topic classification — a hand-written PyTorch training loop, seeded Optuna
HPO, a second encoder candidate, audited model selection, and a full 120k
fine-tune on Apple-Silicon MPS.

## Key results

**Headline:** the full 120k fine-tune of DistilBERT on Apple-Silicon MPS
(laptop GPU, seed 42, 2 epochs, val macro-F1 0.9433 → 0.9464 during training)
reaches **0.9460 test macro-F1** on the same untouched 1,000-row stratified
test split as every other run, at ~18–27 min/epoch measured.

*How to read: every run is scored on the same untouched 1,000-row stratified
test split; rows are historical rungs of one scaling ladder, not separate
experiments; bold = headline.*

| Run | Accuracy | F1 macro |
|---|---|---|
| `naive_majority` | 0.2500 | 0.1000 |
| `random_uniform` | 0.2540 | 0.2533 |
| `baseline_tfidf_logreg` | 0.8720 | 0.8714 |
| `encoder_b` (roberta-base) | 0.8980 | 0.8982 |
| `distilbert` (bounded 3.6k) | 0.9020 | 0.9021 |
| `distilbert_tuned` (bounded 3.6k) | 0.9020 | 0.9021 |
| `distilbert_fulldata_20k` | 0.9270 | 0.9270 |
| `distilbert_full_120k` | **0.9460** | **0.9460** |

The older bounded numbers are historical rungs of one scaling ladder
(0.9021 → 0.9270 → 0.9460, +4.4 pp from bounded to full data). HPO improved
validation macro-F1 (0.8880 → 0.8953) but the gain sat inside seed noise
(mean 0.8910 ± 0.0042 over 3 seeds) and did not transfer to test — the
honesty rule kept the original artifact as `distilbert_tuned`.

**Controlled data-scale ladder — the bounded↔full confound is closed
(roadmap item, delivered).** `train-nn --full-data --subset N` trains seeded,
stratified rungs on one device with identical hypers; subset 4,000 reproduces
the bounded rows exactly, so the 3.6k rung exists as same-rows CPU/MPS twins
that separate the device component from the data component. Every rung is
scored on the shared 1,000-row test split and a disjoint 1,000-row fresh
holdout; per-rung wall-clock and device provenance live in
`reports/scale_meta_<N>.json`; figure `scale_ladder`.

| Train rows | Run | Device | Val F1 | Test macro-F1 | Fresh macro-F1 |
|---|---|---|---|---|---|
| 3.6k | `distilbert` (legacy bounded) | CPU | 0.8880 | 0.9021 | 0.8962 |
| 3.6k | `distilbert_scale_4000` | MPS | 0.8849 | 0.9019 | 0.9067 |
| 10.8k | `distilbert_scale_12000` | MPS | 0.9120 | 0.9170 | 0.9219 |
| 36k | `distilbert_scale_40000` | MPS | 0.9320 | 0.9331 | 0.9428 |
| 108k | `distilbert_full_120k` | MPS | 0.9464 | **0.9460** | 0.9529 |

- **Device component measured, not assumed:** the same-rows twins differ by
  0.0002 macro-F1 on the test split and 0.0105 on the fresh holdout — the
  bounded↔full gap is **not** a device artifact.
- **Data component measured:** at fixed device each 3× step buys +1.5 / +1.6 /
  +1.3 pp on the test split — a monotone, decelerating curve that reproduces
  on the fresh holdout (+1.5 / +2.1 / +1.0 pp). The legacy CPU 18k evidence
  run (0.9270) lands between the 10.8k and 36k rungs, as its size predicts.
- Rung wall-clock on this machine (batch 32, 2 epochs, shared-machine load):
  84 s / 292 s / 995 s for 3.6k / 10.8k / 36k.

**Serving economics** (probe-hardware numbers, not the headline — measured
on this machine, an Apple M4 Max, CPU, torch 2.14.1, 12 threads; batch=1
end-to-end, n=200 predictions per variant; cost at a declared $1/M-input +
$4/M-output rate card, ~51.5 in + ~3.5 out tokens per prediction; accuracy
from the committed test-split metrics, int8 measured on a 2000-row train
sample — single-machine probe figures, not production benchmarks):

| Variant | Size (MB) | p50 latency (ms) | Throughput (pred/s) | Cost ($/1k preds) | Accuracy | F1 macro |
|---|---|---|---|---|---|---|
| `tfidf_logreg` | 0.5 | 0.2 | 4477.8 | 0.0000 | 0.8720 | 0.8714 |
| `distilbert_tuned` fp32 (bounded) | 255.5 | 9.0 | 110.7 | 0.0656 | 0.9020 | 0.9021 |
| `distilbert_full_120k` fp32 | 255.5 | 8.7 | 112.5 | 0.0654 | 0.9460 | 0.9460 |
| `distilbert_full_120k` int8 (dynamic) | 132.3 | 13.2 | 77.6 | 0.0654 | 0.9635 | 0.9637 |

Dynamic int8 (`torch.quantization.quantize_dynamic`, qnnpack on arm64)
halves model size with no measured quality loss (sample macro-F1 0.9627 →
0.9637, Δ +0.0010) but is slower than fp32 at batch=1 on Apple Silicon —
quantization buys memory, not speed, here. Data:
`projects/04-nlp-classification/reports/latency_probe.json`.

![The full 120k DistilBERT fine-tune climbs to 0.946 macro-F1 on the test split within two epochs](../assets/projects/04-nlp-classification/training_curve.png){ width="100%" }

Two epochs is a measured budget, not an assumption: a 4-epoch probe with
early stopping disabled (same hypers, seed 42;
`projects/04-nlp-classification/reports/history_probe4.json`) peaks at val
macro-F1 0.9477 in epoch 3 — +0.0003 over epoch 2, −0.0003 by epoch 4 —
while validation loss climbs again and train loss keeps falling. Epochs 3-4
overfit rather than improve. Both history files are from the **full 120k
data**, not the bounded subsample: `history_fulldata.json` is the shipped
headline run (2 epochs, val macro-F1 0.9433 → 0.9464), `history_probe4.json`
is the 4-epoch probe of the same full-data fine-tune (early stopping
disabled) — read the probe as "extra epochs overfit", not as a better result.

![4-epoch probe: validation macro-F1 plateaus after epoch 2 while train loss keeps falling](../assets/projects/04-nlp-classification/epochs_probe.png){ width="100%" }

Temperature
scaling cuts test ECE 0.047 → 0.013 for free. The dominant confusion pair,
Business → Sci/Tech (24/250 → 15/250 → 14/250 across the curve), is a
labeling-ambiguity floor, not a data-scale problem. Representative
misclassifications of the selected model (`distilbert_tuned`, wave-2
artifact) on the untouched 1,000-row bounded test split — reproduced from
the committed artifact + test split, bit-matching `metrics.json`; full list
in `reports/misclassification_examples.json`:

| text snippet | true | predicted |
|---|---|---|
| "Amazon Snaps Up China's Largest Web Retailer (NewsFactor) … will buy Joyo.com Limited --…" | Business | Sci/Tech |
| "India's Tata makes powerful debut Shares in Indian software services giant Tata Consultancy close 16 higher…" | World | Business |
| "Dell Exits Low-End China Consumer PC Market HONG KONG (Reuters) - Dell Inc., the world's largest PC maker…" | Sci/Tech | Business |
| "U.S. Misses Cut in Olympic 100 Free ATHENS, Greece - Top American sprinters Jason Lezak and Ian Crocker…" | World | Sports |

Full ladder:
`projects/04-nlp-classification/reports/metrics.json`; decision record:
`reports/selection.json`; fresh-holdout reading: `reports/fresh_holdout.json`;
scale rungs: `reports/models/distilbert_scale_<N>.pt` +
`reports/history_scale_<N>.json` + `reports/scale_meta_<N>.json`;
interactive figures in `reports/figures/`.

![Business → Sci/Tech stays the dominant confusion pair at full data — a labeling-ambiguity floor, not a data-scale problem](../assets/projects/04-nlp-classification/confusion_matrix_selected.png){ width="100%" }

## Artifacts

- `projects/04-nlp-classification/README.md` — problem, run ladder, HPO and
  selection narrative, reproduce commands, client takeaways
- `projects/04-nlp-classification/DESIGN.md` — requirements, options
  considered, bounded-data contract, pipeline diagram, changelog
- `projects/04-nlp-classification/story.yaml` — 8-section case study served by
  the showcase API
- `projects/04-nlp-classification/reports/report.html` — standalone themed
  evaluation report

## Reproduce

```bash
uv run python -m nlp_classification.cli all   # prepare → baseline → train-nn → hpo → tuned → encoder-b → evaluate
```

Bounded data contract: 4,000 train / 1,000 test, stratified, seeded for the
CPU ladder — documented in DESIGN.md. The headline run uses the full AG News
train split (120k rows) via `train-nn --full-data` on an accelerator
(Apple-Silicon MPS on this machine). Dataset card:
[data-registry/ag-news](https://amm-ds.github.io/portfolio/data-registry/ag-news/).
