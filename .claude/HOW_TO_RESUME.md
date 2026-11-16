# How to Resume

Run these steps in order. Baseline discovery is read-only; do not install dependencies,
start services, or mutate runtime state without established environment and approval.
At bootstrap there is no Git repository or application tooling: report absence honestly.

1. **Confirm context.** Root CLAUDE.md plus AGENT_RULES, CODING_STANDARDS,
   SECURITY_STANDARDS, and state/CURRENT_STATUS must be visible. Check `/context`
   (or `/context all`); manually read missing files.
   Outside Claude Code, use root AGENTS.md and the loading checks in `.agents/README.md`;
   do not assume Claude import syntax or slash commands exist in the active host.
2. **Select task.** Read `.claude/state/TASK_QUEUE.md`; identify the next task and
   dependencies. Foundation requires the user's purpose/stack confirmation.
3. **Identify environment.** Consult ENVIRONMENT_GUIDE.md. Inspect only the active
   non-secret APP_ENV selector and safe target metadata, never real `.env` files or
   environment dumps. Unknown means production-safe handling; no runtime actions.
4. **Check Git.** When Git exists, use `git status --short --branch`,
   `git branch --show-current`, and `git log -5 --oneline` (only if commits exist).
   Preserve uncommitted work. If absent/unborn, report it; ask before initialization.
5. **Read relevant docs.** Locate PRD, architecture, API contract, and decisions if
   present; record real document paths in root CLAUDE.md as they are created.
6. **Verify environment.** Health-check/startup command: **not yet defined**. Consult
   root CLAUDE.md Commands; after setup, replace this slot with verified safe commands.
   Run a health check only for a confirmed permitted target. Ask before startup or
   changes where required; never start production. Report missing setup as unavailable.
7. **Run baseline tests.** Full-suite command: **not yet defined**. Once known, use
   the documented command in an isolated development/test target with fake/dedicated
   test credentials. Record exit/result; missing tooling is not a passing baseline.
8. **Plan.** State scope, files, risks, and verification. Obtain confirmation for
   architectural, schema, dependency, infrastructure, security, or UX-impacting choices.
9. **Implement.** Use the matching `.claude/templates/` checklist and standards;
   preserve the baseline, stay within scope, stop on regression or security blockers.
10. **Verify.** Run tests, lint, type checks, and the Security Gate. Check development
    and production configuration locally; report N/A/unverified with reasons.
11. **Wrap up.** Update state and affected docs together in one write step before
    final response; `/wrap-up` performs the AGENT_RULES checklist. Report refused writes.

## Verified command references
| Check | Command |
|---|---|
| Development startup | `make db`, `make lab`, `make api`, `make worker`, `make web` (or `make dev`) |
| Health check | `curl -fsS http://127.0.0.1:8000/api/health` |
| Full test suite | `cd backend && .venv/bin/python -m pytest` (95 tests) |
| Lint / format check | `make lint` |
| Type check | `cd backend && .venv/bin/mypy app`; `cd web && npm run typecheck` |
| Browser E2E | `cd web && npx playwright test` (lab/API/worker + seeded demo) |
| Secret scan / dependency audit / static analysis | not yet configured; propose via TASK-002 |
| Migrations | `cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic check` |
| Demo seed | `make demo` (idempotent; lab must be running) |

`/resume` performs only steps 1–7, reports in fewer than 15 lines, and waits for user
confirmation before implementation. It must not silently perform foundation setup.
