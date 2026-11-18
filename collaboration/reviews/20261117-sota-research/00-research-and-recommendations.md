# Online research and recommendations, projects 01–13

Date: 2026-11-17
Reviewer: Claude Code
Method: web search (standard mode) on each project's dataset and method family, plus leaderboard and framework lookups. Search results were mostly secondary (blogs, aggregators, preprints). Where a primary paper or leaderboard number was not reached, this file says so.
Status: recommendations only. Nothing implemented. Owner runs execution.

## How to read the confidence labels

- **Source-backed**: the claim rests on a primary paper or official page that the search returned (link given).
- **Secondary**: the claim rests on a blog, aggregator, or preprint summary. Check the primary source before publishing.
- **Hypothesis**: a suggestion I did not verify against a result.

## Cross-cutting findings

1. **Anomaly scoring has moved on from NAB.** A 2026 adversarial stress test reports that NAB is the hardest of six benchmarks and that under best-of-N reporting several metrics become gameable (secondary; preprint, peer-review status not checked). The TSB-AD work recommends VUS-PR as the most reliable measure among those it examined (source-backed, NeurIPS 2024 "Elephant in the Room").
2. **Benchmark numbers on the same dataset are rarely comparable.** For Hillstrom, AG News, NYC taxi, and M5, the reported figures differ in split, horizon, metric, and preprocessing. Every project should cite its comparator's protocol, not only its number.
3. **Agent reliability is measured by pass^k, not pass@1.** τ-bench reports pass^k (the chance of succeeding on all k trials of a task) and shows strong degradation as k rises (source-backed, Sierra blog).
4. **Tabular deep learning is not a default win.** Grinsztajn et al. report that tree ensembles remain state of the art on medium tabular data (source-backed, arXiv 2207.08815). TabPFN v2 and 2.5 extend small-data foundation models to regression (source-backed, Nature 2025 and arXiv 2511.08667; independent eval arXiv 2502.17361).

## 01 · RAG agent

**What the search found**
- Survey on whether LLMs can be trusted to evaluate RAG (source-backed, arXiv 2504.20119). Judge reliability varies by domain.
- A TREC 2024 RAG agreement figure is reported in a secondary summary: GPT-4o agreed with human judges about 56% of the time from scratch and about 72% when humans post-edited (secondary; check the TREC paper).
- RAGAS faithfulness is reference-free, claim-level, and can return null on domains like finance (secondary).
- RAGAS had API churn around version 0.4.x (secondary).

**Recommendations**
1. (Hypothesis, high value) Add a reranker arm (for example a cross-encoder) and a hybrid BM25 + dense retriever. Report recall@k before generation for each. Rationale: current retrieval is compared only with a random floor.
2. (Source-backed method) Validate the judge against human labels on this corpus before trusting RAGAS or the rubric judge. Report human-judge agreement as a number on the card.
3. (Secondary) Pin the RAGAS version and note the 0.4.x API change in `metrics.json` `_meta`.
4. (Hypothesis) Report null rate for faithfulness, since null outcomes can hide failures.

## 02 · Demand forecasting (M5)

**What the search found**
- The M5 accuracy write-up (Makridakis et al., IJF 2022) is the primary results reference. It was not reached in search; check it directly.
- Anderer and Li (arXiv 2103.08250, source-backed) placed second in M5 with a top-down alignment of independent level forecasts, not optimal reconciliation. The paper argues this helps with many intermittent bottom-level series.
- Wellens et al. (IJF 2022, source-backed, ideas.repec.org) report that transfer learning on the store-level recursive LightGBM kept similar accuracy with about 25% less training time.
- Chronos (arXiv 2403.07815, source-backed) is zero-shot competitive with task-specific models on 42 datasets, but no M5 WRMSSE result was found.
- A 2026 benchmark paper argues TimesFM 2.5 can score a favorable MASE while missing spike structure, so standard metrics can mislead (source-backed, arXiv 2602.12147).

