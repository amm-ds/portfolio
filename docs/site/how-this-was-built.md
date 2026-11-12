# How this was built

A first-person note on process, because the tools question comes up and the
honest answer is more useful than the polished one. This page covers three
things: how the work actually flows, which decisions were mine (and why), and
the standards that keep agent-written code at a senior bar.

## How the work flows — agents with a human in the loop

This portfolio was built with heavy use of AI coding agents (Kimi Code), run
as an orchestrated team rather than a single autocomplete:

- **Specialist agents per task.** An orchestrator briefs exploration,
  implementation and evaluation agents with the exact context they need —
  dataset contracts, baseline requirements, evaluation protocols, the
  documentation template. Each works in its own lane; the orchestrator
  integrates.
- **Refinement loops, not one-shot prompts.** Most of what you see went
  through several rounds: a first build, a review, a viewer report ("the
  legend overlaps the bars", "the chart is clipped"), a targeted fix, a
  re-verification. The git history is the receipt — wave after wave of
  small, reviewed changes.
- **An owner review round gates every publication.** Nothing ships from an
  agent run directly: changes are presented for review, feedback lands in
  structured rounds with agreed scope, and only the approved version is
  committed, pushed and deployed. "Push when approved" is the default
  contract, and it is visible in the commit history.
- **The judgment stays human.** I set the architecture and the acceptance
  criteria; the agents wrote and tested large parts of the code; I reviewed,
  ran and own every result.

## Decisions I made myself

The parts of this portfolio that are hard to fake are decisions. These are
the load-bearing ones, with the reasoning and where the evidence lives.

### Design

- **A terminal, not a template.** JetBrains Mono, teal on dark slate, `>`
prompts, `fig ::` captions — the whole site renders as one coherent
  terminal metaphor rather than a themed portfolio template. Chosen because
  the audience reads code for a living; the design *is* the positioning.
  A light theme came later, with one accessibility lesson baked in: text
  and decoration follow separate tokens, because bright turquoise fails
  WCAG as text on white no matter how good it looks.
- **Figures are data, not images.** Every chart ships as plotly JSON and
  renders through a custom TypeScript converter (`plotlyToECharts`) —
  server-free, themeable, axis-gated in CI. Static screenshots would have
  been faster and far less honest: the same figure must read identically in
  the article, the report page, and light mode.
- **Two audiences, one codebase.** Case studies serve technical evaluators;
  the home, services and contact pages serve prospective clients. One
  repository, one design system, deliberately different reading depths.

### Frameworks and shape

- **FastAPI + React/TypeScript over Streamlit.** A deliberate rejection of
  the fastest demo path: typed API contracts, a real front end, and a
  production shape a client could hire for. The showcase API and web app
  are the same stack as the deliverables they describe.
- **A uv workspace monorepo over scattered repos.** `portfolio-core` holds
  the typed contracts both the API and every project import;
  `portfolio-eval` holds the shared evaluation/reporting library.
  Import-linter contracts enforce the layer boundaries so the sharing stays
  clean as the repo grows.
- **pydantic-ai for the agent applications** (`agent-chat`,
  `document-intelligence`): typed tools, a model-agnostic seam, structured
  outputs a validator can check. The apps are deliberately isolated
  workspaces — production templates someone can lift out whole.
- **mkdocs for the docs site** rather than a second SPA: content belongs in
  git as markdown, reviewable in the same pull-request flow as code.
- **DVC for data, with committed exceptions for authored artifacts.**
  Pipelines and large payloads stay reproducible-from-source; hand-authored
  evidence (golden question sets, feature contracts, the 12→13 contract)
  is committed because a claim that cannot be read from git is not a claim.

### Models

- **Provider selection by measurement, not fashion.** `kimi-for-coding` was
  selected against the incumbent on the project's own rubric: faithfulness
  0.5504 → 0.6209, with the answer-relevancy regression (0.8775 → 0.8602)
  disclosed in the headline, not footnoted.
- **Small models where measurement says so.** MiniLM embeddings match
  BGE-small on recall@5 — so MiniLM ships, CPU-only. A bigger embedding
  model and bigger hosted models were rejected on measured evidence, not
  taste.
- **Local-first inference for the apps.** Ollama is the runtime default for
  the agent templates ($0, private); hosted providers appear only in
  metered evaluation passes under hard cost caps. No runtime mocks anywhere.
- **When the evaluation disagreed with the demo, the evaluation won.**
  Project 03's synthetic-track PR-AUC was 0.92; on real NAB data it is
  0.53 — and 0.53 is the headline. A portfolio of only wins would be
  marketing; the losses are the engineering.

### Process and pipelines

- **The evaluation-first rule.** Every project must beat a naive or random
  baseline on a real dataset, with the delta — not the model — as the
  headline. Floors are seeded so a headline can never restate how easy the
  task is.
- **Sealed sets, written after tuning freezes, scored once.** The 01
  story is the cautionary tale: the original 15-question sealed set was too
  small to trust; the 55-question expansion passed an answerability gate
  that both audits then flagged as biasing retrieval reads toward success —
  so an independent 30-question stress set was authored without the gate.
  Correctness drops from 0.80 to 0.53 there, and that drop is the truth the
  gated set could not show. Methodology improves in public here.
- **The wave system.** Viewer reports become briefs; briefs become focused
  commits; commits pass the gate battery; only green SHA deploy.
  Iteration rounds are visible in history — the chunk-size-sweep figure
  alone went through four review rounds (categorical axis, legend, star
  band, baseline) before it read right.
- **No deploys from red CI.** Adopted after an external evaluation caught a
  red revision in production. Deploys verify the health SHA afterwards; the
  server keeps the previous image for rollback.
- **Nightly health with deduplicated issues.** One open nightly issue at a
  time; failures comment on it with the run link instead of opening a
  duplicate-per-day stream.

### Infrastructure

- **One honest VPS over managed platforms.** Hetzner + Caddy + Docker
  Compose: TLS by Caddy, the API unpublished on the private compose
  network, health/readiness endpoints, a written runbook, and a deployment
  report recording what broke. Cost and ownership were the trade — and the
  operations knowledge is itself a deliverable.
- **Per-route heads served from one shell.** The SPA serves
  route-specific title, description, canonical and a `<noscript>` body from
  the API, plus server-side JSON-LD — so link previews and non-JS crawlers
  see the real page, not an empty root div.
- **Provenance as a release gate.** Every metrics artifact carries a
  versioned `_meta` (git SHA, lockfile hash, params hash, seed, timestamp),
  stamped deterministically and validated in CI; version-tagged images
  ship with an attested SBOM and a keyless signature.

## Reports and context

Agents here do not work from vibes — they work from committed evidence:

- Every brief carries the measured state: `metrics.json`, per-question
  traces, figure payloads, prior evaluation reports, audit findings.
- Every change lands with its verification report — the gates run (lint,
  types, tests, figure axis/budget checks, story-language lint, short-copy
  single-sourcing), the numbers are compared against the committed ones, and
  the deploy is confirmed against the running site (`/health` reports the
  build SHA).
- The public repository is the context. Reports, ADRs, runbooks and audit
  responses are committed next to the code they describe, so any claim can
  be checked from source.

## The standards that keep agent-written code honest

Speed of generation is only safe with a high review bar, so the bar is
machine-checked wherever possible:

- **The eight ADRs** (`docs/architecture/adr/`) record the architectural
  calls — the ones I made myself, with the options considered.
- **An engineering playbook and code-quality guidelines** define the
  conventions: smallest complete change, typed contracts, `mypy` strict,
  import-linter contracts between layers.
- **Gates run on every wave**: ruff, mypy, pytest with a coverage floor,
  figure axis-limit and weight budgets, story-language lint, demo-contract
  checks, a single-sourced short-copy check so no public surface can drift
  from the measured numbers, axe accessibility in both themes, Docker
  smoke, and the release-artifact contract with metrics provenance.
- **Two external audits** (2026-10 and 2026-11) were answered point-by-point
  in public — including the findings I disagreed with and the ones I fixed.

## What the agents did well

Boilerplate, test scaffolds, visualization plumbing, repetitive pipeline
code, and the long tail of "make ruff/mypy/pytest green" cycles. Iterating a
figure until it reads well is exactly the kind of loop agents are good at —
and the viewer reports that drive those iterations are reviewed by a person
before they become briefs.

## Where that leaves the judgment

The parts of this portfolio that are hard to fake — dataset selection,
leakage-free validation design, baseline discipline, deciding which result
is the headline, saying no to a finding you disagree with and showing why,
killing a demo path in favor of the measured one — are the parts I did. The
code is real, the tests run, the numbers regenerate from `dvc repro`, and
every claim on this site traces to a committed artifact. If you want to
probe the difference, start with the audit responses: they show how I
handle being wrong in public.
