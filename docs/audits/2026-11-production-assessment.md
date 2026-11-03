# Production Assessment — 2026-11-03

Whole-repo audit of code quality, documentation, infrastructure, and
productization level. Branch audited: `main`. Read-only investigation; the only
file written is this report. Every claim below carries file:line evidence or a
command that was run (see Appendix A for the verification log).

**Scores at a glance**

| Dimension | Score | One-line justification |
|---|---|---|
| Code quality | **9/10** | 100 % annotated functions, strict-typed libs, ~805 meaningful per-project tests with seeded determinism and a nightly byte-identity job; deductions only for thin/flaky edges. |
| Documentation | **8/10** | README/docs numbers reconcile to committed `metrics.json` to the cent and are machine-gated; deductions for a dual-canonical identity, one stale contract comment, and a binary doc in the docs tree. |
| Infra | **8/10** | Path-filtered CI matrix with real serving smoke, hardened compose, pinned actions, CodeQL + gitleaks + dependabot, and a genuinely impressive nightly suite; deductions for non-blocking lint/a11y gates, no external monitoring, and an empty DVC remote config. |
| Productization | **7/10** | Clean clone serves a functional app (verified live), demo contracts are checked in CI, and offline rebuilds are nightly-proven; deductions because the configured public domain has zero DNS records and several "production" claims rest on manual ops. |

No P0 findings. The repository is release-grade software with a
go-to-market gap (domain) rather than an engineering gap.

---

## 1. Code quality — 9/10

**Justification:** Every one of 1,542 source functions across
`projects/*`, `libs/*`, and `apps/showcase-api` carries annotations (AST scan,
0 unannotated); `mypy libs projects apps` passes with zero issues in 164 files;
ruff (`E,F,I,UP,B,SIM,RUF,S,C901`) and ruff-format are clean over 405 files;
test suites are behavior-shaped (schema rejection tables, parity tests,
golden-set evals), not tautological; determinism is a designed contract
(`seed: 42` in every `params.yaml`, nightly run-twice byte-identity job in
`.github/workflows/nightly.yml:32-69`).

### Findings

**P1 — none.**

**P2-1 · Project test suites flake when the monolith is run wider than CI's
per-project `-n 2`.**
Evidence: a local `pytest projects -n 4` run failed exactly one test,
`projects/04-nlp-classification/tests/test_calibration.py::test_temperature_recovers_known_scale`;
the same test passes in isolation and under the CI invocation
(`cd projects/04-nlp-classification && pytest -n 2` → 78 passed). Root cause
is torch/MPS thread contention under cross-project xdist, not test logic.
Recommendation: keep the per-project matrix as the supported shape (it is),
and add a short comment in `pyproject.toml`'s `[tool.pytest.ini_options]`
(near the existing `--import-mode` note, `pyproject.toml:86-91`) that the
monolithic run is validated at `-n 2` only, so a future "speed up CI" change
doesn't trip this.

**P2-2 · One near-tautological test and uneven per-project coverage floors.**
Evidence: `projects/08-inference-serving/tests/test_scaffold.py:1-3`
(`assert inference_serving is not None`) — the rest of 08's suite (364 lines:
`test_bench_math.py`, `test_fake_server.py`) is genuinely good, so this is
cosmetic. Separately, 04's heaviest modules measure `evaluate.py 54 %`,
`hpo.py 30 %`, `epochs_probe.py 64 %` (measured locally with `--cov=src`);
there is no per-project floor by design (`ci.yml:263-276` reports coverage
"for visibility without a per-project gate"), and the hard 80 % gate covers
only `libs` (`pyproject.toml:97-98`).
Recommendation: replace the scaffold test with an assertion that the CLI entry
point imports and exposes its commands; either accept 04's training-path
coverage as deliberate (it is exercised by DVC stages instead) or add one
integration test at the `evaluate` stage boundary so the lowest-covered
module has a smoke net.

**P2-3 · Pre-commit gates less than CI gates.**
Evidence: `.pre-commit-config.yaml:8-13` scopes mypy to `files: ^libs/`, so a
local commit can pass while project/app typing is broken; CI's
`mypy libs projects apps` (`ci.yml:99-101`) is the real gate. Ruff covers the
repo in pre-commit, so the exposure is typing-only.
Recommendation: either widen the pre-commit mypy `files:` to
`^(libs|projects|apps)/` (cost: slower commits) or add a one-line note in
`docs/engineering-playbook.md`'s Standards section that typing is enforced at
CI, not at commit time — the playbook currently implies both.

