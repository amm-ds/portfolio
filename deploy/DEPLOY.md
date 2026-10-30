# Deployment

## Supported topology

The supported self-hosted path is one Docker image serving the React SPA and
FastAPI, behind Caddy on a single VPS. Caddy terminates TLS; only its ports 80
and 443 are published. The API has no host port and keeps no database.

A future hybrid split may put the static SPA on Cloudflare Pages and the API on
a VPS. That is not the current deployment contract: do not follow this guide as
if the two origins had already been separated.

## Prerequisites

- A VPS with Docker Engine and the Compose plugin.
- A public DNS `A`/`AAAA` record for the chosen hostname pointing at the VPS.
- Inbound TCP 80 and 443 open for Caddy and automatic certificate issuance.
- The repository (or the built image plus `deploy/`) on the host.

## Build and launch

Run from the repository root. `IMAGE` and `TAG` select exactly the same image
for build, launch, later inspection, and rollback; `BUILD_SHA` identifies the
runtime in `/health`. The site URL and build SHA are compiled into the SPA.

```bash
export IMAGE=amm-ds-portfolio
export BUILD_SHA="$(git rev-parse HEAD)"
export TAG="$(git rev-parse --short HEAD)"
export DOMAIN=portfolio.example.com       # replace with your real DNS name
export ACME_EMAIL=you@example.com         # ACME renewal advisories go here
export IP_HASH_SALT="$(openssl rand -hex 32)"

# Keep IP_HASH_SALT in the host's protected environment, not in git.
docker build \
  --build-arg VITE_SITE_URL="https://${DOMAIN}" \
  --build-arg VITE_BUILD_SHA="${BUILD_SHA}" \
  -t "${IMAGE}:${TAG}" .
docker compose -f deploy/docker-compose.prod.yml up -d
docker compose -f deploy/docker-compose.prod.yml ps
```

`DOMAIN`, `ACME_EMAIL`, and `IP_HASH_SALT` are required by Compose; there is
no placeholder hostname, ACME contact, or production default salt. Caddy
waits for the API `/ready` probe to return 200 before starting. Reuse the
same exported variables for every later Compose command, or place them in a
protected environment file passed with `--env-file` (never commit that file).

## Configuration

### SPA build time

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_SITE_URL` | `https://amm-ds.github.io/portfolio` | Canonical public base URL used by app links, static canonical/Open Graph/Twitter metadata, robots, and sitemap. Changing it requires a rebuild. |
| `VITE_BUILD_SHA` | `dev` | Commit exposed in the static `build-sha` meta tag for build attribution. Public, not a secret. |

For a source/web-only build, run `VITE_SITE_URL=https://public.example uv run
python scripts/gen_sitemap.py` before `npm run build`. With no override, the
script preserves the GitHub Pages default. Docker performs this generation in
its metadata stage.

### API runtime

| Variable | Default | Purpose |
| --- | --- | --- |
| `BUILD_SHA` | `dev` | SHA returned by `/health`; set it to the image's source commit. |
| `IP_HASH_SALT` | required in prod compose | Salt for the 12-character client-IP hashes in logs. Use a long random value and rotate only deliberately. |
| `RATE_LIMIT_PER_MINUTE` | `30` | Per-client-IP POST token-bucket refill rate; burst is 10. In-memory, per process, and reset on restart. |
| `DAILY_LIVE_BUDGET` | `1000` | Per-process, per-UTC-day cap on the live POST inference calls (`/forecast`, `/score`, `/solve`). At 80% a WARNING logs once per day; past the cap the endpoints answer 503 (with the demo-replay hint) until the day rolls over. |
| `LIVE_KILL_SWITCH` | unset | Circuit breaker: exactly `1` makes every live POST endpoint answer 503 immediately ("live inference temporarily disabled" + demo-replay hint). Recreate the container with the variable emptied to restore. |
| `RAG_CHAT_ENABLED` | unset | Kill switch. Only exactly `1` registers `/rag/chat` and `/rag/chat/stream`; unset/empty disables them. |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | unset | Optional OpenAI-compatible provider. Without it, Project 01 uses Ollama. |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | host gateway / `qwen3:32b` | Optional local-provider connection for the opt-in RAG path. |
| `LLM_TIMEOUT` | `60` | Provider request timeout in seconds. |
| `LLM_COST_LIMIT_USD` | `3.00` | Per-process cloud-equivalent budget guard, not a provider billing limit. |
| `LLM_MAX_REQUESTS` | `400` | Per-process request budget. |
| `LLM_TOTAL_TOKENS_LIMIT` | `4000000` | Per-process token budget. |
| `FORWARDED_ALLOW_IPS` | `*` in the isolated compose network | Uvicorn trusted-proxy setting; see below. |

The normal 02/05/06/07 serving endpoints need no LLM key. RAG chat is off by
default, and enabling its kill switch is not sufficient by itself: the standard
image deliberately contains neither the `rag_agent` package nor the retrieval
index. Build Project 01 with `cd projects/01-rag-agent && uv run dvc repro`,
use an image that installs Project 01, mount its corpus/index, and configure a
provider plus budgets before enabling chat. Hugging Face models also need a
writable `HF_HOME` volume because the production root filesystem is read-only.

To stop RAG cost exposure immediately, recreate the API with the kill switch
off (a brief interruption is expected):

```bash
RAG_CHAT_ENABLED= docker compose -f deploy/docker-compose.prod.yml up -d --no-deps api
```

## Live-inference kill switch and daily budget

The artifact-backed POST endpoints (`/projects/02…/forecast`,
`/projects/05…/score`, `/projects/07…/forecast`, `/projects/06…/solve`) share
two fail-closed guardrails (see the `LiveGuard` in `showcase_api.main`):

