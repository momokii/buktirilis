# Session History

Append-only: add dated summaries at task boundaries. Preserve earlier entries; current
state belongs in CURRENT_STATUS.md, task details in TASK_QUEUE.md, rationale in DECISIONS_LOG.md.

## 2026-11-14 — Infrastructure bootstrap
Inspected an empty directory with no existing target files or Git repository. Created
the requested general-purpose Claude Code infrastructure, root context imports, shared
permission baseline, safe configuration template, ignore rules, lifecycle commands,
state records, and four implementation checklists. Checked official documentation for
imports, permissions, protected paths, and legacy command-file support. No product
stack, runtime, dependency, Compose setup, or automated guardrail tool was selected.

Key outcomes:
- Security Gate, dev/prod discipline, no-weakening policy, and batch wrap-up established.
- Foundation and automated guardrail work queued conditionally on user confirmation.
- Interactive `/permissions`, `/context`, and command-menu acceptance remain for the
  user's Claude Code session; application checks have no tooling yet.
- Bootstrap structural/hygiene checks are separate from future application/security
  automation; report executed verification evidence rather than assuming success.

Verification: the local bootstrap validator exited successfully for 21 non-empty
files, exactly four resolvable plain-text imports, and context budgets (CLAUDE.md 60,
AGENT_RULES 87, CODING_STANDARDS 51, SECURITY_STANDARDS 125 lines). Settings parsed
with 6 allow / 11 ask / 49 deny rules and no defaultMode. An isolated temporary Git
fixture verified 14 ignored private paths and four visible shared paths, without
initializing this project. Targeted credential/personal-data/machine-path checks had
no matches. No dedicated secret scanner is installed; full secret scanning remains
unverified. Application tests/lint/types are N/A without product code/tooling.

## 2026-11-14 — Development readiness recheck
Re-read the entry point, imported policies, lifecycle commands, environment guide,
and task queue, then reran the local bootstrap validator successfully. All 21 files,
four imports/context budgets, permission JSON, actual ignore behavior, and targeted
hygiene checks passed again. Confirmed Git remains uninitialized and APP_ENV is
unset; no application runtime exists. Clarified in README that Claude Code permission
settings do not establish enforcement in another harness such as OpenCode.

Key outcomes: the general agent scaffold is ready for the first foundation task;
purpose/stack confirmation, Git authorization, stack-specific quality tooling and
approved security automation remain future work. Interactive Claude Code acceptance
and a dedicated secret scan remain unverified; no claim of full runtime readiness.

## 2026-11-14 — Cross-tool agent portability
Extended the shared infrastructure for Claude Code, OpenAI Codex, OpenCode, Pi,
and other AGENTS.md-aware/API clients. Added root AGENTS.md, a human README,
native OpenCode and Codex adapters, a trusted Pi context/approval extension, three
portable skills referencing existing procedures, and reproducible infrastructure
verification. Preserved the original Claude permission baseline and extended shared
rules without weakening them. No product stack, model/provider override, new package
installation, global/personal configuration change, or real-project Git initialization.

Key verification outcomes: 34 known files/imports/budgets/JSON/TOML/hygiene checks
passed; actual Git matcher excluded 12 private paths and retained five shared paths;
12 Pi safety tests passed; installed Codex discovered AGENTS.md and evaluated eight
command-policy cases without executing those commands; installed OpenCode retained
five instruction paths/workflows and nine deny/ask/allow fixtures; installed Pi
discovered AGENTS.md and loaded all three extension hooks. OpenCode and Codex config
validated against official schemas retrieved during the task. A direct downloader
later returned HTTP 403; used the previously retrieved copies without retrying access.

Remaining acceptance: restart OpenCode; use each host's normal trust flow and inspect
actual loaded context, effective permissions, workflows, and approval UI. Raw API
clients require explicit file/tool integration. Dedicated secret scanning and the
product foundation/automated guardrail tasks remain pending. Prefix rules and Pi
approval hooks do not provide universal OS-level secret isolation.


## BuktiRilis first internal release (2026-11-14)
Built the full application from a greenfield repository: FastAPI API and worker, PostgreSQL
schema with migrations, React/TypeScript browser workspace, synthetic staging lab, demo seed,
PDF/CSV/JSON frozen exports, release comparison, and both retest paths. Enforced server-side
roles, CSRF, login rate limits, encrypted test credentials, target allowlists, redirect
re-validation, and worker lease reconciliation.

Verification: 97 backend tests (real HTTP against the lab), ruff and mypy clean, web
typecheck/build clean, 14 Playwright tests at 1440 px and 390 px including an axe-core scan,
fresh-database migrate + seed producing 3 runs and 4 exports, PDF 6 pages with limitations,
CSV/JSON agreeing and free of credential values, and compose config valid for base + demo
profiles. Remaining: live Strix execution and sandbox isolation were not observed; the
adapter is contract-tested with a fake CLI and live mode is disabled by default.

## Demo pilot deployment (2026-11-15)
Built and started the single-host Compose stack (db, api, worker, web, demo lab) with
`APP_ENV=staging`; seeded the synthetic demonstration and bound the web container only to
the Tailscale address `100.124.184.116:8088`. Verified health, login, report data, CSRF
rejection, PDF/JSON export downloads, security headers, disabled API docs, worker retest
execution, restart persistence, and the full 11-test Playwright suite against the deployed
URL (including axe and 390 px). API, database, and lab are not published externally.

## Post-review hardening (2026-11-15)
Fixed review findings: queued-run cancellation now terminates without waiting for a worker;
queued retests re-check current target policy, requester access, recipe approval, and finding
disposition; comparisons and new exports use the selected run snapshot while later evidence
is labelled separately; completed runs no longer grow finding membership from later evidence;
cross-mode comparisons return no buckets; guided changes-requested states report the reason.
Backend tests 85, browser tests 12.

## Hardening backlog completed (2026-11-16)
Added worker-side identity/fixture prerequisite probes, append-only evidence decisions with
snapshot-as-of comparison semantics, explicit surface-absent reasons, OpenAPI operation-diff
discovery candidates, active-only job idempotency, and the approved security guardrails
(pip-audit, npm audit, Bandit, detect-secrets baseline, Trivy image scan, pinned CI actions).
Dependency upgrades cleared known CVEs; image scans are clean. Research and guardrail
runbooks added. Final checks: 97 backend tests, 14 browser tests against the deployed tailnet
URL, fresh-database seed, and restart persistence. Live Strix execution remains blocked on
worker/model/target provisioning.

## Second review remediation (2026-11-16)
Addressed the two-axis review findings: operator-selected discovery routes end to end,
baseline fixture probes, blocked-scenario reporting, segment-aware route matching, safer
probe error handling, corrected evidence backfill timestamps, active-only idempotency,
and added tests for the passing probe/operator-route/template paths. Final checks: 97
backend tests, 14 browser tests against the deployed tailnet URL, image scan clean.
