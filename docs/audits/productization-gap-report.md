# Productization Gap Report — 2026-10-15

> **Superseded (2026-10-16).** This report predates the builds of projects
> 08 (inference & serving), 09 (agentic workflows) and 10 (uplift &
> experimentation), all of which are now built and documented in their own
> READMEs. The per-project gap tables below are historical; treat the
> project READMEs and the second-pass audit response as current.

What separates each project from "closed and productized", and the plan for the new
ones. Criteria for "productized": reproducible pipeline (✅ all), real measured results
with honest baselines (✅ all), a serving or consumption path, operational coverage
(monitoring/drift/runbooks), and a finalized roadmap. The roadmaps were converted to
milestones retrospectives in wave 9; this report is the forward-looking counterpart.

## Status legend
- ✅ shipped · 🔶 partially shipped · ⬜ the gap to productized

| Project | Consumption path | Ops coverage | Remaining gaps (priority order) |
|---|---|---|---|
| 01 RAG agent | 🔶 chat API (env-gated) + case study | ⬜ | Auth/rate-limit for a public demo; provider failover telemetry; embedding-index refresh cadence; client-corpus onboarding productized as a script + docs page |
| 02 Forecasting | ⬜ (batch metrics only) | ⬜ | Forecast-serving endpoint (same pattern as 07); scheduled retraining on new data; alert on backtest degradation; UCI track: returns-aware + calibrated intermittent bands |
| 03 Anomaly detection | ⬜ | 🔶 adaptive-threshold machinery | Streaming integration against a real event source; detector registry (swap without code); alert sink (webhook/email) — the scoring exists, the plumbing doesn't |
| 04 NLP | ⬜ | ⬜ | 120k full fine-tune (GPU, booked); model artifact serving (ONNX/quantized); per-class threshold API for imbalanced mixes |
| 05 Churn | ⬜ | ⬜ | Real CRM extract (engagement-gated — onboarding path ready); scheduled scoring + threshold drift review; dashboard refresh |
| 06 Routing | 🔶 CLI + benchmark tables | ⬜ | Solver-as-a-service endpoint (POST problem → RoutePlan); instance upload path; per-family tuning presets |
| 07 Mobility | ✅ forecast endpoint live | 🔶 serving artifact versioned | Drift monitoring + retrain on new TLC snapshots (deferred, engagement-dependent); per-service retraining (green/FHV); geo view (needs geopandas) |
| 08 Inference & Serving (new) | ✅ built | ✅ cost ledger + budget caps | Serving-economics ladder shipped; second serving stack + repeat runs remain deferred (see project README) |
| 09 Agentic Workflows (new) | ✅ built | ✅ deterministic graders + traces | Held-out task set shipped (reported separately); evals suite is the consumption path |

## Cross-cutting gaps (platform level)

1. **Serving pattern standardization**: 07 proves the pattern (persist serving
   artifact → showcase API endpoint → contract doc). Apply to 02 (forecast),
   06 (solver), 05 (scoring). A generic `ServingContract` in portfolio-core would
   make each new endpoint ~1 hour of work.
2. **Drift/monitoring story**: today only documented (runbooks) — a lightweight
   "re-run eval on schedule, diff vs pinned metrics, alert on regression" job
   (cron + `dvc repro evaluate` + a diff report) would close most of the ops column.
3. **CI vs release verification**: real-model runs are release-time by design
   (ADR-0003); make that explicit with a `make release-verify` target that runs the
   Ollama-gated evaluations and asserts metrics exist.
4. **Notebooks**: 7 shipped; 08/09 get theirs at build time (scaffold convention).

## Suggested build order (next waves)

1. **08 Inference & Serving** — it underpins serving for everything else and is the
   stated next project; its cost-per-token tables also feed the services narrative.
2. **Generic serving contract + 02/06 endpoints** — turns four projects into
   demonstrable APIs.
3. **09 hardening** — expand the task suite; HITL demo; then 08+09 together answer
   "agentic AI + inference" end-to-end.
4. Ops pass (drift-diff job + release-verify target) — productizes the platform
   itself.
