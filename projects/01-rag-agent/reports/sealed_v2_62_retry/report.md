# G4 sealed-v2 held-out retry pass — 33-question continuation (final)

Date: 2026-11-20
Continuation of Amendment 2 under the owner's "proceed with higher cap,
finish finally" (2026-11-20): the 33 still-unfetched questions of the 62
(indices 27–35, 37–42, 44–61), on the same code and model
(kimi-for-coding), into `reports/sealed_v2_62_retry/` alongside the
health-check evidence. Stop $2.50 (hard $3.00); metered spend **$1.316928**.

This run followed two aborted attempts, recorded in the collaboration
report: a 34-retry that tripped the ledger on its first question ($0.362940,
index 26's giant prompt again) and a $1.50 continuation that processed all 33
but died on the final tail call ($1.500479) with the CLI's write-at-end
leaving no artifacts. This re-run is the committed record for the 33.

## Results (one run, 33 traces)

- Verdicts: correct 26, unsupported-claim 6, empty-answer 1. **Zero
  format-failures, zero budget-terminated.**
- All 33 traces carry answer text; 21 carry claim text (verify reports
  present on answered, non-abstained rows).
- Abstention: refusal accuracy **1.0** (12/12 unanswerable); false
  abstention 0.0476 (1/21, empty answer); cite-when-expected 0.9524.
- Unsupported-claim rate (same definitions as the 58 run): **6/33 = 0.1818**,
  Wilson 95% [0.0866, 0.3413] over all 33; over answerable-only (21):
  **6/21 = 0.2857** [0.1378, 0.4838].
- Quality (RAG block): faithfulness 0.531, answer relevance 0.5548, context
  recall 1.0 (n=21 answered).
- Latency: p50 22.53 s, p95 87.00 s.

## Combined 62 view (combined, retry for failed items only)

- 28 real outcomes from the first pass (indices 0–25, 36, 43) + index 26
  from the retry health check + these 33 = **all 62 questions with real
  outcomes; questions still failing: 0.**
- Combined verdicts: correct 46, unsupported-claim 13, empty-answer 3.
- Combined unsupported: **13/62 = 0.2097** [0.1268, 0.3264] over all 62;
  **13/44 = 0.2955** [0.1816, 0.4422] over answerable-only.
- Combined false abstention: 3/44 = 0.0682 [0.0235, 0.1823].
- Budget-terminated rows by index: none in the 62-file (the 58-file's two
  remain indices 23 and 35, listed separately in the pooled metrics).

## Pooled 120

`reports/sealed_v2_120_pooled/metrics.json` is recomputed **without** the
validity warning (Amendment 2's condition is met — no question is still a
provider failure): unsupported **28/120 = 0.2333** [0.1667, 0.3166] over all
questions; **28/92 = 0.3043** [0.2197, 0.4046] over answerable-only; false
abstention 7/92 = 0.0761 [0.0373, 0.1488]; budget-terminated 2 (58-file
indices 23, 35), listed separately.

## Spend accounting (all kimi-for-coding, cloud-equivalent)

- 58-run: $1.034388 (prior, on `apps-rag-pass`)
- G4 pass 1 (62): $0.526214
- Retry authority: health check $0.517896 + aborted 34-retry $0.362940 +
  aborted continuation $1.500479 + this final run $1.316928 = $3.698243
- **G4 total: $4.224457; with the 58-run: $5.258845.**
  The four-attempt path is a property of three pathological ~0.4–0.55 MB-
  prompt questions and the CLI's write-at-end abort behavior, recorded in
  the collaboration report; the first-pass cap ($1.30/$1.20) and Amendment 2
  ($0.80/$0.70) were both structurally under-sized for this subset, and the
  Amendment-2 hard cap was overshot once by the meter's post-pricing jump.
