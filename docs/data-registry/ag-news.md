# AG News (Hugging Face)

- **Canonical source:** https://huggingface.co/datasets/fancyzhx/ag_news
- **License/terms:** Research purposes.
- **Used by:** Project 04 (NLP multi-class classification)
- **Size:** 127k news articles, 4 classes (World, Sports, Business, Sci/Tech).

## Snapshot policy

Loaded via the `datasets` library (HF Hub revision pinned by commit hash in
Project 04's prepare stage). No manual download.

| Field | Value |
|---|---|
| Snapshot date | 2026-10-12 |
| Format | HF datasets (parquet shards) |
| Split used | train (120k) / test (7.6k); a bounded subsample keeps laptop runs fast |

## Access

```bash
uv run python -m datasets.load_dataset fancyzhx/ag_news  # via Project 04 prepare stage
```
