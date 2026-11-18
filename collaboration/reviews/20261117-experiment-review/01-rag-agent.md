# 01 · RAG agent: technical review

## Verdict
Strong evaluation discipline and an honest failure budget. Generation grounding, not retrieval, is the limit, and the copy already says so. Not unattended-ready, as stated.

## Architecture
- Retrieval is provider-independent (recall@5 0.831 vs 0.031 random floor). Good separation of retrieval and generation so each can be measured.
- Judge stack mixes a rubric judge and RAGAS. Two judges is a sound check; the disagreement should be reported, not averaged away.
- Selected provider is hosted `kimi-for-coding`. Generation depends on a single external endpoint, which is a deployment risk the card should name.

## Results vs benchmarks and SOTA
- Comparison is against the incumbent provider and the random floor. Both are fair.
- Missing: a reference RAG pipeline on the same corpus (e.g. a standard BM25 + reranker baseline) to show the retrieval side beats common practice, not just random.
- RAGAS faithfulness 0.7337 [0.656, 0.813] is a usable number; cite the RAGAS version and judge model next to it (verify the version pinned in `uv.lock`).

## Metrics and statistics
- Answer-relevancy regression (0.8775 → 0.8602) is kept in the headline. Good.
- Sealed held-out set has 55 questions. Interval width on n=55 is wide; say so on the card.
- Stress re-run 0.733 with CI [0.567, 0.867] on 30 questions: the CI is wider than the claimed improvement over the tuning set. Do not present it as a gain.
- Unsupported outcomes "11 → 5" is a count on 30 items; present as counts with the denominator.

## Code and tests
- 23 test files. Confirm the failure taxonomy classifier has direct tests against labelled examples.

## Visuals
- `failure_taxonomy` and `retrieval_funnel` are the right figures for the claim. Check the figure states n on the axis.

## Copy and articles
- short_version is accurate. It states "Not unattended-ready", which matches the README.
- The README is 278 lines; the headline table repeats numbers from metrics. Confirm each against `reports/metrics.json`.

## Kimi refinement tasks
1. (major) Add a BM25 + reranker reference arm on the same corpus and report it beside the selected retriever.
2. (major) Put the judge model and RAGAS version on the card and in `reports/metrics.json`.
3. (minor) Present the 30-question stress result as counts with denominators, and state the CI width is not a gain.
4. (minor) Add n to every figure axis label that shows a rate.
