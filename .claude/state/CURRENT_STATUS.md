## Project Phase
First internal release implemented and browser-verified. Demo path is complete; live Strix
execution remains unobserved pending worker provisioning.

## Completed
- [x] Product foundation: FastAPI API + worker + PostgreSQL/Alembic + React/TS workspace
- [x] Auth: Argon2id, cookie sessions, CSRF, login rate limits, audit events, role checks
- [x] Target policy revisions, builds, OpenAPI sanitisation, identity observation/attestation
- [x] Run preflight, quotas, demo fixtures, worker lease, cancellation, interruption
- [x] Evidence provenance/redaction, automatic replay recipes, guided retests, review acceptance
- [x] Release Scan planning, known-finding replay, discovery, comparison buckets
- [x] Frozen PDF/CSV/JSON exports with redaction and historical stability
- [x] 100 backend tests, 14 Playwright tests, axe scan, 1440 px and 390 px screenshots
- [x] Fresh-database migrate + seed: 4 users, 1 project, 3 runs, 4 findings, 4 exports
- [x] Documentation: README, deployment, Strix contract, decisions, progress

## In Progress
- [x] Demo pilot deployed via Compose on the Tailscale interface (http://100.124.184.116:8088)
- [x] Worker prerequisite probes, evidence-decision history, surface-absent reasons, OpenAPI
      discovery candidates, and the approved security guardrails
- [ ] Live Strix pilot provisioning remains the next milestone.

## Blocked
- Live Strix execution was not observed: no model credentials and no pinned engine image in
  the implementation environment. Adapter is contract-tested with a fake CLI.
- Sandbox network isolation is documented, not demonstrated on this host. Keep
  `LIVE_EXECUTION_ENABLED=false` until the three isolation probes pass on deployment.
- Security guardrails are configured and pass locally; GitHub Actions is unverified until a push.

## Open Questions
- Which provider/model and Strix image digest the pilot worker will use.
- Whether the internal reverse proxy or an enforcing gateway will own TLS/path policy.

## Security Notes
- Every route enforces project access server-side; cross-project object access returns 404.
- Session cookies are HttpOnly/SameSite=Lax; Secure is forced outside development.
- Mutations require the per-session CSRF header; login failures are rate-limited.
- Test credentials are Fernet-encrypted with a deployment-derived key and never returned.
- Evidence is redacted at creation; exports apply the same rules; missing artifacts are
  marked unavailable rather than presented as proof.
- Live execution needs deny-by-default egress; the web service must not hold a Docker socket.
- No real secrets are committed; demo credentials are generated into a gitignored file.

## Last Updated
2026-11-16: retention, guided-step revisions, and portable deployment complete (commit 02f86e1); 100 backend
and 14 browser tests pass, audits/image scan clean. Demo pilot redeployed; live execution and isolation remain
unverified pending a provisioned worker.
