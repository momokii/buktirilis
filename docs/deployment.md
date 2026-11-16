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

# Create the first administrator (web bootstrap is disabled outside development):
docker compose exec -T api python -m app.cli bootstrap-admin --email admin@example.internal <<< 'a-long-initial-password'
```

The CLI reads the password from stdin when no TTY is attached; change it after first sign-in.
Alternatively use `--password-env VAR` with a one-time environment value. Web-based first-admin
creation is allowed only in `APP_ENV=development`.

Break-glass password reset (also revokes existing sessions):

```bash
docker compose exec -T api python -m app.cli reset-password --email admin@example.internal <<< 'new-long-password'
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

### Tailscale-only access (verified deployment)

Bind the web service to the tailnet address instead of a LAN/public interface:

```dotenv
APP_ENV=staging
WEB_BIND=100.x.y.z          # the node's Tailscale IPv4 address
WEB_PORT=8088
PUBLIC_ORIGIN=http://100.x.y.z:8088
COOKIE_SECURE=false         # plain HTTP inside the WireGuard tailnet
DEMO_SEED_ENABLED=true      # demo pilot only
```

```bash
docker compose --profile demo up -d --build
docker compose --profile demo exec -T api python -m app.cli seed-demo \
  --credentials-file /srv/var/demo-credentials.txt
docker compose cp api:/srv/var/demo-credentials.txt var/demo-credentials.txt
chmod 600 var/demo-credentials.txt
curl -fsS http://100.x.y.z:8088/api/health
```

Only the `web` container publishes a port, and only on the Tailscale address. API, database,
and lab stay internal/loopback. `make deploy` automates the same sequence.

Tailscale already encrypts traffic in transit, but browsers will treat the origin as plain
HTTP, so `COOKIE_SECURE=false` is required; restrict the bind to the tailnet and keep the ACL
limited to the pilot group. If the Tailscale CLI is available, prefer
`tailscale serve` (or a trusted TLS reverse proxy) and then set `COOKIE_SECURE=true` and an
`https://` `PUBLIC_ORIGIN`.

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

A reproducible probe ships in `scripts/verify-isolation.sh`. Run it **inside the worker
network namespace** (not on the web host):

```bash
APPROVED_TARGET=http://127.0.0.1:8099/deployments/2024.10.1 \
  ./scripts/verify-isolation.sh
```

On the worker VM, enforce the contract with host firewalling before the probe. Example
nftables policy (adapt names/IPs; provider endpoint is the only other allowed outbound):

```nft
table inet buktirilis {
  chain output {
    type filter hook output priority 0; policy drop;
    oif "lo" accept
    ip daddr <staging-ip> tcp dport { 80, 443 } accept
    ip daddr <provider-ip> tcp dport 443 accept
    ct state established,related accept
    meta l4proto { icmp, ipv6-icmp } accept
    counter log prefix "buktirilis-egress-deny " drop
  }
}
```

Also block the container bridge from the host management network and metadata routes.
Record the probe output in the deployment runbook. Until then, keep
`LIVE_EXECUTION_ENABLED=false`; demo runs remain fully usable.

> The worker must run on its own host/VM. Do **not** mount the host Docker socket into the
> web or API containers. If the pinned Strix runtime requires daemon access to launch its
> child sandbox, that daemon belongs to the dedicated worker VM and its network policy, not
> to the application host.

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
- Live authenticated exploration is not enabled in this release: the adapter deliberately
  never writes test credentials into the engine instruction or workspace, and the model can
  see whatever the engine sends it. Authenticated cross-tenant checks are covered by
  BuktiRilis's own constrained replays. A live credential-injection path needs its own
  threat review, short-lived tokens, and artifact sanitization before it can be enabled.

## 5. Evidence retention

`EVIDENCE_RETENTION_DAYS` (default `0`, unlimited) is the documented window. To prune raw
captures older than 90 days:

```bash
docker compose exec -T api python -m app.cli prune-evidence --days 90 --dry-run
docker compose exec -T api python -m app.cli prune-evidence --days 90
```

The evidence row, summary, finding, accepted observations/verdicts, and frozen export bytes
remain. Raw payloads/attachments and their artifact files are removed and the row is marked
pruned; it is never presented as proof. Schedule the command with the host timer after
reviewing the policy.

## 6. Operational checks

```bash
curl -fsS http://127.0.0.1:8080/api/health
docker compose exec api python -m app.cli check
docker compose logs --tail=100 api worker
```

The Settings screen shows queued/running jobs and flags a queue with no running worker.
An interrupted worker is recorded as `interrupted`; its partial artifacts remain viewable
with an incomplete label and are not redelivered automatically.
