# Production deployment — Hetzner VPS + Caddy + Docker

Target: one Hetzner cloud VPS (CX33 class: 4 vCPU / 8 GB) running the showcase app
behind Caddy (automatic TLS) with Cloudflare in front (CDN, WAF, rate limiting).
Docs stay on GitHub Pages.

## 1. Server bootstrap (once)

```bash
# On a fresh Ubuntu 24.04 Hetzner image
curl -fsSL https://get.docker.com | sh
usermod -aG docker <your-user>
mkdir -p /opt/portfolio && chown $USER /opt/portfolio
```

DNS: `your-domain.com` A-record → server IP (proxied through Cloudflare).
Cloudflare: SSL mode "Full (strict)"; add a rate-limiting rule for `/rag/*` and
`/projects/*/forecast` (e.g. 20 req/min per IP) — cheap abuse protection for the
public endpoints. The RAG chat stays OFF publicly (`RAG_CHAT_ENABLED` unset).

## 2. Deploy

```bash
# From the repo (or any machine with ssh access)
docker build -t amm-ds-portfolio .
docker save amm-ds-portfolio | ssh <user>@<server> 'docker load'
scp deploy/docker-compose.prod.yml deploy/Caddyfile <user>@<server>:/opt/portfolio/
ssh <user>@<server> 'cd /opt/portfolio && docker compose -f docker-compose.prod.yml up -d'
```

The image bakes the web build, project stories, metrics, figures, the RAG index
(/rag/chat works if enabled) and the 07 serving artifacts (forecast endpoint).

## 3. Verify

```bash
curl -s https://your-domain.com/health            # {"status":"ok"}
curl -s https://your-domain.com/projects | head -c 120
curl -s -X POST https://your-domain.com/projects/07-open-data-mobility/forecast \
  -H 'content-type: application/json' \
  -d '{"zone_id":132,"features":{"lag_1":191,"lag_2":191,"lag_24":193,"lag_168":197,"hour":11,"day_of_week":4,"month":11,"prcp_mm":0,"tmax_c":14.4,"tmin_c":6.7,"snow_mm":0}}'
```

## 4. Operations

- **Logs**: `docker compose -f /opt/portfolio/docker-compose.prod.yml logs -f api`
- **Update**: rebuild + `docker save | ssh ... 'docker load'` + `up -d` (zero-downtime recreate)
- **Optional LLM sidecar**: to serve a small local model publicly, add an `ollama`
  service (image `ollama/ollama`, `OLLAMA_HOST=0.0.0.0`, pull `qwen3:8b`) to the
  compose file and set `OLLAMA_BASE_URL=http://ollama:11434/v1` for the api service.
  A 32B model does NOT fit this tier — keep big-model demos local (see ADR-0006).
- **No data on the server**: everything regenerates from the repo (`dvc repro`);
  the VPS is stateless apart from Caddy's certificates.
