# G4 sealed-v2 held-out pass — 62-question complement

Date: 2026-11-20
Handoff: `collaboration/designs/20261120-rag-g4-heldout/03-implementation-handoff.md`
(amendment: trace carries answer + claim text)
Subset: `data/golden_sealed_v2_62.json` — complement of the 58 within the
committed 120-question sealed-v2 set, original order (sha256
`a57355f5d853bd86512d2fec816a950fd25a15aee1e540d414871f0c4836b4f0`; parent
sha256 `616973ba390fdc1f8c9bf0b53fcf8e1b9bd24f5e93b563184bbc2ca9f8ce54e2`
unchanged). Mix: 32 single_hop / 12 multi_hop / 18 unanswerable (44
answerable).

Invocation (same CLI form as the 58 run, only the two paths changed):

    uv run python -m rag_agent.cli evaluate --heldout \
      --heldout-file data/golden_sealed_v2_62.json \
      --reports-dir reports/sealed_v2_62

Code: `g4-heldout-62-2026-11-20` @ `f83556c` (includes the G4 trace
amendment `f43e2c9`). Backend: env:kimi-for-coding; ledger budget $1.20;
metered spend **$0.526214 cloud-equivalent** — the stop and hard caps were
not reached.

## Provider failure dominates this run — read before citing

The kimi-for-coding endpoint returned HTTP 500 for most of the second half
of the run (first failure at trace index 26; only indices 36 and 43
succeeded after that). 34 of 62 traces are `format-failure` (33
`ModelHTTPError 500`, 1 request timeout); 28 of 62 questions produced real
outcomes. The numbers below describe those 28 answered rows plus the
failure artifacts, exactly as committed — they are **not** a clean 62-question
configuration measurement.

## Results (as committed; one run)

- n = 62 traces: 44 answerable, 18 unanswerable; **34 format-failure
  (provider 500s/timeout), not configuration signal.**
- Verdicts on answered rows: correct 19, unsupported-claim 7, empty-answer
  2. No budget-terminated rows (indices: none; the 58 run's two were
  indices 23 and 35).
- Unsupported-claim rate: **7/62 = 0.1129**, Wilson 95% [0.0558, 0.2152]
  over all questions; over answerable-only (44): **7/44 = 0.1591**
  [0.0793, 0.2937].
- Abstention: refusal accuracy 0.2778 (5/18 — depressed because 500-failures
  consumed unanswerable rows); false abstention 0.0455 (2/44, empty answers).
- Quality reads (RAG block, answered rows): faithfulness 0.59, answer
  relevance 0.6265, context recall 1.0.
- Latency: p50 10.03 s, p95 132.33 s.

## Trace amendment verified

`question_traces_heldout.json` carries `answer` on the 28 answered rows and
`claims` (`{claim, evidence_span, label, state}`) on the 23 rows with verify
reports — the Phase 1 audit material the 58 run could not provide. Failure
rows carry the pre-amendment schema exactly (no `answer`/`claims` keys).

## Pooled with the 58 run

See `reports/sealed_v2_120_pooled/metrics.json`. Mechanical pool (as the
handoff specifies): unsupported 22/120 = 0.1833 [0.1243, 0.2620] over all
questions (22/92 = 0.2391 over answerable); false abstention 6/92 = 0.0652
[0.0302, 0.1351]; budget-terminated 2 (58-file indices 23, 35), listed
separately. **Validity warning recorded in that file: the pool is dominated
by the 62-run's provider-failure artifacts and is not a valid 120-question
configuration measurement.**
