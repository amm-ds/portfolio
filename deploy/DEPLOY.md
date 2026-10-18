# Production deployment — Caddy + Docker (reference VPS: Hetzner)

Target: one small cloud VPS (Hetzner CX33 is the reference: 4 vCPU / 8 GB) running
the showcase app behind Caddy (automatic TLS) with Cloudflare in front (CDN, WAF,
rate limiting). Docs stay on GitHub Pages.

## 1. Domain + DNS (once)

1. Buy a domain and point its A-record at the server IP (proxied through Cloudflare).
2. Set the environment — no file edits needed, `DOMAIN` is passed through to
   Caddy by `docker-compose.prod.yml`:

   ```bash
   export DOMAIN=example.com
   # Optional: Cloudflare API token, so Caddy can solve the DNS challenge
   # (needed for wildcard/subdomain certificates):
   export CLOUDFLARE_API_TOKEN=...
   ```

3. Cloudflare: SSL mode "Full (strict)"; add a rate-limiting rule for `/rag/*` and
   `/projects/*/forecast` (e.g. 20 req/min per IP) — cheap abuse protection for the
   public endpoints. The API also enforces **in-app per-IP rate limiting as a
   floor**, so the endpoints stay bounded even if a request bypasses Cloudflare.
   The RAG chat stays OFF publicly (`RAG_CHAT_ENABLED` unset).

## 2. Server bootstrap (once)

```bash
# On a fresh Ubuntu 24.04 image
curl -fsSL https://get.docker.com | sh
usermod -aG docker <your-user>
mkdir -p /opt/portfolio && chown $USER /opt/portfolio
```

## 3. Deploy

```bash
# From the repo (or any machine with ssh access)
docker build -t amm-ds-portfolio .
docker save amm-ds-portfolio | ssh <user>@<server> 'docker load'
scp deploy/docker-compose.prod.yml deploy/Caddyfile <user>@<server>:/opt/portfolio/
ssh <user>@<server> 'cd /opt/portfolio && DOMAIN=example.com docker compose -f docker-compose.prod.yml up -d'
```

The image bakes the web build and project stories, plus the deployable
artifacts committed to git: figure specs (`projects/*/reports/figures/*.json`,
with `.html` siblings) and serving bundles (`projects/*/reports/models/serving/`
— live forecast/scoring endpoints). They are committed precisely so a fresh
clone or CI-built image produces a fully functional app; bulky raw data stays
DVC-tracked and regenerates locally via `dvc repro`. The 01 RAG index is the
one opt-in exception — it is not committed: enable `/rag/chat` by running
`dvc repro` in `projects/01-rag-agent` on the host.
On first start Caddy provisions a Let's Encrypt certificate for `$DOMAIN`
automatically — HTTPS is live as soon as DNS resolves.

## 4. Verify

```bash
curl -s https://example.com/health            # {"status":"ok"}
curl -s https://example.com/projects | head -c 120
curl -s -X POST https://example.com/projects/07-open-data-mobility/forecast \
  -H 'content-type: application/json' \
  -d '{"zone_id":132,"features":{"lag_1":191,"lag_2":191,"lag_24":193,"lag_168":197,"hour":11,"day_of_week":4,"month":11,"prcp_mm":0,"tmax_c":14.4,"tmin_c":6.7,"snow_mm":0}}'
```

Also check the response headers: HSTS, CSP, `nosniff`, `Referrer-Policy`, and
`Permissions-Policy` are all set by the Caddyfile.

## 5. Operations

- **Logs**: `docker compose -f /opt/portfolio/docker-compose.prod.yml logs -f api`
  (containers rotate logs: json-file, 10 MB × 3).
- **Update**: rebuild + `docker save | ssh ... 'docker load'` + `up -d` (zero-downtime recreate)
- **No bulk data on the server**: raw datasets stay DVC-tracked and regenerate
  via `dvc repro` where needed; the image ships the committed figure specs and
  serving bundles, so the VPS is stateless apart from Caddy's certificates.

## RAG chat (opt-in, off by default)

Public visitors get the deterministic mock provider — no LLM costs. To serve the
RAG chat publicly:

1. Get the retrieval index onto the host: it is baked into the image when built
   after `dvc repro`; on the server it regenerates from the repo with `dvc repro`
   (or copy the built image from a machine that has it).
2. Add a local model: extend the compose file with an `ollama` service (image
   `ollama/ollama`, `OLLAMA_HOST=0.0.0.0`, pull `qwen3:8b`) and point the api at
   it via `OLLAMA_BASE_URL=http://ollama:11434/v1` — or set a budgeted provider
   key (`LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`, which take priority over Ollama).
   `extra_hosts: host.docker.internal:host-gateway` is already on the api service,
   so a host-level Ollama also works (`OLLAMA_BASE_URL` default).
3. Enable with `RAG_CHAT_ENABLED=1` and keep the Cloudflare rate-limit rules on
   `/rag/*` (plus the API's in-app per-IP floor).

A 32B model does NOT fit this tier — keep big-model demos local (see ADR-0006).

## Alternative: free-tier hosts (no VPS needed)

The showcase is a single container, so free tiers work for a public demo:

- **Render.com** — one Web Service from this repo's Dockerfile (build context
  repo root, port 8000); free tier spins down on idle, which is fine for a
  portfolio. Set no env vars; RAG chat stays off, rate limiting is in-app.
- **Fly.io** — `fly launch` against the root Dockerfile; smallest shared-cpu
  VM is enough (the api service is capped at 2 cpus / 2G in compose).
- **Oracle Cloud free tier** (if you want always-on) — an ARM Ampere VM runs
  the compose stack as-is.

Caveats on any host: the serving artifacts and figures bake into the image
at build time (they are committed to git — nothing else to configure), and
the optional RAG chat needs the 01 index rebuilt on the host (`dvc repro`
in `projects/01-rag-agent`) plus a provider key or Ollama sidecar.
