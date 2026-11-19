# R3 sealed-v2 pass — 58-question subset

Date: 2026-11-19
Handoff: `collaboration/designs/20261119-r3-sealed-v2-58/03-implementation-handoff.md`
Subset: `data/golden_sealed_v2_58.json` — zero-based even indices 0, 2, …,
114 of the committed 120-question sealed-v2 set (sha256
`266d2ef3e5d26176d6b22ade3464984fba48ce89e297ce670c4c0b554420fb17`,
manifest `data/golden_sealed_v2_58.sha256.json`; parent sha256
`616973ba390fdc1f8c9bf0b53fcf8e1b9bd24f5e93b563184bbc2ca9f8ce54e2`
unchanged). Mix: 36 single_hop / 12 multi_hop / 10 unanswerable.

This is **58 of the 120 questions, not the full set**. Halving the set
roughly widens Wilson intervals by ~1.4× versus the full set; treat the
numbers below as a subset measurement, not a replacement for the 120-question
read.

## Results (one run, `uv run python -m rag_agent.cli evaluate --heldout
--heldout-file data/golden_sealed_v2_58.json --reports-dir reports/sealed_v2`)

- n = 58 traces: 48 answerable, 10 unanswerable.
- Abstentions: refusal accuracy **1.0** (10/10 designed-to-fail abstained);
  false abstentions **4** (empty answers, false_abstention_rate 0.0833 of
  answerable); 2 answers budget-terminated by the run's per-answer limits
  (the spend cap was not hit).
- Unsupported-claim rate: **15/58 = 0.2586**, Wilson 95%
  **[0.1635, 0.3838]** (same computation as `reports/error_budget`).
- Quality reads: faithfulness 0.6207, answer relevance 0.6054, context
  recall 1.0 (from the run's RAG block, committed in `metrics.json`).
- Latency: p50 17.09 s, p95 116.90 s per answer pass.

## Spend

- This run: **$1.0344** cloud-equivalent (kimi-for-coding reference card;
  the membership key is not billed).
- Cumulative with R2 (`reports/warrant_check/metrics.json`, $0.394369):
  **$1.4288** — under the $2.50 combined stop throughout.

## Artifacts

- `metrics.json` — the run's full detail (composition, retrieval, RAG,
  faithfulness, taxonomy, abstention, verify blocks + meter).
- `question_traces_heldout.json` — 58 per-question traces (same evidence
  role as the other committed trace files).
- This file. New files only; no committed record, card, or copy changed.
