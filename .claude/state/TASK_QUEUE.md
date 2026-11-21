# Task Queue

Work in this order once dependencies are satisfied. Obtain user confirmation for
purpose/stack before TASK-001; perform it as part of or immediately before the first
real task. Do not install a stack merely because the queue contains foundation work.

## TASK-001: Establish project foundation
| Field | Value |
|---|---|
| Task ID | TASK-001 |
| Name | Establish project foundation |
| Priority | High |
| Status | DONE |
| Complexity | M |
| Depends On | User confirmation of purpose and stack (provided by the BuktiRilis brief) |
| Scope | Confirm purpose/stack; initialize Git only with authorization if still absent; extend .gitignore; configure formatter, linter, type checker where supported, and test tooling; establish Compose dev/prod pattern if containerized. Specialize CODING_STANDARDS, SECURITY_STANDARDS, ENVIRONMENT_GUIDE, HOW_TO_RESUME commands, CLAUDE.md Snapshot/Commands, and README. Propose a narrow stack-specific settings.json allow-list and obtain confirmation before adding. |
| Acceptance Criteria | One verified command each to run, test, lint, and health-check; format/type checks documented where applicable; all .claude files reflect the real stack; local tests cover development/production config and missing/unknown APP_ENV; no production access. |
| Security Concerns | Legitimate pinned/audited dependencies; reviewed install scripts; isolated dev target; fail-closed configuration; no secret reads or security weakening. |

## TASK-002: Add automated security guardrails
| Field | Value |
|---|---|
| Task ID | TASK-002 |
| Name | Add automated security guardrails |
| Priority | High |
| Status | DONE (local); CI unverified |
| Complexity | M |
| Depends On | TASK-001 and explicit user confirmation (given 2026-11-16) |
| Scope | Propose and, with confirmation, add pre-commit secret scanning, dependency audit, static analysis, image scanning if containerized, CI running tests/lint/types/scans, and dependency update tooling. Document commands and findings policy. |
| Acceptance Criteria | Approved checks run locally and in CI as applicable; safe synthetic negative cases demonstrate gates fail on violations; lockfile installs reproducible; applicable scans clean or findings explicitly triaged; no real secrets used to test scanners. |
| Security Concerns | Least-privilege CI tokens; trusted pinned actions/tools; no credentials in artifacts/logs; hooks cannot be silently bypassed; edits to protected hook/config files require expected approval. |

## TASK-003: Provision and verify the live Strix pilot
| Field | Value |
|---|---|
| Task ID | TASK-003 |
| Name | Provision and verify the live Strix pilot |
| Priority | High |
| Status | BLOCKED |
| Complexity | L |
| Depends On | TASK-001; isolated worker host; approved model provider; pinned Strix image |
| Scope | Pin the Strix v1.7.1 image digest; configure model/provider on the worker; prove allowed-target, denied-local, and out-of-scope-redirect probes; run one live baseline against the controlled lab; sanitize and add the observed artifact sample as a fixture. |
| Acceptance Criteria | Live run observed with normalized artifacts matching the contract; isolation probes pass; no credential values in records/exports; deployment runbook records version, digest, and probe evidence. |
| Security Concerns | Deny-by-default egress; no control-plane/metadata reachability; short-lived test credentials; unconfirmed sandbox cleanup blocks redispatch. |

## Completed application work
- [x] Foundation, schema/migrations, auth/CSRF/rate limits, audit and role enforcement
- [x] Approved scope, builds, OpenAPI validation, identity observation/attestation
- [x] Run lifecycle, preflight, demo fixtures, worker lease, cancellation, interruption
- [x] Evidence, replay recipes, guided retests, review acceptance, comparison, exports
- [x] 100 backend tests, 14 Playwright tests, axe scan, fresh-seed and PDF/CSV/JSON verification
- [x] Documentation and reproducible demo walkthrough
- [x] Security guardrails: pip-audit, npm audit, Bandit, detect-secrets baseline, Trivy, pinned CI
- [x] Worker prerequisite probes, evidence-decision history, surface-absent reasons, OpenAPI diff

