# Deployment and operations

BuktiRilis targets a single Linux host with Docker Compose: PostgreSQL, the API, the worker,
and the web server (nginx). The demo lab is an optional Compose profile. Live Strix execution
requires a separately hardened worker boundary described below.

## 1. Single-host Compose

```bash
cp .env.example .env
# Edit .env:
#   APP_ENV=production
#   BUKTIRILIS_SECRET_KEY=<48+ char random value>
#   POSTGRES_PASSWORD=<strong value>
#   PUBLIC_ORIGIN=https://buktirilis.internal.example
#   DEMO_SEED_ENABLED=false
#   ALLOW_LOOPBACK_LAB_TARGETS=false
#   LIVE_EXECUTION_ENABLED=false   # until the worker boundary is proven

docker compose up -d --build
docker compose ps
curl -fsS http://127.0.0.1:8080/api/health
```

Services:

| Service | Port | Notes |
|---|---|---|
| `web` | `127.0.0.1:8080` | nginx-unprivileged, read-only root, static build + `/api` proxy |
| `api` | internal 8000 | non-root, no Docker socket, runs migrations on start |
| `worker` | none | claims queued jobs with a lease; artifact + Strix run volumes |
| `db` | internal 5432 | PostgreSQL 16, persistent volume, healthcheck |
| `lab` | `127.0.0.1:8099` | demo profile only (`--profile demo`); synthetic data |

Persistent volumes: `db_data`, `artifacts`, `strix_runs`. Back them up together; an export
snapshot references stored bytes and the database row.

### Demo profile

```bash
docker compose --profile demo up -d --build
docker compose exec api python -m app.cli seed-demo
docker compose exec api python -m app.cli check
```

The lab binds loopback only. Do not expose it to a network; it contains deliberate flaws.

### TLS / reverse proxy

Put a trusted reverse proxy in front of `web:8080` (Caddy, nginx, or an internal load
balancer) and terminate TLS there. Set `PUBLIC_ORIGIN` to the public HTTPS origin, keep
`COOKIE_SECURE=true`, and forward `X-Forwarded-Proto`/`X-Forwarded-For`. The API enables
proxy headers in Compose. Do not enable HSTS until the internal domain is HTTPS-only.

## 2. Backup, restore, update, stop

**Backup** (adjust names/paths):

```bash
docker compose exec -T db pg_dump -U buktirilis -Fc buktirilis > buktirilis.dump
docker run --rm -v buktirilis_artifacts:/data -v "$PWD":/backup alpine \
  tar czf /backup/artifacts.tgz -C /data .
```

**Restore** into a fresh installation:

```bash
docker compose up -d db
docker compose exec -T db pg_restore -U buktirilis -d buktirilis --clean --if-exists < buktirilis.dump
docker run --rm -v buktirilis_artifacts:/data -v "$PWD":/backup alpine \
  sh -c 'cd /data && tar xzf /backup/artifacts.tgz'
docker compose up -d --build
```

**Update:** back up first, pull the new source/image, then:

```bash
docker compose build
docker compose up -d          # api applies Alembic migrations on start
docker compose ps
```

Migrations are forward-only. Never rewrite history; if a rollback is required, restore the
backup taken before the update.

**Stop:** `docker compose stop` (keeps volumes), `docker compose down` (keeps volumes), or
`docker compose down -v` **only** when you intend to destroy all data.

## 3. Live worker isolation (required before enabling live mode)

The API and web service must never hold the Docker socket. Strix launches its own child
sandbox container, so a Compose network on the wrapper alone does **not** constrain the
scan. The supported pilot topology:

1. **Dedicated worker host or VM** with the pinned Strix CLI (`v1.7.1`) and container runtime.
2. **Deny-by-default egress** for browser/proxy/terminal traffic. Allow only the approved
   staging origins (and the provider endpoint if the model is external) via a firewall or
   enforcing gateway.
3. **No route** from the sandbox to the control plane, database, cloud metadata
   (`169.254.169.254`), Docker management endpoints, or unrelated networks.
4. **Path-level enforcement** at the gateway if path restrictions must bind; a prompt-defined
   focus route is a search preference, not an authorization boundary.
5. **Dedicated artifact volume** mounted into the worker only, minimum state/credentials,
   short-lived test-only credentials for authenticated exploration.
6. **Resource limits and per-job deadlines** on the worker and sandbox; verify that
   cancellation tears down the sandbox (the adapter records unconfirmed cleanup and blocks
   blind redispatch).

Prove the boundary with three checks before the first live pilot:

- an allowed staging target returns the expected identity and a successful scan;
- a denied local destination (metadata, control plane) is refused by the worker;
- an out-of-scope redirect is refused rather than followed.

Record the results in the deployment runbook. Until then, keep
`LIVE_EXECUTION_ENABLED=false`; demo runs remain fully usable.

Strix's own container build and any bundled tooling (including Caido, if present in the
image) carry their own licence terms. BuktiRilis does not redistribute the image; confirm
the pinned image terms, telemetry defaults, and provider data-sharing before deployment.
See [docs/strix-contract.md](strix-contract.md) for the pinned contract and artifact names.

## 4. Credentials and rotation

- Session/CSRF material and test-account bearer credentials are derived/encrypted with
  `BUKTIRILIS_SECRET_KEY`. Losing the key makes stored credentials unrecoverable; rotating
  the key requires re-entering test credentials.
- Test credentials are encrypted at rest with Fernet (AES-128-CBC + HMAC) using a key derived
  from the deployment secret. They are never returned to the browser.
- Replay attempts source credentials **at execution time**. Rotating a credential therefore
  affects queued work and does not rewrite already-accepted evidence. Accepted observations
  and verdicts remain valid for their build unless the build identity or test conditions
  change.
- Provider/model keys belong to the worker environment only. They must not appear in run
  records, exports, or browser responses.

## 5. Operational checks

```bash
curl -fsS http://127.0.0.1:8080/api/health
docker compose exec api python -m app.cli check
docker compose logs --tail=100 api worker
```

The Settings screen shows queued/running jobs and flags a queue with no running worker.
An interrupted worker is recorded as `interrupted`; its partial artifacts remain viewable
with an incomplete label and are not redelivered automatically.
