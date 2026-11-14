# Environment Guide

## Environment definitions
| Environment | Purpose | Characteristics |
|---|---|---|
| `development` | Local development | Debug may be on, verbose safe logs, hot reload, mock/sandbox services |
| `staging` | Pre-production validation | Production-like config, sandboxed real services, debug off |
| `production` | Live system | Debug off, minimal actionable logs, hardened config, real secrets |

## Identify before commands
- Establish APP_ENV from the active process's non-secret selector and the documented
  intended target; never read real env files, credentials, or dump environment values.
  Reading only the APP_ENV selector is permitted; it is not a secret.
- Confirm local versus remote endpoints and, for containers, daemon/context and file
  selection using non-secret metadata. Conflicting or absent evidence means unknown.
- `.env.example` is documentation, not evidence of the active environment. A real `.env`
  is gitignored and is never read by an agent.
- Verified local development target (2026-11-14): APP_ENV=development, PostgreSQL 16
  container `buktirilis-db-dev` on 127.0.0.1:55432, lab on 127.0.0.1:8099, API on 127.0.0.1:8000
  (or 8100 when occupied), Vite on 127.0.0.1:5173, worker in the same backend venv.
  Identify the active target from the process command/port metadata before mutating.
- Unknown means production-safe handling: no runtime/mutating commands until clarified.
  Local read-only inspection and explicitly requested scaffold/doc edits with no runtime
  target can proceed. Never guess development or silently export APP_ENV to bypass this.

## Agent behavior
- Development: verbose **non-sensitive** logs, dev tooling/debug ports, seed scripts,
  and migrations are allowed within task scope after confirming an isolated local target.
  Confirm destructive operations; never use production data or credentials.
- Staging/production contexts: present a written plan and obtain explicit confirmation
  before changes, migrations, or destructive operations; never modify live config/secrets.
- Never run commands against production, even with confirmation. Give production plans
  to an authorized operator. The agent should not hold production credentials; if detected,
  tell the user by location only and stop using them. Do not read them to verify detection.
- Confirmed staging work uses staging-only credentials supplied by the platform without
  exposing their values. Never run load/destructive tests on staging or production.

## Docker Compose pattern (conditional; Compose v2)
Use this pattern only if containerization is confirmed; no Compose files exist yet.
Use `docker compose`, not `docker-compose`, and omit obsolete top-level `version:`.
- `compose.yaml`: environment-agnostic base definitions; secure release image/service base.
- `compose.override.yaml`: development-only hot reload, debug ports, source volume mounts;
  automatically loaded by plain `docker compose up` when default discovery applies.
- `compose.prod.yaml`: explicit production overrides; pinned image tags, restart policy,
  resource limits, no source mounts/debug ports. Keep dev settings in dev overrides so
  Compose merging cannot accidentally retain them in production.

```bash
# Development example only: override file loads automatically under default discovery.
docker compose up

# Production OPERATOR example only; agents must not execute this.
# Explicit -f flags disable automatic loading of compose.override.yaml.
docker compose -f compose.yaml -f compose.prod.yaml up -d
```

Always ask before **any** Compose command not clearly development (including read-only
commands). Check APP_ENV, Docker context/daemon, COMPOSE_FILE and command flags using
safe metadata; allow-rule matches do not establish safety. An explicit `-f` invocation
does not match the baseline allow prefixes, but auto mode can classify it without a
prompt: the agent's duty to ask still applies. Do not print interpolated Compose config,
logs, or container environment if they could reveal secrets; prefer safe status metadata.
Follow and document existing filenames if a future project uses another convention.

## Environment files
```text
.env.example      # committed; every variable documented with placeholder + comment
.env              # never committed; local development values
.env.staging      # never committed
.env.production   # never committed; prefer deployment-platform secret injection
```
Never read/edit real env files as an agent; supply variable names and placeholders in
the example and let the user/platform provide values. Add each new secret-bearing
filename to settings.json's explicit Read/Edit denies before it is introduced.

## Configuration contract
- APP_ENV accepts development, staging, production; missing/unknown values select
  production-safe behavior (debug off). Stop startup when required secure config is absent.
- Centralize environment differences in validated configuration, not scattered hardcoded
  conditionals. Dev tools, debug endpoints, seed data, and admin tools must be absent or
  disabled in production images/configuration; production dependencies exclude dev tooling.
- Development/staging validate the same release artifacts used in production; optional
  local hot reload is a development convenience, not a separate release implementation.
- Test both development and production configuration locally with fake secrets and isolated
  services, including missing/unknown APP_ENV. Production-safe tests are not production access.

## Verified local setup (development)
```bash
make install                 # uv sync (backend/.venv) + npm ci (web/)
make db                      # PostgreSQL 16 container on 127.0.0.1:55432
make migrate                 # Alembic upgrade head
make lab                     # synthetic staging lab on 127.0.0.1:8099
make api                     # API on 127.0.0.1:8000 (VITE_API_TARGET can override the web proxy)
make worker                  # job worker (claims with lease)
make web                     # Vite on 127.0.0.1:5173
make demo                    # migrate + seed; lab must be running
curl -fsS http://127.0.0.1:8000/api/health
```
Health depends on the API and database only. The demo seed additionally needs the lab.
Tests create their own schema in the isolated `buktirilis_test` database and start a real
loopback lab fixture; they do not touch development data.

## Self-update
After foundation approval, replace examples with verified setup, health, migration,
and Compose commands and safe target-identification steps. Record production operator
instructions separately from commands an agent may execute. Preserve all safety rules.
