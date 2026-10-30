// GENERATED — do not edit.
// Static snapshot of the live registry, baked by scripts/gen_static_registry.py
// from projects/*/portfolio.yaml + story.yaml + demo.yaml (same loaders the
// API uses). Re-run that script after changing any of those files; a re-run
// without changes produces byte-identical output.

export interface StaticProject {
  id: string;
  title: string;
  domain: string;
  topic: string;
  techniques: string[];
  data: string;
  status: "flagship" | "working" | "planned";
  order: number;
}

/** Structural story summary — section/figure/metric ids only, no prose. */
export interface StaticStorySummary {
  project_id: string;
  section_ids: string[];
  figure_names: string[];
  metrics_keys: string[];
  has_roadmap: boolean;
}

export interface StaticDemoRegistryEntry {
  id: string;
  title: string;
  hook: string;
  group: string;
  href: string;
  project: string;
  status: string;
  hero: { label: string; value: string; ci: string | null } | null;
}

export const STATIC_PROJECTS: StaticProject[] = [
  {
    "data": "Wikipedia (HF, real)",
    "domain": "Agentic AI / LLM",
    "id": "01-rag-agent",
    "order": 1,
    "status": "flagship",
    "techniques": [
      "pydantic-ai",
      "RAG",
      "FAISS",
      "reranking",
      "structured outputs",
      "RAGAS"
    ],
    "title": "Rag Agent",
    "topic": "Agentic AI & LLM"
  },
  {
    "data": "Synthetic hierarchy (UCI Retail II optional)",
    "domain": "Time-series forecasting",
    "id": "02-demand-forecasting",
    "order": 2,
    "status": "working",
    "techniques": [
      "time-series CV",
      "GBM",
      "PyTorch",
      "Optuna",
      "conformal bands",
      "MinT"
    ],
    "title": "Demand Forecasting",
    "topic": "Forecasting & Time Series"
  },
  {
    "data": "Synthetic (NSL-KDD optional)",
    "domain": "Unsupervised ML / telemetry",
    "id": "03-anomaly-detection",
    "order": 3,
    "status": "working",
    "techniques": [
      "IsolationForest",
      "LOF",
      "OneClassSVM",
      "Optuna",
      "adaptive thresholds",
      "Polars"
    ],
    "title": "Anomaly Detection",
    "topic": "Anomaly Detection"
  },
  {
    "data": "AG News (HF, real)",
    "domain": "Deep learning NLP",
    "id": "04-nlp-classification",
    "order": 4,
    "status": "working",
    "techniques": [
      "DistilBERT",
      "PyTorch",
      "HF datasets",
      "Optuna",
      "TF-IDF",
      "calibration"
    ],
    "title": "Nlp Classification",
    "topic": "NLP & Transformers"
  },
  {
    "data": "Synthetic churn (messy)",
    "domain": "Classical ML",
    "id": "05-ml-pipeline-churn",
    "order": 5,
    "status": "working",
    "techniques": [
      "sklearn Pipelines",
      "cost-aware HPO",
      "calibration",
      "bootstrap CIs",
      "threshold tuning"
    ],
    "title": "Ml Pipeline Churn",
    "topic": "ML Systems & Decisioning"
  },
  {
    "data": "CVRPLIB Solomon VRPTW (real benchmark)",
    "domain": "Combinatorial optimization",
    "id": "06-routing-optimization",
    "order": 6,
    "status": "working",
    "techniques": [
      "VRPTW",
      "ALNS",
      "2-opt",
      "Clarke-Wright",
      "Optuna",
      "pydantic models"
    ],
    "title": "Routing Optimization",
    "topic": "Optimization"
  },
  {
    "data": "NYC TLC + NOAA (real, GB-scale)",
    "domain": "Data engineering + ML",
    "id": "07-open-data-mobility",
    "order": 7,
    "status": "flagship",
    "techniques": [
      "Polars",
      "GBM + quantile",
      "PyTorch",
      "DVC",
      "DQ gates",
      "FastAPI serving"
    ],
    "title": "Open Data Mobility",
    "topic": "Data Engineering"
  },
  {
    "data": "Fixed synthetic 8-prompt structured-output suite (no download)",
    "domain": "Model serving & inference optimization",
    "id": "08-inference-serving",
    "order": 8,
    "status": "working",
    "techniques": [
      "Ollama serving (OpenAI-compatible)",
      "llama.cpp vs MLX runners",
      "quantization (Q4_K_M / Q8_0 / QAT / MXFP4)",
      "concurrency & latency percentiles",
      "structured output (json_schema)",
      "cost/token"
    ],
    "title": "LLM Inference & Serving",
    "topic": "Inference & Serving"
  },
  {
    "data": "Synthetic 12-doc \"Atlas Valley\" handbook + read-only Wikipedia slice from project 01 (CC BY-SA)",
    "domain": "Agentic AI / multi-step LLM workflows",
    "id": "09-agentic-workflows",
    "order": 9,
    "status": "working",
    "techniques": [
      "pydantic-ai",
      "toolsets",
      "pydantic-graph",
      "HITL",
      "pydantic-evals",
      "cross-project RAG retrieval",
      "LLM cost budgeting"
    ],
    "title": "Agentic AI Workflows",
    "topic": "Agentic AI & LLM"
  },
  {
    "data": "Hillstrom email marketing (MineThatData, ~64k customers, sha256-pinned)",
    "domain": "Decision Science",
    "id": "10-uplift-experimentation",
    "order": 10,
    "status": "working",
    "techniques": [
      "CUPED variance reduction",
      "power analysis",
      "uplift meta-learners (T/X)",
      "Qini evaluation",
      "profit-based targeting policy"
    ],
    "title": "Retention Uplift & Experimentation",
    "topic": "Decision Science"
  }
];

