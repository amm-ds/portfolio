# R3 sealed-v2 58 report

Date: 2026-11-19
Handoff: `collaboration/designs/20261119-r3-sealed-v2-58/03-implementation-handoff.md`
Branch: `apps-rag-pass-2026-11-19` (continued; upstream push). No merge, no
deploy. No copy, card, or headline changed.

## Commits and hashes

- Subset commit: **`4af0699`** — `feat(01): R3 58-question subset of
  sealed-v2, fixed and hashed before any run`. Subset sha256
  **`266d2ef3e5d26176d6b22ade3464984fba48ce89e297ce670c4c0b554420fb17`**
  (manifest `data/golden_sealed_v2_58.sha256.json`; parent
  `616973ba390f…ce54e2` embedded and verified before writing). Parent
  `data/golden_sealed_v2.json` (120 questions) and its manifest were **not
  changed** (verified again after the run).
- Run commit: **`557ad6b`** — results under `reports/sealed_v2/`.

## The run

One pass: `uv run python -m rag_agent.cli evaluate --heldout
--heldout-file data/golden_sealed_v2_58.json --reports-dir reports/sealed_v2`
(exit 0). Verify-on, kimi-for-coding only, no `--ragas`, no
`--max-questions`. Per-run ledger capped at $2.09 for the process so the
combined total could not cross $2.50. Not re-run.

## Spend

- Run: **$1.0344** cloud-equivalent (meter, `metrics.json → detail.heldout.meter`).
- R2 (recorded): $0.394369. **Cumulative: $1.4288 < $2.50** ✓.

## Results (58 questions = 36 single_hop / 12 multi_hop / 10 unanswerable)

- 48 answerable, 10 unanswerable. Refusal accuracy **1.0** (10/10);
  false abstentions **4** (empty answers; false_abstention_rate 0.0833 of
  answerable); 2 answers budget-terminated by per-answer limits — the spend
  cap was never hit.
- **Unsupported-claim rate 15/58 = 0.2586, Wilson 95% [0.1635, 0.3838]**
  (same computation as `reports/error_budget/metrics.json`).
- Faithfulness 0.6207 · answer relevance 0.6054 · context recall 1.0;
  latency p50 17.09 s, p95 116.90 s.

## Gates (actual output)

- `uv run pytest -q projects/01-rag-agent` → exit 0.
- `ruff check` → All checks passed! (no source changed this round; format
  check n/a — only data/report/gitignore files).
- `mypy` on `projects/01-rag-agent/src` + `scripts` → Success, 30 files.
- `check_headline_numbers.py` → 11 claims checked, 0 findings (OK).
- `check_docs.py` → check-docs: OK.

## Note on scope

This is a **58-question subset, not the full 120**. Halving the set widens
the Wilson interval by roughly √2; the unsupported rate 0.2586 [0.1635,
0.3838] is a subset measurement and should not be quoted as the sealed-v2
set's final number. The remaining 62 questions stay available for a future
owner-approved run.