**P2-4 · Dependency pins are deliberate but drifting several minors behind.**
Evidence: locked vs PyPI-latest (checked 2026-11-03): fastapi 0.143.0 vs
0.162.0, starlette 1.7.0 vs 1.10.0, pydantic 2.14.1 vs 2.14.2, pydantic-ai
2.55.0 vs 2.65.0, transformers 5.19.0 vs 5.22.1, torch 2.14.1 vs 2.15.0,
polars 2.0.0 vs 2.1.0, ragas 0.3.1 vs 0.4.3, langchain-community 0.3.31 vs
0.4.2. The repo's stated policy is "bump deliberately, not casually"
(`Dockerfile:17-18`), dependabot is configured weekly
(`.github/dependabot.yml`), and CI runs `pip-audit --strict`
(`ci.yml:129-135`) — but pip-audit could not be executed in this audit
environment (host `ensurepip` crash), so the vulnerability gate's current
state is unverified here.
Recommendation: confirm the latest CI run's pip-audit step is green, and
schedule one deliberate bump wave for the serving-critical pair
(fastapi/starlette) before pointing the custom domain at the deployment
(see INFRA-1), since that pair is the public attack surface.

**P2-5 · Dead code is effectively zero; one benign exception.**
Evidence: a vulture pass (≥90 % confidence) over all `src/` trees found only
pydantic-validator `cls` bindings and one unused tuple unpack
(`projects/07-open-data-mobility/src/mobility/geo.py:31` `cfg_key`,
`projects/02-demand-forecasting/src/demand_forecasting/evaluate.py:195`
`y_val`). Zero `TODO`/`FIXME` in any `src/` tree.
Recommendation: replace the unused unpacks with `_` at next touch; no sweep
warranted.

**Shared-code reuse (positive):** all ten projects depend on
`portfolio-core`/`portfolio-eval` via workspace sources; the API composes
02/05/06 as libraries (`apps/showcase-api/pyproject.toml:11-18`) with a
deliberately narrow install in the image (`Dockerfile:74`). The one
cross-project dependency that deserves a watch is
`projects/09-agentic-workflows`'s dependency on `01-rag-agent`
(`projects/09-agentic-workflows/pyproject.toml:18-26`), which drags
sentence-transformers/faiss/ragas into 09's environment — justified by the
documented read-only-index arm, but it makes 09 the second-heaviest install
in the workspace.

---

## 2. Documentation — 8/10

**Justification:** This is the strongest documentation surface of the repo:
the README's per-project numbers reconcile against committed
`reports*/metrics.json` to the cent (spot-verified 10: T-learner Δprofit
+$2,812 matches `projects/10-uplift-experimentation/reports/metrics.json`;
03's synthetic-vs-NAB distinction matches both `metrics.json` and
`nab_metrics.json`), and drift is machine-gated by
`scripts/check_short_copy.py --check` ("40 surfaces across 10 stories"),
`scripts/gen_route_manifest.py --check`, and
`scripts/gen_static_registry.py --check` — all green locally. Every dataset
has a card with license/terms/snapshot/checksum (`docs/data-registry/index.md`
enumerates 10; cards for AG News and NSL-KDD honestly note research-only
terms). Runbooks exist for the three incident classes (drift, LLM cost,
pipeline restore under `docs/runbooks/`), and seven ADRs back the platform
choices.

### Findings

**P1-1 · Dual-canonical public identity, and the custom domain does not
resolve.**
Evidence: the SPA's central config defaults to
`https://alejandromerida.dev` (`apps/showcase-web/src/config.ts:11`), and that
domain is baked into `index.html` canonical/OG/Twitter tags
(`apps/showcase-web/index.html:8,15-37`), `public/robots.txt:4`,
`public/sitemap.xml:2`, and `scripts/gen_sitemap.py:20`. DNS check on
2026-11-03 (1.1.1.1 / 8.8.8.8): the domain is registered with Cloudflare NS
(`lisa.ns.cloudflare.com`, `trey.ns.cloudflare.com`) but publishes **zero
A/AAAA/CNAME records** — nothing answers. Meanwhile the actually-live surface
is GitHub Pages: `https://amm-ds.github.io/portfolio/` returns 200 and is what
README.md:9,106 and mkdocs advertise. So every default build (local
`npm run build`, the Dockerfile's default `ARG VITE_SITE_URL`,
`Dockerfile:21,33`) emits canonical/OG/sitemap metadata pointing at a
dead domain.
Recommendation: decide the launch identity. Until DNS is live, flip the
default in `config.ts`/`gen_sitemap.py`/`index.html` to the GitHub Pages URL
(the same value the Dockerfile and mkdocs already use), or publish the apex
record. This is the single highest-leverage productization fix.

