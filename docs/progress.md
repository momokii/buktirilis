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
| — | Hardening and final documentation | Completed | `ca9abd7`, `8c1de93`, `8575884`, `df9d798`, `1c6b039`, `02f86e1` |

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
| Backend tests | `cd backend && .venv/bin/python -m pytest` | **100 passed** |
| Web types | `cd web && npm run typecheck` | **Passed** |
| Web build | `cd web && npm run build` | **Passed** (production bundle) |
| Browser E2E | `cd web && npx playwright test` | **14 passed** (deployed tailnet URL, 1440 + 390) |
| Accessibility | axe-core via Playwright, WCAG 2 A/AA + 2.1/2.2 AA | **No serious/critical violations** |
| Migrations | `alembic upgrade head && alembic check` | **No pending model diff** |
| Fresh seed | new DB → `alembic upgrade head` → `python -m app.cli seed-demo` | **Passed**; 4 users, 1 project, 3 runs, 4 findings, 4 exports |
| PDF output | pypdf on the seeded snapshot | **6 pages**, has snapshot time + limitations |
| CSV/JSON | parsed seeded exports | findings/coverage agree; no credential values |
| Compose syntax | `docker compose config` (base + demo profile) | **Valid** |
| Isolation probe script | `bash -n scripts/verify-isolation.sh` | **Syntax passed**; execution requires the provisioned worker |
| Compose deployment | `make deploy` on this host | **Running** on `http://100.124.184.116:8088`; api/db/lab healthy, web bound to the tailnet address only |
| Deployed browser E2E | `E2E_EXTERNAL=1 E2E_BASE_URL=http://100.124.184.116:8088 ... npx playwright test` | **14 passed** |
| Restart persistence | `docker compose restart api worker web` | Login, 3 runs, and exports survived |

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

## Hardening pass after code review (2026-11-15)

Findings fixed and covered by tests:

1. **Cancelling a queued run left it stuck.** A run canceled before a worker claimed it
   stayed `cancel_requested` forever because no worker would claim a canceled job. Queued
   cancellation is now terminal immediately; reconcile also finalizes orphaned cancel
   requests.
2. **Queued retests did not re-check authorization.** A retest queued before membership or
   target-policy changes could still execute against the build's old policy. Execution now
   re-checks the current policy revision, requester access, recipe approval, and finding
   disposition; failures are inconclusive with no evidence.
3. **Comparison used live state instead of the selected snapshot.** A retest after the
   current run could change its comparison bucket. Current and baseline outcomes now use
   each run's completion snapshot; later work appears only in Latest verification.
4. **Historical exports could show a later verdict as the run's verdict.** Exports now use
   the run snapshot for the primary verification and label later evidence separately.
5. **Historical run finding membership could grow.** Later evidence on the same build no
   longer adds findings to a completed run's report; they appear in Latest verification.
6. **Cross-mode comparisons could still compute buckets.** Demo and live runs now return no
   bucket rows with an explicit incomparable state.
7. **Pending guided review reason was vague.** Changes-requested submissions report the
   reviewer reason instead of "no comparable retest".
8. **Release Scan did not re-check authorization at stage 2.** A policy narrowed during
   known-finding replay now stops discovery before it starts and marks the run failed
   with a recorded reason.
9. **Preflight did not probe identities/fixtures.** The worker now verifies each selected
   identity and planned recipe fixture against the approved target before discovery; any
   failure fails the run closed with the exact prerequisite listed.
10. **Evidence review state was not historical.** Evidence decisions are now append-only and
    comparisons/exports derive the status as of each run snapshot; current decisions are
    shown separately.
11. **Missing routes had no explicit reason.** An absent affected route now reports
    `surface_absent` / Awaiting verification instead of a generic "not tested" state.
12. **OpenAPI changes did not drive discovery.** Added/changed operations are recorded in the
    release plan, shown in the UI, and passed to the live engine instruction as focus routes.
13. **Security guardrails were absent.** Added pip-audit, npm audit, Bandit,
    detect-secrets baseline scanning, Trivy image scan, pinned CI actions, and dependency
    upgrades that cleared known CVEs. See `docs/security-guardrails.md`.
14. **Browser coverage gaps.** Added login/admin/settings axe checks, console-error checks,
    and run-wizard/admin 390 px tests.
15. **Operator-selected discovery routes were missing.** The run wizard and API accept
    relative routes; the release plan records them as discovery candidates and the live
    instruction receives them as focus routes.
16. **Baseline runs did not probe fixtures.** Approved project recipes are now probed even
    without a release plan.
17. **Prerequisite failures exposed raw exception text.** Probe failures are logged safely
    and return generic policy details; blocked scenarios are recorded and shown in coverage.
