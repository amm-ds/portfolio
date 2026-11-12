# How this was built

A first-person note on process, because the tools question comes up and the
useful answer is more concrete than the polished one. Three things: how the
work flows, which decisions were mine, and the standards that keep the code
at a senior bar.

## How the work flows — agents with a human in the loop

This portfolio was built with heavy use of AI coding agents (Kimi Code), run
as a team rather than a single autocomplete:

- **Specialist agents per task.** An orchestrator briefs exploration,
  implementation and evaluation agents with the context they need — dataset
  contracts, baseline requirements, evaluation protocols, documentation
  templates. Each works in its own lane; the orchestrator integrates.
- **Refinement loops, not one-shot prompts.** Most of what you see went
  through several rounds: a build, a review, a viewer report, a targeted
  fix, a re-verification. The git history is the receipt — waves of small,
  reviewed changes.
- **An owner review gates every publication.** Nothing ships from an agent
  run directly: changes are presented for review, feedback lands in
  structured rounds, and only the approved version is committed, pushed and
  deployed. "Push when approved" is the default contract.
- **The judgment stays human.** I set the architecture and the acceptance
  criteria; the agents wrote and tested large parts of the code; I reviewed,
  ran and own every result.

## Decisions I made myself

The parts that are hard to fake are decisions. These are the load-bearing
ones, with the reasoning.

### Design

- **A terminal, not a template.** A monospace, prompt-driven visual
  language across the whole site, chosen because the audience reads code
  for a living — the design is the positioning.
- **Figures are data, not images.** Charts ship as figure JSON rendered by
  a custom converter — themeable, axis-gated in CI, and identical in the
  article, the report page, and either theme.
- **Two audiences, one codebase.** Case studies serve technical evaluators;
  the home and services pages serve prospective clients — deliberately
  different reading depths on one design system.

### Frameworks and shape

- **FastAPI + React/TypeScript over Streamlit.** A deliberate rejection of
  the fastest demo path in favor of typed contracts and a production shape.
- **A uv workspace monorepo** with shared typed contracts and import-linter
  boundaries, so reuse stays clean as the repo grows.
- **pydantic-ai for the agent applications**, with the apps as isolated
  workspaces — production templates someone can lift out whole.
- **mkdocs for docs** — content belongs in git as markdown, reviewable in
  the same flow as code.
- **DVC for data, with committed exceptions for authored artifacts**
  (golden sets, feature contracts) — a claim that cannot be read from git
  is not a claim.

### Models

- **Selection by measurement, not fashion.** The hosted provider was chosen
  on the project's own rubric, with the regressions disclosed next to the
  gains.
- **Small models where measurement says so** — when two candidates tie, the
  smaller ships; bigger models were rejected on evidence, not taste.
- **Local-first inference for the apps**; hosted providers appear only in
  metered evaluation passes under hard cost caps. No runtime mocks.
- **When the demo and the evaluation disagree, the evaluation wins.** A
  result that looked strong on synthetic data was published at its real,
  weaker number — the losses are part of the engineering record.

### Process and pipelines

- **The evaluation-first rule.** Every project must beat a naive or random
  baseline on real data, with the delta — not the model — as the headline.
- **Sealed sets, written after tuning freezes, scored once.** The RAG
  story is the cautionary tale: the sealed set was expanded, then both
  audits flagged its answerability gate as biasing retrieval reads — so an
  independent stress set was authored without the gate, and correctness
  dropped from 0.80 to 0.53. That drop is published next to the headline.
  Methodology improves in public here.
- **The wave system.** Viewer reports become briefs; briefs become focused
  commits; commits pass the gate battery; only green SHA deploys deploy.
- **No deploys from red CI.** Deploys verify the health SHA afterwards; the
  server keeps the previous image for rollback.

### Infrastructure

- **A single VPS over managed platforms** — Caddy, Docker Compose, a
  written runbook — trading convenience for ownership and cost, with the
  operations knowledge itself a deliverable.
- **Per-route metadata served from one shell**, so link previews and
  non-JS crawlers see the real page.
- **Provenance as a release gate** — versioned identity on every metrics
  artifact, SBOM and keyless signatures on release images.

## Reports and context

Agents work from committed evidence, not vibes:

- Every brief carries the measured state: metrics, traces, figure payloads,
  prior reports, audit findings.
- Every change lands with its verification report — the gates run, numbers
  are compared against the committed ones, the deploy is confirmed against
  the running site.
- The repository is the context: reports, ADRs, runbooks and audit
  responses sit next to the code they describe.

## The standards that keep the code at the bar

Speed of generation is only safe with a high review bar, so the bar is
machine-checked wherever possible:

- **The eight ADRs** (`docs/architecture/adr/`) record the architectural
  calls — mine, with the options considered.
- **An engineering playbook and code-quality guidelines** — smallest
  complete change, typed contracts, strict mypy, import contracts.
- **Gates on every wave**: lint, types, tests with a coverage floor, figure
  budgets, story-language lint, single-sourced short copy, accessibility in
  both themes, Docker smoke, the release-artifact contract, metrics
  provenance.
- **Two external audits** answered point-by-point in public — including the
  findings I disagreed with and the ones I fixed.

## What the agents did well

Boilerplate, test scaffolds, visualization plumbing, repetitive pipeline
code, and the long tail of "make the gates green" cycles. Iterating a
figure until it reads well is exactly the loop agents are good at — and the
viewer reports that drive those iterations pass a human review before they
become briefs.

## Where that leaves the judgment

The parts that are hard to fake — dataset selection, leakage-free validation
design, baseline discipline, deciding which result is the headline, killing
a demo path in favor of the measured one — are the parts I did. The code is
real, the tests run, the numbers regenerate from `dvc repro`, and every
claim on this site traces to a committed artifact. If you want to probe the
difference, start with the audit responses: they show how I handle being
wrong in public.
