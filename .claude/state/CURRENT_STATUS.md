## Project Phase
First internal release and a single-VM live Strix pilot are observed. The demo path is
complete; the live engine runs through the bundle but the chosen target has no
authentication/tenant boundary and coverage is incomplete.

## Completed
- [x] Product foundation: FastAPI API + worker + PostgreSQL/Alembic + React/TS workspace
- [x] Auth: Argon2id, cookie sessions, CSRF, login rate limits, audit events, role checks
- [x] Target policy, builds, OpenAPI sanitisation, identity observation/attestation
- [x] Run preflight, quotas, worker lease, cancellation, interruption, evidence and exports
- [x] Single-VM Compose profile (`compose.mono.yaml`) with worker-only Docker socket,
      pinned Strix 1.7.1, Docker CLI, resource limits, and no-new-privileges
- [x] Live pilot: target `http://100.124.184.116:3100`, run
      `69cbc6dc-a42b-4822-aac6-914b64f9073f`, Strix 1.7.1 completed in 36m 6s
      (111 requests, 7.9M tokens), 0 findings, 4/12 checks tested, 7 not run, 1 needs review
- [x] Live artifacts/report/JSON+PDF exports generated; OpenCode Go `x-opencode-session`,
      Docker CLI, and sandbox-image setup fixed
- [x] 103 backend tests; web typecheck/build and 14 Playwright tests previously pass
- [x] Fresh-database migrate + seed and documentation

## In Progress / Next
- [ ] Run against `http://100.124.184.116:8501` (BoxBox Replay) or an authenticated target;
      3100 is anonymous public read-only, so the access-control profile has no natural object.
- [ ] Complete or explicitly accept the seven unresolved Strix coverage gaps; do not call
      them clean.
- [ ] Re-ingest/supersede the historical live run; it is `ingest_state=partial` because it
      predates clean-SARIF handling.
- [ ] Enforce host egress isolation or move the worker to a dedicated VM.

## Blocked
- Same-VM Docker socket is root-equivalent and host firewall/egress isolation is not
  enforced on this host. Keep this as a local-dev compromise, not a production pilot.
- `make security` currently fails: npm audit reports 4 high dev-only ReDoS advisories in
  `picomatch`/`fdir`/`tinyglobby`/`vite`; no patched version in the current line. Runtime
  bundle is static nginx output, but the Security Gate is not green.
- GitHub Actions remains unverified until a remote push.
- The OpenCode Go key used in the pilot was exposed in chat; rotate it and update `.env.live`.

## Open Questions
- Which target/profile the pilot group wants next: 8501, an authenticated app, or a
  controlled lab.
- Whether the internal reverse proxy or an enforcing gateway owns TLS/path policy.
- Whether to upgrade Vite across a major version for the dev-only audit advisory.

## Security Notes
- Every route enforces project access server-side; cross-project object access returns 404.
- Session cookies are HttpOnly/SameSite=Lax; Secure is forced outside development.
- Mutations require the per-session CSRF header; login failures are rate-limited.
- Test credentials are Fernet-encrypted and never returned; evidence is redacted at creation
  and export; missing artifacts are marked unavailable, not presented as proof.
- Live worker has the Docker socket; web/API do not. It is a documented risk on this host.
- `.env.live` is mode 600 and gitignored; the key is not committed. Rotate it after the pilot.
- Demo and live records remain separated by `mode`; demo fixtures are never used live.

## Last Updated
2026-11-18: live single-VM Strix pilot observed on 3100; 0 findings, 7 coverage gaps;
adapter/clean-SARIF fixes and docs updated. 103 backend tests pass; npm audit gate fails.
