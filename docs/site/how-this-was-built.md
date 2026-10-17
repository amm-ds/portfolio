# How this was built

A first-person note on process, because the tools question comes up and the
honest answer is more useful than the polished one.

## What I used

This repository was built with heavy use of AI coding agents (Kimi Code), in
the same way a senior engineer uses any power tool: I set the architecture and
the acceptance criteria, the agents wrote and tested large parts of the code,
and I reviewed, ran, and owned every result. Most projects were built by a
dedicated agent briefed with the dataset, the baseline requirement, the
evaluation protocol, and the documentation template — then reviewed against the
same bar a pull request would face.

## What I decided myself

- **The platform shape.** Monorepo with typed contracts (`portfolio-core`),
  a shared evaluation/story library (`portfolio-eval`), DVC pipelines, one
  FastAPI showcase, one React/TypeScript front end. The seven ADRs in
  `docs/architecture/adr/` are my calls.
- **The evaluation-first rule.** Every project must beat a naive or random
  baseline on a real dataset, with the delta — not the model — as the
  headline. When results got worse on real data (see project 03: PR-AUC
  0.53 on NAB vs 0.92 synthetic), the worse number is the headline.
- **What not to build.** No new project until the existing ones are
  production-grade; synthetic data demoted behind real tracks; a declined
  DVC remote (artifacts stay reproducible from source instead of hosted).
- **The audits.** Both external audits (2026-10-15/16) were answered
  point-by-point in public, including the findings I disagreed with and the
  ones I fixed.

## What the agents did well

Boilerplate, test scaffolds, visualization plumbing, repetitive pipeline code,
and the long tail of "make ruff/mypy/pytest green" cycles. Iterating a
figure until it reads well is exactly the kind of loop agents are good at.

## Where that leaves the judgment

The parts of this portfolio that are hard to fake — dataset selection,
leakage-free validation design, baseline discipline, deciding which result is
the headline — are the parts I did. The code is real, the tests run, the
numbers regenerate from `dvc repro`, and every claim on this site traces to
a committed artifact. If you want to probe the difference, start with the
audit response page: it shows how I handle being wrong in public.