**P1-2 · `docsUrl()` in the web app hardcodes the dead domain and bypasses the
build-time override mechanism.**
Evidence: `apps/showcase-web/src/pages/ProjectDetail.tsx:27-31` builds
`https://alejandromerida.dev/projects/...` from the project id instead of
using `DOCS_URL`/`absoluteUrl()` from `config.ts:30,48` — the exact config
the Dockerfile parameterizes via `VITE_SITE_URL`. Any non-default build (the
stated purpose of the ARG) still links case studies to the wrong origin.
Recommendation: reimplement as `${DOCS_URL}/projects/${num}-${slug}/` (with
base-path handling via `absoluteUrl`) and add a copy-guard assertion to
`apps/showcase-web/src/__tests__/copy-guard.test.ts` so no hardcoded origin
re-enters the source.

**P2-1 · Stale "mock provider" comment contradicts the no-mock-provider
decision.**
Evidence: `docker-compose.yml:10` says "mock provider is the default";
README.md:118-121, `.env.example:3-4`, and `deploy/DEPLOY.md:81-87` all state
the opposite ("there is no production mock provider"). Behavior matches the
docs (01 without env uses Ollama; chat disabled) — the comment is the stale
surface.
Recommendation: one-line fix in `docker-compose.yml` to "unconfigured
Project 01 uses local Ollama; chat stays disabled without RAG_CHAT_ENABLED=1".

**P2-2 · mkdocs SEO metadata still on the GitHub Pages URL while the web app
claims the custom domain.**
Evidence: `mkdocs.yml:3` (`site_url`), `:42-43` (`card_url`, `page_url`) all
`amm-ds.github.io/portfolio`. Same decision as P1-1: once the identity is
decided, update both sides together; until then the docs side is at least
internally consistent.

**P2-3 · A binary review report lives in the docs tree.**
Evidence: `artifacts/review/Portfolio_Review_Report_amm-ds.docx` (and the markdown sibling
`docs/portfolio_audit_amm-ds.md`) sit under `docs/`; mkdocs excludes both via
`mkdocs.yml:45-47`, so they only add clone weight and cannot be diffed.
Recommendation: move the `.docx` to a release asset (or `artifacts/`, which
is gitignored) and keep the derived markdown if it has unique content;
otherwise archive both under `docs/audits/` with the same superseded-header
convention `docs/audits/productization-gap-report.md` uses.

**P2-4 · The engineering playbook overstates the pre-commit story (see CQ-3).**
Evidence: `docs/engineering-playbook.md` Standards 1-2 say types and lint are
"enforced by pre-commit and CI"; mypy-in-pre-commit is libs-only
(`.pre-commit-config.yaml:13`). Recommendation: align the sentence with the
mechanism.

**Positive:** `test_readme_numbers.py` in 02 gates README figures against
regenerated reports; `lint_story_language.py` enforces plain language over
`projects/*/story.yaml` (10 stories, 0 errors/warnings); every project README
carries a "which track these metrics come from" honesty note consistent with
`RELEASE-NOTES.md:6-12`; the 2026-10-15 gap report is explicitly marked
superseded rather than silently stale.

---

## 3. Infrastructure — 8/10

