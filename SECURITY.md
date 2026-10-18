# Security Policy

## Supported versions

Only the latest state of the `main` branch is supported. This is a
portfolio/research repository — there are no versioned releases with
long-term support.

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.**

Report privately via GitHub Security Advisories:
[github.com/amm-ds/portfolio/security/advisories/new](https://github.com/amm-ds/portfolio/security/advisories/new)

- If the repository shows a **"Report a vulnerability"** button on its
  [Security page](https://github.com/amm-ds/portfolio/security), use it —
  that opens a private advisory visible only to you and the maintainer.
- Otherwise, create a **draft security advisory** from the same page (do
  not publish it); drafts are private by default.

## What to include

- The affected surface (showcase API, a project pipeline, the web app, CI).
- Steps to reproduce, or a failing request/payload.
- Impact assessment, if known (data exposed, RCE, etc.).

## Response expectations

- Acknowledgment within **3 business days**.
- A fix or mitigation plan within **14 days** for confirmed
  high-severity issues in the served application code.
- Credit in the advisory/fix commit unless you prefer to stay anonymous.

## Scope notes

- The RAG chat endpoint is **disabled by default** in any deployment
  (`RAG_CHAT_ENABLED` unset) and fails closed — treat any bypass of that
  gate as high severity.
- Demo/serving endpoints are intentionally unauthenticated but rate-limited
  and input-capped; report bypasses of those guards.
- The machine-learning pipelines run on the reporter's own machine; a
  malicious *dataset* (e.g., a poisoned DVC remote) is out of scope unless
  it compromises code executed from this repository.
