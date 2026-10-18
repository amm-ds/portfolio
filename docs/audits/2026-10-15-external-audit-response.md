# External Audit Response — 2026-10-15

Two independent audits landed on 2026-10-15: a **file-level code audit** (7.1/10 overall;
claims-integrity 5.0) and a **senior-positioning audit** (8.2/10 concept). Every finding
with its status. Audits are a gift — disagreements are noted with reasons.

## Claims integrity (the file-level audit's core concern)

| Finding | Status |
|---|---|
| Project 09 documented as working but a 54-line stub **in the repo** | **Fixed within the hour** — the full implementation existed locally but had never been swept into a commit (orchestration miss, not fabrication). Committed and pushed: toolsets, pydantic-graph workflow, HITL, pydantic-evals suite, 44 tests, real metrics. Docs and code now match. |
| README says 7 projects; repo/docs list 9 | **Fixed** — README states "8 working showcases + 1 planned". |
| "~97% coverage" (libs-only gate) | **Fixed** — per-package wording; CI now runs a second pass enforcing projects+apps ≥55% alongside libs ≥80% strict. |
| 06 gap "vs published optima" (best-known ≠ optimal; vehicles not compared) | **Fixed** — all 56 instances carry SINTEF distance+vehicle references; dual-gap reported; the audit's prediction confirmed: vehicles-first ranking puts ALNS at 43/56 (not 56/56), and both directions are disclosed. |
| "Reproduces from a clean clone" overclaimed (figures gitignored, no DVC remote) | **Partially addressed** — README statics now show results without any run; regenerate-locally contract stands per ADR-0003 (DVC remote consciously declined below). |

## Engineering (file-level audit)

| Finding | Status |
|---|---|
| Frontend never tested in CI; mypy libs-only | **Fixed** — ci.yml runs npm ci/test/build and mypy over libs+projects+apps. |
| Vendored `vendor/libomp.dylib` + import-time hack | **Fixed** — binary removed from the repo; documented prerequisite + actionable import error; the previously-segfaulting e2e passes unskipped. |
| God-module evaluate.py files (06 complexity 53; 01 1,074 lines) | **Fixed** — 01 → evaluate/figures/reporting (71 tests unmodified); 06 → evaluate/figures/reporting + solver/construct/routing, full pipeline rerun with identical numbers. |
| 57 `type: ignore` (~190 `Any`) concentrated in 01/04/05 | **Fixed (majority)** — 05: 13→6, 04: 17→6, 01: 10→5, with reason comments and typed re-export shims. |
| Supply chain: no dependabot/CodeQL/audit | **Fixed** — dependabot (pip/npm/actions), CodeQL (python+TS), pip-audit CI step. |
| Notebooks thin (4 code cells, no outputs) | **Conscious convention** — cleared outputs are deliberate (review diffs stay readable); each notebook is an execution-verified walkthrough, and the README statics now carry the visual load. |
| Seniority signal: 4-day burst, no PRs/issues | **Noted** — moving to PR-based flow post-launch; the audits themselves are being answered in public, which is the practice being asked for. |
| Commissioning brief published, "built to impress" framing | **Addressed earlier** — marked historical, removed from nav; a first-person "How this was built" note is **scheduled (wave 12 follow-up)**. |

## Positioning audit (senior roles)

| Recommendation | Status |
|---|---|
| 07/01 rank #1/#2 — sharpen, don't add | Agreed — wave 12 invests in these (01 module split; 06 sharpening; 07 already served live). |
| Build **08 LLM inference & serving** first | **Scheduled (wave 13)** — both audits' #1; scaffolding exists. |
| Decision-science project (uplift/fraud) as differentiator | **Candidate (wave 13/14)** — the audit's #2/#3 ideas (uplift modeling, Spanish RAG) match the gap report; ranked after 08/09 hardening. |
| Lead README with problem→evidence→trade-off; visuals before inventory | **Partially fixed** — README statics table at the top (wave 12); fuller restructure **scheduled**. |
| Hosted demo | **Scheduled with the Hetzner deploy** — deploy pack ready (`deploy/DEPLOY.md`). |

