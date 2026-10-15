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
