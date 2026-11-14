# Project Context

## Project Snapshot
- Purpose: Not yet defined. Update after the first working session.
- Stack: Not yet defined. Update after the first working session.
- Phase: Agent infrastructure initialized; no product code exists.

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
These are reference slots, not executable commands. Fill them with verified commands
when the stack exists; never guess or install tooling just to populate this table.

| Action | Command |
|---|---|
| Build | not yet defined |
| Test (single full-suite command) | not yet defined |
| Lint | not yet defined |
| Format check | not yet defined |
| Type check (where supported) | not yet defined |
| Run (development) | not yet defined |
| Health check | not yet defined |

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
| Product requirements, architecture, API contracts | Project docs when created; record their actual paths here |

## Maintenance Rules for This File
- Keep under about 150 lines (prefer under 120); link instead of duplicating detail.
- Correct inaccuracies immediately; update Snapshot and Commands as facts become known.
- Keep exactly the four essential imports above; deeper docs load on demand.
- Follow the no-weakening guardrail in `AGENT_RULES.md` for instruction or permission changes.