## Consciously declined (with reasons)

- **DVC cloud remote** — the regenerate-locally contract (ADR-0003) is a deliberate
  reproducibility stance; a free-tier remote is a cheap future add if visitor bandwidth
  demands it.
- **Stored notebook outputs** — convention over preview convenience (see above).
- **PNG/GIF replacing interactive figures** — statics complement per ADR-0005.

## What the audits got wrong or couldn't verify

- "Not verified: that ruff/mypy/pytest pass" — CI runs all of them on every push
  (now including frontend tests); the green runs are public.
- The 09 "docs overclaim" was an orchestration bug (uncommitted work), now fixed —
  the results were real and reproducible from the first landing.
- "Breadth 7.5 — no causal/serving/streaming" — correct; that is exactly the
  productization gap report's build order (08 serving → drift observatory → uplift).

*Updated as wave-12 items land.*

## Second pass (2026-10-16 audit, repo at e1986d1 → 175bbe3) — status

Point-by-point response to the second-pass findings. P0 items landed
2026-10-16 in commits `7142f45` (docs/CI/README/06 relabel), `4de464f`
(07 drift observatory), `2d10528` (10 CIs + honest headline), `e68f366` +
`175bbe3` (all-ten project-page curation).

| Second-pass finding | Status |
|---|---|
| Weekly drift workflow calls a missing command | **Fixed** — `mobility.cli drift-check --month … --fail-on-regression` shipped (drift.py + 9 tests), wired to the Thursday schedule; 2024-11 wiring check at +8.2% MAE (in-window; real value starts with unseen months) |
| 06 OR-Tools arm not independent | **Fixed (relabel)** — "external reference/yardstick" wording removed everywhere; now stated as an ALNS-hinted incumbent-improvement probe that ties 56/56 with no improvement. Unhinted comparison (PyVRP / routing at equal budget) kept as a deferred roadmap item |
| 06 headline not like-for-like | **Fixed** — root README leads with dual criteria (distance 4.23% + vehicles +3.73, 43/56 vehicles-first); "56/56" no longer the public headline |
| README + 01 docs page lag results | **Fixed** — README regenerated with 9 projects and current numbers (04: 0.9460; 02: track-corrected; 03/05 real-data leads; 08/09/10 rows); 01 docs page now carries the 65-question golden set |
| 10 headline weaker than framing | **Fixed** — paired bootstrap CIs (n=1000): Qini ranking NOT established (diff CI [−8.18, 9.52] spans zero), profit advantage IS ([−$3,617, −$48]); mail-everyone ($16,103) stated as the profit maximum at $0.01/email with concentration as the targeting value; cost-grid break-even ≈$0.30/email; `$114` relabeled revenue_per_conversion; discarded statements removed |
| 08/09 thin results | **Fixed** — both built and run on the hosted provider (08: 19-cell author benchmark + serving-economics ladder; 09: full 15-task graded suite, per-call tool capture, cost ledger, held-out task set reported separately, exact-set tool selection iterated to 15/15 on the tuning set with the held-out set as the honest generalization check); remaining per roadmap: second serving stack + repeat runs (08) |
| CI soft spots (`\|\| true`, mixed coverage, no S rules) | **Fixed** — pip-audit can now fail the build; projects/apps coverage pass overrides addopts; ruff S (bandit) rules enabled with justified per-file ignores (tests assert by design; trusted-artifact pickle persistence) and proper fixes elsewhere (2026-10-18) |
| Giant orchestration functions (06 run_evaluate, 01 evaluate.run); mypy strict per project; broad except handlers | **Fixed (2026-10-18)** — 06 decomposed to typed stage functions (entrypoint complexity 2, byte-identical metrics) and 01 to 7; ruff C901 enforced at max-complexity 15 repo-wide with zero noqas; strict mypy extended to 02/06/08/09/10 (zero new ignores needed); all 20 broad excepts narrowed to specific exceptions or logged-and-justified at LLM/network boundaries |
| Public metrics/figures not fetchable without DVC remote | **Addressed (wave 15)** — render specs, serving bundles, `metrics.json`, and `report.html` are committed to git (`164a5eb`), so a fresh clone fetches them and the built app serves them without `dvc pull`; served model artifacts for 02/05 (`7d20032`) and the forecast/score/solve endpoints (`b43b154`) build on that. The declined-remote stance stands only for bulky raw data now |
| Project pages: verbosity, figure linkage, up-to-date numbers | **Fixed** — all 10 stories rewritten to the intro → bullets/tables/mermaid → conclusion → **Business implication** pattern, every eda/evaluation/results section tied to an existing figure, stale numbers reconciled against reports/metrics.json (incl. 01 retrieval headline moved to the 65-q set: 0.831 vs 0.031; 02 track correction; 05 synthetic-as-primary drift) |

