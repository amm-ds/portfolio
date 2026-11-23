# Master Release Plan: RAG 01 Finalization + Portfolio-Wide Polish & Deployment Readiness

Date: 2026-11-23
Designer: Claude Code
Owner: session owner (portfolio repo)
Branch: `phase0-infra-2026-11-22` (and subsequent release branches per wave)
Status: approved roadmap (Wave 1 RAG finalization in progress; Waves 2–5 queued for sequential handoffs)

---

## Wave 1 — Finalize Experiment 01 (RAG Agent) [ACTIVE NOW]

**Goal:** Complete Phase E (`dev_v1` re-gate + `final_v3` 120-question E2E evaluation), hit SOTA retrieval (`recall@5 = 0.9457`, `multi_hop = 0.8333`) and per-question F1 target (`0.85–0.90+`, `0` budget terminations), commit all verified results, and update public RAG copy.

1. **1A — Execute Phase E Revision 1 & Step 3 (Kimi):**
   - Apply deterministic in-tool soft budget ceiling (`agent.py`), multi-hop synthesis Rule 10 + `verify.py:559` guard, and `--retry-failed` (`run_e2e_eval.py`).
   - Re-run the 3 failed `dev_v1` rows (~$0.05), confirm `F1 >= 0.85` & `budget_terminated == 0`.
   - Run the checkpointed 120-question `final_v3` pass (`--reports-dir reports/final_v3_e2e`, `LLM_COST_LIMIT_USD=2.40`, `HF_HUB_OFFLINE=1`).
2. **1B — Review, Validate & Commit (Claude):**
   - Audit `reports/final_v3_e2e/f1_summary.json` and `question_traces_heldout.json`, verify all gates (`pytest --cov`, `ruff`, `mypy`, `check_docs.py`), and commit.
3. **1C — RAG 01 Docs & Article Update (Handoff → Kimi, Commit → Claude):**
   - Update `projects/01-rag-agent/story.yaml`, `README.md`, `DESIGN.md`, `docs/projects/01-rag-agent.md`, and `apps/showcase-web/src/lib/cardCopy.ts` with the finalized `S3` retrieval, `judge_v2` (30/30 = 100% owner-validated), and `final_v3` E2E numbers.
   - Regenerate `storyShort.ts` / `staticRegistry.ts` and verify `check_headline_numbers.py` and `check_short_copy.py --check`.

---

## Wave 2 — UI Light-Mode Polish, About/Contact, Home & Projects Index

**Goal:** Fix visual contrast/consistency in light mode, simplify Contact disclaimer, and refine Home, Services, About, and `/projects` cards.

1. **UI Light-Mode Green Alignment (`apps/showcase-web/src/styles/`):**
   - In `:root[data-theme="light"]` (`tokens-base.css:97-105`), text and components use `--accent-bright: #0f766e` while card left borders (`tokens-base.css:385`, `demos.css:446`, `pages.css:568`, `story.css:226,314`) and clickable buttons (`pages.css:71,547`, `demos.css:40`) use `--accent: #14b8a6`.
   - Align card left borders and clickable primary/action buttons (`Send inquiry`, `Unlock`, demo buttons) in light mode to use `--accent-bright` (`#0f766e`) with `#ffffff` button ink so all light-mode greens match the contrast-safe text/component green.
2. **Contact Disclaimer Simplification (`apps/showcase-web/src/components/ChannelCards.tsx:152-157`):**
   - Replace the verbose 4-line privacy/security-boundary paragraph with a crisp 1–2 line notice (e.g., *"Enter your email or phone to unlock (retained ~30 days to track inquiries; [request deletion](mailto:...))."*).
3. **Home, Services, About & Projects Page Pass (`Home.tsx`, `Services.tsx`, `About.tsx`, `ProjectsIndex.tsx`, `cardCopy.ts`):**
   - Audit `About.tsx` and `Services.tsx` for tone, clarity, and alignment with the rest of the site.
   - Update every project card description and achieved metric in `apps/showcase-web/src/lib/cardCopy.ts` (`CARD_DOES`, `CARD_ACHIEVES`, `CARD_TAGS`) to reflect latest verified results (including RAG 01 and M5 10-origin numbers).

---

## Wave 3 — All 13 Projects: Standardized Roadmaps, Language Pass & Demand Forecasting 02

**Goal:** Unify roadmap structure across all 13 `story.yaml` files, polish technical prose, and investigate erratic-series error reduction in Project 02.

