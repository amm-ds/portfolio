# Hetzner runbook — shared 4GB VPS

Server-specific companion to `DEPLOY.md` (the general contract). Read DEPLOY.md
first; this file only records what is different on this box. **This file is
public: it intentionally contains no hostnames, IPs, key names, or secrets.**
Connection specifics (host, key, user) live in the operator's SSH config and
`/etc/hosts`, never in the repo.

## Server

- Hetzner CX23 — 2 vCPU / 4GB RAM / 38GB disk. `alejandromerida.dev` A record,
  **DNS only** (gray cloud — Caddy terminates TLS and sees real client IPs).
- Ubuntu 26.04, Docker Engine + Compose plugin (official apt repo).
- **4GB swapfile** at `/swapfile` (`vm.swappiness=10`,
  `/etc/sysctl.d/90-swappiness.conf`) — build insurance; do not remove.
- UFW: 22/80/443 tcp only. fail2ban sshd jail (5 tries / 10 min / 1 h ban).
- SSH hardening: `PermitRootLogin no`, `PasswordAuthentication no`
  (`/etc/ssh/sshd_config.d/99-hardening.conf`). Recovery path is the provider's
  web console (verified working). Deploys run as the non-root `amm` user, member
  of the `docker` and `sudo` groups.
- The box is shared with another lightweight project: the stack runs with
  `deploy/docker-compose.prod.4gb.yml` (api 1G/1.5cpu, caddy 256M/0.5cpu limits) and
  must keep ≥1G free. Check coexistence after any release with `docker stats` and the
  co-tenant's health endpoint.

## Secrets

- `/etc/amm-ds-portfolio.env` (root-owned, `chmod 600`): `IMAGE`, `DOMAIN`,
  `ACME_EMAIL`, `IP_HASH_SALT`, `CONTACT_PHONE` (quoted — the value contains spaces;
  unquoted breaks `set -a; . file`). `TAG`/`BUILD_SHA` are exported per release,
  never stored.

## Release

```bash
ssh <deploy-user>@<deploy-host>        # per the operator's SSH config
cd /opt/amm-ds-portfolio
git pull --ff-only
set -a; . /etc/amm-ds-portfolio.env; set +a
export BUILD_SHA="$(git rev-parse HEAD)" TAG="$(git rev-parse --short HEAD)"
# TAG and BUILD_SHA are REQUIRED for every compose command on this box —
# forgetting them makes compose try to pull amm-ds-portfolio:latest, which
# does not exist in any registry.
docker build \
  --build-arg VITE_SITE_URL="https://${DOMAIN}" \
  --build-arg VITE_BUILD_SHA="${BUILD_SHA}" \
  -t "${IMAGE}:${TAG}" .
docker compose -f deploy/docker-compose.prod.yml -f deploy/docker-compose.prod.4gb.yml \
  --env-file /etc/amm-ds-portfolio.env up -d
# smoke test (DEPLOY.md suite) against https://alejandromerida.dev, then:
docker stats --no-stream   # co-tenant headroom check
```

Rollback: DEPLOY.md, using the recorded previous tag (keep the last image until the
new one passes smoke).

## Plan B — build off-box

If an on-server build ever OOMs (swap makes it unlikely): build in CI, then
`docker save amm-ds-portfolio:<tag> | gzip | ssh <deploy-host> 'gunzip | docker load'`.

## What is NOT deployed here

The `apps/document-intelligence` stack (Postgres + API + worker) stays local/staging per
DEPLOY.md; its public path needs a gateway-identity deployment that this box does not
provision. The opt-in RAG chat path (`RAG_CHAT_ENABLED`) stays off: the standard image
ships neither the `rag_agent` package nor a retrieval index.

## History

- 2026-11-08 — first cutover, tag `191a4ce`. Three latent bugs found only by a real
  boot and fixed in `bd60eed` (CMD glob-expansion of `FORWARDED_ALLOW_IPS=*`),
  `db4fc13` (`DAILY_LIVE_BUDGET=10.0` float crashed `int()` parsing), `191a4ce`
  (theme-boot inline script violated the strict SPA CSP). CI now guards the CSP path;
  consider extending CI to actually boot the prod compose stack, which would have
  caught the first two. Hardened the same day: non-root deploy user, root/password
  SSH disabled, fail2ban; connection details removed from this file.