**Justification:** CI is a path-filtered pipeline (`ci.yml`) whose `gate` job
runs ruff, the demo-contract checker, story lint, short-copy freshness, route
manifest + static-registry freshness, full-tree mypy, web install/test/build,
a 250 KB-gzip bundle budget, strict mkdocs, and `pip-audit --strict` — all
blocking. The `tests` job splits 13 matrix cells per project (deliberately
sized so each stays under ~15 min on free runners, `ci.yml:217-276`), and the
`docker` job builds the image and smoke-tests deep links, JSON APIs, and real
02/05/07 inference responses built from committed serving metadata
(`ci.yml:278-375`). The nightly workflow adds run-twice byte-identity for 02's
M5 track, a ×1000-example hypothesis pass with a fresh nightly seed, a 3-minute
container soak that proves the 429 path and zero-5xx contract, offline regrade
sweeps for 08/09, a weekly rotating `dvc repro -f`, and monthly heavy pipelines
for 07/01 — with failure-summary issues. Actions are pinned by SHA, dependabot
covers pip/npm/actions weekly, CodeQL runs both language matrices weekly,
gitleaks is in pre-commit, and the production compose is hardened
(read-only rootfs, tmpfs /tmp, `cap_drop: ALL`, `no-new-privileges`, CPU/RAM
limits, log rotation, unpublished API port, Caddy-pinned-by-digest) with a
Caddyfile carrying a considered security-header set
(`deploy/Caddyfile:17-38`) and a documented trusted-proxy boundary
(`deploy/DEPLOY.md:155-165`).

### Findings

**P1-1 · No external monitoring or alerting for the public deployment.**
Evidence: the only runtime health signals are the in-container healthcheck
(`deploy/docker-compose.prod.yml:45-49`), `/health` + `/ready`
(`apps/showcase-api/src/showcase_api/main.py:146-173`), and Docker log
rotation with *manual* off-host shipping (`deploy/DEPLOY.md:124-139`). GitHub
workflows "stop at notifications/artifacts; none of them reaches the VPS"
(`deploy/DEPLOY.md:141-153`). A dead VPS, expired TLS, or a filled disk is
discovered by a visitor, not by the operator.
Recommendation: add the cheapest possible external probe (e.g. a scheduled
GitHub Actions curl of `https://$DOMAIN/health` + TLS-expiry check that files
an issue on failure) — it reuses the existing notify pattern and does not
contradict the manual-deploy boundary.

**P2-1 · Lint, a11y, and link checks are non-blocking by declaration.**
Evidence: `ci.yml:137-154` (eslint `continue-on-error: true`), `:156-199`
(axe, non-blocking), `:201-215` (lychee, non-blocking). The committed
`reports/axe.json` snapshot shows 1 moderate violation on `/`
(`region` landmark — content outside any landmark) plus per-route results.
This is a stated "this wave" posture, but it has no tracking issue visible in
the repo.
Recommendation: file/plan the "make eslint + axe blocking" wave (the comment
says "becomes a required gate in a later wave" — give it a date), and fix the
single `region` violation so the axe snapshot goes to zero.

**P2-2 · `.dvc/config` is an empty file — no remote, no cache.**
Evidence: `.dvc/config` is 0 bytes; `RELEASE-NOTES.md:43-48` documents "no
cloud remote assumed, per ADR-0003". Reproducibility therefore depends on the
public source URLs staying live (registry manifests pin etags,
`registry/*.dvc`), and `dvc pull` is a no-op for pipelines. This is a designed
boundary and ADR-backed — the risk is only that a dead upstream URL silently
breaks `dvc repro` for whoever clones in two years.
Recommendation: none required; optionally record the "sources must stay live"
assumption in `docs/architecture/adr/0003-dvc-pipeline-reproducibility.md`'s
consequences if it is not already there.

**P2-3 · In-process rate limiter and live-call budget reset on restart.**
Evidence: `apps/showcase-api/src/showcase_api/middleware.py:5-17` documents
the limitation honestly (single process, not DDoS protection, NAT sharing);
`LiveGuard` (`main.py:475-510`) is likewise in-memory per process. Under the
single-container topology this is sound; it only becomes a liability if the
"future hybrid split" mentioned in `deploy/DEPLOY.md:9-11` ships without
revisiting these guards.
Recommendation: add one line to DEPLOY.md's hybrid-split paragraph naming the
rate limiter / live budget / IP-hash salt as components that need a shared
store in any multi-replica topology.