1. **Standardized Ad-Hoc Roadmap Pass (`projects/*/story.yaml`):**
   - Enforce the 5-card `story.yaml` roadmap contract (`docs/engineering/repo-conventions.md:18-24`: 4 `shipped` + 1 `next`, titles 3–6 words verb-first, details ≤ 90 chars) following a consistent lifecycle arc adapted to each project:
     1. **Data** (e.g., corpus/panel ingested & contract pinned)
     2. **Training** (e.g., baseline & model architecture trained)
     3. **Evaluation** (e.g., holdout/leakage-free metric & baseline comparison)
     4. **Production / Serving** (e.g., runtime guardrails, demo, or deployment artifact)
     5. **Next** (explicit gate or next engineering milestone)
2. **Language & Narrative Refinement (`projects/*/story.yaml`, `README.md`, `docs/projects/*.md`):**
   - Polish prose across all 13 experiments for engaging, clear, varied phrasing (no repetitive templates), ensuring every claim traces to `reports/metrics.json` and passes `lint_story_language.py`, `check_short_copy.py --check`, and `check_headline_numbers.py`.
3. **Demand Forecasting 02 (`projects/02-demand-forecasting`) — Erratic Series Investigation:**
   - Current committed `reports_m5_full/metrics.json` (10 origins, 30,490 series): `convex_ensemble` achieves `official_wrmsse = 0.6211` (`bottom_wape = 0.7623`, `bias = +0.0222`), while `erratic_routed` (`lgbm_pool_storecat_peak` on 2,288 erratic series) scored `0.6235` and was rejected by the adoption gate.
   - Design an offline/local challenger round targeting the 2,288 erratic series (`ADI < 1.32, CV2 >= 0.49`) without regressing pooled WRMSSE (`0.6211`): test asymmetric/Huber/Tweedie-power tuning or zero-inflated/hurdle routing and calendar-spike lag features, verify via selection-origin screen before touching the test origin, and update `02-demand-forecasting/{README.md,story.yaml}` and `reports_m5_full/demo_payload.json` so `check_headline_numbers.py` (`0.6211`) is clean.

---

## Wave 4 — Apps Alignment (`agent-chat` & `document-intelligence`)

**Goal:** Bring `apps/agent-chat` and `apps/document-intelligence` to identical code structure, infra hygiene, article depth, and language quality.

1. **Code & Infra Alignment:**
   - Compare `apps/agent-chat/` and `apps/document-intelligence/` (`pyproject.toml`, `.env.example`, `Dockerfile`, `infra/`, `Makefile`/CI gates, `conftest.py`, `README.md`).
   - Align health checks, config/env patterns, test coverage gates, and shared conventions.
2. **Articles & Showcase Integration (`AgentChatArticle.tsx`, `DocumentIntelligenceArticle.tsx`, `apps.ts`):**
   - Align section structure, technical depth, visual flow, terminology, and links to `/glossary` between both app articles.

---

## Wave 5 — Backend Deployment Readiness & Public Repo Hygiene

**Goal:** Ensure `apps/showcase-api` and `deploy/` are production-ready, and declutter development-exclusive documentation from the public repository.

1. **Backend & Deploy Audit (`apps/showcase-api/`, `deploy/`):**
   - Review `main.py`, `contact.py`, `live.py`, `middleware.py`, `vitals.py`, `spa_heads.py`, `Dockerfile`, and `deploy/{Caddyfile,docker-compose.prod*.yml,DEPLOY.md,DEPLOYMENT-REPORT.md}`.
   - Verify health/readiness endpoints, rate limiting, CORS/security headers, and `apps/showcase-api` test suite.
2. **Public Repository Documentation Curation:**
   - Review `docs/audits/`, `docs/portfolio_audit_amm-ds.md`, `docs/repository_setup_report_senior_data_scientist.md`, `docs/engineering/production-review-2026-11-06.md`, and `collaboration/`.
   - Remove or archive stale development-exclusive logs/reports that clutter the public repository, keeping `README.md`, `llms.txt`, `docs/projects/`, `docs/data-registry/`, `docs/architecture/`, and `deploy/` crisp and visitor-focused.
   - Run full release verification: `uv run pytest -q`, `ruff`, `mypy`, `npm test && npm run lint && npm run build`, `uv run mkdocs build --strict`, `check_docs.py`, `check_headline_numbers.py`, `check_short_copy.py --check`.