**Recommendations**
1. (High value, source-backed) Add a zero-shot foundation-model arm (Chronos and/or TimesFM) on the same 28-day origin. Report WRMSSE and a spike or intermittency metric beside it, since the TimesFM paper warns that MASE alone can mislead.
2. (Source-backed) Add top-down alignment (Anderer and Li) as a reconciliation alternative to the current reconciled LightGBM. Report it next to the ensemble.
3. (Source-backed) Report training time per arm. Transfer learning reduces cost at similar accuracy, which strengthens the case for the pooled variants.
4. (Hypothesis) Replace the "one scored origin" limit with a rolling origin set of at least three test origins if compute allows. Single-origin results are the weakest part of the claim.
5. Cite the M5 final leaderboard WRMSSE for context only after checking the M5 paper (not done here).

## 03 · Anomaly detection (NAB)

**What the search found**
- NAB original paper (arXiv 1510.03336, source-backed). **Verified against the official numenta/NAB README (v1.0 scoreboard, Standard profile):** Numenta HTM 70.5–69.7 (seed range), CAD OSE 69.9, ARTime 74.9, Twitter ADVec v1.0.0 47.1, Etsy Skyline 35.7, Random 11.0, Null 0.0, Perfect 100.0. Earlier aggregator figures (HTM 64.7, random 16.8) do not match the official table and must not be quoted.
- TSB-UAD is a univariate benchmark of 12,686 labelled series (source-backed, VLDB paper). Its successor TSB-AD recommends VUS-PR as the most reliable measure among those it analysed (source-backed, NeurIPS 2024).
- A 2026 adversarial preprint reports that point-adjust and best-of-N reporting make several metrics gameable on NAB (secondary; preprint).
- Point adjustment can favour noisy predictors (secondary, review of "Quo Vadis").

**Recommendations**
1. (High value, source-backed) Report VUS-PR (volume under the PR surface) alongside range-F1 and range-PR. It is the measure TSB-AD recommends, and it is less sensitive to window choice.
2. (Source-backed) Do not use point adjustment or best-of-N reporting. State the operating point is frozen on a separate split, as already done, and show results at fixed budgets, not only the best threshold.
3. (Hypothesis) Add an evaluation on TSB-AD's univariate suite so the result is comparable with other detectors on a shared protocol.
4. Keep the official NAB score out of the headline unless computed with the official scorer (the search did not confirm a 2024 NAB leaderboard).

## 04 · NLP classification (AG News)

**What the search found**
- AG News 4-class accuracy around 94–96% for strong fine-tuned transformers (secondary; aggregator entries of 95.58, 95.6, 95.68 with unverified setups).
- A 2026 preprint compares zero- and few-shot LLM prompting with fine-tuned encoders (DistilBERT and others) on AG News and three other benchmarks. It reports fine-tuned encoders are competitive and often superior at one to two orders of magnitude lower cost and latency (secondary, arXiv 2602.06370). Another study reports zero-shot LLMs lag fine-tuned BERT or RoBERTa, with the gap largest on fine-grained tasks.
- **Verified, SetFit Table 2 (arXiv 2209.11055, AG News), accuracy as printed:** FineTune (RoBERTa-Large) N=8 81.7 (std 3.8), N=64 88.4 (std 0.9), full data 93.8; SetFit_MPNet N=8 82.9 (std 2.8), N=64 88.0 (std 0.7); Adapet N=8 85.1, N=64 88.0; Perfect N=8 80.8, N=64 89.0. N is training examples per class. At N=8 SetFit_MPNet beats the fine-tuned RoBERTa-Large baseline by 1.2 points.

**Recommendations**
1. (High value) Add a SetFit arm at a few label budgets (for example 8, 32, 128 per class). It is the natural cheap baseline between TF-IDF and full fine-tuning.
2. (Source-backed) Compare the LLM cascade against a fine-tuned encoder with calibrated confidence rather than raw softmax, since τ depends on calibration. Report ECE beside the cascade.
3. (Source-backed claim) Include a zero-shot LLM arm on the same test split, so the cascade's cost gain is measured against the cheapest LLM-only option, not only the transformer.
4. The cascade-gain CI is already recommended in the 04 review handoff. This is the main statistical fix.

## 05 · ML pipeline churn (IBM Telco)