- Kill switch. Set `LIVE_KILL_SWITCH=1` (recreate the API) or drop a
  `/tmp/live_disabled` file inside the container. Every live call then
  answers 503 with a hint that the precomputed demo replay still works.
  The file flag is the in-incident breaker (the compose container's `/tmp` is
  an ephemeral tmpfs, so it vanishes on recreate); the env var is the durable
  one. Either way, read-only artifact GETs are unaffected.

  ```bash
  # fastest circuit break — no recreate; survives until the container restarts
  docker compose -f deploy/docker-compose.prod.yml exec api touch /tmp/live_disabled
  # restore
  docker compose -f deploy/docker-compose.prod.yml exec api rm /tmp/live_disabled

  # durable switch
  LIVE_KILL_SWITCH=1 docker compose -f deploy/docker-compose.prod.yml up -d --no-deps api
  ```

- Daily budget. `DAILY_LIVE_BUDGET` (default 1000) caps live POST calls per
  process per UTC day; the counter is in-memory and resets on restart/day
  rollover, and a one-time WARNING logs at 80%. It is a floor against
  runaway clients, not a quota system.

## Logs

Both containers log to stdout and Docker's `json-file` driver with
10 MB × 3 rotation (`max-size: 10m`, `max-file: "3"` per service):

```bash
docker compose -f deploy/docker-compose.prod.yml logs --since 24h api
docker compose -f deploy/docker-compose.prod.yml logs caddy   # access + TLS
```

API request lines carry method, path, status, latency, request id, and a
12-char salted client-IP hash — never raw IPs or bodies. Expect one
`WARNING` at API startup when `IP_HASH_SALT` is unset (the built-in default
salt is public; see the configuration table above). To retain logs beyond
the rotation window, ship them off-host with your log collector of choice;
the app writes nothing else to disk.

## Automated vs manual boundary

Nothing deploys or rolls back automatically: pushing to `main` builds and
verifies in CI, but the image that serves production is built, tagged,
launched, smoke-tested, and rolled back by a human on the host using the
commands in this guide. Scheduled GitHub Actions touch the repo only — the
nightly validation suite, the weekly drift observatory (which files an issue
on regression), and the rotating pipeline repro. All three stop at
notifications/artifacts; none of them reaches the VPS. Day-2 operations that
remain manual by design: enabling RAG chat (kill switch + provider + budget
review), rotating `IP_HASH_SALT` (log-hash correlations reset), raising
`DAILY_LIVE_BUDGET`, and any rollback (record the known-good tag first, then
re-create the API and re-run the smoke test).

## Trusted proxy boundary

Caddy is the sole published service and overwrites forwarding headers before
proxying to the API. Uvicorn must trust those headers for per-client rate
limiting and salted log hashes. The compose default `FORWARDED_ALLOW_IPS=*` is
therefore safe only while the API remains unpublished on the private compose
network. Do not publish port 8000 or attach untrusted containers to that
network with this setting. For any other topology, set `FORWARDED_ALLOW_IPS` to
the proxy's literal IP or comma-separated trusted IPs; uvicorn does not resolve
Docker service names for this option. With multiple proxies, also retain their
outer rate limits—the application limiter is not DDoS protection.

## Smoke test

```bash
BASE="https://${DOMAIN}"
curl -fsS "$BASE/ready"
curl -fsS "$BASE/health" | python3 -c \
  'import json,sys; r=json.load(sys.stdin); assert r["ready"] and r["sha"] == "'"$BUILD_SHA"'"'
curl -fsS "$BASE/" | grep -q 'id="root"'
curl -fsS "$BASE/projects/06-routing-optimization" | grep -q 'id="root"'
curl -fsS "$BASE/projects" | grep -q '"id":"01-rag-agent"'
curl -fsS "$BASE/projects/05-ml-pipeline-churn/metrics" \
  | grep -q selected_model_calibrated
curl -fsS "$BASE/robots.txt" | grep -q "Sitemap: https://${DOMAIN}/sitemap.xml"
curl -fsS "$BASE/sitemap.xml" | grep -q "<loc>https://${DOMAIN}/</loc>"
```

Also inspect HSTS, CSP, `nosniff`, `Referrer-Policy`, and
`Permissions-Policy` response headers. CI's Docker smoke builds request bodies
from committed metadata and validates real 02/05/07 inference responses; use
`apps/showcase-api/SERVING.md` for equivalent curl contracts.

## Recreate and rollback

Updates and rollbacks recreate the single API container and can cause a brief
interruption; this is not a zero-downtime deployment. Caddy certificate volumes
are persistent and independent of image rollbacks.

Before moving forward, record the current known-good tag and SHA. To roll back,
select the previous image explicitly and wait for readiness before declaring
success:

```bash
export TAG=<previous-tag>
export BUILD_SHA=<previous-full-commit-sha>
docker compose -f deploy/docker-compose.prod.yml up -d --no-deps api
docker compose -f deploy/docker-compose.prod.yml ps
# Re-run the smoke test above. Keep the newer image until rollback is verified.
```

If the previous image is no longer present, rebuild that exact commit with the
same build arguments. Serving bundles are committed, but a source rebuild is
not claimed to be bit-for-bit identical. Do not prune either image until the
active version passes smoke tests. There is no application database to roll
back; Caddy's certificate/configuration volumes are the only persistent host
state in this topology.

## Privacy posture

No analytics or cookies are configured. Request logs contain paths, status,
latency, request IDs, and salted client-IP hashes—not raw IPs or request
bodies—and Docker retains those logs under the configured rotation policy.
Rate-limit buckets live only in process memory. Do not add third-party
analytics without revisiting this posture and the public privacy copy.
