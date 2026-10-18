# amm-ds — ML/AI Engineering Portfolio

**I build reliable AI and ML systems that turn complex data into measurable
business outcomes.** Ten reproducible case studies — each with a naive
baseline, an honest delta, and the code to verify it.

## Flagships

- **[Urban mobility demand intelligence](projects/07-open-data-mobility.md)** —
  41.2M real trips, **−28.4% forecast error** vs the "same hour last week"
  rule, a 90.8%-calibrated staffing band, and a drift observatory that opens
  an issue when the model degrades.
- **[RAG & agentic assistant](projects/01-rag-agent.md)** — answers only from
  retrieved evidence with per-claim citations; a verify-then-answer loop
  cut unsupported claims from 60% to 47% locally, and a sealed held-out set
  publishes the generalization gap (recall 0.831 → 0.600) instead of hiding it.

## Measured results, three of them

- Churn decision cost **−41.9%** vs the naive policy, bootstrap 95% CI
  [−485, −343] — on real IBM telco data.
- Routing optimization within **4.23% of best-known solutions** on all 56
  Solomon VRPTW instances — hand-written, seeded, machine-validated.
- An agentic-workflow suite where **77/77 graded outcomes pass** across the
  tuning set, a held-out set, and should-fail probes — for $0.10 of a
  metered $2.00 budget cap.

## Talk to me

[Open an inquiry](site/contact.md) — discovery call first, written scope
after. Full offerings on the [Services](site/services.md) page.

---

## Documentation

Architecture decision records, the engineering playbook, per-project design
documents, the open-data registry, and operational runbooks — use the
navigation on the left.

## Quick start

```bash
make setup          # uv sync + pre-commit
make test           # ruff + mypy + pytest with coverage gates
dvc repro           # reproduce all pipelines (downloads public data)
make docs-serve     # docs at http://127.0.0.1:8000
make docker-up      # showcase app (FastAPI + React) at http://localhost:8000 —
                    # serves the real artifacts: forecast/score/solve endpoints,
                    # per-project story/metrics/figures, RAG chat
```
