# Deploying BuktiRilis on another Linux host

This is the portable single-host demo deployment: PostgreSQL, API, worker, web, and the
synthetic Atlas Billing lab in Docker Compose. Live Strix execution has separate worker,
model, and isolation prerequisites described in `docs/deployment.md` and
`docs/strix-contract.md`.

## Requirements

- Linux x86_64 host with Docker Engine 24+ and Compose v2 (`docker compose version`)
- 2 GB RAM, 5 GB free disk (more for evidence/artifacts)
- `git`, `curl`, and `python3` (only used to generate local secrets)
- Inbound access only to the chosen web bind interface; API, database, and lab stay private

## One-command demo install

```bash
git clone <repository-url> buktirilis
cd buktirilis
./scripts/deploy.sh 127.0.0.1 8080
```

For tailnet-only access, pass the Tailscale IPv4:

```bash
./scripts/deploy.sh 100.x.y.z 8088
```

The script:

1. Creates `.env` with generated `BUKTIRILIS_SECRET_KEY` and database password, mode 600.
2. Builds and starts `db`, `api`, `worker`, `web`, and the `lab` Compose profile.
3. Applies Alembic migrations, seeds the deterministic demo, and copies
   `var/demo-credentials.txt` to the host (mode 600).
4. Verifies `/api/health` and prints the URL.

The seed is idempotent. Running the script again does not overwrite existing credentials;
use the password-reset command if needed.

## Manual equivalent

```bash
cp .env.example .env
# set APP_ENV=staging, BUKTIRILIS_SECRET_KEY, POSTGRES_PASSWORD, PUBLIC_ORIGIN,
# LAB_BASE_URL=http://lab:8099, DEMO_SEED_ENABLED=true, WEB_BIND, WEB_PORT
docker compose --profile demo up -d --build
docker compose --profile demo exec -T api python -m app.cli seed-demo \
  --credentials-file /srv/var/demo-credentials.txt
docker compose cp api:/srv/var/demo-credentials.txt var/demo-credentials.txt
chmod 600 var/demo-credentials.txt
docker compose --profile demo ps
curl -fsS "http://${WEB_BIND}:${WEB_PORT}/api/health"
```

## Access, TLS, and cookies

- The web port is published only on `WEB_BIND:WEB_PORT`. API, PostgreSQL, and the lab are not
  published (the lab is loopback-only when enabled).
- Plain HTTP inside a Tailscale/WireGuard tailnet works with `COOKIE_SECURE=false`.
- For browser-facing HTTPS, put Tailscale Serve or a trusted reverse proxy in front, set
  `PUBLIC_ORIGIN=https://<host>`, `COOKIE_SECURE=true`, and restart api/web. Do not expose the
  app publicly; this pilot is for private staging.
- If the bind interface or hostname changes, update `WEB_BIND`, `WEB_PORT`, and
  `PUBLIC_ORIGIN`, then `docker compose up -d web api`.

## Verify the installation

```bash
make deploy-status
curl -fsS http://<host>:<port>/api/health
docker compose --profile demo logs --tail=50 api worker
docker compose --profile demo exec -T api python -m app.cli check
```

Sign in with the `operator` account from `var/demo-credentials.txt`; open
**Atlas Billing → Runs → Open report**. Rotate the admin password after first use:

```bash
docker compose --profile demo exec -T api python -m app.cli reset-password \
  --email admin@demo.buktirilis.local
```

## Retention

Raw evidence payloads/attachments can be pruned while findings, verdicts, and frozen exports
remain:

```bash
make prune-evidence DAYS=90            # dry-run first: --dry-run is available via the CLI
docker compose --profile demo exec -T api python -m app.cli prune-evidence --days 90 --dry-run
docker compose --profile demo exec -T api python -m app.cli prune-evidence --days 90
```

Set `EVIDENCE_RETENTION_DAYS` in `.env` as the documented default; schedule the command with
your host's timer/cron after reviewing the policy. Pruned rows are marked in the UI.

## Backup, restore, update, stop

```bash
# backup
docker compose exec -T db pg_dump -U buktirilis -Fc buktirilis > buktirilis.dump
docker run --rm -v buktirilis_artifacts:/data -v "$PWD":/backup alpine \
  tar czf /backup/artifacts.tgz -C /data .

# update (back up first)
git pull
docker compose --profile demo build
docker compose --profile demo up -d    # api applies migrations

# stop without deleting data
docker compose stop

# full removal (destroys data; operator only)
# docker compose down -v
```

Volumes: `db_data`, `artifacts`, `strix_runs`. Keep them together; the database references
artifact IDs.

## Enabling live execution

The demo does not verify live Strix. Before enabling:

1. Read `docs/deployment.md` and `docs/strix-contract.md`.
2. Provision the isolated worker VM/host, approved model/provider, pinned Strix image, and
   authorized staging target.
3. Run `scripts/verify-isolation.sh` inside the worker network namespace and record the
   output.
4. Set `LIVE_EXECUTION_ENABLED=true`, `STRIX_MODEL`, and `DEMO_SEED_ENABLED=false` on the
   worker, then run one live baseline against the controlled lab before a pilot group.

Live authenticated exploration remains a deliberate security decision; the adapter never
writes credentials into the engine workspace.

## Parity checklist

The same Compose file, migrations, demo seed, UI, and API produce the same features on another
host. The only host-specific values are the bind address, public origin, TLS choice, secrets,
and (for live mode) the worker/model/target provisioning. Pin container image tags/digests in
your deployment runbook for release reproducibility.
