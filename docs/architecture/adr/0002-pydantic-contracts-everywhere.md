# ADR-0002: pydantic contracts at every boundary

- **Status:** Accepted
- **Date:** 2026-10-12

## Context

Portfolio code is read by technical evaluators. Untyped dicts passing through
pipelines hide the design; validation at boundaries turns data drift and config
typos into loud, early failures.

## Decision

Every cross-module boundary — dataset records, run configs, API requests and
responses, agent tool arguments and returns, evaluation rows — is a pydantic
`BaseModel` (v2). Configuration uses `pydantic-settings` with env overrides.
Validators carry hypothesis property tests.

## Consequences

- mypy strict is enforced on `libs/*`; runtime validation complements static
  types at IO edges (files, HTTP, LLM outputs).
- Schemas are the documentation: a reader can reconstruct the data model from
  `portfolio_core.schemas` without running anything.
- Cost: schema churn must be treated as a contract change (PR template asks).
