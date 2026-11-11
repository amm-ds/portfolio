# Portfolio and Website Evaluation — 2026-11

> **Status appendix (2026-11-12, current HEAD `3ba2d64`).** The evaluation
> below was authored against `35598f8` / `f8bd3c9`; this appendix records
> what changed since. Verdict: 7.9/10 — "strong foundations, release hold".

## Findings already resolved at HEAD

| Finding | Resolution |
|---|---|
| P0-1 release-artifact contract (12→13 feature chain) | `check_release_artifacts.py` green; `feature_selection.json` + feature contract committed (audit pass 4) |
| Red `ci` axe job (36 light-theme contrast violations) | R1 (`3ba2d64`): all accent text routed through `--accent-bright`; full 72-state axe matrix reports **0 violations** |
| Report `.table-wrap` not keyboard-focusable | R1: `portfolio_eval/report.py` + all 16 committed report.html carry `tabindex=0` / `region` / accessible name / focus style |
| Initial focus bypasses skip link (`RouteAnnouncer`) | R1: mount vs navigation split; first Tab on fresh load reaches the skip link; browser test added |
| Docker smoke `/docs` CSP drift | R1: smoke now asserts the hardened F-14 edge posture (strict policy refuses the inline bootstrap) and verifies Swagger direct on the opt-in API path |
| Nightly duplicate-issue stream (#24–#28) | R1: notify dedupes onto one open issue; #24–#27 closed as superseded, #28 is the tracking issue; the 04 failure does not reproduce at HEAD |

## Still open (roadmap R2–R5)

Project-detail CLS (07: 0.107 / 03: 0.111), field Web Vitals (RUM),
deployed `/projects` raw head + root JSON-LD, metrics `_meta` provenance,
SBOM/signing/provenance, exporter tracked/ignored manifest, 03 VUS-PR +
no-skill controls, 01 independent (ungated) stress set, agent-chat public
hardening (conditional), conversion measurement, large-module review.

## Release governance rule adopted

No deploys from red CI: a revision ships only after the required checks are
green on its exact SHA, with health-SHA verification after deploy.

---

# Portfolio and Website Evaluation Report

**Repository:** [`amm-ds/portfolio`](https://github.com/amm-ds/portfolio)  
**Website:** [`alejandromerida.dev`](https://alejandromerida.dev)  
**Collaboration artifact:** `agent-chat-v1-20261111T170807-3946625.zip`  
**Evidence cutoff:** 2026-11-12, final deployment-parity and focused browser recheck; full live matrices ran 2026-11-11  
**Audit type:** independent static review, executable checks, live browser/HTTP testing, repeated Lighthouse runs, automated accessibility matrix, and comparison with current engineering guidance

## 1. Executive assessment

### Verdict

**Overall weighted score: 7.9/10 — strong production engineering foundations, but currently on release hold.**

This is an unusually rigorous personal ML/AI portfolio. Its strongest qualities are not visual polish or model novelty; they are the engineering system around the work: typed boundaries, isolated application templates, committed pipelines and evaluation artifacts, honest baselines, generated copy contracts, strict quality gates, route-specific security policy, and reproducibility checks. The supplied Agent Chat package is also substantial and its directly executed backend and frontend checks are strong.

The current state does **not** support an unqualified “production-grade and SOTA” conclusion:

1. **Current main is not release-green.** CI run [`43064295255`](https://github.com/amm-ds/portfolio/actions/runs/43064295255) fails the release-artifact contract and the axe accessibility job at `35598f8`. The release-contract failure reproduces locally because Project 12’s `data/feature_selection.json` and Project 13’s feature-contract path are absent.
2. **The live accessibility result is materially worse than sampled Lighthouse scores suggest.** All 36 light-theme route/viewport combinations failed color contrast in the full `f8bd3c9` matrix, and the Project 01 report had a non-focusable scrollable table wrapper in all six report scans. Focused `35598f8` rechecks reproduce both defect classes.
3. **The largest historical performance problem is improved but not closed.** Homepage mobile performance measured 99/100 in two runs on the prior deployment. Project 07’s repeated CLS was 0.31953 there; a focused recheck after the final deployment measured 0.10684, still marginally above the 0.1 reference. Late report-link insertion was the dominant diagnosed cause in the repeated runs.
4. **Production and main converged during finalization—but through a red pipeline.** Production initially ran `f8bd3c9d9844464397bd702f8914debeba98f6dd`; the final health recheck reports current main `35598f8df4ba6d61b260feea1f352eae7e9a7ca7`, and the 55-question RAG story is now live. This closes deployment lag, but the deployed revision’s CI run remains failed, so release governance is still unresolved.
5. **The collaboration ZIP is integrity-valid, but “clean” is not complete provenance.** All 127 payload hashes and sizes match, the commit is now public, and no real credential was identified. Eight ignored local artifacts are nevertheless present in a `dirty: false` export, so the manifest does not prove that every payload byte came from the named commit.

**Recommended decision:** keep the healthy service online, but treat the current deployment as operationally available rather than release-assured. Fix the release and accessibility gates, verify the already-deployed behavior, and establish a green build→release→production chain for the next revision. Do not normalize deploying revisions whose required checks are red.

### What is genuinely excellent

- Thirteen end-to-end projects with real artifacts, negative results, uncertainty, baselines, and decision-oriented evaluation rather than notebook-only demonstrations.
- Strong monorepo boundaries: `uv` workspace and lockfile, shared libraries, FastAPI/React showcase, and intentionally isolated application templates.
- Strict Ruff/mypy/Pytest/Vitest/ESLint/TypeScript controls, import contracts, release-artifact checks, route/copy freshness checks, Docker smoke tests, dependency audits, and CodeQL.
- DVC pipelines, pinned data, sealed evaluation sets, scored-once protocols, and scheduled reproducibility checks.
- Excellent live homepage performance and a large reduction in figure payload sizes.
- Strong production headers, disabled public API documentation, request IDs, health/readiness endpoints, non-root containers, and privacy-preserving default site behavior.
- Agent Chat’s directly observed checks: Ruff, formatting, strict mypy, 135 backend tests, ESLint, 27 frontend tests, TypeScript/Vite build, and zero reported npm-audit vulnerabilities.
- The new Project 01 sealed evaluation is a meaningful methodological improvement: 55 questions, per-question traces, refusal measurement, failure taxonomy, cost, and latency.

### What prevents a higher score

- Red main and a nine-day observed nightly failure streak weaken otherwise excellent gates.
- Systematic light-theme contrast failures, a report keyboard-access defect, and incorrect initial focus behavior.
- Project-detail CLS, client-side request waterfalls, and no field Web Vitals evidence.
- Missing standardized metrics provenance, SBOM, image signatures, and build-provenance attestations.
- A red-CI revision reached production, with no demonstrated staging tier and no production conversion/RUM measurement.
- Agent Chat’s optional authentication and remaining URL-fetch threat-model verification requirements for a public deployment.

## 2. Scope, states, and scoring

### 2.1 States kept separate

| State | Identifier | How it is used in this report |
|---|---|---|
| Historical supplied audit | `77cb63f` | Baseline only; old findings are not assumed to remain open |
| Initially inspected source | `aa71d1d9d198c4984fe3a4f89feafbb57f0acff8` | Full static snapshot, 1,597 files |
| Supplied Agent Chat ZIP | `394662581d94bf4b10fcec8ca2ffbef5ac704fc5` | Integrity, provenance, source, tests, and exporter comparison |
| Current public main at final recheck | [`35598f8`](https://github.com/amm-ds/portfolio/commit/35598f8df4ba6d61b260feea1f352eae7e9a7ca7) | Current source and CI status |
| Production during full browser/Lighthouse/axe matrices | `f8bd3c9d9844464397bd702f8914debeba98f6dd` | Live functionality, content, security, accessibility, and repeated performance measurements on 2026-11-11 |
| Live production at final recheck | `35598f8df4ba6d61b260feea1f352eae7e9a7ca7` | Health/source parity, live RAG/raw-HTML checks, and focused accessibility/CLS/focus rechecks on 2026-11-12 |

`3946625` is now publicly resolvable and is the parent of `35598f8`. Its earlier provenance failure is therefore **resolved**, not an open finding. A full source diff against earlier deployment `f8bd3c9` was not completed; deployed behavior was tested directly. Measurements from the two production states are labeled separately below rather than combined.

### 2.2 Weighted scorecard

Scores measure the current evidence, not the effort invested and not the historical 8.6/10 assessment.

| Dimension | Weight | Score | Rationale |
|---|---:|---:|---|
| Architecture and system boundaries | 10% | 9.2 | Clear workspace, shared typed libraries, isolated apps, ADRs, generated contracts |
| Code quality and maintainability | 10% | 8.7 | Strict static checks and good conventions; several very large modules merit boundary review |
| Testing and CI effectiveness | 15% | 7.4 | Broad, well-designed controls, but current main and accessibility gates are red |
| Reproducibility and evaluation rigor | 15% | 8.6 | Excellent pipeline/evaluation culture; missing release contract, red nightly, uneven provenance schema |
| Security and software supply chain | 10% | 8.5 | Strong headers and dependency controls; no SBOM/signing/provenance; public-agent hardening remains |
| Deployment and operations | 10% | 7.4 | Healthy current deployment and source parity, but a red-CI revision reached production; red nightly, no field RUM or demonstrated staging |
| Frontend performance and UX | 10% | 7.5 | Excellent prior-deployment homepage; current Project 07 CLS recheck remains 0.10684 and detail/demo performance varies |
| Accessibility | 10% | 5.8 | Good automation intent, contradicted by 39 failing scan states and two keyboard/focus defects |
| SEO and discoverability | 5% | 8.1 | Strong route metadata, sitemap and `llms.txt`; raw root/project-index content and structured-data gaps |
| Content, conversion, and outcome measurement | 5% | 6.7 | Strong technical storytelling and working contact flow; no evidence of inquiries, engagement, or business outcomes |
| **Weighted overall** | **100%** | **7.9** | **Strong foundation; release hold until P0 items close** |

“Production-grade” is treated as a verified operating state, not a synonym for good source code. “SOTA-aligned” is used only for specific practices, not as a claim that every model or method is the newest available.

### 2.3 Evidence base and limitations

Directly performed:

- Static inspection of repository architecture, workflows, source, tests, deployment configuration, and project artifacts.
- Local reproduction of the release-artifact gate at both `aa71d1d` and `35598f8`.
- Agent Chat backend/frontend quality commands and adversarial export tests in a temporary Git repository.
- Live HTTP checks, 26 desktop/mobile browser route checks, 38 unique rendered internal-link checks, and all 23 sitemap URLs.
- Eleven Lighthouse 13.6.0 runs using Node 22.23.4.
- Seventy-two axe scans: 12 routes × 3 viewports × 2 themes, with target-size enabled.
- Keyboard, contact-form, raw-HTML, header, health, readiness, and report/asset checks.

Limitations:

- Private CI logs/artifacts could not be downloaded; the exact CI axe failure cause was not invented. The independent production matrix establishes a real accessibility failure regardless.
- Lighthouse is laboratory evidence, not field Core Web Vitals. No CrUX/RUM dataset was available, and lab TBT is not INP.
- Agent Chat frontend unit/build checks ran under Node 20.20.2 although the project prerequisite is Node 22+. E2E completion is supported by saved Playwright runner state (`status: passed`), not a directly observed completed process.
- The original ZIP was not byte-for-byte regenerated, the exact `uv run` wrapper was not exercised, and exporter commit-range/`--no-diff` paths were not directly tested.
- No cloud infrastructure, host, database, secret store, analytics account, Search Console, or production logs were accessible.
- No claim is made about lead volume, search ranking, revenue, user engagement, real-user INP, or business conversion.

## 3. Repository evaluation

### 3.1 Architecture and maintainability

The platform structure is a strength:

- `libs/portfolio-core` and `libs/portfolio-eval` hold shared contracts and evaluation/reporting behavior.
- Thirteen numbered projects retain their own pipelines and artifacts.
- `apps/showcase-api` and `apps/showcase-web` provide the common product surface.
- `apps/agent-chat` and `apps/document-intelligence` are deliberately isolated with their own dependencies and quality workflows.
- Import-linter contracts, strict typing, generated registries, route manifests, story/copy checks, and release-artifact validation turn conventions into executable constraints.

This is preferable to a collection of unrelated notebooks because improvements to evaluation, rendering, security, or deployment can propagate through a common system. The static registry for above-the-fold project cards is a particularly effective pattern; the report-link availability defect shows where that pattern has not yet been applied consistently.

Maintainability risks are concentrated in a few large modules: `m5_track.py` (102,152 bytes), `plotlyToECharts.ts` (88,694), `m5_full.py` (73,072), Project 01 `evaluate.py` (58,823), Project 10 `evaluate.py` (58,223), and `showcase_api/main.py` (48,597). Size alone is not a defect. Review these by responsibility, coupling, change frequency, and test seams before splitting; do not perform cosmetic decomposition.

### 3.2 Testing and delivery gates

The intended control set is broad and appropriate: Ruff, formatting, strict mypy, Pytest, Vitest, ESLint, TypeScript, dependency contracts, demo contracts, release artifacts, generated-copy freshness, figure checks, bundle budgets, axe, Docker smoke, dependency audits, and CodeQL. Path filtering avoids paying the full matrix cost for irrelevant changes.

The problem is **gate effectiveness**, not gate absence:

- Current main’s release gate fails at “Release-artifact contract.”
- The same missing Project 12 contract reproduces locally with exit code 1.
- Current main’s `a11y-axe` job fails while several unrelated jobs are skipped by path filtering.
- Nightly runs failed from November 2 through November 10 in the observed window; the last observed scheduled success was November 1. Open nightly issues #24–28 cover November 6–10.
- Uptime checks were succeeding through the latest observed schedule, and direct checks found the site live. A red nightly therefore does not mean the website is down; it means the reproducibility/maintenance signal is unhealthy.

**Required practice:** make red main/nightly states exceptional, owned, and time-bounded. Do not merge or release by reclassifying known failures as expected noise. Deduplicate automated nightly issues and record root cause, owner, resolution, and verification.

### 3.3 Reproducibility and metrics provenance

DVC pipelines, pinned datasets, sealed sets, honest baselines, negative results, run-twice checks, and scored-once evaluation protocols are among the repository’s best differentiators. Project 13’s champion re-derivation and ONNX parity gate are good examples of evaluation as an engineering contract.

Two gaps remain:

1. The Project 12→13 feature-selection/feature-contract artifact chain is incomplete in the source archive, despite code and DVC references. This is now a concrete release blocker.
2. In the `aa71d1d` snapshot, none of the 13 `reports/metrics.json` files exposed the complete proposed provenance set at top level or `_meta`: `git_sha`, `uv_lock_sha256`, `data_sha256`, `params_sha256`, `seed`, and `created_at`. This does **not** prove that no provenance exists in nested project-specific structures; it shows the absence of a uniform, machine-checkable schema.

Introduce a versioned common `_meta` contract and validate it in CI. Keep project-specific metric shapes flexible while making artifact identity and regeneration inputs uniform.

### 3.4 Security and supply chain

Verified strengths include per-route CSP, HSTS, COOP, `nosniff`, referrer and permissions policies, frame denial, disabled production API docs, structured errors with request IDs, non-root containers, health checks, CodeQL, and dependency auditing. Production `/docs` and `/openapi.json` return 404 intentionally; unknown API paths return structured 404 responses.

Remaining production-grade improvements:

- Generate an SBOM for each released image.
- Sign the image digest and attach/verify provenance attestations. [Sigstore Cosign supports container signing and attestations](https://docs.sigstore.dev/cosign/signing/signing_with_containers/).
- Map the release workflow to the [SLSA Build track](https://slsa.dev/spec/v1.2/build-track-basics): start with authentic provenance, then hosted signed provenance and hardened builds as justified.
- Verify deployment by digest and expected commit, with a documented rollback.
- Treat current unsigned commit status as a provenance weakness, not as evidence of compromise.

No evidence of an active production vulnerability was found in this audit. The findings are hardening and assurance gaps, not claims of exploitation.

## 4. Project results and technical refinement

### 4.1 Project 01: completed sealed RAG generation evaluation

The most important new project result is the completed 55-question sealed generation pass. It substantially improves the earlier 15-question evidence.

| Measure | Current committed result | Interpretation |
|---|---:|---|
| Sealed questions | 55: 32 single-hop, 10 multi-hop, 13 unanswerable | Larger and more informative than the earlier 15-question pass |
| Correct answers | 44/55 = 0.80; CI [0.6909, 0.8909] | Good result with meaningful uncertainty retained |
| Failure taxonomy | 44 correct, 9 unsupported-claim, 1 retrieval-miss, 1 format-failure | Generation grounding is the dominant failure class |
| Refusal accuracy | 12/13 = 0.9231; CI [0.7692, 1.0] | Strong abstention result, still a small unanswerable subset |
| Operational recall@5 / recall@10 / MRR@5 | 0.74545 / 0.76364 / 0.71818 | Measures the operational reranked/top-citation path |
| Random recall@5 | 0.05455 | Useful floor, not a competing retrieval method |
| Rubric faithfulness / answer relevance / context recall | 0.6338 / 0.7114 / 0.9762 | High context recall coexists with weak supported-generation behavior |
| Evaluation usage | 241 calls; $1.950667 cloud-equivalent under a $3 cap | Estimated cost, not a billed amount |
| Latency | p50 24.443 s; p95 126.811 s | Not suitable for an unattended latency-sensitive production experience |
| Repair behavior | 19 repair calls | Repairs did not eliminate unsupported claims |

**Key diagnosis:** nine of eleven failures retrieved the relevant article at rank 1 but still produced unsupported claims. The next improvement should therefore target citation-constrained generation, claim-level support checks, repair policy, and evaluation of unsupported-claim reduction—not another retrieval rewrite by default.

Raw dense/BM25/RRF retrieval scores are also present, but they are not directly comparable with operational reranked/top-3-citation recall. Keep the two protocols visibly separate in reports.

The 40 expansion questions passed an answerability gate requiring a relevant chunk in the production retriever’s top 10. Their high retrieval values are consistency checks, not an unbiased stress test. Add independently authored, adversarial, multi-hop, temporal, ambiguous, and truly unanswerable questions without using the production retriever as an inclusion filter.

**Final deployment update:** production initially served the older story at `f8bd3c9`, but the final recheck at `35598f8` returns the 55-question story with 44/55 correct and the rank-1 unsupported-claim diagnosis. This improvement is now deployed; the remaining concern is that its revision reached production with a failed CI run.

### 4.2 Cross-project status and next highest-value work

The following table combines current committed result evidence with the supplied per-project technical review. Only Project 01’s changed result set received a complete new deep dive in this pass; the remaining recommendations are refinement directions, not claims that every pipeline was rerun.

| Project | Current evidence and status | Highest-value next refinement |
|---|---|---|
| **01 RAG Agent** | Completed 55-question sealed pass; 44 correct; grounding dominates failures | Claim-level support/citation verification; independent ungated stress set; reduce p95 latency |
| **02 Demand Forecasting** | Full M5 panel, official hierarchical WRMSSE; stability-screened ensemble now present | Per-level WRMSSE decomposition; direct multi-horizon challenger; conformalized interval coverage |
| **03 Anomaly Detection** | Event/alert-budget framing and honest alert-load results; figure payloads greatly reduced | Add robust PR-family evaluation such as VUS-PR/PA%K plus no-skill controls; document NAB module flow |
| **04 NLP Classification** | Calibrated transformer and measured selective-LLM cascade; tiny quality delta is honestly reported | Paired CI for cascade delta, risk–coverage curve, ModernBERT challenger on the same quality/latency harness |
| **05 Churn Pipeline** | Calibrated decision policy with cost curve and bootstrap interval; working interactive sandbox | Temporal-split robustness, threshold-stability distribution, and explicit churn-risk versus uplift comparison |
| **06 Routing Optimization** | Hand-written ALNS with feasible results and best-known comparisons | Add PyVRP/HGS reference and gap-versus-time/Pareto curves rather than rewriting the solver |
| **07 Open-Data Mobility** | 41.2M trips, drift workflow, honest subgroup coverage and strong headline results | Group-aware conformal calibration; report coverage and interval width together; fix live-page CLS |
| **08 Inference Serving** | Multi-engine/quantization harness, 760 requests, latency and energy evidence | Add ITL/TPOT percentiles, quality-per-quantization tasks, and throughput/concurrency frontiers |
| **09 Agentic Workflows** | Fixed/unseen/should-fail suites, budgets, HITL, and explicit supervised-pilot boundary | Broader adversarial and regression suites; tracing/evaluation telemetry; publish failure taxonomy and recovery rates |
| **10 Uplift Experimentation** | Randomized data, Qini/profit framing, model-estimated multi-arm caveat retained | Add doubly robust/R-learner comparison and sensitivity analysis; preserve empirical versus model-estimated distinctions |
| **11 DataFrame Engines** | Metrics artifact now present; parity-checked multi-engine benchmark over 2.96M real trips | Standardize run provenance; publish cold/warm and resource-normalized comparisons; preserve parity gates |
| **12 Tabular ML Lifecycle** | Metrics artifact now present; seeded model ladder and scored-once results | Restore the missing feature-selection artifact first; then consider conformal prediction or a modern tabular challenger |
| **13 Model Serving** | Champion re-derivation and strict ONNX parity pass; measured serving trade-offs | Restore the cross-project feature contract; reduce the 6.5 GB image/CUDA footprint; add signed release evidence |

The portfolio’s best refinement strategy is **adding strong challengers and better evaluation to existing harnesses**, not rewriting working projects to chase framework novelty.

## 5. Website evaluation

### 5.1 Live functionality, resilience, and UX

The full functional pass against `f8bd3c9` found an operational, cohesive site; final production `35598f8` also returns healthy/ready and passes the focused content and browser rechecks. The full route/link inventory below was not rerun after that final deployment change:

- Thirteen representative routes rendered at desktop and mobile sizes with expected H1s, no page errors, no console errors, and no horizontal overflow.
- All 38 unique rendered internal targets returned 200.
- All 23 sitemap URLs returned 200.
- Tested reports, screenshots, SVG logos, video, and social-card assets returned 200. Browser `ERR_ABORTED` observations for some lazy assets were not classified as broken links after direct verification.
- `/health` and `/ready` returned 200.
- Mobile navigation remains visible without a fragile hamburger interaction.
- Forecast and churn demos render usable workbench experiences.
- Contact validation works: empty and invalid submissions focus the first relevant invalid field; valid submission explains that the site composes a `mailto:` and does not itself store or send the message.
- The visual system is distinctive and consistent, and dense case studies remain structured on small screens.

The contact flow is transparent and privacy-friendly, but it adds mail-client friction and cannot provide server-side delivery evidence. A direct form or scheduler is optional, not automatically better: add one only with anti-spam, privacy notice, retention policy, monitoring, and operational ownership.

### 5.2 Laboratory performance

Google’s current guidance defines good field thresholds as **LCP ≤2.5 s, INP ≤200 ms, and CLS ≤0.1 at the 75th percentile**, segmented by mobile and desktop ([Web Vitals](https://web.dev/articles/vitals)). The measurements below are lab runs against the earlier `f8bd3c9` production state, so they are diagnostic comparisons—not proof that the field 75th percentile passes and not a complete characterization of the final `35598f8` deployment.

| Prior-deployment route / run | Performance | LCP | CLS | TBT | Transfer / requests |
|---|---:|---:|---:|---:|---:|
| Home mobile 1 | 99 | 1.067 s | 0.00922 | 51 ms | 142 KiB / 7 |
| Home mobile 2 | 99 | 1.081 s | 0.00922 | 41.5 ms | 142 KiB / 7 |
| Home desktop | 97 | 0.419 s | 0.00598 | 0 ms | 142 KiB / 7 |
| Project 01 mobile | 88 | 2.566 s | 0.07138 | 127 ms | 322 KiB / 24 |
| Project 03 mobile 1 | 91 | 2.104 s | 0.11099 | 232 ms | 322 KiB / 24 |
| Project 03 mobile 2 | 89 | 2.269 s | 0.11099 | 180 ms | 322 KiB / 24 |
| Project 07 mobile 1 | 80 | 1.962 s | 0.31953 | 166 ms | 321 KiB / 24 |
| Project 07 mobile 2 | 73 | 2.457 s | 0.31953 | 136 ms | 321 KiB / 24 |
| Project 07 mobile 3 | 77 | 2.228 s | 0.31953 | 182 ms | 321 KiB / 24 |
| Forecast demo mobile 1 | 89 | 2.705 s | 0 | 123 ms | 197 KiB / 12 |
| Forecast demo mobile 2 | 98 | 1.989 s | 0 | 101 ms | 196 KiB / 12 |

**Assessment of the repeated `f8bd3c9` runs:** the homepage was excellent. Project 03 marginally exceeded the CLS reference and Project 07 failed it decisively. LCP was mostly good but crossed 2.5 s in the sampled Project 01 and first forecast-demo run. Run-to-run score variability means ranges and medians are more honest than a single universal score.

**Exact Project 07 diagnosis on `f8bd3c9`:** `.detail-header .meta-links` contributed 0.2644 and `.detail-header` 0.0551. At approximately one second the links contained code/docs/repository in one row; at approximately two seconds “full evaluation report” appeared, increasing the link block from 28.08 px to 64.16 px and pushing content down. The report link accounted for most of the 0.31953 total.

**Focused `35598f8` recheck:** Project 07’s browser-observed CLS improved to **0.10684**, with the report link present after loading. This is a substantial improvement but still marginally above 0.1. A single focused recheck is not comparable in statistical strength to the three earlier repeated Lighthouse runs; rerun the complete performance matrix on the new deployment before claiming closure.

Project 03’s earlier 0.11099 combined experiment-navigation movement (0.0702) and header movement (0.0282). Project 01’s earlier 0.07138 was below the 0.1 reference but had the same late-render family. Homepage residual CLS came from the typing cursor/`.cmd-partial` and was small.

**Recommended implementation:** bake report/demo availability and breadcrumb data into the static registry; render stable above-the-fold geometry on first paint. If asynchronous availability is unavoidable, reserve responsive space and toggle visibility rather than inserting layout. Add repeated mobile CLS regression checks for every project with a report link.

Secondary opportunities are approximately 22–26 KiB of unused CSS on sampled routes, unused shell/FlowDiagram JavaScript, and registry/story/report/demo request chains. Fix deterministic layout and content availability before micro-optimizing bundles.

**Field measurement gap:** no RUM or CrUX evidence was found. Add privacy-preserving LCP/INP/CLS collection by route, device class, and release SHA; do not collect message content or unnecessary identifiers.

### 5.3 Accessibility

Sampled Lighthouse accessibility scores of 100 do not represent the complete route/theme matrix. The broader scan against `f8bd3c9` found the results below. Focused rechecks against final production `35598f8` still reproduce light-homepage contrast failures and the report’s `.table-wrap` keyboard violation, so neither defect class is stale.

| Result | Count | Meaning |
|---|---:|---|
| Total scans | 72 | 12 routes × desktop/tablet/mobile × dark/light |
| Failing scan states | 39 | Some report scans contain both violation types |
| Violation instances | 42 | 36 contrast + 6 scrollable-region instances |
| Light-theme `color-contrast` | 36 scans | Every tested light-theme route at every viewport |
| `scrollable-region-focusable` | 6 scans | Project 01 report, both themes and all viewports |
| Target-size violations | 0 in this matrix | Historical target-size issue is not reproduced here |

The light-theme accent `#14b8a6` repeatedly measures around 2.12–2.48:1 against white or pale surfaces, below WCAG’s 4.5:1 requirement for normal text. Affected elements include brand accents, active navigation/chips, card headings, KPI values, demo presets, status values, and forecast labels. This is a design-token/system problem, not 36 unrelated component problems.

The report violation targets `iframe .table-wrap`. The shared report template emits `<div class="table-wrap">` with horizontal overflow but no keyboard focus mechanism, so keyboard-only users cannot reliably scroll wide tables.

**Remediation:**

1. Route all light-theme text through a contrast-safe text token such as the existing `--accent-bright`; keep decorative teal separate from text color. Do not assume the current comment “contrast-safe accents” proves every declaration is correct—many text declarations still use `var(--accent)`.
2. Add `tabindex="0"` and an accessible region name to overflowing report table wrappers, with visible focus styling. Prefer generating this in `libs/portfolio-eval/src/portfolio_eval/report.py` so all reports inherit the fix.
3. Rerun the full 72-state matrix and manually verify keyboard scrolling, focus visibility, zoom/reflow, and screen-reader names. Automated scans alone cannot establish full WCAG conformance; use [WCAG 2.2](https://www.w3.org/TR/WCAG22/) as the testable reference.

A separate focus-order defect remains reproducible on final production `35598f8`: `RouteAnnouncer` focuses `#main` on mount as well as after client-side navigation. The first Tab therefore goes to the hero CTA, bypassing the skip link, brand/primary navigation, and theme controls. Track initial mount with a ref; announce and move focus only after actual route changes while preserving hash behavior. Acceptance requires first Tab on fresh load to focus “Skip to content,” and subsequent client-side navigation to focus main.

### 5.4 SEO, raw HTML, and discoverability

Verified strengths:

- `robots.txt`, `sitemap.xml`, `llms.txt`, and `/.well-known/security.txt` return 200.
- Project, app, About, Services, Contact, Glossary, and demo routes generally provide route-specific titles, descriptions, canonicals, Open Graph/Twitter metadata, H1s, and noscript content in raw HTML.
- `/projects/11-data-engineering/metrics` and `/projects/12-tabular-ml-lifecycle/metrics` now return 200.
- `/projects` content negotiation is intentional: HTML-specific requests receive the SPA while generic API requests can receive the registry JSON.

Remaining gaps:

- Final production `/projects` raw HTML is still the generic 2,209-byte shell with homepage title/canonical and no route H1/noscript body, even though production now reports the same SHA as main. Current source contains a `_STATIC_HEADS["/projects"]` implementation, so investigate route matching/content negotiation and the built artifact rather than attributing this to deployment lag.
- Deployed `/` raw HTML is generic: no H1, noscript body, or JSON-LD.
- Homepage `PersonJsonLd` is injected client-side; raw homepage HTML contains no structured data.

Make the existing project-index head implementation effective in the deployed request path and add route-specific root raw content and structured data. If non-JavaScript discoverability becomes business-critical, use the existing route manifest for prerendering/SSG rather than treating noscript text as a complete SEO strategy. Validate rendered and raw HTML separately.

### 5.5 Security and privacy on the live site

The deployed header posture is strong: restrictive route-scoped CSP, HSTS, COOP, `nosniff`, Referrer Policy, Permissions Policy, frame denial, and HTTP/3 advertisement. `HEAD /` now returns 200. No third-party tracker was observed in the tested flows, and the contact page accurately describes its mail-client behavior.

These findings support a strong security posture for the public showcase; they do not prove host hardening, patch latency, backup restoration, or incident readiness because those systems were not accessible.

## 6. Agent Chat package and collaboration workflow

### 6.1 Package integrity and provenance

The supplied ZIP is internally consistent:

| Check | Result |
|---|---|
| Manifest version / commit | v1 / `394662581d94bf4b10fcec8ca2ffbef5ac704fc5` |
| Manifest dirty state | `false` |
| Payload inventory | 127 files, 853,117 uncompressed bytes |
| Compressed ZIP size | 292,779 bytes |
| SHA-256 and size verification | All 127 files match; no missing or extra payload files |
| Public commit resolution | Resolved at final recheck; commit is parent of current main |
| Comparison with current public app source | All 119 current public Agent Chat files are byte-identical to the ZIP |
| Additional ZIP-only files | Eight ignored local artifacts |

The eight ZIP-only files are seven ignored focused reports plus `web/test-results/.last-run.json`. Their presence is compatible with ordinary `git status` reporting a clean worktree, but it means **`dirty: false` does not establish a fully Git-tracked payload**. This is a provenance/hygiene issue, not evidence of credential leakage.

### 6.2 Exporter execution and exclusion tests

The exporter now exists in current main. In an isolated temporary Git repository:

- `git check-ignore` confirmed that `artifacts/` is ignored by `.gitignore` line 41.
- A first export contained 119 files and 848,111 payload bytes; a second export reported no file changes.
- Numbered ZIPs and `.status.json` sidecars were created; `--list` showed both versions correctly.
- Exporting did not dirty the repository.
- After modifying the README and planting `.env`, `agent_chat.db`, session memory, raw/index data, and `node_modules`, the exporter produced a `-dirty.zip`, reported the README change, and excluded every planted sensitive/reproducible artifact.
- `.env.example` remained included, as intended.

The implementation correctly excludes virtual environments, `node_modules`, `dist`, Python/test caches, `.git`, session memory, `.env`, `agent_chat.db`, bytecode, and `data/raw/`/`data/index/`.

Two design weaknesses remain:

1. Files are collected with filesystem `rglob`, while dirty state comes from `git status --porcelain` without ignored files. Ignored reports or runner state can therefore be exported without appearing in `dirty_files`.
2. The Git helper returns stdout without checking subprocess status, so execution outside a Git worktree can produce an empty SHA instead of a clear failure. No dedicated exporter test suite was found.

**Refinement:** record `tracked`, `ignored`, and `untracked` provenance per payload file; default to tracked files plus an explicit allowlist; exclude `test-results`, `playwright-report`, coverage, and other runner state; fail clearly outside Git; and test exclusions, dirty state, sidecars, history, commit ranges, and reproduction from a clean checkout.

### 6.3 Agent Chat engineering checks

| Check | Observed result |
|---|---|
| Ruff lint | Passed |
| Formatting | Passed, 85 files |
| Strict mypy | Passed, 42 source files |
| Backend tests | 135 passed |
| Frontend ESLint | Passed |
| Frontend unit tests | 27 passed across five files |
| TypeScript and Vite production build | Passed |
| npm audit | Zero reported vulnerabilities |
| Playwright E2E | Saved runner state says passed; direct command exceeded observation window |
| Secret scan | Documentation, examples, and test literals only; no real credential identified |

Frontend output was modest: 0.44 kB HTML, 9.66 kB CSS (2.49 kB gzip), and 164.70 kB JavaScript (52.88 kB gzip). Repeat frontend checks under the required Node 22+ before treating the local result as release evidence.

The application architecture is strong for a reusable template: typed tools and skills, provider abstraction, SSE streaming, cited retrieval, bounded history, notebook/session memory, human approvals, PostgreSQL/pgvector with SQLite fallback, and explicit production cautions in the README.

### 6.4 Agent Chat production-security boundary

`require_api_key` returns immediately when no API key is configured. This is reasonable for local development but means authentication is disabled by default. Anonymous session IDs are not authentication; the README correctly requires an authenticated gateway for a public SPA. Before internet exposure, use fail-closed production configuration, real user identity at a gateway, authorization per session, rate limits, audit events, and protected secret storage.

The optional `fetch_url` tool restricts schemes, rejects embedded credentials and non-public addresses, validates the final URL, and caps reads at 200,000 bytes. Before claiming hardened SSRF protection, test every redirect hop, connection-time IP pinning, DNS rebinding, retries/fallbacks, and network egress. [OWASP’s SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) specifically warns that checking DNS separately from the connection does not prevent rebinding and recommends disabling redirects or validating each target.

The collaboration security constraints remain appropriate:

> Local-only: the zips land under artifacts/ (already gitignored repo-wide) — verified with git check-ignore; nothing to hand off ever enters git.

Continue excluding virtual environments, dependencies, builds, caches, local databases, session memory, credentials, environments, and reproducible corpus/index data. Production credentials belong in protected environment/secret storage, never public `VITE_*` browser variables.

## 7. Status against the earlier audit

### 7.1 Verified fixed or materially improved

| Earlier issue | Current evidence | Status |
|---|---|---|
| Projects 11/12 metrics unavailable | Both live metrics routes return 200 | **Fixed** |
| `llms.txt` missing in production | Live route returns 200, 4,536 bytes | **Fixed** |
| `HEAD /` returned 405 | Live HEAD returns 200 | **Fixed** |
| Historical target-size failure | Zero target-size violations in the 72-scan matrix | **Not reproduced; treat as fixed in tested states** |
| Multi-megabyte figure payloads | Figure-weight gate passed with one warning; largest inspected figure is 608,615 bytes | **Materially improved** |
| Small sealed RAG evaluation and missing taxonomy/RRF | 55-question sealed pass, taxonomy, refusal results, dense/BM25/RRF evidence | **Materially improved** |
| ZIP commit initially unresolvable/exporter absent | Commit now public; exporter present and executed | **Resolved** |
| Repository/profile pointers and release visibility | Corrected pointers; `v1.1.0` exists | **Improved** |
| Homepage mobile performance | Two 99/100 runs, approximately 1.07 s LCP and 0.009 CLS | **Improved** |

### 7.2 Still open or only partially closed

| Issue | Current state |
|---|---|
| Nightly reproducibility/validation health | Failed November 2–10 in the observed window; last observed scheduled success November 1 |
| Project-detail rendering stability | Greatly improved from historical CLS 0.714; Project 07 improved from repeated 0.31953 on `f8bd3c9` to 0.10684 in the focused `35598f8` recheck, but remains marginally above 0.1 |
| Field Web Vitals | No RUM/CrUX evidence |
| Non-JavaScript discoverability | Many route heads improved; root and deployed project index remain incomplete |
| SBOM/image signing/build provenance | No implementation found in searched workflows/build files |
| Uniform metrics provenance | No common complete schema across the inspected metrics artifacts |
| Staging and outcome measurement | No demonstrated staging tier or conversion/RUM outcome dataset |
| Large-module maintainability | Still deserves responsibility-based review; not an automatic defect |

### 7.3 New or newly exposed findings

These are not all proven code regressions; some may have existed earlier but were not detected by the previous sampling.

| Finding | Classification |
|---|---|
| Current main fails release-artifact and axe jobs | **Delivery-status regression from the earlier green CI baseline** |
| Light-theme contrast fails in all 36 light scans | **Newly exposed systematic accessibility failure** |
| Report `.table-wrap` is not keyboard-focusable | **Newly discovered accessibility defect** |
| Initial focus bypasses skip link and primary navigation | **Newly discovered keyboard/focus-order defect** |
| Production advanced to current main and the new RAG evaluation while that revision’s CI run was red | **New release-governance gap; deployment lag itself is closed** |
| Clean ZIP includes ignored local artifacts | **Newly discovered exporter provenance limitation** |
| Project 12→13 contract is missing at current HEAD | **New release blocker reproduced locally** |

## 8. Production-grade and SOTA alignment

| Practice area | Current alignment | Gap to close |
|---|---|---|
| Reproducible ML engineering | **Strong / differentiating** | Restore nightly and release contract; standardize provenance metadata |
| AI evaluation and risk measurement | **Strong** | Add independent stress sets and production monitoring; NIST’s [Measure function](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) emphasizes tracking identified risks, not only offline scores |
| Agent observability | **Partial** | Add privacy-aware traces, tool/latency/cost/evaluation dimensions; OpenTelemetry [GenAI conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) are useful but evolving, so version them explicitly |
| Core Web Vitals engineering | **Good in lab, unproven in field** | Fix CLS and collect p75 LCP/INP/CLS by route/device/release |
| WCAG 2.2 accessibility | **Currently failing tested criteria** | Fix contrast, scroll access, and focus order; combine automation with manual keyboard/assistive-technology checks |
| Security headers and public showcase hardening | **Strong** | Maintain route CSP tests and deployment verification |
| SSRF-resistant URL tools | **Partial** | Validate redirect/connection/egress threat model with adversarial tests |
| Supply-chain provenance | **Partial** | SBOM, signed image digest, attested build provenance, verification before deploy |
| Discoverability of a JavaScript SPA | **Good route metadata, incomplete raw content** | Fix deployed project-index head handling, enrich root, prerender if acquisition justifies it |
| Release governance | **Weak at the current snapshot** | Green main/nightly, deployment parity, explicit rollback and release evidence |
| Product/conversion measurement | **Early** | Measure CTA-to-inquiry completion without collecting sensitive message content |

The project does not need a framework migration to become more current. React 18, a single VPS, and a deliberately simple contact flow can all be valid choices. Higher-value SOTA alignment comes from evaluation quality, observable behavior, accessible interaction, provenance, and verified delivery.

## 9. Prioritized remediation plan

Effort estimates are ideal engineer-days for someone familiar with the repository; they exclude waiting for external data and should be revised after root-cause triage.

### P0 — release blockers, 0–3 days

| ID | Action | Effort | Acceptance criteria |
|---|---|---:|---|
| **P0-1** | Restore the Project 12→13 feature-selection/feature-contract artifacts through the documented DVC path | 1–2 d | Clean-checkout release verification exits 0; both artifacts exist intentionally; selected features match; regeneration is documented; current main CI passes |
| **P0-2** | Fix light-theme text contrast and report table keyboard access | 1–2 d | All 72 axe states pass; normal text contrast meets 4.5:1; keyboard users can focus and scroll report tables; visible focus verified manually |
| **P0-3** | Triage nightly failures and restore gate governance | 1–3 d initial triage | Root causes and owners recorded; fixes verified by scheduled green runs; duplicate issues closed/deduplicated; no bypass or silent quarantine; deployment requires required green checks |

### P1 — user-facing correctness and release assurance, week 1–2

| ID | Action | Effort | Acceptance criteria |
|---|---|---:|---|
| **P1-1** | Bake report/demo/breadcrumb availability into first paint | 1–2 d | Three repeated mobile runs per representative detail route have CLS ≤0.1, target ≤0.05; report link never inserts a late row; all report-bearing projects covered |
| **P1-2** | Correct initial-mount focus behavior | 0.25–0.5 d | Fresh-load first Tab focuses “Skip to content”; client navigation focuses main; hash behavior and announcements still pass browser tests |
| **P1-3** | Deploy only a green revision and verify parity | 0.5–1 d | Live health identifies the intended SHA; 55-question RAG story and `/projects` raw head are live; smoke/link/axe/performance checks pass; rollback artifact recorded |
| **P1-4** | Harden exporter provenance | 1–2 d | Manifest records tracked/ignored/untracked status; runner artifacts excluded by default; outside-Git execution fails clearly; automated tests cover exclusions, dirty state, sidecars, history, and commit ranges |
| **P1-5** | Add privacy-preserving field Web Vitals | 1–2 d | p75 LCP/INP/CLS visible by route, mobile/desktop, and release; no message content or unnecessary persistent identifier; CSP-compatible endpoint and retention documented |

### P2 — assurance, discoverability, and depth, weeks 2–6

| ID | Action | Effort | Acceptance criteria |
|---|---|---:|---|
| **P2-1** | Standardize metrics `_meta` provenance | 2–4 d | Versioned schema validates all 13 projects; Git/lock/data/params/seed/timestamp identity present or explicitly justified; report renders provenance |
| **P2-2** | Add SBOM, keyless image signing, and build provenance | 1–3 d | Release emits SBOM and signed digest/provenance; deployment verifies expected identity/digest; verification and rollback runbooks pass a drill |
| **P2-3** | Complete raw root/project-index SEO and structured data | 2–4 d | Raw HTML has correct canonical/title/H1/summary and valid structured data; rendered and raw routes agree; sitemap dates reflect content changes |
| **P2-4** | Reduce detail/demo waterfalls and unused assets | 2–4 d | No avoidable sequential registry/story/report chain above the fold; route budgets hold; repeated lab LCP/CLS and field trends improve without removing functionality |
| **P2-5** | Harden public Agent Chat deployment | 2–5 d | Production auth fails closed; per-user session authorization/rate limits audited; redirect, DNS-rebinding, connection-pinning and egress tests pass; secrets never enter browser variables |
| **P2-6** | Add agent tracing and ongoing evaluation telemetry | 3–7 d | Versioned trace schema covers tool calls, latency, tokens/cost, approval and failure category; sensitive content redaction and retention tested; eval trends are release-visible |

### P3 — strategic refinement

| ID | Action | Effort | Acceptance criteria |
|---|---|---:|---|
| **P3-1** | Improve conversion measurement and optionally direct scheduling/form flow | 2–5 d | CTA-to-inquiry funnel measured without sensitive content; any direct endpoint has anti-spam, privacy, delivery monitoring, and ownership |
| **P3-2** | Review oversized modules by responsibilities and change coupling | 3–8 d, incremental | seams and tests improve; no behavior change; avoid size-only splits |
| **P3-3** | Deepen project challenger arms and evaluation protocols | Ongoing | Each addition uses the same sealed/scored-once harness and reports quality, uncertainty, latency/resource cost, and negative results |
| **P3-4** | Consider prerendering and visual-regression coverage | 3–6 d | Core routes have stable HTML and screenshot diffs; build remains reproducible; decision supported by SEO/performance evidence |

## 10. Recommended release sequence and measurable outcomes

### First 72 hours

1. Freeze nonessential feature merges.
2. Restore the Project 12→13 contract and make the release gate green.
3. Fix the two axe violation classes and initial focus behavior; run the complete matrix plus manual keyboard checks.
4. Triage nightly root causes and deduplicate the issue stream.
5. Stabilize first-paint project headers and rerun mobile CLS checks.

### Next release

1. Run all required checks on the exact release commit.
2. Build/sign/verify the release artifact if supply-chain work is ready; otherwise record it as an explicit remaining assurance gap.
3. Deploy with a known rollback image.
4. Verify production SHA, RAG content, raw `/projects` metadata, health/readiness, internal links, accessibility, and repeated performance runs.
5. Enable field measurement and compare by release rather than relying on one Lighthouse score.

### Scorecard for the next audit

| Outcome | Evidence required |
|---|---|
| Release governance restored | Green required checks on release SHA; nightly root causes closed; no recurring duplicate failure issues |
| Source/production parity | Live build SHA equals approved release; rollback tested |
| Accessible core journeys | Zero violations in the complete automated matrix plus documented manual keyboard/reflow checks |
| Stable case-study rendering | Lab CLS target met repeatedly and field p75 CLS ≤0.1 when enough traffic exists |
| Real-user responsiveness | Field p75 LCP ≤2.5 s and INP ≤200 ms by device class, with small-sample caveats |
| Stronger RAG grounding | Independent sealed stress set shows reduced unsupported-claim rate without correctness/refusal regression; cost and p95 latency reported |
| Traceable ML artifacts | Common provenance schema validates across all projects |
| Verifiable software supply chain | SBOM, signature, provenance, and deploy-time verification available for the released digest |
| Collaboration handoff assurance | Clean export contains only intended files and distinguishes tracked from ignored/untracked payload |
| Product outcomes | Privacy-safe CTA/inquiry measurements; no unsupported revenue or ranking claims |

## 11. Final conclusion

The repository is already well beyond a typical portfolio in engineering discipline, evaluation honesty, and reusable application depth. The live site is fast at the entry point, functional, secure at the HTTP layer, and materially improved since the earlier audit. The new RAG evaluation is especially valuable because it identifies a precise grounding bottleneck rather than presenting an unqualified win.

The current gap is **verification closure**. Strong gates exist, but the current release and accessibility gates are red and that revision nevertheless reached production; automated accessibility sampling previously missed systematic light-theme and keyboard defects that remain reproducible; and the exporter’s clean flag is weaker than full Git provenance.

Closing P0 and P1 should produce a defensible production release without a large architectural rewrite. After that, the highest-return investments are field measurement, uniform artifact/build provenance, accessible and stable first paint, independent agent/RAG stress evaluation, and carefully measured conversion—not adding more surface area for its own sake.
