# Projects

Ten showcases across agentic AI, classical ML, deep learning, optimization,
model serving, decision science, and large-scale open-data engineering. Each
page links the problem, the design record, and the evaluation artifacts; the
same case studies render live (with interactive figures) in the
[showcase app](https://amm-ds.github.io/portfolio/)'s Projects section.

| # | Project | Domain | Data | Impact in one line | Status |
|---|---|---|---|---|---|
| 01 | [RAG & Agentic AI Assistant](01-rag-agent.md) | Agentic AI / LLM | Wikipedia (HF) | retrieval recall@5 0.83 vs 0.03 random; verify loop cut unsupported-claim share 60%→47% in an on/off A/B (committed hosted 65-q run: 18/65) | Flagship — complete |
| 02 | [Demand Forecasting](02-demand-forecasting.md) | Time series | Walmart M5 subset (primary) + UCI Retail II (sparse secondary) + synthetic CI path | M5 headline: convex ensemble (lgbm+xgb+auto_ets) beats the seasonal-naive floor by −0.1125 WAPE (0.491 vs 0.603, 95% CI [−0.1228, −0.1026]) in both volume classes; next-week h≤7 service 0.423 vs 0.544; wave-28 L1/L2 pass: the pure-L2 arm reproduced lgbm bitwise and the WRMSSE-selected blend is a wash (0.4905/0.5952 vs 0.4907/0.5958) — the flat curves are the conditional mean of noisy demand, not a loss-function bug; UCI sparse track: zero stays the ceiling, new wave-22 baselines lose honestly | Working showcase |
| 03 | [Anomaly Detection over Telemetry](03-anomaly-detection.md) | Unsupervised ML | NAB (real) + seeded synthetic CI path | catches 73% of real incidents; alert budget quantifies the false-positive cost | Working showcase |
| 04 | [NLP Classification with Transformers](04-nlp-classification.md) | Deep learning NLP | AG News (HF, full 120k) | full-data fine-tune reaches 0.946 macro-F1 on a laptop GPU | Working showcase |
| 05 | [Churn Modeling with sklearn Pipelines](05-ml-pipeline-churn.md) | Classical ML | IBM telco churn (real) + synthetic CI path | cuts retention-campaign cost 41.9% vs the naive policy (CI excludes zero) | Working showcase |
| 06 | [Routing Optimization (VRPTW)](06-routing-optimization.md) | Combinatorial optimization | CVRPLIB Solomon | within 4.23% of best-known solutions on all 56 instances (+3.73 vehicles) | Working showcase |
| 07 | [Urban Mobility Demand Intelligence](07-open-data-mobility.md) | Data engineering + ML | NYC TLC + NOAA | −28.4% demand error on 41.2M trips; p90 staffing band calibrated at 90.8% | **Flagship — complete** |
| 08 | [LLM Inference & Serving](08-inference-serving.md) | Model serving | Local Ollama stack (GGUF vs MLX) | measured latency/throughput frontier across engines, quants, concurrency | Working showcase |
| 09 | [Agentic AI Workflows](09-agentic-workflows.md) | Agentic AI | Deterministic 15-task suite | 15/15 on every grader on a hosted model + held-out 7/7 answers, 3/3 should-fail refusals — ledger $0.086 of the $2.00 suite cap (cloud-equivalent) | Working showcase |
| 10 | [Retention Uplift & Experimentation](10-uplift-experimentation.md) | Decision Science | Hillstrom email (MineThatData) | targeting profit advantage established by paired bootstrap; mail-everyone named as the bar | Working showcase |