**P2-4 · Secrets and env discipline are clean, with one soft edge.**
Evidence (positive): no hardcoded secrets found by pattern sweep;
`.env` is gitignored (`.gitignore:59`); `.env.example` documents every
variable with honest "cloud-equivalent" cost labeling; prod compose requires
`IP_HASH_SALT` (`deploy/docker-compose.prod.yml:12`) and the middleware warns
once when the public `dev-salt` fallback is in use
(`middleware.py:192-219`); Caddyfile/compose have no placeholder hostnames.
Soft edge: the built-in default salt `dev-salt` is baked into the image and
only a WARNING separates it from production-grade hashing.
Recommendation: keep as is (the WARNING + compose `:?` guard are the right
layered posture); optionally fail startup (not just warn) when
`IP_HASH_SALT` is unset and `BUILD_SHA != "dev"`.

**Caching:** uv cache + npm cache are enabled in CI (`ci.yml:63-65,146-149`);
the Docker build benefits from layer caching of `uv.lock` and the npm
`ci` layer (`Dockerfile:37-42`). Nothing to fix.

---

## 4. Productization — 7/10

**Justification:** The clean-clone story is real and was verified, not
assumed: all ten projects commit their serving-visible artifacts
(9–70 files each under `reports*/`), the demo payloads exist
(`02 reports_m5_full/demo_payload.json` 395 KB, `05 reports/demo_payload.json`
25 KB) and pass `scripts/check_demo_contract.py`, `uv lock --check` is
current, and a locally booted uvicorn answered `/health` 200
(`ready: true`), `/ready` 200, `/projects` JSON, `/demos` JSON, and a real
`POST /projects/05-ml-pipeline-churn/score` (churn_probability 0.0581, alarm
false at the 0.175 threshold) from the committed example row. RAG chat fails
closed (route unregistered → 405 when `RAG_CHAT_ENABLED` is unset,
`main.py:1018-1050`), matching DEPLOY.md. The nightly jobs prove the deeper
claims: 02's M5 metrics + demo payload are byte-identical across runs, 08's
report and 09's grades re-derive byte-identically from committed records, and
weekly/monthly `dvc repro` rotations prove the pipelines still run. Serving
contracts evolve additively (07's `service` field is `Literal["yellow",
"green"] = "yellow"`, `main.py:576-591`), and the web client
(`apps/showcase-web/src/api.ts`) consumes exactly the routes the API serves.

### Findings

**P1-1 · The launch identity is unreachable (same root cause as DOC-1).**
The showcase app, sitemap, robots, and OG metadata default to
`alejandromerida.dev`, which has no DNS records; the live surface is the
GitHub Pages docs site, and the single-container app has no public home until
either DNS is published or the defaults flip. Until fixed, "public deploy:
deploy/DEPLOY.md" (README.md:10) is aspirational.
Recommendation: publish the apex `A`/`AAAA` (and `www`) records to the VPS,
or flip the build defaults to the GitHub Pages origin until launch day; then
re-run `scripts/gen_sitemap.py` and rebuild.

**P1-2 · No versioned API contract artifact.**
Evidence: contracts are pydantic models enforced at runtime and covered by
`apps/showcase-api/tests/test_api.py` (1,000+ lines, green), but there is no
committed OpenAPI snapshot or consumer-contract test that fails when a
response shape changes incompatibly; the docker smoke only probes three
endpoints' key fields (`ci.yml:360-374`).
Recommendation: commit an `/openapi.json` snapshot test (fetch spec in CI,
diff against golden, allow additive diffs only) or pin the three served
response models' JSON Schema goldens in `apps/showcase-api/tests/`. Cheap,
and it turns ADR-0002 from a convention into a gate.

**P2-1 · LLM-dependent evidence cannot be regenerated offline (documented,
but a real boundary).**
Evidence: 01's RAGAS/faithfulness numbers, 08's bench, and 09's hosted-run
grades need Ollama or a hosted key; CI deliberately runs with
`LLM_BASE_URL: ""` (`ci.yml:8-9`) and the Makefile's `release-verify`
requires a running Ollama. The repo mitigates this well (offline fallback
judges, committed run records for 09, committed bench records for 08), so the
boundary is explicit rather than hidden.
Recommendation: none blocking; consider recording in each affected README the
exact command + provider state that reproduces the headline numbers, the way
09 already does.

**P2-2 · Release process is manual end-to-end.**
Evidence: `deploy/DEPLOY.md:141-153` states nothing deploys automatically and
day-2 ops (RAG enablement, salt rotation, budget raises, rollback) are manual;
`RELEASE-NOTES.md` is a single v1.0.0 document; `make release-verify` checks
only that shipped projects have `metrics.json`. There is no tag, no
changelog automation, no signed release.
Recommendation: acceptable for a personal portfolio — but add a `make release`
checklist target (lint-ci + demo contract + short-copy + docker smoke already
exist as pieces) and a dated CHANGELOG section in RELEASE-NOTES.md so the
next wave has a release ritual to follow.

**P2-3 · Demo payload freshness is gated, but payload *regeneration* is not
scheduled.**
Evidence: `check_demo_contract.py` verifies existence, required keys, and
schema_version (and re-gates the static registry), and the nightly determinism
job re-runs 02's demo payload for byte-identity — but nothing re-runs the
payload stages on a schedule for 05 or after a pipeline change; a stale
payload would still pass the contract check.
Recommendation: add the 05 demo-payload stage to the nightly determinism job
(the CLI exists; it is one more run-twice `cmp` pair), matching what 02
already proves.

**P2-4 · `artifacts/playwright-m5/` (15 MB of screenshots) is gitignored but
undated and unexplained at the root.**
Evidence: `artifacts/` is ignored (`.gitignore:41`) yet sits in the working
tree with subdirs (`final-release`, `release-review`, `roadmap-closeout`,
plain-language variants) that read like decision evidence with no README.
Recommendation: add a two-line `artifacts/README.md` (or delete stale waves)
so the next auditor knows which snapshots are evidence and which are scratch.

### Release-readiness checklist (current status)

| Item | Status | Evidence |
|---|---|---|
| Tests green (libs + per-project matrix) | ✅ | libs+API 97 % coverage pass; 04 re-run 78 passed in CI mode; 1 flake only under non-standard `-n 4` |
| Lint + types + format gates | ✅ | ruff/format/mypy all green locally; same commands as `ci.yml` |
| Docs build strict | ✅ | `mkdocs build --strict` passes |
| Demo contract + copy + manifest freshness | ✅ | all four checkers green |
| Web: unit tests, typecheck, build, bundle budget | ✅ (with flake watch) | 350/350 on re-run; `tsc && vite build` OK; CI enforces ≤250 KB gzip index chunk |
| Docker image builds and serves from clean clone | ✅ | CI docker job; local boot verified all endpoint classes |
| Lockfile current | ✅ | `uv lock --check` resolved 333 packages, no changes |
| Vulnerability audit | ⚠️ | CI gate exists (`pip-audit --strict`); not re-verifiable in this environment |
| Public DNS for configured domain | ❌ | `alejandromerida.dev` registered, zero records |
| External uptime/alerting | ❌ | healthchecks + nightly workflows only; nothing watches the VPS |
| Versioned API contract gate | ❌ | runtime models + smoke only (see P1-2) |
| Release ritual (tag/changelog) | ⚠️ | RELEASE-NOTES v1.0.0; no tags/automation |
| Secrets hygiene | ✅ | gitleaks in pre-commit; no hardcoded secrets found; `.env` ignored; prod salt required |
| Reproducibility of evidence | ✅ | nightly byte-identity (02), offline regrades (08/09), rotating `dvc repro` (03/05/06/10 weekly; 07/01 monthly) |

---

## Consolidated fix list

### P0
*None.*

### P1
1. **Launch identity**: publish DNS for `alejandromerida.dev` (apex + www) or
   flip web defaults (`config.ts:11`, `gen_sitemap.py:20`, `index.html`,
   `robots.txt`, `sitemap.xml`) to the GitHub Pages URL; then regenerate the
   sitemap and rebuild. *(DOC-1 / PROD-1)*
2. **Fix `docsUrl()`** in `apps/showcase-web/src/pages/ProjectDetail.tsx:27-31`
   to derive from `DOCS_URL`/`absoluteUrl()` and add a copy-guard test against
   hardcoded origins. *(DOC-2)*
3. **Version the API contract**: commit an OpenAPI/JSON-Schema golden in
   `apps/showcase-api/tests/` that fails on incompatible response-shape
   changes. *(PROD-2)*
4. **External probe**: scheduled `health`/`ready` + TLS-expiry check from
   GitHub Actions that files an issue on failure (reuses the nightly notify
   pattern; does not touch the VPS). *(INFRA-1)*

### P2
5. Fix the stale "mock provider" comment in `docker-compose.yml:10`.
6. Align playbook/pre-commit typing claims (widen pre-commit mypy scope or
   document CI-only enforcement).
7. Add a comment guarding the supported pytest parallelism (`-n 2` per
   project) in root `pyproject.toml`.
8. Replace `projects/08-inference-serving/tests/test_scaffold.py` with a
   meaningful CLI surface test; optionally add one `evaluate`-stage smoke for
   04's lowest-covered modules.
9. Verify the latest CI `pip-audit` step is green; schedule one deliberate
   bump wave for fastapi/starlette before domain cutover.
10. Update mkdocs SEO URLs (`mkdocs.yml:3,42-43`) when the identity decision
    lands.
11. Move `artifacts/review/Portfolio_Review_Report_amm-ds.docx` out of the docs tree (or
    archive under `docs/audits/` with a superseded header).
12. Make the axe snapshot zero-violation (one `region` landmark on `/`), then
    schedule the "eslint + axe become blocking" wave the CI comments promise.
13. Add 05's demo-payload stage to the nightly determinism job (run-twice
    `cmp`), matching 02.
14. Note in DEPLOY.md's hybrid-split paragraph that the rate limiter, live
    budget, and IP-hash salt need a shared store in any multi-replica
    topology.
15. Add `artifacts/README.md` (or prune) for the 15 MB screenshot tree.
16. Decide on a release ritual: `make release` checklist target + dated
    changelog section in RELEASE-NOTES.md.

---

## Appendix A — verification log (commands run, 2026-11-03)

- `uv run pytest libs apps/showcase-api …` → **pass**, 96.66 % coverage vs
  80 % gate (`pyproject.toml:98`).
- `uv run pytest projects -q -n 4` (monolith, wider than CI) → 1 failure
  (`04 test_calibration.py::test_temperature_recovers_known_scale`); passes
  isolated and under CI's `-n 2` per-project invocation (78 passed).
- `uv run ruff check .` → All checks passed; `ruff format --check` → 405 files
  formatted.
- `uv run mypy libs projects apps` → Success, no issues in 164 files.
- `scripts/check_demo_contract.py` → OK (both demos + static registry);
  `check_short_copy.py --check` → 40 surfaces OK; `gen_route_manifest.py
  --check` → 21 routes OK; `gen_static_registry.py --check` → OK;
  `lint_story_language.py` → 0 errors/0 warnings; `lint_ci.py` → OK.
- `uv run mkdocs build --strict` → built clean.
- `npm test` (showcase-web) → first run 349/350 (1 flake,
  `StorySection.test.tsx` typing-timing); re-run 350/350; `npm run build` →
  OK (29 s; heavy chunks — plotly 4.8 MB / mermaid 686 KB — are lazy
  code-split; CI enforces the 250 KB-gzip index budget).
- `uv lock --check` → 333 packages, no changes.
- Local API boot (`uvicorn showcase_api.main:app`) → `/health` 200
  `ready:true`, `/ready` 200, `/projects` JSON index, `/demos` 200,
  `POST …/05-ml-pipeline-churn/score` 200 (real inference from committed
  `meta.json` example row), disabled `/rag/chat` 405, unknown path structured
  404. (An earlier `/ready` 404 was traced to a stale foreign server holding
  port 8123 — bind failure in the log — and reproduced clean on a fresh port.)
- DNS: `dig @1.1.1.1/@8.8.8.8 alejandromerida.dev A/AAAA/TXT` → NS set
  (Cloudflare), **zero address records**; `amm-ds.github.io/portfolio/` →
  HTTP 200.
- PyPI version comparison for 27 locked packages (table in CQ-4).
- vulture ≥90 % over all `src/` trees → only validator `cls` bindings + 2
  benign unused unpacks; zero `TODO`/`FIXME` in `src/`.
- AST annotation scan → 1,542/1,542 functions annotated.
- Secret pattern sweep (api_key/secret/token/password with high-entropy
  literals) → no matches; gitleaks not installed locally (it is in
  pre-commit, `.pre-commit-config.yaml:14-16`).
- pip-audit could not run in this environment (host `ensurepip` SIGABRT); the
  CI gate at `ci.yml:129-135` is the authoritative check.
