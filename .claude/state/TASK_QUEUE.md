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
| Status | BLOCKED |
| Complexity | M |
| Depends On | User confirmation of purpose and stack |
| Scope | Confirm purpose/stack; initialize Git only with authorization if still absent; extend .gitignore; configure formatter, linter, type checker where supported, and test tooling; establish Compose dev/prod pattern if containerized. Specialize CODING_STANDARDS, SECURITY_STANDARDS, ENVIRONMENT_GUIDE, HOW_TO_RESUME commands, CLAUDE.md Snapshot/Commands, and README. Propose a narrow stack-specific settings.json allow-list and obtain confirmation before adding. |
| Acceptance Criteria | One verified command each to run, test, lint, and health-check; format/type checks documented where applicable; all .claude files reflect the real stack; local tests cover development/production config and missing/unknown APP_ENV; no production access. |
| Security Concerns | Legitimate pinned/audited dependencies; reviewed install scripts; isolated dev target; fail-closed configuration; no secret reads or security weakening. |

## TASK-002: Add automated security guardrails
| Field | Value |
|---|---|
| Task ID | TASK-002 |
| Name | Add automated security guardrails |
| Priority | High |
| Status | BLOCKED |
| Complexity | M |
| Depends On | TASK-001 and explicit user confirmation of proposed guardrails |
| Scope | Propose and, with confirmation, add pre-commit secret scanning, dependency audit, static analysis, image scanning if containerized, CI running tests/lint/types/scans, and dependency update tooling. Document commands and findings policy. |
| Acceptance Criteria | Approved checks run locally and in CI as applicable; safe synthetic negative cases demonstrate gates fail on violations; lockfile installs reproducible; applicable scans clean or findings explicitly triaged; no real secrets used to test scanners. |
| Security Concerns | Least-privilege CI tokens; trusted pinned actions/tools; no credentials in artifacts/logs; hooks cannot be silently bypassed; edits to protected hook/config files require expected approval. |

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
