# Wikipedia (Hugging Face)

- **Canonical source:** https://huggingface.co/datasets/wikimedia/wikipedia
  (config `20231101.en`)
- **License/terms:** CC BY-SA / GFDL — **attribution required**. Articles
  retain their licenses; this portfolio uses a bounded topic subset for
  retrieval evaluation and carries this attribution in docs and the UI.
- **Used by:** Project 01 (RAG agent corpus)
- **Size:** 6.4M articles full config; the pipeline filters to a fixed topic
  list (bounded retrieval domain) and materializes a snapshot.

## Snapshot policy

The 20231101 dump config is immutable. The filtered corpus snapshot is
materialized by Project 01's `prepare_corpus` stage and tracked by DVC;
the filter (topic list, max articles per topic) is versioned code.

| Field | Value |
|---|---|
| Snapshot date | 2026-10-12 (corpus materialized from config 20231101.en) |
| Format | HF datasets → chunked JSONL |

## Access

Via Project 01's prepare stage (`datasets` library, revision pinned).
