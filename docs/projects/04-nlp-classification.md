# 04 · NLP Classification with Transformers

**Domain:** Deep learning NLP · **Data:** AG News (real, HuggingFace `fancyzhx/ag_news`) ·
**Status:** Working showcase

> Newsrooms, aggregators, and compliance teams routing a continuous stream of
> headlines need topic triage that keyword rules break on at the first
> unfamiliar wording. A full-data DistilBERT fine-tune on a laptop GPU
> reaches **0.9460 test macro-F1**, ~7.5 pp above the strong TF-IDF baseline.
>
> [Interactive case study with figures →](https://github.com/amm-ds/portfolio/tree/main/projects/04-nlp-classification)

Fine-tuned transformers vs. a TF-IDF + LogisticRegression baseline on news topic
classification — with a hand-written PyTorch training loop, an Optuna HPO stage
(seeded TPE, median pruning), a second encoder candidate, and audited model
selection, plus a full 120k fine-tune on Apple-Silicon MPS.

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
validation macro-F1 (0.8880 → 0.8953) but gains sat inside seed noise
(mean 0.8910 ± 0.0042 over 3 seeds) and did not transfer to test — the
honesty rule kept the original artifact as `distilbert_tuned`. Temperature
scaling cuts test ECE 0.047 → 0.013 for free. The dominant confusion pair,
Business → Sci/Tech (24/250 → 15/250 → 14/250 across the curve), is a
labeling-ambiguity floor, not a data-scale problem. Full ladder:
`projects/04-nlp-classification/reports/metrics.json`; decision record:
`reports/selection.json`; interactive figures in `reports/figures/`.

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