## Completed infrastructure work
- [x] Initial Claude Code bootstrap and readiness recheck
- [x] Cross-tool portability: AGENTS.md, native adapters, Pi hook, and shared workflow skills
- [x] 34-file/static/schema checks, native host diagnostics, and 12 Pi safety tests

## Bootstrap follow-up (user sessions)
Local cross-tool checks passed: 34 files, four imports/context budgets, valid JSON/TOML,
published schemas, actual Git ignore matching, and targeted content-hygiene checks.
Full secret scanning is unverified until an approved scanner is available (TASK-002).
Run `/context` (or `/context all`) and inspect `/permissions` after opening Claude Code
here. Confirm all four imports and each shared rule source; check the `/` command menu.
Restart OpenCode to load opencode.json. In Codex/Pi, review and trust project resources
through their normal UI and verify actual instruction loading, native controls, and
workflow discovery. Pi's project-policy extension must be active. Verify effective
permissions with synthetic non-secret fixtures; see `.agents/README.md`.
These are interactive acceptance checks, not instructions to edit personal settings
or bypass a refused trust decision. API-only clients need explicit context/tool integration.

## Template for every new task
| Field               | Value                                               |
|---------------------|-----------------------------------------------------|
| Task ID             | TASK-XXX                                            |
| Name                | [Task name]                                         |
| Priority            | High / Medium / Low                                 |
| Status              | TODO / IN PROGRESS / DONE / BLOCKED                 |
| Complexity          | S / M / L                                           |
| Depends On          | [Task IDs]                                          |
| Scope               | [Exact description of what must be built]           |
| Acceptance Criteria | [Measurable definition of done]                     |
| Security Concerns   | [Security considerations for this task]             |

## TASK-004 — single-VM live Strix pilot (2026-11-18)
Status: DONE for the first run; follow-ups open.

- Live target: `http://100.124.184.116:3100` (Kevelry, anonymous public read-only).
- Run: `69cbc6dc-a42b-4822-aac6-914b64f9073f`; Strix 1.7.1 quick baseline; 36m 6s;
  111 model requests; 0 findings; 4 tested / 7 not-run plan rows. This was adapter evidence,
  not a 4/12 access-control profile result; the run had no identities.
- Fixed to get there: OpenCode Go `x-opencode-session` header, Docker CLI in the worker,
  pinned sandbox image `ghcr.io/usestrix/strix-sandbox:1.4.1`, `STRIX_LLM`/`LLM_API_BASE`
  child-process passthrough, clean-SARIF handling.
- Worker is running; the operator accepted the local-only same-VM socket risk and rejected
  a separate VM. Do not expose the host publicly.
- Follow-ups: manual batch/detail replay (the one real gap); synthetic-lab run with two
  identities; re-ingest the now-loadable historical run; npm dev-only deferral; rotate key.
  Do not use `:8501` for access-control coverage; it has no account surface.

## TASK-005 — single-VM boundary decision (2026-11-18)
Status: ACCEPTED LOCAL-ONLY; worker running.

Research found the sandbox is on the default bridge with NET_ADMIN/NET_RAW,
host.docker.internal, and no host firewall; the host runs other stacks and :8501 is published
on 0.0.0.0. The socket-bearing worker was stopped. Choose dedicated VM or isolated lab-only
network, then probe inside the sandbox network before restarting.

## TASK-006 — end-to-end user guide (2026-11-20)
Status: DONE.

- Canonical Markdown in `web/src/content/guide/guide/` (16 pages), rendered in-app at
  `/guide` by a dependency-free parser and readable on GitHub; `docs/user-guide.md` is a
  pointer. Installation remains in the deployment documents.
- Verification: web typecheck/build pass; 14 guide Playwright tests pass, including public
  access from login, content drift checks, search, TOC focus, axe, favicon, and 320/390 px
  reflow.
- Follow-up: update the guide and `anchors.ts` whenever a route, UI label, status, or retest
  path changes.

## TASK-007 — guide UI revamp (2026-11-21)
Status: DONE.

- Persistent grouped guide sidebar and public access; three-column desktop reading layout;
  mobile page menu and TOC; task-oriented index/search; active TOC.
- Fixed the parser so table header separators never render as data.
- Added desktop/mobile screenshots and reflow tests for both index and page.
- Verification: web typecheck/build pass; 14 guide Playwright tests pass.
