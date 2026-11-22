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
| — | Hardening and final documentation | Completed | `ca9abd7`, `8c1de93`, `8575884`, `df9d798`, `1c6b039`, `02f86e1`, `2e45425` |

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
- Deployed code: `e65870d` (admin flows, audit pagination, form hardening); web and API images rebuilt
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

## Single-VM live profile (prepared)
Added `compose.mono.yaml` and a live worker image with pinned Strix `v1.7.1`; the worker alone
receives the Docker socket, with resource limits and no-new-privileges. Added
`docs/monodeploy.md`, `.env.live.example`, and `make mono-up`. Live execution has not been
observed; it waits for the operator-supplied `LLM_API_KEY` in `.env.live`. The same-VM socket
is documented as a local-dev compromise; host egress isolation is not enforced without
firewall/root access.

## Live pilot observed (2026-11-18)

The single-VM profile ran a real Strix assessment, not a fixture:

- Target: `http://100.124.184.116:3100` (Kevelry CVE-intelligence console, public read-only).
- Project `local-next-3100`; build `local-3100-2026-11-17`; operator-attested identity
  `local-next-3100` because the target has no `/api/meta`.
- Run `69cbc6dc-a42b-4822-aac6-914b64f9073f`: quick baseline, live mode, unauthenticated,
  reduced-scope acknowledgement.
- Strix `1.7.1` completed in 36m 6s, 111 model requests, 7.9M tokens. The app recorded
  0 findings and 4 tested / 7 not-run plan rows; coverage is incomplete. This is not a
  "4/12 access-control result": the 12 rows are Strix coverage entries plus gap rows, and
  the profile's two required identities were not present. Strix's own report says the target is anonymous-by-design and the requested
  cross-account/tenant classes have no natural target. The app's 4 tested / 7 not-run rows
  are plan-row bookkeeping, not a 4/12 access-control profile result; the run had no
  authenticated identities.
- Real artifacts produced: `run.json`, `coverage.json`, `findings.sarif`,
  `penetration_test_report.md`, `strix.log`; `vulnerabilities.json` is only written when a
  finding exists. The report lists unresolved `/showcase`, batch-vs-detail, method-override,
  and server-component checks.
- JSON and PDF exports generated successfully from the live run.
- The run initially failed because the OpenCode Go endpoint requires
  `x-opencode-session`, the worker image lacked the Docker CLI, and the sandbox image was not
  cached. Those were fixed; the successful rerun used the pinned sandbox image
  `ghcr.io/usestrix/strix-sandbox:1.4.1`.
- `ingest_state` is `partial` for this historical run because it predates the clean-SARIF
  handling. Re-loading the real artifact set with the current loader returns
  `missing=[]`, `status=complete`; re-ingest is now viable but not yet done.

## Open backlog after live pilot

- [ ] Operator accepted the local-only same-VM socket risk and rejected a separate VM.
      Do not expose this host publicly; use only authorized local targets.
- [ ] Close the one real coverage gap by manual replay of the batch/detail comparison. The
      other six gaps are bookkeeping/`unrecorded_risk_class`, not six untested surfaces.
- [ ] Run the profile against the synthetic lab with two identities, fixtures, and an owner
      positive control. `:8501` has no account/login surface and is not an access-control
      target.
- [ ] Re-ingest the historical live run with the current loader; the real artifacts now
      return `status=complete`, so the old `partial` result is not structural.
- [ ] Rotate the operator's OpenCode Go key after the pilot; it was used from the exposed
      chat value and must not be treated as a long-term secret.
- [ ] Resolve or formally triage the npm `picomatch` ReDoS advisory (dev-only, no patched
      version in the current Vite line).

## Research correction (2026-11-18)

Research `docs/research/2026-11-18-monodeploy-next-steps.md` verified five backlog claims
against the artifacts and primary sources:

- The seven gaps are **one** unexecuted test plus six `unrecorded_risk_class` bookkeeping
  gaps (one agent recorded no coverage); six app `not_run` rows have an empty surface.
- Gap 1 was blocked by the sandbox proxy, which returned a 9,088-byte Caido error page for
  every request; the hypothesis still needs a manual two-request replay.
- The sandbox runs on Docker's default bridge with `NET_ADMIN`/`NET_RAW`,
  `host.docker.internal`, and no host firewall. `:8501` is published on `0.0.0.0`; the
  host runs other stacks. The socket worker was stopped as a result.
- A clean Strix 1.7.1 run has no `vulnerabilities.json`; the current loader treats a
  coverage-only SARIF as clean and returns `status=complete` on the real artifacts.
- npm GHSA-fc5q-39xc-vjpf has no patched `picomatch`; Vite 8 still uses `^4.0.7`.
  This is a documented dev-only deferral, not a green security gate.

The next profile-faithful target is the **synthetic lab** (6 accounts, 3 tenants, owned
invoices, export and two-actor approval), not `:8501`, which has no account/login surface.

## User guide delivered (2026-11-20)

- Canonical Markdown lives in `web/src/content/guide/guide/` (16 pages); GitHub reads the same
  files, and `docs/user-guide.md` is a pointer rather than a copy.
- The SPA renders it at `/guide` and `/guide/:slug` with a dependency-free parser, a grouped
  index, search, an on-page TOC, previous/next links, author-controlled heading anchors, and
  page titles. No new dependency and no CSP change.
- `web/e2e/guide.spec.ts` checks manifest/file one-to-one, parser problems, H1/heading rules,
  anchors and links, app-route coverage, UI-label drift, table captions, size budget, search,
  TOC focus, axe, and 320/390 px reflow.