export const STATIC_STORIES: StaticStorySummary[] = [
  {
    "figure_names": [
      "chunk_size_sweep",
      "eda_corpus_composition",
      "failure_taxonomy",
      "latency_histogram",
      "model_comparison",
      "retrieval_funnel",
      "retrieval_hpo_frontier"
    ],
    "has_roadmap": true,
    "metrics_keys": [
      "rag_agent",
      "retrieval_chunks_200",
      "retrieval_lexical_chunks_200",
      "retrieval_model_bge_small_chunks_200",
      "retrieval_model_minilm_chunks_200",
      "retrieval_random_chunks_200",
      "retrieval_rerank_off_chunks_200",
      "retrieval_rerank_on_chunks_200"
    ],
    "project_id": "01-rag-agent",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  },
  {
    "figure_names": [
      "eda_series_overview",
      "eda_units_distribution",
      "hpo_history",
      "hpo_importance",
      "m5:band_calibration",
      "m5:class_comparison",
      "m5:horizon_growth",
      "m5:wape_bars",
      "m5:win_rate",
      "uci:fold_stability",
      "uci:multistep_error_vs_horizon",
      "uci:multistep_routing"
    ],
    "has_roadmap": true,
    "metrics_keys": [
      "ets",
      "hgb",
      "hgb_tuned",
      "lgbm_tuned",
      "naive_last",
      "naive_mean",
      "ridge",
      "seasonal_naive",
      "temporal_net",
      "xgb_tuned"
    ],
    "project_id": "02-demand-forecasting",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  },
  {
    "figure_names": [
      "adaptive_stream",
      "eda_signals_overview",
      "hpo_importance",
      "nab_alert_budget",
      "nab_score_distribution",
      "nab_timeline_nyc_taxi",
      "nab_timelines",
      "nab_tune_surface",
      "pr_curves",
      "telemetry_flags",
      "threshold_sweep"
    ],
    "has_roadmap": true,
    "metrics_keys": [
      "isolation_forest",
      "isolation_forest_tuned",
      "lof",
      "lof_tuned",
      "ocsvm",
      "ocsvm_tuned",
      "random"
    ],
    "project_id": "03-anomaly-detection",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  },
  {
    "figure_names": [
      "confusion_matrix_selected",
      "eda_class_balance",
      "epochs_probe",
      "hpo_history",
      "per_class_f1_comparison",
      "scale_ladder",
      "training_curve"
    ],
    "has_roadmap": true,
    "metrics_keys": [
      "baseline_tfidf_logreg",
      "distilbert",
      "distilbert_full_120k",
      "distilbert_scale_12000",
      "distilbert_scale_4000",
      "distilbert_scale_40000",
      "distilbert_tuned",
      "encoder_b"
    ],
    "project_id": "04-nlp-classification",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  },
  {
    "figure_names": [
      "bootstrap_ci",
      "business_cost_curve",
      "calibration_curve",
      "cost_surface",
      "eda_churn_profile",
      "fairness_slices",
      "permutation_importance",
      "precision_recall_curve"
    ],
    "has_roadmap": true,
    "metrics_keys": [
      "logreg_threshold_0.300",
      "naive_majority",
      "selected_model",
      "selected_model_calibrated"
    ],
    "project_id": "05-ml-pipeline-churn",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  },
  {
    "figure_names": [
      "alns_convergence_C101",
      "eda_instance_map",
      "family_gap",
      "gap_pct",
      "pareto_gap_runtime",
      "route_map_C101",
      "solver_profile"
    ],
    "has_roadmap": true,
    "metrics_keys": [
      "alns",
      "alns_fleet",
      "clarke_wright",
      "ortools_cp",
      "randomized",
      "two_opt",
      "two_opt_tuned"
    ],
    "project_id": "06-routing-optimization",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  },
  {
    "figure_names": [
      "actual_vs_pred_top5",
      "borough_mae",
      "gbm_vs_nn",
      "hour_borough_heatmap",
      "p90_band",
      "weather_elasticity",
      "zone_demand_map",
      "zone_fan",
      "zone_hour_heatmap"
    ],
    "has_roadmap": true,
    "metrics_keys": [
      "gbm_mean",
      "gbm_tuned",
      "naive_lag24",
      "temporal_net",
      "temporal_net_tuned"
    ],
    "project_id": "07-open-data-mobility",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  },
  {
    "figure_names": [
      "engine_panel",
      "latency_concurrency",
      "quality_quant",
      "toks_per_s"
    ],
    "has_roadmap": true,
    "metrics_keys": [],
    "project_id": "08-inference-serving",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  },
  {
    "figure_names": [
      "cost_latency_bars",
      "node_waterfall",
      "suite_summary",
      "tool_usage_matrix"
    ],
    "has_roadmap": true,
    "metrics_keys": [
      "agentic_suite"
    ],
    "project_id": "09-agentic-workflows",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  },
  {
    "figure_names": [
      "cost_sensitivity",
      "cuped_variance",
      "eda_segment_profile",
      "profit_frontier",
      "profit_frontier_multi_arm",
      "qini_curves",
      "qini_per_arm",
      "recommended_arm_distribution",
      "uplift_by_decile"
    ],
    "has_roadmap": true,
    "metrics_keys": [
      "random",
      "response",
      "t_learner",
      "treat-everyone",
      "x_learner"
    ],
    "project_id": "10-uplift-experimentation",
    "section_ids": [
      "background",
      "objectives",
      "data",
      "eda",
      "training",
      "evaluation",
      "results",
      "conclusions"
    ]
  }
];

