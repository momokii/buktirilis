## Project Phase
Single-VM monodeploy is running with a live Strix worker on the same host as the app.
The operator accepted the local-only socket risk and explicitly rejected a separate VM.
This is ready for authorized local use, not for public/untrusted production.

## Completed
- [x] Product foundation: FastAPI API + worker + PostgreSQL/Alembic + React/TS workspace
- [x] Auth: Argon2id, cookie sessions, CSRF, login rate limits, audit events, role checks
- [x] Target policy, builds, OpenAPI sanitisation, identity observation/attestation
- [x] Run preflight, quotas, worker lease, cancellation, interruption, evidence and exports
- [x] Single-VM Compose profile (`compose.mono.yaml`) with worker-only Docker socket,
      pinned Strix 1.7.1, Docker CLI, resource limits, and no-new-privileges
- [x] Live pilot: target `http://100.124.184.116:3100`, run
      `69cbc6dc-a42b-4822-aac6-914b64f9073f`, Strix 1.7.1 completed in 36m 6s
      (111 requests, 7.9M tokens), 0 findings. The 4 tested / 7 not-run rows are
      plan-row bookkeeping, not a profile result; the run had no authenticated identities.
- [x] Live artifacts/report/JSON+PDF exports generated; OpenCode Go session, Docker CLI,
      sandbox image, and clean-SARIF handling fixed
- [x] 103 backend tests; web typecheck/build and 14 Playwright tests previously pass
- [x] Research note and corrected live-pilot interpretation
- [x] Fresh-database migrate + seed and documentation
- [x] User guide: 16 canonical Markdown pages under `web/src/content/guide/guide/`, rendered at
      `/guide` and readable on GitHub; `docs/user-guide.md` is a pointer. 12 guide tests pass.

## In Progress / Next
- [ ] Run the profile against the synthetic lab with two identities, fixtures, and an owner
      positive control. The lab has 6 accounts / 3 tenants; `:8501` has no account surface.
- [ ] Close the one real gap by manual replay: compare `GET /api/v1/cves/{id}` with
      `GET /api/v1/cves/batch?ids=`; the other six gaps are bookkeeping, not six tests.
- [ ] Re-ingest the historical run; its real artifacts now load as `status=complete`.
- [ ] Record the npm dev-only deferral; no patched `picomatch` exists.
- [ ] Keep `web/src/content/guide` and `anchors.ts` current when routes, labels, statuses, or
      retest paths change; run `cd web && npx playwright test e2e/guide.spec.ts`.

## Accepted local risks / Blocked
- Same-VM Docker socket is root-equivalent; the sandbox has `NET_ADMIN`/`NET_RAW`,
  `host.docker.internal`, and no host firewall. `:8501` is published on `0.0.0.0`.
  Accepted only for local authorized testing; do not expose this host publicly.
- `make security` fails on 4 high dev-only ReDoS advisories in
  `picomatch`/`fdir`/`tinyglobby`/`vite`; no patched version in the current line.
  Runtime is static nginx; the gate stays red.
- GitHub Actions remains unverified until a remote push.
- `.env.live` is mode 600 and gitignored; the key was not committed. It remains local and
  was not rotated at the operator's request. Chat exposure is accepted as local-only.

## Open Questions
- Which synthetic-lab scenario/profile to run next.
- Whether an authenticated real target will follow the lab.

## Security Notes
- Every route enforces project access server-side; cross-project object access returns 404.
- Session cookies are HttpOnly/SameSite=Lax; Secure is forced outside development.
- Mutations require the per-session CSRF header; login failures are rate-limited.
- Test credentials are Fernet-encrypted and never returned; evidence is redacted at creation
  and export; missing artifacts are marked unavailable, not presented as proof.
- Live worker is running with the Docker socket; web/API do not hold it.
- Demo and live records remain separated by `mode`; demo fixtures are never used live.

## Last Updated
2026-11-18: single-VM worker restored at the operator's request; local-only risk accepted.
No separate VM. Live pilot is adapter evidence; the synthetic lab is the next profile target.