18. **Surface matching used substring checks.** Route presence now compares path segments
    with template placeholders, so concrete evidence routes match templated scopes and
    `/api/user` does not match `/api/users-admin`.
19. **Pre-migration evidence backfill was misleading.** A corrective migration stamps
    synthetic decisions at migration time and labels them; pre-migration comparisons fall
    back to current state and are documented as a limitation.
20. **Raw evidence had no retention policy.** `EVIDENCE_RETENTION_DAYS` and the
    `prune-evidence` command remove old raw payloads/attachments while retaining the
    evidence record, verdicts, and frozen exports; pruned rows are visibly marked.
21. **Guided steps could not be corrected by a reviewer.** Append-only
    `guided_step_revisions` let operators revise steps; the finding's original steps and
    prior revisions remain intact, and submissions record the revision followed.
22. **Deployment portability was undocumented.** Added `scripts/deploy.sh`,
    `docs/deploying-elsewhere.md`, retention operations, and a parity checklist.
23. **Reduced-scope recovery required a manual resubmission.** A failed prerequisite run now
    offers an explicit "Retry with passing identities" action that creates a new run from the
    identities that passed; fixture/build failures still require repair.
24. **Baseline fixture probing was over-broad.** Baselines now probe only selected identities;
    recipe fixtures are required for planned replays (release scans), not unrelated recipes.

Backend tests increased from 81 to **100**; browser tests from 11 to **14**.

## Blocked / not verified

- **Live Strix execution**: not observed. Requires a provisioned worker with the pinned
  `v1.7.1` CLI, an approved model/provider, and a permitted staging target. The adapter is
  implemented and contract-tested with a fake CLI only.
- **Sandbox network isolation**: documented topology provided, but not demonstrated on this
  host. Do not enable `LIVE_EXECUTION_ENABLED` until the allowed-target, denied-local, and
  out-of-scope-redirect probes pass on the deployment.
- **Real linked HTTP evidence sample**: contract parser handles `http_exchanges.json`; no real
  `v1.7.1` sample was available, so only its absence handling is verified.
- **DNS pinning/sandbox egress**: resolution is checked, but the connection is not pinned and
  sandbox egress isolation is not demonstrated; require the enforcing gateway/worker boundary.
- **CI has not run remotely** (no remote repository push): the workflow is present and the same
  checks pass locally, but GitHub Actions execution is unverified.
- **A second physical-host deployment is unverified.** The script and Compose path are
  checked locally; another machine still needs an operator run.
- **Pre-migration findings have no historical evidence-review timeline.** Existing findings
  backfilled before the evidence-decisions table fall back to current status before the
  migration timestamp; this is recorded in the migration and ADR-002a.
- **Container rebuild reproducibility** is traded for clean image scans because runtime images
  apply distribution security upgrades; rebuild and rescan per release.
- **Live authenticated exploration** remains disabled; the worker prerequisite probe verifies
  identities without sending them to the model.

## Current deployment (demo pilot)

- URL: `http://100.124.184.116:8088` (Tailscale interface only; not LAN/public)
- Deployed code: `02f86e1` (retention, guided revisions, and portable deployment); images rebuilt and scanned after the change
- Mode: `APP_ENV=staging`, demo records, web bootstrap disabled, API docs disabled,
  live execution disabled. `COOKIE_SECURE=false` because the tailnet origin is plain HTTP;
  path is WireGuard-encrypted. Prefer `tailscale serve` + TLS to enable Secure cookies.
- Credentials: `var/demo-credentials.txt` (mode 600, gitignored); rotate the admin password
  after signing in.
- API, database, and lab are not published; lab is loopback-only.

## Backlog state (2026-11-16)

- TASK-001 foundation: DONE
- TASK-002 security guardrails: DONE locally (audits/static/secret/image clean,
  pinned CI workflow added); CI execution remains unverified until a push.
- TASK-003 live Strix pilot: BLOCKED on external worker/model/target prerequisites.
- Product/demo release: complete for the documented acceptance paths; no known code-side
  blocker for the demo. CI is unverified remotely; live Strix/isolation remain externally
  blocked. Retention, guided-step revisions, reduced-scope retry, and portable deployment are
  implemented.

## Next action

1. Provision the isolated worker and model, pin the Strix image digest, and run the three
   isolation probes in `docs/deployment.md`.
2. Run one live baseline against the controlled lab target; compare its normalized records
   with the fixture contract and record the observed artifact shapes.
3. Run `scripts/verify-isolation.sh` inside the worker network namespace and record the
   allowed/denied/redirect output in the runbook.
4. Add the observed real artifact sample as a regression fixture (sanitized) before enabling
   live mode for the pilot group.