export const STATIC_DEMO_REGISTRY: StaticDemoRegistryEntry[] = [
  {
    "group": "plan operations",
    "hero": {
      "ci": "paired bootstrap CI [−0.123, −0.103] on the −0.112 gap; 88.8% per-series win rate; 80% band covers 77.7% (m5_direct_v1, horizon 28)",
      "label": "pooled test WAPE, ensemble vs seasonal-naive floor (600 series, 2 scored origins)",
      "value": "0.491 vs 0.603"
    },
    "hook": "Pick a committed M5 store-product series, compare the seasonal naive, AutoETS, LightGBM and the pooled ensemble on the two scored-once test origins, and slide the horizon — curves, 80% band and per-series WAPE respond.",
    "href": "/demos/forecast-workbench",
    "id": "forecast-workbench",
    "project": "02-demand-forecasting",
    "status": "live",
    "title": "demand forecast workbench"
  },
  {
    "group": "retain customers",
    "hero": {
      "ci": "paired bootstrap CI [−485, −343]",
      "label": "decision cost per 1,400 customers",
      "value": "$601 vs $1,035 naive"
    },
    "hook": "Move the alarm threshold and the missed-churner cost — watch the optimal cutoff and the saved budget change on a real churn model.",
    "href": "/demos/churn-sandbox",
    "id": "churn-sandbox",
    "project": "05-ml-pipeline-churn",
    "status": "live",
    "title": "churn threshold sandbox"
  }
];