**What the search found**
- No churn-specific SOTA search was run in this pass. The recommendations here come from the general small-tabular results above.
- TabPFN v2 and 2.5 are small-data tabular foundation models; TabPFN v2 was described for datasets up to about 10k rows (secondary summary of the v2 paper; check the Nature paper).

**Recommendations**
1. (Hypothesis, high value) Add TabPFN as a challenger at the same frozen-threshold protocol. A 7,043-row dataset is within its stated small-data range.
2. (Source-backed general claim) Keep gradient-boosted trees as the main challenger, since Grinsztajn et al. find trees strong on medium-sized tabular data.
3. (Hypothesis) Report the decision curve (net benefit) alongside business cost, since it does not depend on the cost weights.
4. Repeat the cost-weight sensitivity across a range, not one weight pair (already in the 05 handoff).

## 06 · Routing optimization (VRPTW)

**What the search found**
- Kool et al. (ORTEC, source-backed, wouterkool.github.io) describe an HGS implementation for VRPTW built on HGS-CVRP. Their VRPTW version ranked first in Phase 1 of the 12th DIMACS challenge and reports new best-known solutions on the larger Gehring and Homberger instances.
- PyVRP (arXiv 2403.13795, source-backed) is an MIT-licensed HGS package that supports VRPTW, ranked first in the 2021 DIMACS VRPTW challenge and first on the static EURO Meets NeurIPS 2022 competition track. **Verified: its VRPTW benchmark uses the 1000-customer Homberger and Gehring instances, not Solomon 100-customer.** Table 2 (verbatim): PyVRP mean gap 0.40%, HGS-DIMACS 0.32%, DIMACS reference 0.29%, BKS 0.00%, on the 1000-customer set with a two-hour limit scaled by CPU speed. PyVRP improved 27 of the 300 best-known solutions on that set. No Solomon table exists in the paper, so the Solomon comparison in our 06 plan must be run, not quoted.
- SINTEF hosts the Solomon 100-customer best-known solutions (source-backed, sintef.no). Use it as the reference for gaps.
- Bent and Van Hentenryck's two-stage hybrid local search reported improving the published best on about 10 of 56 Solomon instances (secondary summary).

**Recommendations**
1. (High value, source-backed) Add PyVRP as the SOTA-practice comparator on the same 56 instances, using the SINTEF best-known values. This answers the "no SOTA comparator" gap in the 06 review directly.
2. (Source-backed) Keep the hierarchical objective (vehicles first, distance second). PyVRP and HGS both work on it, so the comparison is fair.
3. (Hypothesis) Investigate the +3.7 vehicle delta by testing whether a vehicle-minimising phase (as in HGS) closes it.
4. Report runtime per instance under a fixed time budget for each solver, since HGS results depend on budget.

## 07 · Open data mobility (NYC taxi)

**What the search found**
- No agreed SOTA MAE for NYC taxi zone demand was found. The task definitions vary widely (zone vs grid, horizon, years, pickup definition) (secondary).
- GSA-Forecaster (arXiv 2104.05914, source-backed) uses 471 Manhattan locations with graph sequence attention and weather as auxiliary input.
- Forecaster (arXiv 1909.04019, source-backed) uses 996 NYC hot locations with a Transformer-based design.
- Leaderboard MAE figures on aggregators (4.9, 9.78, 9.87) do not state horizon or split, so they cannot be quoted.

**Recommendations**
1. (High value, source-backed) Add a spatio-temporal graph baseline (GSA-Forecaster-style) on the same zones and holdout. The current GBM is compared with persistence only, which the 07 review already flags.
2. (Hypothesis) Add a seasonal model with weather covariates as a stronger classical baseline than same-hour-yesterday.
3. Keep validation-based selection as is (already correct).
4. Do not quote an external SOTA MAE unless the horizon, zone definition, and split match.

## 08 · LLM inference and serving

