# NLP Classification with Transformers

**Domain:** Deep learning NLP · **Data:** AG News (real, HuggingFace `fancyzhx/ag_news`) ·
**Status:** Working showcase

Fine-tuned DistilBERT vs. a TF-IDF + LogisticRegression baseline on news topic
classification — trained with a **hand-written PyTorch loop** (manual
warmup/decay LR schedule, per-epoch validation macro-F1, patience-1 early
stopping) on a bounded, stratified, seeded CPU-feasible subsample.

## Key results

Bounded test split: 1000 rows, stratified 250/class, seed 42.

| Run | Accuracy | F1 macro | F1 weighted |
|---|---|---|---|
| `baseline_tfidf_logreg` | 0.8720 | 0.8714 | 0.8714 |
| `distilbert_finetuned` | **0.9020** | **0.9021** | **0.9021** |

Fine-tuning beats the strong classical baseline by **+3.0 pp macro-F1** after 1
effective epoch (3600 train rows); the loop early-stopped at epoch 2 with
best val F1 0.8880. Full numbers: `projects/04-nlp-classification/reports/metrics.json`;
interactive figures: `reports/figures/` (confusion heatmap, per-class F1,
training curve — HTML + showcase-API JSON).

## Artifacts

- `projects/04-nlp-classification/README.md` — problem, results, reproduce
  commands, client takeaways
- `projects/04-nlp-classification/DESIGN.md` — requirements, options
  considered, bounded-data contract, pipeline diagram
- `projects/04-nlp-classification/reports/report.html` — standalone themed
  evaluation report (metrics JSON + interactive figures under `reports/`)

## Reproduce

```bash
uv run python -m nlp_classification.cli all   # ~4 min on CPU
```

Data bound: 4000 train / 1000 test, stratified, seeded — documented in
DESIGN.md; the full AG News corpus (120k rows) is intentionally not used.
