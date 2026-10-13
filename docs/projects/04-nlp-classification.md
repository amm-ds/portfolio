# NLP Classification with Transformers

**Domain:** Deep learning NLP · **Data:** AG News (real, HuggingFace `fancyzhx/ag_news`) ·
**Status:** Working showcase

Fine-tuned transformers vs. a TF-IDF + LogisticRegression baseline on news topic
classification — with a hand-written PyTorch training loop, an Optuna HPO stage
(seeded TPE, median pruning), a second encoder candidate, and honest model
selection, all on a bounded, stratified, seeded CPU-feasible subsample.

## Key results

All runs on the same untouched 1,000-row stratified test split (CPU, seed 42):

| Run | Accuracy | F1 macro |
|---|---|---|
| `naive_majority` | 0.2500 | 0.1000 |
| `random_uniform` | 0.2540 | 0.2533 |
| `baseline_tfidf_logreg` | 0.8720 | 0.8714 |
| `encoder_b` (roberta-base) | 0.8980 | 0.8982 |
| `distilbert` | 0.9020 | 0.9021 |
| `distilbert_tuned` | 0.9020 | 0.9021 |
| `distilbert_fulldata_20k` | **0.9270** | **0.9270** |

Encoders beat the strong classical baseline by ~+3 pp macro-F1 at 3.6k rows;
the GPU-gated `--full-data` path (20k-row evidence run) adds +2.5 pp more.
HPO improved validation macro-F1 (0.8880 → 0.8953) but gains sat inside seed
noise (mean 0.8910 ± 0.0042 over 3 seeds) and did not transfer to test — the
honesty rule kept the wave-2 artifact as `distilbert_tuned`. Temperature
scaling cuts test ECE 0.047 → 0.013 for free. Full ladder:
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

Data bound: 4,000 train / 1,000 test, stratified, seeded — documented in
DESIGN.md; the full AG News corpus (120k rows) is intentionally not used.