**What the search found**
- An arXiv study on Apple Silicon LLM inference at scale (arXiv 2601.19139, source-backed) and a late-2025 study of MLX, MLC-LLM, Ollama, llama.cpp, and PyTorch MPS (source-backed, reported in a summary): MLX reaches about 230 tokens per second in sustained decode, but lacks paged attention, so throughput degrades beyond about 32k context.
- MoE models show a much wider MLX advantage than dense models (secondary; one report of about 130 vs 43 tok/s for a 30B MoE on M4 Pro).
- MLX performs full prefill before the first token, so time-to-first-token grows linearly with input length (secondary).
- vllm-mlx reports 21–87% higher throughput than llama.cpp on M4 Max (author's own benchmark, treat with caution).
- Ollama's MLX backend roughly doubled decode speed in one reported release (secondary).

**Recommendations**
1. (High value, source-backed) Add a prompt-length sweep. The MLX prefill and context-degradation findings mean a single short-prompt benchmark can mislead for real workloads.
2. (Source-backed) Report TTFT and decode tok/s separately, not one aggregate. The prefill finding makes them diverge.
3. (Hypothesis) Test a concurrency arm with vllm-mlx or vllm-metal, since the search points to batching as the advantage of vLLM-style servers on Mac.
4. Report the MoE vs dense gap explicitly, since it is the largest effect in the sources.

## 09 · Agentic workflows

**What the search found**
- τ-bench (source-backed, Sierra blog): tasks use simulated users, programmatic APIs and domain policies. GPT-4o reached 61.2% on retail and 35.2% on airline at pass^1, and its pass^8 drops below 25% on retail.
- A third-party leaderboard lists several models near 60–70% pass^1, but the settings differ, so cross-row comparisons are unreliable (secondary).

**Recommendations**
1. (High value, source-backed) Report pass^k (for example k=4 or k=8) alongside pass^1 for the tuning and unseen suites. Reliability is the claim a workflow needs, and pass^1 hides its decay.
2. (Source-backed) Adopt a simulated user in the evaluation, as τ-bench does, rather than scripted inputs, if the workflow faces users.
3. The live confirmation remains the blocker. It is a paid run and needs separate owner approval.

## 10 · Uplift experimentation (Hillstrom)

**What the search found**
- Hillstrom (MineThatData) has 64,000 customers split across men's email, women's email, and control (source-backed in a paper's description; secondary).
- Qini is the standard comparison metric where ground-truth uplift is unavailable (source-backed, arXiv 2003.11940).
- A reinforcement-learning uplift paper reports Qini values on MineThatData (for example RLift 0.0656), but setups differ across papers (source-backed, arXiv 1811.10158; comparability not checked).
- A 2024 revenue uplift paper evaluates Hillstrom-Men and Hillstrom-Women splits with AUUC and AUQC against causal forests, T- and S-learners, and DragonNet (source-backed, arXiv 2405.15301).
- UpliftBench (arXiv 2604.06123, April 2026, preprint, source-backed) compares S-, T-, and X-learners with a causal forest on Criteo. It found the S-learner highest on Qini and attributes the causal forest's low score to subsample size. It uses Criteo, not Hillstrom.

**Recommendations**
1. (High value, source-backed) Report AUUC alongside Qini, and use the Men and Women splits from the 2024 revenue-uplift paper so the result can be compared with a published protocol.
2. (Source-backed) Add an S-learner arm. UpliftBench finds it competitive, and this repo's comparison omits it.
3. (Source-backed) Give the causal forest enough data before concluding anything about it. UpliftBench shows the ranking is confounded by sample size.
4. Keep the "mailing everyone wins at $0.01" finding, which is the most useful result here.

## 11 · Data engineering (DataFrame engines)

**What the search found**
- ClickBench (GitHub, source-backed) is the common analytics benchmark. DuckDB reported reaching #1 in October 2025 with its 1.4 LTS release (source-backed, duckdb.org).
- A QuestDB re-run of ClickBench reports DuckDB and Polars close on hot runs, and notes that ClickBench drives Polars as a long-lived Python session, which affects comparability (secondary).
- A critique notes that ClickBench gives almost no signal on multi-table joins (secondary).
- Polars publishes its own benchmark page (source-backed, pola.rs), and Coiled publishes TPC-H results for Spark, Dask, DuckDB, and Polars (source-backed, docs.coiled.io).
- A 2026 Uvik benchmark on 10M rows puts pandas far behind Polars and DuckDB on group-by (secondary).

**Recommendations**
1. (High value, source-backed) Add cold and hot run reporting, following ClickBench's split. The current median of warm runs hides cold-start cost.
2. (Source-backed) Add TPC-H queries, which include joins, since ClickBench is weak there. Coiled's TPC-H page is a reference.
3. (Source-backed) Note how each engine is driven. The Polars long-lived-session issue shows that process model changes the ranking.
4. (Hypothesis) Map the 10 tasks to ClickBench query numbers where they overlap, and say which tasks have no ClickBench equivalent.

## 12 · Tabular ML lifecycle (bike sharing)

**What the search found**
- Grinsztajn et al. (arXiv 2207.08815, source-backed, NeurIPS 2022 Datasets and Benchmarks): tree ensembles remain state of the art on medium tabular data (around 10k samples). They release a benchmark and tuning methodology that accounts for search cost.
- TabPFN v2 (Nature, January 2025, source-backed via model card and Hutter's announcement). An independent evaluation on over 300 datasets reports strong generalisation on small to medium tasks but some degradation (arXiv 2502.17361, source-backed). TabPFN-2.5 extends to up to 50,000 rows and 2,000 features (source-backed, arXiv 2511.08667).

**Recommendations**
1. (High value, source-backed, scope corrected) Add TabPFN v2 or 2.5 as a challenger. Correction: the bike dataset has 17,379 rows, which is above the 10,000-sample scope the Nature paper evaluates (v2). TabPFN-2.5 reports up to 50,000 rows (secondary, arXiv 2511.08667). So run v2.5, or run v2 on a documented subsample, and say which in the card.
2. (Source-backed) Use a tuning budget that accounts for search cost, as Grinsztajn et al. recommend, when comparing the MLP to LightGBM.
3. (Source-backed) The current evidence does not show the MLP beating LightGBM (0.2 MAE on validation). The honest claim is a tie, as the 12 review states.
4. Keep the seasonal-naive floor and the block-bootstrap sensitivity, which are already good practice.

## 13 · Model serving (ONNX, FastAPI)

**What the search found**
- No 2025 head-to-head CPU benchmark of ONNX Runtime, Triton, and TorchServe behind FastAPI was found (searched; results were GPU-focused or vendor pieces).
- A 2026 guide frames ONNX Runtime as an execution engine and Triton or vLLM as serving layers, so the comparison may be between different kinds of thing (secondary).
- A thesis on inference runtimes reports TorchServe best overall on its tests, but the hardware and year were not confirmed (secondary).
- One GPU article reports ONNX Runtime p95 of 14 ms on a T4, 22% below TorchServe (secondary; methodology not verified).

**Recommendations**
1. (High value, hypothesis-level) Compare like with like: ONNX Runtime inside the same FastAPI wrapper against ONNX Runtime inside Triton, not against a different engine. The search supports the framing point (secondary).
2. (Source-backed general practice) Report p95 and p99 with sample sizes, since the headline is p50 only.
3. (Hypothesis) Run one standard load generator on the top cell, as the 13 review suggests, and cite its version.
4. State on the card that no published CPU head-to-head was found for this stack, so the comparison here is the reference.

## Sources retrieved

- arXiv 2103.08250 — Anderer and Li, top-down alignment in M5 (https://arxiv.org/pdf/2103.08250)
- IJF 2022 Wellens et al. (https://ideas.repec.org/a/eee/intfor/v38y2022i4p1482-1491.html)
- Kool et al. HGS for VRPTW (https://wouterkool.github.io/pdf/paper-kool-hgs-vrptw.pdf)
- SINTEF Solomon 100-customer best-known solutions (https://sintef.no/projectweb/top/vrptw/100-customers)
- PyVRP arXiv 2403.13795 (https://arxiv.org/abs/2403.13795)
- arXiv 2504.20119 — survey of LLM judges for RAG (https://arxiv.org/pdf/2504.20119)
- arXiv 2602.06370 — zero- and few-shot LLMs vs fine-tuned encoders (https://arxiv.org/html/2602.06370)
- arXiv 2502.11830 — text classification in the LLM era (https://arxiv.org/html/2502.11830v1)
- arXiv 2003.11940 — causal classification, Qini on Hillstrom (https://arxiv.org/pdf/2003.11940)
- arXiv 1811.10158 — RL for uplift modeling (https://arxiv.org/pdf/1811.10158)
- arXiv 2405.15301 — revenue uplift with Hillstrom splits (https://arxiv.org/pdf/2405.15301)
- arXiv 2604.06123 — UpliftBench, Criteo (https://arxiv.org/abs/2604.06123)
- arXiv 2207.08815 — Grinsztajn et al., tree-based vs deep learning (https://arxiv.org/abs/2207.08815)
- arXiv 2502.17361 — independent TabPFN v2 evaluation (https://arxiv.org/pdf/2502.17361v1)
- arXiv 2511.08667 — TabPFN-2.5 (https://arxiv.org/pdf/2511.08667v2)
- arXiv 1510.03336 — NAB (https://arxiv.org/pdf/1510.03336)
- NeurIPS 2024 "Elephant in the Room" TSB-AD (https://nips.cc/virtual/2024/poster/97690)
- arXiv 2607.11969 — adversarial stress test of post-point-adjustment metrics, 2026 preprint (https://arxiv.org/pdf/2607.11969)
- ClickBench (https://github.com/ClickHouse/ClickBench/)
- DuckDB 1.4 LTS benchmark (https://duckdb.org/2025/10/09/benchmark-results-14-lts.html)
- Polars benchmarks (https://www.pola.rs/posts/benchmarks/)
- Coiled TPC-H comparison (https://docs.coiled.io/blog/tpch)
- arXiv 2601.19139 — LLM inference on Apple Silicon (https://arxiv.org/html/2601.19139v1)
- arXiv 2403.07815 — Chronos (https://arxiv.org/pdf/2403.07815v1.pdf)
- arXiv 2602.12147 — TimesFM benchmark critique (https://arxiv.org/html/2602.12147)
- arXiv 2104.05914 — GSA-Forecaster (https://arxiv.org/pdf/2104.05914)
- arXiv 1909.04019 — Forecaster (https://arxiv.org/pdf/1909.04019)
- τ-bench, Sierra (https://sierra.ai/blog/benchmarking-ai-agents)

## Not reached (check before publishing)

- **Verified citation, values still open:** M5 accuracy write-up, Makridakis, Spiliotis and Assimakopoulos, IJF 38(4): 1346–1364 (2022), DOI 10.1016/j.ijforecast.2021.11.013. Attempts to read the WRMSSE values of top entries failed: PMC returned a bot-check page, and the Lancaster discussion PDF refused the connection. A search found that the 1st-place Accuracy entry (In and Jung) used multiple direct and recursive LightGBM models (secondary, Packt/Medium summaries). The reconciliation step and the 0.52 score remain unconfirmed.
- **Verified, with a correction:** PyVRP's Solomon table does not exist; its VRPTW results are on 1000-customer Homberger and Gehring instances (see the 06 section above).
- **Verified, from the Transportation Science abstract:** Bent and Van Hentenryck (2004) improved 10 of 56 Solomon best-known solutions (17%) and matched or improved 46 (82%). An earlier 2001 tech report claimed 13 of 58; cite the 2004 journal version.
- **Verified, TabPFN Nature 637, 319–326 (2025), DOI 10.1038/s41586-024-08328-6, via Europe PMC full text:** the evaluation covers 28 regression datasets with up to 10,000 samples and 500 features. Metric is R² and negative RMSE, normalised per dataset (1.0 best, 0.0 worst). Verbatim: "For regression, TabPFN outperforms CatBoost in normalized RMSE by 0.051 (0.923 compared with 0.872) in the default setting and by 0.093 (0.968 compared with 0.875) in the tuned setting." "TabPFN (PHE) outperforms AutoGluon (allowed 4 h) after its minimal tuning budget of 300 s, a 48× speedup." Raw regression values sit in Extended Data Table 2, an image not readable in text. The paper states its scope limit: "scalability to larger datasets requires further study."
- **Verified, SetFit Table 2:** see the 04 section above.
- **Verified, NAB v1.0 scoreboard:** see the 03 section above.
- **Still open:** Hillstrom-specific Qini leaderboard under one protocol. Not searched in this pass.
