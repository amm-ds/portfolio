# Deployment Report — alejandromerida.dev

**2026-11-08 — CUTOVER COMPLETE.** The supported single-origin topology
(DEPLOY.md) is live: `https://alejandromerida.dev` serves tag `191a4ce`
(full SHA `191a4ce5470f88401637652e0d23ff1a4c8dd911`) from the Hetzner CX23
`ubuntu-4gb-nbg1-1` (2.31.119.56), DNS `A` record DNS-only, Caddy-provisioned
TLS, uptime workflow enabled. Server-specific operations live in
[`HETZNER.md`](HETZNER.md). The tier evaluation below is retained as history.

Cutover record: image built on the host from the pushed tree; smoke suite
(DEPLOY.md) passed end to end including a live `/score` POST; three latent
bugs surfaced only under a real boot and were fixed in `bd60eed`, `db4fc13`,
`191a4ce` (see HETZNER.md history). Memory footprint on the 4GB shared box:
api ~223MB of a 1G limit, caddy ~25MB of 256M, ≥2.9GB available for the OS
and the co-tenant project.

---

**Date:** 2026-11-04 · **Status:** dated alternatives evaluation, not the supported runbook.

Use [`DEPLOY.md`](DEPLOY.md) for the current single-origin deployment contract.
The split-origin tiers below are options under evaluation; their configuration
and cost claims are point-in-time notes, not instructions to run production.

**Blocker for every tier:** `alejandromerida.dev` is registered (Cloudflare
NS) but publishes **zero DNS records**. Step one is the registrar/Cloudflare
step: apex + `www` → the chosen origin, plus `api` if Tier 2.

## What the site actually needs (verified against the code)

| Capability | Needs a server? | Evidence |
|---|---|---|
| Home / Projects / experiment pages / glossary / about / services | **No** | the SPA renders from the static registry when the API is down |
| Case-study stories, roadmaps, conclusions | **No** | `staticRegistry` + `storyShort` are generated snapshots |
| Replay demos (workbench, churn sandbox) | **No** | demo payloads are committed JSON; the workbench has a static fallback manifest |
| Interactive figures (Plotly) | **Only as static files** | figure payloads are committed `*.json` under `reports*/figures/` but are *served by the API today* — bake them into the static bundle and charts work without any server |
| Live scoring (churn `/score`, forecast `/forecast`, mobility) | **Yes** | FastAPI POST endpoints with in-process models |
| RAG chat | **Yes, and it stays off** | behind `RAG_CHAT_ENABLED`, disabled by default |

## Recommendation — Tier 2 (Cloudflare Pages + the smallest Hetzner VM)

### Tier 1 — Cloudflare Pages only (free)
The static SPA. Requires one build change first: copy `reports*/figures/*.json`
and demo payloads into `dist/` and make the figure/payload fetchers try the
relative static path before the API (small, reversible front-end change).
Result: every page, chart, and replay demo works at zero cost. Live scoring
is off.

### Tier 2 — Pages + the smallest VM (~€0–5/month) **← recommended**
Tier 1 plus the FastAPI image on `api.alejandromerida.dev` (CORS-restricted
to the site origin) serving **only** the live POST endpoints. This matches
how the portfolio is presented (live demos are part of the pitch), keeps the
expensive part (the always-on site) free, and the VM is the smallest size —
the API is stateless and light. Cloudflare Pages Functions cannot run
FastAPI, and a VM-only deploy would pay for static hosting Pages does better
(CDN, TLS, rollback).

**VM choice:**
- **Oracle Cloud Always Free (Ampere A1 ARM) — $0.** Since August 2026 the
  free allowance is **2 OCPU / 12 GB** (halved from 4/24) + 10 TB egress —
  still generous for this API. Caveats: ARM A1 shows "out of host capacity"
  constantly (provisioning can take days of retries; PAYG unlocks instantly),
  signup rejections are routine, idle free-tier VMs risk reclamation, and the
  image must build for linux/arm64 (verify wheels: sklearn / xgboost /
  polars / duckdb all ship aarch64 — the repo already builds on Apple
  Silicon, so this is a cutover check, not a rewrite).
- **Hetzner CX11/CX22 — ~€4–5/mo.** Always provisionable, x86 or ARM, no
  idle policy, no account roulette. The reliable fallback if Oracle's
  provisioning stalls.

Try Oracle free first; fall back to Hetzner at the cost of a coffee.

### Tier 3 — single VM serves everything (current Dockerfile shape)
Simplest mental model, worst cost/uptime: one origin does static + API.
Only choose this if live endpoints must share the origin (they don't — CORS
is fine).

## Minimal analytics

**Cloudflare Web Analytics**: cookieless, no personal data, free, one
snippet in `index.html`. Consistent with the privacy posture (no visitor
tracking; aggregate page-view insight only). Add at cutover; revisit monthly.
Alternative if even that is unwanted: no analytics (status quo).

## Cutover checklist (Tier 2)

1. DNS: apex + `www` → Cloudflare Pages; `api` → the VM's IP.
2. Build change: bake figures/payloads into `dist` (Tier 1 prerequisite).
3. `VITE_SITE_URL`/`SITE_URL` already default to the domain; set `DOCS_URL`
   if the docs stay on GitHub Pages.
4. Deploy workflow: build SPA → publish to Pages; VM runs compose with
   `DOMAIN` + `IP_HASH_SALT` set (compose already requires them).
5. Cloudflare Web Analytics snippet; verify no cookies are set.
6. Smoke: `/`, `/projects/02-demand-forecasting`, a figure JSON, one replay
   demo (API stopped), then one live POST (API up).
7. Uptime: Cloudflare's free health checks against `/` and `/health`.

## Cost summary

| Tier | Monthly cost | Live demos | Ops surface |
|---|---|---|---|
| 1 | €0 | no | Pages only |
| **2 (Oracle free)** | **€0** | **yes** | Pages + one tiny ARM VM (provisioning patience) |
| 2 (Hetzner) | ~€4–5 | yes | Pages + one tiny VM |
| 3 | ~€4–5 | yes | one VM (you own TLS/CDN/static) |
