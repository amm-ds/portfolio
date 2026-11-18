# Hillstrom Qini leaderboard search — findings (owner decision 13)

Date: 2026-11-19 (overnight queue, item 17)
Executor: Kimi Code
Protocol adopted for this search (one protocol): the portfolio's own —
Hillstrom **Mens E-Mail vs No E-Mail two-arm frame, conversion outcome,
out-of-fold Qini coefficient** (area between the ranked incremental-conversions
curve and the random line, `qini.py` convention). The question: does any public
source report Hillstrom Qini/AUUC numbers comparable under this protocol?

## Finding

**No public Hillstrom Qini leaderboard exists under one protocol.** Published
Hillstrom evaluations each use their own frame, outcome, and curve convention;
none reports the Mens-vs-control × conversion × out-of-fold Qini coefficient
directly. What exists:

1. **Hu, de Haan & Skiera (2024), "Uplift modeling with quasi-loss-functions",
   Data Mining and Knowledge Discovery 38:2495–2519**
   ([publisher PDF via Groningen](https://pure.rug.nl/ws/files/1088016559/s10618-024-01042-x.pdf)).
   The most rigorous recent Hillstrom comparison found: 14 uplift models
   (S/T/X/R meta-learners, causal/uplift trees/CTS, and four proposed UpliftQL
   variants) evaluated on **100 bootstrapped Hillstrom samples**, ranked by
   **AUUC average rank** (Table 10). Four of the top five AUUC models are
   UpliftQL variants. Protocol: bootstrap-resampled ranking, not a single
   held-out Qini coefficient; outcome/frame details differ from the portfolio's
   two-arm conversion frame.

2. **Diemert, Betlei, Renaudin & Amini (KDD 2018), "A Large Scale Benchmark for
   Uplift Modeling"** — the canonical uplift benchmark, but its large-scale
   table is **Criteo**, not Hillstrom ([benchmark PDF](https://bitlater.github.io/files/large-scale-benchmark_comAH.pdf),
   [2026 preprint re-analysis](https://arxiv.org/html/2604.06123v1)). The
   2026 UpliftBench line extends this with a "living leaderboard" and reports
   the methodological caution that **Qini shows no detectable alignment with
   effect accuracy** ([UpliftBench, arXiv 2608.00915](https://arxiv.org/html/2608.00915v1)).

3. **Original Hillstrom challenge write-up (Stochastic Solutions)** — the
   winning solution was selected on Qini curves over the campaign's own
   evaluation frame ([HillstromChallenge.pdf](https://www.stochasticsolutions.com/pdf/HillstromChallenge.pdf));
   pre-registration-style, but no model-by-model coefficient table under a
   reusable protocol.

4. Secondary reproductions (e.g.
   [uplift-modeling-hillstrom](https://github.com/nadhifspaer/uplift-modeling-hillstrom),
   [QiniDeep](https://www.researchgate.net/publication/391275528_QiniDeep_-Deep_Neural_Uplift_Modeling))
   report per-arm Qini curves or synthetic-first validations; protocols vary
   (visit vs conversion, any-campaign vs single-arm).

## Implication for project 10's card

The card's Qini numbers (T-learner 12.03, response model 13.01, X-learner 5.90
— incremental conversions at the 25% budget on the out-of-fold two-arm frame)
cannot be placed on a public leaderboard because **no public Hillstrom number
shares the protocol**. The honest card statement is: "published Hillstrom
evaluations use heterogeneous frames and metrics (bootstrap AUUC ranks, per-arm
Qini curves, visit vs conversion); under this project's fixed two-arm
conversion protocol the ladder is internally paired-bootstrapped; a public
one-protocol comparison does not exist as of 2026-11." This satisfies decision
13 (search run, one protocol stated, result reported) without claiming a
 ranking the evidence does not support.

## Sources

- [Uplift modeling with quasi-loss-functions (DMKD 2024)](https://pure.rug.nl/ws/files/1088016559/s10618-024-01042-x.pdf)
- [UpliftBench: living leaderboard + Qini caveat (arXiv 2608.00915)](https://arxiv.org/html/2608.00915v1)
- [Meta-learner comparison re-analysis (arXiv 2604.06123)](https://arxiv.org/html/2604.06123v1)
- [A Large Scale Benchmark for Uplift Modeling (KDD 2018 PDF)](https://bitlater.github.io/files/large-scale-benchmark_comAH.pdf)
- [Hillstrom challenge winning solution (Stochastic Solutions)](https://www.stochasticsolutions.com/pdf/HillstromChallenge.pdf)
