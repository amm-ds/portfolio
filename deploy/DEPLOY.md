# Deployment

## Current state: code-first, deploy deferred

The app is fully buildable from source but **not deployed anywhere yet** — there
is no domain, no server, and no live URL. Deliberately: deployment is deferred
until a domain exists, so no configuration carries placeholder hosts.

What works today, locally and in CI:

- **SPA** — `apps/showcase-web` builds to a static `dist/` (client-side
  routing, deep links need a SPA fallback rewrite). The CI gate enforces a
  bundle budget on the entry chunk.
- **API** — `apps/showcase-api` serves project stories, metrics, live
  forecast/scoring endpoints (from the git-committed serving bundles) and the
  health check. The all-in-one image at the repo root bakes the SPA build and
  the API into a single container (`deploy/docker-compose.prod.yml` +
  `deploy/Caddyfile` describe that topology for when a host exists).
- **Docs** — built with MkDocs (`mkdocs build --strict` in CI).

## Recommended target when a domain exists (per the readiness brief)

**Hybrid:**

- **Static SPA on Cloudflare Pages** — deploy `apps/showcase-web/dist` as a
  Pages project. Cloudflare provides the CDN, TLS, and the SPA fallback
  rewrite. Cost: free tier.
- **API on a small VPS** — the all-in-one image (or a slim API-only variant)
  on one small VPS (Hetzner CX33-class: 4 vCPU / 8 GB is the reference) behind
  Caddy for TLS. The SPA talks to the API at a configured origin; Cloudflare
  proxies and rate-limits the API hostname.

Until the hybrid split is implemented, the single-container image behind
Caddy remains the simplest whole-app target — same env vars, one host.

## Required environment variables

| Variable | Where | Purpose |
| --- | --- | --- |
| `SITE_URL` | SPA build time (`VITE_SITE_URL`) | Canonical origin baked into the build: sitemap, `og:url`/canonical tags, `absoluteUrl()`, contact copy. Must be the final public URL — rebuilding is required when it changes. |
| `BUILD_SHA` | SPA build time (`VITE_BUILD_SHA`) | Git commit baked into the build for cache-busting / build attribution. |
| `LIVE_*` | SPA build time | Feature switches for the live-demo registry (which demos render as interactive vs static fallback). Off/absent = static fallbacks, safe default. |
| `IP_HASH_SALT` | API runtime | Salt for hashing client IPs before they are stored/logged — the privacy floor behind "no user data stored". Rotate on any suspected compromise (invalidates historical buckets only). |
| `RATE_LIMIT_PER_MINUTE` | API runtime | Per-IP POST rate limit (default 30/min, burst 10). |
| `RAG_CHAT_ENABLED` | API runtime | `1` opts in to the public RAG chat (off by default; needs a provider key or Ollama). |

`VITE_*` values are compiled into the static bundle — they are public, never
secrets. The API container needs no secrets for the default configuration.

## Smoke test (after any deploy)

```bash
BASE="https://<your-domain>"   # or http://localhost:8000 for the all-in-one image

curl -fsS "$BASE/health"                                   # {"status":"ok"}
curl -fsS "$BASE/" | grep -q 'id="root"'                   # SPA shell served
# Deep links return the SPA shell (client-side routing fallback):
curl -fsS "$BASE/projects/06-routing-optimization" | grep -q 'id="root"'
curl -fsS "$BASE/projects" | grep -q '"id":"01-rag-agent"' # project index JSON
curl -fsS "$BASE/projects/05-ml-pipeline-churn/metrics" | grep -q selected_model_calibrated
```

Also verify response headers (HSTS, CSP, `nosniff`, `Referrer-Policy`,
`Permissions-Policy`) and that the served HTML carries the expected
`BUILD_SHA`/`SITE_URL`.

## Rollback outline

1. **Static (Pages)** — Pages keeps prior deployments: roll back in the
   Cloudflare dashboard (instant) or redeploy the previous CI artifact.
   Because `SITE_URL`/`BUILD_SHA` are baked per build, a rollback is a pure
   pointer move, no rebuild.
2. **API (VPS)** — the image is immutable and tagged by commit:
   keep the previous image on the host, `docker compose up -d` with the prior
   tag (zero-downtime recreate), and only prune the old image after the
   smoke test passes. Serving bundles are committed to git, so any historical
   image can be rebuilt bit-for-bit from its commit.
3. **Database/state** — none: the app stores no user data (privacy note in
   the footer is literal); the only host state is Caddy's certificates and
   regenerable serving artifacts.

## Privacy posture

No analytics, no cookies, no user data stored — stated in the site footer and
a design constraint, not a marketing line. Client IPs are only ever handled
salted-hashed (`IP_HASH_SALT`) or held in memory for the rate-limit bucket,
which resets on restart. Keep it that way when wiring the hybrid target: no
third-party analytics scripts, no Cloudflare Web Analytics without revisiting
this document.