*Updated 2026-10-16 as second-pass items land; 2026-10-18: wave-15 serving/artifacts commits (`7d20032`, `b43b154`, `164a5eb`) close the metrics/figures-without-remote row above.*

## Third-party pass (2026-10-18, external review of repo + live site + website)

| Finding | Status |
|---|---|
| Live website behind the repository ("Pages deployed once, 12 Oct"; index shows 7 projects, 08 planned) | **Disproved at review time** — GitHub Pages deployments were running on every push (verified via the deployments API) and the live `/projects/` index reads "Ten showcases" with real-data headlines (curl-verified). The review's source snapshot predated those fixes. |
| Metrics drift between layers (README 0.962 vs report 0.831/0.600; MAE 8.53 vs 8.989) | **Fixed in source earlier this wave** — README row 01 leads with the 65-q tuning + held-out distinction; row 02 carries the UCI champion 8.989. A full results registry was evaluated and **declined as overkill**: consistency is enforced by the full-repo audit validator (dupes/mentions/budgets/roadmaps) run every wave. |
| React showcase not publicly accessible | **Pending the user's hosting decision** — the one-command VPS path is in `deploy/DEPLOY.md`, now with free-tier alternatives (Render/Fly/Oracle) documented. A public demo requires a host; nothing else blocks it. |
| SECURITY.md missing | **Fixed** — `SECURITY.md` at root (advisories route, response expectations, scope notes; linked from README). The private-reporting repo toggle is not API-enableable on this account, so the policy routes through draft Security Advisories, which are private by default. |
| Browser-level smoke tests missing | **Partially fixed, rest declined for CI cost** — the docker smoke job now asserts SPA deep links (`/projects/:id`, `/services`) and a live metrics API response. Full Playwright runs were evaluated and deferred (~3 min per CI run against already-high unit/build coverage); noted here instead of half-built. |
| CI release discipline / in-progress runs | **Fixed** — the two red runs traced to real bugs (ruff-format nit; `torch.mps.empty_cache()` unguarded off-MPS) fixed at source; runs after the fixes are green. Actions are now pinned to commit SHAs across all workflows (dependabot keeps them current). |
| Case-study visual structure + per-project improvements (alert-budget/targeting simulators, promote held-out story) | **Mostly already in place** (03's alert-budget curve, 01's held-out-as-lead, Business-summary cards, ≤3 referenced figures per section). Interactive simulators are **declined as engagement-gated features**, consistent with the roadmap policy. |
| Client-first landing + frictionless contact | **Fixed** — `docs/index.md` now leads with positioning, two flagships, three measured results and a contact CTA (ADRs/runbooks remain in nav); the contact page and README offer a direct pre-filled inquiry link. A public email address is not on file — the user can drop one into the contact page in a single edit when ready. |
