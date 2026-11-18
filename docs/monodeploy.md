# Single-VM monodeploy (v1)

This is the requested first-version topology: PostgreSQL, API, worker, web, synthetic lab,
and the live Strix worker all on **one machine**. It is intentionally simple; the security
boundary is weaker than the separate-worker topology in `docs/deployment.md`.

## Security layers in this profile

- Web and API containers have **no Docker socket**.
- Only the worker gets `/var/run/docker.sock`, because Strix launches a sandbox container.
- Worker has `no-new-privileges`, dropped capabilities, memory and PID limits.
- The web port binds to an explicit interface; API, database, and lab stay internal.
- The live model key and target credentials live in gitignored env files, never in images.
- Target policy, redirect re-validation, loopback controls, credential encryption, and
  worker re-authorization remain active.

**Accepted local risk:** Docker socket access is root-equivalent. A compromised sandbox or
worker can reach host Docker, the app database/API, metadata, and other tailnet services.
Use host firewall rules to allow only the approved target and model endpoint from the
sandbox network, or move the worker to a dedicated VM for a pilot. Do not expose this host
publicly.

## Configure

```bash
cp .env.live.example .env.live
chmod 600 .env.live
# edit .env.live: paste LLM_API_KEY (OpenCode Go key) in your own terminal
# optional: LLM_API_BASE, STRIX_MODEL
```

`STRIX_MODEL=openai/deepseek-v4.1-flash` and
`LLM_API_BASE=https://opencode.ai/inference/go/openai/v1` match the OpenCode Go endpoint.
The key is only passed to the worker; the browser never sees it.

## Start

```bash
docker compose -f compose.yaml -f compose.mono.yaml up -d --build api worker
docker compose ps
curl -fsS http://${WEB_BIND}:${WEB_PORT}/api/health
```

The base stack (db/web) is started by the same command. The demo seed is not enabled in
this profile; existing demo records remain, but new runs are live. Register the live target
as a new project in the UI or API.

## Target setup

- Base URL must be the worker-visible target: for a target on this host use the Tailscale
  address, e.g. `http://100.124.184.116:3100`, not `localhost` (inside the sandbox,
  localhost is the sandbox).
- Attest the expected build identity if the target has no `/api/meta`; the run records the
  attestation and notes that identity was not observed.
- With no target credentials, select an unauthenticated run and acknowledge reduced scope.
  For authenticated scans, add test identities with short-lived bearer tokens in the
  project settings; the worker probes identity/fixtures before discovery.

## Verify one live scan

```bash
docker compose -f compose.yaml -f compose.mono.yaml logs -f worker
# In BuktiRilis: project -> build -> New run -> live mode, quick depth
```

A live run must show `mode=live`, engine version `1.7.1`, real coverage/artifacts, and a
healthcheck identity result. Demo fixtures are never used in live mode.

## Switch back to demo / stop

```bash
# stop the socket-bearing worker; keep data
docker compose -f compose.yaml -f compose.mono.yaml stop worker
# normal demo profile
docker compose --profile demo up -d worker
```

## Limits

Live execution was observed on 2026-11-18 against `http://100.124.184.116:3100`: Strix
`1.7.1` completed a quick unauthenticated run with 0 findings, 4 tested checks, 7 unresolved
gaps, and full artifact/report/export ingestion. That proves the bundle works, not that the
target is clean or fully covered.

Sandbox egress isolation is still not enforced by this profile; the socket and same-host
target make host services reachable unless the host firewall restricts the sandbox network.
The worker received the host Docker socket for this local test. For production, use the
dedicated worker + deny-by-default boundary from `docs/deployment.md`.
