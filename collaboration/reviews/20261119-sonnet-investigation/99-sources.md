# Sources

Labels: **SB** = source-backed (page fetched and read, through the fetch tool, which summarises long pages); **SEC** = secondary (search snippet, abstract surfaced by search, blog, aggregator); **GAP** = no source found (listed at the end). All searches ran in standard mode on the session date 2026-11-18. Aggregator pages (benchmarklist.com, sotaverified.org, emergentmind.com, papers aggregators) are pointers only and carry no SOTA claim here.

| ID | URL | Label | Claim it supports |
|---|---|---|---|
| S01 | https://arxiv.org/abs/2605.28044 | SB | ForceBench: 198 contrastive pairs, five force axes; aggregate MVR 47.2% generic vs 24.5% warrant prompting; token/entity overlap 32.8-36.4%; single locality-filtered set |
| S02 | https://arxiv.org/html/2403.13795v2 | SB | PyVRP: VRPTW Table 2 (1000-customer Homberger and Gehring) PyVRP 0.40% / HGS-DIMACS 0.32% / DIMACS ref 0.29% mean gap; CVRP Table 1 PyVRP 0.22% / HGS-2012 0.21% / HGS-CVRP 0.11% (gap of mean 0.27 / 0.28 / 0.16) |
| S03 | https://arxiv.org/abs/2406.12045 | SB | tau-bench introduces pass^k; gpt-4o-class under 50% task success; pass^8 under 25% in retail |
| S04 | https://huggingface.co/Prior-Labs/tabpfn_2_5 | SB | TabPFN-2.5 weights under tabpfn-2.5-license-v1.1: research and limited internal evaluation allowed; no commercial or production use of model, derivatives or outputs |
| S05 | https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents | SB | pass@k vs pass^k; multiple trials; code, model, human graders; read transcripts; capability vs regression evals |
| S06 | https://github.com/TheDatumOrg/TSB-AD | SB | TSB-AD: 1,070 series, 40 datasets, 40 algorithms; VUS-PR recommended; Apache-2.0 code; leaderboard accepts PRs |
| S07 | https://arxiv.org/abs/2511.08667 | SB | TabPFN-2.5: up to 50,000 points and 2,000 features; leads TabArena; distillation to MLP or trees (licence text not on that page) |
| S08 | https://arxiv.org/pdf/2309.15217 | SEC | RAGAS faithfulness as supported-statement fraction; WikiEval validation |
| S09 | https://arxiv.org/pdf/2411.15594 | SEC | LLM-as-a-judge survey; kappa and correlation as agreement measures; kappa 0.6 convention (heuristic) |
| S10 | https://arxiv.org/html/2606.00093v1 | SEC | Agreement metrics for judge evaluation; kappa adds information; metric choices often unstated |
| S11 | https://econpapers.repec.org/RePEc:eee:intfor:v:38:y:2022:i:4:p:1346-1364 | SEC | M5 accuracy results paper (IJF 38(4)); 42,840 series; winning submission LightGBM-based |
| S12 | https://pure.unic.ac.cy/en/publications/the-m5-uncertainty-competition-results-findings-and-conclusions/ | SEC | M5 uncertainty track; scaled pinball loss; nine quantiles |
| S13 | https://arxiv.org/html/2411.13479v3 | SEC | Conformal prediction for hierarchical data: reconciliation inside split conformal; regression setting, no M5 experiment |
| S14 | https://nixtlaverse.nixtla.io/hierarchicalforecast/examples/probabilistic-reconciliation-comparison.html | SEC | Conformal method in HierarchicalForecast; default in-sample calibration; marginal coverage |
| S15 | https://proceedings.neurips.cc/paper_files/paper/2024/file/c3f3c690b7a99fba16d0efd35cb83b2c-Paper-Datasets_and_Benchmarks_Track.pdf | SEC | TSB-AD NeurIPS 2024 paper (PDF fetched but unreadable by the tool; claims from search snippet) |
| S16 | https://arxiv.org/abs/2109.05257 | SEC | Point adjustment inflates anomaly scores; random score can look state of the art |
| S17 | https://arxiv.org/abs/2502.13318 | SEC | VUS accuracy measures for time-series anomaly detection |
| S18 | https://arxiv.org/abs/2607.11969 | SEC | Lyu 2026 stress test: VUS-ROC gamed on 119 series where VUS-PR is not; VUS-PR gamed on NAB (id and claims from a search answer; paper not opened) |
| S19 | https://arxiv.org/html/2502.09054v2 | SEC | Cost-saving LLM cascades with early abstention; AUARC; deferral rule limits |
| S20 | https://arxiv.org/pdf/2407.01032 | SEC | AURC weakness and AUGRC proposal (association of this URL with the claim inferred from the search result list) |
| S21 | https://arxiv.org/pdf/2610.00118 | SEC | Telco churn audit: isotonic strongest default across 15 seeds; cost-optimal threshold 5-10x below F1-optimal; savings depend on assumed costs |
| S22 | https://arxiv.org/pdf/2507.08860v2 | SEC | e-Profits profit-based evaluation on IBM Telco reorders rankings |
| S23 | https://arxiv.org/pdf/2510.22016 | SEC | Cost-sensitive evaluation for binary classifiers |
| S24 | https://arxiv.org/html/2504.13961v2 | SEC | CONTINA adaptive conformal intervals for taxi and bike demand |
| S25 | https://arxiv.org/abs/2106.00170 | SEC | Adaptive conformal inference under distribution shift |
| S26 | https://aeaweb.org/conference/2018/preliminary/paper/eF2rFtsd | SEC | Rain as instrument for NYC taxi/Uber demand; validity and weak-instrument caution (preliminary paper) |
| S27 | https://fairlearn.org/main/user_guide/assessment | SEC | MetricFrame, selection rate, demographic parity and equalized odds metrics |
| S28 | https://arxiv.org/pdf/2607.03999 | SEC | Hillstrom Qini: honest forest 0.0346, causal forest 0.0214, T-learner 0.0192; 36 runs; large SDs |
| S29 | https://arxiv.org/pdf/2608.00915 | SEC | UpliftBench: AUUC variants differ; Qini and AUUC can rank differently |
| S30 | https://arxiv.org/pdf/2604.06123 | SEC | Criteo benchmark: S-learner Qini 0.3759; causal forest 0.2524 on 10% subsample |
| S31 | https://arxiv.org/pdf/1702.02896v5 | SEC | Athey and Wager efficient policy learning with doubly robust scores |
| S32 | https://www.arxiv-vanity.com/papers/1810.04778/ | SEC | Zhou, Athey, Wager: offline multi-action policy learning under budget |
| S33 | https://arxiv.org/pdf/1905.05389.pdf | SEC | Hahn et al.: area under prescriptive effect curve across budgets |
| S34 | https://arxiv.org/pdf/2609.30273 | SEC | 2026 paper: off-policy evaluation vs Qini/AUUC ranking for uplift |
| S35 | https://arxiv.org/pdf/2506.16791 | SEC | TabArena: GBTs strong; foundation models best on small data; ensembling helps |
| S36 | https://github.com/ClickHouse/ClickBench/issues/656 | SEC | ClickBench cold vs lukewarm runs; disputes over hot/cold labelling (issue seen through mirror snippets) |
| S37 | https://questdb.com/blog/lies-damn-lies-and-database-benchmarks | SEC | Competitor critique: result caching, fragile rankings (vendor blog) |
| S38 | https://duckdb.org/docs/current/guides/performance/benchmarks | SEC | DuckDB guidance on fair benchmarking; latest version; TPC-derived not official |
| S39 | https://ibis-project.org/posts/ibis-bench/ | SEC | Ibis bench: TPC-H derivative; Polars LazyFrames without streaming |
| S40 | https://docs.coiled.io/blog/tpch | SEC | Winner depends on scale and hardware |
| S41 | https://www.cncf.io/blog/2026/07/20/why-goodput-matters-more-than-throughput-for-llm-serving/ | SEC | Goodput and SLO-based serving metrics; TTFT, TPOT |
| S42 | https://arxiv.org/pdf/2608.28667 | SEC | GreenBench: Apple Silicon energy per token with package power and assumed 10 W system |
| S43 | https://arxiv.org/pdf/2603.23640 | SEC | Energy per token = average power x decode time / decode tokens |
| S44 | https://arxiv.org/pdf/2409.11055v3 | SEC | 4-bit quantization quality depends on model size (title not verified; association inferred from result list) |
| S45 | https://pytorch.org/docs/stable/_modules/torch/onnx/verification | SEC | PyTorch ONNX verification defaults rtol 1e-3, atol 1e-7 (from snippet) |
| S46 | https://artillery.io/blog/load-testing-workload-models | SEC | Open vs closed workload models |
| S47 | https://dev.to/speed_engineer/coordinated-omission-why-your-load-testing-tool-is-lying-about-your-p99-4p7k | SEC | Coordinated omission under-reports tails; vendor test p95 67 ms vs about 1 s (single vendor, as described in a different search summary) |
| S48 | https://arxiv.org/pdf/2305.14627 | SEC | ALCE citation recall and precision; 85.1% / 77.6% agreement with humans; 49% of ELI5 generations lacked complete support |
| S49 | https://arxiv.org/html/2412.07626v2 | SEC | OmniDocBench: 981 pages, 9 types; text edit distance, TEDS, reading order |
| S50 | https://arxiv.org/pdf/2506.07982 | SEC | tau2-bench dual-control telecom domain; 34-49% success (ICML summary) |
| S51 | https://ai.pydantic.dev/evals/evaluators/overview | SEC | pydantic-evals LLMJudge and deterministic evaluators |
| S52 | https://arxiv.org/html/2404.10774v2 | SEC | MiniCheck: 770M fact-checker; GPT-4-level claim on LLM-AggreFact at far lower cost |
| S53 | https://arxiv.org/pdf/2107.07002 | SEC | The Benchmark Lottery: benchmark and test-set reuse issues |
| S54 | https://papers.nips.cc/paper/9117-a-meta-analysis-of-overfitting-in-machine-learning | SEC | Kaggle meta-analysis of test-set reuse overfitting |
| S56 | https://tianpan.co/blog/2026-04-09-production-retrieval-stack-hybrid-search-reranking | SEC | Practitioner blog: hybrid BM25+dense+reranker default (low quality; no primary numbers) |
| S57 | https://search.r-project.org/CRAN/refmans/forecast/html/tsCV.html | SEC | Rolling-origin time-series cross-validation (Hyndman) |
| S58 | https://sintef.no/projectweb/top/vrptw/homberger-benchmark | SEC | SINTEF Gehring-Homberger benchmark: hierarchical objective, double precision, rounding, comparability caveat |
| S59 | https://sintef.no/projectweb/top/vrptw/1000-customers | SEC | SINTEF 1000-customer best-known table (numeric rows not read) |
| S60 | https://huggingface.co/ArmanXAI/bert-base-agnews-news-classifier | SEC | Community BERT card 94.74% (pointer only; not SOTA) |
| S60b | https://asrjetsjournal.org/American_Scientific_Journal/article/view/12048 | SEC | 2025 study: fine-tuned BERT beats zero-shot LLMs on AG News by about 10-25 points (numbers unverified) |
| S62 | https://arxiv.org/pdf/2602.06370 | SEC | Cost-aware classification comparison; inherited from the 2026-11-19 gap analysis, not re-opened here |
| S63 | https://findingspress.org/article/157499-probabilistic-bike-sharing-demand-forecasting-under-changing-weather-and-seasonal-regimes-with-transformer-based-models | SEC | 2026 forward-chaining probabilistic bike demand study on UCI hourly |
| S64 | https://ndjstn.github.io/posts/bike-sharing-timeseries-cv/ | SEC | Blog: random CV vs time-series CV reverses ranking on UCI hourly data |
| S65 | https://www.stochasticsolutions.com/pdf/HillstromChallenge.pdf | SEC | Hillstrom dataset design and segment effects |
| S66 | https://arxiv.org/pdf/2609.27912 | SEC | Global tree forecasters degrade at the hierarchical aggregate (abstract-level) |

## Claims with no source found (GAP)
- BEIR and MTEB primary numbers for hybrid retrieval and rerankers (projects 01).
- Minimum sealed-set size for a target CI width at n = 30-55 (01).
- Whether M5 used rolling-origin evaluation, and the M5 top accuracy score (02).
- A current NAB leaderboard for 2025-2026 (03).
- An AG News SOTA figure for 2025-2026 fine-tuned LLMs (04).
- Time-stamped version of the IBM telco data (05).
- 2025-2026 HGS vs ALNS tables on Solomon or Gehring-Homberger; numeric 1000-customer best-known values (06).
- A stronger public NYC zone-hour baseline and multi-hour benchmark (07).
- MLX vs GGUF quality comparison; lm-evaluation-harness primary docs (08).
- Radcliffe's original Qini definition (10).
- TabPFN vs LightGBM on bike data (12).
- k6 and wrk2 primary docs; ONNX Runtime Server, Triton comparisons (13).
