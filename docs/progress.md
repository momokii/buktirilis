# BuktiRilis — Implementation Progress

Product: self-hosted security testing workspace. Engine: Strix OSS (pinned `v1.7.1` adapter).
Browser UI: React/TypeScript. Backend/worker: Python/FastAPI. DB: PostgreSQL.

## Milestones

| # | Milestone | Status | Commit |
|---|---|---|---|
| M1 | Inspection, contract, foundation (Git, schema, auth, policy, worker, tests) | Completed | `a0eeedb` |
| M2 | Browser vertical slice: project/build/run/report/finding, filters, scroll restoration | Completed | `0b9d286` |
| M3 | Evidence, automatic + guided retest, reviewer acceptance, readiness | Completed | `0b9d286` |
| M4 | Frozen PDF/CSV/JSON exports with snapshots | Completed | `0b9d286` |
| M5 | Worker, live Strix adapter, synthetic lab, isolation preflight | Adapter implemented; live execution **not observed** | `a0eeedb` + `0b9d286` |
| M6 | Release Scan, discovery, comparison, final browser verification | Completed (demo path) | `0b9d286` + `27fedbe` |

## What is delivered

- FastAPI API + separate worker + PostgreSQL + Docker Compose for a single host.
- Role-scoped accounts (admin/operator/developer/viewer), Argon2id passwords, cookie sessions,
  CSRF, login rate limits, audit events, encrypted test credentials.
- Immutable target-policy revisions, builds, OpenAPI validation/sanitization, expected and
  attested build identity, run preflight, quotas, cancellation, lease reconciliation.
- Versioned Web & API Access Control profile; Quick/Standard depth; OWASP references.
- Findings with evidence provenance, evidence-status/retest-method/verification separation,
  positive-control replay, guided retest packages, review acceptance, dispositions.
- Release Scan plan snapshot at submission, known-finding replay, discovery, comparison
  buckets, latest-verification panel.
- PDF/CSV/JSON exports generated server-side and frozen in DB + artifact volume.
- React workspace at 1440 px and 390 px with accessible tabs, dialogs, tables, evidence
  panels, empty/error/loading states, and a demo-mode banner.
- Synthetic Atlas Billing lab with three deployments + identity-mismatch build; deterministic
  demo artifacts labelled as such.

## Verification performed (2026-11-14)

Environment: Python 3.12.3, Node 22.23.4, Docker 29.3.1 / Compose v5.1.1, PostgreSQL 16
container on `127.0.0.1:55432`, lab on `127.0.0.1:8099`.

| Check | Command | Result |
|---|---|---|
| Backend lint | `cd backend && .venv/bin/ruff check app tests` | **Passed** |
| Backend format | `cd backend && .venv/bin/ruff format --check app tests` | **Passed** |
| Backend types | `cd backend && .venv/bin/mypy app` | **Passed** (38 files) |
| Backend tests | `cd backend && .venv/bin/python -m pytest` | **80 passed** |
| Web types | `cd web && npm run typecheck` | **Passed** |
| Web build | `cd web && npm run build` | **Passed** (production bundle) |
| Browser E2E | `cd web && npx playwright test` | **9 passed** (1440 + 390) |
| Accessibility | axe-core via Playwright, WCAG 2 A/AA + 2.1/2.2 AA | **No serious/critical violations** |
| Migrations | `alembic upgrade head && alembic check` | **No pending model diff** |
| Fresh seed | new DB → `alembic upgrade head` → `python -m app.cli seed-demo` | **Passed**; 4 users, 1 project, 3 runs, 4 findings, 5 exports |
| PDF output | pypdf on the seeded snapshot | **6 pages**, has snapshot time + limitations |
| CSV/JSON | parsed seeded exports | findings/coverage agree; no credential values |
| Compose syntax | `docker compose config` (base + demo profile) | **Valid** |
| Isolation probe script | `bash -n scripts/verify-isolation.sh` | **Syntax passed**; execution requires the provisioned worker |

Evidence screenshots: `docs/screenshots/` (report overview, filtered findings, finding
detail, coverage, comparison, 390 px report/findings/finding).

### Specific acceptance paths

- **First launch / demo report:** Verified via fresh database seed and browser login.
- **Baseline / preflight:** Verified; denied host and unapproved OpenAPI override fail closed
  in API and policy tests; duplicate submission returns the same queued run.
- **Explain the scan:** Verified in browser and tests; counts match rows; budget-stopped and
  incomplete coverage are explicit.
- **HTTP finding:** Verified against the real lab: Still reproducible on `2024.10.1`,
  Fix verified on `2024.10.2`, expired auth/missing fixture/failed control/identity mismatch
  all inconclusive.
- **Guided retest:** Verified in browser: submission stays pending until operator acceptance.
- **Release Scan:** Verified: `2024.10.2` fix verified, `2024.10.3` regression, export
  still reproducible, guided/weak items pending, insufficient/no-evidence cases awaiting.
- **Cancellation / revocation / interruption:** Verified in backend tests (cancel before
  discovery, revoked membership, narrowed policy, expired lease, no redispatch).
- **Exports:** Verified PDF pages/text, CSV quoting and formula neutralization, JSON schema
  and redaction, frozen snapshot stability after a later retest.
- **Access isolation:** Verified; another user gets 404 for project, run, finding, evidence,
  artifact, and export routes; viewer cannot start a retest.
- **UI quality:** Verified at 1440 and 390; no page-level horizontal overflow; keyboard tab
  navigation and axe scan pass.

## Blocked / not verified

- **Live Strix execution**: not observed. Requires a provisioned worker with the pinned
  `v1.7.1` CLI, an approved model/provider, and a permitted staging target. The adapter is
  implemented and contract-tested with a fake CLI only.
- **Sandbox network isolation**: documented topology provided, but not demonstrated on this
  host. Do not enable `LIVE_EXECUTION_ENABLED` until the allowed-target, denied-local, and
  out-of-scope-redirect probes pass on the deployment.
- **Real linked HTTP evidence sample**: contract parser handles `http_exchanges.json`; no real
  `v1.7.1` sample was available, so only its absence handling is verified.
- **DNS pinning**: resolution is checked, but the connection is not pinned; require an
  enforcing gateway for rebinding-sensitive targets.

## Next action

1. Provision the isolated worker and model, pin the Strix image digest, and run the three
   isolation probes in `docs/deployment.md`.
2. Run one live baseline against the controlled lab target; compare its normalized records
   with the fixture contract and record the observed artifact shapes.
3. Run `scripts/verify-isolation.sh` inside the worker network namespace and record the
   allowed/denied/redirect output in the runbook.
4. Add the observed real artifact sample as a regression fixture (sanitized) before enabling
   live mode for the pilot group.
