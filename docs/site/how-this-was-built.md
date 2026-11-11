# How this was built

A first-person note on process, because the tools question comes up and the
honest answer is more useful than the polished one.

## How the work flows — agents with a human in the loop

This portfolio was built with heavy use of AI coding agents (Kimi Code), run
as an orchestrated team rather than a single autocomplete:

- **Specialist agents per task.** An orchestrator briefs exploration,
  implementation and evaluation agents with the exact context they need —
  dataset contracts, baseline requirements, evaluation protocols, the
  documentation template. Each works in its own lane; the orchestrator
  integrates.
- **Refinement loops, not one-shot prompts.** Most of what you see on this
  site went through several rounds: a first build, a review, a viewer report
  ("the legend overlaps the bars", "the chart is clipped"), a targeted fix,
  a re-verification. The git history is the receipt — wave after wave of
  small, reviewed changes.
- **An owner review round gates every publication.** Nothing ships from an
  agent run directly: changes are presented for review, feedback lands in
  structured rounds with agreed scope, and only the approved version is
  committed, pushed and deployed. "Push when approved" is the default
  contract, and it is visible in the commit history.
- **The judgment stays human.** I set the architecture and the acceptance
  criteria; the agents wrote and tested large parts of the code; I reviewed,
  ran and own every result.

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

- **Eight ADRs** (`docs/architecture/adr/`) record the architectural calls —
  the ones I made myself, with the options considered.
- **An engineering playbook and code-quality guidelines** define the
  conventions: smallest complete change, typed contracts
  (`portfolio-core`), `mypy` strict, import-linter contracts between layers.
- **Gates run on every wave**: ruff, mypy, pytest with a coverage floor,
  figure axis-limit and weight budgets, story-language lint, demo-contract
  checks, and a single-sourced short-copy check so no public surface can
  drift from the measured numbers.
- **Two external audits** (2026-10-15/16) were answered point-by-point in
  public — including the findings I disagreed with and the ones I fixed.

## What I decided myself

- **The platform shape.** Monorepo with typed contracts (`portfolio-core`),
  a shared evaluation/story library (`portfolio-eval`), DVC pipelines, one
  FastAPI showcase, one React/TypeScript front end. The eight ADRs in
  `docs/architecture/adr/` are my calls.
- **The evaluation-first rule.** Every project must beat a naive or random
  baseline on a real dataset, with the delta — not the model — as the
  headline. When results got worse on real data (see project 03: PR-AUC
  0.53 on NAB vs 0.92 synthetic), the worse number is the headline.
- **What not to build.** No new project until the existing ones are
  production-grade; synthetic data demoted behind real tracks; a declined
  DVC remote (artifacts stay reproducible from source instead of hosted).

## What the agents did well

Boilerplate, test scaffolds, visualization plumbing, repetitive pipeline
code, and the long tail of "make ruff/mypy/pytest green" cycles. Iterating a
figure until it reads well is exactly the kind of loop agents are good at —
and the viewer reports that drive those iterations are reviewed by a person
before they become briefs.

## Where that leaves the judgment

The parts of this portfolio that are hard to fake — dataset selection,
leakage-free validation design, baseline discipline, deciding which result
is the headline, saying no to a finding you disagree with and showing why —
are the parts I did. The code is real, the tests run, the numbers
regenerate from `dvc repro`, and every claim on this site traces to a
committed artifact. If you want to probe the difference, start with the
audit response page: it shows how I handle being wrong in public.