- Verification: typecheck/build pass; 16 guide Playwright tests pass against the deployed
  `http://100.124.184.116:8088`. The guide is public at `/guide`; the login page links to it.
- Brand assets: proof-tag mark and wordmark, SVG favicon, Apple touch icon, 192/512 icons, and
  web manifest in `web/public/`; the app header, login card, and public guide share the mark.
- Installation remains separate in `docs/deploying-elsewhere.md`, `docs/deployment.md`, and
  `docs/monodeploy.md`.

## Guide UI revamp (2026-11-21)

- Replaced the card-stack guide index with a docs layout: persistent grouped sidebar,
  task-oriented start path, compact directory, and inline search.
- Guide pages now use a three-column reading layout (sidebar, 68ch article, sticky TOC) on
  desktop and a disclosure-based page menu with a mobile TOC on narrow screens.
- Added active TOC tracking, page-level Previous/Next navigation, sentence-case table
  headers, and table separator parsing coverage.
- The public guide is reachable without sign-in and linked from the login screen.
- Added the proof-tag brand mark, wordmark, favicon, Apple touch icon, install icons, and
  web manifest.
- Desktop and mobile screenshots: `docs/screenshots/guide-index-desktop.png`,
  `guide-page-desktop.png`, `guide-page-mobile.png`.
- Verification: web typecheck/build pass; 16 guide Playwright tests pass, including public
  access, favicon, search, axe, TOC focus, table parsing, and 320/390 px index/page reflow.

## Annotated guide figures (2026-11-22)

Five high-value workflow screens now carry numbered, boxed screenshots with real-text captions:

- `images/where-things-live/01-navigation-and-tabs.png`
- `images/queue-run/01-preflight-reduced-scope.png`
- `images/read-report/01-risk-and-coverage.png`
- `images/retest/01-retest-panel.png`
- `images/compare/01-run-selection-and-buckets.png`

The Markdown stays plain: an image followed by a bold `**Figure N.**` caption, readable on
GitHub; the SPA upgrades the pair to a semantic `<figure>` and loads 1x/2x PNGs through Vite.
Assets are stored beside the guide, not in `web/public`, so one relative path works in both
renderers. The images use demo data only and carry numbered boxes; the real-text captions
explain each number.

Capture is repeatable with `web/scripts/capture-guide-screenshots.mjs` against the local demo
fixture. The script refuses to run without the demo banner. It uses 2x Playwright captures,
ImageMagick for crop/compression, and writes `figureMeta.ts` from the PNG headers. No new
dependency, no CSP change, and no external image host.

Verification: web typecheck/build pass; 16 guide Playwright tests pass, including public access,
figure alt/dimensions/2x sources, route/label drift, search, axe, TOC focus, and 320/390 px
reflow.

## Usability corrections (2026-11-22)

- **Project creation discoverability:** administrators now get a **New project** action on the
  **Projects** page; it opens the existing registration dialog via `/admin?new=project`.
  Non-administrators see a clear instruction to ask an installation administrator. The server
  remains admin-only.
- **Environment semantics:** `staging` is the configured `APP_ENV` deployment label, not a
  production parity guarantee. The top-bar tooltip, Settings page, deployment guide, and user
  guide now say this explicitly.
- **Settings spacing:** the worker counters, recent-jobs table, and notices now sit in a
  consistent `worker-status` stack; the active-run summary no longer crowds the table.
- Verification: web typecheck/build pass; full guide suite 16 passed; the two focused project
  creation/role tests passed against the deployed app.

## Production transition check (2026-11-22)

The deployed app remains `APP_ENV=staging`. A production label was not applied because the
current deployment is not production-safe:

- With the current plain-HTTP/`COOKIE_SECURE=false` settings, `APP_ENV=production` fails closed
  with `COOKIE_SECURE cannot be false in production`; this is intentional.
- A production configuration with secure cookies and demo disabled can be instantiated, but
  the host still has the worker's root-equivalent Docker socket, the npm audit gate is red,
  and no production TLS endpoint or isolated worker exists.
- Production therefore requires a separate deployment with TLS, secure cookies, a separate
  database/secret, no demo/lab, a dedicated or strictly egress-controlled worker, and a green
  security/CI release check. The staging label is not a 1:1 production guarantee.

Project creation remains installation-administrator-only. Operators manage builds, runs,
retests, recipes, and verdicts within projects; they do not create projects or installation
accounts. This is server-enforced, not just hidden UI.

## Admin flow and audit pagination (2026-11-22)

- The Admin page now supports paginated audit events (20 per page) with Previous/Next controls
  and a total count.
- Account creation supports multiple project/role rows; installation administrator is an
  explicit opt-in and bypasses project memberships.
- Admins can reset another account's password, replace project access, disable/enable accounts,
  and grant/remove admin with confirmation dialogs. The server still enforces self-protection
  and admin authorization.
- Project creation is available directly on the Projects page for admins; the project dialog
  uses dynamic origin/path-prefix rows instead of comma-separated text.
- Fixed target origin normalization so a trailing slash or an empty origin list uses the
  normalized base origin.
- Fixed shared form-error leakage between account and project dialogs.
- Updated Admin/Projects screenshots: `admin-desktop.png`, `admin-mobile.png`,
  `admin-project-dialog.png`, `admin-account-dialog.png`, `projects-desktop.png`.
- Verification: backend 107 passed; web typecheck/build pass; full browser suite 18 passed
  and guide suite 16 passed against the deployed app.
