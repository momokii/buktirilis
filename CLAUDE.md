# Project Context

## Project Snapshot
- Purpose: BuktiRilis — self-hosted security testing workspace (Strix OSS engine) with
  projects, builds, runs, evidence, retests, release comparison, and frozen exports.
- Stack: React 19 + TypeScript + Vite; Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic;
  PostgreSQL 16; Docker Compose; synthetic FastAPI lab; Playwright + axe-core.
- Phase: First internal release implemented and deployed as a demo pilot on the Tailscale
  address 100.124.184.116:8088 (Compose, APP_ENV=staging). Live Strix execution wired but
  unobserved. See `docs/progress.md`.

## Always-Loaded Context
@.claude/AGENT_RULES.md
@.claude/CODING_STANDARDS.md
@.claude/SECURITY_STANDARDS.md
@.claude/state/CURRENT_STATUS.md

## Session Protocol (summary)
1. Confirm this file and all four imports loaded; read any missing context manually.
2. Read `.claude/state/TASK_QUEUE.md` and `.claude/HOW_TO_RESUME.md`.
3. Identify the active environment before commands; read `.claude/ENVIRONMENT_GUIDE.md`.
   Unknown means production-safe handling. Never run against production.
4. Check branch, uncommitted changes, and recent commits; preserve existing work.
5. Read relevant project docs; verify environment health and the existing test baseline.
   If commands or Git do not exist, report that explicitly rather than inventing results.
6. Plan scope, files, risks, and verification; obtain required confirmations.
7. Implement within scope using the matching checklist; verify tests, lint, types,
   development/production configuration behavior, and the Security Gate.
8. Wrap up at every completed or paused task: batch state and instruction updates
   into one write step before the final response. Report blocked writes.

## Commands
Verified in this environment (see `docs/progress.md` for results):

| Action | Command |
|---|---|
| Install | `make install` (uv sync + npm ci) |
| Local database | `make db` (PostgreSQL 16 container, 127.0.0.1:55432) |
| Migrate | `make migrate` or `cd backend && .venv/bin/alembic upgrade head` |
| Demo seed | `make demo` (lab must be running) |
| Run everything | `make dev` (lab :8099, API :8000, worker, Vite :5173) |
| Health check | `curl -fsS http://127.0.0.1:8000/api/health` |
| Backend tests | `cd backend && .venv/bin/python -m pytest` (95 tests) |
| Lint / format | `make lint` |
| Type check | `make typecheck` |
| Web build | `cd web && npm run typecheck && npm run build` |
| Browser E2E | `cd web && npx playwright test` (requires lab/API/worker + seeded demo) |
| Deploy (single host) | `make deploy` (reads `.env`; binds web to `WEB_BIND:WEB_PORT`) |
| Deployed status | `make deploy-status` |
| Install browser | `cd web && npx playwright install chromium` |

## On-Demand References
Paths below are references, not imports.
For other coding agents, root `AGENTS.md` supplies the shared startup contract.

| When you need | Read |
|---|---|
| Next task, dependencies, acceptance criteria | `.claude/state/TASK_QUEUE.md` |
| Decision rationale and established patterns | `.claude/state/DECISIONS_LOG.md` |
| Environment identification, configuration, Compose | `.claude/ENVIRONMENT_GUIDE.md` |
| Full startup and baseline protocol | `.claude/HOW_TO_RESUME.md` |
| Feature, endpoint, test, or bug-fix checklist | Matching file in `.claude/templates/` |
| Infrastructure map and permission limitations | `.claude/README.md` |
| Cross-tool discovery, native controls, trust, and shared workflows | `.agents/README.md` |
| Earlier session outcomes | `.claude/state/HISTORY.md` |
| Product requirements and current milestone state | `docs/progress.md` |
| Strix contract, artifacts, exit codes, demo/live boundary | `docs/strix-contract.md` |
| Decisions and rationale | `docs/decisions.md` |
| Deployment, isolation, backup/restore, rotation | `docs/deployment.md` |
| Product and demo walkthrough | `README.md` |

## Maintenance Rules for This File
- Keep under about 150 lines (prefer under 120); link instead of duplicating detail.
- Correct inaccuracies immediately; update Snapshot and Commands as facts become known.
- Keep exactly the four essential imports above; deeper docs load on demand.
- Follow the no-weakening guardrail in `AGENT_RULES.md` for instruction or permission changes.
